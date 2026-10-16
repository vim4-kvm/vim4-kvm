# 2026-10-14：One-KVM 输入状态与流设置

One-KVM `c4364572`，打包入口 `eac6414`，正式组件版本
`2.5.1+vim4.20261014.5`。仅升级板上的 vim4-onekvm；manager 保留 `.4`，
NanoKVM、JetKVM 及其已有部署改动未覆盖。包使用固定 ARM64 Ubuntu builder，
One-KVM 重新编译，其余六项复用 `.4` 中源码版本不变的产物；sources.json 记录此关系。

输入状态接口原先把 `/dev/video_cap` 当作普通 V4L2 节点拒绝，改为直接读取 HDMI RX
sysfs，观看期间可返回 3840×2160、59.98/59.99 Hz、NV21。NV21 表示采集输出格式。
输出设置与源信号独立，支持原尺寸/720p/1080p/2160p 上限、帧率上限、MJPEG 质量、
H.264/H.265 码率、EDID 预设和共享 HDR 曲线。

首次 GE2D 连续切编码测试暴露厂商 DMA 分配器重复关闭 fd，进程报
`safe_close ... EBADF`。私有分配器将 fd 仅交给 GstDmaBufMemory 管理，
随应用部署且不替换系统库；另提供 gfx2d 所需的同步入口，使用独立 GStreamer 注册缓存。
修复后完整切换过程中 `NRestarts=0`。

验证：

- 前端构建、557 项 Rust 单元测试、4 项特权助手测试、42 项工作区测试通过；
  私有分配器的 100 次缓冲区引用/释放生命周期测试通过。
- 七组件包的校验和、ARM64 ELF、动态依赖、sudoers、配置保留与损坏文件拒绝检查通过。
  APT 预检只升级 One-KVM，安装后 `dpkg --audit` 无输出。
- Chrome 实际解码：H.264 1920×1080 29.97 fps，H.265 1280×720 14.98 fps，
  恢复 H.264 3840×2160 59.97 fps。观看过程中改 1080p→720p→1080p 无需刷新页面。
- MJPEG 1080p 质量 35 的每帧约 141 KB，质量 90 约 347 KB；页面质量表单也实际提交成功。
  保持 MJPEG 观看时改 EDID，输入先变为 1920×1080，再恢复 3840×2160，两次均继续收到 JPEG 帧。
- 重启 One-KVM 后输出限制与质量保留；EDID 1080p/4K60 可往返，HDR 220/1200
  可保存并恢复 203/1000。当前输入为 SDR，本次没有验证 HDR 曲线对 HDR 画面亮度的影响。
- 全程 HDMI 服务 InvocationID 保持 `5adb6d1c9b494584996befd0f64d2877`。
  管理页面 5 个 SVG 图表仍存在，`board.py check` 通过。

收尾恢复为 H.264、跟随输入尺寸/帧率、Balanced 码率、MJPEG 质量 80、4K60 EDID、
HDR 203/1000。日志位于 `logs/one-kvm-settings/`；`source-recovery.log` 的视频验证通过，
末尾图表检查误用 canvas 选择器，已在独立的 `manager-charts.log` 按实际 SVG 实现复核通过。
