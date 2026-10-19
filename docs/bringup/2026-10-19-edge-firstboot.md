# 2026-10-19：7.3 edge 首次启动

结论：`7.3.0-rc7-vim4kvm-edge+` 已在当前新款 VIM4 上启动到 Ubuntu，
eMMC 根分区、八核 CPU、有线网络、SSH 和温度读取可用。
这是基础启动验证，不是完整 KVM 或驱动稳定性验证。

## 固定版本与引导固件

- Linux：`9c8bb58158d810a38ff37dec7c7d18cb131a3b52`。
- U-Boot：`4317387a6a58f4d42186cbadc24cd3cc52675bc3`，
  VM `~/src/u-boot-edge`，分支 `vim4-kvm-2019.01-edge`，尚未推送。
- 固件基于现有安静启动版本，增加主线 reserved-memory 检查修复、PD 修复和 BL31 更新。
- tools/vim4-repack.py 增加显式 `--update-bl31`；默认模式拒绝不同 BL31 的实测通过。
  原厂 round-trip、逐固件载荷对照和完整文件差异范围检查通过。
- 候选镜像 SHA-256：`be2a07fd0475deabc950af2e05b843cf8d1373844ed502fbe7af562c888ad0f5`。
  大小 3,248,640 字节；差异仅限 device FIP 元数据、BL31 和 BL33。

用户确认可在板旁按 FUNCTION+RESET 进入 SPI OOWOW。检查串口无其他进程占用、
无挂载的虚拟介质及明显硬件测试进程后，读取 eMMC 前 16 MiB。
备份 SHA-256：`5842f38902b0b76a173bf8e67d287985730f944b29a28497e21620e4a55d4796`。
本机备份 `build/kernel-edge/boot-backup/emmc-prefix-16MiB.bin`，板上为
`/var/backups/vim4-before-edge-fip.bin`。

核对 p1 起始扇区仍为 32768，仅写 device FIP `[672256, 3248640)`，fsync 后读取
完整 16 MiB 与期望结果逐字节比较；其余引导区、分区表和文件系统保持不变。
SPI、eMMC boot0/boot1 未写入。先重启 5.15，串口确认 BL31 `v1.3.2 ... 2dd964006`，
board.py check 在应用启动完成后通过。第一次检查因 8081 尚未监听失败，未当作通过。

需要固件回退时只能在核实同一布局及备份校验和后恢复备份中的上述 FIP 区间，
再 fsync 并读回验证；不能无条件覆盖完整 16 MiB。Ubuntu 无法运行时用 SPI OOWOW。

## 测试启动方式

模块安装到独立 `/usr/lib/modules/7.3.0-rc7-vim4kvm-edge+`，删除构建目录链接并 depmod。
`/boot/edge/Image` 与基础产物校验一致；DTB 在原始产物中加入本板以太网 MAC，
SHA-256 为 `bf1e90e6f71cbb61cc751b5975af2f4ecca5677c0d6c2d21758f563ade6e8215`。
该 DTB 仅适用于本板，不能把其 MAC 用作通用镜像默认值。

备份 extlinux.conf 到 `/var/backups/extlinux-before-edge.conf`，增加第三项 EdgeTest，
显式使用 `/edge/vim4.dtb`。保持 Default 和 Stock 及默认选择不变，串口只选择一次第三项。
根参数为本板 `root=PARTUUID=bcb80000-02 rootwait rw rootfstype=ext4 rootflags=data=ordered`，
串口 `console=ttyS0,921600n8 earlycon=meson,0xfe078000`，`panic=20`。
本次依靠内建 eMMC/ext4 驱动直接挂根，无 initramfs；安装后 /boot 约剩 15 MiB。

使用启动参数 systemd.mask 临时屏蔽 tvserver、HDMI/gadget、manager、One-KVM、
NanoKVM、JetKVM、PiKVM 和 audioserver。没有永久禁用这些服务。
测试结束通过默认项回到 5.15；新固件与非默认 EdgeTest 入口保留用于后续开发。
回退后 SSH 确认 `5.15.137-vim4kvm`，board.py check 通过，USB gadget 为 configured，
systemd 无失败服务。这是服务与设备状态检查，未重新执行音视频、键鼠端到端回归。

## 观察与验证边界

- Linux 版本经串口和 SSH 双重确认，CPU online 为 0–7，MemTotal 约 7.69 GiB。
- eMMC HS200，ext4 ordered 挂载；临时文件 1 MiB 写入、fsync、读回哈希校验通过，随后删除。
- RTL8211F 协商 1 Gbps 全双工，原 MAC 和 DHCP 地址 192.168.50.210，SSH 可用；未测吞吐。
- 六个温区读取约 44–47°C，khadas-mcu-fan cooling device 已注册、当时状态 0；未做热负载测试。
- CPU 调频表可见 A73 最高 2.208 GHz、A53 最高 2.016 GHz；未验证负载下频率和稳定性。
- Mali-G52 被 Panfrost 识别，`/dev/dri/renderD128` 已注册。日志缺 mali regulator，
  后续使用 dummy regulator 并完成初始化；不能将该条错误直接当作探测失败，未做渲染验证。
- HDMI 输出 DRM 与 KHADAS-VIM4 ALSA 声卡已注册；当前未接显示器，未做显示/声音验证。
- Wi-Fi 缺少 `brcm/brcmfmac43752-sdio.bin`，后续 HT clock timeout，没有无线网口。
- SCMI 有 malformed reply 日志并启用 clock-rates quirk，需要进一步审查，不能声称固件完全兼容。
- 旧根文件系统的 binder、bluetooth-khadas、rc-local、tee-supplicant、video-firmware-preload
  五个厂商服务失败，需要新内核专用系统集成。
- `/sys/class/udc` 为空，没有 HDMI 输入采集设备；现有 KVM 功能仍不可用。

日志位于主仓库 `logs/kernel-edge/`：firmware-5.15-uart.log、firmware-5.15-ready.log、
edge-firstboot-uart.log、edge-runtime-state.log、edge-full-state.log、return-5.15-uart.log、
return-5.15-check.log。主仓库离线测试共 83 项，成功，跳过 4 项。
固件候选、verification.json、备份和增量 Git bundle 在 `build/kernel-edge/`，均不入 Git。
