from __future__ import annotations

import os
import struct
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from dolphin_batch_rename.engine import (
    RenameError,
    RenameItem,
    TemplateError,
    apply_plan,
    build_plan,
    parse_template,
    undo_history,
    validate_name,
)
from dolphin_batch_rename.exif import read_exif_datetime
from dolphin_batch_rename.i18n import tr


class TemplateTests(unittest.TestCase):
    def test_parses_tokens_and_literals(self):
        tokens = parse_template("IMG_{T:%Y%m%d}_{P}_{z1}{S}")
        self.assertEqual(
            [token.kind for token in tokens],
            ["literal", "date", "literal", "stem", "literal", "number", "ext"],
        )
        self.assertEqual(tokens[1].fmt, "%Y%m%d")
        self.assertEqual(tokens[5].pad, 2)

    def test_escaped_braces(self):
        tokens = parse_template("{{P}}")
        self.assertEqual("".join(t.text for t in tokens), "{P}")

    def test_unknown_token(self):
        with self.assertRaises(TemplateError):
            parse_template("{X}")

    def test_missing_brace(self):
        with self.assertRaises(TemplateError):
            parse_template("{P")

    def test_validate_name(self):
        self.assertIsNone(validate_name("ok.txt"))
        self.assertIsNotNone(validate_name(""))
        self.assertIsNotNone(validate_name("a/b"))
        self.assertIsNotNone(validate_name(".."))
        self.assertIsNotNone(validate_name("x" * 300))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def touch(self, *names: str) -> list[Path]:
        paths = []
        for name in names:
            path = self.dir / name
            path.write_text(name, encoding="utf-8")
            paths.append(path)
        return paths

    def test_numbering_and_natural_sort(self):
        paths = self.touch("b.txt", "a.txt", "c.txt")
        items = build_plan("{P}_{z1}{S}", paths)
        self.assertEqual(
            [(item.original, item.new) for item in items],
            [("a.txt", "a_01.txt"), ("b.txt", "b_02.txt"), ("c.txt", "c_03.txt")],
        )

    def test_start_number_and_no_padding(self):
        paths = self.touch("a.txt", "b.txt")
        items = build_plan("{P}_{0}{S}", paths)
        self.assertEqual([item.new for item in items], ["a_0.txt", "b_1.txt"])

    def test_extension_is_dropped_when_template_has_none(self):
        paths = self.touch("a.txt")
        items = build_plan("{P}.bak", paths)
        self.assertEqual(items[0].new, "a.bak")

    def test_date_token(self):
        path = self.touch("a.txt")[0]
        stamp = 1_600_000_000
        os.utime(path, (stamp, stamp))
        expected = datetime.fromtimestamp(stamp).strftime("%Y%m%d")
        items = build_plan("{T:%Y%m%d}{S}", [path])
        self.assertEqual(items[0].new, f"{expected}.txt")

    def test_unchanged(self):
        paths = self.touch("a.txt")
        items = build_plan("{P}{S}", paths)
        self.assertEqual(items[0].status, "same")

    def test_duplicate_targets_are_conflicts(self):
        paths = self.touch("a.txt", "b.txt")
        items = build_plan("same{S}", paths)
        self.assertTrue(all(item.status == "conflict" for item in items))

    def test_existing_target_is_conflict(self):
        paths = self.touch("a.txt", "b.txt")
        items = build_plan("b{S}", [paths[0]])
        self.assertEqual(items[0].status, "conflict")

    def test_directory_keeps_name(self):
        folder = self.dir / "photos.2024"
        folder.mkdir()
        items = build_plan("{P}", [folder])
        self.assertEqual(items[0].new, "photos.2024")

    def test_invalid_name_is_error(self):
        paths = self.touch("a.txt")
        items = build_plan("x/{P}{S}", paths)
        self.assertEqual(items[0].status, "error")

    def test_missing_source_is_error(self):
        items = build_plan("{P}{S}", [self.dir / "missing.txt"])
        self.assertEqual(items[0].status, "error")


class ApplyUndoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.state = self.dir / "state"
        self.env = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.state)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.temp.cleanup)

    def touch(self, name: str, content: str) -> Path:
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_apply_and_undo(self):
        self.touch("a.txt", "A")
        self.touch("b.txt", "B")
        paths = [self.dir / "a.txt", self.dir / "b.txt"]
        items = build_plan("{P}_new{S}", paths)
        result = apply_plan(items)
        self.assertEqual(result.renamed, 2)
        self.assertFalse((self.dir / "a.txt").exists())
        self.assertEqual((self.dir / "a_new.txt").read_text(encoding="utf-8"), "A")
        self.assertEqual((self.dir / "b_new.txt").read_text(encoding="utf-8"), "B")

        undone = undo_history(result.history_path)
        self.assertEqual(undone.restored, 2)
        self.assertEqual((self.dir / "a.txt").read_text(encoding="utf-8"), "A")
        self.assertFalse((self.dir / "a_new.txt").exists())

    def test_swap_uses_two_phase_rename(self):
        a = self.touch("a.txt", "A")
        b = self.touch("b.txt", "B")
        items = [
            RenameItem(a, b, "a.txt", "b.txt", "ok"),
            RenameItem(b, a, "b.txt", "a.txt", "ok"),
        ]
        apply_plan(items)
        self.assertEqual(a.read_text(encoding="utf-8"), "B")
        self.assertEqual(b.read_text(encoding="utf-8"), "A")

    def test_undo_refuses_when_original_is_occupied(self):
        self.touch("a.txt", "A")
        path = self.dir / "a.txt"
        result = apply_plan(build_plan("{P}_new{S}", [path]))
        self.touch("a.txt", "taken")
        with self.assertRaises(RenameError):
            undo_history(result.history_path)

    def test_apply_skips_conflicts(self):
        self.touch("a.txt", "A")
        self.touch("b.txt", "B")
        items = build_plan("b{S}", [self.dir / "a.txt"])
        self.assertEqual(apply_plan(items).renamed, 0)


class ExifTests(unittest.TestCase):
    def _jpeg_with_datetime(self, text: str) -> bytes:
        tiff = bytearray()
        tiff += b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
        # IFD0：一个指向 Exif IFD 的条目
        exif_ifd_offset = 26
        tiff += struct.pack("<H", 1)
        tiff += struct.pack("<HHI", 0x8769, 4, 1) + struct.pack("<I", exif_ifd_offset)
        tiff += struct.pack("<I", 0)
        # Exif IFD：DateTimeOriginal
        value_offset = exif_ifd_offset + 18
        tiff += struct.pack("<H", 1)
        encoded = text.encode("ascii") + b"\x00"
        tiff += struct.pack("<HHI", 0x9003, 2, len(encoded)) + struct.pack(
            "<I", value_offset
        )
        tiff += struct.pack("<I", 0)
        tiff += encoded

        payload = b"Exif\x00\x00" + bytes(tiff)
        return (
            b"\xff\xd8"
            + b"\xff\xe1"
            + struct.pack(">H", len(payload) + 2)
            + payload
            + b"\xff\xd9"
        )

    def test_reads_datetime_original(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "photo.jpg"
            path.write_bytes(self._jpeg_with_datetime("2024:05:06 07:08:09"))
            self.assertEqual(read_exif_datetime(path), datetime(2024, 5, 6, 7, 8, 9))

    def test_returns_none_for_non_image(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "note.txt"
            path.write_text("hello", encoding="utf-8")
            self.assertIsNone(read_exif_datetime(path))


class LanguageTests(unittest.TestCase):
    def test_switches_language(self):
        with mock.patch.dict(os.environ, {"DOLPHIN_BATCH_RENAME_LANG": "en"}):
            self.assertEqual(tr("apply"), "Rename")
        with mock.patch.dict(os.environ, {"DOLPHIN_BATCH_RENAME_LANG": "zh"}):
            self.assertEqual(tr("apply"), "执行重命名")


if __name__ == "__main__":
    unittest.main()
