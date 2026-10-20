# 2026-10-20：One-KVM 7.3 CPU 性能定位

摘要：真实 Rust One-KVM 的 4K60/30 Mbps 链路仍高于 5.15 的 CPU 开销。采样已将
额外负载定位到 VDIN 私有环复制及缓存同步、编码后 NAL 解析。先缓存压缩码流后，
H.264/H.265 整机 CPU 分别从约 12.45%/11.85% 降至 9.96%/9.78%。仍未对齐
5.15；不能用此前 Python 测试桥接的 CPU 代替真实应用结果。

## 基线与测量方法

- 内核：5.15.137-vim4kvm 与 7.3.0-rc7-vim4kvm-uhd1+；后者提交 `702421daa1a1`。
- 5.15 使用原生产 One-KVM；7.3 使用独立程序 `34df7ad5ca88`、独立数据和端口。
- 同一 VIM4，Mac 物理 HDMI 桌面上的相同运动标记，3840×2160p60，30 Mbps。
  5.15 为 NV21、逐行刷新；7.3 为 NV12、GOP 60。不能将两者当成相同编码参数。
- 两边均为 performance governor；CPU0–3 最大容量 1024、2208 MHz，CPU4–7
  容量 577、2016 MHz；Wave A/B/C 均约 666.7 MHz，没有超频。
- Chrome 155.0.8059.85，经 SSH 回环转发访问各自后端。浏览器单独运行，暖机 8 秒，
  推流 35–45 秒，期间用 `mpstat -P ALL 1 25`、`pidstat -h -u -t` 采样 25 秒。
  没有同时运行其他编码测试。5.15 保留生产后台服务，7.3 屏蔽不兼容的旧服务。
- 整机 CPU 为八个逻辑 CPU 的平均忙碌比例，不按 big/LITTLE 容量加权；
  pidstat 的进程/线程百分比按一个逻辑 CPU=100% 计，不能与整机百分比直接比较。
  测量包含 SSH 和采样工具开销。7.3 没有 CONFIG_SCHEDSTATS，不能把 %wait=0
  当作没有调度等待的证据。

| 链路 | 格式 | 整机 CPU | One-KVM（单核百分比） | VDIN 复制线程（单核百分比） |
|---|---|---:|---:|---:|
| 5.15 生产 | H.264 | 3.93% | 18.27% | 未单列 |
| 5.15 生产 | H.265 | 3.77% | 17.83% | 未单列 |
| 7.3 原实验程序 | H.264 | 12.45% | 48.66% | 45.30% |
| 7.3 原实验程序 | H.265 | 11.85% | 48.00% | 45.48% |

基线证据：`logs/kernel-edge/perf-515-h264-*`、`perf-515-h265-*`、
`perf-7-h264-*`、`perf-7-h265-before-*`。7.3 H.264 的第一个线程采样命令错误地
查找 t7-vdin-test 进程，不使用其结果；使用 `threads-corrected.log`。
两边浏览器均接近 60 fps；5.15 此轮 H.264/H.265 呈现间隔 p99 34.3/32.5 ms。

## 热点证据

用同一内核源码构建独立的 perf 工具，仅复制到板上 `/var/tmp`。另开推流窗口，
`perf record -a -e cpu-clock -F 199 -g -- sleep 15`；profiling 与无 profiling 的
CPU 基线分开，不把 profiling 窗口用作优化后的 CPU 比较。
工具未启用 DWARF/libbpf，内核也缺少 schedstat，采集时会提示这些限制；这里只用
采样 IP 对应的叶符号占比，不依赖完整用户态调用栈或调度等待统计。

23K 样本、无丢失，按所有 CPU（包含 idle）统计：

| 线程 / 符号 | 样本占比 |
|---|---:|
| t7-vdin-capture / __pi_memcpy_generic | 4.01% |
| t7-vdin-capture / __pi_dcache_clean_poc_nosync | 0.85% |
| t7-vdin-capture / __pi_dcache_inval_poc_nosync | 0.83% |
| encoder:src / gst_byte_reader_masked_scan_uint32 | 2.45% |

见 `perf-7-h264-hotspots.log`、`perf-7-h264-hotspots-flat.log`。复制线程合计
5.72% 样本，编码输出线程 3.03%。Rust 平面桥接线程约 1.04% 单核，占比很小；
本轮没有运行 Python 采集桥接或板上软件解码。

原始 NV12 为每帧 12,441,600 字节，60 fps 单向复制约 746.5 MB/s，另有缓存同步。
现有私有环将硬件写入隔离于应用缓冲，即便 DMA 停写超时也不释放硬件仍可能使用的
内存。优化不能省略所有权交接或以提前归还缓冲换 CPU。

NAL 解析则直接逐字节扫描 Wave5 coherent DMA 映射。现在在编码器 src pad 上把
有效压缩载荷深复制到普通内存，再交给 h264parse/h265parse；30 Mbps 约 3.75 MB/s。
平面桥接继续只建立视图，不增加用户态原始帧复制。离线测试验证实际载荷长度、
独立内存、时间戳、持续时间和帧型标记；GStreamer TAG_MEMORY 仅是内存池标记，
不要求新分配继续携带。

## 压缩码流缓存结果

One-KVM 提交 `c6327c3e332f`，只在 Wave5 后端启用编码后缓存；内核、原始帧复制、
缓存同步、码率及 GOP 没有变化。实验二进制 SHA-256
`79ca51f942432e38847c5881fa557d8ac83c0197d596fcc2fa7690164d917403`。
原实验二进制保存在板上
`/var/backups/vim4-onekvm-edge-20261020/one-kvm-before-cached-bitstream`。
生产 5.15 程序没有替换。

| 格式 | 整机 CPU：之前 → 缓存后 | 应用：之前 → 缓存后（单核） | 编码输出线程：之前 → 缓存后（单核） |
|---|---:|---:|---:|
| H.264 | 12.45% → 9.96% | 48.66% → 30.23% | 23.67% → 4.72% |
| H.265 | 11.85% → 9.78% | 48.00% → 30.70% | 23.28% → 5.32% |

均使用未固定 CPU 亲和性的 25 秒窗口。证据为 `perf-7-h264-cached-{system,threads}.log`、
`perf-7-h265-cached-{system,threads}.log`。原始复制线程仍约 44–45% 单核。
按该窗口拆分，复制线程约占整机 5.6 个百分点，余下约 4.3%；这不是直接 DMA
已经实现或一定能达到 5.15 性能的证明。

另外在同一推流会话后半段分别测试了亲和性：H.264 仅把复制线程限在 CPU0–3，
复制线程从 45.14% 降到 33.43% 单核，应用却从 30.23% 增到 42.38%，
整机 10.47%，没有整体收益。H.265 仅把应用所有线程限在 CPU0–3，整机
9.77%，与未固定的 9.78% 基本相同。因此没有修改默认亲和性，测试后恢复 0–7。
见 `perf-7-h264-cached-bigcpu-*`、`perf-7-h265-cached-app-bigcpu-*`。
80 秒 cached-browser 结果包含上述临时亲和性阶段，不能把其全部呈现间隔变化
单独归因于缓存改动。

`cargo test --locked --features vim4 --lib` 共 718 通过、1 ignored；ARM64 release
构建通过。新测试用文件支持的
DMA 内存、非零偏移和较大的分配容量验证只复制有效压缩载荷，保留帧时间与类型，
复制后源内存变化不影响缓存内容。

复采样的编码输出线程由所有 CPU 样本的 3.03% 降到 0.71%，原先的逐字节扫描
符号低于 0.15% 的报告阈值。复制线程仍为 5.71%，与之前 5.72% 相近，见
`perf-7-h264-cached-hotspots.log`、`perf-7-h264-cached-hotspots-threads.log`。

## 功能回归与剩余工作

- 缓存版两种格式各推流 80 秒，均约 60 fps，解码丢帧/丢包/freeze 为 0。
- H.264/H.265 网页运动检查分别抽样 78/77 个帧号，invalid/incoherent 均为 0，
  见 `perf-7-h264-cached-coherence.json`、`perf-7-h265-cached-coherence.json`。
- 切换 8000/20000 kbps、红绿蓝颜色检查、三轮重连及拒绝 MJPEG 通过，见
  `onekvm-cached-browser-features.json`。首次仅等 videoWidth 就立即读取画布得到
  黑色，未计通过；后续等待 30 个实际呈现帧再验收，保留原颜色阈值。
- 关闭应用后 CMA 为 469760 KiB，DMA-buf 数量为 0，内核 taint=0，
  dmesg 未见 WARN/Oops/分配失败；见 `perf-7-cached-final-state.log`。

下一项是去掉 VDIN 私有环到 vb2 的整帧 CPU 复制，同时保留关流、缓冲持有、孤儿
DMA-buf 和停写超时的内存安全。需由硬件写入完成证明决定何时归还每个缓冲，
不能只切换指针或跳过 DMA 同步。周期 IDR 的呈现尾部、动态 HDMI 和长期稳定性
也尚未与 5.15 对齐；本次不声称第 2 步的全部性能适配已完成。

结束时正常重启回 5.15，原应用、管理器、HDMI、gadget、PD 均 active，UDC configured。
生产受保护文件哈希全部吻合备份；旧版网页再次解码 3840×2160 H.264，约 60 fps，
丢帧/丢包/freeze 为 0，见 `perf-production-return-browser.json`，之后恢复测试前的
H.265 模式。主仓库离线测试 99 项（95 通过、4 跳过）。
