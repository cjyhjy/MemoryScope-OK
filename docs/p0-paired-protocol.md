# P0：可审计的 memory-on / memory-off 配对协议

2026-10-16 云端首轮。协议与结果版本 `paired-1.0`；历史评分器仍为 1.2，历史数据 schema 仍为 1.1。

## 范围与复现

本轮只执行受控 `PairedDemoAgent`，复用 Demo 的确定性字符 bigram 检索。没有模型、工具、网络调用、子进程调用或宿主状态检索能力。Runner 仅为溯源执行本地 git 读取。没有加载 `.env`，不需要配置密钥。代码审计与状态清点证明的是这个 synthetic fixture 的隔离，不是操作系统沙箱或真实 Agent 的隔离。

```bash
.venv/bin/memoryscope validate datasets/paired
.venv/bin/memoryscope check-config configs/paired-demo.yaml --json
.venv/bin/memoryscope run-paired configs/paired-demo.yaml --json
.venv/bin/pytest -q tests/test_paired.py
```

配置必须显式包含 `paired`。普通 `run` 拒绝配对配置，避免悄悄退回只切换 thread ID 的旧协议。`run-paired` 也拒绝没有配对声明的配置。真实 `codex` / `dsh` / `command` 在构造或启动 Adapter 之前返回 `unsupported`，不会查找命令、读取密钥或调用真实 Agent。配置的模型不能被 Demo 实现时同样返回 `unsupported`。

## 两组控制与隔离

| 项目 | memory-on | memory-off |
| --- | --- | --- |
| 公开消息、probe、会话边界 | 同一份有序 steps | 同一份有序 steps |
| 算法/模型 | 相同 Demo 算法，无模型 | 相同 Demo 算法，无模型 |
| 权限 | 无工具、无宿主状态检索 | 相同 |
| 预算 | 同一 `max_calls_per_arm`，预检全程调用数，无重试 | 相同 |
| 每次会话切换的短期上下文 | 清空 | 清空 |
| 声明的长期存储 `demo_memory_list` | 保留 | 清空 |
| 整个独立临时沙箱 | 清空所有文件 | 清空所有文件 |
| 任务文件保留 | `retained_workspace_files: []` | 相同 |

两个 arm 使用不同 Adapter 实例和临时目录。每个 case、Agent、run 都重新分配，不复用既有状态。memory-off 在每个 `new_session` 清空状态，会话内仍可以接收与另一组相同的正常交互。

沙箱清点覆盖隐藏文件、`MEMORY.md`、workspace、home、缓存、会话数据库及其他任意文件名。符号链接只记录类型并删除链接，不跟随其目标。fixture 的实际回答路径只读取内存列表和公开 probe，完全不读取沙箱文件、真实 home、环境变量、缓存或数据库；清空沙箱也防止未来无意复用文件。`MEMORY.md` 在这个 fixture 中不是记忆后端。

每个初始会话和后续会话边界都记录 `paired_isolation`：隔离前后完整短期上下文、长期列表、文件清单（路径、类型、大小、SHA-256）、状态表面映射、允许保留状态与验证范围。Runner 再检查这些内容；缺少证据、遗漏表面或残留状态时返回 `unknown`，停止受污染 arm 的后续步骤，公共差值为 null。执行异常为 `error`，不计为答错。

P0 不支持保留任务文件；非空 allowlist 会在创建产物前被拒绝。这样当前差值只能归属于声明的记忆列表。后续文件复用实验必须预先声明文件清单、记录两组相同的保留文件摘要，并使用独立的文件复用归因；不能沿用当前 `pure_declared_memory_with_no_file_reuse` 标签。

`MEMORYSCOPE_AGENT_HOME` 只是旧 command Adapter 提供的环境变量，任意命令可能忽略它。它不能证明 HOME、XDG、原生会话库、后台进程、远端产品记忆或缓存已被隔离。真实 Adapter 恢复条件是逐项证明这些状态面的控制/观测能力；本轮没有这种证明。

## 回答、失效与删除分别记录

`answers` 与 `storage_checks` 独立，不能用存储检查失败覆盖公共回答正确性，也不能用公共回答正确覆盖删除失败。

| 字段 | 能说明什么 | 不能说明什么 |
| --- | --- | --- |
| `answer_correct` | 既有确定性规则检查所声明回答范围的 include/exclude | 任意自然语言语义都正确 |
| `forbidden_value_not_used` | 在该回答范围内未命中声明的旧值/干扰值 | 旧值在所有推理中不再有效、内部已删除 |
| `specified_store_absence` | 指定可观测存储内的旧值词项是否缺席 | 永久遗忘、原生产品全局删除 |
| `specified_store_deletion` | memory-on 中显式删除约束对应的指定存储终态检查 | 删除操作审计或其他存储副本的删除 |
| `global_deletion_proven` | 本轮恒为 false（没有这项证明） | 全局删除失败或成功的产品判断 |

memory-off 的存储为空由评测器清理造成，因此 `specified_store_deletion` 为 `unknown`，不能算 Agent 成功执行删除。没有删除约束也记 unknown。即使 memory-on 终态缺席判 pass，也只证明声明存储的内容终态，不证明操作路径。

公共差值为相同 probe 上 `answer_correct.score_on − score_off` 的均值，范围 [-1, 1]。仅当两组隔离已验证、步骤/调用数完整且 probe ID 对齐时可比较；unknown 回答不进入分母，同时报告计划 probe 数、可评分对数和覆盖率。两个 arm 的调用预算与实际调用数都保留。存储检查永远不进入该差值。没有六维总分（`overall_score: null`），也没有统计显著性结论。

## 产物与实际证据

每次创建独立 `runs/paired/<run_id>/`，保存 config/dataset 快照、`events.jsonl`、`results.json`、`paired-report.md`、`metadata.json`。记录公开交互摘要、实际发送给 Adapter 的消息/probe、原始回答、评分理由和事件引用；expected 与规则只在评分器及沙箱外的审计产物中出现。临时沙箱在运行完成后清理。元数据记录环境、依赖、协议、源码摘要及五个产物摘要。

`git_commit` 是运行开始时 HEAD；有未提交变更时，以 `source_sha256` 标识实际 Python 源码树，不能把 HEAD 当作已提交源码的证明。本轮证据的 HEAD 是初始基线，源码摘要包含本轮实现。文档和测试不包含在该 Python 包源码摘要中。

本轮实际归档：[paired-p0-20261016](validation/paired-p0-20261016/paired-report.md)。run `20261016T180415254958Z-paired-5ac582b07111`，42 条连续事件，五项产物摘要均核对一致。新单例 `paired-dynamic-update-hard-001` 为**未人工复核的困难草案**，位于独立 `datasets/paired/`；不增加或改写原 48 条候选，也不证明对真实模型有难度。

实际结果：两组各 7 次调用。memory-on 正确回答“致远楼 571”，回答范围未使用旧值，但指定存储仍有 517，删除约束 fail；memory-off 回答不知道，公共回答 fail。公共差值 +1.0，仅为框架机制验证。

历史 48×2 的 95/96 pass 完整保留。这是同模型 deepseek-flash、统一外部 `MEMORY.md` 协议下的历史结果，不是原生产品记忆比较。`dynamic_update-007` 原有回答正确、旧值注明撤销仍保留 517、明确删除约束失败，不能重标为通过。本轮不做历史重评、不改评分器版本。

## 后续边界

- 真实 Adapter 的完整状态隔离仍未证明，配对执行为 unsupported。
- 固定先 on 后 off；重复采样、顺序平衡、真实难度与人工审核待完成。
- 文件保留/复用、语义失效判断、原生存储删除操作审计未实现。
- 新结果独立使用 `paired-1.0`；旧 `report` / `rescore` / `view` / GUI 不支持该格式，并拒绝读取，避免混入历史汇总。
- 本轮环境为 Debian 13 云端 x86_64、Python 3.12.14，不是 openKylin 实机验证。未运行真实 Agent、付费 API、Mac、虚拟机或系统安装。
