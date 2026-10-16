# CLI 与图形界面协作约定

> 2026-10-16 实现状态（Claude）：GUI 已按本文实现为 PySide6 桌面程序 `src/memoryscope_gui/`（入口 `memoryscope-gui [项目或运行目录]`，.deb 中为 `memoryscope-ok gui` 与开始菜单项；依赖在可选 extra `gui`，CLI 不依赖 Qt）。
> - `model.py`：不依赖 Qt 的数据层，读取/校验 results（主版本 1，损坏、NaN、未知主版本拒绝）、metadata、events 增量读取（保留半行、坏行标记）、`configs/gui/<uuid>.yaml` 独占生成和 `runs/gui/<uuid>/` 独占输出父目录、CLI 1.0 行解析。
> - 结果页：运行列表（含 GUI 请求与重评修订）、雷达图（缺维留缺口）、六维/覆盖率/状态分布表、synthetic 与未完成横幅、逐条用例筛选、检查的评分理由/必含/禁止项/回答或被检查内容、按 evidence 区间查看 events、经 CLI 调用 `report --json --reuse` 与 `rescore --json`。
> - 新建评测页：数据集、Adapter（来自注册表）、模型、超时、种子；预检 `check-config --json`；`run --jsonl` 的 QProcess 异步执行与 case 完成比例；真实 Agent 需确认；停止/关窗提示不完整；进程退出且 results/metadata 齐全后才生成报告并跳转。只显示是否检测到 DEEPSEEK_API_KEY，不读取或显示其值。
> - 新建评测页同时列出 `configs/custom-agents.yaml` 中声明的 `type: command` 命令行 Agent（经核心 AgentConfig 校验，无效时提示）；请求配置原样写入这些条目。
> - 测试 `tests/test_gui.py` 覆盖第 6 节验收清单（有效 run、缺维、synthetic、fail 但 completed、Agent error、损坏/不支持 schema、半行事件、无结果中断、已有 report）及 offscreen 窗口端到端 synthetic 运行。另有 `memoryscope view` 离线 HTML 页用于无 Qt 环境。

更新时间：2026-10-15。本文是用户确认的分工及接口约定，供 Codex 与 Claude 接续开发。除“现有接口”外，待实现项均不表示已完成。实现现状以源码与 STATUS.md 为准。

## 1. 分工与边界

| 负责人 | 负责交付 | 主要文件 |
| --- | --- | --- |
| Codex | CLI、配置与结果契约、Runner、Adapter、证据、评分、报告；openKylin 环境与 CLI 验证 | `src/memoryscope/`、`tests/`、`scripts/`、本文 |
| Claude | 图形界面、运行配置表单、进程控制、进度、结果/雷达图/证据查看；openKylin 桌面验收 | 建议 `src/memoryscope_gui/`、GUI 专属测试和使用文档 |
| 双方联调 | 同一配置在 CLI/GUI 下执行，核对产物来源、数值、状态与错误展示 | 记录在 `STATUS.md` / `TODO.md` |

CLI 与 GUI 共用唯一的执行、评分与报告核心。GUI 不实现第二套 evaluator，不调整结果得分，不将 Demo 当作真实 Agent。Claude 修改核心协议前先在本文列出变更；Codex 同步调用方和验证记录，不能静默改字段。

默认技术方向：Python + PySide6 桌面程序，通过异步子进程调用 CLI；GUI 依赖放在可选 extra，CLI 安装与无显示环境运行不得依赖 Qt。此为待实现的工程选择，当前没有 GUI 入口。无需新增 Web 服务或数据库。若改用其他 GUI 技术，保留本文的进程与文件契约。

## 2. 官方演示要求

核验于 2026-10-15：[openKylin 官方赛题说明](https://www.openkylin.top/news/4094-cn.html)，交付要求段：代码在 openKylin 上编译运行，提供一键 CLI，建议提供 .deb；在 openKylin 桌面环境演示至少两款智能体评测及多维对比雷达图，提供 3–5 分钟完整录屏。

CLI + GUI 是用户追加的产品范围；官网要求桌面环境演示，不等于官网要求参赛作品必须有 GUI。最终演示必须使用 openKylin 内的实际运行与产物。macOS 的旧结果可用于界面开发，但需标清其运行环境，不能当作 openKylin 验收。

## 3. 现有 CLI 接口（MVP 0.3.0）

CLI 实现已完成。macOS Python 3.13 与 openKylin 3.0 ARM64 Python 3.12.2 均通过 85 项测试；openKylin 安装与 synthetic 报告验证见 [记录](openkylin-validation.md)。Claude 可从本节命令和结果 schema 开始，GUI 尚未实现，Linux 两款真实 Agent 验收仍待进行。

以项目根目录为工作目录，使用同一虚拟环境的 `.venv/bin/python -m memoryscope` 调用。GUI 使用参数数组、`shell=False`（或 QProcess 参数列表），不拼 shell 字符串，不阻塞 UI 线程。

| 参数 | 功能 | 当前输出/约束 |
| --- | --- | --- |
| `--version` | 包版本 | 文本 |
| `list-agents [--json]` | Adapter 列表 | 从注册表读取类型、synthetic、能力；不创建 Agent |
| `validate DATASET [--json]` | 校验数据 | JSON 包含数量、类别与来源摘要；成功 0，拒绝 2 |
| `check-config CONFIG [--json]` | 配置和数据预检 | 解析相对路径、校验 schema 与路径边界；不读取密钥、调用 Agent 或创建输出 |
| `run CONFIG [--json 或 --jsonl]` | 创建新 run、执行评测 | completed 为 0，执行 failed 为 1，输入/文件处理错误为 2，中断为 130；产物目录显式返回 |
| `report RUN_DIR [--json] [--reuse]` | 从结果生成报告 | 完整生成后发布；默认保留已有报告，--reuse 仅读取完整且来源匹配的报告 |
| `rescore RUN_DIR [--json]` | 离线重评 | 新目录内带证据、配置/数据快照、metadata 与新的 results；可单独报告或再次重评 |

以上退出码指已处理的正常路径；未捕获异常、启动失败、信号退出也必须在 GUI 显示为异常。`completed` 表示执行完成，不代表所有 case 都 pass。当前没有 `--run-id`、HTTP API、恢复执行或正式取消协议，不能在界面假装这些能力已存在。

所有 `--json` 命令输出一条 JSON：`schema_version: "1.0"`、`command`、`ok`、`data`、`error`。成功 error=null；失败 error 为 `{type, message}`，执行失败可能同时有 data 与已保存产物。CLI 参数拼写/未知选项等 Typer 解析错误仍通过 stderr 与退出码 2 报告，不能假定任意失败的 stdout 都是 JSON。原有不带参数的文本接口保留，report 默认仍输出旧摘要 JSON。

`run --jsonl` 的每行有 `schema_version: "1.0"` 和 `type`。`type=progress` 的 data 包含 event、sequence、timestamp、run_id、run_dir、agent_id、case_id、completed_cases，以及适用的 planned_cases/status/synthetic；仅含生命周期标量，不携带消息、记忆、参考答案或原始响应。`run_started` 提供实际目录与总计划 case 数（Agent × case）；`case_finished` 对 pass/fail/unknown/error/unsupported 各状态均计数。`type=result` 是最终命令结果，其 data 提供 run_dir、results_path、events_path、metadata_path 和摘要。run_finished 进度事件早于 metadata 写入，必须等最终 result 和进程退出再标记产物齐全。--json 与 --jsonl 互斥。

核心不依赖 CLI/Qt。进度通过可选回调传出，显示端异常会记录 progress_observer_error 并停止通知，不改变 Agent 评分；它不代表取消评测。扩展 Adapter 需要实现 AgentAdapter、加入 ADAPTERS 并显式扩展配置类型；扩展 evaluator 保持统一结果状态与证据引用。当前不引入动态插件加载服务。

## 4. GUI 启动一次评测

1. 让用户选数据集、Agent 和配置，显示真实调用会使用的模型、超时及是否 synthetic。首次可先支持已有配置；不要为 UI 需要改变 benchmark 用例。
2. 在项目 `configs/gui/` 下用独占创建生成 `<request_id>.yaml`，UUID 作为 request_id。配置 schema 为 `1.0`，使用已支持的 `dataset`、`output_dir`、`agents`、`seed`。相对路径基于配置文件目录；所有输入输出须处于项目根目录内，输出不能与数据集目录重叠。
3. 为该请求指定独占输出父目录 `runs/gui/<request_id>/`。CLI 会在其中新建自己的 `<run_id>/` 子目录。GUI 只观察这一请求的父目录，不能从全局 runs 中猜“最新一次”运行，也不能改名 CLI 生成的 run_id。
4. 启动 `python -m memoryscope run <config绝对路径>`，cwd 为项目根目录；环境继承用户已有设置。API key 由环境或项目本地 `.env` 供核心读取；首版 GUI 不编辑/显示密钥，不把密钥写入 YAML、命令行、截图或日志。
5. 优先用 `run --jsonl` 的 run_started 得到实际目录，显示当前阶段；completed_cases / planned_cases 是 case 完成比例，不是时间估计。也可等独占父目录下唯一 run 子目录出现后增量读取 events.jsonl。没有目录时显示“准备/校验中”；不能伪造评测百分比。
6. 进程结束后检查退出状态和 `results.json` / `metadata.json`。`results.json` 可能早于 metadata 和进程退出出现，不能据此提前标记全部完成。异常退出且无结果时保留已有证据，显示“中断/未完成”，允许用户发起全新运行。
7. 对完成产物另行调用 `report <run_dir> --json --reuse`，成功后显示图和报告。已有报告只有四类文件完整且来源摘要匹配时才复用；过旧、损坏或来源变化会明确拒绝，不能删除用户原报告。报告失败仍可查看原始结果和证据。

配置示例（仅示例，request_id 由 GUI 生成；从 `configs/gui/` 解析）：

```yaml
schema_version: "1.0"
dataset: ../../datasets/golden
output_dir: ../../runs/gui/EXAMPLE_REQUEST_ID
agents:
  - id: codex
    type: codex
    model: deepseek-flash
    timeout_seconds: 300
  - id: dsh
    type: dsh
    model: deepseek-flash
    timeout_seconds: 300
seed: 0
```

此示例配置会调用真实 Agent；界面不得在打开页面或读取历史报告时自动执行它。首版暂不提供“取消后继续”；窗口关闭时若仍有运行，明确提示用户进程状态，不把关闭窗口显示为完成。

## 5. 文件与结果契约

| 文件 | 当前 schema | 使用方式 |
| --- | --- | --- |
| `config.snapshot.yaml` | 配置 `1.0` | 运行采用的配置快照 |
| `dataset.snapshot.jsonl` | 逐例 schema | 复现与审阅，不传给被测 Agent |
| `events.jsonl` | `1.0` | 运行时追加且 flush；增量读取完整行，保留半行等待下次读取 |
| `results.json` | `1.1` | 最终逐 Agent、case、检查与评分事实源 |
| `metadata.json` | `1.1` | OS、Python、依赖、代码/数据摘要、评分器与时间 |
| `report/report.json` | `1.0`（0.3.0 起） | 派生摘要；source_results_sha256 是完整结果按 UTF-8、sort_keys=True、ensure_ascii=False 的标准 json.dumps 序列化得到的摘要；完整结果仍读 results.json |
| `report/report.csv`、`report.md`、`radar.png` | 派生报告 | 同一次运行的导出与展示 |

事件公共字段：`schema_version, sequence, timestamp, run_id, agent_id, case_id, session_id, event, payload`。sequence 是 run 内递增序号。当前可显示 `run_started`、`agent_started`、`case_reset`、`message_started`、`session_reset`、`probe_started`、`evaluation`、`case_error`、`case_unsupported`、`agent_error`、`case_finished`、`run_finished` 等事件；未知事件可保留原文而忽略其 UI 映射。旧 run 可能没有 case_finished；不要把 evaluation 数量当作完成 case 数量，一个 case 可有多次检查。

重评保留原执行 run_id，不伪造新的 Agent 执行；修订目录以 rescore-时间-随机值命名，results 中有 rescored_from / evaluator_version / status_changes，metadata.rescore 保存来源文件摘要和原评分器信息。证据与快照是原样副本，新评分理由在修订 results 中；引用的 evidence 仍指向原始执行。重评不改原 run。旧版本只有 results 的重评目录仍可查看/报告，但没有证据就不能再次重评。

`results.json` 顶层有 `run_id, status, synthetic, purpose, dataset_case_count, agent_results`。每个 Agent 有 `agent_id, adapter_type, describe, synthetic, status, dimensions, dimension_scores, overall_score, cases, errors`。

六维顺序固定为 `retention, retrieval, dynamic_update, disambiguation, boundary, reuse`。每维包含 `planned, pass, fail, unknown, error, unsupported, scorable, score, scorable_coverage`。维度分与覆盖率为 0–100；逐 case score 为 0/1/null。GUI 直接展示核心提供的聚合值；null 显示“未测/不可评分”，雷达图保留缺口，六维不全时 overall_score 为 null。

逐例详情读取 `cases[].probes[]` 的 `evaluation.explanation`、`response`、`evaluation_event`，以及 `cases[].evidence` 的序号区间。用 evaluation_event 对应 events.sequence，便于查证。错误/缺能力路径可能没有完整 probes 或 evidence，字段缺失须容错。逐 Agent 的 synthetic 标识优先；混合运行顶层 synthetic 不能代替逐 Agent 判断。

未知主版本拒绝解释；遇到当前不认识的状态显示“未知状态”及原始值，不推定 pass。Agent 文本、路径和日志一律当作数据；HTML 展示要转义，不执行其中脚本/命令，报告内路径只能访问选定 run 目录内的文件。

## 6. Claude 可立即开展的工作

先实现读取历史 run 的结果页：环境/版本信息、Agent 对比、六维与覆盖率表、已有 radar.png、失败检查及证据定位。可用 `docs/results/` 理解展示，但该目录只有报告副本；完整 run 从用户选择的 `runs/<run_id>/` 读取。

随后增加配置与异步运行页，按第 4 节接 CLI。页面载入和历史查看不调用 API。先联调 synthetic，再在用户确认环境和凭据后执行真实 Agent；真实运行成本与调用沿用现有授权范围，不自行购买资源。

验收需覆盖：有效 run、缺失维度、synthetic、case fail 但 run completed、Agent 错误、损坏/不支持 schema、半行事件、无结果的中断、已有 report。最后在 openKylin 桌面里实际启动 GUI，执行 CLI 与 GUI 的同配置流程，核对相同聚合语义和可追踪证据。每次 run 结果可能受模型随机性影响，不要求两次真实调用逐字相同。

当前交接不表示已将任务发送给 Claude，也不表示 GUI 已实现。Claude 接手先读本文、AGENTS.md、STATUS.md、TODO.md，再检查代码，避免覆盖其他人的改动。
