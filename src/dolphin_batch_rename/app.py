"""程序入口：从 Dolphin 服务菜单启动图形界面，或执行撤销。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .engine import RenameError, latest_history, undo_history
from .gui import RenameDialog
from .i18n import tr


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if any(arg in ("-h", "--help") for arg in args):
        print(tr("usage"))
        return 0
    if "--version" in args:
        print(__version__)
        return 0

    undo = "--undo-last" in args
    paths = [Path(arg) for arg in args if not arg.startswith("-")]

    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("dolphin-batch-rename")
    app.setApplicationDisplayName(tr("app_title"))
    app.setWindowIcon(QIcon.fromTheme("edit-rename"))

    if undo:
        return _undo_last()
    if not paths:
        QMessageBox.warning(None, tr("app_title"), tr("select_first"))
        return 2

    existing = [path for path in paths if path.exists() or path.is_symlink()]
    if not existing:
        QMessageBox.warning(None, tr("app_title"), tr("none_exist"))
        return 2

    dialog = RenameDialog(existing)
    dialog.exec()
    return 0


def _undo_last() -> int:
    record = latest_history()
    if record is None:
        QMessageBox.information(None, tr("undo_title"), tr("no_undo"))
        return 1

    try:
        payload = json.loads(record.read_text(encoding="utf-8"))
        count = len(payload.get("entries") or [])
        when = payload.get("time", "")
    except (OSError, ValueError):
        QMessageBox.critical(
            None, tr("undo_title"), tr("undo_corrupt", path=record)
        )
        return 1

    if (
        QMessageBox.question(
            None,
            tr("undo_title"),
            tr("undo_question", when=when, count=count),
        )
        != QMessageBox.StandardButton.Yes
    ):
        return 0

    try:
        result = undo_history(record)
    except RenameError as exc:
        QMessageBox.critical(None, tr("undo_failed_title"), str(exc))
        return 1

    QMessageBox.information(
        None, tr("undo_done_title"), tr("undo_done_text", n=result.restored)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
