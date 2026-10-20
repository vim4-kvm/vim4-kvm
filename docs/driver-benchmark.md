# VIM4 驱动基准

摘要：`tools/vim4-driver-bench.c` 用原生 C/GStreamer 分别测纯采集、采集加 H.264、
采集加 H.265。默认不读取像素、不解析压缩码流、不写录像、不经过网络或应用。
同一入口支持 7.x 的 V4L2/Wave5 与 5.15 的 vfmcapsrc/amlvenc；运行当前内核的
对应 backend，不会切内核、加载模块或停启服务。需要调用者事先取得板子独占。

## 构建与离线回归

在有 GStreamer 1.x 开发库的 Linux ARM64 上编译，产物只写临时目录：

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror tools/vim4-driver-bench.c \
  -o /var/tmp/vim4-driver-bench \
  $(pkg-config --cflags --libs gstreamer-app-1.0 gstreamer-allocators-1.0 gstreamer-video-1.0)
python3 -m unittest discover -s tests -p 'test_driver_bench.py'
```

Python 测试仅加载 appsrc/appsink 插件，不探测 V4L2；无开发库时显式跳过。
实际 C 回归检查预热边界、PTS 配对、漏帧/重排拒绝，以及两个共享 DMA 平面
持有父采集缓冲，直至下游释放；包含可见行高与分配行高不同的情况。
文件模拟的 DMA-buf 仅验证所有权，不代替真实硬件 DMA 一致性验收。

## 7.x 测量

先核对内核、实验模块参数、设备、占用者和服务，保持当前 HDMI 接收器与 EDID。
在 Mac 的物理 HDMI 桌面运行 [运动标记](latency.md)，待其稳定再开始。
不要同时运行浏览器推流、原始帧校验、perf、其他 benchmark 或软件解码。
实验服务停止和恢复只包住测试窗口；不卸载 RX/VDIN/Wave5，不改变供电或 USB。

以下在板子运行，前提是 `one-kvm-edge` 原本 active、没有其他占用者，且匹配的
驱动、固件和私有插件已安装。trap 保证测试失败时也尝试恢复原本运行的实验服务。
如果原本服务未运行，应保持原状，不照搬恢复命令。

```sh
set -eu
sudo systemctl stop one-kvm-edge
trap 'sudo systemctl start one-kvm-edge' EXIT
for codec in capture h264 h265; do
  sudo env GST_PLUGIN_PATH=/opt/vim4-onekvm-edge/gstreamer-1.0 \
    GST_REGISTRY=/var/tmp/vim4-driver-bench-registry.bin \
    /var/tmp/vim4-driver-bench --exclusive --backend=edge --codec="$codec" \
    --warmup=120 --frames=1800 --bitrate=20000000 --gop=60 \
    --output="/var/tmp/driver-edge-$codec-NEW.json"
done
```

新报告使用独占创建，不覆盖既有文件。`--device` 默认 /dev/video0；edge 会核对
采集及编码设备名。默认 4K60，也可同时指定 `--width=1920 --height=1080`，
但接收驱动与真实 HDMI 模式必须事先匹配，工具不负责切换输入。
并发工具实例使用只读 flock 协调；`--exclusive` 仍要求调用者确认没有其他应用占用。

7.x 用 NV12、父缓冲 lease 和两个 DMA 平面视图导入 Wave5，不复制原始帧。
H.264 请求 High、H.265 请求 Main，开启帧/块级码率控制，GOP 60、禁用逐行刷新。
caps 的 level 请求均为 5.1，这是当前驱动公开的上限；caps 不能证明实际 SPS。
匹配旧固件实际输出 H.264 Level 5.2、HEVC Level 5.0，必须在单独录像中
解析核对，不宣称 caps 已解决 level 标记问题。旧驱动请求 High 实际输出 High 10；
该回归通过固件命令边界的 profile 编号转换修正，仍须用下面的严格校验核实上板结果。

## 5.15 对照

保留同一个运动负载、分辨率、20 Mbps、GOP 60、performance governor 和编码器
时钟，再用 `--backend=stock` 运行三种 codec。该路径固定 NV21、关闭逐行刷新，
使用现有 vfmcapsrc/amlvenc，不使用 7.x 私有 V4L2 插件。
依照 [部署](subsystems/deployment.md) 协调并暂停实际视频应用，结束恢复原状态。
板子需要重启才能切内核；本工具不会代劳。

**厂商编码测试必须以生产应用的 khadas 用户运行**，复用其插件与兼容分配器环境，
不要 sudo 执行 stock 后端，也不要删除或重新初始化 /tmp/vpu_mutex.map。
可读的 debugfs 时钟写入报告；缺少权限时该字段为空，补充旁路只读记录。
仅请求参数相同仍不等于画质、码控或固件行为完全相同。

## 指标解释

- CPU 窗口：预热最后一个输出帧之后，到最后一个测量输出帧；排除启动和关闭。
  整机值来自 /proc/stat，按全核平均计算，含中断、驱动 worker、系统后台及工具。
  进程值来自 getrusage，按单核 100% 计算，不能与整机值直接相减。
- 三段 pad 时间：source src → encoder sink、encoder sink → encoder src、
  source src → encoder src。按同一 PTS 配对；缺失、漏帧、重复或重排会失败。
  编码 sink 到 src 包含 V4L2 排队、固件和线程调度，**不是纯硬件编码时间**。
- 帧率和间隔来自输出对应的采集 PTS；不等于光学延迟或浏览器呈现节奏。
  原始缓冲和编码输出数必须完整；工具不检查像素帧号或编码图像质量。
- 码率是测量窗口内压缩 buffer 的有效字节，不含网络/容器；同时记录最大帧和
 关键帧数，避免只看平均码率忽略突发。capture 模式这些字段为 0。
- CMA 记录启动前、预热结束和管线销毁后立即采样。最后值可能受延迟释放影响；
  需另核对 DMA-buf、稍后 CMA 与连续循环，不能凭一次差值认定泄漏。
- IRQ 只累计含 `vpu_irq` / `video-capture` 标签的计数；stock 未暴露相同标签时
  0 表示没有匹配项，不代表硬件无中断。报告记录内核 build、GStreamer、caps、
  governor、CPU 频率、Wave 时钟、温度、taint 和直接 DMA 参数。
- 温度和 CPU 不能代替功耗瓦数；当前没有电功率采样。也不以此证明 runtime PM 已验收。

重复至少三轮，保留源码/二进制/插件/固件 SHA、原始 JSON、运动源日志及恢复状态。
改变任何配置后独立重测；历史 Python 桥接＋parser＋文件输出结果不是该入口的
同条件基线。尚未用此入口实测的内核，不得写成已经完成性能对齐。

## 独立验证图像

可在另一轮加 `--save-bitstream=/var/tmp/NEW.h264`（或 .h265），写出编码器原始
输出，再在构建 VM 用 ffprobe/ffmpeg 解码以及
`tools/hdmirx-encode-check.py verify FILE --frames=总帧数 --check-colors --expect-profile=High`
检查 H.264；HEVC 使用 `--expect-profile=Main`。这会拒绝请求 High 却实际输出 High 10
等不匹配，不能仅凭成功解码或 GStreamer caps 判定 profile 已对齐。
总帧数包含 warmup。报告 measurement_kind 会标记 file IO，**这一轮不能与默认
基准比较 CPU**。原始码流没有容器时间轴；帧完整性和实际 SPS 使用离线解码核对。
采集一致性、缓冲耗尽、关闭及 DMA 生命周期仍由
[原生采集检查](bringup/2026-10-20-direct-dma-benchmark.md) 覆盖。
