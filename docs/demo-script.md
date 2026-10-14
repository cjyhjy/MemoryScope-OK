# 演示录屏脚本（3–5 分钟，openKylin 桌面）

**录屏工具**：openKylin 自带的截图/录屏工具（麒麟截图，支持录屏）；也可以用 `sudo apt install simplescreenrecorder`。分辨率 1920×1080，终端字号调大到 16 以上。

**录前准备**（不录）：
- 已执行 `bash scripts/setup_openkylin.sh`，`.env` 已填入密钥，`export PATH="$HOME/.local/bin:$PATH"`；
- 提前跑完一次完整评测（约 40 分钟），留好运行目录，录屏时直接展示；
- 准备好终端窗口、文件管理器、图片查看器；
- 确认屏幕上不会出现 `.env` 内容。

| 时间 | 画面 | 操作 / 命令 | 旁白要点 |
| --- | --- | --- | --- |
| 0:00–0:20 | 终端 | `cat /etc/os-release; uname -m; python3 --version` | 在 openKylin 上运行，交代架构和 Python 版本 |
| 0:20–0:45 | 终端 | `memoryscope --help`；`memoryscope list-agents` | 一键 CLI；demo 标为 synthetic，codex 和 dsh 是真实 Agent |
| 0:45–1:30 | 编辑器 | 打开 `datasets/golden/dynamic_update.jsonl`，展示 `dynamic_update-005`（改动后撤销）；再打开 `boundary.jsonl` 的 `boundary-006`（配置行里的 token 不许记） | 步骤化用例：消息 → 新会话 → 提问；exclude 用来捕捉旧值和泄露；`check_memory` 检查存储层 |
| 1:30–2:30 | 终端 | `memoryscope validate datasets/golden`；`.venv/bin/python -m pytest -q`；`memoryscope run configs/smoke.yaml`（现场跑 1 条，约 1 分钟） | 校验和测试先过；现场看到两个 Agent 跨会话作答 |
| 2:30–3:15 | 终端 | `grep -E '"event": "(session_reset\|evaluation)"' runs/<smoke_run>/events.jsonl \| head -4 \| cut -c1-300` | session_reset 证明会话真的切换了；evaluation 带逐词理由和证据序号 |
| 3:15–4:00 | 图片查看器 + 编辑器 | 打开完整评测的 `report/radar.png` 和 `report/report.md` | 六维得分、状态分布、未通过项及理由；指出两个 Agent 的差异 |
| 4:00–4:30 | 终端 | `memoryscope rescore runs/<完整run>` | 评分器升级后离线重评，不需要重跑 Agent，状态变化可追溯 |
| 4:30–5:00 | 终端（可选） | `sudo apt install ./dist/memoryscope-ok_*.deb`；`memoryscope-ok --help` | 提供 .deb 包；结束语：可扩展的数据、可解释的评分、零侵入的隔离 |

**注意**：
- 不要在画面中打开 `.env`，也不要执行 `env`、`printenv` 或 `echo $DEEPSEEK_API_KEY`。
- 现场评测只用 `configs/smoke.yaml`；完整 36 条的结果用事先跑好的运行目录展示。
