#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/kio/servicemenus"
LAUNCHER="$HOME/.local/bin/dolphin-batch-rename"

rm -f "$SERVICE_DIR/dolphin-batch-rename.desktop"
rm -f "$LAUNCHER"

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 --noincremental >/dev/null 2>&1 || true
fi

echo "已移除 Dolphin 服务菜单和启动器（项目目录与撤销记录未删除）。"
echo "Removed the service menu and launcher (project directory and undo history kept)."
