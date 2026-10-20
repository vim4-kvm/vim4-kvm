# 2026-10-19：7.3 HDMI DMA-buf 与软件 H.264

结论：1080p60 RGB24 采集已能通过标准 V4L2 EXPBUF 导出 DMA-buf，5400 帧运动校验通过。
缓冲跨队列重建、采集文件关闭、驱动卸载及重载后保持有效，最终资源恢复基线。
GStreamer 接收实际 DMA-buf，180 帧 OpenH264 软件编码再解码后全部通过运动标记检查。
软件链路约 4.8fps，不能替代硬件编码适配。测试后已恢复默认 5.15。

## 源码与缓冲所有权

内核提交 `e602ece7c5e5af498219d7be9ef53697c67dbffc`，tree
`11beab35d711327c847045f17b216a824b630cc2`，基于
[私有 DMA 环](2026-10-19-hdmirx-dma-ring.md)。源码路径与构建环境沿用该记录。
仍使用独占 VPU、禁用 DRM 的专用实验 DTB，仅支持 RGB8、逐行 1920×1080、60Hz。

应用队列从 vb2_vmalloc 改用 vb2_dma_contig，分配物理连续的 coherent 输出缓冲，
增加 `VIDIOC_EXPBUF`。队列分配接口仍为 MMAP，不支持应用传入任意 DMA-buf。
私有 cached DMA 环及其初始、逐轮 CPU/device 同步保持原实现。
工作线程从已完成的私有槽复制到输出缓冲，`dma_wmb()` 后交给 vb2。
这条路径仍有一次 CPU 复制，不是采集到编码的全程零复制。

导出对象由标准 vb2 分配器持有内存和设备引用；应用关闭采集文件、释放队列后，
旧导出 fd 可以独立存活。消费者必须在归还缓冲前结束访问；CPU 访问使用
`DMA_BUF_IOCTL_SYNC` START/END。本次验证 CPU 映射与软件消费者，尚未验证硬件编码器的
DMA attachment/import、格式转换或相关缓存边界。

## 连续采集

版本 `7.3.0-rc7-vim4kvm-export1+`，GCC 13.3 完整构建 Image/dtbs/modules。
全部 2332 个安装模块与最终暂存产物 SHA-256 逐个吻合；Image/DTB 哈希也与板上吻合。
Mac 物理 HDMI 屏运行 `latency-source.swift --motion --verify-coherence`。
源码图案中的固定文字 `VIM4 4K60` 不代表本次分辨率，输入实际为 1080p60。
长测没有并行构建、模块哈希检查或编码任务。

先通过普通 MMAP 32 帧和 DMA-buf 三轮各 32 帧，再运行：

```sh
gcc -O2 -Wall -Wextra -Werror tools/hdmirx-stream-check.c -o /tmp/hdmirx-stream-check
mkdir /tmp/hdmirx-export-check
sudo /tmp/hdmirx-stream-check /dev/video0 1800 3 /tmp/hdmirx-export-check --dmabuf
```

节点编号动态分配，须核对 name 为 `t7-vdin-test`。导出使用 O_CLOEXEC，
CPU 从只读 DMA-buf mmap 读取；逐帧检查长度、错误标志、三处帧号、magic/checksum、
黑白三通道一致、源帧号推进、V4L2 序号连续和 monotonic 时间戳。

| 轮次 | 帧数 | 首末源帧号 | 稳定段间隔中位数 | STREAMOFF |
|---|---:|---|---:|---:|
| 0 | 1800 | 2744 → 4617 | 16.667ms | 11.209ms |
| 1 | 1800 | 4623 → 6496 | 16.667ms | 0.204ms |
| 2 | 1800 | 6504 → 8377 | 16.667ms | 11.395ms |

每轮 sequence≥32 的 1768 个间隔合计范围 16.662–16.673ms，源帧号均逐次加 1。
每轮开头有意持有全部四个缓冲，验证空队列 poll 超时及整帧指纹不变，再归还恢复。
持有、指纹读取及保存 raw 会造成输入跳帧，每轮总跨度约 31.217 秒；不将此阶段算入稳态。
这些证据支持本窗口的真实运动 1080p60，不代表每像素保真、光学延迟或隔夜稳定性。
六张保存的首末帧也用 Python 检查器独立复核通过。

首次 DMA-buf、普通 MMAP 及旧快照检查都失败。查看实际快照发现 Finder 的 Dock 弹窗
遮住中间标记。测试源原来使用 floating 窗口层级，现仅在 `--verify-coherence` 模式
提高到 screenSaver 层级，以覆盖该 HDMI 屏上的弹窗；不发送键鼠或关闭其他应用。
随后原阈值检查通过，受遮挡的日志保留且不计为成功。

## 导出生命周期与资源回收

检查器在关流后用 REQBUFS(0) 释放原队列，再分配新四缓冲队列、取帧并直接关闭采集文件。
旧 DMA-buf 的整帧指纹保持不变，取消映射后只凭导出 fd 也能重新映射读取。
`--hold-exports` 在该阶段输出 waiting_for_controller 并等待 stdin 的一个换行；
控制端可在此期间卸载 VDIN、重新加载并采集，最后发换行让原进程重新映射、校验和释放。

实机控制顺序：卸载 VDIN 记录基线 → 加载并运行 16 帧持有测试 → 卸载 VDIN →
保留旧导出期间重新加载、8 帧取流、再次卸载 → 释放旧导出。结果：

| 状态 | CMA 已分配页 | 活跃 DMA-buf |
|---|---:|---|
| VDIN 未加载的基线 | 708 | 0 |
| 卸载 VDIN，四个旧导出仍持有 | 6784 | 4，合计 24,887,296 字节 |
| 新驱动取流后再次卸载，旧导出仍持有 | 6784 | 同上 |
| 关闭全部旧导出后 | 708 | 0 |

每页 4096 字节；四个 6,220,800 字节缓冲按页对齐，恰好增加 6076 页。
所有阶段的 vpu、vapb、vpu_clkb、vdin_meas、t7_sys_vpu_intr 时钟 prepare/enable
引用均回到 0。RX 的 5V、HPD、PLL、对齐、尺寸及 EDID 哈希保持不变，tainted=0。
旧导出跨驱动替换的重映射和整帧指纹检查通过。

首次控制器严格比较 CmaFree，因最终空闲量比起点增加 188kB 而失败。
CmaFree 包含普通可迁移页，不等同于 CMA 客户端分配量；后续保留它作观察值，
改以 `/sys/kernel/debug/cma/reserved/used` 和 DMA-buf 对象总数严格比较资源。
复核结束 CmaFree 为 259300kB、起点 259304kB，已分配页及对象数完全恢复。
编码测试结束后再次卸载也恢复到 708 页、零 DMA-buf，未出现内核 WARN/Oops。

## 软件 H.264 端到端校验

新增 [编码检查器](../../tools/hdmirx-encode-check.py)，板上需要 Python GI、GStreamer、
GstAllocators、OpenH264，以及解码检查所需的 ffmpeg/ffprobe。保持测试图案运行：

```sh
sudo python3 tools/hdmirx-encode-check.py capture --exclusive \
  --output /var/tmp/NEW-180.mkv --frames 180
python3 tools/hdmirx-encode-check.py verify /var/tmp/NEW-180.mkv --frames 180
```

输出目录必须已存在，视频及对应 `.mkv.json` 必须是新文件。流水线为：
v4l2src io-mode=dmabuf → RGB1080p60 → videoconvert/I420 → openh264enc → H.264/Matroska。
编码参数 20Mbps、GOP60、complexity=low。源侧 probe 要求单平面实际 DMA-buf、
6,220,800 字节、递增 PTS，fdinfo 的 exporter 必须为 videobuf2_dma_contig；
不把自动退回普通内存视为通过。

本次 GStreamer 1.24.2 接收 180 个实际 DMA-buf，输出 26,998,201 字节，
包含启停的耗时 37.850 秒，吞吐约 4.76fps。软件处理造成背压和源帧跳过，
不声称编码 60fps；输入帧号从 14527 推进到 16717。
ffprobe 确认 H.264 1920×1080，ffmpeg 按原帧解码得到恰好 180 帧，逐帧三处标记、
黑白通道、checksum 及向前推进均通过，没有重复或倒退。
GStreamer 扫描器对现有 amlvideosink/nvcodec 插件报告缺失厂商库，并有一条属性注册
critical 日志；所需流水线仍成功，不能据此宣称整个插件环境无告警。

硬件 Wave521 尚未适配。7.3 Wave5 目前匹配 TI wave521c，产品识别接受 WAVE521C，
使用 TI 固件；T7 实际产品码尚未读取。下一阶段应先补齐 T7 的时钟、复位、电源和
资源管理，安全读取产品信息，再确认固件及命令 ABI，不能直接套 TI compatible/固件。
同时仍缺 NV12 等硬件输入格式、4K、动态 PHY、真实失锁/模式切换恢复、输入音频、
共享 VPU 架构、完整 v4l2-compliance 和应用接入。

## 构建、证据与恢复

实际 C 的 DDC、PHY、core、VDIN 快照、stream 五组回归均在 VM GCC 环境通过；
strict checkpatch 为 0 errors、0 warnings、0 checks。主仓库新增管道短读/截断检查，
验证解码输出必须组装成完整帧，不能把短读当成正常 EOF。
主仓库完整离线测试运行 92 项，4 项跳过，其余通过，日志为 `hdmirx-export1-main-tests.log`。

本轮忽略目录中的证据：

- `logs/kernel-edge/hdmirx-export1-long.jsonl`、`hdmirx-export1-long-summary.json`：5400 帧及节奏。
- `hdmirx-export1-covered.jsonl`、`hdmirx-export1-mmap-covered.jsonl`：短测及 MMAP 回归。
- `hdmirx-export1-held-confirm.jsonl`、`hdmirx-export1-lifetime-confirm.log`：跨模块替换及资源。
- `hdmirx-export1-encode.log`、`hdmirx-export1-encoded-verify.jsonl`：实际 DMA-buf 与解码标记。
- `hdmirx-export1-installed-match.log`、`hdmirx-export1-final-c-tests.log`：模块核对、C 回归与风格检查。
- `hdmirx-export1-final-state.log`、`hdmirx-export1-final-resources.log`：内核日志、时钟和最终资源。
- `build/kernel-edge/export1-long/`：六张 raw；`build/kernel-edge/software-180.mkv` 及 JSON 为视频和采集报告。

| 产物 | SHA-256 |
|---|---|
| Image | `e9cb260b8ea2f69d4862b7fa8f13ba335d4b2854050ddf3ac78ebf72382bc0c7` |
| 本板 MAC 测试 DTB | `25189da7420576c73ceacec6301f38bfd6e1a9f5843efa4048bd7c3695df8e37` |
| 完整模块归档 | `3bd64300a398ea4b0c59bc3dca71ba788e1e88654828b26dca226799c8733894` |

VM 输出 `~/build/kernel-edge-export1-test`、模块暂存 `kernel-edge-export1-stage`；
最终配置 SHA-256 为 `91598fe06672851a314494e9edc8682f106b72849373fbac3a59a120fc850e58`。
部署清单在 `build/kernel-edge/export1-deploy/`，内核版本见
[源码锁](../../packaging/kernel-edge/sources.toml)。
只更新实验 Image/DTB 和独立 release 的完整模块；备份在板上
`/var/backups/vim4-before-export1-20261020/`。未改 BL31/U-Boot、分区或默认项。

正常重启后恢复 `5.15.137-vim4kvm`，USB gadget 为 configured，tvserver、HDMI、gadget
服务均 active，无失败单元；启动配置与备份逐字节一致，`/lib` 符号链接保留。
实验定时器随重启消失。证据为 `hdmirx-export1-restored-confirm.log` 和返回串口日志。
首次 SSH 恢复检查在启动期间超时，稍后复核成功；未做网口热解绑。
这不代表全部生产应用已经重新验收。
