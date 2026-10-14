# TODO

更新时间：2026-10-14（UTC）。已完成事项与证据见 STATUS.md；未勾选项均未完成。

## 已完成

- [x] 包、CLI（validate / list-agents / run / report / rescore）、steps 格式用例、五种结果状态与覆盖率。
- [x] 评分器 1.2（边界匹配、下划线分隔、星期写法归一），离线重评。
- [x] Codex CLI 与 DeepSeek Harness Adapter，每个 case 独立 home/工作区，不触碰用户配置。
- [x] JSON/CSV/Markdown/雷达图报告。
- [x] 24 条用例（六维各 4）上两个真实 Agent 完整评测（macOS），两者均 100。
- [x] 新增 12 条 hard 用例（共 36 条），完整评测：codex 97.2，dsh 100.0，结果在 docs/results/。
- [x] dsh 模型通过 `--patch` 固定为 deepseek-flash，并用 `--dump-config` 读回验证。
- [x] 脚本：setup_openkylin.sh、run_all.sh、build_deb.sh、dataset_table.py（openKylin 上未实测）。
- [x] 文档：SOLUTION.md、dataset-review.md、demo-script.md，README 已重写。
- [x] 创建 openKylin ARM64 虚拟机（未装系统）。

## 用户需亲自操作

- [x] 下载官方 openKylin 3.0 ARM64 ISO，核对 MD5 `29e1ba9b3d2f8fa088f308ea4d83b6ea`。
- [ ] 在重新启动的 VMware 安装器中自行设置 openKylin 登录密码（此前已设置过一次，但未写盘并因输入故障重启；当前停在 Hostname）。
- [ ] 确认改接 SATA 后安装器能列出 80 GB 虚拟盘；此前 NVMe 接口未列出磁盘。
- [ ] 完成虚拟磁盘安装、重启及首次登录；将内核启动绕过参数持久化，并验证系统可再次启动。
- [ ] 在 openKylin 内安装项目、codex、dsh，运行完整评测（可由 Claude 远程指导或代为执行命令）。
- [ ] 录制 3–5 分钟演示视频。

## 数据集（优先）

- [ ] 区分度仍然很低：36 条中只有 codex reuse-002 一条未通过。需要更难的机制，例如更长的会话链（10 次以上切换）、冲突来源（两个人给出矛盾信息）、需要推理的组合、多文件任务、记忆容量压力（大量相似事实）。
- [ ] 扩到六维各 8 条共 48 条，逐条人工复核，`review_status` 从 draft 改为 reviewed。
- [ ] 加入无记忆基线（例如关闭 MEMORY.md 约定），证明题目确实依赖跨会话记忆。

## 评测与报告

- [ ] 每个 Agent 重复多次，报告均值与波动。
- [ ] 可选的 LLM Judge（默认关闭，不能覆盖确定性检查）。

## openKylin 与交付

- [ ] openKylin 上：安装、pytest、validate、demo、两个真实 Agent 完整 run、报告与雷达图，记录发行版/架构/Python 版本。
- [ ] Python 3.10 解释器完整测试。
- [ ] 在 openKylin 上执行 build_deb.sh，并实测安装与 `memoryscope-ok all`。
- [ ] openKylin 实测后，把 SOLUTION.md 第 7、8 节与 STATUS 更新为实机结果。
- [ ] 从官方来源核实赛题、截止时间（项目目标写的是 2026-10-16）、提交要求。
