# 2026-10-19：7.3 HDMI 私有 DMA 环与 1080p60

结论：V4L2 MMAP 已从约 10fps 提升到稳定段约 60fps。三轮各 1800 帧、共 5400 帧
运动标记检查通过；每轮排除主动缓冲耗尽阶段后，源帧号逐次加 1，帧间隔中位数均为
16.667ms。仍限定 RGB8、逐行 1920×1080、60Hz 输入，尚无 DMA-buf、4K 或编码器接入。
5.15 保持默认启动项。

## 源码与所有权

内核提交 `99fbe81fdcbf8b88836574323c410b293c8b6be6`，tree
`866535fece97691eb9c4d69a9f4919a75bf05096`，基于
[首版 V4L2 队列](2026-10-19-hdmirx-v4l2.md)。源码仍在 VM `vim4-build` 的
`/home/deepdream/src/linux-7.3/drivers/media/platform/amlogic/t7-hdmirx/`。
普通 VIM4 DTB 不启用此实验；专用 DTB 独占整个 VPU 寄存器窗口并禁用 DRM VPU 节点。
共享 VPU、时钟和电源的生产架构仍需处理。

VDIN 新增三个驱动私有的 cached DMA 缓冲，每个 6,220,800 字节；原来的 coherent
快照缓冲保留。应用继续使用独立的 vb2 vmalloc 缓冲，硬件不会直接写入应用内存。
每个私有槽的状态由 `irq_lock` 保护：

| 状态 | 可执行的操作 |
|---|---|
| FREE | 可选为下一次硬件写入目标；CPU 访问已结束 |
| WRITING | 硬件可能写入；不能交给 CPU 或应用 |
| READY | 写完成后撤下的槽，等待工作线程；不会再次被选中写入 |
| COPYING | 工作线程持有；完成缓存同步、复制和归还后才能成为 FREE |

写完成中断中短暂关闭 WR_REQ/VCP_WR，读回控制寄存器，再检查写完成状态。
确认完成后才将旧槽转为 READY、更新下一个 FREE 槽的地址并恢复请求。
没有空槽时维持停写；工作线程归还槽后恢复。首次启动和暂停后的恢复都丢弃一帧，
避免从中间开始的部分帧被交付。READY 按序号先后取出，包含 u32 序号回绕处理。
这条路径在帧边界交接地址，不再逐帧重设整套 VDIN 或等待两次 RX 稳定采样。

cached 内存通过 `dma_alloc_noncoherent(..., DMA_FROM_DEVICE)` 分配，初次交给硬件前
也做 `dma_sync_single_for_device`：分配器会通过 CPU 映射清零，不能遗漏初始所有权转移。
每次复制前后分别调用 `dma_sync_single_for_cpu/device`，CPU 拷贝期间槽不会被硬件重用。

RX 将原有检查拆成一次进程上下文采样和两次稳定采样。启动仍保留两次采样和 20ms 间隔，
每帧复制前后用一次采样检查 5V、对齐、RGB、位深、尺寸、总时序及帧率，不等待 20ms。
一次采样也调用 `clk_get_rate`，不能放入硬中断上下文。

STREAMOFF／最后一个文件及映射释放时，等待工作线程结束复制，在下一次写完成处停写。
中断缺失或无法证明 DMA 已完成时，仍保留所有私有 DMA 内存、时钟和模块引用直到重启；
应用缓冲可安全归还。错误队列需要显式关流后重新开流；未新增任意输入的自动重锁恢复。
开关流、队列耗尽及 VDIN 模块重载均不改 EDID 或脉冲 HPD。

## 实机结果

版本 `7.3.0-rc7-vim4kvm-ring1+`；GCC 13.3，完整 Image/dtbs/modules 构建通过。
新增初始缓存同步后再次完整 make，Image 逐字节未变，只更新同次 Image 对应的 VDIN 模块。
最终暂存的全部 2332 个模块与板上文件 SHA-256 逐个吻合。

先通过三轮各 32 帧，再用现有
[V4L2 检查器](../../tools/hdmirx-stream-check.c) 做三轮各 1800 帧。
Mac 物理 HDMI 屏幕运行 `latency-source.swift --motion --verify-coherence`。
源图固定文字 `VIM4 4K60` 不代表本次分辨率；输入实际为 1080p60。
长测窗口没有并行构建、模块哈希检查或其他硬件任务。

| 轮次 | 帧数 | 首末源帧号 | 稳定段间隔中位数 | STREAMOFF |
|---|---:|---|---:|---:|
| 0 | 1800 | 4156 → 5969 | 16.667ms | 7.405ms |
| 1 | 1800 | 5974 → 7787 | 16.667ms | 8.523ms |
| 2 | 1800 | 7792 → 9605 | 16.667ms | 8.558ms |

每个出队缓冲均检查 bytesused、上中下三处帧号、magic/checksum、黑白三通道一致、
源帧号向前、V4L2 序号连续和 monotonic 时间戳。5400 帧均通过，没有重复或倒退的源帧号。
统计每轮 sequence≥32 的 1768 个间隔，范围 16.661–16.674ms，源帧号每次恰好加 1。
该证据支持此测试窗口的真实 1080p60 运动采集，不等同于每个像素的保真、光学延迟或隔夜稳定性。

每轮开始将四个应用缓冲全部出队并持有，空队列 poll 200ms 超时，完整缓冲指纹保持不变；
重新入队后恢复。包含有意暂停的每轮首末帧跨度约 30.218 秒，不将这一阶段算入稳态帧率。
持有缓冲及写 raw 的暂停会造成输入帧跳过；未声称消费者停止取帧时仍保留全部 HDMI 帧。
每轮关流后复用原缓冲再次开流；程序最后直接关闭文件和全部映射，也能正常停流。

补充 600 帧检查中，在程序明确报告开流后尝试卸载，`rmmod t7_vdin_test` 返回 in use。
关闭全部引用后正常卸载。三轮模块加载／8 帧取流／卸载后：

- 五项 VDIN 时钟的 prepare/enable 引用均回到 0，视频节点及 debugfs 消失。
- 每轮 CMA 可用内存均恢复至同一基线 259308kB，覆盖私有 cached 槽及快照缓冲释放。
- RX 的 HPD、EDID 哈希、PLL、对齐与输入尺寸状态保持不变。
- tainted=0，无 WARN/Oops；旧 debugfs 快照也重新取到有效帧并独立校验通过。

首次补测快照时，240 秒测试源已正常退出，采到的是原桌面而非标记，检查器拒绝通过。
重新启动测试源后，快照帧号 2813 校验通过；未修改阈值或把前一次失败计为有效图案。

## 验证入口与证据

加载接收器参数及实验启动隔离沿用
[完整快照记录](2026-10-19-hdmirx-frames.md)。V4L2 工具和调用方法沿用首版记录；
长测参数为 `/dev/video0 1800 3 输出目录`。仅支持 MMAP；节点编号动态分配。

内核的 `test_stream.py` 直接编译实际 C IRQ、私有环、工作线程和队列函数，用条件变量
协调硬件完成、CPU 复制及关流，不依赖 sleep。覆盖 COPYING 槽不能被写、耗尽暂停／恢复、
缓存 CPU／设备交接、复制期间关流、迟到且仍忙的中断、缺失中断、队列错误及序号回绕。
原有 DDC、PHY、core、快照实际 C 回归也在构建 VM 的 GCC 环境通过。
strict checkpatch 无错误、警告或检查项。主仓库离线测试运行 89 项，4 项跳过，其余通过。

主仓库忽略目录中的关键证据：

- `logs/kernel-edge/hdmirx-ring1-long.jsonl`、`hdmirx-ring1-long-summary.json`：5400 帧及时间统计。
- `hdmirx-ring1-busy-stream.jsonl`、`hdmirx-ring1-module-busy.log`：600 帧及活动引用保护。
- `hdmirx-ring1-reload.log`、`hdmirx-ring1-final-state-confirm.log`：CMA、时钟及无告警状态。
- `hdmirx-ring1-installed-match.log`：完整模块与 Image/DTB 核对。
- `hdmirx-ring1-final-c-tests.log`、`hdmirx-ring1-initial-sync-build.log`：离线 C 回归及最终构建。
- `hdmirx-ring1-saved-frames.jsonl`、`hdmirx-ring1-snapshot-regression-confirm.jsonl`：独立离线复核。
- `build/kernel-edge/ring1-long/`：六张首末帧 raw，末帧 PNG 已人工查看，图案清晰。

## 产物与恢复

| 产物 | SHA-256 |
|---|---|
| Image | `3ed1c54b41a7c627fc9fce7307e720801e22e56ddd6cd8d9a50b89d61a2a6b3d` |
| 本板 MAC 的测试 DTB | `25189da7420576c73ceacec6301f38bfd6e1a9f5843efa4048bd7c3695df8e37` |
| 最终完整模块归档 | `9a0970fa8df5ced5d2e0f0d99c50a48b5d611980c593dc193b0c93f866a85e2e` |

VM 输出／暂存目录分别为 `~/build/kernel-edge-ring1-test`、`kernel-edge-ring1-stage`；
主仓库部署清单位于 `build/kernel-edge/ring1-deploy/`，源码版本见
[实验内核锁](../../packaging/kernel-edge/sources.toml)。
只更新 `/boot/edge/` 及实验 release 模块，更新前备份在
`/var/backups/vim4-before-ring1-20261020/`。未改 BL31/U-Boot、分区或生产默认项。

测试后已恢复 `5.15.137-vim4kvm`，USB gadget 为 configured，tvserver、HDMI 和 gadget
服务均 active，无失败单元；启动配置与备份逐字节一致，`/lib` 符号链接保留。
实验返回定时器已随重启消失。证据为 `logs/kernel-edge/hdmirx-ring1-restored.log` 及对应串口日志。
这不代表全部生产应用已重新验收。

后续仍需 DMA-buf／编码器接入、4K、输入音频、动态 PHY、真实 HDMI 断线／模式变化与
睡眠恢复，以及共享 VPU 架构和完整 v4l2-compliance。本轮未物理拔插 HDMI，未验证真实失锁恢复。
