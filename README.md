# MemoryScope-OK

面向 openKylin 的 AI Agent **长期记忆**自动化评测 Benchmark。数据集可扩展，用例以步骤描述，评分基于证据并给出可解释的理由，在六个维度上比较真实 Agent 的跨会话记忆能力：

| 长期保持 | 记忆调用 | 动态更新 | 相近区分 | 边界识别 | 任务复用 |
| --- | --- | --- | --- | --- | --- |
| `retention` | `retrieval` | `dynamic_update` | `disambiguation` | `boundary` | `reuse` |

当前目标为可扩展的 MVP：CLI 与 GUI 共用评测核心，Codex 负责 CLI，Claude 负责 GUI。CLI 版本 0.3.0，当前有 48 条候选用例（质量复核待完成）。2026-10-16 已在 openKylin 3.0 ARM64 / Python 3.12.2 上完成 Codex CLI 与 DeepSeek Harness 两个真实 Agent 的全量评测，共产生 96 条 case 结果；Codex 47/48、六维总分 97.9，dsh 48/48、总分 100.0，覆盖率均为 100%。详见 [STATUS.md](STATUS.md) 与 [openKylin 真实评测记录](docs/validation/openkylin-real-20261016.md)。GUI 当前待实现。

## 快速开始

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

`.deb` 包：`bash scripts/build_deb.sh` 会生成 `dist/memoryscope-ok_<版本>_<架构>.deb`。安装后运行 `memoryscope-ok all`。

## 命令

| 命令 | 作用 |
| --- | --- |
| `memoryscope validate datasets/golden` | 校验数据 schema 与 ID 唯一性 |
| `memoryscope list-agents` | 列出 Adapter 及其是否为 synthetic |
| `memoryscope check-config configs/agents.yaml --json` | 离线预检配置、数据与路径；不创建 Agent 或调用 API |
| `memoryscope run configs/agents.yaml` | 运行评测，写入 `runs/<run_id>/`（含 events.jsonl 证据） |
| `memoryscope report runs/<run_id>` | 生成 JSON / CSV / Markdown / 雷达图，不调用 Agent |
| `memoryscope rescore runs/<run_id>` | 用当前评分器离线重评已保存证据 |
| `python scripts/dataset_table.py` | 输出数据集审阅表 |

配置：`configs/agents.yaml` 跑完整评测，`configs/smoke.yaml` 每个 Agent 各跑 1 条，`configs/demo.yaml` 是 synthetic 自检。

GUI/脚本可给各命令加 `--json` 读取版本化结果；`run --jsonl` 实时输出不含提示词和响应的生命周期进度，最后一条 result 给出实际运行目录及产物路径。`report --reuse --json` 可复用来源匹配的完整报告。具体字段与失败处理见 [CLI/GUI 接口](docs/CLI_GUI_HANDOFF.md)。

最小离线验证用 `memoryscope run configs/demo-smoke.yaml --jsonl`（1 条 synthetic 用例，不调用 API）。当前 48 条仍为 draft；这次 96 条真实结果证明执行闭环，不等于数据已完成独立质量复核。新增 Agent/评分器沿现有接口扩展，无需增加 Web 服务或数据库。

若系统依赖已具备，或使用 OSTree 桌面而不进行系统包变更，可用 `SKIP_SYSTEM=1 SKIP_AGENTS=1 bash scripts/setup_openkylin.sh` 仅在项目虚拟环境安装 Python 部分。它不会自动启用系统开发模式；缺失的 Python/venv 依赖仍需明确解决，不能跳过后声称验证通过。

## 文档

- [CLI 与图形界面分工和接口约定](docs/CLI_GUI_HANDOFF.md)：Claude 接手 GUI 的入口；GUI 当前待实现
- [openKylin 桌面部署记录](docs/openkylin-deployment.md)：系统安装、启动兼容参数、资源与验证边界
- [openKylin 48×2 真实评测记录](docs/validation/openkylin-real-20261016.md)：环境、隔离、结果、完整性与边界
- [方案文档](docs/SOLUTION.md)：测试目标、架构、隔离、数据、评分、结果、局限、创新点
- [数据集审阅表](docs/dataset-review.md)
- [openKylin 实测报告](runs/20261016T064413939014Z-0d5dfa7e5bd8/report/report.md) 与 [雷达图](runs/20261016T064413939014Z-0d5dfa7e5bd8/report/radar.png)；`docs/results/` 保留旧 macOS 36 条历史结果
- [演示录屏脚本](docs/demo-script.md)
- [进度](STATUS.md) / [待办](TODO.md) / [开发约定](AGENTS.md) / [贡献指南](CONTRIBUTING.md)

## 安全

- 密钥只从环境变量或项目 `.env` 读取，不会写入配置、日志或报告。
- 每个用例使用独立的临时 Agent home 和工作区，不读写 `~/.codex`、`~/.dsh`。
- 数据全部虚构。

许可证：[MIT](LICENSE)。
