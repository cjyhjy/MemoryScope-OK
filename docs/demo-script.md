# 演示录屏脚本（3–5 分钟，openKylin 桌面）

状态：脚本已定稿，尚未录制。依据 [openKylin 官方赛题交付段](https://www.openkylin.top/news/4094-cn.html)（2026-10-15 核验）：在 openKylin 桌面环境演示至少两款智能体评测、多维对比雷达图，提交 3–5 分钟完整录屏。

录制对象是 VMware 中的 openKylin 3.0 ARM64 桌面（UKUI）。所有命令在虚拟机内的终端执行，结果页用虚拟机内的浏览器打开。Mac 只负责录屏软件。

## 录前准备（不录）

1. 已用 `.deb` 安装 MemoryScope-OK（`/mnt/hgfs/msok/check.sh` 会安装、自检，并把 openKylin 48×2 真实结果导入 `~/memoryscope-ok/runs/`）。
2. 终端字体调大（Ctrl+Shift+= 两三次），窗口约占屏幕左 60%；关闭通知。
3. 执行 `cd ~/memoryscope-ok` 和 `R=runs/20261016T064413939014Z-0d5dfa7e5bd8`，再 `clear`。
4. 确认屏幕上没有 `.env` 内容、密钥、个人文件。不要 `cat .env`。
5. 如果想现场跑真实 Agent，`~/memoryscope-ok/.env` 需要有 key，且虚拟机里装好 codex 与 dsh。时间不够就只跑 synthetic 一键流程，并在旁白里说明。

## 分镜

| 时间 | 画面与操作 | 旁白要点 |
| --- | --- | --- |
| 0:00–0:20 | 桌面全景；终端 `head -2 /etc/os-release; uname -m` | 这是 openKylin 3.0 ARM64 桌面，所有演示都在系统内完成 |
| 0:20–0:45 | `dpkg -s memoryscope-ok \| head -3`；`memoryscope-ok --help` | 作品以 .deb 安装，依赖离线打包；命令有 validate、run、report、rescore、view |
| 0:45–1:15 | `memoryscope-ok list-agents`；`memoryscope-ok validate datasets/golden` | 两款真实 Agent：Codex CLI 与 DeepSeek Harness；Demo 标记为 synthetic，不计成绩。数据集 48 条，六维各 8 条，JSONL 可直接追加 |
| 1:15–1:45 | `head -c 600 datasets/golden/dynamic_update.jsonl` | 一条用例是一串步骤：告诉信息、切换会话、更正、再提问、检查存储；expected 只给评分器，Agent 看不到 |
| 1:45–2:30 | `memoryscope-ok all configs/demo-smoke.yaml` | 一键流程：校验、运行、报告、HTML 页。这里用 synthetic 管线演示，不调用 API；真实评测命令相同，只是配置换成 `configs/agents.yaml` |
| 2:30–3:40 | `memoryscope-ok view $R --open`，浏览器打开结果页：雷达图、六维表，滚到逐条结果，状态筛选选 fail | 这是事先在这台 openKylin 上跑完的 48 条 × 2 个真实 Agent，共 96 条结果，耗时约 57 分钟。dsh 100 分，Codex 97.9：唯一失败的 dynamic_update-007，回答对了新值 571，但 MEMORY.md 里还留着旧值 517，被存储检查判失败。每条都有评分理由和 events.jsonl 证据序号 |
| 3:40–4:10 | 回终端 `memoryscope-ok rescore $R` | 评分规则升级时离线重评保存的证据，不重新调用 Agent，原结果保留 |
| 4:10–4:40 | `ls $R`；`head -c 400 $R/metadata.json` | 每次运行都留存配置与数据快照、SHA-256、Agent 版本、评分器版本，可复现、可审计 |
| 4:40–5:00 | 回到结果页雷达图 | 总结：六维、证据化评分、可扩展数据与 Adapter，openKylin 原生运行 |

## 注意

- 全量结果是事先运行的，不是录屏时现场跑出来的；旁白必须这样说，不能暗示现场刚跑完。
- 现场如改跑 `configs/smoke.yaml`（两个真实 Agent 各 1 条），它只有单维数据，总分为空属于正常，不要拿它当六维成绩。
- 录完后在 Mac 上检查时长落在 3–5 分钟，且没有出现密钥或个人信息。
