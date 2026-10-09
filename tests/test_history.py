"""History persistence and Markdown export, using temporary directories only."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import transcription_history as history
from transcription_history import (
    HistoryError, HistoryStore, default_history_path, markdown_record, new_record,
    write_markdown,
)


def leftover_temporaries(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if p.name.startswith(".") and p.suffix == ".tmp"]


class HistoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "history.json"

    def write_raw(self, payload) -> bytes:
        raw = (payload if isinstance(payload, bytes)
               else json.dumps(payload).encode("utf-8"))
        self.path.write_bytes(raw)
        return raw


class PathsTest(unittest.TestCase):
    def test_demo_and_real_histories_use_different_files(self) -> None:
        real, demo = default_history_path(False), default_history_path(True)
        self.assertNotEqual(real, demo)
        self.assertEqual(real.parent, demo.parent)
        self.assertEqual(real.name, "history.json")
        self.assertEqual(demo.name, "demo-history.json")


class RecordTest(unittest.TestCase):
    def test_new_record_shape(self) -> None:
        record = new_record("olá", 3.14159, demo=True)
        self.assertEqual(set(record), {"id", "created_at", "duration_seconds", "text", "demo"})
        self.assertEqual(record["duration_seconds"], 3.1)
        self.assertIs(record["demo"], True)
        self.assertNotEqual(record["id"], new_record("olá", 1, demo=True)["id"])


class LoadTest(HistoryTestCase):
    def test_missing_file_starts_empty_and_writable(self) -> None:
        store = HistoryStore(self.path, demo=False)
        self.assertEqual(store.records, [])
        self.assertEqual(store.warning, "")
        record = new_record("primeira nota", 2.0, demo=False)
        store.save([record])
        self.assertEqual(HistoryStore(self.path, demo=False).records, [record])

    def test_round_trip_preserves_unicode_and_order(self) -> None:
        records = [new_record("ação é configuração", 1.0, False),
                   new_record("deploy e code review", 4.5, False)]
        HistoryStore(self.path, demo=False).save(records)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)
        self.assertIn("ação", self.path.read_text(encoding="utf-8"))
        self.assertEqual(HistoryStore(self.path, demo=False).records, records)

    def test_consecutive_saves_by_same_store_succeed(self) -> None:
        store = HistoryStore(self.path, demo=False)
        first = new_record("um", 1.0, False)
        second = new_record("dois", 1.0, False)
        store.save([first])
        store.save([second, first])
        store.save([second])
        self.assertEqual(HistoryStore(self.path, demo=False).records, [second])


class CorruptDataTest(HistoryTestCase):
    def assert_blocked_and_preserved(self, raw: bytes, demo: bool = False) -> None:
        store = HistoryStore(self.path, demo=demo)
        self.assertEqual(store.records, [])
        self.assertIn(str(self.path), store.warning)
        with self.assertRaises(HistoryError):
            store.save([new_record("nova", 1.0, demo)])
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(leftover_temporaries(self.dir), [])

    def test_invalid_json_is_preserved(self) -> None:
        self.assert_blocked_and_preserved(self.write_raw(b"{not json"))

    def test_invalid_utf8_is_preserved(self) -> None:
        self.assert_blocked_and_preserved(self.write_raw(b"\xff\xfe\x00garbage"))

    def test_unknown_version_is_preserved(self) -> None:
        self.assert_blocked_and_preserved(self.write_raw({"version": 2, "records": []}))

    def test_records_not_a_list(self) -> None:
        self.assert_blocked_and_preserved(self.write_raw({"version": 1, "records": {}}))

    def test_duplicate_ids(self) -> None:
        record = new_record("texto", 1.0, False)
        self.assert_blocked_and_preserved(self.write_raw({"version": 1, "records": [record, record]}))

    def test_bad_field_values(self) -> None:
        cases = {
            "text": "   ",
            "created_at": "ontem",
            "duration_seconds": -1,
            "demo": "false",
            "id": "",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                record = new_record("texto", 1.0, False)
                record[field] = value
                self.assert_blocked_and_preserved(self.write_raw({"version": 1, "records": [record]}))

    def test_boolean_duration_is_rejected(self) -> None:
        record = new_record("texto", 1.0, False)
        record["duration_seconds"] = True
        self.assert_blocked_and_preserved(self.write_raw({"version": 1, "records": [record]}))

    def test_demo_records_never_load_into_real_history(self) -> None:
        demo_record = new_record("fictícia", 1.0, demo=True)
        self.assert_blocked_and_preserved(self.write_raw({"version": 1, "records": [demo_record]}))

    def test_real_records_never_load_into_demo_history(self) -> None:
        real_record = new_record("real", 1.0, demo=False)
        raw = self.write_raw({"version": 1, "records": [real_record]})
        self.assert_blocked_and_preserved(raw, demo=True)


class AtomicWriteTest(HistoryTestCase):
    def test_replace_failure_keeps_original_and_cleans_temporary(self) -> None:
        store = HistoryStore(self.path, demo=False)
        original = new_record("original", 1.0, False)
        store.save([original])
        before = self.path.read_bytes()
        with mock.patch.object(history.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(HistoryError) as caught:
                store.save([new_record("nova", 1.0, False), original])
        self.assertIn("disk full", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(leftover_temporaries(self.dir), [])
        self.assertEqual(store.records, [original])

    def test_write_failure_before_replace_keeps_original(self) -> None:
        store = HistoryStore(self.path, demo=False)
        original = new_record("original", 1.0, False)
        store.save([original])
        before = self.path.read_bytes()
        with mock.patch.object(history.os, "fsync", side_effect=OSError("I/O error")):
            with self.assertRaises(HistoryError):
                store.save([])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(leftover_temporaries(self.dir), [])

    def test_store_recovers_after_transient_failure(self) -> None:
        store = HistoryStore(self.path, demo=False)
        record = new_record("depois", 1.0, False)
        with mock.patch.object(history.os, "replace", side_effect=OSError("busy")):
            with self.assertRaises(HistoryError):
                store.save([record])
        store.save([record])
        self.assertEqual(HistoryStore(self.path, demo=False).records, [record])

    def test_external_modification_blocks_writes(self) -> None:
        store = HistoryStore(self.path, demo=False)
        store.save([new_record("minha", 1.0, False)])
        external = self.write_raw({"version": 1, "records": []})
        with self.assertRaises(HistoryError):
            store.save([])
        self.assertEqual(self.path.read_bytes(), external)
        with self.assertRaises(HistoryError):
            store.save([])

    def test_unwritable_directory_raises_history_error(self) -> None:
        blocker = self.dir / "not-a-directory"
        blocker.write_text("file", encoding="utf-8")
        store = HistoryStore(blocker / "history.json", demo=False)
        with self.assertRaises(HistoryError):
            store.save([new_record("texto", 1.0, False)])


class ExportTest(HistoryTestCase):
    def test_markdown_record_contents(self) -> None:
        record = new_record("Texto da nota.", 12.34, demo=False)
        record["created_at"] = "2026-10-09T14:05:00-03:00"
        markdown = markdown_record(record)
        self.assertTrue(markdown.startswith("# Transcrição\n"))
        self.assertIn("Data: 09/10/2026 às 14:05", markdown)
        self.assertIn("Duração: 12.3 segundos", markdown)
        self.assertTrue(markdown.endswith("## Texto\n\nTexto da nota.\n"))
        self.assertNotIn("DEMONSTRAÇÃO", markdown)

    def test_demo_export_is_labelled_fictional(self) -> None:
        markdown = markdown_record(new_record("Exemplo.", 1.0, demo=True))
        self.assertIn("DEMONSTRAÇÃO", markdown)

    def test_write_markdown_creates_and_overwrites(self) -> None:
        target = self.dir / "nota.md"
        write_markdown(target, "primeira\n")
        write_markdown(target, "segunda ação\n")
        self.assertEqual(target.read_text(encoding="utf-8"), "segunda ação\n")
        self.assertEqual(leftover_temporaries(self.dir), [])

    def test_write_markdown_failure_keeps_existing_export(self) -> None:
        target = self.dir / "nota.md"
        target.write_text("anterior\n", encoding="utf-8")
        with mock.patch.object(history.os, "replace", side_effect=OSError("read-only")):
            with self.assertRaises(OSError):
                write_markdown(target, "nova\n")
        self.assertEqual(target.read_text(encoding="utf-8"), "anterior\n")
        self.assertEqual(leftover_temporaries(self.dir), [])


if __name__ == "__main__":
    unittest.main()
