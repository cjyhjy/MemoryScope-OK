# MemoryScope-OK 评测报告

- Run ID：`20261016T122728161616Z-339acc5fa99a`
- 运行状态：completed
- 性质：**synthetic 管线验证，不是真实 Agent 成绩**
- 用例数：1

维度分 = 100 × 通过 / (通过 + 失败)。unknown、error、unsupported 不计入分母，单独列出并降低覆盖率；任一维度缺失时不计算六维总分。

## 六维得分

| 维度 | demo |
| --- | --- |
| 长期保持 `retention` | 100.0（1/1，覆盖 100.0%） |
| 记忆调用 `retrieval` | null（0/0，覆盖 null） |
| 动态更新 `dynamic_update` | null（0/0，覆盖 null） |
| 相近区分 `disambiguation` | null（0/0，覆盖 null） |
| 边界识别 `boundary` | null（0/0，覆盖 null） |
| 任务复用 `reuse` | null（0/0，覆盖 null） |
| **六维总分** | null |

## 状态分布

| Agent | pass | fail | unknown | error | unsupported |
| --- | --- | --- | --- | --- | --- |
| demo | 1 | 0 | 0 | 0 | 0 |

## Agent 信息

- **demo**：capabilities=['cross_session', 'memory_inspection']

## 未通过的检查（含评分理由）


原始证据见同一运行目录的 `events.jsonl`；每条检查的 `evaluation_event` 指向其事件序号。
