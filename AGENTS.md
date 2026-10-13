# MemoryScope-OK 项目工作规范

## 开始工作

先读 `PROJECT_SPEC.md`、`IMPLEMENTATION_PLAN.md`、`STATUS.md`、`TODO.md`；以用户最新指令和实际代码为准。规范描述目标，STATUS 记录已验证的事实。比赛规则没有官方来源时必须标为待核实，不要沿用聊天中的日期、评分权重或兼容性结论。

## 实施原则

- 先单例端到端，再六类各 2 条，最后各 8 条共 48 条。不要用批量生成的数据凑数。
- Python 3.10+，CLI 优先；核心不依赖特定 Agent。保持依赖轻量，暂不增加 Web 服务或数据库。
- Demo/Mock 只测试框架；所有产物必须标识 synthetic，不能计入“至少两个真实 Agent”验收。
- Agent 只能接收交互、任务及必要执行环境，不能读 expected、评分规则、其他 Agent 或其他 case 的记忆。
- `reset_session` 清除短期对话但保留同一 case 的长期记忆；`reset_case` 清除上一个 case 的全部状态。没有隔离或截断证据，不能宣称测到了长期记忆。
- 确定性检查优先；LLM Judge 可选且默认关闭。不能用 Judge 替代文件存在、实际工具执行等事实检查。
- 失败、错误、unsupported、无法观测要分别记录。缺失维度用 null；六维不完整时不要生成完整 Overall Score。
- 稳定 case ID、schema 版本、数据/配置摘要、原始证据和评分理由必须可追踪。更改指标语义要更新版本和文档。
- 数据只用虚构信息；密钥只能从环境变量读取，不得进配置、数据集、日志或报告。外部 Agent 接入前落实脱敏、权限和隔离。
- 文件任务只能使用测试沙箱；不能把数据集中的 `~` 或绝对路径映射到真实用户目录。不要执行用例中的任意 shell。
- 保持 Linux/openKylin 可移植性。macOS 本地测试不能替代 openKylin 实机验证。

## 验证与交接

使用项目虚拟环境。标准检查：

```bash
python -m pip install -e '.[dev]'
memoryscope --help
memoryscope validate datasets/golden
memoryscope run configs/demo.yaml
pytest -q
```

每个阶段完成后记录实际测试命令、测试数、环境、run 路径、局限和下一步到 `STATUS.md` / `TODO.md`。不得把未执行的命令写为通过。复杂变更加入有意义的负例、隔离和失败路径测试。

先检查已有文件再修改；保留用户现有内容。非关键设计选择采用合理默认值并记录，不频繁打断。不得推送远端、购买 API、创建付费资源、泄露凭据、删除重要内容或执行危险修改。账户/费用/设备受阻时记录原因并继续独立的本地工作。

## 规范来源

此文件用于项目级工作约定，参考 [Codex 官方 AGENTS.md 文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。后续从本项目根目录启动 Codex；无需更改全局设置。
