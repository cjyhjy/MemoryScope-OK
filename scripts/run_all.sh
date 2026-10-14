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
set +e
"$MS" run "$CONFIG" 2>&1 | tee "$LOG"
STATUS=${PIPESTATUS[0]}
set -e
RUN_DIR=$(grep -Eo '(/[^ ]*)?runs/[0-9TZ]+-[0-9a-f]+' "$LOG" | tail -1)
rm -f "$LOG"
if [ -z "$RUN_DIR" ] || [ ! -f "$RUN_DIR/results.json" ]; then
  echo "评测没有生成结果（退出码 $STATUS）" >&2
  exit 1
fi
[ "$STATUS" = 0 ] || echo "注意：评测退出码 $STATUS（有 error 等非通过状态），仍生成报告" >&2

step "生成报告"
"$MS" report "$RUN_DIR" >/dev/null || true
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
