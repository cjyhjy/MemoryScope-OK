# 项目状态

更新日期：2026-10-13（America/New_York）。项目根目录：`/Users/cjy/Documents/MemoryScope-OK`。

## 当前结论

**本轮文档、Phase 1 初始化和 Phase 2 单例离线闭环已完成并验证。** Phase 3–9 尚未完成；完整比赛 MVP 尚未完成。

已创建 PROJECT_SPEC.md、IMPLEMENTATION_PLAN.md、AGENTS.md、README.md、CONTRIBUTING.md、LICENSE、TODO.md 及本状态文件。规格明确区分用户要求、开发建议和官方待核实信息；后续 Codex 可从根目录继续读取执行。

首次检查项目目录为空。写入时对每个目标文件做存在性检查，以新建方式复制，没有覆盖用户原有内容。未建立/推送远程仓库，未购买 API，未调用真实 AI API，未修改系统 Python 或进行危险操作。

## 已实现

- `src/memoryscope/` 可安装 Python 包与 CLI：help、version、validate、list-agents、run、report。
- 严格 JSONL/Pydantic schema 及 YAML 配置校验；报告损坏输入、重复字段/ID、空数据集、不支持类型。
- 1 条 `retention-001` 候选用例，包含偏好写入、2 条干扰、session 切换与 probe。
- DemoAdapter 统一生命周期；session reset 清短期留长期，case reset 清全部，Agent/run 状态独立。
- Runner 仅向 Adapter 传入公开消息和 probe，expected 留在评分器；当前仅执行 retention。
- `contains` 大小写不敏感的子串规则，include 全命中且 exclude 均未命中才通过；输出理由和证据范围。
- 唯一 run 目录、17 条实际执行事件、输入快照、文件 SHA-256、软件/依赖/系统/评分器信息。
- 配置路径相对于配置文件，限制在项目内；拒绝符号链接越界及输入/输出目录重叠。
- 启动、执行及关闭错误留证；失败调用前保存请求；错误运行非零退出。
- 所有结果明确 `synthetic: true`。case 分数 0–1，维度分数 0–100；未测维度和整体总分为 null。

## 已执行验证

最终项目目录使用 `.venv`：Python **3.13.15**，macOS arm64；Typer 0.27.3、Pydantic 2.14.1、PyYAML 6.0.3、httpx 0.28.1、matplotlib 3.11.2、pytest 8.4.2。

依赖先下载到任务独立缓存，再通过 `uv pip install --offline --no-build-isolation -e '/Users/cjy/Documents/MemoryScope-OK[dev]'` 安装到项目独立环境。使用该环境实际验证如下：

| 检查 | 实际结果 |
| --- | --- |
| `python -m pytest -q` | **32 passed**，退出 0 |
| `memoryscope --help` / `--version` | 正常，版本 0.1.0，退出 0 |
| `memoryscope list-agents` | 仅 demo，标 synthetic=true，退出 0 |
| `memoryscope validate datasets/golden` | 1 case / 1 file，退出 0 |
| `python -m memoryscope --help` | 模块入口正常，退出 0 |
| `memoryscope run configs/demo.yaml` | 完整落盘，退出 0 |
| `memoryscope report runs/<本次run_id>` | 从已保存 JSON 读取摘要，退出 0 |
| 文件哈希、事件序号、session reset、缺维分数 | 校验通过 |

测试覆盖合法/损坏 schema、重复/空数据、配置未知字段、路径越界与重叠、session/case/Agent/run 隔离、正反评分、标准答案不传入 Adapter、调用失败留证和 CLI 退出码。测试中的异常均为明确注入的测试情境，没有当作真实 Agent 结果。

另对源码进行 Python 3.10 语法解析通过；**尚未运行 Python 3.10 解释器的完整测试**。离开项目工作目录的配置解析由测试覆盖。详细命令及输出见 `docs/validation.json`。

## 首次最终目录运行结果

运行 ID：`20261013T135407045749Z-3eb9536a2c1f`。

```text
runs/20261013T135407045749Z-3eb9536a2c1f/
  metadata.json
  results.json
  events.jsonl
  config.snapshot.yaml
  dataset.snapshot.jsonl
```

- Agent：`demo`；性质：**synthetic 管线测试，不是真实 AI Agent 评测**。
- 实际回答：`你的 Python 项目使用 uv 管理依赖。`
- case score：1.0；Retention：100.0；其余五维：null；Overall：null。
- 切换到 probe session 时：短期消息 0 条、长期记忆 1 项，先前 3 条短期消息已清除。
- include `uv` 命中；exclude `pip`、`poetry` 均未命中。
- 17 条事件及 4 个产物摘要与落盘内容一致。结果由程序实际执行与评分得到，不是手填成绩。

## 已知限制与未验证项目

1. Demo 是固定范围的确定性玩具记忆，只证明管线和隔离行为，真实 Agent 完成数为 **0/2**。
2. 当前只有 **1** 条 retention 候选；12 条 seed、48 条人工审核 golden 均未完成。只有六类 schema 枚举不代表六类行为已支持。
3. 首轮仅 question + contains + cross_session。截断协议、进程重启、真实时间跨度、多用户、文件/工具动作尚未实现。
4. 子串匹配不理解否定和引用；不得用当前规则处理复杂语义并宣称已可靠判定。
5. 当前聚合对任一执行出错的维度返回 null，整体总分始终 null；完整状态分母、覆盖率、六维宏平均将在 Phase 4 实现。
6. `report` 目前只输出 JSON 摘要。完整 JSON/CSV/Markdown/雷达图在 Phase 6，尚未生成。
7. LLM Judge、外部 HTTP/真实 Agent Adapter、凭据脱敏与调用预算尚未实现；当前离线配置不接收密钥。
8. **未在 openKylin 运行。** macOS 测试与 Python 3.10 语法检查不能代替目标系统及最低版本验证。
9. 依赖范围已声明、当前运行版本已记录；跨平台锁定与干净环境安装矩阵仍需后续验证。
10. 当前项目没有 Git 仓库，git_commit 为 null；manifest 保存源文件 SHA-256。比赛截止时间、规则和许可条款尚未核实。

## 下一步

从 Phase 3 开始：按六维各 2 条设计 seed，先审核正例、反例和证据要求，再扩展 schema/协议/evaluator，并用离线测试验证。随后进入完整评分、两套真实 Agent 和报告阶段。外部服务、凭据和 openKylin 设备缺失只阻塞对应集成，不阻止本地数据与评分开发。

完整待办见 TODO.md；本轮没有配置后台自动继续或定时任务。

## 架构意见保存记录（2026-10-13）

已按用户要求新增 [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)，完整保存六点架构建议和建议执行顺序；在 PROJECT_SPEC.md、IMPLEMENTATION_PLAN.md、README.md 中加入入口，并在 TODO.md 添加未完成的落实清单。

本次是文档更新。六点建议及前置真实 Agent/openKylin 验证尚待实施，Phase 3–9 的完成状态保持待开发/待验证。上文 32 项测试结果来自先前骨架验证，本次仅检查 Markdown 文件内容、引用和保存结果，没有新增程序测试或 Agent 实测。

继续开发时先读架构评审，再结合原九阶段计划选择最早可执行的工作；外部接入受阻时继续独立的用例、协议和评分任务。
