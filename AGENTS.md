# AGENTS.md

Canonical instructions for coding agents working in this repository. Write all code, comments, commit messages, and documentation in English. The app UI stays in Brazilian Portuguese on purpose.

## Project

Local-first Tkinter desktop app that records Brazilian Portuguese voice notes and transcribes them with faster-whisper.

- `transcriber_app.py`: UI, state machine, `MicrophoneRecorder`, worker thread, `--demo` flag.
- `transcription_history.py`: record schema, validation, atomic JSON history, Markdown export. Standard library only.
- `tests/`: `unittest` suite, standard library only.
- `docs/PORTFOLIO-PLAN.md` (roadmap) and `docs/VALIDATION.md` (what was and was not verified).

## Commands

Prefix every shell command with `rtk` (use `rtk proxy <cmd>` for commands without a dedicated filter).

```bash
rtk proxy python3 -m py_compile transcriber_app.py transcription_history.py tests/*.py
rtk proxy python3 -m unittest discover -v # use a Tk-enabled Python to run the demo tests
rtk proxy .venv/bin/python -m pip check
rtk proxy .venv/bin/python transcriber_app.py --demo
```

Homebrew `python@3.14` lacks `_tkinter`; demo tests are skipped there. Use python.org Python (`/usr/local/bin/python3`) or a uv-managed Python for GUI work.

## Rules

- Keep the app Python/Tkinter and local-first. Do not add network calls beyond the faster-whisper model download.
- Worker threads must never call Tk. Send events through `self.events` and handle them in `_poll_events`.
- Import `sounddevice`, `numpy`, and `faster_whisper` lazily. `--demo` must never import them, open the microphone, or load a model; `tests/test_demo_isolation.py` enforces this.
- Never overwrite a history file that failed validation or changed on disk. Keep writes atomic (temporary file, `fsync`, `os.replace`).
- Keep demo and real histories in separate files and never mix their records.
- Agents must not record from the microphone, fake audio capture, or download Whisper models. Report those flows as unverified instead.
- Never commit `.venv/`, bytecode, models, history JSON, exports, or any personal note data.
- Do not present generated images as app screenshots; portfolio images must come from the real `--demo` window.
- Update `README.md` and `docs/VALIDATION.md` when behavior, setup, or verification status changes.

## CI

`.github/workflows/tests.yml` mirrors the commands above on Python 3.12 under `xvfb-run`. Do not add `requirements.txt` installs, model downloads, or microphone access to it.

## Git

- `master` is the only long-lived branch. Make small atomic commits with imperative English subjects.
- Run the unit tests before committing code changes. Never force push.
