# 2026-10-12：自编内核与 `/lib` 事故

内核构建/安装方法见 [kernel.md](../kernel.md)。

**事故**：第一次安装时用 `sudo tar xzf vim4kvm-*.tgz -C / --no-same-owner`。Ubuntu 24.04 的 `/lib` 是指向 `usr/lib` 的符号链接，tar 不带 `--keep-directory-symlink` 时会把它换成真实目录（只剩 `modules/5.15.137-vim4kvm`），`/lib/ld-linux-aarch64.so.1` 消失，所有动态链接程序（ssh、sudo、reboot）都无法运行。

- 串口上已登录的 bash 只能用内建命令；`/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1 --library-path /usr/lib/aarch64-linux-gnu /usr/bin/xxx` 可以跑普通程序，但 setuid 失效，sudo 不可用；logind 重启需要 polkit 认证；串口 break + SysRq 无效
- 恢复：用户按 FUNCTION + RESET 进 OOWOW（root busybox），`mount /dev/mmcblk0p2 /mnt/r`，把 `lib/modules/5.15.137-vim4kvm` 移到 `usr/lib/modules/`，`rmdir lib/modules lib && ln -s usr/lib lib`，重启
- 现在用 `tools/kernel-install.sh`，解包后会检查 `/lib` 仍是符号链接

**另一个坑**：`ssh vim4 'echo khadas | sudo -S tee file <<EOF ...'` 在 sudo 凭据已缓存时不读密码，tee 把 "khadas" 写进了 `extlinux.conf`（重启前发现并修复）。写板上配置文件改用 scp 到 /tmp 再 `sudo cp`。

新内核验证：

- `5.15.137-vim4kvm` 启动正常，无失败服务；`Retrieving file: /dtb/amlogic/kvim4n.dtb.overlay.env` 正常读取
- 风扇：`cat /sys/class/fan/temp` → `level0:60 level1:80 level2:100`，mode auto
- `modprobe vfm_cap` → `/dev/video0`（`VFM Capture Tee`）
