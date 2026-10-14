# MemoryScope-OK 评测报告

- Run ID：`20261014T130907864234Z-42ff04345691`
- 运行状态：completed
- 性质：真实 Agent 实测
- 用例数：24

维度分 = 100 × 通过 / (通过 + 失败)。unknown、error、unsupported 不计入分母，单独列出并降低覆盖率；任一维度缺失时不计算六维总分。

## 六维得分

| 维度 | codex | dsh |
| --- | --- | --- |
| 长期保持 `retention` | 100.0（4/4，覆盖 100.0%） | 100.0（4/4，覆盖 100.0%） |
| 记忆调用 `retrieval` | 100.0（4/4，覆盖 100.0%） | 100.0（4/4，覆盖 100.0%） |
| 动态更新 `dynamic_update` | 100.0（4/4，覆盖 100.0%） | 100.0（4/4，覆盖 100.0%） |
| 相近区分 `disambiguation` | 100.0（4/4，覆盖 100.0%） | 100.0（4/4，覆盖 100.0%） |
| 边界识别 `boundary` | 100.0（4/4，覆盖 100.0%） | 100.0（4/4，覆盖 100.0%） |
| 任务复用 `reuse` | 100.0（4/4，覆盖 100.0%） | 100.0（4/4，覆盖 100.0%） |
| **六维总分** | 100.0 | 100.0 |

## 状态分布

| Agent | pass | fail | unknown | error | unsupported |
| --- | --- | --- | --- | --- | --- |
| codex | 24 | 0 | 0 | 0 | 0 |
| dsh | 24 | 0 | 0 | 0 | 0 |

## Agent 信息

- **codex**：agent=codex-cli；capabilities=['cross_session', 'memory_inspection', 'workspace_files']；memory_mechanism=workspace MEMORY.md declared via per-case CODEX_HOME/AGENTS.md；model=deepseek-flash；version=codex-cli 0.162.0-alpha.17.2
- **dsh**：agent=deepseek-harness；capabilities=['cross_session', 'memory_inspection', 'workspace_files']；memory_mechanism=workspace MEMORY.md declared via per-case DSH_HOME/AGENTS.md；model=None；version=0.2.0-rc.2

## 未通过的检查（含评分理由）


原始证据见同一运行目录的 `events.jsonl`；每条检查的 `evaluation_event` 指向其事件序号。
