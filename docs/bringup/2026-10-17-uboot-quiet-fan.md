# 2026-10-17：U-Boot 取消启动风扇测试

结论：删除 U-Boot 的 MCU 风扇测试写入后，实板重启成功，用户在板旁确认原来的
启动加速声消失。Linux 自动温控正常接管。本轮验证系统重启，未做拔电冷启动。

## 源码与构建

- Fork：[vim4-kvm/u-boot](https://github.com/vim4-kvm/u-boot/tree/vim4-kvm-2019.01)。
- 基线：Khadas `khadas-vims-u-boot-2019.01-v1.7.5-release`，
  `9834e1b545e3a00ac8d2d49821244acc5b03b3a4`。
- 修改：`b60ff51ece0fb05456261b1aabb043db6bd923d5`，删除
  `board/khadas/kvim4/kvim4.c` 的 `i2c dev 6` / `i2c mw 0x18 0x96 1`。
- VM `vim4-build:~/src/u-boot`；GCC 12、binutils 2.42；主程序及 BL33Z 构建通过。
  复现命令与重打包工具在 fork 的 VIM4.md、tools/vim4-repack.py。
- 现代编译器需要兼容上游 array-bounds、misleading-indentation 告警；链接器需
  允许上游 RWX LOAD segment。没有为了编译修改无关驱动。

原厂包 `linux-u-boot-vim4-vendor 1.7.5-2019.01` 中 SD/eMMC 镜像 SHA256：
`95547c4cd3624fab11ff118668bd15d1497aef8c8339049c714566bb63adadee`。
工具只接受该输入，先用 vendor acpu-imagetool 重打包原始载荷并逐字节对照全部
固件 blob，再替换压缩的 BL33。保留前级引导、DDR、BL30，BL31/32/40 与基线源码
中的签名固件一致。输出 SHA256：
`4166c07fe6efae2d50398effc61a66c1cd3894f754ff93d6450758390d272f3a`。

## 上板与回退

上板前没有发现串口或硬件测试进程占用，无挂载的虚拟介质。板子使用
`boot_source=emmc partition_type=generic`，p1 从 16 MiB 开始。
读取前 16 MiB，确认现有引导内容与原厂包一致（跳过 sector 0 的分区表部分）。
备份分别保存在本机 `logs/uboot-fan/emmc-prefix-before.bin` 和板上
`/var/backups/vim4-uboot-before-b60ff51.bin`，SHA256 为
`e90fffee23325eb99a87a4e0d90dfa9c1e412e4ba3c8b0d8e0291d3eba967606`。

只写入 `/dev/mmcblk0` 的 device FIP 区间 `[0xa4200, 3248640)`；fsync 后读回
整个 16 MiB，验证目标区与新镜像一致，其余字节与备份一致。未改分区表、文件系统、
eMMC boot0/boot1 或 SPI OOWOW。随后 sync、systemctl reboot，并记录串口。

需要回退时，在同一布局下从备份恢复该区间：offset=672256，length=2576384；
写后 fsync、读回比较，再重启。Ubuntu 无法启动时由 SPI OOWOW 恢复。
不要把整个旧 16 MiB 无条件覆盖到已经改变分区布局的设备上。

本次为直接引导区实验，`/usr/lib/u-boot` 仍是原厂包内容；以后更新原厂引导包
可能覆盖修改。尚未纳入 deb 发布或候选整机镜像。

## 验证结果与边界

- 串口确认 `U-Boot 2019.01-00001-gb60ff51ece`，正常进入 `5.15.137-vim4kvm`。
- 用户现场确认此次重启没有原来的启动加速声。
- 自动温控：enable=1、mode=1，温度约 51–52°C，控制输出由 27% 回落到 22%；
  阈值保持 60/80/100°C。speed 是控制百分比，非实测 RPM。
- board.py check 第一次因应用仍在启动、8080 未监听失败；稍后重试通过：
  tvserver、HDMI、gadget、manager active，UDC configured，无失败 systemd 单元，
  当前 One-KVM 运行，8080 HTTP 可访问。内核命令行与重启前一致。
- 日志有 DRM vblank 时间戳及等待告警；没有持久 journal 可用于前一次启动对照，
  未证明它们由本次修改引起或解决。未执行端到端视频、音频、HID 回归。

本机证据在 `logs/uboot-fan/`：quiet-boot-uart.log、before-check.log、
after-check.log（首次未就绪）、after-check-ready.log、after-state.log，以及镜像与备份。
