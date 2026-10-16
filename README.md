# MemoryScope-OK

面向 openKylin 的 AI Agent **长期记忆**自动化评测 Benchmark。数据集可扩展，用例以步骤描述，评分基于证据并给出可解释的理由，在六个维度上比较真实 Agent 的跨会话记忆能力：

| 长期保持 | 记忆调用 | 动态更新 | 相近区分 | 边界识别 | 任务复用 |
| --- | --- | --- | --- | --- | --- |
| `retention` | `retrieval` | `dynamic_update` | `disambiguation` | `boundary` | `reuse` |

当前目标为可扩展的 MVP：CLI 与 GUI 共用评测核心，Codex 负责 CLI，Claude 负责 GUI。CLI 版本 0.3.0，当前有 48 条候选用例（质量复核待完成）。2026-10-16 已在 openKylin 3.0 ARM64 / Python 3.12.2 上完成 Codex CLI 与 DeepSeek Harness 两个真实 Agent 的全量评测，共产生 96 条 case 结果；Codex 47/48、六维总分 97.9，dsh 48/48、总分 100.0，覆盖率均为 100%。详见 [STATUS.md](STATUS.md) 与 [openKylin 真实评测记录](docs/validation/openkylin-real-20261016.md)。桌面 GUI（PySide6）提供结果浏览（雷达图、六维表、逐条评分理由、证据事件、报告与重评）和新建评测（配置、异步运行、进度），通过同一 CLI 执行；`memoryscope view` 另可生成离线 HTML 结果页。

## 快速开始

2026-10-16 云端 P0 新增[可审计配对协议](docs/p0-paired-protocol.md)：
`.venv/bin/memoryscope run-paired configs/paired-demo.yaml --json`。
当前仅支持受控 synthetic 离线单例；真实 Adapter 隔离未证明时返回 unsupported。公共回答、旧值非使用与指定存储删除检查分开，任务文件不保留。历史 48×2 为同模型、统一 `MEMORY.md` 协议结果，不能当作原生产品记忆比较；原有 95/96 与删除失败不变。

作品材料：

- [作品介绍 PDF](docs/submission/MemoryScope-OK-作品介绍.pdf)
- [演示视频下载（GitHub Release）](https://github.com/cjyhjy/MemoryScope-OK/releases/download/v0.3.0-demo/memoryscope-ok-demo.mp4)
- [视频剪辑工程](video/README.md)

视频中的现场单例使用 synthetic Demo，仅展示框架运行与实时进度；48×2 雷达图和逐条评分来自事先完成的 openKylin 真实 Agent 评测。视频成片作为 Release 附件分发，不纳入 Git 历史。

openKylin / Debian / Ubuntu：

```bash
bash scripts/setup_openkylin.sh   # 系统依赖、.venv、用户级 Node 24、codex 与 dsh
vi .env                           # 填入 DEEPSEEK_API_KEY（只保存在本地，已加入 .gitignore）
bash scripts/run_all.sh           # 校验 → 测试 → 两个 Agent 完整评测 → 报告与雷达图
```

只安装 Python 部分（Python 3.10+ 且具备 venv/ensurepip；本次 openKylin 缺失该组件的用户目录替代方案见 [验证记录](docs/openkylin-validation.md)）：

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'
.venv/bin/memoryscope run configs/demo.yaml   # synthetic 管线自检，不调用 API
```

`.deb` 包（依赖 wheel 已打包，离线安装，不依赖 python3-venv/ensurepip）：

```bash
bash scripts/build_deb.sh                              # 在 openKylin 上按本机架构与 Python 构建
bash scripts/build_deb.sh --arch arm64 --python 3.12   # 或在其他机器上交叉构建
sudo dpkg -i dist/memoryscope-ok_0.3.0_arm64.deb
memoryscope-ok all configs/demo-smoke.yaml             # synthetic 自检，不调用 API
memoryscope-ok all                                     # 两个真实 Agent 完整评测 + 报告 + HTML 结果页
```

## 命令

| 命令 | 作用 |
| --- | --- |
| `memoryscope validate datasets/golden` | 校验数据 schema 与 ID 唯一性 |
| `memoryscope list-agents` | 列出 Adapter 及其是否为 synthetic |
| `memoryscope check-config configs/agents.yaml --json` | 离线预检配置、数据与路径；不创建 Agent 或调用 API |
| `memoryscope run configs/agents.yaml` | 运行评测，写入 `runs/<run_id>/`（含 events.jsonl 证据） |
| `memoryscope run-paired configs/paired-demo.yaml --json` | 受控 synthetic memory-on/off 配对，保存独立结果与 `paired-report.md`；不调用真实 Agent |
| `memoryscope report runs/<run_id>` | 生成 JSON / CSV / Markdown / 雷达图，不调用 Agent |
| `memoryscope rescore runs/<run_id>` | 用当前评分器离线重评已保存证据 |
| `memoryscope-gui`（需 `pip install -e '.[gui]'`；.deb 中为 `memoryscope-ok gui`） | 桌面 GUI：历史结果、新建评测与进度、证据查看 |
| `memoryscope view runs/<run_id> [--open]` | 生成自包含 HTML 结果页 `view.html`（雷达图、得分、逐条评分理由），不联网、不调用 Agent |
| `python scripts/dataset_table.py` | 输出数据集审阅表 |

配置：`configs/agents.yaml` 跑完整评测，`configs/smoke.yaml` 每个 Agent 各跑 1 条，`configs/demo.yaml` 是 synthetic 自检。

GUI/脚本可给各命令加 `--json` 读取版本化结果；`run --jsonl` 实时输出不含提示词和响应的生命周期进度，最后一条 result 给出实际运行目录及产物路径。`report --reuse --json` 可复用来源匹配的完整报告。具体字段与失败处理见 [CLI/GUI 接口](docs/CLI_GUI_HANDOFF.md)。

最小离线验证用 `memoryscope run configs/demo-smoke.yaml --jsonl`（1 条 synthetic 用例，不调用 API）。当前 48 条仍为 draft；这次 96 条真实结果证明执行闭环，不等于数据已完成独立质量复核。新增 Agent/评分器沿现有接口扩展，无需增加 Web 服务或数据库。

若系统依赖已具备，或使用 OSTree 桌面而不进行系统包变更，可用 `SKIP_SYSTEM=1 SKIP_AGENTS=1 bash scripts/setup_openkylin.sh` 仅在项目虚拟环境安装 Python 部分。它不会自动启用系统开发模式；缺失的 Python/venv 依赖仍需明确解决，不能跳过后声称验证通过。

## 接入其他 Agent

除内置的 Codex CLI 与 DeepSeek Harness 外，任何能“接收一段提示词、在 stdout 输出回答”的命令行 Agent 都可以在配置中声明，无需写代码：

```yaml
agents:
  - id: my-agent
    type: command
    name: My Agent CLI
    command: ["my-agent", "--prompt", "{prompt}"]   # 参数列表，不经过 shell；{prompt} 替换为本轮消息
    timeout_seconds: 300
```

把条目写进运行配置即可用 CLI 运行；复制 [configs/custom-agents.example.yaml](configs/custom-agents.example.yaml) 为 `configs/custom-agents.yaml`，GUI“新建评测”页会自动列出，勾选即可。命令型 Agent 使用每例独立工作目录，并接收 `MEMORYSCOPE_AGENT_HOME` 环境变量及 `MEMORY.md` 约定。任意命令可能忽略该变量，当前没有强制切断真实 HOME、缓存、会话库或远端状态，不能据此宣称完整隔离。约定附在每条提示词前，框架不提供通用会话续接；命令自身如何保存上下文仍须独立验证。P0 配对命令对它返回 unsupported。需要深度集成（续接会话、解析工具事件）时，再按 `adapters/` 下的方式写 Adapter。

## 修改或新增用例

用例在 `datasets/<目录>/*.jsonl`，一行一条，格式见 `datasets/schema/case.schema.json` 与[方案文档第 4 节](docs/SOLUTION.md)。

1. 复制一行改 `id`（同一数据集内唯一，如 `retention-009`）、`category` 和 `steps`：`message` 的 `content` 就是发给 Agent 的提示词，`new_session` 切换会话，`probe` 提问并按 `expected.include / exclude` 评分，`check_memory` / `check_file` 检查记忆内容和工作区文件。第一个 probe 之前必须有 `new_session`，保证测的是跨会话记忆。
2. `memoryscope validate datasets/<目录>` 检查格式与 ID 唯一性。
3. 复制 `configs/agents.yaml`，把 `dataset` 指向该目录，然后 `memoryscope run <配置>`；GUI 的“新建评测”页也可以直接选择该目录。

## 文档

- [CLI 与图形界面接口约定及 GUI 实现说明](docs/CLI_GUI_HANDOFF.md)
- [openKylin 桌面部署记录](docs/openkylin-deployment.md)：系统安装、启动兼容参数、资源与验证边界
- [openKylin 48×2 真实评测记录](docs/validation/openkylin-real-20261016.md)：环境、隔离、结果、完整性与边界
- [方案文档](docs/SOLUTION.md)：测试目标、架构、隔离、数据、评分、结果、局限、创新点
- [数据集审阅表](docs/dataset-review.md)
- [P0 配对协议、指标边界与云端 synthetic 证据](docs/p0-paired-protocol.md)
- openKylin 48×2 实测结果副本：[报告](docs/results/openkylin-48x2/report.md)、[雷达图](docs/results/openkylin-48x2/radar.png)、[HTML 结果页](docs/results/openkylin-48x2/view.html)、results.json / metadata.json；完整证据在 `runs/`（不入库）。`docs/results/macos-36/` 为 macOS 36 条历史结果
- [演示录屏脚本](docs/demo-script.md)
- [进度](STATUS.md) / [待办](TODO.md) / [开发约定](AGENTS.md) / [贡献指南](CONTRIBUTING.md)

## 安全

- 密钥只从环境变量或项目 `.env` 读取，不会写入配置、日志或报告。
- 内置 CLI Adapter 配置独立的临时 Agent home 和工作区；这不是完整 OS 沙箱证明。通用 command 可能忽略 home 环境变量，完整配对隔离仍 unsupported。
- 数据全部虚构。

许可证：[MIT](LICENSE)。
