# 2026-10-24：HDMI RX 持续采集稳定性复测

接续 [周期量化根因与厂商对照](2026-10-24-hdmi-capture-quantization.md)，
记录TOP计量器与真实源/自环长测，仍不是VDIN→VD1透传验收。
完整任务状态见 [第二阶段实现记录](2026-10-24-hdmi-passthrough.md)。
默认eeddb005与manager974ab40不改，不合入正式内核、不正式部署。
本地原始证据位于 `logs/hdmi-passthrough/`。

## FDET修复后的长测与计量器重测

真实Mac mini 4K60、SDR/444/8bit、同一运动源，`03cabbd5cd714` 严格采集在
315.679115秒遇到首个ERROR后停止：18941个完成帧、18940有效、1 ERROR，
出队59.997634fps、有效59.994466fps、ERROR率0.0052796%。全部三处标记一致，
含该ERROR帧；19次源帧号重复，不能称为每帧均为新源内容。
IRQ frame-done→DQBUF：p50 0.121ms、p95 0.166ms、p99 0.185ms、最大1.325ms；
它仅为软件取帧时间，不是透传或光学延迟。

本次拒绝原因为 `tmds-measurement error=-11`，不是FDET差异：
cable=`0x8000c5ff`、HDMI meter=`0x000317fc`（计数保留、VALID清零），
PLL/SQO/alignment均1，RX ready保持1、stream_stops=0、VDIN faulted=0。
未把采样标记完整扩大为整幅图像已证明无损；该窗口**不通过零ERROR长测门禁**。
原始记录为 `fix-4k-long-1.jsonl`、同名dmesg及 `fix4k-monitor.jsonl`。

后续候选 `131fbdf603eee` 仅在TOP测量暂不可用时，按8192个参考时钟周期等待，
最多两轮后重新检查；24MHz下每轮342–392µs。只接受重新置VALID的匹配时钟，
每轮重新检查5V/alignment/SQO；不接受保留的旧计数，不改变2MHz时钟匹配阈值。
持续无效仍返回EAGAIN；真实失锁仍返回ENOLINK。正常路径不等待，恢复时限频记录轮数。
实际C故障注入覆盖第一/第二轮恢复、持续无效及等待期间失锁；68项host fixtures与
strict checkpatch通过；随后完整构建并上板，结果见下段。

两窗口候选build ID `40c03d84ae2210909c7ab458748c429928955c76` 上板后，
实际多次取得第一/第二轮有效测量，但严格4K长测仍在151.189963秒停止：
9072个完成、9071有效、1 ERROR，ERROR帧标记完整；没有失锁、stream_stops或fault。
这表明两个窗口的边界不足，不能以短测或个别重测成功宣布修复。

随后进行180秒**诊断采样**：`/dev/mem`只读映射已核对的RX TOP页，仅轮询
METER_CABLE_STAT/METER_HDMI_STAT及5V/SQO/alignment，不写寄存器、不复位meter。
同时持续采集以避免空闲link worker的周期重装干扰。1547722次采样捕获936个
VALID低脉冲：观测长度p50 715.720µs、p90 1063.184µs、p99 1082.726µs、
最大1101.935µs；采样粒度及调度会影响边界，不能当作精确硬件脉宽。
所有低脉冲的5V/SQO/alignment正常，HDMI原始计数仅 `0x317fc/0x317fe`，
恢复VALID后为 `0x317fc/0x317fd`。未确认硬件VALID内部判稳算法，不推测其精确语义。
本段同步11101帧、185.006075秒、59.998030fps、0 ERROR/坏标记，9次重复；
它带高频寄存器观察且不足10分钟，不是验收窗口，也不能覆盖前一段失败。

`41c31fc123935` 据实际观测将有限等待扩为四个meter窗口：三个覆盖已测低脉冲，
一个覆盖采样相位；24MHz时最多约1.37–1.57ms。保留新VALID、2MHz匹配阈值、
每轮物理检查及超时拒绝，未调整PHY或硬件meas_tolerance。
实际C测试覆盖四个允许恢复点和第五窗口超时；68项host fixtures和strict checkpatch通过。
完整Image/DTBs/2339模块构建完成，build ID `890406629692236532d2cfaa2346ee052fa85755`，
Image SHA256 `647754467dab353c57693c562d9f5598e812d68985ee158754f71d2f652c134b`。
真实源/自环逐档长测结果见下节。原始证据 `meter-observe*`、`fix2-4k-long*`。

## 四窗口候选的稳定性窗口（仍非透传验收）

| 输入 | 完成/有效/ERROR | 有效计时 / fps | 画面标记 | 状态 |
|---|---|---|---|---|
| Mac mini 4K60 SDR/444/8bit | 36601/36601/0 | 610.019695s /59.998063 | 坏0、重复51 | 本档原始采集通过 |
| Mac mini 1080p60 SDR/444/8bit | 36601/36601/0 | 610.019815s /59.998051 | 坏0、重复36 | 本档原始采集通过 |
| 自环1080p60 RGB full | 36601/36601/0 | 609.949290s /60.004988 | 静态图案，见下文 | 本档原始采集通过 |
| 自环4K60 RGB full | 36601/36601/0 | 610.009797s /59.999036 | 静态图案，见下文 | 本档原始采集通过 |

4K窗口的610个完整一秒桶中每秒有效帧59–61、ERROR均0；1Hz状态全部ready=1，
invalid_frames/stream_stops/faulted/stream_copy_bytes均0，source_changes始终为入场时的3。
有效帧IRQ→DQBUF：p50 0.121358ms、p95 0.167821ms、p99 0.187798ms、最大1.009081ms。
有源帧号重复，因此只证明有效完成帧率约60，不声称每帧都是新源内容。
证据 `fix3-4k-long*`、`fix3-4k-monitor.jsonl`、`fix3-4k.dmesg`。

1080切换先发现两类fixture陷阱：`CGDisplaySetDisplayMode` 的效果只在调用进程存活时保持，
进程退出恢复用户设置（见 [Apple API说明](https://developer.apple.com/documentation/coregraphics/cgdisplaysetdisplaymode%28_%3A_%3A_%3A%29)）；
保持进程后，CG桌面尺寸仍不能代表HDMI线上时序，RX实际仍为4K。这些尝试均未计作1080测试。
最终备份原RTK EDID，通过标准V4L2 S_EDID临时公布仅1080p60、SDR/8bit/48k立体声的
EDID（SHA256 `9c95c89c67d2b9aafea2112b1b9cf319bb8379aaca1f2162f0e1f8feaffd17bb`），
保留显示器身份和名称，不写用户持久配置。RX确认1920×1080、2200×1125、约148.497MHz
后才开始计时。结束已通过标准S_EDID恢复原始字节，SHA256重新匹配 `32c6a608…`，
Mac恢复原模式81（逻辑1920×1080、像素3840×2160、60Hz）。

1080窗口同为610个完整秒桶、每秒有效59–61、ERROR均0；全部1Hz状态ready=1，
invalid_frames/stream_stops/faulted/stream_copy_bytes均0，source_changes始终为入场时的5。
有效帧IRQ→DQBUF：p50 0.118737ms、p95 0.152561ms、p99 0.171256ms、最大0.916356ms。
实际NV12 stride1920、UV offset2073600、payload3110400、sizeimage3133440；
尾部对齐空间不能被误当成Y/UV间隙。证据 `fix3-1080-long*`、1Hz监控及同名dmesg。
基线十个完整秒桶（无像素读取）的有效帧37–60/s、ERROR 0–23/s；
带标记且受传输部分干扰的另段为31–59/s、ERROR 1–29/s，分别保留，不混为同条件对比。

用户通过need-user协议回复“已接自环”，读取后归档并删除回复。
TX通过标准DRM connector读到的EDID与RX原始RTK字节一致，两路ALSA PCM均closed，
整个自环窗口无音频回送。模式切换后的预期失锁/重新资格确认另计，不混入稳定窗口。

1080自环以KMS dumb buffer显示静态色彩图案，native V4L2直接DMA采集，不读像素计时；
开始和结束分别另取三帧完整原始NV12作颜色校验，最大8bit误差均1（门限2）。
不声称静态图案包含独立运动帧号。持续窗口中1Hz状态ready始终1，
invalid_frames/stream_stops/faulted/stream_copy_bytes均0，source_changes保持入场值17。
609个完整一秒桶有效59–61帧、ERROR均0，尾部不足一秒保留在原始数据。
有效帧IRQ→DQBUF：p50 0.117966ms、p95 0.156344ms、p99 0.173931ms、最大0.937134ms。
证据 `loop-1080-long*`、`loop-1080-monitor.jsonl`、`loop-1080.dmesg`，
前后原始图案及逐块误差为 `loop-1080-{start,end}*`。

4K自环通过标准atomic TEST_ONLY并设置594MHz/3840×2160p60 RGB full，
开始和结束各三帧图案最大误差均1。全部1Hz状态ready=1，invalid_frames、stream_stops、
faulted、stream_copy_bytes均0，source_changes保持入场值19。
有效帧IRQ→DQBUF：p50 0.117374ms、p95 0.155879ms、p99 0.172328ms、最大0.957206ms。
证据 `loop-4k-long*`、1Hz监控、同名dmesg及 `loop-4k-{start,end}*`。

## 结论适用范围

四个目标持续采集窗口均通过，合计146404个有效完成帧、约2440秒，0 ERROR和观测失锁。
真实源下已重现旧测量误拒绝，因此它不是自环独有问题；正式基线与颜色候选共有该RX算法，
没有证据将这类ERROR归为颜色候选独有回归。修复没有取消ERROR标志，仍拒绝测量超时、
有效时钟不匹配、真实5V/SQO/alignment丢失和租约几何/色彩变化。
运动标记仅校验三个高度，自环色彩图案仅作前后抽样，不将它们扩大为逐像素全程无损证明。

历史lowclock 36/38最后两次失败发生在QUERY阶段，分别ENOLINK和ERANGE，没有本轮
同等FDET/VALID现场；不能据此宣布同源或整套38项已修复。相关PHY/增益改动未合入本分支。
本记录只解除上述1080p60/4K60目标下的持续采集前置门禁，仍不是VD1透传验收或正式部署结论。
