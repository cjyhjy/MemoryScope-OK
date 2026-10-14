# MemoryScope-OK 方案文档

面向 openKylin 的 AI Agent 长期记忆自动化评测 Benchmark。版本 0.2.0，评分器 1.2，数据 schema 1.1。

## 1 测试目标

只测**跨会话**的长期记忆。每个用例先在一个或多个会话中写入信息，再在新会话中提问或布置任务，Agent 此时看不到之前的对话，只能依靠自身的长期记忆。不跨会话、仅靠当前上下文就能答对的题，不算长期记忆题，schema 校验会拒绝这类用例（第一个 probe 之前必须有 `new_session`）。

| 类别值 | 维度 | 考察内容 | 典型失败 |
| --- | --- | --- | --- |
| `retention` | 长期保持 | 在多次干扰和会话切换后仍能回忆唯一事实 | 忘记；与相似事实（预发/生产端口）混淆 |
| `retrieval` | 记忆调用 | 任务不提“记得吗”，Agent 需主动调出并组合多条约定 | 用默认值（22 端口、main 分支、example.com） |
| `dynamic_update` | 动态更新 | 信息被修改、撤销修改、多字段分次更新后使用最新状态 | 用旧值；撤销后仍用改动后的值；只更新部分字段 |
| `disambiguation` | 相近区分 | 名称/数字极相近的实体、同名不同组织的人 | 张冠李戴 |
| `boundary` | 边界识别 | 不该记的不记（密码、token）、临时信息不当长期事实、过时信息不再使用 | 泄露敏感值；把“今天临时”当长期事实 |
| `reuse` | 任务复用 | 把记住的模板、命名规则、风格迁移到新任务，并在工作区真实生成文件 | 只口头答应不建文件；格式不符 |

## 2 系统架构

```text
datasets/*.jsonl ──► Runner ──► Adapter ──► 真实 Agent（codex / dsh 子进程）
     (用例)            │            │
configs/*.yaml ───────┘            └─► 证据：回答、工具事件、MEMORY.md 快照、工作区文件
                                     │
                      events.jsonl ◄─┘（每一步一条事件，带序号与时间戳）
                                     │
                     规则评分器（answer_line / contains / check_memory / check_file）
                                     │
                     results.json ──► report：JSON / CSV / Markdown / 雷达图
                                     └─► rescore：用新评分器离线重评已保存证据
```

- **Runner**（`runner.py`）：按 steps 顺序驱动用例，处理 `reset_case` / `reset_session`，把每一步写入 `events.jsonl`。
- **Adapter**（`adapters/`）：统一接口 `start / reset_case / reset_session / send_message / execute_task / collect_evidence / shutdown`。目前有三个实现：Demo（标为 synthetic，只用于测框架）、Codex CLI、DeepSeek Harness。新增 Agent 只需实现一个 Adapter。
- **评分器**（`evaluator.py`）：确定性规则，不调用 LLM。
- **报告**（`reporting.py`）与**重评**（`rescore.py`）都只读已保存的文件，不会再调用 Agent。

## 3 隔离与公平性

- **零侵入**：每个用例都有自己的临时 `CODEX_HOME` / `DSH_HOME` 和工作区，位于项目之外的临时目录。不读写用户的 `~/.codex`、`~/.dsh`，也不改 shell 配置。
- **相同的记忆约定**：两个 Agent 拿到同一份用户级 `AGENTS.md`，声明工作区 `MEMORY.md` 是唯一的跨会话记忆，由 Agent 自行决定记什么、何时读写。所以本测试比较的是“Agent 能否按约定维护外部记忆”，不是各产品原生的记忆功能。
- **会话边界**：新会话就是新线程，看不到历史；同一会话内续接同一线程（codex `exec resume`，dsh `--session-id`）。
- **用例之间**：`reset_case` 换新目录，同一命名空间不能复用。Agent 之间各有自己的沙箱目录。
- **相同模型**：两者都用 `deepseek-flash`（DeepSeek 接口目前提供的 Flash 模型名）。codex 在临时 `config.toml` 中指定该模型，走 DeepSeek OpenAI 兼容接口。dsh 用 `--patch` 覆盖层固定 `agent-default-model` 的模型，启动时再用 `dsh --dump-config` 读回实际生效的模型，记入 `describe.effective_model`；读回的值与配置不一致就拒绝运行。
- **答案隔离**：expected 只交给评分器，Adapter 只能拿到 `Probe(content)`，测试会验证这一点。
- **密钥**：只从环境变量或项目 `.env` 读入当前进程，不写入配置、事件或报告。manifest 里只记录加载了哪些变量名。

## 4 数据设计

Schema 1.1 用一个有序的 `steps` 列表描述用例：

| step 类型 | 作用 |
| --- | --- |
| `message` | 用户发一条消息（写入信息、更新、干扰） |
| `new_session` | 结束当前会话，开一个新会话 |
| `probe` | 提问并评分（`expected.include/exclude` + `evaluation.type`） |
| `check_memory` | 检查 Agent 存下的长期记忆内容（存储层证据） |
| `check_file` | 检查 Agent 在工作区中实际创建的文件（行为证据，路径不能越出工作区） |

Schema 1.0（固定 setup/updates/distractors/probe）由 `upgrade_case` 显式转换为 1.1，并保留 `source_schema_version`。

设计原则：

- 所有值都是虚构且无法凭常识猜中的，例如端口 5734、机柜 R7-C14-U31、`bk-tern-04.lab.internal`。
- 难度来自机制而不是措辞：更多干扰、更多会话切换、多条约定组合、撤销修改、近似实体、部分敏感信息。
- 用 `exclude` 词捕捉典型错误：旧值、相近实体、泄露的敏感值、默认值。
- 目前 36 条，六维各 6 条（每维 2 条 hard），均为 `review_status: draft`。审阅表见 [dataset-review.md](dataset-review.md)，可用 `python scripts/dataset_table.py` 重新生成。

## 5 自动评分

- `answer_line`：只看最后一行 `答案：…`，避免解释里提到被否定的选项而误判。`contains`：看整段回答。
- 拉丁字母/数字词按边界匹配（`uv` 不会命中 `uvicorn`），下划线视为分隔符（`OSC204_KJ` 能命中 `20261014_OSC204_KJ.pdf`）。中文词按子串匹配。
- 星期写法归一：星期三/礼拜三 → 周三，星期天/礼拜天/周天 → 周日。
- `check_memory`：对 `MEMORY.md` 快照应用同样的 include/exclude 规则。`check_file`：检查文件是否存在及其内容。
- 每一条检查都输出逐词的命中/未命中理由，并指向对应的证据事件序号（`evaluation_event`）。

| 状态 | 含义 | 是否计入分母 |
| --- | --- | --- |
| pass | 全部 include 命中、exclude 均未命中 | 是 |
| fail | 有 include 未命中或 exclude 命中 | 是 |
| unknown | 无法判定（如没有 `答案：` 行） | 否，降低覆盖率 |
| error | Agent 调用失败（网络、超时、退出码） | 否，降低覆盖率 |
| unsupported | Adapter 不具备该用例所需能力 | 否，降低覆盖率 |

- 维度分 = 100 × pass / (pass + fail)。
- 覆盖率 = (pass + fail) / 用例数。
- 六维总分 = 六个维度分的平均值；任一维度缺失时为 null，不用 0 或满分去补。
- `memoryscope rescore <run>`：用当前评分器重新评一次已保存的证据，结果写入新的 `rescore-*` 目录，并列出状态变化，不调用 Agent。评分器 1.1→1.2 就是这样修正了 4 处误判。

## 6 证据与可复现

每次 run 都会生成一个唯一目录 `runs/<run_id>/`：

- `metadata.json`：git commit、评分器版本、数据与配置文件的 SHA-256、Python/依赖/系统信息、Agent 版本。
- `config.snapshot.yaml`、`dataset.snapshot.jsonl`：本次运行用的配置和数据快照。
- `events.jsonl`：逐步事件，包括发送的消息、Agent 回答、工具事件、`MEMORY.md` 快照、会话重置、评分及理由。
- `results.json`：用例和维度结果。`report/` 下是 JSON、CSV、Markdown 和雷达图。

## 7 在 openKylin 上运行

```bash
bash scripts/setup_openkylin.sh   # apt 依赖、.venv、用户级 Node 24、codex 与 dsh（npm）
vi .env                           # 填入 DEEPSEEK_API_KEY
bash scripts/run_all.sh           # 校验 → pytest → 评测 → 报告与雷达图
bash scripts/build_deb.sh         # 可选：生成 dist/memoryscope-ok_<版本>_<架构>.deb
sudo apt install ./dist/memoryscope-ok_*.deb && memoryscope-ok all
```

dsh 在 macOS 上运行在 DeepSeek Harness 桌面应用内部。它的 CLI 以 `@deepseek-ai/dsh` 发布在 npm 上（MIT，与 Mac 上的版本相同，提供 Linux x64/arm64 的沙箱组件），Linux 上用 npm 安装。**上述脚本尚未在 openKylin 实机上验证。**

## 8 实测结果

见 [results/report.md](results/report.md) 和 [results/radar.png](results/radar.png)。

RESULTS_PLACEHOLDER

## 9 局限

- 记忆机制是评测框架统一声明的 `MEMORY.md` 约定，不是各产品原生的记忆功能。
- 每个 Agent 只跑了 1 次，没有重复采样和方差。
- 只用确定性规则评分，开放式语义判断有限；LLM Judge 尚未实现（设计上默认关闭，且不能覆盖事实检查）。
- 36 条均为 draft，尚未经过独立人工复核；目标是 48 条。
- 目前只在 macOS 上实测过；openKylin 实机验证和 .deb 安装待完成。

## 10 创新点

1. **步骤化用例**：消息、会话切换、提问、存储检查、文件检查自由组合，可以表达撤销、分次更新、长干扰链。
2. **存储层证据**：`check_memory` 直接检查 Agent 存了什么，区分“没说出来”和“确实没记”。
3. **行为证据**：`check_file` 检查 Agent 真的在工作区建了文件，而不是口头承诺。
4. **严格状态与分母**：error、unknown、unsupported 不混入失败，覆盖率单独报告，缺维度不给总分。
5. **离线重评**：评分规则升级后不必重跑 Agent，结果可追溯到评分器版本。
6. **零侵入隔离**：每个用例使用独立的临时 home 和工作区，不碰用户原有的 Agent 配置。
