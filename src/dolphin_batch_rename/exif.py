"""读取图片的 EXIF 拍摄时间（JPEG / PNG），不依赖第三方库。"""

from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path

_EXIF_IFD = 0x8769
_DATETIME = 0x0132
_DATETIME_ORIGINAL = 0x9003
_TYPE_ASCII = 2


def read_exif_datetime(path: Path) -> datetime | None:
    """返回 EXIF 中的拍摄时间，读取失败或没有 EXIF 时返回 None。"""
    try:
        with open(path, "rb") as handle:
            header = handle.read(8)
            if header.startswith(b"\xff\xd8"):
                tiff = _jpeg_exif(handle)
            elif header.startswith(b"\x89PNG\r\n\x1a\n"):
                handle.seek(0)
                tiff = _png_exif(handle)
            else:
                return None
            if not tiff:
                return None
            return _parse_tiff(tiff)
    except (OSError, ValueError, struct.error):
        return None


def _jpeg_exif(handle) -> bytes | None:
    handle.seek(2)
    while True:
        marker = handle.read(2)
        if len(marker) < 2 or marker[0] != 0xFF:
            return None
        code = marker[1]
        if code in (0xD8, 0x01) or 0xD0 <= code <= 0xD7:
            continue
        if code == 0xDA:  # 图像数据开始，后面不会再有 EXIF
            return None
        length_bytes = handle.read(2)
        if len(length_bytes) < 2:
            return None
        length = int.from_bytes(length_bytes, "big")
        if length < 2:
            return None
        payload = handle.read(length - 2)
        if code == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            return payload[6:]


def _png_exif(handle) -> bytes | None:
    handle.seek(8)
    while True:
        head = handle.read(8)
        if len(head) < 8:
            return None
        length = int.from_bytes(head[:4], "big")
        kind = head[4:8]
        payload = handle.read(length)
        handle.read(4)  # CRC
        if kind == b"eXIf":
            return payload
        if kind == b"IEND":
            return None


def _parse_tiff(data: bytes) -> datetime | None:
    if len(data) < 8:
        return None
    if data[:2] == b"II":
        endian = "<"
    elif data[:2] == b"MM":
        endian = ">"
    else:
        return None
    if struct.unpack_from(endian + "H", data, 2)[0] != 42:
        return None

    first_ifd = struct.unpack_from(endian + "I", data, 4)[0]
    ifd0 = _read_ifd(data, first_ifd, endian)
    if ifd0 is None:
        return None

    candidates: list[str] = []
    exif_pointer = ifd0.get(_EXIF_IFD)
    if exif_pointer:
        offset = _first_long(data, exif_pointer, endian)
        if offset:
            exif_ifd = _read_ifd(data, offset, endian)
            if exif_ifd and _DATETIME_ORIGINAL in exif_ifd:
                candidates.append(_ascii_value(data, exif_ifd[_DATETIME_ORIGINAL], endian))
    if _DATETIME in ifd0:
        candidates.append(_ascii_value(data, ifd0[_DATETIME], endian))

    for text in candidates:
        parsed = _parse_datetime(text)
        if parsed is not None:
            return parsed
    return None


def _read_ifd(data: bytes, offset: int, endian: str) -> dict[int, tuple[int, int, int]] | None:
    if offset < 8 or offset + 2 > len(data):
        return None
    count = struct.unpack_from(endian + "H", data, offset)[0]
    entries: dict[int, tuple[int, int, int]] = {}
    position = offset + 2
    for _ in range(min(count, 512)):
        if position + 12 > len(data):
            break
        tag, kind, number = struct.unpack_from(endian + "HHI", data, position)
        value_or_offset = struct.unpack_from(endian + "I", data, position + 8)[0]
        entries[tag] = (kind, number, value_or_offset)
        position += 12
    return entries


def _first_long(data: bytes, entry: tuple[int, int, int], endian: str) -> int | None:
    kind, number, value = entry
    if number < 1:
        return None
    if kind in (3, 4) and number == 1:  # SHORT / LONG 直接内联
        return value if kind == 4 else value & 0xFFFF
    if value + 4 > len(data):
        return None
    return struct.unpack_from(endian + "I", data, value)[0]


def _ascii_value(data: bytes, entry: tuple[int, int, int], endian: str) -> str:
    kind, number, value = entry
    if kind != _TYPE_ASCII or number == 0:
        return ""
    if number <= 4:
        raw = value.to_bytes(4, "little" if endian == "<" else "big")[:number]
    else:
        raw = data[value : value + number]
    return raw.split(b"\x00", 1)[0].decode("ascii", "ignore").strip()


def _parse_datetime(text: str) -> datetime | None:
    text = text.strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
