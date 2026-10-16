# openKylin 验证记录

2026-10-16 的真实 48×2 全量评测见 [独立记录](validation/openkylin-real-20261016.md)。本页以下内容保留 2026-10-15 的 CLI/synthetic 初验历史。

## 已验证

- 已安装桌面：openKylin 3.0 (huanghe)，aarch64，Linux 7.0.0-3-generic，Python 3.12.2。
- 项目：MemoryScope-OK 0.3.0；客体路径 `/home/openkylin/msok-validation-20261015-1840/MemoryScope-OK`。
- 用户目录 `.venv` editable 安装成功；CLI version/help、48 条数据校验、单例配置预检通过。
- `pytest -q`：**85 passed in 1.28s**。
- synthetic 单例：`20261015T184021223058Z-8ea846f47945`，completed、1 pass。其余五维和 Overall 保持 null。
- 离线报告及 `--reuse` 成功，生成 JSON / CSV / Markdown / PNG。文件大小检查通过；未将 synthetic 称为真实成绩。

完整命令与 stdout/stderr：[成功日志](validation/openkylin-20261015.log)。原始 events、results、metadata 和报告位于客体项目的 `runs/<run_id>/`。本轮没有调用真实 Agent API，宿主机 `.env` 未传入客体。

源码传输归档 SHA256：`e38515acbec0a74430f0b5c94899fed72d6c279060e410c62f2d1dd517274991`，客体读回一致。归档采用文件白名单，没有 `.git`、`.env`、旧运行结果或虚拟环境。运行内 metadata 记录源码/数据/配置摘要；归档无 Git 历史，不能提供该客体 checkout 的 commit ID。临时传输仅监听 VMware 网段 `172.16.63.1:8765`，验证后已关闭。

## ensurepip 缺失的处理

系统的 `python3 -m venv` 实际失败，原因是缺少 ensurepip，见[首次失败日志](validation/openkylin-20261015-venv-initial.log)。保持系统部署与安全设置，改用 [PyPA 官方 virtualenv zipapp](https://bootstrap.pypa.io/virtualenv.pyz) 在用户目录创建环境。下面是复现方式；本轮工具由宿主机从该官方地址下载后经 VMware 网段传入。

```bash
cd /path/to/MemoryScope-OK
curl -fL https://bootstrap.pypa.io/virtualenv.pyz -o /tmp/virtualenv.pyz
python3 /tmp/virtualenv.pyz .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/memoryscope --help
.venv/bin/memoryscope validate datasets/golden
.venv/bin/pytest -q
.venv/bin/memoryscope run configs/demo-smoke.yaml --json
# 使用上条 JSON 返回的 data.run_dir
.venv/bin/memoryscope report <run_dir> --json
```

首次创建的不可用 `.venv` 已保留为 `.venv-incomplete`。继续使用已有环境，无需再次创建。若使用安装脚本，应先创建可用 `.venv`，再用 `SKIP_SYSTEM=1 SKIP_AGENTS=1 bash scripts/setup_openkylin.sh` 避开系统包管理；该脚本整体本轮未在客体执行，不能记为通过。

## 后续与边界

两个真实 Agent 的完整 Linux 评测已于 2026-10-16 完成，不再是待办。GUI 由 Claude 接续 [CLI/GUI 契约](CLI_GUI_HANDOFF.md)；GUI 联调、.deb 安装、一键脚本整体、Python 3.10 和录屏仍未完成。原桌面 ISO 的启动兼容参数及升级限制见 [系统部署记录](openkylin-deployment.md)。
