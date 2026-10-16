# 演示录屏脚本（3–5 分钟，openKylin 桌面，GUI 主线）

状态：脚本已定稿，尚未录制。要求来源：[openKylin 赛题页](https://www.openkylin.top/news/4094-cn.html)。在 openKylin 桌面环境中，对至少两款智能体运行评测，产出多维对比雷达图，提交 3–5 分钟的完整录屏。

录制对象是 VMware 中的 openKylin 3.0 ARM64 桌面（UKUI）。所有操作都在虚拟机里完成，Mac 只运行录屏软件。

## 录前准备（不录）

1. 已运行 `/mnt/hgfs/msok/check.sh`。它会安装 .deb（如果系统不允许，会装到用户目录），并把 openKylin 上 48×2 的真实结果导入 `~/memoryscope-ok/runs/`。
2. 关闭通知，打开一个终端，调大字号。当前验收使用用户目录安装：先执行 `export PATH="$HOME/.local/bin:$PATH"`，再 `cd ~/memoryscope-ok`。系统级安装按用户要求暂缓。
3. 确认屏幕上不会出现 `.env` 内容、密钥或个人文件。
4. 第 4 段要现场跑真实 Agent 时，需要 `~/memoryscope-ok/.env` 里有 key，并且虚拟机里装好了 codex 和 dsh。不具备这些条件的话，第 4 段改用 demo（synthetic），旁白要说明。

## 分镜

| 时间 | 画面与操作 | 旁白要点 |
| --- | --- | --- |
| 0:00–0:20 | 桌面全景；终端执行 `head -2 /etc/os-release; uname -m` | 这是 openKylin 3.0 ARM64 桌面，全部演示都在系统内完成 |
| 0:20–0:45 | `memoryscope-ok --version`；`memoryscope-ok --help` | 作品提供 .deb，当前演示使用从包中解出的用户目录安装，依赖已离线打包；CLI 提供 validate、run、report、rescore 等命令，也可以一键执行 `memoryscope-ok all` |
| 0:45–1:10 | `head -c 500 datasets/golden/dynamic_update.jsonl`；`memoryscope-ok validate datasets/golden` | 数据集 48 条，六个维度各 8 条。每条用例是 JSONL 里的一行：message 是发给 Agent 的提示词，new_session 表示换一个新会话，probe 表示提问并评分，expected 是评分依据（Agent 看不到）。想改提示词或加题，直接编辑或追加一行，用 validate 检查格式，再在配置的 dataset 字段指向这个目录就能跑 |
| 1:05–1:20 | 从开始菜单打开“MemoryScope-OK”（或终端执行 `memoryscope-ok gui`） | GUI 和 CLI 共用同一套评测核心 |
| 1:20–2:10 | “新建评测”页：数据集选 `datasets/smoke`，勾选 codex 和 dsh，点“预检配置”，再点“开始评测”并确认 | 预检不调用 API。开始后能看到 case 完成进度，结束后自动生成报告并跳到结果页。说明这只是每个 Agent 跑 1 条的短演示。顺带一句：其他命令行 Agent 写进 configs/custom-agents.yaml 就会出现在这里，勾选即可参评 |
| 2:10–3:30 | “评测结果”页：在左侧选中 `20261016T064413939014Z-0d5dfa7e5bd8`，指着雷达图和六维表讲；在逐条结果里把状态筛选为 fail，选中 `dynamic_update-007`，点“查看证据事件” | 这是事先在这台 openKylin 上跑完的 48 条 × 2 个真实 Agent，共 96 条结果，用时约 57 分钟。dsh 得 100 分，Codex 得 97.9 分。Codex 唯一失败的一条：回答里用对了新值 571，但 MEMORY.md 里还写着旧值 517，因此存储检查判它失败。每条结果都附有评分理由和 events 证据编号 |
| 3:30–3:50 | 切到“运行环境与可追溯信息”页 | 页面上有系统、Python、评分器版本，以及数据和结果的 SHA-256，可以复现和审计 |
| 3:50–4:15 | 切到“报告与重评”页，点“离线重评” | 评分规则升级后，可以对已保存的证据离线重评，不需要再调用 Agent，原结果也会保留 |
| 4:15–4:40 | 回到雷达图 | 总结：六个维度、基于证据的确定性评分、可扩展的数据集和 Adapter，在 openKylin 上原生运行 |

## 注意

- 全量结果是事先跑好的，不是录屏时现场跑出来的，旁白必须明确这一点。
- `datasets/smoke` 只覆盖一个维度，所以这次短运行的总分为空是正常的，不要拿它当六维成绩。
- 录完后检查：时长在 3–5 分钟之间，画面里没有出现密钥或个人信息。
