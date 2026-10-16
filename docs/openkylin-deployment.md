# openKylin 桌面环境部署记录

日期：2026-10-15。此记录说明操作系统安装与启动。CLI 的后续初验已完成，见 [项目验证记录](openkylin-validation.md)；真实 Agent 的 Linux 完整评测仍待完成。

## 已验证环境

- VMware Fusion 26.0.0，Apple Silicon，ARM64 / UEFI。
- 虚拟机：`~/Virtual Machines.localized/openKylin-Desktop-3.0-ARM64.vmwarevm`。
- 4 vCPU、8 GB RAM、80 GB 容量上限的 SATA 虚拟盘、NAT；当前只运行这一台虚拟机。
- 官方桌面 ISO：`openKylin-Desktop-V3.0-20260918-arm64.iso`，7,063,267,328 字节。
- MD5：`58650dfbe8c272167f6f2f59eb04eb8a`，与[官方下载页](https://www.openkylin.top/downloads/)一致（Desktop ARM，downloadId 132）。[官方直链](https://cdimage.openkylin.top/3.0/openKylin-Desktop-V3.0-20260918-arm64.iso)。
- 原版镜像保存在 `~/Downloads/`。图形安装器提示“安装完成”；安装光盘随后已断开。
- 主机名 `openkylin-desktop`，用户名 `openkylin`，密码由用户自行设置，未记录到项目。
- 第一次硬盘启动及随后一次 `vmrun reset ... soft` 正常重启，均观察到 UKUI 桌面。vmware.log 两次显示 `EFI boot: openkylin`，串口显示同一 machineid、不同 bootid 和新主机名。

## 启动兼容处理

原版桌面内核 `7.0.0-3-generic` 与此前 Server 的 `7.0.0-2-generic` 一样，在 VMware 中触发 i8042_init / logic_inb 内核异常。安装介质副本的 GRUB 配置加入 `initcall_blacklist=i8042_init`，启用 VMware USB 键盘后成功进入 UKUI Live 桌面。安装成功后临时副本已删除，原版 ISO 未修改。

桌面系统使用 OSTree；不能直接把物理根分区下的 `/etc` 当作已部署系统的完整 `/etc`。实际分区检查为：sda1 EFI 512 MB、sda2 /boot 2 GB、sda3 sysroot 40.9 GB、sda4 /data 27.3 GB、sda5 swap 9.3 GB。以实测 fstab / lsblk 为准，安装确认页的预览不是最终分区证据。

从 Live 用 VMware Tools 读取与维护已安装分区，先只读检查，随后备份配置并写入参数。自带 `ostree admin instutil set-kargs --merge --append=...` 在 Live 中调用 grub-mkconfig 失败；有效 loader 指针仍为 loader.0。故对有效 `boot/loader.0/grub.cfg`、其两份 entries 和两个部署的 `etc/default/grub` 保存备份后加入：

```text
initcall_blacklist=i8042_init console=ttyS0,115200 console=tty0
```

配置读回一致，`grub-script-check` 退出 0，sync 与分区卸载成功，之后两次硬盘启动均成功。将来升级内核或系统部署后仍需检查参数保留与启动，不能据此宣称所有后续版本都兼容。

本地诊断文件位于 `/private/tmp/msok-boot-fixed.txt`、`/private/tmp/msok-post-kargs.txt`、`/private/tmp/openkylin-desktop-serial.log`；原始记录含最早失败启动，不能仅看到日志中的旧 panic 就认定当前启动失败。日志为临时文件，长期交接以本记录和实际复验为准。

## 资源与清理

旧 Server 已正常关机并移入 `~/.Trash/openKylin-Server-3.0-ARM64-20261015.vmwarevm`，CPU/内存资源已释放，恢复副本仍占约 9.7 GB 磁盘；未清空废纸篓。桌面磁盘 80 GB 是上限，安装期间实际占用约 26 GB。临时桌面安装副本（约 6.6 GB）已清理，官方 ISO 保留在下载目录。实际物理磁盘回收量会受 APFS 共享块等因素影响，不能把逻辑文件大小当作已释放空间。

## 后续验证

已在已安装的系统内检查 OS / kernel / Python，并完成用户虚拟环境安装、CLI 帮助、validate、synthetic 单例、报告和 85 项测试，见 `docs/openkylin-validation.md`。真实 Agent 完整评测与图形界面验收需分别记录，macOS 旧结果不能代替。
