# 2026-10-23：T7 H.264 启动链与安全微码审计

本页是[首次超时现场记录](2026-10-23-vdec-timeout.md)的出处明细；
源码相同或加载成功均不能替代正确帧验收。

以下厂商出处均相对 VM `~/src/linux/common_drivers`，候选相对独立 worktree
`~/src/linux-7.3-vdec`。厂商调用成功不等于候选已经解出一帧。

| 环节 | 厂商 5.15 证据 | 候选与判断 |
|---|---|---|
| 安全固件 | `drivers/tee/tee.c:626–644` 将 index/core/swap 直接传给 SMC；`drivers/media_modules/frame_provider/decoder/utils/amvdec.c:631–638,670–675` 将 mh264 映射为 H264_MULTI=15、legacy core=0 | T7 调 `0xb200000f(15,0,0)`，检查 a0，保存 secure scratch G；不复制受限固件字节 |
| 微码包 | 已有 `video_ucode.bin` 为 NEWP 包；H264_MULTI 描述长度 28672，不能把加密包直接减去 512 字节后 DMA | 继续走 TEE，原始微码加载及 swap 拷贝仅用于非 T7；加载返回零尚不能证明固件 ABI 一致 |
| AMRISC | `decoder/utils/amvdec.c:989–1023`：三次读 RESET0，写 bit12/11、零，三次读，MPSR=1 | 候选保持同序；启动前及超时读取 MPSR、MPC、IMEM/LMEM DMA 状态 |
| 中断 | 厂商 `arch/arm64/boot/dts/amlogic/mesont7.dtsi:2434–2451` 的 mailbox1 是 GIC SPI92/rising；`decoder/utils/vdec.c:6000–6035` 注册 wrapper ISR | 候选也用 SPI92；Linux virq 数字会变，比较 mailbox1 计数增量和硬/线程 ISR 次数 |
| mailbox | `decoder_v4l/h264_multi/vmh264.c:8268,8707–8710` 清 MBOX1、开 MASK | 候选使用相同 word 0x75/0x76，快照读 IRQ/MASK/FIQ_SEL，不读 CLR |
| 输入 FIFO | `decoder/utils/vdec.c:1954–1978` END=block.start+block.size−8，WP 为 payload+padding 并按 ring 回绕 | 发现旧 END=payload 尾，而 WP 已越过 END；改用整个 vb2 plane 的大小，保留 8 字节间隙并清零 1024 字节 lookahead |
| 启动命令 | `decoder_v4l/h264_multi/vmh264.c:4178–4210,11463–11529` 设置模式、INIT、输入、NAL、MMC，启动后发 SEARCH_HEAD | 厂商首次 INIT=0，stateless 前端原实现为 1 且由 host 注入 SPS/PPS；不能只改这个位宣称 ABI 兼容，须看固件进度与 IRQ |
| canvas/DDR | 候选 `h264.c:534–579,1610–1637` 仅在 slice-header IRQ 后配置 canvas；LMEM/workspace 先用 coherent DMA 分配 | 首次 header IRQ 前不能把 REC_CANVAS=0 单独判为故障；比较 MMC/MMU 位、LMEM/workspace 地址与 FIFO 进度，尚未证明像素输出权限 |

厂商非 MMU 路径清 `VDEC_ASSIST_MMC_CTRL1.bit3`，候选同样清除并关闭
MDEC MMU mux；没有额外构造页表。厂商有独立 MMU 固件 index=23，不能把它与
当前 index=15 的 legacy VLD/canvas 路径混用。

另复核已归档的[社区 v11 原文](https://lists.openwall.net/linux-kernel/2026/10/12/439)：
`aml_vdec_tee_fw.c` 先经 PTA `526fc4fc-7ee6-4a12-96e3-83da9565bce8`
预装去除前 32KiB 的固件，再以 index15/core0/**swap1** 加载，INIT 仍为 1。
T7 厂商 mh264 是 swap0，不能由入口相同推出固件协议相同。板上已有
`video-firmware-preload-khadas.service` 调用 `tee_preload_fw`；本轮恢复后的
7.3 journal 在 6.796 秒记录 skip header=0x8000、VDEC CA 1.0.16-g86c435e、
`tee preload video fw ok`。5.15 在 9.823 秒报告 VDEC TA 同版本、15 个固件、
336KiB 载入及 `TEE_Video_Load_FW success`。所以当前并非完全缺少预装；驱动
依赖这个现有服务，候选解码前核验服务退出成功及包哈希，不再重复上传。
SMC 没有返回 secure 微码版本/hash，仍须用执行进度和 IRQ 判断协议兼容性。
首轮归档 NEWP 的 `t7_h264_multi.bin` 元数据版本为
`v0.4.81.If60661d.7f05035`，包 SHA-256
`59e242bd63d6372d6462d2a2d6815e7bdea1a2cd12cd29fac093f38e73294e4b`；
这是包描述，不是本轮读出的 secure 代码版本。

## 现场寄存器差分

同一白名单 43/43 完整，地址为 `0xfe320000 + offset`，数值均为十六进制。
厂商列采于解码进程运行中，prepared 为候选首作业 AMRISC 启动前，timeout 为
后来首个超时作业 stop/reset 前；这是顺序快照，不能按同一帧/同一硬件阶段解释。

| offset / 寄存器 | 5.15 活动 | 7.3 prepared | 7.3 timeout |
|---|---|---|---|
| 0004 MMC_CTRL0 | ffff | ffff | ffff |
| 0008 MMC_CTRL1 | 32 | 32 | 32 |
| 0114 MBX_SSEL | 0 | 0 | 0 |
| 0118 DBUS_DISABLE | 0 | 0 | 0 |
| 01d0 MBOX1_IRQ | 0 | 0 | 0 |
| 01d8 MBOX1_MASK | 0 | 1 | 1 |
| 01dc MBOX1_FIQ_SEL | 0 | 0 | 0 |
| 0c04 MPSR | 0 | 0 | 1 |
| 0c18 MPC_P | 0 | 0 | 35b |
| 0c20 MPC_E | 0 | 0 | 359 |
| 0c84 CPSR | 0 | 0 | 5 |
| 0d00 IMEM_DMA_CTRL | 0 | 0 | 0 |
| 0d04 IMEM_DMA_ADR | 0 | 0 | 0 |
| 0d08 IMEM_DMA_COUNT | 0 | 0 | 0 |
| 0d40 LMEM_DMA_CTRL | 4000 | 4000 | 42fc |
| 2638 MDEC_PIC_DC_CTRL | 2a008 | 2a100 | 2a008 |
| 26c8 REC_CANVAS_ADDR | 30302 | 0 | 10100 |
| 2700 SCRATCH_0 | 1 | 3101000 | 1 |
| 2704 SCRATCH_1 | 81039828 | 0 | 81039828 |
| 2708 SCRATCH_2 | 18023 | 1 | 8000 |
| 2710 SCRATCH_4 | 1 | 1 | 1 |
| 2714 SCRATCH_5 | 81039828 | 81039828 | 81039828 |
| 2720 SCRATCH_8 workspace | 9f6c0000 | c0510000 | c0510000 |
| 2724 SCRATCH_9 | 0 | 10f04 | 0 |
| 2728 SCRATCH_A | 0 | 0 | 0 |
| 2738 SCRATCH_E | 1e20 | 4088 | 2054 |
| 273c SCRATCH_F | 10 | 10 | 10 |
| 2740 SCRATCH_G secure swap | 6a68000 | 6a68000 | 6a68000 |
| 2748 SCRATCH_I | 7 | 0 | 11 |
| 274c SCRATCH_J DPB_STATUS | 2 | 0 | f3 |
| 2754 SCRATCH_L LMEM | 9f6ac000 | 3f12000 | 3f12000 |
| 3020 POWER_CTL_VLD | 1250 | 250 | 1250 |
| 3060 VLD_DECODE_CONTROL | 0 | 0 | 0 |
| 3068 VIFF_BIT_CNT | 1 | 20440 | e84f |
| 3100 FIFO_START | 9f900000 | c0000000 | c0080000 |
| 3104 FIFO_CURR | 9f9119a8 | c000000c | c0080354 |
| 3108 FIFO_END | 9faffff8 | c00563f8 | c00d63f8 |
| 310c FIFO_BYTES_AVAIL | 1d8 | 1f4 | 1ac |
| 3110 FIFO_CONTROL | 8200 | 11063e | 11063e |
| 3114 FIFO_WP | 9f911da0 | c0004488 | c0082450 |
| 3118 FIFO_RP | 9f911b80 | c0000200 | c0080500 |
| 311c FIFO_LEVEL | 220 | 4288 | 1f50 |
| 3120 FIFO_BUF_CNTL | 2 | 2 | 2 |

厂商 mailbox1 从 0→20（活动采样）→1223（EOS）；候选从 0→43，硬 IRQ 和
线程 ISR 各 43。候选 MPSR、PC、SPS scratch 及 VLD 指针都有进度，已经越过
“微码不运行/没有中断”的假设。prepared 与 timeout 来自不同输入缓冲，不能
用两个绝对地址的差值当消费量；timeout RP/CURR 均在当前 ring 内前进，WP 未越界。

两侧 MMC_CTRL1.bit3=0、DBUS_DISABLE=0、secure swap 相同，未发现本组寄存器
中的 MMU 模式错配。厂商帧间停 AMRISC/关 MASK，解释活动进程中的零值；候选
最终 f3 是主机发出的 DECODE_NEWPIC，不是成功完成。REC_CANVAS 索引不同来自
分配顺序，不能只把候选改成 0x30302；必须核验其 LUT 与实际 vb2 DMA 目标一致。

输出全零仍未定位到唯一原因。离线复核 candidate `h264.c:1217–1240`：单平面
NV12 的 UV 地址为 Y+fb_size[0]，不是误取不存在的 plane1。厂商
`drivers/media/common/canvas/canvas.c:340–397` 的 probe 也没有显式 canvas
功能时钟启用，因此不能仅凭主线 canvas 没有 clocks 属性就判定缺门控。
两侧 LUT 数据布局相同，但此次未读取 LUT 表项和原始 NV12 目标内容，也未逐帧
记录 LMEM/DPB 状态；这些是下一轮需要补的观测，不能声称已经证实像素 DMA 安全
权限错误或固件 swap 参数错误。
