"""Local transcription records, with conservative and atomic persistence."""

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid


class HistoryError(Exception):
    """Persistence failed; callers must keep the visible transcription."""


def default_history_path(demo: bool) -> Path:
    if sys.platform == "darwin":
        directory = Path.home() / "Library" / "Application Support" / "Audio to Text"
    else:
        directory = Path.home() / ".local" / "share" / "audio-to-text"
    return directory / ("demo-history.json" if demo else "history.json")


def new_record(text: str, duration: float, demo: bool) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "text": text,
        "demo": demo,
    }


def write_markdown(path: Path, text: str) -> None:
    """Replace an export only after its complete contents reach the temporary file."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".export-", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


class HistoryStore:
    """One app owns a file; detect external edits rather than overwriting them."""

    def __init__(self, path: Path, demo: bool) -> None:
        self.path = path
        self.demo = demo
        self.records: list[dict] = []
        self.warning = ""
        self._blocked = False
        self._original: bytes | None = None
        try:
            raw = path.read_bytes()
            self._original = raw
            payload = json.loads(raw)
            if not isinstance(payload, dict) or payload.get("version") != 1:
                raise ValueError("formato de histórico desconhecido")
            records = payload.get("records")
            if not isinstance(records, list):
                raise ValueError("lista de transcrições inválida")
            ids = set()
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("registro inválido")
                identifier = record.get("id")
                if not isinstance(identifier, str) or not identifier or identifier in ids:
                    raise ValueError("identificador inválido ou repetido")
                ids.add(identifier)
                if not isinstance(record.get("text"), str) or not record["text"].strip():
                    raise ValueError("texto inválido")
                timestamp = record.get("created_at")
                if not isinstance(timestamp, str):
                    raise ValueError("data inválida")
                datetime.fromisoformat(timestamp)
                duration = record.get("duration_seconds")
                if (type(duration) not in (int, float) or not 0 <= duration < float("inf")):
                    raise ValueError("duração inválida")
                if type(record.get("demo")) is not bool or record["demo"] != demo:
                    raise ValueError("histórico real e demonstração não podem ser misturados")
            self.records = records
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, OverflowError, RecursionError) as exc:
            self._blocked = True
            self.warning = (
                f"Histórico indisponível: {exc}. O arquivo original foi preservado. "
                "Novas transcrições ficarão apenas nesta sessão; copie ou exporte o texto. "
                f"Para recuperar, feche o app e revise o arquivo: {path}"
            )

    def save(self, records: list[dict]) -> None:
        if self._blocked:
            raise HistoryError(self.warning)
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            current = self.path.read_bytes() if self.path.exists() else None
            if current != self._original:
                self._blocked = True
                self.warning = (
                    "O histórico foi alterado fora desta janela. Escrita bloqueada para "
                    "preservar o arquivo; copie ou exporte o texto e reabra o app."
                )
                raise HistoryError(self.warning)
            raw = (json.dumps({"version": 1, "records": records}, ensure_ascii=False,
                              indent=2, allow_nan=False) + "\n").encode("utf-8")
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=".history-",
                                             suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            temporary = None
            self._original = raw
            self.records = list(records)
        except OSError as exc:
            raise HistoryError(f"Não foi possível salvar o histórico: {exc}") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    # Cleanup must not mask the actual persistence failure.
                    pass


def markdown_record(record: dict) -> str:
    timestamp = datetime.fromisoformat(record["created_at"]).strftime("%d/%m/%Y às %H:%M")
    notice = "\n> DEMONSTRAÇÃO: conteúdo inteiramente fictício, sem áudio real.\n" if record["demo"] else ""
    return (f"# Transcrição\n\nData: {timestamp}\n\n"
            f"Duração: {record['duration_seconds']:.1f} segundos\n"
            f"{notice}\n## Texto\n\n{record['text']}\n")
