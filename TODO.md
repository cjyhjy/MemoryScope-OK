# TODO

## 云端优化：P0 配对基础设施（2026-10-16）

- [x] 检查远端分支与用户改动，在干净基线新建 `dot/memoryscope-p0`，保留历史数据和结果。
- [x] 受控 synthetic 困难单例 memory-on/off 离线闭环；新增草案不计入原 48 条人工审核。
- [x] 相同公开交互、算法/模型身份、权限与预算；切断上下文、MEMORY.md、workspace、home、缓存、会话数据库等沙箱状态，记录前后证据和实际 probe。
- [x] 公共回答、旧值非使用和指定存储删除独立；保留 `dynamic_update-007` 删除失败，未升级历史评分器。
- [x] 真实 Adapter 配对默认 unsupported；缺失隔离证据 unknown；不信任 command 的 `MEMORYSCOPE_AGENT_HOME`。
- [x] 故障、残留状态、缺失状态面、评分答案泄漏、预算、旧格式边界与历史失败回归；云端完整测试 114 passed / 1 GUI module skipped。
- [ ] 证明真实 Adapter 的全状态边界后再接入配对；不得以关闭 MEMORY.md 提示词或换 thread ID 代替隔离。在线实验需后续单独任务，本轮不执行。
- [ ] 文件复用协议：预声明保留清单，两组相同文件与摘要，独立于纯记忆归因；P0 禁止保留文件。
- [ ] 配对结果的离线重评/GUI 支持、重复采样与顺序平衡、语义失效判断、指定存储删除操作审计。
- [ ] 人工复核新困难草案与原 48 条，验证真实模型难度；本轮 synthetic 差值不能证明实际区分度。
- [ ] 配对实现的 openKylin 实机验证与可选 GUI 回归；当前 Debian 云端结果不能替代。

更新时间：2026-10-16（America/New_York）。已完成事项与证据见 STATUS.md；未勾选项均未完成。

## 当前协作任务（2026-10-16）

- [x] 核验官网交付段，确认 openKylin 桌面、两款智能体、多维雷达图、3–5 分钟录屏要求；完整规则仍需核对。
- [x] 写入 `docs/CLI_GUI_HANDOFF.md`：Codex 负责核心/CLI，Claude 负责 GUI；约定现有命令、独占请求目录、结果与事件 schema、错误和缺维展示。
- [x] Codex：按用户要求将 Server 安装替换为 ARM64 桌面版，校验官方 ISO，完成安装、桌面与两次硬盘启动验证；见 `docs/openkylin-deployment.md`。
- [x] Codex CLI 本地实现：0.3.0 机器接口、进度、可复用报告、自包含离线重评；85 项测试及 synthetic 一键脚本通过，见 STATUS。
- [x] Codex CLI MVP Goal：补齐稳定的机器可读命令、运行定位/进度、报告与重评、错误处理和扩展接口，完成测试及 openKylin 的项目初验；保留现有真实结果，不以 48 条或 Judge 作为 MVP 门槛。
- [x] openKylin 真实全量评测：48 条 draft cases × Codex CLI/dsh，共 96 条 case 结果；报告、雷达图、事件与快照已安全带回宿主项目。
- [x] Claude：PySide6 GUI（结果页、新建评测、异步进度、证据、报告/重评）与 `memoryscope view` HTML 页，macOS 测试通过（2026-10-16）。
- [x] openKylin 桌面 GUI 核心验收：真实 48×2 展示、fail 筛选与证据、新建 synthetic 单例/进度/报告、离线重评、历史恢复、空 Agent 校验；详见 STATUS 及 docs/validation/gui-acceptance-20261016-run/。
- [ ] 外部 PNG 查看器唤起待排查：内嵌雷达图、PNG 文件和缩略图正常，但打开按钮未观察到查看器窗口。
- [x] 录屏归档与初剪：`video/public/rec/demo.mov`，3:57；原片和剪点 JSON 已保留。现场单例为 synthetic，48×2 为既有真实结果。
- [ ] 视频精剪：按配音调整时序/定格，完成字幕及最终逐帧隐私复核。
- [ ] 系统级 dpkg 安装：按用户最新要求暂缓；用户安装已通过，不作为当前 GUI 验收阻塞项。

## 已完成

- [x] 包、CLI（validate / list-agents / run / report / rescore）、steps 格式用例、五种结果状态与覆盖率。
- [x] 评分器 1.2（边界匹配、下划线分隔、星期写法归一），离线重评。
- [x] Codex CLI 与 DeepSeek Harness Adapter，每个 case 独立 home/工作区，不触碰用户配置。
- [x] JSON/CSV/Markdown/雷达图报告。
- [x] 24 条用例（六维各 4）上两个真实 Agent 完整评测（macOS），两者均 100。
- [x] 新增 12 条 hard 用例（共 36 条），完整评测：codex 97.2，dsh 100.0，结果在 docs/results/macos-36/。
- [x] dsh 模型通过 `--patch` 固定为 deepseek-flash，并用 `--dump-config` 读回验证。
- [x] 脚本：setup_openkylin.sh、run_all.sh、build_deb.sh、dataset_table.py（macOS 一键脚本已验证；openKylin 本轮手动执行等价的 Python 安装/测试/CLI/报告流程，未声称脚本整体或 .deb 通过）。
- [x] 文档：SOLUTION.md、dataset-review.md、demo-script.md，README 已重写。
- [x] 创建 openKylin ARM64 虚拟机并完成 Server 写盘；2026-10-15 观察到登录界面，现按用户要求替换桌面版。

## 用户需亲自操作

- [x] 下载官方 openKylin 3.0 ARM64 ISO，核对 MD5 `29e1ba9b3d2f8fa088f308ea4d83b6ea`。
- [x] 在 Server 安装器中自行设置用户与 root 密码；Server 已写盘，桌面版需另行设置。
- [x] 确认改接 SATA 后安装器能列出 80 GB 虚拟盘；此前 NVMe 接口未列出磁盘。
- [x] 完成桌面版安装、桌面及重启验证；记录 i8042 启动参数修复与 OSTree 维护限制。
- [x] 在 openKylin 内安装项目、codex、dsh，并运行两个真实 Agent 的 48×2 完整评测。
- [ ] 录制 3–5 分钟演示视频。

## 数据集（优先）

- [ ] 区分度仍然很低：openKylin 48×2 单次运行中仅 codex `dynamic_update-007` 未通过，dsh 全部通过。需要更长会话链、冲突来源、组合推理、多文件任务和记忆容量压力，并做重复运行。
- [ ] 逐条复核现有 48 条候选（六维各 8 条，提交 661e339）；数量已齐，质量验收仍未完成，复核后才将 `review_status` 从 draft 改为 reviewed。此项不阻塞 MVP CLI 接口交付。
- [ ] 将已完成的受控 synthetic 配对基线扩展到隔离已证明的真实 Agent；仅关闭 MEMORY.md 约定不足以建立无记忆条件。

## 评测与报告

- [ ] 每个 Agent 重复多次，报告均值与波动。
- [ ] 可选的 LLM Judge（默认关闭，不能覆盖确定性检查）。

## openKylin 与交付

- [x] openKylin 上：CLI 安装、85 项 pytest、validate、synthetic 单例、报告与雷达图文件；记录环境和日志。
- [x] openKylin 上：两个真实 Agent 完整 48 条 run，生成 JSON/CSV/Markdown/雷达图并目视核对；run `20261016T064413939014Z-0d5dfa7e5bd8`。
- [ ] openKylin 桌面录屏中展示完整报告和雷达图；GUI 核心桌面联调已通过，录屏未执行。
- [x] Python 3.10 解释器完整测试（macOS，uv 3.10.21，90 passed）。
- [x] .deb 交叉构建（macOS → arm64 / Python 3.12），见 STATUS。
- [ ] 在 openKylin 上 `sudo dpkg -i` 安装并运行 `memoryscope-ok all configs/demo-smoke.yaml`（用户要求暂缓，当前使用已验收的用户目录安装）。
- [x] 把 SOLUTION.md 第 7、8 节、STATUS、README、演示和验证文档更新为 openKylin 实机结果。
- [ ] 从官方来源核实赛题、截止时间（项目目标写的是 2026-10-16）、提交要求。

## GitHub 交付（2026-10-16）

- [x] 创建公开仓库 cjyhjy/MemoryScope-OK 并推送本地代码与作品材料。
- [x] 发布 v0.3.0-demo Release，上传最终演示视频与作品介绍 PDF，README 提供下载入口。
