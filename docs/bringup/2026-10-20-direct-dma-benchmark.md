# 2026-10-20：本地基准与 VDIN 直接 DMA

摘要：新增无需部署应用或切内核的 buffer benchmark；独立程序也能在板子的当前
内核运行。实际 VDIN 输出映射上的标量/SIMD 对照没有收益，因此未采用 SIMD。
新的显式直接 DMA 路径取消私有环到 vb2 的整帧 CPU 复制，已完成固定 4K60 实验验收；
H.264/H.265 整机 CPU 分别从 9.57%/9.71% 降到 4.33%/4.22%。长期稳定性仍待验收。

## 软件与原生复制基准

入口和解释见 [本地视频基准](../local-video-benchmark.md)。One-KVM `dd52bdb4035b`
只增加 cfg(test) benchmark 和说明，直接调用生产 plane_view/cached_bitstream。
实际实验应用仍为此前 `c6327c3e332f` 构建，SHA 为
`79ca51f942432e38847c5881fa557d8ac83c0197d596fcc2fa7690164d917403`。
没有替换生产 5.15 应用。容器/板上测试均编译 release，预热校准后测九个批次。

| CPU 软件路径 | 本机 Linux ARM64 容器中位数 | VIM4 A73 CPU0 中位数 |
|---|---:|---:|
| 1080p 平面视图（包含 1088 行尾容量） | 1.10 µs | 18.32 µs |
| 4K 平面视图 | 0.25 µs | 1.70 µs |
| 普通缓存 RAM 的 4K NV12 复制 | 1.30 ms | 6.20 ms |
| 合成压缩载荷 62,500 字节深复制 | 3.38 µs | 67.53 µs |
| 合成压缩载荷 1 MiB 深复制 | 22.60 µs | 614.49 µs |

file-backed GstDmaBufMemory 不是 V4L2/VPU 映射，map/unmap 与容量也影响结果；
这些数字不能换算为 DMA 路径 CPU 或内核吞吐。5.x 同样能跑这些软件 case，但
不能用它验证 7.x 驱动。板上两轮同配置结果通过 20% 回归门槛；该门槛是本次
选择的检测容差，不是运行时帧延迟保证。另测试了 7.x 的真实 system heap，显式
同步后 62,500 字节/1 MiB 为 35.13/257.55 µs，仍不能代替 VPU 映射测量。
记录：`logs/kernel-edge/local-buffers-before.json`、`board7-buffers-{before,repeat,real-heap}.json`。
这些早期报告尚未包含后补的 uname -v/负载记录字段；最终入口会一并记录。

`test_copy.py` 将当前内核实际 memcpy_generic 与独立 SIMD 候选编成原生小程序，
在闲置 VDIN 队列申请四个真实 vb2 MMAP 缓冲，以普通缓存源帧轮转写入。
交替采九组、每组 32 帧，逐组比较完整输出，不启动 HDMI 采集。

| 候选 | 核 | 标量 → SIMD 的每帧中位数 |
|---|---|---:|
| 初版 SIMD | A73 CPU0 | 1.909 → 1.918 ms |
| SIMD 加源预取 | A73 CPU0 | 1.907 → 2.206 ms |
| 固定偏移载入、流式写入 | A73 CPU0 | 1.913 → 1.920 ms |
| 固定偏移载入、流式写入 | A53 CPU4 | 4.232 → 4.275 ms |

均无收益，候选汇编只保留给 benchmark，未链接到采集驱动。普通 RAM 复制与
这里的真实输出映射差异，也说明不能用容器内存测试替代板端映射测试。
记录：`vdin-copy-{candidate,prefetch,stream}-cpu*.json`。

## 直接 DMA 的实现与本地回归

内核 `1762175bf43d`，tree `30b5286910130747b2c39362809e85115ba35c76`。
模块参数 `direct_dma=1` 从已排队的 coherent vb2 缓冲取得下一个 DMA 地址；
IRQ 证明最终 AXI 写入完成才发布 READY。应用未重新排队的缓冲不会被再次选中；
队列耗尽暂停，恢复时丢掉可能不完整的第一帧。快照和原私有环复制仍可独立使用。
应用的 ParentBufferMeta 继续保留采集池 lease，直到编码器释放输入。

每个直接缓冲在 buf_init 提前取得独立 allocator DMA-buf 引用。正常 STREAMOFF
等待 worker、帧完成和 IRQ/DMA 停写，再允许清理；关闭和 REQBUFS(0) 可让外部
export 继续持有分配。如果停写超时，返回 ERROR 的内容无效，队列不能重启，
用过的分配引用与原有模块/内存保留一起保持到硬件重启，避免物理地址被释放复用。
这会故意保留内存，不是超时后可继续使用的恢复机制。

Mac 与 Linux ARM64 的 test_stream.py 编译实际 IRQ、队列、worker、清理 C 代码，
ASan/UBSan 检查：持有不覆写、队列耗尽恢复、写入中的 STREAMOFF、busy/missing
IRQ 隔离、lease 分配失败，以及 vb2 对象销毁后硬件分配仍存活。原复制路径也继续
通过；另通过 Wave5 偏移/容量和 32 个分配失败/关闭用例。真实硬件未人为注入
停写失败，不能把桩测试写成该硬件故障已经通过。

完整 Image/dtbs/modules 构建通过，2333 个模块，未发现 warning:/error:。
Image SHA：`de496d2b0a4b04badbb33cc2593802b3af126ada4dc9e71690a6839735f95d48`。
同次构建模块归档 SHA：`b8364ed1916cb8346f0c1c78538201068293e377f13701c189cd29ec3efebb71`。
替换了完整匹配模块集；先前 Image、模块和清单在板子
`/var/backups/vim4-onekvm-edge-20261020/direct-dma-1762175`。5.15 Image、程序、
兼容分配器、服务及 extlinux 配置 SHA 未改变。DTB、固件和私有 GStreamer 插件未改。

## 同一新内核的应用对照

同一应用、4K60 RGB8 物理 HDMI 运动标记、30 Mbps、GOP 60，performance governor，
Wave 时钟约 666.7 MHz，未固定应用/复制线程亲和性。Chrome 155；70 秒网页窗口中，
第 15 秒起用 mpstat/pidstat 采 25 秒，采样位于稳定推流内。整机 CPU 是八核平均，
进程/线程按单核 100% 计。没有同时运行其他性能或编码测试。

| 采集模式 | 编码 | 整机 CPU | 应用 CPU | 采集 worker CPU |
|---|---|---:|---:|---:|
| 私有环复制 | H.264 | 9.57% | 30.00% | 44.44% |
| 私有环复制 | H.265 | 9.71% | 32.00% | 41.48% |
| 直接 DMA | H.264 | 4.33% | 28.00% | 0.20% |
| 直接 DMA | H.265 | 4.22% | 28.11% | 0.24% |

H.264 复制/直接与 H.265 直接均约 60 fps、3840×2160，70 秒增量零丢帧、丢包、
freeze。直接 DMA 的 stream_copy_bytes 为 0，说明驱动取消了该整帧 CPU 复制；
压缩码流缓存复制仍保留。不能由此声称所有层次都零复制或完整性能已与 5.15 相同。
H.264 直接呈现回调 p99 39.4 ms；H.265 为 59.0 ms，回调采样仍有漏采，平均
60 fps/零 freeze 不能替代逐帧呈现或光学延迟验收。

`direct-dma-copy-matched-*`、`direct-dma-h264-*`、`direct-dma-h265-*` 保存本轮结果。
H.265 的同内核复制对照为 `direct-dma-copy-h265-*`，在独立窗口补测，未与直接模式并发。
更早的 `direct-dma-copy-baseline-*` 为 40 秒探索窗口，CPU 采样可能跨越结束，不作
CPU 对照。不要混用此前不同内核和不同采样窗口的基线。

网页像素一致性已采 H.264 80、H.265 81 个不同帧号样本，三处标记无损坏或不一致，
H.265 从实际 codec stats 核对。采样不是对全部视频帧的完整检查。
两次关闭后 DMA-buf 为 0，CMA 约回到 469,760 KiB，taint=0。

原生 hdmirx-stream-check 又检查了 600 帧 × 3 轮，1800 帧的三处帧号、推进和原色
均通过。每轮持有全部四个缓冲、确认内容不变、空队列等待，然后重新排队恢复；
每轮序号 8 之后的稳定段均约 59.998 fps。总 span 含完整缓冲哈希和 200 ms
人为耗尽等待，不能将其平均值当成稳定采集帧率。
另通过 REQBUFS(0) 孤立旧导出、分配新队列、活动流直接 close、保留旧导出跨
采集模块卸载后的重映射及完整哈希比较。释放后 DMA-buf=0，卸载采集模块后
CMA=518,384 KiB，正常重载后约 469,760 KiB。记录为 `direct-dma-native-stream.jsonl`。

网页功能检查通过 RGB 原色、8/20 Mbps 动态码率、三轮重连（包含一次 6 秒空闲
关闭后重建）及拒绝不支持的 MJPEG。8/20 Mbps 窗口约 59.94/59.77 fps；结束
恢复实验配置为 H.264/30 Mbps。记录为 `direct-dma-browser-features.json`。

实验准备器现显式要求 nv12=1/direct_dma=1，并拒绝已经预载的复制模式；正常的
实验服务 stop/start 已验证这一加载路径。内核参数本身仍默认关闭，独立快照和
手动复制对照可以使用原路径。板子保持 7.x，5.15 默认启动与回退项未改；没有
安排自动返回 5.15。实验应用仍为独立目录、数据及 loopback 8082，未切换生产应用。

最终入口在容器再次运行成功；板上两轮完整 JSON（包含 loaded kernel 的 uname -v）
对照通过 20% 门槛，见 `final-local-buffers.json`、`board7-final-buffers-{before,after}.json`。
One-KVM 库测试 718 通过、2 ignored；主仓库离线测试 103 项，99 通过、4 跳过。
最终服务保持运行，DMA-buf=0、taint=0；没有进行长期推流、动态输入或完整 USB/音频验收。

模块对照中 modprobe -r 自动移除了未占用的 HDMI 接收依赖；随后自动加载默认
参数导致 -ENOLINK。恢复了明确的接收参数后继续，失败窗口不计作通过。
只切采集实现时使用 rmmod t7_vdin_test，保留接收器；若需卸载接收器，先停 Mac
源窗口再重新协商，避免窗口随显示连接变化迁移。普通网页重连不需要这样操作。
