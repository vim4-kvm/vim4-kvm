# 2026-10-14：Wave521 时钟与编码耗时

## Wave521 时钟与 4K 编码耗时（2026-10-14）


内核 5.15.137-vim4kvm，已安装 amlvenc（`/usr/lib/vim4-kvm/gstreamer-1.0`）。
停止 NanoKVM 后以 khadas 独占编码器；HDMI 3840×2160 约 60Hz 桌面，
12000 Kbps、60fps 预算、GOP120。耗时为 amlvenc sink→src pad probe 间隔，
输入为 vfmcapsrc DMA-buf，不含网络和浏览器。

| Wave b/c 时钟 | H.264 每帧 p50 / p99 ms | H.265 每帧 p50 / p99 ms |
|---|---|---|
| 500 MHz（fclk_div4） | 15.17 / 15.44 | 17.11 / 17.52 |
| 666 MHz（fclk_div3，当前） | 11.55 / 11.71 | 12.96 / 13.23 |
| 800 MHz（gp1_pll/3，实验） | 9.75 / 10.05 | 未取得有效数据 |

40000 Kbps 与 12000 Kbps 耗时相同；插件进程 CPU 约 3%。耗时与时钟成反比，
瓶颈是编码核本身。单独降低 clock_a 不影响耗时，b、c 任一降低都会变慢。
当前 666 MHz 下 4K60 剩余约 5ms（H.264）/ 3.7ms（H.265）。

### 超频正确性

可选父时钟中 fclk_div3 是最高固定源；更高频率只能借用闲置的 gp1_pll
（clk_msr 实测 0Hz）。实验模块把 gp1_pll 设为内核表中的 2400/3000 MHz 并保持开启，
再通过 amvenc_multi 的 clock_b/c 参数设置目标频率，clk_msr 核对实际频率。
同一段录制的 120 帧 NV21 原始画面（filesrc → rawvideoparse，非 DMA）每档编码三次，
比较完整码流 SHA256。666 MHz 下 H.264/H.265 多轮输出逐字节一致。

| 时钟 | H.264 | H.265 |
|---|---|---|
| 600 MHz（gp1_pll/4，对照） | 3/3 与 666 MHz 参考一致 | 3/3 一致 |
| 750 MHz（gp1_pll 3000/4） | 2/3 一致，1 次不同 | 3 次互不相同 |
| 800 MHz（gp1_pll 2400/3） | 3 次互不相同 | 未完成（期间录制文件被清除，作废） |

600 MHz 对照排除了 gp1_pll 来源本身的问题；750/800 MHz 输出不再确定，
视为硬件计算错误，**不采用超频**。gp1_pll 表中没有 666–750 MHz 之间的档位，
未测试其他 PLL 配置，也未做长时温度测试（各轮约 49–52°C）。
恢复 666 MHz 后参考码流复现，NanoKVM 4K H.264 浏览器 10 秒 60.07fps、
零丢帧/丢包。实验模块已卸载，未改动安装的模块参数或内核。

注意：khadas 的最后一个 SSH 会话退出时 logind 会清空其 /dev/shm 文件，
长测试的数据放 /var/tmp。实验源码和脚本在忽略入库的 `logs/encoder-clock/`。
