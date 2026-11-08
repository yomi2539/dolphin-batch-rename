"""表达式批量重命名核心引擎。

模板语法（参考 MT 管理器的批量重命名）::

    {P}        原文件名（不含扩展名），目录则为完整名称
    {S}        原扩展名（含点，例如 .txt），没有则为空
    {T}        文件修改时间，默认 "%Y-%m-%d %H.%M.%S"
    {T:%Y%m%d} 自定义时间的 strftime 格式
    {E}        图片 EXIF 拍摄时间（无 EXIF 时回退到修改时间）
    {E:%Y%m%d} 自定义 EXIF 时间格式
    {0} {1}    从指定数字开始递增的序号
    {z1} {z8}  序号，并补零到至少两位（01、02 … 10）
    {{ }}      字面量花括号

模板中的多个序号表达式共享同一个递增计数，起始值取第一个序号表达式。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .exif import read_exif_datetime
from .i18n import tr

DEFAULT_DATE_FORMAT = "%Y-%m-%d %H.%M.%S"
MAX_NAME_BYTES = 255
HISTORY_LIMIT = 50


class TemplateError(ValueError):
    """模板语法错误。"""


class MetadataError(RuntimeError):
    """无法读取文件元数据（EXIF）。"""


class RenameError(RuntimeError):
    """执行重命名或撤销时失败。"""


@dataclass(frozen=True)
class Token:
    kind: str  # literal / stem / ext / date / exif / number
    text: str = ""
    fmt: str | None = None
    start: int = 1
    pad: int = 0


@dataclass
class RenameItem:
    source: Path
    target: Path
    original: str
    new: str
    status: str  # ok / same / conflict / error
    message: str = ""

    @property
    def will_rename(self) -> bool:
        return self.status == "ok"


@dataclass
class ApplyResult:
    renamed: int
    history_path: Path | None


@dataclass
class UndoResult:
    restored: int
    history_path: Path


# ---------------------------------------------------------------------------
# 模板解析
# ---------------------------------------------------------------------------

def _make_token(content: str) -> Token:
    if content == "P":
        return Token("stem")
    if content == "S":
        return Token("ext")
    if content == "T" or content.startswith("T:"):
        return Token("date", fmt=content[2:] or DEFAULT_DATE_FORMAT)
    if content == "E" or content.startswith("E:"):
        return Token("exif", fmt=content[2:] or DEFAULT_DATE_FORMAT)
    if re.fullmatch(r"z\d+", content):
        start = int(content[1:])
        return Token("number", start=start, pad=max(2, len(str(start))))
    if content.isdigit():
        return Token("number", start=int(content))
    raise TemplateError(tr("err_unknown_token", token=content))


def parse_template(template: str) -> list[Token]:
    """把模板字符串解析为 token 列表，语法错误时抛 TemplateError。"""
    tokens: list[Token] = []
    buf: list[str] = []
    i = 0
    length = len(template)

    def flush() -> None:
        if buf:
            tokens.append(Token("literal", "".join(buf)))
            buf.clear()

    while i < length:
        ch = template[i]
        if ch == "{":
            if template.startswith("{{", i):
                buf.append("{")
                i += 2
                continue
            end = template.find("}", i + 1)
            if end < 0:
                raise TemplateError(tr("err_missing_brace"))
            flush()
            tokens.append(_make_token(template[i + 1 : end]))
            i = end + 1
        elif ch == "}":
            if template.startswith("}}", i):
                buf.append("}")
                i += 2
                continue
            raise TemplateError(tr("err_extra_brace"))
        else:
            buf.append(ch)
            i += 1
    flush()
    return tokens


def template_start(tokens: list[Token]) -> int:
    for token in tokens:
        if token.kind == "number":
            return token.start
    return 1


# ---------------------------------------------------------------------------
# 排序 / 名称拆分
# ---------------------------------------------------------------------------

SORT_MODES = ("name", "name_desc", "mtime", "mtime_desc", "size")


def natural_key(text: str) -> tuple:
    parts = re.split(r"(\d+)", text.casefold())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def sort_paths(paths: list[Path], mode: str = "name") -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normpath(os.path.abspath(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)

    if mode == "name":
        return sorted(unique, key=lambda p: natural_key(p.name))
    if mode == "name_desc":
        return sorted(unique, key=lambda p: natural_key(p.name), reverse=True)
    if mode == "mtime":
        return sorted(unique, key=lambda p: (_mtime(p), natural_key(p.name)))
    if mode == "mtime_desc":
        return sorted(unique, key=lambda p: _mtime(p), reverse=True)
    if mode == "size":
        return sorted(unique, key=lambda p: (_size(p), natural_key(p.name)))
    return sorted(unique, key=lambda p: natural_key(p.name))


def _mtime(path: Path) -> float:
    try:
        return path.lstat().st_mtime
    except OSError:
        return 0.0


def _size(path: Path) -> int:
    try:
        return path.lstat().st_size
    except OSError:
        return 0


def split_name(path: Path) -> tuple[str, str]:
    """返回 (主名, 扩展名)。目录、隐藏文件不拆分扩展名。"""
    try:
        is_dir = path.is_dir()
    except OSError:
        is_dir = False
    if is_dir:
        return path.name, ""
    return path.stem, path.suffix


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_name(tokens: list[Token], path: Path, sequence: int) -> str:
    stem, ext = split_name(path)
    try:
        mtime = datetime.fromtimestamp(path.lstat().st_mtime)
    except OSError as exc:
        raise MetadataError(tr("err_mtime", detail=exc.strerror or exc)) from exc

    out: list[str] = []
    for token in tokens:
        if token.kind == "literal":
            out.append(token.text)
        elif token.kind == "stem":
            out.append(stem)
        elif token.kind == "ext":
            out.append(ext)
        elif token.kind == "number":
            out.append(str(sequence).zfill(token.pad) if token.pad else str(sequence))
        elif token.kind == "date":
            out.append(mtime.strftime(token.fmt or DEFAULT_DATE_FORMAT))
        elif token.kind == "exif":
            taken = read_exif_datetime(path)
            out.append((taken or mtime).strftime(token.fmt or DEFAULT_DATE_FORMAT))
    return "".join(out)


def validate_name(name: str) -> str | None:
    if not name:
        return tr("err_name_empty")
    if "/" in name or "\x00" in name:
        return tr("err_name_slash")
    if name in (".", ".."):
        return tr("err_name_dotdot")
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        return tr("err_name_too_long")
    return None


# ---------------------------------------------------------------------------
# 预览 / 冲突检测
# ---------------------------------------------------------------------------

def build_plan(template: str, paths: list[Path], sort_mode: str = "name") -> list[RenameItem]:
    tokens = parse_template(template)  # 语法错误直接抛出
    ordered = sort_paths(paths, sort_mode)
    start = template_start(tokens)

    items: list[RenameItem] = []
    for index, source in enumerate(ordered):
        sequence = start + index
        try:
            new_name = render_name(tokens, source, sequence)
        except MetadataError as exc:
            items.append(
                RenameItem(source, source, source.name, "", "error", str(exc))
            )
            continue

        problem = validate_name(new_name)
        target = source.with_name(new_name) if not problem else source
        if problem:
            status, message = "error", problem
        elif not os.path.lexists(source):
            status, message = "error", tr("status_source_missing")
        elif new_name == source.name:
            status, message = "same", tr("status_unchanged")
        else:
            status, message = "ok", ""
        items.append(RenameItem(source, target, source.name, new_name, status, message))

    _mark_conflicts(items)
    return items


def _mark_conflicts(items: list[RenameItem]) -> None:
    source_keys = {
        os.path.normpath(os.path.abspath(item.source))
        for item in items
    }
    targets: dict[str, list[RenameItem]] = {}
    for item in items:
        if item.status in ("ok", "same"):
            key = os.path.normpath(os.path.abspath(item.target))
            targets.setdefault(key, []).append(item)

    for key, group in targets.items():
        if len(group) > 1:
            for item in group:
                others = [other for other in group if other is not item]
                message = tr("conflict_same_name", other=others[0].original)
                item.message = message
                if item.status != "same":
                    item.status = "conflict"

    for item in items:
        if item.status != "ok":
            continue
        key = os.path.normpath(os.path.abspath(item.target))
        if key in source_keys:
            # 目标是本批次中的另一个源文件：只有当它自己也会被改名时才安全
            other = next(
                (it for it in items if os.path.normpath(os.path.abspath(it.source)) == key),
                None,
            )
            if other is not None and other.status in ("ok", "same") and not other.will_rename:
                item.status = "conflict"
                item.message = tr("conflict_occupied")
            continue
        if os.path.lexists(item.target):
            item.status = "conflict"
            item.message = tr("conflict_exists")


# ---------------------------------------------------------------------------
# 执行 / 撤销
# ---------------------------------------------------------------------------

def _state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "dolphin-batch-rename" / "history"


def _unique_temp(directory: Path) -> Path:
    stamp = f"{os.getpid()}-{time.time_ns()}"
    candidate = directory / f".dbr-tmp-{stamp}"
    counter = 1
    while os.path.lexists(candidate):
        candidate = directory / f".dbr-tmp-{stamp}-{counter}"
        counter += 1
    return candidate


def _write_history(pairs: list[tuple[Path, Path]]) -> Path:
    history_dir = _state_dir()
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.json"
    payload = {
        "version": 1,
        "time": datetime.now().isoformat(timespec="seconds"),
        "undone": False,
        "entries": [
            {"source": str(source), "target": str(target)} for source, target in pairs
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _prune_history(history_dir)
    return path


def _prune_history(history_dir: Path) -> None:
    records = sorted(history_dir.glob("*.json"), reverse=True)
    for old in records[HISTORY_LIMIT:]:
        try:
            old.unlink()
        except OSError:
            pass


def apply_plan(items: list[RenameItem]) -> ApplyResult:
    """执行预览中状态为 ok 的条目，使用两阶段重命名以支持交换/链式改名。"""
    operations = [item for item in items if item.status == "ok"]
    if not operations:
        return ApplyResult(0, None)

    sources = {os.path.normpath(os.path.abspath(item.source)) for item in operations}
    for item in operations:
        if not os.path.lexists(item.source):
            raise RenameError(tr("source_missing_path", path=item.source))
        target_key = os.path.normpath(os.path.abspath(item.target))
        if target_key not in sources and os.path.lexists(item.target):
            raise RenameError(tr("target_exists_path", path=item.target))

    staged: list[tuple[Path, Path]] = []  # (临时文件, 原文件)
    moved: list[tuple[Path, Path]] = []  # (目标文件, 临时文件)
    try:
        for item in operations:
            temp = _unique_temp(item.source.parent)
            os.rename(item.source, temp)
            staged.append((temp, item.source))
        for (temp, _source), item in zip(staged, operations):
            os.rename(temp, item.target)
            moved.append((item.target, temp))
    except OSError as exc:
        for target, temp in reversed(moved):
            try:
                os.rename(target, temp)
            except OSError:
                pass
        for temp, source in reversed(staged):
            try:
                if os.path.lexists(temp):
                    os.rename(temp, source)
            except OSError:
                pass
        detail = exc.strerror or str(exc)
        raise RenameError(tr("rename_failed", detail=detail)) from exc

    history_path = _write_history([(item.source, item.target) for item in operations])
    return ApplyResult(len(operations), history_path)


def latest_history(history_dir: Path | None = None) -> Path | None:
    directory = history_dir or _state_dir()
    for record in sorted(directory.glob("*.json"), reverse=True):
        try:
            payload = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not payload.get("undone") and payload.get("entries"):
            return record
    return None


def undo_history(record_path: Path) -> UndoResult:
    try:
        payload = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RenameError(tr("undo_read_failed", detail=exc)) from exc

    entries = payload.get("entries") or []
    if payload.get("undone"):
        raise RenameError(tr("undo_already"))
    if not entries:
        raise RenameError(tr("undo_empty"))

    pairs = [(Path(entry["target"]), Path(entry["source"])) for entry in entries]
    for current, original in pairs:
        if not os.path.lexists(current):
            raise RenameError(tr("undo_missing_current", path=current))
        if os.path.lexists(original):
            raise RenameError(tr("undo_target_occupied", path=original))

    staged: list[tuple[Path, Path]] = []
    moved: list[tuple[Path, Path]] = []
    try:
        for current, _original in pairs:
            temp = _unique_temp(current.parent)
            os.rename(current, temp)
            staged.append((temp, current))
        for (temp, _current), (_cur, original) in zip(staged, pairs):
            os.rename(temp, original)
            moved.append((original, temp))
    except OSError as exc:
        for target, temp in reversed(moved):
            try:
                os.rename(target, temp)
            except OSError:
                pass
        for temp, current in reversed(staged):
            try:
                if os.path.lexists(temp):
                    os.rename(temp, current)
            except OSError:
                pass
        raise RenameError(tr("undo_failed", detail=exc.strerror or exc)) from exc

    payload["undone"] = True
    payload["undone_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        record_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return UndoResult(len(pairs), record_path)
