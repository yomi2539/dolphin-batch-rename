from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_CONFIG_HOME = tempfile.mkdtemp(prefix="dbr-test-config-")
os.environ["XDG_CONFIG_HOME"] = _CONFIG_HOME

from PySide6.QtWidgets import QApplication  # noqa: E402

from dolphin_batch_rename.gui import RenameDialog  # noqa: E402


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        for name in ("b.txt", "a.txt"):
            (self.dir / name).write_text(name, encoding="utf-8")
        self.paths = [self.dir / "a.txt", self.dir / "b.txt"]

    def make_dialog(self) -> RenameDialog:
        dialog = RenameDialog(self.paths)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_preview_and_apply_state(self):
        dialog = self.make_dialog()
        dialog.template_edit.setText("{P}_{z1}{S}")
        dialog._refresh()
        self.assertEqual(
            [item.new for item in dialog.items], ["a_01.txt", "b_02.txt"]
        )
        self.assertTrue(dialog.apply_button.isEnabled())

    def test_conflict_disables_apply(self):
        dialog = self.make_dialog()
        dialog.template_edit.setText("same{S}")
        dialog._refresh()
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertIn("2", dialog.summary_label.text())

    def test_template_error_disables_apply(self):
        dialog = self.make_dialog()
        dialog.template_edit.setText("{nope}")
        dialog._refresh()
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertTrue(dialog.summary_label.text())

    def test_builtin_presets_are_present(self):
        dialog = self.make_dialog()
        self.assertGreaterEqual(dialog.preset_combo.count(), 6)

    def test_english_ui(self):
        with mock.patch.dict(os.environ, {"DOLPHIN_BATCH_RENAME_LANG": "en"}):
            dialog = self.make_dialog()
            self.assertIn("Batch Rename", dialog.windowTitle())
        with mock.patch.dict(os.environ, {"DOLPHIN_BATCH_RENAME_LANG": "zh"}):
            dialog = self.make_dialog()
            self.assertIn("批量重命名", dialog.windowTitle())


if __name__ == "__main__":
    unittest.main()
