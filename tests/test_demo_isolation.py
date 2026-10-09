"""Demo mode must never reach the microphone, the model or the real history.

Audio and model packages are replaced by ``None`` in ``sys.modules`` so any
import attempt fails loudly. Skipped when the interpreter has no working Tk.
"""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

BLOCKED_MODULES = ("sounddevice", "numpy", "faster_whisper", "ctranslate2")

try:
    import tkinter as tk
except ImportError:  # e.g. Homebrew Python without the _tkinter extension
    tk = None


@unittest.skipIf(tk is None, "tkinter is not available in this interpreter")
class DemoIsolationTest(unittest.TestCase):
    def setUp(self) -> None:
        blocked = {name: None for name in BLOCKED_MODULES}
        modules = mock.patch.dict(sys.modules, blocked)
        modules.start()
        self.addCleanup(modules.stop)
        import transcriber_app
        self.app_module = transcriber_app

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        paths = {True: self.dir / "demo-history.json", False: self.dir / "history.json"}
        patch = mock.patch.object(transcriber_app, "default_history_path", lambda demo: paths[demo])
        patch.start()
        self.addCleanup(patch.stop)
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no Tk display available: {exc}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def make_app(self):
        app = self.app_module.SpeechTranscriberApp(self.root, demo=True)
        self.addCleanup(app._closing.set)
        return app

    def run_simulation(self, app) -> None:
        app.toggle_recording()
        self.assertEqual(app.state, "recording")
        app.toggle_recording()
        app._worker_thread.join(timeout=10)
        self.assertFalse(app._worker_thread.is_alive())
        app._poll_events()

    def test_demo_flow_saves_only_fictional_records_to_demo_file(self) -> None:
        app = self.make_app()
        self.run_simulation(app)
        self.assertEqual(app.state, "ready")
        self.assertIsNone(app.recorder)
        self.assertIsNone(app.model)
        self.assertEqual(len(app.records), 1)
        self.assertTrue(app.records[0]["demo"])
        self.assertIn(app.records[0]["text"], self.app_module.DEMO_TEXTS)
        self.assertTrue((self.dir / "demo-history.json").exists())
        self.assertFalse((self.dir / "history.json").exists())
        for name in BLOCKED_MODULES:
            self.assertIsNone(sys.modules.get(name), name)

    def test_demo_history_persists_across_restarts(self) -> None:
        self.run_simulation(self.make_app())
        reopened = self.make_app()
        self.assertEqual(len(reopened.records), 1)
        self.assertEqual(reopened.store.warning, "")

    def test_demo_refuses_to_load_a_model(self) -> None:
        app = self.make_app()
        with self.assertRaises(RuntimeError):
            app._get_model()
        self.assertIsNone(app.model)


if __name__ == "__main__":
    unittest.main()
