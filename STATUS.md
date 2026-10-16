# 项目状态

## 2026-10-16 云端 P0：可审计配对基础设施

本节为当前云端任务记录；下文 Mac/openKylin 内容保留为历史。云端目录 `/workspace/MemoryScope-OK`，Debian GNU/Linux 13 x86_64，Python 3.12.14；不是 openKylin 实机验证。初始工作区干净，HEAD 与远端 main 均为 `b8b89a98e32f56726351635eef1d154c9299bf1d`，远端检查时不存在 `dot/memoryscope-p0`，本轮新建该分支。用户最新授权允许测试通过后提交并推送该分支，禁止强推、合并 main、创建 PR。

已实现：独立 `run-paired`、`paired-1.0` 结果、显式协议与相同调用预算、受控 synthetic Adapter、每个会话边界的状态清理及前后审计、公共回答与存储检查分离、独立 Markdown 报告。memory-on 只保留 `demo_memory_list`；memory-off 同时清空它；两组都清空上下文和整个沙箱。禁止任务文件保留，真实 codex/dsh/command 在构造/启动前 unsupported；缺少或违反隔离证据为 unknown，执行异常为 error。没有加载 `.env`、调用真实 Agent/付费 API、配置密钥或操作其他设备/系统包。

新单例位于 `datasets/paired/`，hard / draft，明确未人工复核，不计入原 48 条。原 `datasets/golden` 和 `docs/results` 没有 diff；历史仍为 95/96 pass，同模型、统一 `MEMORY.md` 协议，不能声称原生产品记忆比较。`dynamic_update-007` 正确回答致远楼 571、保留已撤销旧值 517、原明确删除约束失败均保留，未改评分器或重评。

| 实际命令 / 检查 | 结果 |
| --- | --- |
| `python3 -m venv .venv`；`.venv/bin/python -m pip install -e '.[dev]'` | 成功，未安装 GUI extra |
| `.venv/bin/memoryscope --help` | 成功，列出 run-paired |
| `.venv/bin/memoryscope validate datasets/golden` | 48 cases / 6 files 有效 |
| `.venv/bin/memoryscope validate datasets/paired` | 1 case / 1 file 有效 |
| `.venv/bin/memoryscope check-config configs/paired-demo.yaml --json` | 成功 |
| `.venv/bin/pytest -q tests/test_paired.py`（阶段验证） | 20 passed；随后新增 1 项遗漏状态面负例纳入完整测试 |
| `.venv/bin/pytest -q`（最终代码） | **114 passed, 1 skipped**，3.29s；GUI 模块缺少 PySide6，未验证 GUI |
| `.venv/bin/memoryscope run-paired configs/paired-demo.yaml --json` | 实际运行成功，synthetic 公共差值 +1.0；不是实际模型记忆收益 |
| `run_paired(Path('configs/paired-demo.yaml'))`（最终代码归档） | run `20261016T180415254958Z-paired-5ac582b07111`，42 个连续事件、两组各 7 次调用；五项产物 SHA-256 一致 |
| `.venv/bin/memoryscope run configs/demo.yaml --json` | 旧 synthetic 流程完成：8 条 retention，3 pass / 5 fail，整体缺维 null；不伪报全通过 |
| `.venv/bin/memoryscope run configs/demo-smoke.yaml --json` | run `20261016T180415419976Z-1953de4f1303`，synthetic 单例 pass，Overall null |
| `.venv/bin/memoryscope report runs/20261016T180415419976Z-1953de4f1303 --json` | 成功生成四类旧格式报告；matplotlib 对只读默认缓存采用临时目录回退 |
| `git diff --exit-code -- datasets/golden docs/results`；`git diff --check` | 历史数据/结果无修改，差异格式检查通过 |

最终配对原始产物：[docs/validation/paired-p0-20261016/](docs/validation/paired-p0-20261016/paired-report.md)，包含完整快照、事件、结果与元数据，测试日志也归档于该目录。源码 SHA-256 `544bb5eb409f69b52cf525706606bde655acf2f5d507c5ab0d3e73865434078d` 与最终 Python 代码树核对一致；产物中的 git_commit 是初始 HEAD，源码摘要包含当时尚未提交的实现。

实际困难草案结果：memory-on 回答正确、旧值在最终回答中未使用，但指定存储仍保留 517，删除检查 fail；memory-off 回答 fail，存储清空由 harness 导致，其 Agent 删除判断为 unknown。公共差值仅由回答计算，存储不进入分母，Overall 为 null。

限制与恢复条件：真实 Agent 的 HOME/XDG、缓存、原生/远端存储、会话数据库、权限等完整隔离待逐项证明；`MEMORYSCOPE_AGENT_HOME` 不能作证明。文件复用、语义失效判定、重复采样/顺序平衡、人工用例审核及配对 GUI/离线重评待完成。详见 [配对协议](docs/p0-paired-protocol.md)。本轮交付只验证云端离线基础设施。

更新日期：2026-10-16（America/New_York）。项目根目录：`/Users/cjy/Documents/MemoryScope-OK`。本文件只记录已实际执行并核对过的事实。

## 当前结论

- 版本 **0.3.0**，评分器 **1.2**，数据 schema 1.1。
- 数据集 `datasets/golden`：**48 条候选**（六维各 8 条），均为 draft。2026-10-16 已在 openKylin 用两个真实 Agent 全量执行，共 96 条 case 结果；这不替代逐条人工质量复核，不能仅凭数量称为最终 golden。
- openKylin 主结果：run `20261016T064413939014Z-0d5dfa7e5bd8`；Codex CLI 47/48、总分 97.9，DeepSeek Harness 48/48、总分 100.0，覆盖率均 100%。旧 macOS 36 条结果保留为历史对照，不冒充本次 Linux 结果。
- 2026-10-16 新增 PySide6 GUI 与 `memoryscope view` HTML 页；.deb 改为可交叉构建、离线安装并包含 GUI（130 MB）。macOS 上 104 项测试通过（Python 3.10/3.13）。openKylin 上 .deb 安装与 GUI 启动尚未验收（`check.sh` 待运行）。
- 官方要求（2026-10-16 核对）：开源中国报道写 10 月 16 日 24 点前提交代码仓库链接、作品介绍文档、演示视频链接，10/21 公布决赛名单，10/29 决赛；openKylin 赛题页仍写 10 月 11 日截止，以报名页为准。
- 架构评价与后续规划：`docs/architecture-review-20261016.md`（取代 2026-10-13 的 ARCHITECTURE_REVIEW.md）。

## 已实现

- CLI：`validate`、`list-agents`、`run`、`report`、`rescore`（离线重评已保存证据，不调用 Agent）。
- 用例格式：steps（message / new_session / probe / check_memory / check_file）。expected 只交给评分器，不传给 Agent。
- 结果状态 pass / fail / unknown / error / unsupported 分开记录。维度分 = 100 × pass / (pass + fail)，其余状态不进分母，但会降低覆盖率。任一维度缺失时六维总分为 null。
- 评分器 1.2（确定性规则，无 LLM）：
  - `contains` / `answer_line`；拉丁字母/数字词按边界匹配，下划线视为分隔符。
  - “星期X/礼拜X”统一为“周X”。
- Adapter：Demo（synthetic）、Codex CLI（`codex exec --json`，DeepSeek OpenAI 兼容接口）、DeepSeek Harness（`dsh --profile headless --json`）。
  - 每个 case 使用独立的临时 home 和工作区，不读写 `~/.codex`、`~/.dsh`。
  - 两者都用 `deepseek-flash`。dsh 通过 `--patch` 覆盖 `agent-default-model` 来固定模型，启动时用 `--dump-config` 读回实际模型，记入 `describe.effective_model`；不一致则拒绝运行。
  - 长期记忆仅为工作区 `MEMORY.md`，每步后保存快照。
  - 密钥只从环境变量或项目 `.env` 读取。
- 报告：JSON / CSV / Markdown / 雷达图。Run 记录配置与数据快照、SHA-256、git commit 和源码摘要（自 9b81681 起在运行开始时记录）、评分器版本、Agent 版本。
- 脚本：
  - `scripts/setup_openkylin.sh`：apt、.venv、用户级 Node 24，npm 安装 `@openai/codex` 与 `@deepseek-ai/dsh`。
  - `scripts/run_all.sh`：在 macOS 上用 demo 配置实测通过。
  - `scripts/build_deb.sh`：只做过语法检查，macOS 没有 dpkg，无法实测。
  - `scripts/dataset_table.py`。
- 文档：`docs/SOLUTION.md`、`docs/dataset-review.md`、`docs/demo-script.md`、README。

## 已执行验证（2026-10-14，macOS）

环境：macOS 26.5.1，Apple M5 Pro（arm64），项目 `.venv` Python 3.13.15；codex-cli 0.162.0-alpha.17.2；dsh 0.2.0-rc.2。

| 命令 | 结果 |
| --- | --- |
| `.venv/bin/pytest -q` | **64 passed** |
| `memoryscope validate datasets/golden` | 36 cases / 6 files，有效 |
| `memoryscope list-agents` | demo / codex / dsh |
| `bash scripts/run_all.sh configs/demo.yaml` | 校验、测试、demo 运行和报告均成功；demo 为 synthetic，不计成绩 |
| `memoryscope rescore runs/20261013T185847074474Z-e26d88f7bfa9` | 评分器 1.2 重评，4 项 fail→pass |
| `memoryscope run configs/agents.yaml`（24 条） | run `20261014T130907864234Z-42ff04345691`：两者 100.0，48/48 pass |
| `memoryscope run configs/agents.yaml`（36 条） | run `20261014T134105387645Z-4d4bb8788e74`，见下 |
| `memoryscope run configs/smoke.yaml` | run `20261014T142602344632Z-b2790f5f2d12`：两者 pass；dsh `effective_model=deepseek-flash`，确认 `--patch` 在真实调用中可用 |
| 实际 dsh `--dump-config` | 默认模型就是 deepseek-flash；打补丁改成 deepseek-v4-pro 后读回的也是 v4-pro（未调用 API） |

## macOS 历史真实 Agent 评测（36 条，2026-10-14）

- Run：`runs/20261014T134105387645Z-4d4bb8788e74`，13:41–14:25 UTC（约 44 分钟），completed，982 条事件。
- 代码与数据为提交 379e74c 时的状态。metadata 中的 git_commit 显示为 700964a，是因为当时在运行结束时才记录；9b81681 已改为在开始时记录。运行期间数据和评分器都没有改动。
- 报告副本：[docs/results/macos-36/report.md](docs/results/macos-36/report.md)、[docs/results/macos-36/radar.png](docs/results/macos-36/radar.png)。

| 维度 | codex（Codex CLI + deepseek-flash） | dsh（DeepSeek Harness + deepseek-flash） |
| --- | --- | --- |
| retention | 100.0（6/6） | 100.0（6/6） |
| retrieval | 100.0（6/6） | 100.0（6/6） |
| dynamic_update | 100.0（6/6） | 100.0（6/6） |
| disambiguation | 100.0（6/6） | 100.0（6/6） |
| boundary | 100.0（6/6） | 100.0（6/6） |
| reuse | **83.3（5/6）** | 100.0（6/6） |
| **六维总分** | **97.2** | **100.0** |

- 状态分布：
  - codex：35 pass / 1 fail / 0 unknown / 0 error / 0 unsupported；
  - dsh：36 pass / 0 fail，其余为 0。
- 唯一未通过：codex `reuse-002`。codex 在第一个会话写 MEMORY.md 时自拟了示例 `exp-01.md`，第二个会话按这个示例建了 `notes/exp-07.md`（编号补零），用户要求的是 `exp-编号.md`，即 `notes/exp-7.md`。因此 `check_file` 判为找不到文件，`answer_line` 中的路径也不符（给的是绝对路径 `…/notes/exp-07.md`）。这是 Agent 在记忆写入时自行加工规则导致的偏差。没有为了提分修改题目或答案。
- 新增的 12 条 hard 题中，两个 Agent 全部通过。区分度依然很低，需要更难的机制。

## openKylin 48 条真实全量评测（2026-10-16）

- 环境：openKylin 3.0 (huanghe)，aarch64，Linux 7.0.0-3-generic，Python 3.12.2；MemoryScope-OK 0.3.0、evaluator 1.2、schema 1.1。
- 运行：06:44:13–07:40:50 UTC，约 56 分 36 秒；completed、synthetic=false。codex-cli 0.162.1 与 dsh 0.2.0-rc.2 均使用 deepseek-flash，dsh 的 effective_model 读回一致。
- 数据与结果：48 条 draft cases × 2 个真实 Agent，共 96 条 case 结果。Codex 47 pass / 1 fail，dynamic_update 为 87.5，其余五维 100，总分 97.9；dsh 48/48、六维均 100，总分 100。两者均无 error / unknown / unsupported，覆盖率 100%。
- Codex 唯一失败 `dynamic_update-007`：最终回答正确使用“致远楼 571”，但 `MEMORY.md` 仍保留旧值 517，触发存储证据的 exclude 检查。
- 隔离证据：96 个唯一 namespace、96 次 `case_reset`，reset 后遗留 memory 为 0；1506 条事件序号连续且时间单调，包含 270 次 `session_reset` 和 124 条 evaluation。
- 原始产物和四类报告已安全带回宿主 [run 目录](runs/20261016T064413939014Z-0d5dfa7e5bd8)，未覆盖既有运行。传输归档 SHA-256 为 `5ed48c950c992c2aad88d3ba06702ccb0dab76bd98f417afe705aea5fc719f1d`；关键文件 hash 与 metadata 一致。
- 宿主执行 `memoryscope report <run> --reuse --json` 成功；[雷达图](runs/20261016T064413939014Z-0d5dfa7e5bd8/report/radar.png)已目视核对标题、run ID、六轴、图例和 87.5 差异，无明显遮挡。
- run 目录密钥扫描未发现 `DEEPSEEK_API_KEY=` 赋值或常见 `sk-...` 形态；metadata 仅记录环境变量名。完整记录见 [docs/validation/openkylin-real-20261016.md](docs/validation/openkylin-real-20261016.md)。

## 局限与解读

1. **区分度不足**：openKylin 48×2 结果中仍只有 1 条拉开差距，单次运行的 1 条差异不足以下结论。
2. 长期记忆机制是评测框架声明的 `MEMORY.md` 约定（两个 Agent 相同），测的不是各产品原生的记忆功能。
3. 每个 Agent 只跑了 1 次，没有重复采样和方差。
4. 评分只用确定性规则，LLM Judge 尚未实现。
5. openKylin 的两个真实 Agent 全量评测已完成；Python 3.10、.deb、一键脚本整体、GUI 联调和录屏仍未实测。
6. 2026-10-15 已核验官网交付段：openKylin 桌面、至少两款智能体、CLI、多维雷达图及 3–5 分钟录屏；完整规则与最新提交安排仍待核对，来源见下文。

## openKylin 虚拟机准备（2026-10-14）

已在 VMware Fusion 26.0.0 中新建独立虚拟机 `~/Virtual Machines.localized/openKylin-3.0-ARM64.vmwarevm`：Other Linux 6.x 64-bit Arm、UEFI、4 vCPU、8 GB 内存、80 GB 虚拟盘。现有 Ubuntu 虚拟机未改动。

用户已将官方 `openKylin-Server-V3.0-2026.8.27-3-arm64.iso` 下载到 `~/Downloads/`。已核对文件大小 1,748,994,048 字节、MD5 `29e1ba9b3d2f8fa088f308ea4d83b6ea`，与官网公布值一致；原 ISO 未修改。

首次从 ISO 启动时，Linux 7.0.0-2-generic 在 `i8042_init` 内的 `logic_inb` 发生内核异常，无法进入安装器。为排查制作了 `/private/tmp/openkylin-v3-arm64-install-workaround.iso` 临时副本，仅修改其 GRUB 启动参数为 `initcall_blacklist=i8042_init` 并延长菜单等待时间。虚拟机加了串口文件日志 `/private/tmp/openkylin-serial.log` 用于记录内核输出；后因跳过旧式键盘控制器后无法输入，又在该虚拟机中启用 `keyboard.vusb.enable = "TRUE"`。这组设置已让安装器正常启动并接收键盘输入。

首次安装会话未列出 NVMe 磁盘，故将同一 80 GB 虚拟盘改接 SATA。后续安装器识别 `/dev/sda`，用户设置用户/root 密码、America/New_York、简体中文、DHCP，并确认目标盘。安装器完成 10/10 步骤、提示 `Installation complete`。断开 ISO 后首次引导的串口日志显示同一 i8042 内核异常；2026-10-15 当前观察到 openKylin 3.0 的 tty1 登录画面，证明 Server 已能启动，但本次未审计期间的修复操作，不能据此补记项目验证通过。

## 桌面版与协作交接（2026-10-15）

- 用户要求删除昨日 Server 安装、重新安装 openKylin 桌面版。已从官方下载 `openKylin-Desktop-V3.0-20260918-arm64.iso`，大小 7,063,267,328 字节，本地 `md5` 为 `58650dfbe8c272167f6f2f59eb04eb8a`，与官网一致。
- 已正常关闭旧 Server（`vmrun stop ... soft`，退出 0；`vmrun list` 确认 0 台运行），将旧 bundle 移入 `~/.Trash/openKylin-Server-3.0-ARM64-20261015.vmwarevm`，可恢复。新建 `~/Virtual Machines.localized/openKylin-Desktop-3.0-ARM64.vmwarevm`，4 vCPU、8 GB RAM、全新 80 GB SATA 虚拟盘、NAT。
- 桌面 ISO 内核为 `7.0.0-3-generic`，原版启动仍在 i8042_init / logic_inb 崩溃。已制作独立副本 `/private/tmp/openkylin-desktop-arm64-workaround.iso`，仅在 GRUB 配置原位置等长替换内容，保留 Try/Install 菜单，增加 `initcall_blacklist=i8042_init` 和串口参数。修改内容从副本读回核对；原版 ISO 未改。副本已成功越过内核异常，进入 UKUI 图形桌面（串口 `/private/tmp/openkylin-desktop-serial.log`）；VMware Tools 报告 IP `172.16.63.130`。
- 用户确认协议、自行设置密码并开始安装；安装器最终提示“安装完成”。实测分区为 EFI、boot、sysroot、data、swap（安装预览曾含 backup，以最终 lsblk/fstab 为准）。已通过备份、修改有效 GRUB/OSTree 条目和部署内配置源保存 i8042 参数，`grub-script-check` 退出 0。断开 ISO 后两次正常硬盘启动均进入 UKUI 桌面，vmware.log 与串口不同 bootid 交叉确认。**桌面系统部署完成；后续 CLI 项目验证见本文末尾。**细节、工具失败与恢复、升级限制见 `docs/openkylin-deployment.md`。
- 原版桌面 ISO 已移至 `~/Downloads/`，Mac 只读挂载已卸载，本次生成的临时安装副本已清理。旧 Server 的 9.7 GB 恢复副本仍在废纸篓，未清空。
- 官方来源：[系统下载页](https://www.openkylin.top/downloads/)（桌面 ARM downloadId=132）与[镜像直链](https://cdimage.openkylin.top/3.0/openKylin-Desktop-V3.0-20260918-arm64.iso)。本地暂存 `/private/tmp/`，避免把 ISO 加入项目。
- 已核验[官网赛题交付段](https://www.openkylin.top/news/4094-cn.html)，记录桌面环境录屏约束；未将“官网要求桌面演示”解释为“官网强制作品提供 GUI”。
- 用户决定 CLI + GUI：Codex 负责评测核心/CLI，Claude 负责 GUI；新建 `docs/CLI_GUI_HANDOFF.md`，并更新 PROJECT_SPEC、IMPLEMENTATION_PLAN、README、TODO。约定使用现有子进程接口、每个 GUI 请求的独占输出父目录、results 1.1 / events 1.0、报告与证据读取、失败/缺维/synthetic 展示。
- 首次交接仅核对文档、尚未修改核心；随后已完成下文 CLI 0.3.0 实现，GUI 尚未实现。`.gitignore` 增加 GUI 自动生成的 `configs/gui/`。已执行 `git diff --check`，退出 0；未因此重跑评测或测试。

## CLI MVP Goal（2026-10-15）

按用户要求，在系统部署完成后创建 Goal：在现有实现上完成可交付 MVP CLI 和供 Claude GUI 使用的稳定接口，保持核心独立、Agent/评分器可扩展、轻量依赖。优先机器可读输出、运行定位与进度、报告/离线重评、输入和错误路径以及本地与 openKylin 验证；GUI 由 Claude 负责。48 条扩展、可选 Judge、Web 服务和数据库不作为本轮 MVP 门槛。此段是工作目标，不是实现完成声明。

### CLI 0.3.0 本地实现与验证

已实现版本 1.0 的 `--json` 命令信封、离线 `check-config`、`run --jsonl` 安全生命周期进度与实际运行目录定位。进度仅公开标量状态，不包含题目、答案或记忆；界面观察器失败不改变评测成绩。报告分阶段发布，完整且与原始结果摘要匹配时才允许 `--reuse`；离线重评保留原始证据和来源摘要，生成可独立继续重评的新修订。CLI/GUI 仍共同调用已有核心，新增 Agent 沿 Adapter 注册扩展，评分语义仍为 1.2；没有增加 Web 服务或数据库。详见 `docs/CLI_GUI_HANDOFF.md`。

2026-10-15，macOS arm64 / 项目 `.venv` Python 3.13.15，实际执行：

| 命令 | 实际结果 |
| --- | --- |
| `.venv/bin/python -m pip install -e '.[dev]'` | 成功，安装 memoryscope-ok 0.3.0；首次受限环境网络失败，获准联网后重试成功 |
| `.venv/bin/memoryscope --help` | 成功，含 `check-config` 等命令 |
| `.venv/bin/memoryscope validate datasets/golden` | 成功，48 条 / 6 文件；只证明 schema/唯一性，不代表题目质量审阅通过 |
| `.venv/bin/memoryscope check-config configs/demo-smoke.yaml --json` | 成功，单例配置离线校验 |
| `.venv/bin/memoryscope run configs/demo-smoke.yaml --jsonl` | 成功，run `20261015T182409990450Z-732ccd23ee7b`，1 synthetic case，事件 18 条 |
| `bash scripts/run_all.sh configs/demo-smoke.yaml` | 成功，85 tests passed in 12.58s；run `20261015T182422072326Z-68c37f20b8d9`，完成报告 JSON/CSV/Markdown/PNG |
| `.venv/bin/memoryscope run configs/demo.yaml --json` | 成功，run `20261015T183025775852Z-686ca82eea1c`，synthetic；未调用真实 Agent |
| `bash -n scripts/run_all.sh scripts/setup_openkylin.sh`、`git diff --check` | 成功 |

新增测试覆盖机器接口、输入失败、执行失败、unsupported 进度、观察器异常、Ctrl+C 证据边界、报告中断/锁/旧结果不覆盖、离线重评来源与独立修订等。单维 synthetic 示例缺失维度与 Overall 保持 null，不作为两款真实 Agent 验收。Matplotlib 在受限 macOS 环境改用临时缓存目录，报告正常生成。

### openKylin 实机验证完成

环境：openKylin 3.0 (huanghe)，aarch64，内核 7.0.0-3-generic，Python 3.12.2。项目位于虚拟机 `/home/openkylin/msok-validation-20261015-1840/MemoryScope-OK`，独立用户虚拟环境 `.venv`。

- 首次 `python3 -m venv .venv` 因系统缺少 ensurepip 失败；保留初次日志 `docs/validation/openkylin-20261015-venv-initial.log`。未修改系统安全模式或安装系统包，改用 PyPA 官方 `https://bootstrap.pypa.io/virtualenv.pyz` 创建用户虚拟环境，原不完整目录改名 `.venv-incomplete`。
- `.venv/bin/python -m pip install -e '.[dev]'` 成功，安装 0.3.0；`memoryscope --version` / `--help`、`validate datasets/golden`（48/6）、`check-config configs/demo-smoke.yaml --json` 均成功。
- `.venv/bin/pytest -q`：**85 passed in 1.28s**。
- `memoryscope run configs/demo-smoke.yaml --json`：run `20261015T184021223058Z-8ea846f47945`，completed、synthetic，1 pass，缺失五维与 Overall 为 null。
- `memoryscope report <run_dir> --json` 与 `--reuse --json` 均成功；JSON 2137 B、CSV 468 B、Markdown 1189 B、PNG 136729 B。报告布局修复后，在 macOS 另一个 synthetic run 中目视核对图例不遮挡标题；Linux 验证了文件生成与完整性。
- 源码通过 VMware 专用网段临时传入，仅包含显式允许的源码、测试、配置和虚构数据；没有 `.env`、Git 历史、旧 runs 或密钥。归档 SHA256：`e38515acbec0a74430f0b5c94899fed72d6c279060e410c62f2d1dd517274991`，客体读回一致。归档不含 `.git`，该 Linux run 的 git_commit 无法记录；以此归档摘要和运行内源码摘要追踪。
- 完整成功日志：`docs/validation/openkylin-20261015.log`，末尾 `VALIDATION_EXIT=0`。原始 events/results/metadata 与报告保存在上述客体项目的 runs 目录。

CLI MVP、本地检查、openKylin 初验及两款真实 Agent 的 48×2 全量评测均已完成。GUI、打包、Python 3.10、重复运行与录屏仍是后续工作。2026-10-15 初验没有调用真实 API；2026-10-16 的独立全量运行调用了真实 API，二者不可混为同一次验证。

### 2026-10-16 宿主回归与收尾

- `.venv/bin/memoryscope --help`：退出 0。
- `.venv/bin/memoryscope validate datasets/golden`：48 cases / 6 files，退出 0。
- `.venv/bin/memoryscope report runs/20261016T064413939014Z-0d5dfa7e5bd8 --reuse --json`：退出 0，返回两款非 synthetic Agent 的同一分数和报告目录，未调用 Agent。
- `.venv/bin/pytest -q`：**86 passed in 17.13s**；新增回归覆盖 macOS AppleDouble `._*.jsonl` 旁文件不会被误当数据集。
- `git diff --check`：退出 0。
- 重新计算配置、数据、events、results 四个 SHA-256，与 metadata 全部一致。
- 结果确认带回后，已移除 VMware 的 `MSOK_TRANSFER` 临时共享、关闭运行时共享文件夹，并删除宿主 `/private/tmp` 中的传输归档；正式 run 目录保留且未覆盖既有运行。

## 2026-10-16 收尾（Claude）

- 把 Codex 留在工作区的 CLI 0.3.0 改动与文档在本地提交为 b1de9b6（提交前 86 项测试通过，做过密钥形态扫描）。
- 新增 `memoryscope view RUN_DIR [--open]`（`src/memoryscope/htmlview.py`）：离线生成自包含 HTML 结果页，作为图形化结果查看；`run_all.sh` 与 .deb 的 `memoryscope-ok all` 在报告之后自动生成并在有桌面时打开。已在浏览器中打开 openKylin 48×2 run 的页面核对：雷达图、六维表（Codex dynamic_update 87.5）、状态筛选到 fail 只剩 `dynamic_update-007`，评分理由与存储内容显示正确。
- `.deb` 改为 `scripts/build_deb.py`（标准库 + pip，无需 dpkg-deb，可在 macOS 交叉构建）：依赖 wheel 按目标平台下载并打包，postinst 用 `python3 -m venv --without-pip` 加随包 pip wheel 安装，不再依赖 openKylin 默认缺失的 ensurepip/python3-venv；Python 小版本写入 Depends 并在 postinst 校验。已在 macOS 构建 `dist/memoryscope-ok_0.3.0_arm64.deb`（Python 3.12，47,157,982 字节，sha256 `06e679d45f3f9e2a24693e4fb3e9f41749472a5c5529d025c1eda060c383fec4`），解析 ar/control/data 结构核对。openKylin 安装验收见下一条。
- `docs/results/` 重组：`openkylin-48x2/`（report.md/csv/json、radar.png、view.html、results.json、metadata.json；results.json SHA-256 与 metadata 一致）和 `macos-36/`（历史）。
- 录屏脚本按 .deb + 桌面 + HTML 结果页重写。
- 测试：`.venv/bin/pytest -q` **90 passed**（Python 3.13.15，macOS）；uv 创建的 Python **3.10.21** 环境 `pytest -q` **90 passed**。`bash scripts/run_all.sh configs/demo-smoke.yaml` 成功（synthetic）。
- 用户指出应按交接文档做 GUI，随即实现 PySide6 桌面 GUI（`src/memoryscope_gui/`，详见 `docs/CLI_GUI_HANDOFF.md` 顶部实现说明）。macOS 上 `.venv/bin/pytest -q` **104 passed**（新增 `tests/test_gui.py` 14 项，含 offscreen 窗口通过 CLI 端到端跑完 synthetic 评测并生成报告）；offscreen 截图核对了 48×2 run 的雷达图、六维表与 fail 用例详情。确认 PyPI 有 PySide6-Essentials 6.12.0 的 manylinux_2_39_aarch64 wheel（openKylin glibc 2.43）。
- .deb 重新构建为含 GUI 版本：`memoryscope-ok_0.3.0_arm64.deb` 129,571,582 字节，sha256 `a124693667ff84e2bc3ec487a83fed63e53348bef38a02b576f07ed2323df537`；新增 `memoryscope-ok gui` 与 `/usr/share/applications/memoryscope-ok.desktop`。openKylin 桌面上的安装与 GUI 启动尚未验证（OSTree 下 dpkg 是否可写 /usr 未知，验收脚本带用户目录回退）。

## 2026-10-16 Codex 接续 GUI 验收（等待客体解锁）

基于本地提交 ce515f5，开始时工作区干净；未覆盖 Claude 的实现、旧 run 或构建包。macOS arm64 / 项目 `.venv` Python 3.13.15 实际执行：

- `.venv/bin/python -m pip install -e '.[dev]' --no-build-isolation`：退出 0。
- `.venv/bin/memoryscope --help`、`validate datasets/golden`：退出 0，48 条 / 6 文件；仅 schema 验证。
- `.venv/bin/pytest -q`：104 passed in 11.68s，含 GUI offscreen CLI 端到端测试。
- `.venv/bin/memoryscope run configs/demo.yaml --json`：退出 0，run `20261016T113922611977Z-643ecdd792b3`；synthetic，retention 8 条为 3 pass / 5 fail，其他维度及 Overall 为 null。执行完成不代表 case 全通过。
- `bash scripts/run_all.sh configs/demo-smoke.yaml`：退出 0，104 passed in 13.55s；run `20261016T113950657024Z-d68c9997a119`，synthetic 单例 pass；JSON/CSV/Markdown/PNG 与 HTML 生成成功。Matplotlib/Fontconfig 报宿主缓存目录不可写，但最终报告成功。完整日志：`docs/validation/gui-acceptance-20261016-host.log`。
- 既有 openKylin 真实 run `20261016T064413939014Z-0d5dfa7e5bd8` 的 `report --reuse --json`：退出 0，Codex 97.9167、dsh 100；未重新调用真实 Agent。
- `dist/` 与 Claude 已有共享目录 `MemoryScope-OK-vmshare/okcheck/` 中的 arm64 deb SHA-256 均为 `a124693667ff84e2bc3ec487a83fed63e53348bef38a02b576f07ed2323df537`。
- 审阅共享目录 `check.sh`：它尝试 sudo dpkg，失败则回退用户目录安装，且最终 ALL DONE 不能代表每项成功；后续须逐项读取 DPKG_EXIT / ALL_EXIT / REUSE_EXIT / GUI_OFFSCREEN_EXIT 并核对可见窗口。

已启动现有 openKylin Desktop 虚拟机并观察到 UKUI 桌面与终端，随后客体进入密码锁屏。尚未取得客体命令输出，未执行 dpkg 安装，未启动项目 GUI；等待用户在虚拟机内自行解锁。没有收集或尝试猜测密码。openKylin GUI、deb 实装与桌面联调仍未验收通过；录屏、发布也未执行。

### 客体解锁后的连接检查

用户已解锁，已目视确认 openKylin 终端。当前 CUA 的点击可见，但多种键盘输入（typeText/paste/逐键/延长按键）未在客体终端产生可确认文本或命令输出，因此没有将按键发送记为执行成功。`vmrun getGuestIPAddress` 返回 `172.16.63.130`；SSH 22 端口连接被拒绝（不是认证失败）。已通过 `vmrun enableSharedFolders ... runtime` 启用预先配置的 msok 专用验收共享，退出 0；未增加新的共享目录。需要用户在客体终端启动已审阅的 `check.sh`，之后可从宿主共享目录读取各项日志继续验收；sudo 密码仅由用户在客体输入。

### 连接恢复进一步诊断

用户要求自行恢复连接后，再次确认 vmrun 列出目标虚拟机正在运行。尝试 VMware Tools 的 `listProcessesInGuest`（仅指定 openkylin 用户，不提供/猜测密码），明确返回 `Command requires valid user name and password for the guest OS`。重建 CUA 会话并重新绑定 Fusion 后，窗口树仍能返回，但坐标输入多次返回 `Computer Use server error -10005: noWindowsAvailable`；当前不能依赖其截图判断实时客体状态。尚未建立可执行客体命令的通道，安装与 GUI 验收保持待完成。未重置密码、关闭认证或开放远程服务。

### 已恢复客体命令输入，安装等待 sudo（2026-10-16）

更正此前推断：Mac 锁屏没有证据，虚拟机窗口可见。CUA 输入存在延迟和输入法预编辑/标点丢失；逐步核对后已实际执行 `pwd`（/home/openkylin）与 `ls /mnt/hgfs/msok`。创建已有共享 check.sh 的同内容、无标点入口 checkrun（保留原文件），成功执行 `bash /mnt/hgfs/msok/checkrun`。宿主已收到 `check-20261016-050836.log`，记录 openKylin 3.0、aarch64、Python 3.12.2、glibc 2.43、Wayland。当前脚本停在 sudo 密码提示，尚未运行 dpkg；需要用户仅在该提示中输入密码，然后继续读取日志验收。

### 用户目录安装与客体验收结果（2026-10-16）

已读取完整 `check-20261016-050836.log`，归档到 `docs/validation/gui-acceptance-20261016-openkylin.log`。sudo 三次密码错误，`DPKG_EXIT=1`，dpkg 实际未获授权执行；这不能证明 OSTree 或软件包不兼容，也不能算系统安装通过。

- 同一 arm64 .deb 解包到 `/home/openkylin/.local/memoryscope-ok-root/opt/memoryscope-ok`，随包 wheels 离线用户安装成功；工作目录 `/home/openkylin/memoryscope-ok`。
- `VERSION_EXIT=0`（0.3.0）、`VALIDATE_EXIT=0`（48 cases / 6 files）。
- `memoryscope-ok all configs/demo-smoke.yaml`：`ALL_EXIT=0`；run `20261016T121032656194Z-8d724513a404`，synthetic 单例 retention-001 pass，缺失五维与 Overall 均 null；报告及 HTML 已生成。
- 已有真实 run 的导入与 `report --reuse --json`：`REUSE_EXIT=0`；未调用真实 Agent。
- xcb 插件依赖齐全；GUI offscreen 成功加载真实 48×2 run，列表 2 项，`GUI_OFFSCREEN_EXIT=0`；启动后 `GUI_RUNNING=yes`，gui-stderr.log 为空。
- 当前实际看到 Firefox 打开的新 synthetic run HTML 页面，openKylin/Python 版本、用例 pass 和事件索引正常显示。桌面 PySide6 主窗口仍未目视验收：尝试切换时 CUA 坐标动作反复报 `noWindowsAvailable`，窗口截图可读，不能据此推断 Mac 锁屏或 GUI 故障。

当前通过的是用户安装、客体 CLI 一键流程和 GUI 离屏加载；系统 dpkg 安装、桌面 GUI 交互流程与录屏仍待完成。保留既有程序与数据，未推送远端。

### openKylin 桌面 GUI 实际交互验收（2026-10-16，Codex）

用户明确暂不验收系统级安装；本轮使用已有用户目录安装，通过 Fusion 内的真实 UKUI 桌面操作 PySide6 窗口。核心 GUI 流程通过，外部 PNG 查看器唤起仍未确认；不宣称所有桌面集成均通过。未修改 GUI 源码，未重新调用真实 Agent。

- 原生启动、中文布局、运行列表及重启后历史恢复正常。
- 加载既有真实 run `20261016T064413939014Z-0d5dfa7e5bd8`：48×2、Codex 97.9 / dsh 100、动态更新 87.5 / 100，内嵌六维雷达图与表格一致。运行环境页显示 openKylin 3.0 / Linux aarch64。
- 状态筛选 fail 仅剩 Codex `dynamic_update-007`；详情和证据弹窗显示事件 303–317，能查看 reset、记忆快照和评分证据。
- 新建评测仅勾选 demo，选择 datasets/smoke；预检成功，开始后显示异步进度、1/1 pass、报告生成并自动跳转结果页。run `20261016T122728161616Z-339acc5fa99a`，客体路径 `runs/gui/34d5b634-f029-415d-afc2-537c449dfa77/` 下。
- 新 run 明确显示 SYNTHETIC；retention 100，其余五维与 Overall 不可评分，没有伪造完整雷达多边形。
- GUI 报告复用成功；离线重评生成独立 `rescore-20261016T122803748366Z-9aa20e6d`，0 状态变化，原 run 保留。
- 空 Agent 预检弹出“配置无效 / 至少选择一个 Agent”，没有启动运行；缺少 DEEPSEEK_API_KEY 的提示可见，未填写密钥。
- “打开运行目录”成功打开客体文件管理器；report 中 JSON/CSV/Markdown/PNG 存在，PNG 缩略图可见。“打开 radar.png”及文件管理器双击未观察到外部图片查看器窗口，故此项保留待排查，不据此判定图表生成失败。
- 通过既有共享目录取回本次 synthetic 原始结果及重评，共 14 文件，保存到 `docs/validation/gui-acceptance-20261016-run/`；原 run 与重评各 4 个 artifacts SHA-256 均与 metadata 一致。

本轮完成 GUI 核心流程的客体可见交互验收；录屏尚未执行，系统级 dpkg 安装按用户要求暂缓。停止/取消运行及全部文件类型的外部默认程序打开未专项验收。前文连接失败和未验收描述为历史状态，以本节为当前结论。

## 2026-10-16 自定义命令行 Agent（Claude）

- 用户要求开放更多 Agent：新增 `type: command`（`adapters/command.py`，AgentConfig 增加 `command` / `name`，要求含 `{prompt}`，非 command 类型禁止 `command`）。复用 CliMemoryAgent 的每例独立 home/工作区与 MEMORY.md 约定；记忆约定附在每条提示词前，stdout 为回答，无会话续接。GUI 自动列出 `configs/custom-agents.yaml` 中的条目（示例 `configs/custom-agents.example.yaml`）。
- 测试：macOS `.venv/bin/pytest -q` **108 passed**（新增假命令行 Agent 端到端 pass、缺失命令记为 Agent 错误、配置校验、GUI 列出并写入请求）。已验收的 48×2 结果与 openKylin 安装未改动；含此功能的 .deb 尚未重建，openKylin 上未验证 command 类型。
- 已重建 `dist/memoryscope-ok_0.3.0_arm64.deb`（含 command 类型）：129,686,842 字节，sha256 `f13e7f8ef8af7e9bd3c838237ce1312446c74bc99f29bbd92e91127656500448`。共享目录 `okcheck/` 中保留的是已在 openKylin 验收的旧包 `a1246936…`，未覆盖。

## 录屏归档与初剪（2026-10-16，America/New_York）

- 桌面原片 `录屏2026-10-16 上午9.18.47.mov` 已复制为 `video/public/rec/demo-raw.mov`，桌面原文件保留。
- 初剪 `video/public/rec/demo.mov`：ffprobe 实测 237.000 秒（3:57），2784×1900，H.264，30 fps，无音轨；原片 1050.602 秒。
- 删除锁屏、输入调试、过程长等待和结尾等待；保留原顺序与原速，GUI 单例进度、既有真实 48×2 结果/证据/环境/重评，以及 CLI 演示。现场单例是 synthetic Demo，不能称为现场双真实 Agent 或全量运行。
- 剪点记录：`video/public/rec/demo-edit.json`。用 ffmpeg 解码并按 5 秒间隔抽帧核对，抽查未见 .env 内容或密钥，锁屏和文件管理器调试片段已去除。后续按配音精剪并完成最终逐帧隐私复核。

## GitHub 提交准备（2026-10-16）

- 纳入作品介绍 PDF、HTML 与配图，GUI 验收记录及视频剪辑源码。视频原片、成片、音频与 node_modules 继续排除在 Git 外；正式成片计划作为 Release 附件分发。
- 本轮 macOS 项目虚拟环境验证：`.venv/bin/pytest -q`，108 passed in 13.73s；`git diff --check` 通过。
- 正式成片 `video/out/memoryscope-ok-demo.mp4` 经 ffprobe 确认 249.472 秒、61,982,058 字节。作品介绍本地路径 `docs/submission/MemoryScope-OK-作品介绍.pdf`。
- 提交准备时远端尚未创建，未将计划推送写为已完成。

## GitHub 已发布（2026-10-16）

- 用户确认公开后，已创建并推送 https://github.com/cjyhjy/MemoryScope-OK ，提交 `2856ed2` 包含作品介绍 PDF、GUI 验收记录与剪辑源码。
- Release：https://github.com/cjyhjy/MemoryScope-OK/releases/tag/v0.3.0-demo 。正式视频 61,982,058 字节、作品介绍 PDF 4,842,582 字节均由 GitHub API 确认为 uploaded，Release 非草稿。
- README 视频链接指向 Release 附件。PDF 在仓库保留中文原名，Release 使用 `memoryscope-ok-introduction.pdf`。原片和视频输出未纳入 Git 历史。
