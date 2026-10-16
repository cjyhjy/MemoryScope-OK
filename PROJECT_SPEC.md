# MemoryScope-OK 项目说明书

> 架构评审补充（2026-10-13）：见 [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)。其中保存了提前接入真实 Agent、对照实验、步骤化用例、行为评分与离线重评、能力与观测范围、openKylin 初验六点建议，以及建议执行顺序。原 Phase 编号和验收标准保留；建议的落实情况由 STATUS/TODO 记录。

> 文档版本：1.0；制定日期：2026-10-13。本文是目标规范，不是功能已实现的声明。
> 实际完成情况以 `STATUS.md`、测试记录和带来源的运行产物为准。

## 1. 项目定位与要求来源

MemoryScope-OK 是面向 openKylin 的 AI Agent 长期记忆自动化 Benchmark。
它提供统一的数据集、执行协议、证据、评分和报告，用于比较不同 Agent 的记忆能力。
项目提供 CLI 与图形界面，共用同一评测核心；不开发新的记忆 Agent。2026-10-15 用户追加图形界面范围：Codex 负责核心和 CLI，Claude 负责 GUI，接口与交接见 [CLI_GUI_HANDOFF.md](docs/CLI_GUI_HANDOFF.md)。

2026-10-15 用户明确本项目当前交付为 MVP 简化版：先让现有 CLI 闭环与 GUI 接口可靠可用；核心、Adapter、评分与展示保持边界，便于后续扩展。48 条数据扩展和可选 Judge 保留为后续目标，不为架构完整而增加 Web 服务、数据库或大型插件系统。

本说明书区分三类信息：

| 标记 | 含义 | 使用方式 |
| --- | --- | --- |
| 用户要求 | 当前任务明确指定的范围 | 作为项目交付目标 |
| 开发建议 | 为可靠实现而确定的技术方案 | 可经说明和测试后调整 |
| 官方待核实 | 尚无已核验比赛原文支撑的事项 | 不可写成比赛硬性要求或符合性结论 |

本文件中的六维能力、技术栈、48 条扩展目标和阶段划分来自用户要求。
2026-10-15 已核验 [openKylin 官方赛题说明](https://www.openkylin.top/news/4094-cn.html) 的交付要求：代码在 openKylin 上编译运行，提供一键 CLI，建议提供 .deb；在 openKylin 桌面环境演示至少两款智能体评测及多维对比雷达图，提交 3–5 分钟完整录屏。其余完整规则、最新提交安排及最终符合性仍需逐项核实；GUI 是用户追加范围。

## 2. 范围与完成层级

核心流程：配置 → 数据校验 → Agent 初始化 → 记忆写入 → 干扰/更新 → session 隔离 → probe → evidence → 评分 → 报告。

| 层级 | 目标 | 不应据此宣称 |
| --- | --- | --- |
| Phase 1 | 可安装包、CLI、基础 schema、测试与说明 | 完整 Benchmark 已完成 |
| Phase 2 | 1 条 retention 用例、离线 Demo、跨 session、真实执行所得 JSON | 完成真实 Agent 评测 |
| Phase 3 | 六类各 2 条，共 12 条 seed，形成六维执行覆盖 | 48 条数据集完成或覆盖充分 |
| Phase 4–6 | 评分、至少两个真实 Agent、完整报告 | openKylin 已通过验证 |
| Phase 7 | 六类各 8 条，共 48 条高质量 golden cases | 官方要求固定为 48 条 |
| Phase 8–9 | openKylin 验证与比赛材料 | 尚未核验的硬件/系统具有兼容性 |

首轮交付优先完整 Markdown、Phase 1 和 Phase 2 可运行骨架；后续阶段按计划实施。
48 条是扩展目标，不是首轮完成门槛；12 条 seed 通过复审后纳入 48 条，不重复计数。
不得用预先编造的分数、Mock 输出或人工替换的响应冒充运行结果。

## 3. 六项评测能力

| 类别值 | 能力与正例 | 必须控制的混淆因素 |
| --- | --- | --- |
| `retention` | 写入“Python 项目使用 uv”，经历干扰和 session 切换后仍采用 uv | probe 不重复答案；新 session 不携带旧对话 |
| `retrieval` | 写入论文目录，后续相关任务主动使用正确目录 | 只证明保存不足够；记录是否在相关任务中调用 |
| `dynamic_update` | 编辑器从 VS Code 改为 Cursor，后续采用 Cursor | 陈旧记忆仍作为有效偏好使用应计错；合理说明旧值不能简单误判 |
| `disambiguation` | 工作/课程/个人数据库分别不同，只为课程选择 MySQL | 用实体和项目作用域区分；干扰项结构相近 |
| `boundary` | 区分稳定偏好、临时上下文、敏感信息与过时信息，按其性质控制持久化和使用 | 不应长期保存/使用的内容与可保存内容分开判定；不可观察的存储行为记 unknown |
| `reuse` | 在新任务中组合已知路径、工具偏好与命名约定形成正确方案 | 要求迁移应用，不仅照抄一个事实；评分任务结果中的实际使用 |

Boundary 的必备子类为 `stable_preference`（稳定偏好，允许按指令长期使用）、`temporary_context`（临时上下文，作用域结束后不再当成稳定偏好）、`sensitive_information`（敏感信息，按用例明确的不保存/不泄露约束）、`obsolete_information`（过时信息，不再作为当前有效事实使用）。
`unsafe_instruction`、跨用户/项目访问和删除验证作为扩展子类；子类定义来自项目需求与开发设计，不代表已确认的比赛评分定义。
敏感信息测试只用明显虚构的凭据、号码等合成值；不引入真实个人信息或可用密钥。
输出没有回忆某信息不证明它未被存储：存储边界需可审计的记忆读写/导出证据；仅能观察输出时只评价使用/泄露边界，并将持久化判断记为 unknown。
真实时间跨度、session 数、干扰数量和上下文长度须记录；短时切换不能宣称数月记忆保持。
每条用例有一个主类别；可附加标签，但主类别聚合不得重复计数。

## 4. 技术栈与工程结构

用户要求：Python 3.10+、Typer、Pydantic、PyYAML、httpx、matplotlib、pytest。
开发建议：`src` 布局、UTF-8 文本、`pathlib` 路径、显式配置、最少必要依赖。
Typer 负责 CLI，Pydantic 负责契约，PyYAML 负责配置，httpx 负责后续远程 Adapter。
matplotlib 负责无界面雷达图；pytest 覆盖协议和评分等关键行为。
依赖版本由已验证的构建约束或锁定文件管理；不得把未测试版本范围写成兼容性结论。

建议目标结构（目录可按实现阶段逐步增加）：

```text
MemoryScope-OK/
  PROJECT_SPEC.md  IMPLEMENTATION_PLAN.md  AGENTS.md
  STATUS.md  TODO.md  README.md  pyproject.toml
  configs/demo.yaml
  datasets/golden/retention.jsonl     # 首轮 1 条；Phase 3 各类 2 条；Phase 7 各类 8 条
  datasets/golden/retrieval.jsonl     # 以下五个文件从 Phase 3 起逐步增加
  datasets/golden/dynamic_update.jsonl
  datasets/golden/disambiguation.jsonl
  datasets/golden/boundary.jsonl
  datasets/golden/reuse.jsonl
  src/memoryscope/
    cli.py  models.py  runner.py
    adapters/                        # Demo 与真实集成明确分离
    evaluators/                      # 规则优先，可选 Judge
    reporting/                       # 后续 JSON/CSV/Markdown/图
  tests/
  docs/
  runs/                              # 默认不入版本控制
```

允许首轮将小模块合并，待功能增长后拆分；不得为目录完整而制造空实现。

## 5. 标准化 JSONL 数据集

每行一个独立 JSON 对象；空行处理应明确，损坏行必须报告文件、行号和原因。
同一数据集 `id` 唯一；不认识的版本、类别、协议或 evaluator 必须明确拒绝或标记不支持。
校验禁止依靠隐式猜测转换字段；任何迁移必须保存原版本和迁移记录。

| 字段 | 类型/用途 | 首轮范围 |
| --- | --- | --- |
| `schema_version` | 字符串，当前为 `"1.0"` | 必须验证 |
| `id` | 稳定且非空的用例 ID | 必须唯一 |
| `category` | 六种类别之一 | 首轮只执行 retention |
| `description` | 人类可读的测试意图 | 必填 |
| `setup` | `{role, content}` 消息数组 | 支持用户消息写入 |
| `updates` | 后续纠正或替换事实的消息数组 | 可为空；语义执行后续扩展 |
| `distractors` | 无关/相近干扰消息数组 | 可为空 |
| `probe` | `{type, content}`，测试请求 | 首轮仅 `type: question` |
| `expected` | `{include: string[], exclude: string[]}` | 首轮包含/排除约束 |
| `evaluation` | evaluator 及参数配置 | 首轮仅 `type: contains` |
| `protocol` | 执行协议、session 与截断策略 | 首轮 `mode: cross_session` |
| `metadata` | 当前为 `{difficulty, tags}` | `difficulty` 必填且为 easy/medium/hard；tags 默认空数组 |

示例为公开测试输入，不是预先生成的 Agent 结果：

```json
{"schema_version":"1.0","id":"retention_uv_001","category":"retention","description":"跨 session 后保持 Python 依赖管理偏好","setup":[{"role":"user","content":"以后我的 Python 项目都使用 uv 管理依赖。"}],"updates":[],"distractors":[{"role":"user","content":"我今天整理了书架。"}],"probe":{"type":"question","content":"帮我创建一个新的 Python 项目，你会采用什么依赖管理工具？"},"expected":{"include":["uv"],"exclude":["pipenv"]},"evaluation":{"type":"contains"},"protocol":{"mode":"cross_session"},"metadata":{"difficulty":"easy","tags":["preference","session_switch"]}}
```

`expected` 和评分规则仅供执行器/evaluator 使用，禁止交给被测 Agent。
当前 ID 限 1–80 个 ASCII 字母、数字、下划线、点或连字符，首字符须为字母或数字；消息 role 仅接受 user/assistant。
`setup` 与 `expected.include` 至少含一项；文本不能为空；include/exclude 忽略大小写后不允许重复、交集或必含词包含禁含词。
来源、作者、边界子类及复审等质量信息先记录在数据说明或 tags，新增结构字段须先扩展并版本化 schema；当前拒绝未知字段。
后续 action、工具调用、结构化答案、删除及多用户协议须通过显式 schema 扩展加入。
解析接受一个字段不等于支持其语义；未实现能力必须停止执行或报告 `unsupported`。
每条 golden case 应含：测试目的、唯一关键事实、合理 probe、独立预期、评分理由、失败反例。
避免 48 条仅替换名词；覆盖不同实体、干扰强度、更新次数、作用域和复用方式。
发布前人工复审歧义、隐含答案、真实个人信息、规则误判和模板泄漏；记录复审者与版本。

## 6. 统一 Adapter 契约

Adapter 将被测 Agent 的差异封装为统一接口，不在 evaluator 中写厂商分支。
目标接口至少包含：

```text
describe() -> identity, version, kind, capabilities
reset_case(namespace) -> 清空或新建该用例的独立持久记忆空间
ingest(messages) -> 写入/交互结果和 evidence
reset_session() -> 新建短期对话，保留当前用例的持久记忆
probe(request) -> response, tool events, usage, timing
close() -> 释放连接和测试资源
```

`reset_case` 和 `reset_session` 语义不可互换；前者隔离用例，后者测试持久记忆。
最小接口可以使用不同函数名，但必须有测试证明上述语义。
首轮接口采用 `start`、`reset_case`、`reset_session`、`send_message`、`execute_task`、`collect_evidence`、`shutdown`，分别覆盖启动、隔离、会话、写入、probe、证据与清理；完整能力声明属于后续扩展。
能力声明包括持久记忆、独立 session、namespace 隔离、更新、删除、导出记忆和工具 evidence。
不支持的能力不可默认为成功；例如无法创建独立 session 的 Adapter 不能参加跨 session 保持结论。
对外部 Agent 无法验证的内部行为如实写 `unknown`，记录能观察的边界与限制。
所有请求设置超时；重试次数与规则入配置，保留尝试记录，防止重复写入污染状态。
Agent 请求报错与能力失败分开统计；中止/重试不能悄悄筛掉困难用例。

## 7. Demo、基线与真实 Agent 的资格

首轮 Demo 为离线确定性实现，只检验管线、证据和协议；所有结果标记 `synthetic: true`。
可实现具有可查看持久状态的参考基线，但须标明实现范围与局限。
Mock、返回硬编码答案、按 case ID 查答案、读取 `expected` 或为题目定制响应均不算真实 Agent 评测。
裸语言模型在单次请求中接收完整旧对话，只能作为上下文基线，不能等同长期记忆 Agent。

项目至少评测两个真实 Agent；上述官网交付段也明确要求演示至少两款智能体。
真实 Agent 应运行可确认的实际系统，具备自身记忆存储/检索机制，并接受相同隔离协议。
记录系统名称、版本/提交、模型、记忆配置、接口、运行环境和适配限制。
同一 Agent 仅换两个模型，不自动计作两个独立 Agent；资格在接入前写明。
系统必须实际执行测试并留下原始 evidence，凭配置名称或安装成功不能宣称完成评测。
真实 Agent 的具体选择、获取方式及是否需要账户/API 仍待确认。
未配置凭据时应明确跳过相应集成，保持离线 Demo 可运行，不自动购买 API 或创建付费资源。

## 8. 长期记忆执行协议

跨 session 基本步骤：

1. 创建 `run_id / agent_id / case_id / repetition` 隔离 namespace，并执行 case reset。
2. 在 session A 发送 `setup`，按定义发送 `updates` 和 `distractors`，记录返回与写入 evidence。
3. 执行 `reset_session`；关闭/替换原 conversation ID，清空短期消息历史。
4. 在 session B 仅发送 probe 和必要固定系统提示；保留该 case 的持久记忆空间。
5. 保存请求边界、响应、检索/工具记录和评分，再销毁本 case 的测试状态。

每阶段顺序必须固定且版本化；若未来需要交错 update/distractor，新增显式事件序列。
不得在 session B 注入旧对话、参考答案或由执行器总结的关键事实。
Agent 自己从持久记忆检索到的信息属于被测行为，应记录来源和可观察程度。
证明材料至少包括前后 session 标识、probe 请求消息及 Adapter 隔离方式。
进程内内存保留仅证明跨会话状态保持；重启进程仍保留应作为独立协议另测。

上下文截断是另一种可选协议，不能与跨 session 混为同一实验：

- 声明截断规则、消息/字符/token 上限、tokenizer、保留角色及截断时点。
- 将承载关键事实的早期消息移出实际发送的上下文，保存被移除消息 ID 和最终消息边界。
- token 统计无法取得时报告字符/消息计数，不伪造 token 数。
- 持久记忆由 Agent 自己读取；执行器不得通过摘要或隐藏提示回填被截断事实。
- 保留未截断基线、截断条件及 cross-session 条件各自结果，避免混合比较。

首轮只要求跨 session；上下文截断、进程重启与真实时间延迟均为后续扩展。

## 9. 证据与可复现运行

每次运行使用唯一目录和 run ID；默认不覆盖既有运行，恢复运行须显式校验兼容性。
目标 evidence 采用追加式 JSONL，事件包含时间、序号、run/agent/case/repetition/session 标识、事件类型和 payload。
事件至少覆盖 case reset、输入、响应、session reset、probe、评分与异常；工具/检索事件在可获得时保存。
首轮计划保存 `events.jsonl`，结果以引用关联事件；后续扩展检索、工具和远程调用 evidence。
报告必须能追踪到具体响应、规则版本和输入证据，不能只有汇总分数。

运行 manifest 目标记录：

- 数据集版本与内容哈希、解析后配置与哈希、软件版本/提交和未提交修改状态。
- Python、依赖、OS/CPU、Adapter/Agent/模型版本、持久化位置的脱敏表示。
- 随机种子、采样参数、session/截断规则、超时、重试、顺序与重复次数。
- 开始/结束时间、实际处理用例、错误、缺失 evidence、运行是否完整。

随机种子有助于控制实验，不保证远程模型逐字复现；复现承诺应区分协议与输出。
默认固定数据集顺序和种子；对顺序敏感性及随机性进行重复实验属于后续质量工作。
耗时使用实际测量；token、费用等取实际返回或带来源的估算，否则为 `null/unknown`。
静态价格不可冒充实际账单；首轮不要求费用统计。

## 10. 评分与六维指标

评分先规则后可选 LLM Judge；规则无法可靠判断时报告 unknown，不用模糊匹配掩盖歧义。
首轮 `contains` 仅验证 `include` 全部出现、`exclude` 全部未出现，并输出逐项命中结果，原始每例 `score` 为 1.0 或 0.0。
首轮用 `str.casefold()` 忽略大小写后作子串匹配，不作额外 Unicode 规范化、分词或词边界判断；未来变更须测试并升级 evaluator 版本。
子串匹配不能充分判断否定、推荐方向或历史说明；相关用例应设计明确可判的输出或升级 evaluator。
Phase 4 目标 evaluator 包括 Exact、Contains、NotContains、Regex、JSON 字段、Numeric、File、Tool、Action 和可选 semantic/Judge 插件；逐项定义输入、证据与正反例，未实现者不得静默回退到 contains。
File/Tool/Action 仅基于安全测试空间中的实际证据评分；实体/作用域、更新冲突和路径规范化应有显式规则。
安全行为或拒答不得仅凭单个关键词判断；规则需配正反例测试。

| 结果状态 | 含义 | 聚合原则 |
| --- | --- | --- |
| `pass` | 有充分证据符合判定标准 | 计入可评分成功 |
| `fail` | 有充分证据违反判定标准 | 计入可评分失败 |
| `unknown` | 已执行但证据/判断不足 | 单列，不伪造为 0 或 1 |
| `unsupported` | Adapter/协议/evaluator 不支持 | 单列，降低覆盖率 |
| `error` | 接口、执行、解析等技术错误 | 单列，不当成记忆失败 |
| `skipped` | 未尝试，包含凭据缺失等原因 | 单列并说明原因 |

后续完整聚合对每个 Agent/类别 c 记计划 case-repetition 数为 N_c；全部状态计数之和必须为 N_c。
设 E_c 为具有有效原始 score 且 status 为 pass/fail 的结果集合，n_c = |E_c|；其他状态的 score 必须为 null。
原始每例 s_i ∈ [0,1]；维度、报告及雷达图用 0–100 尺度：D_c = 100 × Σ(i∈E_c) s_i / n_c。
六个 D_c 均非 null 时，总分 M = (D_retention + D_retrieval + D_dynamic_update + D_disambiguation + D_boundary + D_reuse) / 6；任一缺失则 M = null。
二值规则下 D_c 等于 100 × pass_c / (pass_c + fail_c)；未来部分给分须预先定义 rubric，且单列二值通过率，不能将平均部分得分称为准确率。
可评分覆盖率 C_c = 100 × n_c / N_c；运行覆盖率 R_c = 100 × (pass_c + fail_c + unknown_c + error_c) / N_c。
可另列 100 × pass_c / N_c 为“计划任务中的已证实通过比例”，不得替换准确率或隐藏覆盖率。
以上任何公式分母为 0 时均为 null；缺测不补 0、100 或均值；子集平均必须另命名并列出参与类别。
初始 Demo 未实现全部状态或部分给分时，只报告实际支持的结果及其范围，不预填未实现分数。
首轮 vertical slice 的原始 case score 为 0/1、已测维度为 0–100、缺测维度为 null，`overall_score` 始终为 null；完整六维宏平均在后续阶段实现并测试。

六维和辅助指标统一展示百分数，并随指标给出原始分子、分母及适用范围：

| 指标 | 精确定义与分母 |
| --- | --- |
| Retention Accuracy | 100 × retention 通过数 / retention 可评分数 n_retention |
| Retrieval Success Rate | 100 × retrieval 通过数 / retrieval 可评分数 n_retrieval |
| Relevant Memory Usage Rate | 100 × 已证实在当前任务正确使用的必需记忆项数 / 可判定是否正确使用的必需记忆项数；以用例预先列出的 required-memory 项为单位 |
| Update Accuracy | 100 × dynamic_update 通过数 / dynamic_update 可评分数 n_dynamic_update |
| Stale Memory Rate | 100 × 将至少一个已被替换旧值仍作为当前有效值使用的 probe 数 / 存在旧值且能判定其使用方向的 dynamic_update probe 数 |
| Disambiguation Accuracy | 100 × disambiguation 通过数 / disambiguation 可评分数 n_disambiguation |
| Memory Confusion Rate | 100 × 错用其他预定义实体/作用域事实的 probe 数 / 具有相近实体干扰且能判定最终选择的 disambiguation probe 数 |
| Boundary Compliance | 100 × boundary 通过数 / boundary 可评分数 n_boundary；另按四个必备子类给同一公式，存储不可观察的子用例为 unknown |
| Reuse Success Rate | 100 × reuse 通过数 / reuse 可评分数 n_reuse；通过须满足预定义的新任务结果和必需记忆应用约束 |

辅助指标只能按预先标注的旧值、实体关系和 required-memory 项评估，不能从主分数反推；此结构化标注及 evaluator 属于后续扩展。
每个辅助指标还报告观测覆盖率 = 100 × 其可判定分母 / 全部适用项数；缺证据的项记 unknown，未适用项不进入适用总数。
例如只看到输出未包含旧值，不能推断内部未检索旧值；Stale Memory Rate 评价可观察的当前使用，内部检索率另行观测。
若相关行为、适用集合或判断所需证据不可获得，指标及分母均为 null，并说明原因，禁止推定为零泄漏/零混淆。
不同 Agent 同时报共同可评分用例子集与各自覆盖率；不以少量通过用例营造全面领先。
样本数与重复次数必须显示；12 或 48 条的小样本结果不宣称统计显著。

可选 Judge 使用独立配置，记录模型、提示版本、输入、输出、重试和评分理由。
Judge 对 Agent 身份盲化，不接收凭据，将被测输出视为不可信文本，防止指令劫持。
Judge 必须返回经 schema 校验的对象：`{score, status, reason, evidence}`；status 仅为 pass/fail/unknown，reason 非空，evidence 是引用已存在事件 ID 和相关原文片段的数组。
默认二值 rubric 要求 pass→score=1、fail→score=0、unknown→score=null；若启用部分给分，需显式 rubric、阈值及 score/status 一致性校验，禁止越界、NaN 和未知字段。
不得接受自由文本提取出的猜测分数；引用不存在的事件、证据与结论矛盾或结构错误都判为无效 Judge 输出。
开发建议默认每次请求超时 30 秒、最多重试 2 次（总尝试最多 3 次），配置中可收紧但不得无限重试；保留每次输出和失败原因。
Judge 超时、校验最终失败或证据不足均为 unknown；不能自动给满分，也不能为凑结果自动付费调用。
关键事实/安全约束的确定性规则一旦明确失败，最终结果必须为 fail、score=0；Judge 不得覆盖该失败，只能补充解释或评估尚未被规则决定的条件。
规则条件与 Judge 条件的组合在执行前声明；任何必要条件仍未知时，未被硬失败决定的总结果为 unknown，不能靠其他条件平均成通过。
需抽样人工复核、与规则比较，并分别展示规则/Judge 分数及不一致情况。

## 11. CLI、配置与报告

核心入口为 `memoryscope run configs/demo.yaml`；离线配置默认使用 Demo。
首轮 CLI 约定为帮助、`validate PATH`、`list-agents`、`run CONFIG` 和 `report RUN_DIR`。
首轮 `report` 只查看已有 JSON 汇总，完整文档/表格/图导出在 Phase 6 实现。
具体可用选项以 CLI 帮助和 README 为准，避免 CLI 承诺超出已实现能力。
配置须明确数据集、Agent、协议、输出目录、种子及可选超时；相对路径相对于配置文件所在目录解析。
首轮配置示例：

```yaml
schema_version: '1.0'
dataset: ../datasets/golden/retention.jsonl
output_dir: ../runs
agents:
  - id: demo
    type: demo
seed: 0
```

首轮协议由每条用例给出；数据集/输出路径必须是相对路径，解析后不可逃逸最近含 `pyproject.toml` 的项目根。
允许 `../` 指向同一项目内目录，禁止通过符号链接逃逸；数据集也可指定含 JSONL 的目录。
禁止 `eval` 和任意 YAML 对象构造；未知字段、路径错误、重复 ID 和非法值给出可行动的错误消息。
错误退出码与完整/不完整运行状态必须明确，不能报错后以成功摘要掩盖问题。

最终目标产物：manifest、原始 evidence、逐例 JSON、平面 CSV、Markdown 总结和六维雷达图。
首轮目标产物为 `metadata.json`、`results.json`、`events.jsonl`、`config.snapshot.yaml`、`dataset.snapshot.jsonl` 及哈希。
CSV、Markdown 与图在 Phase 6 完成，禁止提交占位图作为实测图。
完整报告位于运行目录的 `report/report.json`、`report/report.csv`、`report/report.md`、`report/radar.png`；运行根目录的 `results.json` 始终保留为逐例事实源。
JSON 为机器可读事实源；CSV 保留 status、分母、reason 和 evidence 引用；Markdown 写清范围与局限。
雷达图统一 0–100 刻度、同一六维顺序与颜色，标注样本数、覆盖率及 synthetic/真实属性。
缺失维度显示缺失且不连成完整面积，不把 unknown/unsupported 当作零分。
CSV 导出应防止以 `= + - @` 开头的外部文本被表格软件当公式执行。
图形生成使用无界面的 Agg 后端，兼容服务器与 openKylin，中文字体缺失时提供明确回退。

## 12. 安全、隐私与数据隔离

默认仅访问合成数据和项目测试目录，不读个人聊天、邮件、密钥、真实用户记忆或宿主机文件。
Dataset 的命令和路径是待评测数据，不是执行器指令；工具执行默认关闭。
未来 action 测试使用临时 sandbox、路径白名单与最小权限；禁止任意 shell、删除真实目录和高权限运行。
路径解析须检查越界与符号链接；清理仅作用于本次创建且有标识的测试空间。
每个 Agent/case/repetition 隔离；用户边界测试使用显式模拟身份，不能共享真实用户 namespace。
Adapter 不得接触 expected；不同 Agent 不共享写入过的测试记忆；启动/清理失败使相应用例停止。
跨 session 应保留同一 case 的记忆；跨 case 必须清理或更换 namespace，避免误清和污染。
边界测试也须防止测试日志成为下一次 Agent 可检索的记忆来源。
凭据仅从用户批准的环境/密钥来源读取，不写数据集、配置明文、日志、报告或版本库。
请求头、token、用户标识等敏感字段先脱敏再落盘；出站请求不得包含无关工作区文件。
默认不推送远端、不购买 API、不创建付费资源、不安装系统级服务、不进行危险修改。

## 13. openKylin 验证

实现目标为 openKylin Linux；本机测试通过不能代替目标系统验证。
使用跨平台路径与 Python API，避免 macOS 特有命令、GUI、绝对用户路径和隐式 shell 工具依赖。
Phase 8 记录实际系统版本、架构、Python/依赖版本、安装步骤、测试与 CLI 产物。
Phase 8 完成要求包括干净环境安装、pytest、离线完整运行、完整报告输出，以及至少两个真实 Agent 在该 openKylin 环境中的实测证据。
离线检查通过但真实 Agent 接入受阻只能写“部分验证”；外部服务不可用应单独记录，不能把 Phase 8 或未验证功能标为通过。
openKylin 发行版、x86_64/ARM 要求、联网条件和打包格式均待确认。
未实际执行的目标环境写“待验证”，不使用“已兼容”或“认证通过”。

## 14. 验收标准

| 里程碑 | 必须提供的可检查证据 |
| --- | --- |
| 首轮文档 | 本说明书、九阶段计划、AGENTS、STATUS/TODO；已有内容未被无记录覆盖 |
| Phase 1 | 包与 CLI 可运行、配置/数据验证有效、必要单测通过、README 可复现步骤 |
| Phase 2 | 1 条 retention 实际执行；短期上下文清空且持久状态保留的测试；结果标 synthetic；含响应和规则依据 |
| Phase 3 | 六类各 2 条经复审 seed；全部可解析；已执行范围和未支持协议透明 |
| Phase 4 | 评分正反例、缺失/失败分母与 unknown 处理通过测试；可选 Judge 关闭时仍可运行 |
| Phase 5 | 至少两个合格真实 Agent 的原始执行记录、身份版本、隔离证明与能力限制 |
| Phase 6 | JSON/CSV/Markdown/雷达图均来自同一实测数据；计数与分母一致 |
| Phase 7 | 六类各 8 条共 48 条，唯一 ID、质量复审、版本/哈希、seed 没有重复计数 |
| Phase 8 | 真实 openKylin 环境信息、安装/测试日志、两个真实 Agent 的实测与完整报告、问题清单；仅离线通过为部分验证 |
| Phase 9 | 经核验规则对照表、项目说明、架构、演示与真实结果；所有未完成项如实列出 |

每阶段运行与该变更有关的测试，记录实际命令、时间、环境、数量、结果和局限。
不能通过降低断言、替换真实数据或吞掉异常实现“全部通过”。
STATUS 写已完成和证据；TODO 写下一步、阻塞与验收，不以计划内容替代完成状态。

## 15. 来源与官方待核实清单

- 主要来源：用户在 2026-10-13 的当前指令，作为本轮开发范围的直接依据。
- 背景来源：原对话《比赛优先级分析》，仅是讨论与需求背景，不是比赛官方材料。
- 开发建议：本文 schema、Adapter 契约、状态分母、隔离方式和工程实现细节。
- 官方待核实：比赛名称/赛道、赛题全文、主办方、截止时间与时区、报名资格、评分细则。
- 官方待核实：是否指定 Agent/数据集/模型、最低样本量、许可与开源要求、外部 API/费用限制。
- 已核验交付要点：见第 1 节和 [CLI/GUI 交接](docs/CLI_GUI_HANDOFF.md)；官方说明明确桌面环境、两款智能体、多维雷达图与 3–5 分钟录屏。
- 官方待核实：指定 openKylin 版本与架构、离线条件、完整交付格式、复现与查重规定；最新截止时间以赛事方更新为准。
- 核实后建立来源链接、发布日期/访问日期与逐项映射；冲突时先记录差异，再调整计划。

以上待核实事项不阻止离线骨架、数据契约和可复现管线的开发，但限制最终参赛符合性声明。
