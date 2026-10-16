# 2026-10-12：HDMI 输入采集

**拓扑**：Mac mini HDMI 输出 → VIM4 Micro HDMI 输入（RX port 1）；VIM4 HDMI 输出未接任何设备。

**Mac 不输出信号**：板子上 `hdmiin-demo` 打开源后 HPD 拉高，Mac 读到 EDID（"AML TV"），`ioreg` 中 `HDMI_HPD=Yes` 但 `HDMI_HPD-Debounced=0`，RX 端 `cable clock = 0`。原因是 Mac 上正在使用屏幕共享的高性能虚拟显示器（CoreGraphics 只有一个 Screen Sharing Virtual Display），物理 HDMI 不启用。退出后 Mac 立即输出，RX 锁定 `3840x2160@60 YUV420 10bit`（之后 Mac 也会切到 4K30/RGB/YUV444 等模式，RX 都能锁定）。

调试用：`echo "hpd0 1" > /sys/class/hdmirx/hdmirx0/debug` / `hpd1 1` 软件拔插 port 1（最后一个参数是端口号）；`echo "state 1" > .../debug` 把 port 1 状态打到 dmesg。

**采集链路**：

- tvserver（`tvserver.service`）负责打开 HDMI 源并启动 vdin0；客户端用 `hdmiin-demo`（忽略所有参数，打开即运行；用 `nohup setsid` 后台跑）。**必须在 Mac 已输出信号后再启动**，否则 vdin0 停在 `TVIN_PORT_NULL`，需要重启 `hdmiin-demo`
- 默认 `tvpath { vdin0 amlvideo2.0 deinterlace amvideo }`；改为无下游的 standalone：先停 `hdmiin-demo`，`echo rm tvpath > /sys/class/vfm/map; echo add tvpath vdin0 vfm_cap > /sys/class/vfm/map`，再启动 `hdmiin-demo`
- vfm_cap 的 V4L2 mmap 缓冲只是 4KB 流控令牌，帧数据要在 DQBUF 后用 `VFM_CAP_IOC_GET_DMABUF` 取 DMA-buf fd 再 mmap（`test_dmabuf`）；`v4l2-ctl --stream-to` 拿不到数据
- vdin0 默认 `tv_bit_mode = 0x235`，4K 时输出 Amlogic 40-bit packed 422 10bit（fourcc `AMLY`，非标准，按常规位序解不对）。KVM 只需 8bit：`echo "color_depth_support 0x1" > /sys/class/vdin/vdin0/attr` 后重新开源，输出 **UYVY 3840x2160**，`ffmpeg -f rawvideo -pix_fmt uyvy422` 可直接转换
- 以上已固化为 `tools/hdmi-capture.sh`

**内核 bug（已修复）**：合入的 "Fix vdin1 stuck state" 补丁在 `vdin_v4l2_release()` 中遇到 DEC 已启动就强制 `vdin_v4l2_stop_tvin()`，不区分启动者——只要有进程 `v4l2-ctl -d /dev/video70 --info`，tvserver 启动的 vdin0 就被停掉且 vsync 中断不再恢复（`irq_cnt: 0`）。修正为仅在 V4L2 工作模式且关闭的是 vb2 队列 owner 时强停。
