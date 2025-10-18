import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


class MicrophoneRecorder:
    """Thin wrapper around sounddevice.InputStream to capture raw audio."""

    def __init__(self, samplerate: int = 16000, channels: int = 1) -> None:
        self._samplerate = samplerate
        self._channels = channels
        self._frames: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            print(f"Audio callback status: {status}", flush=True)
        self._frames.append(indata.copy())

    def start(self) -> None:
        if self._stream is not None:
            return
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self._samplerate,
            channels=self._channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is None:
            return np.array([], dtype=np.float32)

        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._frames:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(self._frames, axis=0)
        return audio.flatten()


class SpeechTranscriberApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Audio to Text")
        self.root.geometry("520x380")

        self.text_area = tk.Text(self.root, wrap="word", font=("Helvetica", 12))
        self.text_area.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        controls = tk.Frame(self.root)
        controls.pack(fill="x", padx=12, pady=(0, 12))

        self.toggle_button = tk.Button(
            controls,
            text="🎙️ Start Recording",
            command=self.toggle_recording,
            width=18,
        )
        self.toggle_button.pack(side="left")

        self.copy_button = tk.Button(
            controls,
            text="Copy Text",
            command=self.copy_to_clipboard,
            width=12,
        )
        self.copy_button.pack(side="left", padx=(8, 0))

        self.status_label = tk.Label(self.root, text="Ready", anchor="w")
        self.status_label.pack(fill="x", padx=12, pady=(0, 12))

        self.recorder = MicrophoneRecorder()
        self.model: Optional[WhisperModel] = None
        self.recording = False
        self._worker_thread: Optional[threading.Thread] = None
        self._recording_start_time: Optional[float] = None
        self._timer_after_id: Optional[str] = None

    def toggle_recording(self) -> None:
        if not self.recording:
            self.start_recording()
        else:
            self.stop_and_transcribe()

    def start_recording(self) -> None:
        try:
            self.recorder.start()
        except Exception as exc:
            messagebox.showerror("Audio error", f"Could not access microphone:\n{exc}")
            return

        self.recording = True
        self.toggle_button.configure(text="⏹️ Stop Recording")
        self._start_timer()

    def stop_and_transcribe(self) -> None:
        self.recording = False
        self.toggle_button.configure(text="🎙️ Start Recording", state="disabled")
        self._cancel_timer()
        self._set_status_text("Transcribing… please wait.")

        def worker():
            audio = self.recorder.stop()
            if audio.size == 0:
                self._update_ui_after_transcription("No audio captured. Try again.")
                return

            try:
                model = self._get_model()
                segments, _ = model.transcribe(
                    audio,
                    beam_size=5,
                    language="pt",
                    task="transcribe",
                    initial_prompt=(
                        "Transcreva em português brasileiro, mantendo termos técnicos "
                        "em inglês quando necessário."
                    ),
                    temperature=0.0,
                    condition_on_previous_text=False,
                    vad_filter=True,
                )
                text = "".join(seg.text for seg in segments).strip()
            except Exception as exc:
                self._update_ui_after_transcription(
                    "Transcription failed. Check console for details."
                )
                print(f"Transcription error: {exc}", flush=True)
                return

            if not text:
                text = "[No speech detected]"

            self._update_ui_after_transcription(text, append=True)

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _get_model(self) -> WhisperModel:
        if self.model is None:
            # Load lazily to avoid slow startup times.
            self._set_status_text("Loading model…")
            self.model = WhisperModel(
                "base",
                device="cpu",
                compute_type="int8",
            )
            self._set_status_text("Transcribing… please wait.")
        return self.model

    def _update_ui_after_transcription(self, text: str, append: bool = False) -> None:
        def update():
            if append:
                if self.text_area.index("end-1c") != "1.0":
                    self.text_area.insert("end", "\n\n")
                self.text_area.insert("end", text)
            else:
                self.text_area.delete("1.0", "end")
                self.text_area.insert("end", text)
            self.text_area.see("end")
            self.toggle_button.configure(state="normal")
            self.status_label.configure(text="Ready")

        self.root.after(0, update)

    def copy_to_clipboard(self) -> None:
        text = self.text_area.get("1.0", "end-1c")
        if not text:
            self.status_label.configure(text="Nothing to copy.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_label.configure(text="Transcription copied to clipboard.")

    def _set_status_text(self, text: str) -> None:
        """Schedules a status label update on the Tk main loop."""
        self.root.after(0, lambda: self.status_label.configure(text=text))

    def _start_timer(self) -> None:
        self._recording_start_time = time.time()
        self._schedule_timer()

    def _schedule_timer(self) -> None:
        if not self.recording or self._recording_start_time is None:
            self._timer_after_id = None
            return

        elapsed = max(0.0, time.time() - self._recording_start_time)
        minutes, seconds = divmod(int(elapsed), 60)
        self.status_label.configure(text=f"Recording… {minutes:02d}:{seconds:02d}")
        self._timer_after_id = self.root.after(200, self._schedule_timer)

    def _cancel_timer(self) -> None:
        if self._timer_after_id is not None:
            self.root.after_cancel(self._timer_after_id)
            self._timer_after_id = None
        self._recording_start_time = None


def main() -> None:
    root = tk.Tk()
    app = SpeechTranscriberApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
