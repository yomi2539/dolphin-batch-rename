"""重命名预设的读写。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .i18n import tr

DEFAULT_PRESETS: list[dict[str, str]] = [
    {"key": "preset_keep_name", "template": "{P}{S}", "sort": "name"},
    {"key": "preset_append_seq", "template": "{P}_{1}{S}", "sort": "name"},
    {"key": "preset_padded_seq", "template": "文件_{z1}{S}", "sort": "name"},
    {"key": "preset_date_prefix", "template": "{T:%Y-%m-%d}_{P}{S}", "sort": "name"},
    {"key": "preset_taken_time", "template": "IMG_{E:%Y%m%d_%H%M%S}{S}", "sort": "mtime"},
    {"key": "preset_ext_bak", "template": "{P}.bak", "sort": "name"},
]

# 内置预设中不随语言变化的字面量部分
_PADDED_PREFIX = {"en": "file_", "zh": "文件_"}


def default_presets() -> list[dict[str, str]]:
    from .i18n import current_language

    language = current_language()
    result = []
    for preset in DEFAULT_PRESETS:
        name = tr(preset["key"])
        template = preset["template"]
        if preset["key"] == "preset_padded_seq":
            template = f"{_PADDED_PREFIX.get(language, 'file_')}{{z1}}{{S}}"
        result.append(
            {
                "name": name,
                "template": template,
                "sort": preset["sort"],
                "builtin": True,
            }
        )
    return result


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "dolphin-batch-rename"


def presets_path() -> Path:
    return config_dir() / "presets.json"


def load_presets() -> list[dict[str, str]]:
    presets = default_presets()
    try:
        payload = json.loads(presets_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return presets

    if not isinstance(payload, list):
        return presets
    known = {item["name"] for item in presets}
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        template = str(item.get("template", ""))
        if not name or name in known:
            continue
        presets.append(
            {
                "name": name,
                "template": template,
                "sort": str(item.get("sort", "name")),
                "builtin": False,
            }
        )
        known.add(name)
    return presets


def save_user_presets(presets: list[dict[str, str]]) -> None:
    custom = [
        {"name": item["name"], "template": item["template"], "sort": item["sort"]}
        for item in presets
        if not item.get("builtin")
    ]
    path = presets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(custom, ensure_ascii=False, indent=2), encoding="utf-8"
    )
