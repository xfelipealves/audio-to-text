# Audio to Text — portfolio plan

## Goal

Turn the small Tkinter tool into a demonstrable local desktop app for Brazilian Portuguese voice notes. The first slice must show an understandable flow, recover from errors, and stay useful after the app closes, while keeping local transcription with faster-whisper and on-demand model loading.

## Starting point

The slice started from commit `78eefe9` on the `portfolio-audio-to-text` feature checkout. The project had a single Python app and a README, and no `AGENTS.md`. The original UI had a text area, recording, a timer, and copy. It used mono 16 kHz audio, the `base` model on CPU/int8, VAD, and Portuguese as the language. History existed only for the session, errors replaced the text, and there was no export, installer, or test suite. Risks: Tkinter calls from the worker thread and exceptions while stopping audio.

## First slice

1. Improve the existing desktop UI with visual hierarchy, a selectable history, and a reading pane.
2. Make ready, recording, model loading, transcribing, and error states explicit; prevent concurrent recordings and keep notes when something fails.
3. Persist notes locally as JSON with atomic writes, failure handling, confirmed deletion, and Markdown export.
4. Provide `--demo` with fictional content and separate storage. This mode never touches the microphone or loads the model.
5. Document setup, privacy, limits, and a manual validation script.

## Acceptance criteria

- The app stays Python/Tkinter; no migration to React/Electron.
- The faster-whisper model is created only when the first real transcription is requested; processing stays local after the download.
- The UI communicates state and gives actionable guidance on failure without erasing previous transcripts.
- History survives restarts, demo data is kept apart from real data, and storage failures are never reported as success.
- The user can select, copy, delete, and export a note to Markdown.
- No real audio capture, microphone access, or real conversation is used during development checks.
- Module syntax is verified; GUI, device, download, and inference validation gaps are recorded honestly.

## Reconciliation with later authorization

The original slice (2026-10-08) was explicitly limited: static review and syntax/dependency checks only, no tests, and no commit, push, merge, deploy, or publication outside the feature checkout. On 2026-10-09 the user explicitly authorized a follow-up integration that supersedes those restrictions:

- The feature work was preserved byte-for-byte in atomic commits on `master`, then translated and extended there. No new branch or worktree was created, and the fully integrated feature branch was removed.
- A standard-library `unittest` suite was added for history persistence, atomic write failures, corrupt data, Markdown export, and demo isolation.
- All documentation was translated to English and a canonical `AGENTS.md` was added. The UI remains in Brazilian Portuguese by design.
- `master` was pushed normally (no force push).

The restriction against real microphone capture, model downloads, and faked captures still holds for automated agents. Those flows remain manual; see [VALIDATION.md](VALIDATION.md).

## Next steps (planned)

These depend on Felipe's manual validation of the first slice.

| Step | Expected result | Start / delivery criteria |
| --- | --- | --- |
| Real-app screenshot | Portfolio image of the actual `--demo` window | Captured from the running app with fictional data only; generated art does not replace it |
| Audio import | Pick a file and transcribe it through the same local pipeline | First slice validated; formats and limits defined, clear errors, no permanent audio copy by default |
| Global shortcut | Start/stop recording with an explicit user action | macOS permissions assessed, capture indicator always visible, shortcut conflicts resolved |
| macOS installer | Packaged app with model and permission instructions | Validated on a clean machine; signing, distribution, and license decided before publishing |
| Short GIF | 10–20 second demo of the note and export flow | Uses only `--demo` and fictional data; checked for legibility and absence of personal data |
| CI | Run the unit tests on push | A runner with Tk (or the demo tests skipped) and no model download |

## Validation and continuity

Check results are recorded in [VALIDATION.md](VALIDATION.md). Manual validation must cover a recording with the user's explicit participation, first model load, empty transcription, device failure, history restart, deletion, export, and closing during work. Syntax checks and unit tests do not prove those real flows.

## State at the end of the slice

Implemented: Portuguese desktop UI, explicit states, event queue, persistent selectable history, confirmed deletion, copy, atomic Markdown export, and a fictional `--demo` mode with separate history. Added the history module, `requirements.txt`, setup and validation docs, and (in the integration follow-up) unit tests and `AGENTS.md`. Local faster-whisper and on-demand loading were preserved.

The demo window launches under a Tk-enabled Python and the demo flow passes automated tests. Real recording, transcription, native dialogs, and macOS permissions still depend on Felipe's manual script. The next steps above remain planned.
