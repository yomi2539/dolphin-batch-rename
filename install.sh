#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kio/servicemenus"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/dolphin-batch-rename"

echo "==> 准备 Python 环境 / Preparing Python environment"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
    if command -v uv >/dev/null 2>&1; then
        uv venv "$ROOT/.venv"
    else
        python3 -m venv "$ROOT/.venv"
    fi
fi

if ! "$ROOT/.venv/bin/python" -c "import PySide6" >/dev/null 2>&1; then
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$ROOT/.venv/bin/python" PySide6-Essentials
    else
        "$ROOT/.venv/bin/pip" install PySide6-Essentials
    fi
fi

echo "==> 安装启动器 / Installing launcher"
mkdir -p "$BIN_DIR"
chmod +x "$ROOT/bin/dolphin-batch-rename"
ln -sf "$ROOT/bin/dolphin-batch-rename" "$LAUNCHER"

echo "==> 安装 Dolphin 服务菜单 / Installing Dolphin service menu"
mkdir -p "$SERVICE_DIR"
sed "s|@LAUNCHER@|$LAUNCHER|g" \
    "$ROOT/packaging/dolphin-batch-rename.desktop" \
    > "$SERVICE_DIR/dolphin-batch-rename.desktop"
# 用户目录下的服务菜单必须可执行，否则 Dolphin 报「没有此文件的执行权限」
chmod +x "$SERVICE_DIR/dolphin-batch-rename.desktop"

echo "==> 刷新 KDE 服务缓存 / Refreshing KDE service cache"
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 --noincremental >/dev/null 2>&1 || true
fi

echo
echo "安装完成。在 Dolphin 中选中文件 → 右键 →「批量重命名」。"
echo "Installed. Select files in Dolphin → right-click → \"Batch Rename\"."
