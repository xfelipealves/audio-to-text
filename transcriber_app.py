"""Portuguese desktop transcription; --demo never touches audio dependencies."""

import argparse
from datetime import datetime
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from transcription_history import (
    HistoryError, HistoryStore, default_history_path, markdown_record, new_record,
    write_markdown,
)

DEMO_TEXTS = (
    "Esta é uma nota fictícia para demonstrar o aplicativo. Vamos organizar as "
    "ideias do projeto, revisar o backlog e preparar uma apresentação em português.",
    "Reunião fictícia de planejamento: a próxima etapa é revisar o design da "
    "interface e documentar as decisões. Os termos técnicos, como deploy e code "
    "review, devem permanecer em inglês quando fizer sentido.",
    "Lembrete fictício: separar trinta minutos para escrever, revisar o texto e "
    "exportar a nota em Markdown. Nenhum microfone foi utilizado nesta demonstração.",
)


class MicrophoneRecorder:
    """Created only after an explicit recording action outside demo mode."""

    def __init__(self) -> None:
        import numpy as np
        import sounddevice as sd

        self._np = np
        self._sd = sd
        self._frames = []
        self._stream = None
        self._audio_status = ""

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            self._audio_status = str(status)
        self._frames.append(indata.copy())

    def start(self) -> None:
        self._frames = []
        self._audio_status = ""
        stream = self._sd.InputStream(
            samplerate=16000, channels=1, dtype="float32", callback=self._callback,
        )
        try:
            stream.start()
        except Exception:
            stream.close()
            raise
        self._stream = stream

    def stop(self):
        stream = self._stream
        if stream is None:
            return self._np.array([], dtype=self._np.float32)
        try:
            stream.stop()
        finally:
            try:
                stream.close()
            finally:
                self._stream = None
        frames, self._frames = self._frames, []
        if self._audio_status:
            raise RuntimeError(f"Captura de áudio incompleta: {self._audio_status}")
        if not frames:
            return self._np.array([], dtype=self._np.float32)
        return self._np.concatenate(frames, axis=0).flatten()


class SpeechTranscriberApp:
    BG = "#f4f5f7"
    INK = "#182736"
    MUTED = "#596777"

    def __init__(self, root: tk.Tk, demo: bool = False) -> None:
        self.root = root
        self.demo = demo
        self.recorder = None
        self.model = None
        self.events = queue.Queue()
        self._closing = threading.Event()
        self._capture_released = threading.Event()
        self._capture_released.set()
        self._worker_thread = None
        self._poll_id = None
        self._timer_id = None
        self._started_at = None
        self._demo_index = 0
        self.state = "ready"
        self.store = HistoryStore(default_history_path(demo), demo)
        self.records = list(self.store.records)
        self.current = None
        self._unsaved_ids = set()
        self.root.title("Audio to Text" + (" · Demonstração fictícia" if demo else ""))
        self.root.geometry("1000x680")
        self.root.minsize(800, 540)
        self.root.configure(bg=self.BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._build_ui()
        self._refresh_history()
        if self.records:
            self._select_record(self.records[0])
        self._set_state("ready")
        if self.store.warning:
            self.notice.configure(text=self.store.warning)
            self._set_state("error", "Histórico indisponível · você ainda pode transcrever e exportar.")
        self._poll_id = self.root.after(80, self._poll_events)

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.INK, font=("Helvetica", 12))
        style.configure("Title.TLabel", font=("Helvetica", 25, "bold"))
        style.configure("Muted.TLabel", foreground=self.MUTED, font=("Helvetica", 11))
        style.configure("TButton", padding=(12, 9), font=("Helvetica", 11))
        style.configure("Accent.TButton", background="#205c75", foreground="white")
        style.map("Accent.TButton", background=[("active", "#17475c"), ("disabled", "#d7dce2")],
                  foreground=[("disabled", "#596777")])
        style.configure("Treeview", rowheight=55, font=("Helvetica", 11),
                        background="white", fieldbackground="white", foreground=self.INK)
        style.map("Treeview", background=[("selected", "#dcecf3")],
                  foreground=[("selected", self.INK)])
        container = ttk.Frame(self.root, padding=24)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="Da voz ao texto.", style="Title.TLabel").pack(anchor="w")
        subtitle = ("DEMONSTRAÇÃO FICTÍCIA · nenhum microfone ou modelo é utilizado"
                    if self.demo else "Notas em português, transcritas no seu computador.")
        ttk.Label(container, text=subtitle, style="Muted.TLabel").pack(anchor="w", pady=(6, 16))
        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(0, 12))
        self.toggle_button = ttk.Button(controls, style="Accent.TButton", command=self.toggle_recording)
        self.toggle_button.pack(side="left")
        self.status_label = ttk.Label(controls, wraplength=480)
        self.status_label.pack(side="left", padx=18)
        self.progress = ttk.Progressbar(container, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 12))
        self.notice = ttk.Label(container, text="", foreground="#975321", wraplength=880)
        self.notice.pack(fill="x", pady=(0, 10))
        body = ttk.Frame(container)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(body, width=270)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        ttk.Label(sidebar, text="Histórico", font=("Helvetica", 14, "bold")).pack(anchor="w")
        self.history_count = ttk.Label(sidebar, style="Muted.TLabel")
        self.history_count.pack(anchor="w", pady=(4, 12))
        history_frame = ttk.Frame(sidebar)
        history_frame.pack(fill="both", expand=True)
        self.history = ttk.Treeview(history_frame, show="tree", selectmode="browse", height=6)
        self.history.column("#0", width=250, minwidth=200, stretch=True)
        self.history.pack(side="left", fill="both", expand=True)
        history_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.history.yview)
        history_scroll.pack(side="right", fill="y")
        self.history.configure(yscrollcommand=history_scroll.set)
        self.history.bind("<<TreeviewSelect>>", self._on_select)
        self.delete_button = ttk.Button(sidebar, text="Apagar selecionada", command=self.delete_selected)
        self.delete_button.pack(fill="x", pady=(12, 0))
        content = ttk.Frame(body)
        content.grid(row=0, column=1, sticky="nsew")
        ttk.Label(content, text="Transcrição", font=("Helvetica", 14, "bold")).pack(anchor="w")
        self.metadata = ttk.Label(content, text="Sua próxima ideia começa aqui.", style="Muted.TLabel")
        self.metadata.pack(anchor="w", pady=(4, 12))
        text_frame = ttk.Frame(content)
        text_frame.pack(fill="both", expand=True)
        self.text_area = tk.Text(text_frame, wrap="word", font=("Helvetica", 14),
                                 background="white", foreground=self.INK, relief="flat",
                                 padx=18, pady=18, spacing1=3, spacing3=8, state="disabled")
        self.text_area.pack(side="left", fill="both", expand=True)
        text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_area.yview)
        text_scroll.pack(side="right", fill="y")
        self.text_area.configure(yscrollcommand=text_scroll.set)
        self._show_text("Inicie uma gravação para transformar sua fala em uma nota.\n\n"
                        "Selecione uma transcrição no histórico para reler, copiar ou exportar."
                        if not self.demo else
                        "Explore com segurança.\n\nClique em Simular gravação e depois em "
                        "Concluir simulação para gerar um exemplo inteiramente fictício.")
        actions = ttk.Frame(content)
        actions.pack(fill="x", pady=(12, 0))
        self.copy_button = ttk.Button(actions, text="Copiar texto", command=self.copy_to_clipboard)
        self.copy_button.pack(side="left")
        self.export_button = ttk.Button(actions, text="Exportar Markdown…", command=self.export_markdown)
        self.export_button.pack(side="left", padx=(8, 0))
        footer = ("Exemplos fictícios · histórico separado do modo real" if self.demo else
                  "Whisper base · CPU int8 · carregado na primeira transcrição")
        ttk.Label(container, text=footer, style="Muted.TLabel").pack(anchor="w", pady=(18, 0))

    def _show_text(self, text: str) -> None:
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", text)
        self.text_area.configure(state="disabled")

    def _set_state(self, state: str, detail: str = "") -> None:
        self.state = state
        labels = {
            "ready": "Pronto · tudo preparado para sua próxima nota.",
            "recording": "Gravação em andamento…",
            "loading": "Carregando modelo… a primeira vez pode exigir download.",
            "transcribing": "Transcrevendo… aguarde um instante.",
            "error": "Erro · tente novamente quando estiver pronto.",
        }
        self.status_label.configure(text=detail or labels[state],
                                    foreground="#a33232" if state == "error" else self.INK)
        busy = state in ("loading", "transcribing")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(value=0)
        caption = ("Concluir simulação" if self.demo else "Parar e transcrever") if state == "recording" else (
            "Simular gravação" if self.demo else "Iniciar gravação")
        self.toggle_button.configure(text=caption, state="disabled" if busy else "normal")
        self._update_actions()

    def _update_actions(self) -> None:
        selected = self.current is not None
        self.copy_button.configure(state="normal" if selected else "disabled")
        self.export_button.configure(state="normal" if selected else "disabled")
        busy = self.state in ("recording", "loading", "transcribing")
        self.delete_button.configure(state="normal" if selected and not busy else "disabled")

    def toggle_recording(self) -> None:
        if self.state == "recording":
            self.stop_and_transcribe()
        elif self.state in ("ready", "error"):
            self.start_recording()

    def start_recording(self) -> None:
        if not self.demo:
            try:
                if self.recorder is None:
                    self.recorder = MicrophoneRecorder()
                self.recorder.start()
            except Exception as exc:
                self._error("Não foi possível acessar o microfone", str(exc))
                return
            self._capture_released.clear()
        self._started_at = time.monotonic()
        self._set_state("recording")
        self._tick_timer()

    def _tick_timer(self) -> None:
        if self.state != "recording":
            return
        minutes, seconds = divmod(int(time.monotonic() - self._started_at), 60)
        prefix = "Gravação fictícia" if self.demo else "Gravando"
        self.status_label.configure(text=f"{prefix} · {minutes:02d}:{seconds:02d}")
        self._timer_id = self.root.after(200, self._tick_timer)

    def stop_and_transcribe(self) -> None:
        duration = time.monotonic() - self._started_at
        if self._timer_id is not None:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
        self._set_state("loading" if self.demo or self.model is None else "transcribing",
                        "Carregamento fictício · preparando exemplo…" if self.demo else "")
        self._worker_thread = threading.Thread(target=self._transcribe_worker,
                                               args=(duration,), daemon=True)
        self._worker_thread.start()

    def _get_model(self):
        if self.demo:
            raise RuntimeError("O modo demonstração não permite inicializar modelos.")
        if self.model is None:
            self.events.put(("state", "loading", ""))
            from faster_whisper import WhisperModel

            self.model = WhisperModel("base", device="cpu", compute_type="int8")
        return self.model

    def _transcribe_worker(self, duration: float) -> None:
        # Workers interact only with this queue, never with Tcl/Tk (including after).
        try:
            if self.demo:
                if self._closing.wait(0.6):
                    return
                self.events.put(("state", "transcribing", "Transcrição fictícia · gerando exemplo…"))
                if self._closing.wait(0.8):
                    return
                text = DEMO_TEXTS[self._demo_index % len(DEMO_TEXTS)]
                self._demo_index += 1
            else:
                try:
                    audio = self.recorder.stop()
                finally:
                    self._capture_released.set()
                if self._closing.is_set():
                    return
                if audio.size == 0:
                    raise RuntimeError("Nenhum áudio foi capturado. Grave uma nova nota.")
                model = self._get_model()
                if self._closing.is_set():
                    return
                self.events.put(("state", "transcribing", ""))
                segments, _ = model.transcribe(
                    audio, beam_size=5, language="pt", task="transcribe",
                    initial_prompt=("Transcreva em português brasileiro, mantendo termos "
                                    "técnicos em inglês quando necessário."),
                    temperature=0.0, condition_on_previous_text=False, vad_filter=True,
                )
                text = "".join(segment.text for segment in segments).strip()
                if not text:
                    raise RuntimeError("Nenhuma fala foi detectada. Tente uma gravação mais clara.")
            if not self._closing.is_set():
                self.events.put(("result", new_record(text, duration, self.demo)))
        except Exception as exc:
            if not self._closing.is_set():
                self.events.put(("error", "Não foi possível transcrever", str(exc)))

    def _poll_events(self) -> None:
        if self._closing.is_set():
            return
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "state":
                    self._set_state(event[1], event[2])
                elif event[0] == "error":
                    self._error(event[1], event[2])
                elif event[0] == "result":
                    self._accept_result(event[1])
        except queue.Empty:
            pass
        if not self._closing.is_set():
            self._poll_id = self.root.after(80, self._poll_events)

    def _accept_result(self, record: dict) -> None:
        self.records.insert(0, record)
        saved = self._persist()
        if not saved:
            self._unsaved_ids.add(record["id"])
        self._refresh_history()
        self._select_record(record)
        if saved:
            self._set_state("ready", "Pronto · transcrição salva no histórico local.")
        else:
            self._set_state("error", "Texto disponível · não salvo. Copie ou exporte para preservar.")

    def _persist(self) -> bool:
        try:
            self.store.save(self.records)
        except HistoryError as exc:
            self.notice.configure(text=str(exc))
            return False
        self._unsaved_ids.clear()
        self.notice.configure(text="")
        return True

    def _refresh_history(self) -> None:
        selected_id = self.current["id"] if self.current else None
        for item in self.history.get_children():
            self.history.delete(item)
        for record in self.records:
            date = datetime.fromisoformat(record["created_at"]).strftime("%d/%m · %H:%M")
            preview = " ".join(record["text"].split())[:28]
            suffix = " · não salvo" if record["id"] in self._unsaved_ids else ""
            self.history.insert("", "end", iid=record["id"], text=f"{date}{suffix}\n{preview}")
        count = len(self.records)
        self.history_count.configure(text=f"{count} {'nota' if count == 1 else 'notas'}" +
                                     (" fictícias" if self.demo else " locais"))
        if selected_id and self.history.exists(selected_id):
            self.history.selection_set(selected_id)

    def _on_select(self, event=None) -> None:
        selection = self.history.selection()
        if selection:
            record = next((r for r in self.records if r["id"] == selection[0]), None)
            if record:
                self._select_record(record)

    def _select_record(self, record: dict) -> None:
        self.current = record
        if self.history.selection() != (record["id"],):
            self.history.selection_set(record["id"])
        self.history.see(record["id"])
        date = datetime.fromisoformat(record["created_at"]).strftime("%d/%m/%Y às %H:%M")
        suffix = " · fictícia" if record["demo"] else ""
        if record["id"] in self._unsaved_ids:
            suffix += " · não salva"
        self.metadata.configure(text=f"{date} · {record['duration_seconds']:.0f}s{suffix}")
        self._show_text(record["text"])
        self._update_actions()

    def delete_selected(self) -> None:
        if self.current is None or self.state in ("recording", "loading", "transcribing"):
            return
        if not messagebox.askyesno("Apagar transcrição", "Apagar esta nota do histórico local?",
                                  parent=self.root):
            return
        record = self.current
        remaining = [r for r in self.records if r["id"] != record["id"]]
        try:
            self.store.save(remaining)
        except HistoryError as exc:
            # A session-only note can be removed without changing the protected file.
            if record["id"] not in self._unsaved_ids:
                self._error("Não foi possível apagar", str(exc))
                return
            self.notice.configure(text=str(exc))
        else:
            self._unsaved_ids.clear()
            self.notice.configure(text="")
        self._unsaved_ids.discard(record["id"])
        self.records = remaining
        self.current = None
        self._refresh_history()
        if self.records:
            self._select_record(self.records[0])
        else:
            self._show_text("Nenhuma transcrição selecionada. Inicie uma nova nota.")
            self.metadata.configure(text="Sua próxima ideia começa aqui.")
            self._update_actions()

    def copy_to_clipboard(self) -> None:
        if self.current is not None:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(self.current["text"])
            except tk.TclError as exc:
                self._error("Não foi possível copiar", str(exc))
                return
            self._action_feedback("Texto copiado para a área de transferência.")

    def _action_feedback(self, text: str) -> None:
        if self.current and self.current["id"] in self._unsaved_ids:
            text += " · nota não salva no histórico"
        self.metadata.configure(text=text)

    def export_markdown(self) -> None:
        if self.current is None:
            return
        record = self.current
        stamp = datetime.fromisoformat(record["created_at"]).strftime("%Y-%m-%d_%H-%M-%S")
        filename = filedialog.asksaveasfilename(
            parent=self.root, title="Exportar transcrição em Markdown", defaultextension=".md",
            initialfile=f"{'demo-' if self.demo else ''}transcricao-{stamp}.md",
            filetypes=[("Markdown", "*.md")],
        )
        if not filename:
            return
        try:
            destination = Path(filename).expanduser().resolve()
            # Never let the export dialog overwrite either JSON history.
            if destination in {default_history_path(False).resolve(), default_history_path(True).resolve()}:
                self._error("Destino inválido", "Escolha um arquivo Markdown fora do histórico do aplicativo.")
                return
            write_markdown(destination, markdown_record(record))
        except (OSError, RuntimeError) as exc:
            self._error("Não foi possível exportar", str(exc))
            return
        self._action_feedback(f"Markdown exportado · {destination.name}")

    def _error(self, title: str, detail: str) -> None:
        # Operational errors never replace the selected transcript or history.
        if self.state in ("recording", "loading", "transcribing") and title in (
                "Não foi possível exportar", "Não foi possível copiar", "Não foi possível apagar",
                "Destino inválido"):
            messagebox.showerror(title, detail, parent=self.root)
            return
        self._set_state("error", title + " · tente novamente.")
        messagebox.showerror(title, detail, parent=self.root)

    def close(self) -> None:
        if self._closing.is_set():
            return
        if self._unsaved_ids and not messagebox.askyesno(
                "Texto não salvo", "Há transcrições não salvas. Fechar perderá essas notas. "
                "Deseja fechar mesmo assim?", parent=self.root):
            return
        busy = self.state in ("recording", "loading", "transcribing")
        if busy and not messagebox.askyesno(
                "Operação em andamento", "Fechar descartará a operação atual. Deseja fechar?",
                parent=self.root):
            return
        was_recording = self.state == "recording"
        self._closing.set()
        for callback in (self._timer_id, self._poll_id):
            if callback is not None:
                self.root.after_cancel(callback)
        if was_recording and self.recorder is not None:
            threading.Thread(target=self._discard_recording, daemon=False).start()
        self.toggle_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.delete_button.configure(state="disabled")
        self.status_label.configure(text="Encerrando demonstração…" if self.demo else
                                    "Encerrando · liberando o microfone…")
        self.progress.stop()
        self._finish_close()

    def _finish_close(self) -> None:
        # Keep the main loop alive until the audio stream has closed.
        if self._capture_released.is_set():
            self.root.destroy()
        else:
            self.root.after(80, self._finish_close)

    def _discard_recording(self) -> None:
        try:
            self.recorder.stop()
        except Exception:
            pass
        finally:
            self._capture_released.set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcrição local em português com interface desktop.")
    parser.add_argument("--demo", action="store_true",
                        help="Demonstração exclusivamente fictícia, sem microfone ou modelo.")
    args = parser.parse_args()
    root = tk.Tk()
    SpeechTranscriberApp(root, demo=args.demo)
    root.mainloop()


if __name__ == "__main__":
    main()
