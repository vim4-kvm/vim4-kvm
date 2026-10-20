# 上板记录索引

每条记录一个文件，位于 `bringup/日期-主题.md`。先按日期或标签在本页找到条目，只打开需要的文件；
不要通读整个目录。标签：board、kernel、video、audio、usb、application、pikvm、uu、manager、deployment。

新记录：新建 `bringup/YYYY-MM-DD-英文短名.md`，首行 `# YYYY-MM-DD：标题`，并在本页对应日期下追加一行。

## 2026-10-20

- [One-KVM 接入 7.3 V4L2/Wave5](2026-10-20-onekvm-wave5.md) — application kernel video board
- [One-KVM 7.3 CPU 性能定位](2026-10-20-onekvm-performance.md) — application kernel video board
- [本地基准与 VDIN 直接 DMA](2026-10-20-direct-dma-benchmark.md) — application kernel video board
- [驱动原生基准、AVC profile 与采集内存](2026-10-20-driver-profile-memory.md) — kernel video board
- [实验 One-KVM 局域网登录入口](2026-10-20-edge-lan-gateway.md) — application manager board
- [7.3 One-KVM HID 接入](2026-10-20-edge-hid-integration.md) — application usb audio board

## 2026-10-19

- [7.3 edge 首次启动](2026-10-19-edge-firstboot.md) — kernel deployment board
- [7.3 CRG UDC 与最小 HID 实测](2026-10-19-crg-udc.md) — kernel usb board
- [7.3 CRG 真实 HID 与只读虚拟盘](2026-10-19-crg-composite.md) — kernel usb board
- [7.3 HDMI RX 资源与源端 5V 实测](2026-10-19-hdmirx-resources.md) — kernel video board
- [7.3 HDMI RX EDID 与源端 DDC 读回](2026-10-19-hdmirx-ddc.md) — kernel video usb board
- [7.3 HDMI RX 固定频率 PHY PLL 实测](2026-10-19-hdmirx-phy.md) — kernel video board
- [7.3 HDMI RX 1080p 完整视频帧](2026-10-19-hdmirx-frames.md) — kernel video board
- [7.3 HDMI V4L2 连续取帧](2026-10-19-hdmirx-v4l2.md) — kernel video board
- [7.3 HDMI 私有 DMA 环与 1080p60](2026-10-19-hdmirx-dma-ring.md) — kernel video board
- [7.3 HDMI DMA-buf 与软件 H.264](2026-10-19-hdmirx-dmabuf.md) — kernel video board
- [7.3 Wave521 硬编码与 4K60](2026-10-19-wave521-uhd.md) — kernel video board

## 2026-10-12

- [串口、OOWOW 与 Ubuntu 首次启动](2026-10-12-initial-serial-oowow-ubuntu.md) — board
- [自编内核与 `/lib` 事故](2026-10-12-custom-kernel-lib-symlink.md) — kernel
- [HDMI 输入采集](2026-10-12-hdmi-input-capture.md) — video
- [采集→编码链路与 USB gadget](2026-10-12-capture-encode-usb-gadget.md) — video usb
- [Mac USB HID 实测与描述符修复](2026-10-12-mac-hid-descriptor-fix.md) — usb
- [PD 开机初始化固化](2026-10-12-pd-boot-init.md) — usb
- [WebRTC 网页 KVM](2026-10-12-webrtc-web-kvm.md) — video
- [4K 视频输出](2026-10-12-4k-video-output.md) — video
- [自动风扇和 Wave521 提频](2026-10-12-auto-fan-wave521-clock.md) — kernel video
- [应用主线调整为 NanoKVM-Pro](2026-10-12-switch-to-nanokvm-pro.md) — application
- [NanoKVM-Pro 首阶段部署](2026-10-12-nanokvm-pro-first-deploy.md) — application
- [NanoKVM 原版视频控件、MJPEG 与 VDIN 缓冲区释放](2026-10-12-nanokvm-video-controls-mjpeg-vdin.md) — application video
- [NanoKVM 终端、脚本、网络唤醒与镜像管理](2026-10-12-nanokvm-terminal-scripts-wol-images.md) — application
- [NanoKVM HDMI 音频、Ubuntu 管理与应用更新](2026-10-12-nanokvm-hdmi-audio-ubuntu-update.md) — application audio
- [4K60 编码预算与局域网 RTP 分包](2026-10-12-4k60-encoder-budget-rtp.md) — video

## 2026-10-13

- [组件包部署闭环验证](2026-10-13-component-deploy-loop.md) — deployment
- [无人值守部署](2026-10-13-unattended-deploy.md) — deployment
- [保持画质的低延迟验证](2026-10-13-low-latency-quality.md) — video
- [键鼠输入延迟与行为](2026-10-13-input-latency-behavior.md) — usb
- [HDMI 静音修复及重新打包验证](2026-10-13-hdmi-mute-fix-repack.md) — audio
- [补齐原 NanoKVM 功能缺项](2026-10-13-nanokvm-missing-features.md) — application
- [HID 生命周期与部署可靠性](2026-10-13-hid-lifecycle-deploy-reliability.md) — usb kernel
- [采集分辨率菜单部署](2026-10-13-capture-resolution-menu.md) — application video
- [H.265 默认开放](2026-10-13-h265-default.md) — video
- [KVM 界面管理面板](2026-10-13-kvm-manager-panel.md) — manager
- [JetKVM 完整功能接入](2026-10-13-jetkvm-full-integration.md) — application
- [NanoKVM 正式部署与 JetKVM 往返切换](2026-10-13-nanokvm-deploy-jetkvm-switch.md) — application
- [NanoKVM 终端、镜像上传与可写 U 盘](2026-10-13-nanokvm-terminal-upload-writable-disk.md) — application usb
- [虚拟显示器退出后 HDMI 桌面未恢复](2026-10-13-virtual-display-hdmi-not-restored.md) — video

## 2026-10-14

- [HDR 输入映射到 SDR](2026-10-14-hdr-to-sdr.md) — video
- [HDR 审查修复与部署](2026-10-14-hdr-review-fix-deploy.md) — video
- [JetKVM 默认 EDID 改为 4K60 并部署](2026-10-14-jetkvm-default-edid-4k60.md) — application video
- [One-KVM VIM4 与三套界面切换](2026-10-14-onekvm-integration-three-ui.md) — application
- [One-KVM 输入状态与流设置](2026-10-14-onekvm-input-stream-settings.md) — application
- [One-KVM 虚拟盘初始化修复](2026-10-14-onekvm-virtual-disk-init.md) — application usb
- [One-KVM 本地扩展、看门狗与包更新](2026-10-14-onekvm-extensions-watchdog-update.md) — application
- [One-KVM HID 功能配置与 USB 组合](2026-10-14-onekvm-hid-usb-profiles.md) — application usb
- [4K60 高码率编码实验](2026-10-14-4k60-high-bitrate-experiment.md) — video
- [三套 KVM 自定义 60 Mbps 部署](2026-10-14-custom-60mbps-deploy.md) — video application
- [One-KVM 高码率连接偶发退化到 10fps](2026-10-14-onekvm-high-bitrate-10fps.md) — application video
- [Wave521 时钟与编码耗时](2026-10-14-wave521-clock-encode-time.md) — video
- [4K60 编码链路抖动与丢帧检查](2026-10-14-4k60-encode-jitter-drops.md) — video
- [WebRTC 视频分段卸载发送（.23）](2026-10-14-webrtc-segmentation-offload.md) — video
- [NanoKVM Wi-Fi 扫描空列表](2026-10-14-nanokvm-wifi-empty-scan.md) — application
- [提交工作区积累改动并部署 .24](2026-10-14-workspace-commit-deploy-24.md) — deployment
- [PiKVM VIM4 构建、集成和上板验证](2026-10-14-pikvm-build-integrate.md) — pikvm
- [PiKVM 切入检查补漏](2026-10-14-pikvm-switch-check-gaps.md) — pikvm
- [PiKVM HEVC、卡顿定位与全新 Ubuntu 组装](2026-10-14-pikvm-hevc-stutter-fresh-ubuntu.md) — pikvm deployment
- [PiKVM 卡顿：ICE 选路与实际收包接口](2026-10-14-pikvm-ice-path-receive-interface.md) — pikvm video

## 2026-10-15

- [PiKVM 隔夜降帧：采集线程与 CPU0 中断争用](2026-10-15-pikvm-overnight-fps-cpu0-irq.md) — pikvm video
- [部署 One-KVM UU 远程开发版本](2026-10-15-onekvm-uu-dev-deploy.md) — uu
- [UU 输出设置与缩放吞吐检查](2026-10-15-uu-output-scaling-throughput.md) — uu video
- [UU 网页输出控制、名称与系统身份](2026-10-15-uu-output-controls-identity.md) — uu
- [UU Mac 身份的键盘错码](2026-10-15-uu-mac-identity-keycodes.md) — uu usb
- [UU 滚轮方向默认值与手动覆盖](2026-10-15-uu-scroll-default-override.md) — uu usb
- [UU 连接初期体感延迟诊断](2026-10-15-uu-initial-latency.md) — uu
- [UU H.265 协商与封包修正](2026-10-15-uu-h265-negotiation-packetization.md) — uu video
- [UU H.265 出画面与周期性发送阻塞](2026-10-15-uu-h265-picture-send-stalls.md) — uu video

## 2026-10-14

- [MJPEG 单帧耗时与 NanoKVM 分辨率菜单](2026-10-14-mjpeg-frame-time-resolution-menu.md) — video application
- [MJPEG 硬件编码与 4K 运动画面吞吐](2026-10-14-mjpeg-hardware-4k-throughput.md) — video
- [JetKVM 码率控件部署](2026-10-14-jetkvm-bitrate-control.md) — application
- [NanoKVM 码率菜单样式修正](2026-10-14-nanokvm-bitrate-menu-style.md) — application
- [NanoKVM 码率滑块部署](2026-10-14-nanokvm-bitrate-slider.md) — application

## 2026-10-15

- [Screen Sharing 退出后物理桌面未恢复：同步取证](2026-10-15-screen-sharing-desktop-not-restored.md) — video
- [管理器 EDID 预设接口验证](2026-10-15-manager-edid-preset-api.md) — manager
- [部署 EDID 管理器，并保留 UU 虚拟屏故障现场](2026-10-15-edid-manager-deploy-uu-virtual-screen.md) — manager uu
- [UU 虚拟屏恢复故障定位](2026-10-15-uu-virtual-screen-recovery.md) — uu video
- [UU 与网页滚轮对照及采样干扰](2026-10-15-uu-web-scroll-sampling-interference.md) — uu usb
- [管理器侧边栏、风扇曲线调节与 EDID 界面](2026-10-15-manager-sidebar-fan-edid-ui.md) — manager
- [PiKVM H.265 菜单与 Direct 实板部署](2026-10-15-pikvm-h265-menu-direct.md) — pikvm
- [PiKVM Direct 周期停顿与绘制延迟](2026-10-15-pikvm-direct-stalls-paint-latency.md) — pikvm video
- [One-KVM UU 会话链路展示与鼠键反转核对](2026-10-15-onekvm-uu-session-path-input-swap.md) — uu
- [UU 会话卡片界面整理](2026-10-15-uu-session-card-ui.md) — uu
- [RTK EDID 音频与 One-KVM 运动后延迟](2026-10-15-rtk-edid-audio-onekvm-motion-latency.md) — audio application
- [跨 KVM 运动播放与积压恢复](2026-10-15-cross-kvm-motion-playout-backlog.md) — video
- [不同系统缓冲差异的原因调查](2026-10-15-buffering-difference-causes.md) — video
- [One-KVM 尽快播放策略对照](2026-10-15-onekvm-asap-playout-comparison.md) — video application
- [One-KVM 正式启用低延迟播放](2026-10-15-onekvm-low-latency-playout.md) — video application
- [PiKVM 尽快播放策略部署与对照](2026-10-15-pikvm-asap-playout.md) — pikvm video

## 2026-10-16

- [RTK UHD HDR 4K60 成为各应用内置 EDID](2026-10-16-rtk-uhd-hdr-builtin-edid.md) — video
- [CRG EP0 重复入队导致重启](2026-10-16-crg-ep0-double-queue-reboot.md) — kernel usb
- [共享虚拟介质状态与等待切换](2026-10-16-shared-media-state-wait-switch.md) — usb manager
- [管理器已有虚拟磁盘管理](2026-10-16-manager-virtual-disk.md) — usb manager
- [虚拟介质独立页面与跨应用介质状态](2026-10-16-virtual-media-page-cross-app.md) — usb manager
- [共享数据盘管理与四套 KVM 目录部署](2026-10-16-shared-data-disk-four-kvm.md) — usb manager
- [UU 信令与输入生命周期更新部署](2026-10-16-uu-signaling-input-lifecycle.md) — uu
- [4K60 8-bit YUV444 原始采集实测](2026-10-16-4k60-yuv444-raw-capture.md) — video
- [4:4:4 采集接口实现与生命周期修复](2026-10-16-yuv444-capture-interface-lifecycle.md) — video kernel
- [4:4:4 全帧处理优化至 4K60](2026-10-16-yuv444-full-frame-4k60.md) — video
- [4:4:4 编码能力核验与错误声明修复](2026-10-16-yuv444-encoder-capability.md) — video
- [PiKVM HDMI 音频周期性爆音](2026-10-16-pikvm-hdmi-audio-pops.md) — pikvm audio
- [数据盘交互修正与管理器动效](2026-10-16-data-disk-ui-motion.md) — manager
- [开发版本规则与管理器正式版部署](2026-10-16-development-release-versions.md) — manager deployment
- [四套 KVM 正式包部署](2026-10-16-kvm-release-deployment.md) — applications deployment

## 2026-10-17

- [One-KVM 设备端带声音录屏](2026-10-17-onekvm-device-recording.md) — application video audio

- [One-KVM HID 队列修复部署](2026-10-17-hid-queue.md) — usb uu application deployment
- [UU 视频诊断统计部署](2026-10-17-uu-video-metrics.md) — uu video application deployment

- [供电信息只读验证](2026-10-17-power-telemetry.md) — usb manager board

- [Tailscale 管理修复部署](2026-10-17-tailscale-management-fixes.md) — manager application deployment
- [U-Boot 取消启动风扇测试](2026-10-17-uboot-quiet-fan.md) — kernel deployment
- [管理器 Wi-Fi 网络管理与热点模式](2026-10-17-wifi-client-hotspot.md) — manager deployment

## 2026-10-18

- [One-KVM 原生指针默认样式](2026-10-18-onekvm-native-cursor.md) — application deployment
- [One-KVM UU 远程终端与卡片重设计](2026-10-18-onekvm-uu-terminal.md) — application uu usb deployment

- [NAS 网络存储与 NAS 文件夹 U 盘](2026-10-18-nas-storage-usb-disk.md) — manager usb kernel
- [One-KVM H.264 每秒停顿](2026-10-18-onekvm-h264-periodic-stutter.md) — application video
- [One-KVM MCP Fit 截图提前“超时”](2026-10-18-onekvm-snapshot-fit.md) — application video deployment
- [管理器统一登录与 8080 KVM 网关](2026-10-18-unified-auth-gateway.md) — manager application deployment
