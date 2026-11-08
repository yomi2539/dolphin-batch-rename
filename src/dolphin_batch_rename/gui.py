"""批量重命名对话框。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QToolButton,
    QVBoxLayout,
)

from .engine import (
    ApplyResult,
    RenameError,
    RenameItem,
    SORT_MODES,
    TemplateError,
    apply_plan,
    build_plan,
)
from .i18n import tr
from .presets import load_presets, save_user_presets

_STATUS_COLOR = {
    "ok": None,
    "same": QColor("#8a8a8a"),
    "conflict": QColor("#c77c02"),
    "error": QColor("#c0392b"),
}


class PreviewModel(QAbstractTableModel):
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[RenameItem] = []

    def set_items(self, items: list[RenameItem]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        headers = (tr("col_original"), tr("col_new"), tr("col_status"))
        return headers[section] if 0 <= section < len(headers) else None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return item.original
            if column == 1:
                return item.new or "—"
            if column == 2:
                label = tr(f"status_{item.status}")
                if item.message and item.status != "ok":
                    return tr("status_detail", label=label, message=item.message)
                return label
        if role == Qt.ItemDataRole.ToolTipRole:
            if column == 0:
                return str(item.source)
            if column == 1:
                return str(item.target) if item.new else item.message
            return item.message or str(item.target)
        if role == Qt.ItemDataRole.ForegroundRole and column >= 1:
            color = _STATUS_COLOR.get(item.status)
            if color is not None:
                return color
        return None


class RenameDialog(QDialog):
    def __init__(self, paths: list[Path], parent=None):
        super().__init__(parent)
        self.paths = paths
        self.items: list[RenameItem] = []
        self.result_info: ApplyResult | None = None
        self.settings = QSettings("dolphin-batch-rename", "dolphin-batch-rename")
        self.presets = load_presets()
        self._loading_presets = False

        self.setWindowTitle(tr("window_title", count=len(paths)))
        self.setWindowIcon(QIcon.fromTheme("edit-rename"))
        self.resize(1000, 660)

        self._build_ui()
        self._reload_presets()
        self._restore_settings()
        self._refresh()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel(tr("expression")))

        self.template_edit = QLineEdit()
        self.template_edit.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.template_edit.setPlaceholderText(tr("placeholder"))
        self.template_edit.setClearButtonEnabled(True)
        layout.addWidget(self.template_edit)

        tokens = QHBoxLayout()
        tokens.setSpacing(4)
        self._add_token_button(tokens, "token_name", "tip_name", "{P}")
        self._add_token_button(tokens, "token_ext", "tip_ext", "{S}")
        self._add_token_button(tokens, "token_seq", "tip_seq", "{1}")
        self._add_token_button(tokens, "token_seq_pad", "tip_seq_pad", "{z1}")
        self._add_token_button(tokens, "token_mtime", "tip_mtime", "{T:%Y-%m-%d}")
        self._add_token_button(tokens, "token_exif", "tip_exif", "{E:%Y%m%d_%H%M%S}")
        tokens.addStretch(1)
        layout.addLayout(tokens)

        help_label = QLabel(tr("help"))
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(help_label)

        options = QHBoxLayout()
        options.setSpacing(8)
        options.addWidget(QLabel(tr("sort")))
        self.sort_combo = QComboBox()
        for key in SORT_MODES:
            self.sort_combo.addItem(tr(f"sort_{key}"), key)
        self.sort_combo.setMinimumWidth(200)
        options.addWidget(self.sort_combo)

        options.addSpacing(12)
        options.addWidget(QLabel(tr("preset")))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(170)
        options.addWidget(self.preset_combo)
        self.save_preset_button = QPushButton(tr("save"))
        self.delete_preset_button = QPushButton(tr("delete"))
        options.addWidget(self.save_preset_button)
        options.addWidget(self.delete_preset_button)
        options.addStretch(1)
        layout.addLayout(options)

        self.model = PreviewModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(2, 300)
        layout.addWidget(self.table, 1)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.button_box = QDialogButtonBox()
        self.apply_button = self.button_box.addButton(
            tr("apply"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.cancel_button = self.button_box.addButton(
            tr("cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self.apply_button.setDefault(True)
        layout.addWidget(self.button_box)

        self.template_edit.textChanged.connect(self._schedule_refresh)
        self.sort_combo.currentIndexChanged.connect(self._schedule_refresh)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        self.save_preset_button.clicked.connect(self._save_preset)
        self.delete_preset_button.clicked.connect(self._delete_preset)
        self.apply_button.clicked.connect(self._apply)
        self.cancel_button.clicked.connect(self.reject)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._refresh)

    def _add_token_button(
        self, layout: QHBoxLayout, label_key: str, tip_key: str, token: str
    ) -> None:
        button = QToolButton()
        button.setText(tr(label_key))
        button.setToolTip(f"{token}  {tr(tip_key)}")
        button.setAutoRaise(True)
        button.clicked.connect(lambda _=False, value=token: self._insert(value))
        layout.addWidget(button)

    def _insert(self, token: str) -> None:
        self.template_edit.insert(token)
        self.template_edit.setFocus()

    # -- 预设 ---------------------------------------------------------------

    def _reload_presets(self) -> None:
        self._loading_presets = True
        self.preset_combo.clear()
        for preset in self.presets:
            self.preset_combo.addItem(preset["name"], preset["template"])
        self.preset_combo.setCurrentIndex(-1)
        self._loading_presets = False

    def _apply_preset(self, index: int) -> None:
        if self._loading_presets or index < 0 or index >= len(self.presets):
            return
        preset = self.presets[index]
        self.template_edit.setText(preset["template"])
        sort_index = self.sort_combo.findData(preset.get("sort", "name"))
        if sort_index >= 0:
            self.sort_combo.setCurrentIndex(sort_index)

    def _save_preset(self) -> None:
        name, ok = QInputDialog.getText(
            self, tr("preset_save_title"), tr("preset_save_label")
        )
        name = name.strip()
        if not ok or not name:
            return
        if any(preset["name"] == name for preset in self.presets):
            QMessageBox.warning(
                self, tr("preset_save_title"), tr("preset_exists", name=name)
            )
            return
        self.presets.append(
            {
                "name": name,
                "template": self.template_edit.text(),
                "sort": self.sort_combo.currentData(),
                "builtin": False,
            }
        )
        save_user_presets(self.presets)
        self._reload_presets()

    def _delete_preset(self) -> None:
        index = self.preset_combo.currentIndex()
        if index < 0 or index >= len(self.presets):
            return
        preset = self.presets[index]
        if preset.get("builtin"):
            QMessageBox.information(
                self, tr("preset_delete_title"), tr("preset_builtin")
            )
            return
        if (
            QMessageBox.question(
                self,
                tr("preset_delete_title"),
                tr("preset_delete_question", name=preset["name"]),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        del self.presets[index]
        save_user_presets(self.presets)
        self._reload_presets()

    # -- 预览 / 执行 --------------------------------------------------------

    def _schedule_refresh(self) -> None:
        self._timer.start()

    def _refresh(self) -> None:
        self._timer.stop()
        template = self.template_edit.text()
        mode = self.sort_combo.currentData() or "name"
        try:
            self.items = build_plan(template, self.paths, mode)
        except TemplateError as exc:
            self.items = []
            self.model.set_items([])
            self.summary_label.setText(tr("template_error", error=exc))
            self.summary_label.setStyleSheet("color: #c0392b;")
            self.apply_button.setEnabled(False)
            return

        self.model.set_items(self.items)
        renaming = sum(1 for item in self.items if item.status == "ok")
        conflicts = sum(1 for item in self.items if item.status == "conflict")
        errors = sum(1 for item in self.items if item.status == "error")
        unchanged = sum(1 for item in self.items if item.status == "same")

        parts = [
            tr("summary_total", n=len(self.items)),
            tr("summary_rename", n=renaming),
        ]
        if unchanged:
            parts.append(tr("summary_same", n=unchanged))
        if conflicts:
            parts.append(tr("summary_conflict", n=conflicts))
        if errors:
            parts.append(tr("summary_error", n=errors))
        self.summary_label.setText(tr("summary_sep").join(parts))
        self.summary_label.setStyleSheet(
            "color: #c77c02;" if conflicts else ("color: #c0392b;" if errors else "")
        )
        self.apply_button.setEnabled(renaming > 0 and not conflicts and not errors)

    def _apply(self) -> None:
        self._refresh()
        renaming = sum(1 for item in self.items if item.status == "ok")
        if not renaming:
            return
        if (
            QMessageBox.question(
                self, tr("confirm_title"), tr("confirm_text", n=renaming)
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            result = apply_plan(self.items)
        except RenameError as exc:
            QMessageBox.critical(self, tr("done_title"), str(exc))
            self._refresh()
            return

        self.result_info = result
        self._save_settings()
        QMessageBox.information(
            self, tr("done_title"), tr("done_text", n=result.renamed)
        )
        self.accept()

    # -- 设置 ---------------------------------------------------------------

    def _restore_settings(self) -> None:
        template = str(self.settings.value("template", "{P}{S}"))
        sort_mode = str(self.settings.value("sort", "name"))
        self.template_edit.setText(template)
        index = self.sort_combo.findData(sort_mode)
        if index >= 0:
            self.sort_combo.setCurrentIndex(index)

    def _save_settings(self) -> None:
        self.settings.setValue("template", self.template_edit.text())
        self.settings.setValue("sort", self.sort_combo.currentData())
        self.settings.sync()

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)
