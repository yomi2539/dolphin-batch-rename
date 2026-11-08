#!/usr/bin/env bash
# 构建发布包 / Build release artifact
#   dist/dolphin-batch-rename-<版本>.run   单文件自解压安装器（chmod +x 后直接运行）
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/src/dolphin_batch_rename/__init__.py")"
[ -n "$VERSION" ] || { echo "无法读取版本号 / cannot read version" >&2; exit 1; }

NAME="dolphin-batch-rename-$VERSION"
DIST="$ROOT/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$DIST" "$STAGE/$NAME"
cp -a \
    "$ROOT/bin" \
    "$ROOT/packaging" \
    "$ROOT/src" \
    "$ROOT/tests" \
    "$ROOT/install.sh" \
    "$ROOT/uninstall.sh" \
    "$ROOT/README.md" \
    "$STAGE/$NAME/"
find "$STAGE/$NAME" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$STAGE/$NAME" -type f -name '*.pyc' -delete

TARBALL="$STAGE/$NAME.tar.gz"
tar --sort=name --owner=0 --group=0 --numeric-owner \
    --mtime="@${SOURCE_DATE_EPOCH:-$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || date +%s)}" \
    -czf "$TARBALL" -C "$STAGE" "$NAME"

# 单文件自解压安装器：安装到 ~/.local/share/dolphin-batch-rename 后调用 install.sh
RUNNER="$DIST/$NAME.run"
cat > "$RUNNER" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail

DEST="${XDG_DATA_HOME:-$HOME/.local/share}/dolphin-batch-rename"
LOG="${TMPDIR:-/tmp}/dolphin-batch-rename-install.log"

notify() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -a "Dolphin Batch Rename" "$@" >/dev/null 2>&1 || true
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --passivepopup "$*" 10 >/dev/null 2>&1 || true
    fi
}

finish() {
    local code=$?
    if [ "$code" -ne 0 ]; then
        if [ ! -t 1 ]; then
            notify -u critical "安装失败 / Installation failed" "日志 / Log: $LOG"
        fi
        echo "安装失败，日志：$LOG / Installation failed, see $LOG" >&2
    fi
    exit "$code"
}
trap finish EXIT

mkdir -p "$DEST"
SKIP="$(awk '/^__ARCHIVE_BELOW__$/{print NR + 1; exit}' "$0")"
tail -n "+$SKIP" "$0" | tar xz -C "$DEST" --strip-components=1

if [ -t 1 ]; then
    "$DEST/install.sh"
else
    "$DEST/install.sh" >"$LOG" 2>&1
    notify "安装完成，在 Dolphin 中右键使用。" "Installed. Right-click in Dolphin to use."
fi
exit 0
__ARCHIVE_BELOW__
STUB
cat "$TARBALL" >> "$RUNNER"
chmod +x "$RUNNER"

echo "构建完成 / Built:"
ls -lh "$RUNNER"
echo
echo "分发 / Distribute: 单个文件，chmod +x 后直接运行（或文件管理器中双击）"
