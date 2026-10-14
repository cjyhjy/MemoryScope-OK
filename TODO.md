# TODO

更新时间：2026-10-14（UTC）。已完成事项与证据见 STATUS.md；未勾选项均未完成。

## 已完成

- [x] 包、CLI（validate / list-agents / run / report / rescore）、steps 格式用例、五种结果状态与覆盖率。
- [x] 评分器 1.2（边界匹配、下划线分隔、星期写法归一），离线重评。
- [x] Codex CLI 与 DeepSeek Harness Adapter，每个 case 独立 home/工作区，不触碰用户配置。
- [x] JSON/CSV/Markdown/雷达图报告。
- [x] 24 条用例（六维各 4）上两个真实 Agent 完整评测（macOS），结果在 docs/results/。
- [x] 创建 openKylin ARM64 虚拟机（未装系统）。

## 用户需亲自操作

- [ ] 下载官方 openKylin 3.0 ARM64 ISO，核对 MD5 `29e1ba9b3d2f8fa088f308ea4d83b6ea` 后安装系统。
- [ ] 在 openKylin 内安装项目、codex、dsh，运行完整评测（可由 Claude 远程指导或代为执行命令）。
- [ ] 录制 3–5 分钟演示视频。

## 数据集（优先）

- [ ] 当前两个 Agent 都是满分、区分不开：设计更难的用例（长干扰链、多次更新、更多相近实体、隐式调用、文件/工具复用）。
- [ ] 扩到六维各 8 条共 48 条，逐条人工复核，`review_status` 从 draft 改为 reviewed。
- [ ] 加入无记忆基线（例如关闭 MEMORY.md 约定），证明题目确实依赖跨会话记忆。

## 评测与报告

- [ ] 每个 Agent 重复多次，报告均值与波动。
- [ ] 可选的 LLM Judge（默认关闭，不能覆盖确定性检查）。
- [ ] 更新 README 到当前功能（目前仍写 1 条用例）。

## openKylin 与交付

- [ ] openKylin 上：安装、pytest、validate、demo、两个真实 Agent 完整 run、报告与雷达图，记录发行版/架构/Python 版本。
- [ ] Python 3.10 解释器完整测试。
- [ ] 打 .deb 包（一键 CLI）。
- [ ] 方案文档、样例与结果整理、录屏脚本。
- [ ] 从官方来源核实赛题、截止时间（项目目标写的是 2026-10-16）、提交要求。
