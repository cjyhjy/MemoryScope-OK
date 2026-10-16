#!/usr/bin/env bash
# Validate the dataset, run the tests, run a benchmark config and build its report.
#
#   bash scripts/run_all.sh                     # configs/agents.yaml (two real agents)
#   bash scripts/run_all.sh configs/smoke.yaml  # one short case per agent
#   bash scripts/run_all.sh configs/demo.yaml   # synthetic pipeline check, no API calls
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONFIG=${1:-configs/agents.yaml}
cd "$ROOT"
export PATH="${MEMORYSCOPE_PREFIX:-$HOME/.local}/bin:$PATH"
MS=.venv/bin/memoryscope
[ -x "$MS" ] || { echo "未找到 $MS，请先运行 bash scripts/setup_openkylin.sh" >&2; exit 1; }

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "数据集校验"
"$MS" validate datasets/golden

step "单元与集成测试"
.venv/bin/python -m pytest -q

step "评测：$CONFIG"
LOG=$(mktemp)
trap 'rm -f "$LOG"' EXIT
set +e
"$MS" run "$CONFIG" --json | tee "$LOG"
STATUS=${PIPESTATUS[0]}
set -e
RUN_DIR=$(.venv/bin/python - "$LOG" <<'PY'
import json
import sys
from pathlib import Path
try:
    message = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    data = message.get("data") or {}
    path = data.get("run_dir")
    if message.get("schema_version") != "1.0" or not isinstance(path, str):
        raise ValueError("no run directory in CLI result")
    print(path)
except (OSError, ValueError, TypeError, AttributeError) as error:
    print(f"无法读取评测结果：{error}", file=sys.stderr)
    sys.exit(1)
PY
) || exit 1
if [ -z "$RUN_DIR" ] || [ ! -f "$RUN_DIR/results.json" ]; then
  echo "评测没有生成结果（退出码 $STATUS）" >&2
  exit 1
fi
[ "$STATUS" = 0 ] || echo "注意：评测退出码 $STATUS（有 error 等非通过状态），仍生成报告" >&2

step "生成报告"
if ! "$MS" report "$RUN_DIR" --reuse --json; then
  echo "报告生成失败；原始结果保留在 $RUN_DIR" >&2
  exit 1
fi
REPORT="$RUN_DIR/report"
echo "运行目录：$RUN_DIR"
echo "Markdown 报告：$REPORT/report.md"
echo "雷达图：$REPORT/radar.png"
echo "CSV / JSON：$REPORT/report.csv  $REPORT/report.json"
sed -n '/## 六维得分/,/## Agent 信息/p' "$REPORT/report.md"

if command -v xdg-open >/dev/null && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  xdg-open "$REPORT/radar.png" >/dev/null 2>&1 &
fi
exit "$STATUS"
