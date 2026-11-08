"""极简中英双语支持。

语言按 DOLPHIN_BATCH_RENAME_LANG > LANGUAGE > LC_ALL > LC_MESSAGES > LANG 的顺序
判断：以 zh 开头用中文，其余用英文。
"""

from __future__ import annotations

import os

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # engine
        "err_unknown_token": "Unknown token {{{token}}}",
        "err_missing_brace": "Missing closing brace }",
        "err_extra_brace": "Unexpected closing brace }, write }} for a literal brace",
        "err_mtime": "Cannot read modification time: {detail}",
        "err_name_empty": "Name is empty",
        "err_name_slash": "Name cannot contain /",
        "err_name_dotdot": "Name cannot be . or ..",
        "err_name_too_long": "Name exceeds 255 bytes",
        "status_source_missing": "Source no longer exists",
        "status_unchanged": "Unchanged",
        "conflict_same_name": "Same new name as \"{other}\"",
        "conflict_occupied": "Target is occupied by a file that keeps its name",
        "conflict_exists": "Target already exists",
        "rename_failed": "Rename failed: {detail}",
        "source_missing_path": "Source no longer exists: {path}",
        "target_exists_path": "Target already exists: {path}",
        "undo_read_failed": "Cannot read undo record: {detail}",
        "undo_already": "This batch has already been undone",
        "undo_empty": "The undo record is empty",
        "undo_missing_current": "File no longer exists, cannot undo: {path}",
        "undo_target_occupied": "Original location is occupied, cannot undo: {path}",
        "undo_failed": "Undo failed: {detail}",
        # sort modes
        "sort_name": "File name (natural)",
        "sort_name_desc": "File name (reverse)",
        "sort_mtime": "Modified time (old → new)",
        "sort_mtime_desc": "Modified time (new → old)",
        "sort_size": "File size (small → large)",
        # gui
        "window_title": "Batch Rename — {count} items",
        "expression": "Name expression",
        "placeholder": "{P}{S}  — e.g. {T:%Y%m%d}_{P}_{z1}{S}",
        "token_name": "Name",
        "token_ext": "Extension",
        "token_seq": "Number",
        "token_seq_pad": "Padded",
        "token_mtime": "Modified",
        "token_exif": "Taken",
        "tip_name": "Original file name without extension",
        "tip_ext": "Original extension including the dot (.txt)",
        "tip_seq": "Starts at 1 and increments; use {0} to start at 0",
        "tip_seq_pad": "At least two digits: 01, 02, … 10",
        "tip_mtime": "File modification time, any strftime format",
        "tip_exif": "EXIF capture time, falls back to modification time",
        "help": (
            "<span style='color:#8a8a8a'>"
            "{P} name · {S} extension · {1}/{0} start number · {z1} zero-padded number · "
            "{T} modified time · {E} EXIF capture time · "
            "{{ }} for literal braces."
            "</span>"
        ),
        "sort": "Sort",
        "preset": "Preset",
        "save": "Save…",
        "delete": "Delete",
        "col_original": "Original name",
        "col_new": "New name",
        "col_status": "Status",
        "status_ok": "Will rename",
        "status_same": "Unchanged",
        "status_conflict": "Conflict",
        "status_error": "Error",
        "status_detail": "{label}: {message}",
        "summary_total": "{n} items",
        "summary_rename": "{n} to rename",
        "summary_same": "{n} unchanged",
        "summary_conflict": "{n} conflicts",
        "summary_error": "{n} errors",
        "summary_sep": " · ",
        "template_error": "Expression error: {error}",
        "apply": "Rename",
        "cancel": "Cancel",
        "confirm_title": "Rename",
        "confirm_text": "Rename {n} items?",
        "done_title": "Rename complete",
        "done_text": (
            "Renamed {n} items.\n\n"
            "To undo: right-click in Dolphin and choose "
            "\"Batch Rename → Undo Last Batch Rename\"."
        ),
        "preset_exists": "Preset \"{name}\" already exists.",
        "preset_builtin": "Built-in presets cannot be deleted.",
        "preset_save_title": "Save preset",
        "preset_save_label": "Preset name:",
        "preset_delete_title": "Delete preset",
        "preset_delete_question": "Delete preset \"{name}\"?",
        "preset_delete_hint": "Delete preset",
        # app
        "app_title": "Batch Rename",
        "select_first": "Select files or folders in Dolphin first, then use the context menu.",
        "none_exist": "None of the selected items exist anymore.",
        "undo_title": "Undo Batch Rename",
        "no_undo": "There is no batch rename to undo.",
        "undo_corrupt": "The undo record is corrupt:\n{path}",
        "undo_question": "Undo the rename from {when} ({count} items)?",
        "undo_failed_title": "Undo failed",
        "undo_done_title": "Undo complete",
        "undo_done_text": "Restored {n} items.",
        "usage": (
            "Usage: dolphin-batch-rename [files or folders…]\n"
            "       dolphin-batch-rename --undo-last\n\n"
            "Run it from the Dolphin context menu; --undo-last reverts the last batch."
        ),
    },
    "zh": {
        # engine
        "err_unknown_token": "未知表达式 {{{token}}}",
        "err_missing_brace": "表达式缺少右花括号 }",
        "err_extra_brace": "多余的右花括号 }，字面量请写成 }}",
        "err_mtime": "无法读取修改时间：{detail}",
        "err_name_empty": "名称为空",
        "err_name_slash": "名称不能包含 /",
        "err_name_dotdot": "名称不能是 . 或 ..",
        "err_name_too_long": "名称超过 255 字节",
        "status_source_missing": "源文件不存在",
        "status_unchanged": "名称未变化",
        "conflict_same_name": "与「{other}」的新名称相同",
        "conflict_occupied": "目标位置被未改名的文件占用",
        "conflict_exists": "目标文件已存在",
        "rename_failed": "重命名失败：{detail}",
        "source_missing_path": "源文件不存在：{path}",
        "target_exists_path": "目标文件已存在：{path}",
        "undo_read_failed": "无法读取撤销记录：{detail}",
        "undo_already": "该次重命名已经撤销过",
        "undo_empty": "撤销记录为空",
        "undo_missing_current": "文件已不存在，无法撤销：{path}",
        "undo_target_occupied": "原位置已被占用，无法撤销：{path}",
        "undo_failed": "撤销失败：{detail}",
        # sort modes
        "sort_name": "文件名（自然排序）",
        "sort_name_desc": "文件名（倒序）",
        "sort_mtime": "修改时间（旧 → 新）",
        "sort_mtime_desc": "修改时间（新 → 旧）",
        "sort_size": "文件大小（小 → 大）",
        # gui
        "window_title": "批量重命名 — {count} 个项目",
        "expression": "命名表达式",
        "placeholder": "{P}{S}  —— 例如 {T:%Y%m%d}_{P}_{z1}{S}",
        "token_name": "文件名",
        "token_ext": "扩展名",
        "token_seq": "序号",
        "token_seq_pad": "补零序号",
        "token_mtime": "修改时间",
        "token_exif": "拍摄时间",
        "tip_name": "原文件名，不含扩展名",
        "tip_ext": "原扩展名，含点（.txt）",
        "tip_seq": "从 1 开始递增；写 {0} 则从 0 开始",
        "tip_seq_pad": "至少两位：01、02 … 10",
        "tip_mtime": "文件修改时间，可自定义 strftime 格式",
        "tip_exif": "EXIF 拍摄时间，缺失时用修改时间",
        "help": (
            "<span style='color:#8a8a8a'>"
            "{P} 原名 · {S} 扩展名 · {1}/{0} 起始序号 · {z1} 补零序号 · "
            "{T} 修改时间 · {E} EXIF 拍摄时间 · "
            "{{ }} 输出花括号。"
            "</span>"
        ),
        "sort": "排序",
        "preset": "预设",
        "save": "保存…",
        "delete": "删除",
        "col_original": "原名称",
        "col_new": "新名称",
        "col_status": "状态",
        "status_ok": "将重命名",
        "status_same": "不变",
        "status_conflict": "冲突",
        "status_error": "错误",
        "status_detail": "{label}：{message}",
        "summary_total": "共 {n} 项",
        "summary_rename": "将重命名 {n} 项",
        "summary_same": "不变 {n} 项",
        "summary_conflict": "冲突 {n} 项",
        "summary_error": "错误 {n} 项",
        "summary_sep": " · ",
        "template_error": "表达式错误：{error}",
        "apply": "执行重命名",
        "cancel": "取消",
        "confirm_title": "执行重命名",
        "confirm_text": "将重命名 {n} 个项目，继续？",
        "done_title": "重命名完成",
        "done_text": (
            "已重命名 {n} 个项目。\n\n"
            "如需撤销：在 Dolphin 中右键选择「批量重命名 → 撤销上次批量重命名」。"
        ),
        "preset_exists": "预设「{name}」已存在。",
        "preset_builtin": "内置预设不能删除。",
        "preset_save_title": "保存预设",
        "preset_save_label": "预设名称：",
        "preset_delete_title": "删除预设",
        "preset_delete_question": "删除预设「{name}」？",
        "preset_delete_hint": "删除预设",
        # app
        "app_title": "批量重命名",
        "select_first": "请先在 Dolphin 中选中文件或文件夹，再使用右键菜单「批量重命名」。",
        "none_exist": "选中的项目都不存在了。",
        "undo_title": "撤销批量重命名",
        "no_undo": "没有可撤销的重命名记录。",
        "undo_corrupt": "撤销记录已损坏：\n{path}",
        "undo_question": "撤销 {when} 的重命名（{count} 个项目）？",
        "undo_failed_title": "撤销失败",
        "undo_done_title": "撤销完成",
        "undo_done_text": "已恢复 {n} 个项目。",
        "usage": (
            "用法：dolphin-batch-rename [文件或文件夹…]\n"
            "      dolphin-batch-rename --undo-last\n\n"
            "从 Dolphin 右键菜单调用；--undo-last 撤销最近一次批量重命名。"
        ),
        # presets
        "preset_keep_name": "保留原文件名",
        "preset_append_seq": "追加序号",
        "preset_padded_seq": "补零编号",
        "preset_date_prefix": "日期前缀",
        "preset_taken_time": "拍摄时间命名",
        "preset_ext_bak": "修改扩展名",
    },
}

# 英文侧还需要预设名称
_TRANSLATIONS["en"].update(
    {
        "preset_keep_name": "Keep original name",
        "preset_append_seq": "Append number",
        "preset_padded_seq": "Zero-padded number",
        "preset_date_prefix": "Date prefix",
        "preset_taken_time": "EXIF date name",
        "preset_ext_bak": "Change extension",
    }
)


def current_language() -> str:
    override = os.environ.get("DOLPHIN_BATCH_RENAME_LANG", "").strip().lower()
    if override:
        return "zh" if override.startswith("zh") else "en"
    for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(variable, "").strip().lower()
        if value:
            return "zh" if value.startswith("zh") else "en"
    return "en"


def tr(key: str, **kwargs) -> str:
    table = _TRANSLATIONS.get(current_language(), _TRANSLATIONS["en"])
    text = table.get(key) or _TRANSLATIONS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
