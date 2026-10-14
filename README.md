# MemoryScope-OK

面向 openKylin 的 AI Agent **长期记忆**自动化评测 Benchmark。数据集可扩展，用例以步骤描述，评分基于证据并给出可解释的理由，在六个维度上比较真实 Agent 的跨会话记忆能力：

| 长期保持 | 记忆调用 | 动态更新 | 相近区分 | 边界识别 | 任务复用 |
| --- | --- | --- | --- | --- | --- |
| `retention` | `retrieval` | `dynamic_update` | `disambiguation` | `boundary` | `reuse` |

当前状态：版本 0.2.0，36 条用例（六维各 6 条），已接入 Codex CLI 和 DeepSeek Harness 两个真实 Agent，在 macOS 上实测通过；openKylin 实机验证待完成。详见 [STATUS.md](STATUS.md)。

## 快速开始

openKylin / Debian / Ubuntu：

```bash
bash scripts/setup_openkylin.sh   # 系统依赖、.venv、用户级 Node 24、codex 与 dsh
vi .env                           # 填入 DEEPSEEK_API_KEY（只保存在本地，已加入 .gitignore）
bash scripts/run_all.sh           # 校验 → 测试 → 两个 Agent 完整评测 → 报告与雷达图
```

只安装 Python 部分（任意 Python 3.10+ 系统）：

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
| `memoryscope run configs/agents.yaml` | 运行评测，写入 `runs/<run_id>/`（含 events.jsonl 证据） |
| `memoryscope report runs/<run_id>` | 生成 JSON / CSV / Markdown / 雷达图，不调用 Agent |
| `memoryscope rescore runs/<run_id>` | 用当前评分器离线重评已保存证据 |
| `python scripts/dataset_table.py` | 输出数据集审阅表 |

配置：`configs/agents.yaml` 跑完整评测，`configs/smoke.yaml` 每个 Agent 各跑 1 条，`configs/demo.yaml` 是 synthetic 自检。

## 文档

- [方案文档](docs/SOLUTION.md)：测试目标、架构、隔离、数据、评分、结果、局限、创新点
- [数据集审阅表](docs/dataset-review.md)
- [实测报告](docs/results/report.md) 与 [雷达图](docs/results/radar.png)
- [演示录屏脚本](docs/demo-script.md)
- [进度](STATUS.md) / [待办](TODO.md) / [开发约定](AGENTS.md) / [贡献指南](CONTRIBUTING.md)

## 安全

- 密钥只从环境变量或项目 `.env` 读取，不会写入配置、日志或报告。
- 每个用例使用独立的临时 Agent home 和工作区，不读写 `~/.codex`、`~/.dsh`。
- 数据全部虚构。

许可证：[MIT](LICENSE)。
