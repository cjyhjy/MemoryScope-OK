#!/usr/bin/env bash
# Build dist/memoryscope-ok_<version>_<arch>.deb on the target machine (openKylin/Debian/Ubuntu).
#
#   bash scripts/build_deb.sh
#   sudo apt install ./dist/memoryscope-ok_*.deb      # or: sudo dpkg -i ...
#   memoryscope-ok all                               # validate + run configs/agents.yaml + report
#
# The package ships the project plus pre-built wheels of every dependency, so installation is offline.
# postinst creates /opt/memoryscope-ok/.venv; each user gets a workspace in ~/memoryscope-ok
# (configs, datasets, .env, runs). Agents (codex/dsh) are not bundled: see scripts/setup_openkylin.sh.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
command -v dpkg-deb >/dev/null || { echo "需要 dpkg-deb（Debian/openKylin 系统自带）" >&2; exit 1; }
PY=${PYTHON:-python3}
VERSION=$("$PY" -c "import re; print(re.search(r'^version = \"([^\"]+)\"', open('pyproject.toml').read(), re.M).group(1))")
ARCH=$(dpkg --print-architecture)
NAME=memoryscope-ok
STAGE=$(mktemp -d)
PKG=$STAGE/${NAME}_${VERSION}_${ARCH}
APP=$PKG/opt/$NAME
trap 'rm -rf "$STAGE"' EXIT

echo "==> 打包 $NAME $VERSION ($ARCH)"
mkdir -p "$APP" "$PKG/DEBIAN" "$PKG/usr/bin"
cp -r src configs datasets pyproject.toml README.md LICENSE .env.example "$APP/"
[ -d docs ] && cp -r docs "$APP/"
find "$APP" -name '__pycache__' -prune -exec rm -rf {} +
rm -rf "$APP"/src/*.egg-info

echo "==> 构建依赖 wheel（离线安装用）"
"$PY" -m pip wheel --wheel-dir "$APP/wheels" ".[dev]"

cat > "$PKG/DEBIAN/control" <<EOF
Package: $NAME
Version: $VERSION
Section: devel
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-venv
Recommends: fonts-noto-cjk
Maintainer: MemoryScope-OK <memoryscope-ok@users.noreply.local>
Description: Long-term memory benchmark for AI agents (MemoryScope-OK)
 Six-dimension, evidence-based evaluation of agent long-term memory:
 retention, retrieval, dynamic update, disambiguation, boundary and reuse.
 Command: memoryscope-ok
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
APP=/opt/memoryscope-ok
if [ "$1" = configure ]; then
  rm -rf "$APP/.venv"
  python3 -m venv "$APP/.venv"
  "$APP/.venv/bin/pip" install --no-index --find-links "$APP/wheels" "memoryscope-ok[dev]" >/dev/null
  echo "MemoryScope-OK installed. Run: memoryscope-ok --help   or   memoryscope-ok all"
fi
EOF

cat > "$PKG/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
rm -rf /opt/memoryscope-ok/.venv
EOF

cat > "$PKG/usr/bin/$NAME" <<'EOF'
#!/bin/sh
# MemoryScope-OK launcher. Per-user workspace: ${MEMORYSCOPE_HOME:-~/memoryscope-ok}.
set -e
APP=/opt/memoryscope-ok
WS=${MEMORYSCOPE_HOME:-$HOME/memoryscope-ok}
if [ ! -f "$WS/pyproject.toml" ]; then
  mkdir -p "$WS"
  cp -r "$APP/configs" "$APP/datasets" "$APP/pyproject.toml" "$WS/"
  cp "$APP/.env.example" "$WS/.env.example"
  [ -f "$WS/.env" ] || { cp "$APP/.env.example" "$WS/.env"; chmod 600 "$WS/.env"; }
  echo "已创建工作目录 $WS；请在 $WS/.env 中填入 DEEPSEEK_API_KEY" >&2
fi
export PATH="$HOME/.local/bin:$PATH"
MS="$APP/.venv/bin/memoryscope"
cd "$WS"
if [ "$1" = all ]; then
  CONFIG=${2:-configs/agents.yaml}
  "$MS" validate datasets/golden
  LOG=$(mktemp)
  set +e
  "$MS" run "$CONFIG" 2>&1 | tee "$LOG"
  set -e
  RUN_DIR=$(grep -Eo '(/[^ ]*)?runs/[0-9TZ]+-[0-9a-f]+' "$LOG" | tail -1)
  rm -f "$LOG"
  [ -n "$RUN_DIR" ] || { echo "评测没有生成运行目录" >&2; exit 1; }
  "$MS" report "$RUN_DIR" >/dev/null || true
  echo "报告：$RUN_DIR/report/report.md"
  echo "雷达图：$RUN_DIR/report/radar.png"
  exit 0
fi
exec "$MS" "$@"
EOF
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/prerm" "$PKG/usr/bin/$NAME"

mkdir -p dist
dpkg-deb --root-owner-group --build "$PKG" "dist/${NAME}_${VERSION}_${ARCH}.deb"
echo "==> 生成 dist/${NAME}_${VERSION}_${ARCH}.deb"
