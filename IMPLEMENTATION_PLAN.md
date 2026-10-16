# MemoryScope-OK 执行计划

> 最新评价与剩余规划见 [docs/architecture-review-20261016.md](docs/architecture-review-20261016.md)。
>
> 架构评审补充（2026-10-13）：见 [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)。其中保存了提前接入真实 Agent、对照实验、步骤化用例、行为评分与离线重评、能力与观测范围、openKylin 初验六点建议，以及建议执行顺序。原 Phase 编号和验收标准保留；建议的落实情况由 STATUS/TODO 记录。

本文件是开发顺序与验收清单；需求定义以 `PROJECT_SPEC.md` 为准，实际完成情况与验证证据写入 `STATUS.md`，未完成工作写入 `TODO.md`。计划中的命令、文件及通过标准不表示已经实现或通过。

## 1. 执行约定与范围

- 优先形成可运行闭环：本轮先完成 Phase 1 骨架，再实现 Phase 2 的一条 retention 离线 Demo。后续阶段按依赖推进，真实完成情况单独记录。
- Phase 2 的 Demo 只证明框架连通；确定性本地 Adapter 不计入“至少两个真实 Agent”的验收，报告必须标识其类型。
- Phase 3 先形成六类、每类两条、共 12 条 seed；48 条是 Phase 7 的扩展目标，不是第一轮运行门槛。
- 文件位于 `datasets/golden/` 不意味着已经完成 golden 审核；初始样例是 golden 候选，审核状态必须可追踪。
- 框架优先采用 Python 3.10+、Typer、Pydantic、PyYAML、httpx、matplotlib、pytest；新增依赖必须解决具体问题。
- 2026-10-15 核验了官网交付段的 CLI、openKylin 桌面、两款智能体、雷达图及 3–5 分钟录屏要求；完整规则和最新提交安排仍需核实，来源见 `PROJECT_SPEC.md`。
- 用户追加 CLI + GUI 交付：Codex 负责核心/CLI，Claude 负责桌面 GUI，共用执行、评分和报告；按 [接口交接](docs/CLI_GUI_HANDOFF.md) 联调。GUI 作为可选依赖，通过进程和版本化产物接入，不增加 Web 服务或数据库。
- 默认采用简单、可逆、跨 Linux 的实现；非关键细节自行选择合理默认值，并把有影响的选择记入状态文档。
- 开始修改前检查目录、现有文件、Git 状态与 `AGENTS.md`。保留既有内容，避免覆盖用户工作；当前任务不推送远端、不购买 API、不执行危险修改。
- 新付费、凭据、外部账户或设备依赖缺失时，将受阻项记入 `TODO.md`，继续不依赖它的工作；不得用 Mock、缓存答案或编造结果替代真实验证。

## 2. 工作目录与运行约定

```text
PROJECT_SPEC.md                 需求、设计与验收标准
IMPLEMENTATION_PLAN.md          本执行计划
AGENTS.md                       后续开发规范
STATUS.md / TODO.md             已执行证据 / 待办与依赖
pyproject.toml                  安装、CLI 与测试配置
src/memoryscope/                模型、数据、Adapter、执行、评分、报告
configs/demo.yaml               一条 retention 的离线配置
datasets/golden/retention.jsonl 初始用例；其余维度分文件扩展
tests/                         有意义的单元与集成测试
runs/<run_id>/                 每次运行的隔离输出
docs/                          协议、真实 Agent、openKylin 与参赛材料
```

以上是目标布局，允许保持同等职责的简洁实现。数据协议版本为 `1.0`。配置里的相对路径按配置文件所在目录解析，不能依赖启动时的当前目录；例如 `configs/demo.yaml` 应通过 `../datasets/golden/retention.jsonl` 定位单例数据集，也支持目录。数据与输出路径解析后必须位于项目根目录内，符号链接同样不能绕过该边界。

每个 run 最少包含 `metadata.json`、`results.json` 和 `events.jsonl` evidence 记录；保存 `config.snapshot.yaml`、`dataset.snapshot.jsonl` 与摘要。根目录的 `results.json` 保留为机器可读事实源；Phase 6 在 run 的 `report/` 子目录输出 `report.json`、`report.csv`、`report.md` 与 `radar.png`。记录代码/运行环境信息、随机种子、Adapter 身份、session 切换及上下文截断策略。真实 Agent 运行另记录可获取的模型版本、参数及请求重试信息，不保存密钥。

建议在项目根目录的隔离环境内执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
memoryscope --help
memoryscope validate datasets/golden
memoryscope run configs/demo.yaml
pytest -q
```

如果环境已有可用的 Python 3.10+ 或依赖管理工具，可等价替换，记录实际命令与版本。后续出现的新配置、新测试目录与命令属于阶段交付项，应先实现再运行；不得将规划命令写成已通过证据。

## 3. Phase 1：项目初始化

**目标：** 建立能安装、能启动、能验证最小输入的 Python 包，并保存完整项目文档。

**任务与文件：**

1. 检查本地项目内容与已有规范；创建或谨慎合并本说明书、项目规格、`AGENTS.md`、`STATUS.md`、`TODO.md`。
2. 创建 `pyproject.toml`、`src/memoryscope/`、`tests/`、`configs/`、`datasets/golden/` 与简洁 README；采用 src 布局和 `memoryscope` CLI 入口。
3. 实现版本 `1.0` 的 Pydantic 数据模型与 YAML 配置加载；至少明确 case ID、维度、输入步骤、session、预期行为及评估定义。
4. 实现 JSONL 加载与 `memoryscope validate datasets/golden`，对空数据集、重复 ID、非法维度、未知字段和损坏 JSON 给出可定位错误。
5. 定义统一 Adapter 接口和执行结果结构，提供 `memoryscope list-agents`；此阶段只做接口与配置选择，不假设所有 Agent 都支持记忆导出或删除。
6. 补充 `.gitignore`，排除密钥、本地环境、实际运行输出；提供安全的配置示例。

**检查：** 安装包，执行 `memoryscope --help`、`memoryscope validate datasets/golden`、`pytest -q`。初始有效用例存在后才进行成功验证；损坏输入也应有针对性测试。

**通过标准：** CLI 可从安装入口调用；合法输入通过，非法输入以非零退出码失败且指出文件/行或字段；无需 API key；测试通过；所有文档可供后续 Codex 继续执行。

**依赖与失败处理：** Python 版本或依赖安装失败时记录实际错误，优先使用已存在且兼容的环境；不要修改系统 Python，不将跳过测试写为通过。

## 4. Phase 2：一条用例的端到端闭环

**目标：** 用一条 retention 候选用例验证“加载 → Adapter → evidence → 确定性评分 → 落盘”。

**任务与文件：**

1. 在 `datasets/golden/retention.jsonl` 放入一条人工可理解、无敏感数据的候选用例；包含记忆写入、无关干扰、新 session 与延迟探测。
2. 实现明确标为 `demo` 的确定性本地 Adapter、统一 Runner 和 `configs/demo.yaml`。Adapter 可持久保存输入中的偏好，但不能接收 expected、评分规则或 case 答案。
3. 新 session 清空短期消息上下文、保留同一用例内的长期记忆；不同用例、Agent 和 run 使用独立命名空间。探测阶段不重放原始写入对话。
4. evidence 记录实际发送给 Adapter 的可见输入、session 事件、输出、状态、时间与可观测行为；敏感字段先脱敏。
5. 实现最小确定性评分器，输出分数、命中/未命中原因和 evidence 引用。只有 retention 有覆盖，其他五维必须是 `null`，不得生成完整六维总分。
6. 写入 `runs/<run_id>/metadata.json`、`results.json` 和 evidence；错误运行同样保存诊断且 CLI 返回非零退出码。

**检查：** 执行 `memoryscope run configs/demo.yaml` 和 `pytest -q`；检查落盘文件，验证探测输入里没有原始偏好。测试必须证明清空短期上下文后仍走指定记忆路径，以及换用例/换 run 时不会复用旧记忆。

**通过标准：** 从干净环境运行一次得到可解释的真实程序输出；可以依据记录重建步骤；Demo 标识清楚；故意取消记忆或改错输出时不能仍获满分；不存在预期答案泄漏与虚构分数。

**依赖与失败处理：** 本阶段完全离线，不等待真实 Agent 账户。若某种 session/截断方式尚未实现，应缩小已声明能力并记录限制，不将普通上下文回答宣称为长期记忆能力。

## 5. Phase 3：六类 seed，各两条

**目标：** 形成 retention、retrieval、dynamic update、disambiguation、boundary、reuse 共 12 条高质量 seed，并让同一协议容纳不同任务。

**任务与文件：**

1. 在 `datasets/golden/` 下按六个维度组织 JSONL，保留稳定 case ID、主要维度、任务描述、观察要求与审核状态。
2. retention 覆盖干扰与跨 session；retrieval 测试相关记忆的主动调用；dynamic update 同时检查新信息生效与旧信息失效。
3. disambiguation 使用相似但不同归属的信息；boundary 主类型为 `stable_preference`、`temporary_context`、`sensitive_information`、`obsolete_information`，区分应长期保留、仅当前情境有效、不应保存或使用、已经失效的信息。跨用户隔离与删除作为扩展测试；reuse 检查经验在新情境中的迁移，避免只复述原文。
4. 每条用例写明正例、容易误判的反例、可观察证据与规则可判部分；数据集中不使用真实个人资料、真实账户或可执行危险操作。
5. 建立跨 session 与上下文截断检查，至少覆盖短期上下文不会被偷偷回填、保留的长期状态是否符合声明、不同测试主体不串数据。
6. 形成 `docs/dataset-review.md`；先评审设计，再运行。Demo 无法完成的任务允许真实失败或能力缺失状态，不为取得漂亮分数硬编码答案。

**检查：** `memoryscope validate datasets/golden`、`pytest -q`；实现 `configs/seed.yaml` 后执行 `memoryscope run configs/seed.yaml`，核对六类各两条以及状态分布。

**通过标准：** 12 条数据均满足协议并可被执行；每维有两条独立设计的用例；未观测到的能力不被推定为成功；新增用例不迫使 Adapter 知道答案。

**依赖与失败处理：** 依赖 Phase 2。难以评分的用例进入人工审核清单；不能以格式合法替代质量验收，不能将未审核 seed 宣称为完成审核的 golden。

## 6. Phase 4：完整评分系统

**目标：** 建立可解释、可复查的确定性评分与聚合规则，并将 LLM Judge 作为显式可选项。

**任务与文件：**

1. 在 `src/memoryscope/` 的评分模块实现规则注册与结构化评估结果；明确支持 Exact、Contains、NotContains、Regex、JSON 字段、Numeric、File、Tool、Action 检查，并提供 semantic evaluator 插件接口。规则优先检查实际行为、字段、路径及状态；文本匹配必须考虑否定、引用和旧值，不能以口头承诺替代 File/Tool/Action 证据。
2. 按规格书定义各维指标、失败/不支持/不可观察/跳过/执行错误状态、分母与覆盖率；不能将执行错误静默丢出报告。
3. dynamic update 同时报告新值命中与 stale memory；disambiguation 报告混淆；boundary 区分“本次未输出”与“已证明删除”。缺乏内部观察证据时不能宣称永久遗忘。
4. 缺失维度为 `null`；六维未齐时不计算完整总分。任何部分汇总明确标注覆盖范围、权重和纳入样本，不能冒充完整比较。
5. 增加评分版本、判定理由、evidence 引用和复评分入口；复评分读取已落盘输出，不再次调用被测 Agent。
6. 将 LLM Judge 设计为独立、默认关闭、显式启用的扩展；固定 rubric、模型配置和输入边界，记录成本与不确定性，校准后再用于无法规则判定的用例。
7. 将被测输出与数据中的指令视为待评估数据，不能授予它们控制 Judge、执行工具或改变判分规则的权限。

**检查：** `pytest -q`；新增具有相反结论的正反例测试、否定和引用误判测试、状态分母测试、缺维总分测试；用保存的 evidence 验证重复复评分一致性。

**通过标准：** 规则结果可追踪到证据；已知反例不会被关键词命中误判；默认运行不发出 Judge 网络请求；LLM 与规则结果分开记录，不能覆盖原始输出。

**依赖与失败处理：** 依赖 Phase 3 的多维样例。新凭据或付费未获授权时，只阻塞在线 Judge 验证，保留离线规则评分可用，不申请购买或伪造 Judge 输出。

## 7. Phase 5：至少两个真实 Agent

**目标：** 在同一数据与协议下，对至少两套真实、有可说明记忆机制的 Agent 系统取得可核验结果。

**任务与文件：**

1. 先调查用户可用的系统、运行方式、接口与许可证，写入 `docs/real-agents.md`；标明系统身份、版本、记忆机制、重置能力和观测限制。
2. 实现至少两个真实 Adapter 及各自配置示例。不同名字指向同一裸模型、同一无记忆端点或同一 Demo，不满足两套真实 Agent 的要求。
3. 核对各 Agent 的 session 创建、短期上下文清空、持久状态保留与用例结束清理；记录无法等价执行的协议差异，避免虚假的公平比较。
4. 增加受限超时、失败记录、重试上限及调用预算；重试不能默默重复有副作用的写入，不能以失败前记忆状态继续冒充干净重跑。
5. 对两套 Agent 运行相同数据版本，保存请求/响应证据、配置摘要、评分解释与故障；汇总时显示支持情况、覆盖率、成本和可比性限制。
6. 凭据仅从环境或明确授权的本地机制读取，示例配置只放变量名；测试用临时命名空间，不向用户生产记忆写入合成测试数据。

**检查：** `pytest -q`；真实集成测试明确标记并默认不调用网络；准备实际配置后分别运行 `memoryscope run configs/real-agent-a.yaml` 与 `memoryscope run configs/real-agent-b.yaml`，人工抽查证据。

**通过标准：** 两套真实系统身份可查、调用真实、跨 session 行为可解释；报告没有把 Mock/Demo 或无记忆基线算作真实 Agent 验收；缺失能力如实显示。

**依赖与失败处理：** 依赖完整协议和确定性评分。服务、凭据、预算或授权缺失时精确记录受阻项，继续 Phase 6/7 的离线工作；不得为消除阻塞自行购买 API 或创建付费资源。

## 8. Phase 6：报告与雷达图

**目标：** 从同一次运行的真实记录生成一致的 JSON、CSV、Markdown 与比较图表。

**任务与文件：**

1. 实现报告模块和 `memoryscope report RUN_DIR`，从根 `results.json` 和 metadata 读取数据，在 run 的 `report/` 下输出 `report.json`、`report.csv`、`report.md`、`radar.png`；报告生成不重复调用 Agent，不替换原始事实源。
2. 包含运行环境、数据版本、Agent 类型、指标定义、六维值、有效样本数、覆盖率、错误与限制；保留逐 case 结果和证据定位方式。
3. 所有格式使用同一个聚合结果；逐例分数为 0/1，维度分数统一为 0–100，并注明单位。缺失值保留为空/null，图中以缺失标记或断线表达，不补为零、不插值得分。
4. 完整六维对比雷达图只对具备所需有效数据的结果生成；不完整运行仍输出报告，并清晰解释为什么没有完整总分或闭合雷达图。
5. matplotlib 使用无显示环境可用的后端，处理中文字体缺失；机器可读报告不依赖特定桌面或字体。

**检查：** `pytest -q`；运行 Demo/seed 配置，人工打开 Markdown 和图像，核对 JSON/CSV/Markdown 数值相同，以及缺维场景的显示。

**通过标准：** 报告可以脱离开发环境阅读；图表来源明确；Demo 与真实 Agent 一眼可区分；不出现人为补齐、假六维总分或丢失错误样本。

**依赖与失败处理：** 依赖 Phase 4，可与 Phase 5 的外部接入并行。绘图/字体错误必须记录并保留其他报告，不能因图表失败丢失原始证据。

## 9. Phase 7：扩展到 48 条 golden cases

**目标：** 六维各 8 条，共 48 条完成审核的 golden；提高任务覆盖，而非复制改写样例凑数。

**任务与文件：**

1. 从 12 条 seed 扩展，每维覆盖不同干扰类型、session 距离、更新冲突、归属关系、边界和迁移情境；在数据说明中展示覆盖矩阵。
2. 为每条 case 核对事实、步骤、预期行为、负例、自动评分可靠性、证据可获得性和独立性；审核记录可追踪到 case ID。
3. 对路径、工具名和项目情境做 openKylin 适用性检查；平台特定要求用显式前置条件表示。
4. 保持开发集与用于最终比较的数据版本清楚分离，冻结发布版本和摘要；禁止把期望答案提供给被测系统或按结果挑选样本。
5. 执行全数据协议验证、离线回归及可用真实 Agent 回归；抽查评分分歧并修正数据或规则版本。

**检查：** `memoryscope validate datasets/golden`、`pytest -q`；准备全量配置后运行 `memoryscope run configs/golden.yaml`，核对总数 48、每维 8、ID 唯一及审核记录齐全。

**通过标准：** 数量、覆盖和人工审核同时达标；已知歧义被解决或明确排除；数据变更可追踪，旧结果不会静默套用新评分定义。

**依赖与失败处理：** 依赖 Phase 3/4；48 条不是首轮门槛。质量审核未完成时如实报告候选数与审核数，不将未审数据标为最终 golden。

## 10. Phase 8：openKylin 环境验证

**目标：** 在真实 openKylin 环境上验证安装、CLI、文件系统、运行与报告的可用性。

**任务与文件：**

1. 获取可用测试机或明确记录来源的虚拟机；记录发行版版本、架构、Python、依赖与运行方式，不预先声称某版本已兼容。
2. 在新建隔离环境里按 README 安装并执行离线 Demo、数据验证和测试；检查无桌面运行、中文路径、相对路径、输出权限与图像生成。
3. 在目标 openKylin 环境运行完整数据集及至少两个真实 Agent，生成完整 JSON/CSV/Markdown/雷达图并抽查；区分框架兼容性、外部服务连接限制、系统工具支持情况。
4. 将完整命令、退出码、环境信息、问题与修复记录写入 `docs/openkylin-validation.md`；修复必须回归已有测试。

**检查：** 在 openKylin 执行安装、`memoryscope --help`、`memoryscope validate datasets/golden`、`memoryscope run configs/demo.yaml`、`pytest -q`；随后使用至少两个真实 Agent 的完整数据配置运行，并验证 `report/` 下四类实际报告文件。

**通过标准：** 有可追溯的 openKylin 实机/虚拟机执行证据，完整数据集、至少两个真实 Agent 的评测和四类报告均已在目标环境验证。只有离线闭环与测试通过时只能记为“部分验证”；真实集成或报告因外部依赖受阻，Phase 8 仍未通过。不把 macOS、其他 Linux 或“理论兼容”写成 openKylin 验证通过。

**依赖与失败处理：** 依赖可用环境，缺失时标为待验证并继续文档和交付准备。不得自行重装系统、格式化磁盘或修改用户重要系统配置。

## 11. Phase 9：参赛材料与最终核对

**目标：** 形成可审阅、可复跑的项目交付包；最终提交要求以核实后的官方材料为准。

**任务与文件：**

1. 核实官方赛题、授权与开源要求、提交格式及验收规则；记录来源链接、查阅日期和对项目的影响，尚未核实项继续显式标注。
2. 完善 README、架构图、数据协议、Adapter 接入指南、评分说明、复现指南、已知限制和演示脚本；说明项目测试的是记忆能力，不是宣称创造新的记忆 Agent。
3. 整理真实运行证据、两个真实 Agent 的比较报告和 openKylin 验证记录，明确 Demo/正式结果边界；截图与数字来自保存的真实结果。
4. 检查许可证、第三方依赖与数据来源；只打包允许分享的数据和脱敏证据，排除密钥、用户记忆、私人路径和缓存。
5. 从干净环境复跑最小闭环，审查 `STATUS.md` 与 `TODO.md`，形成“已完成 / 受阻 / 未验证”清单。

**检查：** `pytest -q` 与 README 中的实际复现命令；对交付包做文件清单和敏感字段检查，人工核对文档数字与原始结果。

**通过标准：** 用户可以按文档复现已声明的结果；官方要求核实情况清楚，未完成项没有被包装为完成；材料在本地可审阅。远程推送、发布或正式提交需另有用户授权。

## 12. 阶段追踪与交接

以下为计划验收表；实际状态以 `STATUS.md` 的运行证据为准。完成一阶段时更新该表或状态文档，不能仅凭生成了文件勾选完成。

| 阶段 | 最小交付 | 核心验收证据 | 依赖 |
| --- | --- | --- | --- |
| 1 初始化 | 文档、可安装包、CLI、协议验证 | 安装/帮助/验证/测试记录 | 本地 Python 环境 |
| 2 单例闭环 | 1 条 retention、Demo、原始结果 | 跨 session 与隔离测试、实际 run | Phase 1 |
| 3 六类 seed | 12 条候选、六类执行 | 各维 2 条、质量审核与状态记录 | Phase 2 |
| 4 评分 | 规则、聚合、可选 Judge 边界 | 正反例、分母、缺维、复评分测试 | Phase 3 |
| 5 真实 Agent | 至少两套真实接入 | 系统身份、请求证据、统一数据运行 | Phase 4、服务/凭据 |
| 6 报告 | JSON/CSV/Markdown/雷达图 | 格式一致、图像检查、缺值显示 | Phase 4 |
| 7 golden 扩展 | 48 条已审用例 | 每维 8 条、覆盖矩阵、回归证据 | Phase 3/4 |
| 8 openKylin | 完整目标环境验证 | 发行版信息、完整数据、2 个真实 Agent、四类报告 | 可用 openKylin 环境及真实集成 |
| 9 参赛材料 | 文档与本地交付包 | 官方来源核对、干净环境复现 | 已完成阶段与明确限制 |

每次交接在 `STATUS.md` 写明日期、实际修改、实际命令与退出结果、运行目录、验证范围和限制；在 `TODO.md` 写明下一项可执行任务及外部依赖。对受阻工作给出恢复条件，其余工作继续推进。不要把待办、跳过、未运行或计划中的检查写成已通过。
