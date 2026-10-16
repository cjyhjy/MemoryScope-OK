# 演示录屏脚本（3–5 分钟，openKylin 桌面）

状态：演示方案，尚未录制；不得把本脚本的准备步骤当作已完成验证。

依据：[openKylin 官方赛题交付段](https://www.openkylin.top/news/4094-cn.html)，2026-10-15 核验：在 openKylin 桌面环境演示至少两款智能体评测、多维对比雷达图及 3–5 分钟完整录屏。

录制 VMware 中的 openKylin 桌面，在其中的终端运行 CLI，在其中打开报告与雷达图。GUI 完成并验证后，由 Claude 补入界面操作；CLI 与 GUI 读取同一份实际结果，不预设展示分数。

## 录前准备

- 已完成同环境全量运行：`runs/20261016T064413939014Z-0d5dfa7e5bd8`，48 条 draft cases × 2 个真实 Agent，共 96 条结果。不要改用旧 macOS 36 条报告或 synthetic 结果。
- 设 `R=runs/20261016T064413939014Z-0d5dfa7e5bd8`，查看 metadata 中的 OS、数据摘要和评分器。不要用全局 `runs/*` 或“最新文件”混合不同运行。
- 已有完整报告可用 `memoryscope report "$R" --reuse` 核对；旧格式报告若不支持 --reuse，保留原产物，选用新生成的可追踪运行。
- `configs/smoke.yaml` 对两个真实 Agent 各运行一条，用于现场短演示；它只有单维数据，不用于展示完整六维成绩。`configs/demo-smoke.yaml` 是 synthetic 自检，必须明确标识，不能替代真实 Agent 演示。
- 不预先承诺真实 API 响应时长。若采用“现场短运行 + 展示事先完成的全量结果”，画面和旁白明确区分两个 run；赛事方是否接受该安排仍需核实，不能为凑时长把缓存产物说成现场刚跑完。
- 进入项目虚拟环境，确认屏幕不会显示密钥、私人文件或账户信息。录屏工具可在 Mac 上捕获虚拟机窗口，作品的运行和结果展示均在 openKylin 内。

## 建议画面顺序

| 时间 | openKylin 中的画面与操作 | 说明 |
| --- | --- | --- |
| 0:00–0:25 | 桌面、系统版本；终端执行 `head -4 /etc/os-release`、`uname -m` | 展示真实系统与架构 |
| 0:25–0:55 | `memoryscope --help`、`memoryscope list-agents --json` | CLI 入口、可扩展 Adapter、synthetic 标识 |
| 0:55–1:20 | `memoryscope check-config configs/smoke.yaml --json`，查看一条用例的步骤 | 配置预检不调用 API；解释跨 session 协议和证据 |
| 1:20–2:30 | `memoryscope run configs/smoke.yaml --jsonl` | 现场执行两个 Agent，观察进度及最终产物目录；时间以实际响应为准 |
| 2:30–3:10 | 查看本次短 run 的结果、session_reset 与具体评分理由 | 解释 pass/fail/unknown/error/unsupported，不把完成等同通过 |
| 3:10–4:15 | 打开同环境全量报告、`xdg-open "$R/report/radar.png"` | 明示 RUN_ID、48×2 结果、100% 覆盖率，以及 Codex 97.9 / dsh 100.0；图表在 openKylin 内显示 |
| 4:15–4:45 | `memoryscope rescore "$R" --json` | 离线重评保存为新修订，原证据与原结果保留，不重调 Agent |
| 4:45–5:00 | 展示运行目录与复现入口 | 明确已验证范围和后续扩展点 |

GUI 就绪后，可用其配置页、运行进度、对比图和证据详情替换相应画面，但数据来源及边界不变。脚本仍未录制；若现场短 run 得分变化，应明确它与上述已保存全量 run 是两次不同执行。
