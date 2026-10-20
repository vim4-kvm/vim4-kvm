# 2026-10-19：7.3 HDMI RX 1080p 完整视频帧

结论：7.3 实验内核已取得真实 1920×1080、RGB24 视频帧，单帧 6,220,800 字节。
Mac 运动测试图的上、中、下三处帧号一致，重复采集帧号推进。此为按需 debugfs
快照，尚未提供 V4L2、持续流、4K、输入音频或编码器接入；5.15 仍为默认启动项。

## 源码与范围

Linux 分支 `vim4-kvm-7.3`：

- `1f489ef6464ea`：COR、VDIN 实验绑定及 VPU 时钟编号。
- `4f4e16a761425`：VPU、VAPB、CLKB、VDIN 测量时钟。
- `80e9d8f0e4f352904f5fc0936f9d23b2daab308b`：接收核心、PCS 复位及有界 DMA 快照。
- `37d7198db3daeec68eb8ca264724f614586c0ca3`：核心启动顺序、卸载恢复与源端重连等待。
  最终 tree `9debf52a72383f18a47bd95c2cdc33a834bd7c89`。

源码位于 VM `vim4-build` 的 `/home/deepdream/src/linux-7.3`；本仓库保存配置、版本锁、
检查工具与测试记录。入口仍在 `drivers/media/platform/amlogic/t7-hdmirx/`。
普通 VIM4 DTB 不启用实验采集。专用 `amlogic-t7-a311d2-khadas-vim4-hdmirx-test.dtb`
禁用 DRM VPU 节点，由 VDIN 实验独占 `0xff000000/0x40000` 寄存器窗口。
这不是可上游提交的最终共享 VPU/V4L2 架构。

RX 新增 `cor` 窗口 `0xfe3a0000/0x8000`，必须按字节访问；TOP 寄存器仍按 32 位访问。
`core_test=1` 要求 `phy_test=1` 及固定 148.5 MHz、无 CTA 扩展的数字 EDID。
核心访问先经固件 SMC `0x8200008c/0xa2/0x1f` 解锁，检查返回值与寄存器读回。
准备接收核心寄存器，PHY 锁定后最后脉冲 TOP PCS 复位位 13、7。
实际启动先准备 PHY 寄存器，再解除 COR 隔离／启用内部时钟，之后才等待 cable clock 和 PLL；
不能等 PLL 锁定后才解除 COR 隔离。源端 EDID 重连的等待上限由约 3 秒扩至约 10 秒。
卸载时恢复启动前的 COR 隔离与内部时钟状态，再由原有流程释放 PHY、TOP、时钟及电源。

VDIN0 使用 SPI 213 写帧完成中断；固件 mempd SMC `0x82000093/60/1` 打开行缓存。
时钟约为 VPU/CLKB 400 MHz、VAPB 250 MHz、measure 50 MHz。
32 位 coherent DMA 地址与 5760 字节 stride 均按 16 字节单位写入硬件。
只接受 RGB、8 位、逐行 1920×1080、2200×1125、59..61 Hz 的两次稳定采样，采集前后均检查。

打开 `frame` 时丢弃第一张可能不完整的帧，第二次完成中断中停止写请求，再检查写完成。
复制到每个 fd 独立的不可变 CPU 缓冲区，读完或关闭后释放。
超时无法证明 DMA 已停止时，保留 DMA 内存、时钟及模块引用至重启，后续读取返回错误；
不要强制卸载。核心实验模式隐藏 RX/VDIN 的 sysfs bind/unbind，避免绕过故障保留。
既有 DDC/PHY 模式仍保留原有资源检查入口。

## 关键失败与修正

| 现象 | 本次核实结果与修正 |
|---|---|
| PHY 锁定但 COR 读回为 0、没有尺寸 | 缺少安全 TOP 配置；SMC 解锁后 TMDS 对齐，测得 1080p60 |
| VDIN 只有行计数、有效像素为 0 | CLKB 未接入；补齐后测得 1920 像素，保留 LFIFO 未知高位 |
| 写完成为 1，但中断计数为 0 | TOP_DOUBLE_CTRL 位 20 置 1 才放行写完成中断；同时脉冲清除已锁存的中断 |
| 已收到两次中断，收尾却超时 | completion 的计数已被 wait 消耗；以已处理帧数和硬件写完成判断，补齐真实语义回归 |
| 图案随行逐渐偏移、不能正确结束帧 | 写 MIF 必须置 EOL_SEL 位 27，每行重新结束打包 |
| 早期调试图帧号可解码，但一个颜色分量严重损坏 | 新启动并修正 EOL 后首帧已经清晰；保留 PCS 复位为初始化步骤，未单独证明颜色问题由缺少该复位引起 |
| 完整卸载 RX 后再次加载，cable clock 接近 0 | 核心仍被隔离却先等输入时钟；调整初始化先后顺序，并恢复卸载前状态 |

失败试验均保留日志，没有将空 raw 文件或花屏当作成功，没有强制释放不确定状态的 DMA。
一次 RX 初次探测失败后 VDIN 仍绑定，触发 device-link WARN；已增加 supplier bound 检查，
失败时延后探测。宽寄存器访问与按字节访问不可混用。

## 复现取帧

只在独占的实验启动项中操作；屏蔽生产采集、编码、KVM、PD、音频和 gadget 服务，
禁止自动加载 `crg_udc,t7_hdmirx,t7_vdin_test`。使用同次构建的 Image、DTB 和完整模块集。
保留串口及定时返回默认内核的 timer。不能直接在 5.15 中加载这些模块。

板端手动加载：

```sh
sudo modprobe t7-hdmirx phy_test=1 core_test=1 edid_firmware=vim4-hdmirx-ddc-test/edid-0.bin
sudo modprobe t7-vdin-test
sudo cat /sys/kernel/debug/fe398000.hdmi-receiver/status
sudo cat /sys/kernel/debug/ff000000.video-capture/status
```

Mac 测试源使用现有工具；等待显示名称与接收时序稳定后开始，EDID 切换期间可能需重载 RX：

```sh
swiftc tools/latency-source.swift -o build/kernel-edge/hdmirx-frame-source
VIM4_HDMI_DISPLAY=VIM4-DDC-A build/kernel-edge/hdmirx-frame-source 90 --motion --verify-coherence
```

源图中文字 `VIM4 4K60` 是该工具原有固定标签；本实验实际分辨率为 1920×1080，不能据此声称 4K。
另一个终端读取两次，确认 SSH 命令均成功，再离线校验：

```sh
ssh vim4 'sudo -n cat /sys/kernel/debug/ff000000.video-capture/frame' > build/kernel-edge/frame-a.raw
ssh vim4 'sudo -n cat /sys/kernel/debug/ff000000.video-capture/frame' > build/kernel-edge/frame-b.raw
python3 tools/hdmirx-frame-check.py build/kernel-edge/frame-a.raw build/kernel-edge/frame-b.raw
```

检查器验证文件长度、三处 magic/checksum/帧号、黑白三通道一致，以及后续帧号推进。
它不测帧率、延迟或逐像素保真。原始 RGB24 可用图像工具按 1920×1080 打开。

## 验证与证据

`hdmirx4` 的首次完整驱动快照帧号 102，黑白三通道也正确；手动核实 PCS 复位后帧号 3232，图像清晰。
随后的 5 张运动快照帧号为 6694、6716、6740、6764、6789，三处标记一致，
`tools/hdmirx-frame-check.py` 校验通过。此为按需读取，没有声称 60 fps 连续采集。

日志与原始帧位于主仓库忽略目录 `logs/kernel-edge/`、`build/kernel-edge/`。
关键入口：`hdmirx-frame4-pcs-trial.log`、`hdmirx-frame-repeat-verified.jsonl`、
`frame4-pcs.png`、`hdmirx-frame-final-regressions.log`、`hdmirx-frame-final-checkpatch.log`。

最终独立版本为 `7.3.0-rc7-vim4kvm-hdmirx5+`，输出目录
`~/build/kernel-edge-frame5-test`。完整 Image/dtbs/modules 构建通过；绑定／专用 DTB、
strict checkpatch、四组实际 C fake-MMIO 回归通过。主仓库 89 项离线测试通过，4 项跳过。
新增离线取帧回归覆盖短文件、撕裂、单通道损坏、checksum、旧帧及计数回绕。

最终上板通过：

- RX 完整卸载／重载三轮，每轮约 1.1 秒恢复 PLL、TMDS 对齐与 1080p 时序。
- 随后三轮 VDIN 加载／采集／卸载，共 6 帧，帧号 87、93、121、127、156、162。
  每帧 6,220,800 字节，三处 ID/checksum 及黑白三通道均一致，帧号推进。
- 第一个 fd 跨第二次采集仍读出旧快照；持有 fd 时模块卸载被拒绝，关闭后正常卸载。
  每轮 DMA 写请求已停止，VDIN 五项时钟的 prepare/enable 引用均恢复为 0。
- 另做三轮原有资源模式回归：旧 status fd 在卸载后拒绝读取，RX 六项时钟引用归零。
  最终内核 tainted=0。没有声称实现任意格式或断线自动恢复。

对应日志：`hdmirx-frame5-final-core-reload.log`、`hdmirx-frame5-confirm-cycles.log`、
`hdmirx-frame5-confirm-frames.jsonl`、`hdmirx-frame5-resource-regression.log`。
最终 raw 与 PNG 位于 `build/kernel-edge/frame5-final/`。
早期重载脚本用 `modprobe -r` 连带卸载 RX，导致下一次依赖自动按无参数模式加载；
独立 VDIN 重载试验改用 `rmmod t7_vdin_test`，不将脚本问题混作硬件验证结果。

| 最终产物 | SHA-256 |
|---|---|
| Image | `77e3b53c1528cfb06dbec0750b7526e736823e021f7fcf3060e0c02f7050e2be` |
| 加本板 MAC 的测试 DTB | `25189da7420576c73ceacec6301f38bfd6e1a9f5843efa4048bd7c3695df8e37` |
| 最终完整模块归档 | `36bc6c0f33f06db6e44a43e23721434dc597cb7a04f6e6a78ee7bcf91b29eaf1` |

最后的重载修正只重新编译接收模块；完整 make 后对 Image 做逐字节比较，确认仍与
首个 hdmirx5 Image 相同。重新暂存完整模块集，并核对板上 2332 个模块文件与最终暂存一致，
不混用另一个 Image 的分离 BTF。构建／部署清单在 `build/kernel-edge/frame5-deploy/`。

测试结束已正常回到 `5.15.137-vim4kvm`，SSH／以太网恢复，USB gadget 为 configured，
tvserver、HDMI 与 gadget 服务均 active，没有失败的 systemd 单元。
启动配置与安装前备份逐字节一致，5.15 仍为默认项；未改 BL31/U-Boot 或分区布局。
此恢复检查不等于重新验收全部生产应用。证据见 `hdmirx-frame5-final-restored.log`、
`hdmirx-frame5-installed-match.log` 和返回默认内核的串口日志。

## 后续

下一阶段为 V4L2/videobuf2 连续采集和多缓冲 DMA：处理丢帧、输入热插拔及格式变化，
明确共享 VPU/时钟/电源所有权，再接编码器和应用。4K60、HDMI 输入音频、HDCP、FRL、
完整 PHY 自动调谐及 suspend/resume 均未在本次完成。
