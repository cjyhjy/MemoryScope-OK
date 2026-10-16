#!/usr/bin/env bash
# Build dist/memoryscope-ok_<version>_<arch>.deb (offline-installable; dependency wheels bundled).
#
#   bash scripts/build_deb.sh                         # on openKylin: native arch and python3 version
#   bash scripts/build_deb.sh --arch arm64 --python 3.12   # cross-build (e.g. from macOS)
#   sudo dpkg -i dist/memoryscope-ok_*.deb
#   memoryscope-ok all configs/demo-smoke.yaml        # synthetic self-check, no API calls
#   memoryscope-ok all                                # two real agents on configs/agents.yaml
#
# The builder is scripts/build_deb.py (stdlib + pip only, no dpkg-deb needed). postinst creates
# /opt/memoryscope-ok/.venv without ensurepip; each user gets a workspace in ~/memoryscope-ok
# (configs, datasets, .env, runs). Agents (codex/dsh) are not bundled: see scripts/setup_openkylin.sh.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-}
if [ -z "$PY" ]; then
  if [ -x "$ROOT/.venv/bin/python" ]; then PY=$ROOT/.venv/bin/python; else PY=python3; fi
fi
exec "$PY" "$ROOT/scripts/build_deb.py" "$@"
