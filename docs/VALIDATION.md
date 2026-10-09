# Validation

## Integration follow-up — 2026-10-09 (`master`)

The feature work was integrated into `master`, unit tests were added, and checks were rerun. No microphone was opened, no audio was captured or faked, and no Whisper model was downloaded or instantiated.

| Check | Result |
| --- | --- |
| Sibling feature files vs. integrated commits | Byte-identical (`cmp`) before translation |
| Syntax compile of app, history module, and tests | Passed on Python 3.12.6 and 3.14.8 |
| `python -m unittest -v` on Python 3.12.6 (python.org, Tk 8.6) | 26 tests, OK |
| Same on Python 3.13.12 (uv-managed, Tk 9.0) | 26 tests, OK |
| Same on Python 3.14.8 (Homebrew, no `_tkinter`) | 23 OK, 3 demo tests skipped |
| `pip check` in the feature `.venv` (3.14.8) | `No broken requirements found.` |
| Dependency import (no model, no stream) | faster-whisper 1.2.1, numpy 2.5.3, sounddevice 0.5.6 import successfully; `sounddevice` initializes PortAudio but opens no stream |
| `import transcriber_app` on Homebrew 3.14.8 | Fails with `No module named '_tkinter'` (interpreter setup, not app code) |
| `transcriber_app.py --demo` launch, isolated `HOME`, Python 3.12.6 and 3.13.12 | Process stayed up for 6 s with no traceback; macOS reported window `Audio to Text · Demonstração fictícia`; terminated by the check |
| `git diff --check` | Clean |
| Existing CI | None at integration time; added afterwards (see below) |

What the unit tests cover:

- History: round trip with Unicode and order, repeated saves, missing file, invalid JSON and UTF-8, unknown version, wrong record types, duplicate IDs, invalid fields (including boolean durations), demo/real mixing in both directions, `os.replace` and `fsync` failures (original preserved, no temporary left behind), recovery after a transient failure, external modification blocking writes, unwritable directory.
- Export: Markdown content and date format, demo notice, overwrite, failed replace keeping the previous export.
- Demo isolation (needs Tk): the full simulated flow runs with `sounddevice`, `numpy`, `faster_whisper`, and `ctranslate2` blocked in `sys.modules`, writes only the demo history, persists across a restart, and refuses to load a model.

Not verified (requires a person and real hardware):

- Visual layout, resizing, keyboard focus, and appearance. The demo launch only proves the window opens; nobody inspected it, and no screenshot was taken.
- Microphone permission prompts, real capture, device errors, first model download, inference quality, and timing.
- Native dialogs: delete confirmation, Markdown save dialog, close confirmation.
- Closing during a real recording or transcription.

Setup blocker: Homebrew's `python@3.14` has no `_tkinter`, so the GUI cannot start from the feature `.venv`. Recreate `.venv` with a Tk-enabled Python (python.org 3.12 at `/usr/local/bin/python3` or a uv-managed Python on this machine) before running the app or the manual script. Large audio/model packages were not reinstalled for this check.

## Continuous integration — 2026-10-09

`.github/workflows/tests.yml` runs on every push to `master`, on pull requests, and on manual dispatch:

1. `actions/setup-python` with Python 3.12 on `ubuntu-latest`.
2. Installs only `xvfb` with `apt-get`. `requirements.txt` is not installed, so no audio library or Whisper model is downloaded.
3. `python -m py_compile transcriber_app.py transcription_history.py tests/*.py`.
4. Opens and destroys `tkinter.Tk()` under `xvfb-run`; the job fails if Tk is unavailable instead of skipping the demo tests.
5. `xvfb-run -a python -m unittest discover -v` (26 tests expected, 0 skips).

CI proves the history logic and demo isolation on Linux. It does not prove macOS layout, microphone access, model download, inference, or native dialogs; those remain in the manual script below.

## First slice — 2026-10-08 (feature checkout)

That task, by its scope at the time, created and ran no automated tests, opened no GUI, recorded no audio, and downloaded no model. Validation was limited to static review and the checks below.

| Check | Result |
| --- | --- |
| README, original code, and instructions read | Done; no `AGENTS.md` in the checkout |
| Initial Git state | Clean |
| Python available | 3.14.8 |
| Install into `.venv` | faster-whisper 1.2.1, sounddevice 0.5.6, numpy 2.5.3 and dependencies |
| `.venv/bin/python -m pip check` | Passed |
| Tk availability | `find_spec("_tkinter")` returned `None`; this interpreter cannot open the GUI |
| `py_compile` of both modules | Passed |
| `git diff --check` | Passed |
| Final static review | Recording, queue, on-demand loading, history, deletion, export, and close flows reviewed; no other blockers found |

Changes made during that review:

- Audio dependencies imported only after an explicit action; faster-whisper imported and the model created only in the real transcription worker.
- The worker sends events through `queue.Queue`; Tkinter calls stay on the main loop.
- Errors never replace note text. Save failures keep the note for the session with a warning and an unsaved marker; copy and export stay available.
- History validates version and records; corruption or external edits block writes to the original file. JSON and Markdown use a temporary file plus atomic replace. Cleanup failures never mask the main error.
- History selection is guarded against repeated events; deletion is disabled during capture or processing.
- Closing confirms loss of in-progress work or unsaved notes and waits for the capture to be released before destroying the window. Inference has no cooperative cancellation; closing discards a pending result.

Known limitations from that slice still apply: a successful install and `pip check` do not prove native library loading, device compatibility, or inference; history is unencrypted; deletion does not remove exports or backups; simultaneous instances of the same mode are not coordinated.

## Pending manual script for Felipe

Run only with a Tk-enabled Python. The capture steps require the user's explicit participation.

1. Open with `--demo`. Confirm the history is fictional and no microphone prompt or model download happens. Check legibility, resizing, and keyboard navigation.
2. Run the simulated flow and check states, selection, copy, Markdown export, and confirmed deletion. Restart the demo and check persistence. The real history must stay separate.
3. Open the real mode. Confirm opening the window does not capture audio. Record a short note and check the timer, first load, transcription, saved note, and reopening.
4. Check device/permission errors, no speech, and download/inference failure. Previous notes must remain available and controls must allow a retry.
5. With a backup of the demo data directory, check an invalid history and a write failure. The invalid file must be preserved; an unsaved note must remain available to copy or export.
6. Check cancelling the export dialog, an unwritable destination, and overwriting an existing file.
7. Check closing during recording and during transcription, including the confirmation and device release. Do not assume an interrupted daemon finished the transcription.

Only move to the planned next steps after fixing what this script finds.
