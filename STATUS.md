# 项目状态

更新日期：2026-10-14（UTC）。项目根目录：`/Users/cjy/Documents/MemoryScope-OK`。本文件只记录已实际执行并核对过的事实。

## 当前结论

- 版本 **0.2.0**，评分器 **1.2**，提交 `ac3a318`。
- 数据集 `datasets/golden`：**24 条**用例，六维各 4 条（schema 1.1，steps 格式），`review_status` 均为 draft。48 条目标尚未完成。
- 两个真实 Agent（Codex CLI、DeepSeek Harness）已在 macOS 上完成一次完整、无错误的评测。
- **尚未在 openKylin 上安装或运行。** 虚拟机已建好，系统未装（见下文）。

## 已实现

- CLI：`validate`、`list-agents`、`run`、`report`、`rescore`（离线重评已保存证据，不调用 Agent）。
- 用例格式：steps（message / new_session / probe），probe 级 expected 只交给评分器，不传给 Agent。
- 结果状态 pass / fail / unknown / error / unsupported 分开记录。维度分 = 100 × pass / (pass + fail)，其余状态不进分母，但会降低覆盖率。任一维度缺失时六维总分为 null。
- 评分器 1.2（确定性规则，无 LLM）：
  - `contains` 与 `answer_line`（只评最后一行“答案：”）两种规则。
  - 拉丁字母/数字词按边界匹配，下划线视为分隔符。
  - “星期X/礼拜X”统一为“周X”，礼拜天/星期天/周天统一为周日。
- Adapter：Demo（synthetic）、Codex CLI（`codex exec --json`，DeepSeek OpenAI 兼容接口，model `deepseek-flash`）、DeepSeek Harness（`dsh --profile headless --json`）。
  - 每个 case 使用独立的临时 home（`CODEX_HOME`/`DSH_HOME`）和工作区，不读写 `~/.codex`、`~/.dsh`。
  - new_session 会开新线程。长期记忆仅为工作区 `MEMORY.md`，每步后保存快照作为存储证据。
  - 密钥只从项目 `.env` 读入当前进程环境变量，不写入配置、事件或报告。
- 报告：JSON / CSV / Markdown / 雷达图（matplotlib），从保存的 results 离线重建。
- Run 记录：配置与数据快照、文件 SHA-256、git commit、评分器版本、Agent 版本（0.2.0 起在 `start()` 之后记录）。

## 已执行验证（2026-10-14，macOS）

环境：macOS 26.5.1，Apple M5 Pro（arm64），项目 `.venv` Python 3.13.15；codex-cli 0.162.0-alpha.17.2；dsh 0.2.0-rc.2。

| 命令 | 结果 |
| --- | --- |
| `.venv/bin/python -m pip install -e '.[dev]'` | 成功 |
| `.venv/bin/pytest -q` | **63 passed**（含评分器 1.2 新增 5 条参数化用例） |
| `memoryscope --version` | 0.2.0 |
| `memoryscope validate datasets/golden` | 24 cases / 6 files，有效 |
| `memoryscope run configs/demo.yaml` | 退出 0，synthetic，run `20261014T065010954632Z-5dcb8ba8b36b` |
| `memoryscope rescore runs/20261013T185847074474Z-e26d88f7bfa9` | 评分器 1.2 重评旧 run，4 项 fail→pass（下划线文件名、星期写法），输出 `rescore-20261014T064914583919Z/` |
| `memoryscope run configs/agents.yaml` | 退出 0，run `20261014T130907864234Z-42ff04345691`，见下 |

## 完整真实 Agent 评测

- Run：`runs/20261014T130907864234Z-42ff04345691`
  - 13:09–13:33 UTC，约 24 分钟，状态 completed，574 条事件。
  - 提交 `ac3a318`，评分器 1.2。
- 报告副本：[docs/results/report.md](docs/results/report.md)、[docs/results/radar.png](docs/results/radar.png)。

| 维度 | codex（Codex CLI + deepseek-flash） | dsh（DeepSeek Harness） |
| --- | --- | --- |
| retention | 100.0（4/4） | 100.0（4/4） |
| retrieval | 100.0（4/4） | 100.0（4/4） |
| dynamic_update | 100.0（4/4） | 100.0（4/4） |
| disambiguation | 100.0（4/4） | 100.0（4/4） |
| boundary | 100.0（4/4） | 100.0（4/4） |
| reuse | 100.0（4/4） | 100.0（4/4） |
| **六维总分** | **100.0** | **100.0** |

- 状态分布：两个 Agent 都是 24 pass / 0 fail / 0 unknown / 0 error / 0 unsupported。覆盖率均 100%。
- 上一次 run（`…e26d88f7bfa9`）codex 有 2 条 error，原因是网络断线（Reconnecting）。本次没有。

## 局限与解读

1. **区分度不足**：在当前 24 条 draft 用例上两个 Agent 都是满分，无法比较二者，雷达图是两个重合的满分多边形。需要更难的用例：更长干扰、多次更新链、相近实体更多、需主动调用而非直接提问、文件/工具复用。
2. 长期记忆机制是由评测框架声明的 `MEMORY.md` 约定（两个 Agent 相同），测的是“Agent 是否按约定读写外部记忆文件”，不是各产品原生的记忆功能。
3. 每个 Agent 只跑了 1 次，没有重复采样和方差。
4. 评分只用确定性规则。LLM Judge 尚未实现；否定和引用之类的语义只靠 `answer_line` 规避。
5. 仅在 macOS 上验证过；openKylin、Python 3.10 解释器上的完整测试、.deb 打包均未做。
6. README 仍是旧版描述（写的是 1 条用例），需更新。
7. 比赛规则、截止时间和提交要求尚未从官方来源核实。

## openKylin 虚拟机准备（2026-10-14）

已在 VMware Fusion 26.0.0 中新建独立虚拟机 `~/Virtual Machines.localized/openKylin-3.0-ARM64.vmwarevm`：Other Linux 6.x 64-bit Arm、UEFI、4 vCPU、8 GB 内存、80 GB NVMe。现有 Ubuntu 虚拟机未改动。

拟用官方 `openKylin-Server-V3.0-2026.8.27-3-arm64.iso`，官网公布的 MD5 为 `29e1ba9b3d2f8fa088f308ea4d83b6ea`。由用户自行下载。**系统尚未安装，openKylin 内未做任何项目验证。**
