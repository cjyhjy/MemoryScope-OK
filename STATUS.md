# 项目状态

更新日期：2026-10-14（UTC）。项目根目录：`/Users/cjy/Documents/MemoryScope-OK`。本文件只记录已实际执行并核对过的事实。

## 当前结论

- 版本 **0.2.0**，评分器 **1.2**，数据 schema 1.1。
- 数据集 `datasets/golden`：**36 条**，六维各 6 条，其中每维 2 条 hard（由 `scripts/add_hard_cases.py` 生成），全部 `review_status: draft`。48 条目标尚未完成。
- 两个真实 Agent（Codex CLI、DeepSeek Harness）在 macOS 上完成 36 条完整评测，codex 97.2，dsh 100.0。
- 已写好 openKylin 安装脚本、一键运行脚本、.deb 打包脚本和方案/演示文档，**均未在 openKylin 上执行过**。系统安装进度见下文。

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

## 完整真实 Agent 评测（36 条）

- Run：`runs/20261014T134105387645Z-4d4bb8788e74`，13:41–14:25 UTC（约 44 分钟），completed，982 条事件。
- 代码与数据为提交 379e74c 时的状态。metadata 中的 git_commit 显示为 700964a，是因为当时在运行结束时才记录；9b81681 已改为在开始时记录。运行期间数据和评分器都没有改动。
- 报告副本：[docs/results/report.md](docs/results/report.md)、[docs/results/radar.png](docs/results/radar.png)。

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

## 局限与解读

1. **区分度不足**：36 条中只有 1 条拉开差距，单次运行的 1 条差异不足以下结论。
2. 长期记忆机制是评测框架声明的 `MEMORY.md` 约定（两个 Agent 相同），测的不是各产品原生的记忆功能。
3. 每个 Agent 只跑了 1 次，没有重复采样和方差。
4. 评分只用确定性规则，LLM Judge 尚未实现。
5. 仅在 macOS 上验证过；openKylin、Python 3.10 解释器、.deb 打包与安装、Linux 上 npm 安装 dsh 均未实测。
6. 比赛规则、截止时间和提交要求尚未从官方来源核实。

## openKylin 虚拟机准备（2026-10-14）

已在 VMware Fusion 26.0.0 中新建独立虚拟机 `~/Virtual Machines.localized/openKylin-3.0-ARM64.vmwarevm`：Other Linux 6.x 64-bit Arm、UEFI、4 vCPU、8 GB 内存、80 GB 虚拟盘。现有 Ubuntu 虚拟机未改动。

用户已将官方 `openKylin-Server-V3.0-2026.8.27-3-arm64.iso` 下载到 `~/Downloads/`。已核对文件大小 1,748,994,048 字节、MD5 `29e1ba9b3d2f8fa088f308ea4d83b6ea`，与官网公布值一致；原 ISO 未修改。

首次从 ISO 启动时，Linux 7.0.0-2-generic 在 `i8042_init` 内的 `logic_inb` 发生内核异常，无法进入安装器。为排查制作了 `/private/tmp/openkylin-v3-arm64-install-workaround.iso` 临时副本，仅修改其 GRUB 启动参数为 `initcall_blacklist=i8042_init` 并延长菜单等待时间。虚拟机加了串口文件日志 `/private/tmp/openkylin-serial.log` 用于记录内核输出；后因跳过旧式键盘控制器后无法输入，又在该虚拟机中启用 `keyboard.vusb.enable = "TRUE"`。这组设置已让安装器正常启动并接收键盘输入。

首次安装会话中，用户已自行设置用户和 root 密码；时区选 `America/New_York`。但到目标磁盘步骤时，安装器没有列出任何磁盘，只反复提示 `Enter a numeric selection.`。因此停止该会话，将同一块尚未写入系统的 80 GB 虚拟盘由 NVMe 改接到 SATA；VMware 界面确认显示 `Hard Disk (SATA) connected`。重新启动后，自动输入回车时出现 `Password must not be empty` 循环，故再次停止并重启。当前安装器重新停在 **Hostname [openkylin]**，等待用户在 VMware 窗口以物理键盘完成主机名、用户名及密码输入，然后继续检查 SATA 磁盘是否列出。**系统尚未写入虚拟磁盘；openKylin 内未做任何项目验证。**
