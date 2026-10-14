# 演示录屏脚本（3–5 分钟，openKylin 3.0 文字控制台）

**录制方式**：在 Mac 上用 macOS 自带录屏（Shift+Command+5，选“录制所选部分”）框住 VMware Fusion 的 openKylin 窗口。控制台无法粘贴，命令需要手打，所以都尽量简短。雷达图在 Mac 上打开展示（虚拟机里没有图形界面也不影响）。

**录前准备**（不录）：
- 完整评测已经在虚拟机里跑完（`bash /mnt/msok/vm_run.sh`），结果目录已复制到共享文件夹 `vm-results/`；
- 在虚拟机里执行 `cd ~/MemoryScope-OK && export PATH=$HOME/.local/bin:$PATH && . .venv/bin/activate`，再执行 `clear`；
- 记下完整评测的运行目录名，下文用 `<RUN>` 表示；可以先执行 `R=runs/<RUN>`，录制时直接用 `$R`；
- 确认屏幕上不会出现 `.env` 的内容。

| 时间 | 画面 | 输入 | 旁白要点 |
| --- | --- | --- | --- |
| 0:00–0:20 | 虚拟机 | `head -4 /etc/os-release; uname -m` | 运行环境是 openKylin 3.0（huanghe），aarch64 |
| 0:20–0:45 | 虚拟机 | `memoryscope --help`，然后 `memoryscope list-agents` | 一键 CLI；demo 标为 synthetic，codex 和 dsh 是真实 Agent，两者都用 deepseek-flash |
| 0:45–1:30 | 虚拟机 | `python scripts/dataset_table.py \| less -S`，翻到 `dynamic_update-007` 和 `boundary-008`，按 q 退出 | 用例由多个步骤组成：先写入，再更正或要求删除，换新会话后检查；`check_memory` 直接看存储里旧值和密码有没有被删掉 |
| 1:30–2:30 | 虚拟机 | `memoryscope validate datasets/golden`；`pytest -q`；`memoryscope run configs/smoke.yaml` | 48 条数据通过校验，64 项测试通过；现场让两个 Agent 跨会话作答，约 1 分钟 |
| 2:30–3:10 | 虚拟机 | `grep -c session_reset runs/*/events.jsonl \| tail -1`；`grep evaluation runs/<smoke>/events.jsonl \| head -1 \| cut -c1-400` | 证据：会话确实被重置过；每条评分都带逐词理由和证据序号 |
| 3:10–4:00 | 虚拟机 | `less $R/report/report.md` | 完整 48 条的六维得分、状态分布、未通过项及理由 |
| 4:00–4:20 | Mac | 在访达打开共享文件夹 `MemoryScope-OK-vmshare/vm-results/<RUN>/report/radar.png` | 两个 Agent 的雷达图；这张图是在 openKylin 上生成的 |
| 4:20–4:50 | 虚拟机 | `memoryscope rescore $R` | 评分规则升级后，离线重评已保存的证据，不需要重跑 Agent |
| 4:50–5:00 | 虚拟机 | — | 结束语：数据集可扩展，评分可解释，隔离不改动用户环境，在 openKylin 上一键运行 |

**注意**：
- 不要执行 `cat .env`、`env`、`printenv`，也不要 `echo $DEEPSEEK_API_KEY`。
- 现场评测只跑 `configs/smoke.yaml`；完整 48 条的结果用事先跑好的运行目录展示。
- 打错命令不必重录，旁白继续即可。
