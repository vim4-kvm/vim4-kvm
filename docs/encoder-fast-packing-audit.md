# 厂商编码库 fast packing 审计（2026-10-25）

本轮只读源码、厂商包和已有测量文件，未访问板子、构建或部署候选。
`lowLatencyMode=1` 是可单独验证的候选；尚无硬件收益、码流一致性或画质验收结论。
测量背景见 [下游分段记录](bringup/2026-10-25-video-downstream-latency.md)，
本结论限该记录中的 5.15 厂商编码路径，不能据此解释与 7.3 的全部差异。

## 已有测量能确认什么

One-KVM、4K60 SDR、30Mbps；端点为插件编码入口到完整编码输出。
H.264 1019 帧、H.265 842 帧对应已有详细记录，H.265 另有 1181 帧对照。

| 段，平均 ms | H.264 | H.265 |
|---|---:|---:|
| 编码入口 → 完整输出 | 12.499 | 13.294 |
| amvenc API 调用 | 12.417 | 13.212 |
| WAIT_INTERRUPT ioctl | 12.085 | 12.874 |
| API 中其余 CPU 工作 | 0.266 | 0.273 |
| API 返回 → 插件输出复制等 | 0.052 | 0.053 |

重新解析已有 `logs/down-{h264,h265,h265-control}.events.bin`：所有匹配的
1019/842/1181 帧都是 DMA_TYPE=3、单平面、有效输出，每帧恰好一次 WAIT、
两次 CLOCK_GATE、一次 CONFIG_DMA、CACHE_INV、UNMAP，无多次等待重试。
API 开始到 WAIT 开始平均 0.148/0.147/0.123ms，WAIT 返回到 API 返回
平均 0.183/0.191/0.175ms。当前没有每帧原始图像 CPU 复制的证据。

`common_drivers/.../encoder/multi/vpu_multi.c:1373–1461` 的 WAIT 使用条件等待，
中断已到则直接返回；timeout 是上限，并非固定休眠。硬中断先推入队列，再由
tasklet 唤醒用户线程（约 805–990、781–805 行）。现有探针没有 IRQ 到达时间，
所以这 12ms 包含硬件执行、IRQ/tasklet/线程调度，不能全部称为硅片计算时间。
时钟 ioctl 实测合计约 0.024ms，调用 `clk_enable/disable`，没有每帧重设 PLL。
DMA config/unmap 合计约 0.027ms，缓存或映射重构优先级低于硬件等待。

## 厂商包、源码身份与 ABI

[Khadas 官方编码说明](https://docs.khadas.com/products/sbc/vim4/applications/hardware-encoding)
链接的公开仓库为 `numbqq/encoder_libs_aml` 的 `yocto-202311/multiEnc`。
审查基线 `4c38af2b398d00a906c26aa166d630a9f73d3f9e`；同时核对包含
2024 年接口更新的 `ceaca278be7a0d86b2826ceb77e751209c995817`。

| 证据 | 已核对内容 |
|---|---|
| `packaging/ubuntu/downloads.lock.json` | libamvenc `0.2-202406~noble`；SHA256 `bba5b248f0111bed1fde5c6996f5272eb6d4b03a270323dcadc20cca9e0aba59` |
| `logs/preflash-backup-20261013-123403/home-and-packages.txt:517` | 历史安装清单 libmultienc `0.7-202406~noble` |
| 官方 noble Packages 与下载包 | 同版 libmultienc；SHA256 `629aff8c5d106b4fa6b1a3c0d5e8332cc1f9ec9a3b9987c75c83f4facbd6fdae` |
| libamvenc 包头文件 | 与 `logs/down-amvenc.h`、ceaca278 的 amvenc.h 字节一致 |
| libmultienc 包头文件 | vp_multi_codec_1_0.h 与 ceaca278 字节一致；包内有 libvpcodec.so、libamvenc_api.so |
| 包内库字符串 | 构建目录含 `yocto_202406_an400_20240704`；不是精确源码提交证明 |

原始包：[libamvenc](https://dl.khadas.com/repos/vim4/pool/main/liba/libamvenc/libamvenc_0.2-202406~noble_arm64.deb)、
[libmultienc](https://dl.khadas.com/repos/vim4/pool/main/libm/libmultienc/libmultienc_0.7-202406~noble_arm64.deb)、
[Packages 索引](https://dl.khadas.com/repos/vim4/dists/noble/main/binary-arm64/Packages.gz)。
libmultienc 尚未被上述下载锁固定；10/13 清单不能证明 10/25 未换库，
实测前仍须记录实际加载库哈希。公开源码和 ABI 匹配也不等于厂商二进制完全同源。

旧 yocto-202311 的 amvenc.h 缺少 `level` 和 crop 字段，直接替换 wrapper 会破坏
结构布局；更新到 2026 分支又包含较新的 SEI 接口，不能任意混编。
应保留当前 libamvenc wrapper 和匹配的公开 ABI，只制作单独 libvpcodec 候选。
ceaca278 与旧基线的 `AML_MultiEncoder.c` SHA256 均为
`186b906ebfd9994373f7fc94e760bca8560d8ac1e6e2184882f37038ea72304f`。

当前源码调用链为插件同步调用 amvenc → wrapper 动态加载 libvpcodec →
libamvenc_api 的 VPU/VDI 接口 → `/dev` 厂商驱动。`vpuapi.c:40,213–228`
将 `chagall.h` 内的固件数组用于 VPU_Init；不要为测试此位同时更换底层库或固件。
源码有 Amlogic 的再分发限制声明，本轮未将厂商源码复制进项目。

## 单 bit 候选及陷阱

以下链接固定在审查提交，行号以该版本为准：

- [AML_MultiEncoder.c:794–820](https://github.com/numbqq/encoder_libs_aml/blob/ceaca278be7a0d86b2826ceb77e751209c995817/multiEnc/amvenc_lib/AML_MultiEncoder.c#L794)：默认码流缓冲 2MB、lineBufIntEn=1、lowLatencyMode=0。
- [vpuapi.h:4159](https://github.com/numbqq/encoder_libs_aml/blob/ceaca278be7a0d86b2826ceb77e751209c995817/multiEnc/vpuapi/include/vpuapi.h#L4159)：bit0 为 fast bitstream-packing，bit1 为低延迟中断；注释限定 VP5。
- [enc_driver.c:65–75](https://github.com/numbqq/encoder_libs_aml/blob/ceaca278be7a0d86b2826ceb77e751209c995817/multiEnc/vpuapi/enc_driver.c#L65)：521 与 521C 映射到同一个 PRODUCT_ID_521。
- [enc_driver.c:1044–1045](https://github.com/numbqq/encoder_libs_aml/blob/ceaca278be7a0d86b2826ceb77e751209c995817/multiEnc/vpuapi/enc_driver.c#L1044)：创建实例时将 `(lowLatencyMode<<7)|(lineBufIntEn<<6)|endian` 写入 **VP5_CMD_BS_PARAM**。
- [product.c:594–612](https://github.com/numbqq/encoder_libs_aml/blob/ceaca278be7a0d86b2826ceb77e751209c995817/multiEnc/vpuapi/product.c#L594)：ring-buffer 的 521 专门要求包括 16 字节地址对齐、至少 64KB；当前 line-buffer 路径不能套用这些 ring 条件。
- [AML_MultiEncoder.c:2334–2345](https://github.com/numbqq/encoder_libs_aml/blob/ceaca278be7a0d86b2826ceb77e751209c995817/multiEnc/amvenc_lib/AML_MultiEncoder.c#L2334)：FULL/LOW_LATENCY 中断路径读取指针后直接返回 AMVENC_FAIL。

`mode=1` 仅开启 fast packing，不开启低延迟中断；host 侧未同时修改码率、QP、
GOP 或编码质量 preset。所查验证逻辑没有 mode1 专属缓冲条件或 521C 禁用判断。
通常的 AXI 地址对齐、容量 1024 倍数、足够容纳完整 AU 的条件仍需保持。
这只是源码所见：未找到公开芯片手册独立保证 521C 固件对 bit0 的行为、吞吐或
码流逐比特等价，不能把未发现约束写成已证明没有约束。

**不能直接启用 mode2/3。** 当前 wrapper 不支持持续排空部分码流，接到低延迟
中断会失败；sample 的组件式编码器有另一套排空流程，不能只照搬命令行参数。
同理，设置 multi-slice 只改变 NAL 分片，当前 API 仍到整帧完成才交付，不能据此
宣称编码与网络发送已流水。`useRecommendEncParam=2/3` 分别是中等/较低画质
的速度选项，不列为等画质优化；已有失败的 750/800MHz 超频不再作为候选。

## 已有日志的离线回归

对 `logs/down-{h264,h265,h265-control}.detail-rows.json` 的同帧数据做最小二乘：
`WAIT_ms = intercept + slope × bytes_per_frame/1024`，未重跑硬件。

| 数据 | n | intercept ms | slope µs/KiB | Pearson r |
|---|---:|---:|---:|---:|
| H.264 | 1019 | 11.6247 | 8.1301 | 0.96795 |
| H.265 | 842 | 12.4090 | 8.2407 | 0.98648 |
| H.265 对照 | 1181 | 12.4548 | 7.9250 | 0.98848 |

平均 AU 的网络字节数约 58–60KB，回归中的尺寸相关项约 0.45ms。
它提示大帧值得单独分桶，但不能据此预测 mode1 能节省 0.45ms，或消除 12ms 主体：
画面复杂度同时影响编码耗时与字节数，bytes_per_frame 包含 RTP/加密等网络开销，
截距是数据范围外的外推，连续帧也非独立随机样本。这三段不是固定输入模式 A/B，
H.265 的 90 秒段带 Chrome trace 与双端抓包，对照关闭这两项，不能把其差值
解释成优化效果，也不能用 90 秒诊断段进行验收 P99 比较。
相关系数不提供硬件因果证据。

同一板端时钟使 WAIT 分段不受 Mac/板子时钟对齐误差影响；但 ioctl 包装和探针
有观测开销，且没有硬件结束/IRQ 的直接时间戳。API 内其他 CPU 工作只有约
0.27ms，即使全部消除也不是 12ms 级收益。IRQ 唤醒的份额只能另行上板跟踪。

## 下一步硬件 A/B 协议（尚未执行）

1. 独占硬件，先记录运行内核、插件、实际加载的三层厂商库与固件身份/哈希、
   Wave 时钟、温度和当前配置。保留恢复路径；候选用私有库搜索目录加载，不覆盖系统库。
2. 先做默认 mode0 的重建库与原厂库对照。只有固定录制 NV21 输入的完整输出、
   帧数、错误和时序足够一致，才测单独将 `lowLatencyMode=0` 改为 `1` 的候选。
   保持原有公开 ABI、libamvenc_api、固件和所有其余参数。
3. H.264/H.265 分开，对同一录制帧序列按 0→1→0→1 重复多轮，预热后计数。
   覆盖文字/静态、连续运动和高复杂度，保留 IDR、主动请求关键帧及行刷新负载；
   保持分辨率、实际60fps预算、码率、QP、GOP和输入像素不变。
4. 同时记录编码入口、API、WAIT、输出，按帧型/字节数分桶报告 p50/p95/p99/max、
   吞吐、错误和温度。文件回放可能慢于实时；其吞吐不能充当实时或端到端结果。
5. 同模式多轮先检查码流确定性，再比较两模式的逐帧长度/哈希、平均QP、帧型、
   SPS/PPS/VPS、分辨率、帧顺序和完整解码。若码流不同，必须对相同源帧比较解码像素、
   文字细节及 PSNR/SSIM，不能仅凭成功解码或平均码率认定等画质。
6. 硬件回放通过后，回到实际 DMA 采集与 One-KVM 浏览器验证：同连接配置、同运动
   标记、同观察开销，复测大帧和呈现间隔尾部、重连、PLI/FIR、重复启停及错误恢复。
   任一失败先恢复 mode0；成功也须分别报告编码段收益与端到端收益。

离线可检查 ABI、单 bit 配置差异、WAIT 重试行为和上述日志统计；mock 或桌面
benchmark 不运行 WAVE521C，不能量化 mode1 的硬件性能、固件兼容性或画质。
IRQ→tasklet→用户态的直接分段，以及真正的 fast packing A/B 均仍待上板。

## 相关记录

- [编码实验记录](bringup/2026-10-13-encoder-controls.md)：旧插件降级、帧率重建、QP 与行刷新验证。
