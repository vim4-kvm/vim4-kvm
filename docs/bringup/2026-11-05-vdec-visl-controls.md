# 2026-11-05：H.264 剩余失败的 visl 离线控制采证

17 条残余 Fail 中，**13 条隔行流及 CAWP5 都被 Khadas parser 漏掉最后一个 slice**。
在 arm64 QEMU 中只换官方 Ubuntu 同版本 parser，14 条全部恢复末请求；MR3/MR4/MR5
两种 parser 均提交 300 个请求。它们因此分成两条调查线，不能继续把特性分组直接当根因。
这不是像素验收：visl 只生成测试图案，14 条是否还存在驱动像素错误须另验。

内核 topic `vdec-avc-residual` 从 `c99c3eddea02823a6b958d16e35ec7d7fd0ccc0d` 建立，
T7 驱动未修改、无修复提交。全程未接板、未排板票、未改变系统库。

## 身份与可复查的原始证据

工作目录 `build/hwdecode-parity/avc-residual/visl/`：

- `inputs.json`：17 条输入路径及 SHA-256；源来自锁定 fluster 缓存。
- `kernel.config`、`evidence-kernels.txt`：QEMU 配置、两种 Image 哈希和唯一临时差异。
- `rootfs-manifest.json`：初始 rootfs 的逐文件来源/哈希；后续替换依赖见
  `khadas-dependencies.sha256`、`ubuntu-full.sha256`，不能把初始清单当作后续组的清单。
- 各组 `*.controls`、`*.stats`、`*.gst.log`、`status`、`uart.log`：完整原始输出。
- `comparison.json`、`weights.json`：一次性分析结果；分析脚本只在 build 下，不是新增驱动测试。
- 父目录 `*.trace.log`：FFmpeg trace_headers 原始位流解析，`MR3-mmco.log` 为软件参考解码的 MMCO 日志。

Khadas deb 来自其 noble 仓库，包 SHA-256
`8b3050f5b925c541349027572acca579755b6bf8b373f1c2c2858ebc67d4c3ff`。
提取 parser SHA-256 `2da88e7aa1c9bd39a74f5cf6806d24f1c7cd80ec11aab712b25f0975e89bb017`，
私有 v4l2codecs SHA-256 `ca9b5d41cd5cb4e1971778e3db99171c66bc78a24a6b9bcd906cfe7de2e8f601`，
均与 [r56 板端身份](2026-11-05-vdec-r56-fmo-parser.md) 相同。
官方 Ubuntu parser SHA-256 `6b8523110912868c168e1c5b85be2883fbafd925c4996bc1069b65915e1d7cf2`，
下载版本/来源与 [r55](2026-11-05-vdec-r55-parser-identity.md) 相同。
guest 基础 GStreamer/GLib 使用 VM 的库，不宣称整个用户空间与板端逐文件相同。

## visl 与实际驱动的差异

源码 `drivers/media/test-drivers/visl/visl-core.c` 默认 slice-based、无 start code；
T7 `aml_vdec.c` 固定 frame-based、Annex B。GStreamer 从 G_EXT_CTRLS 读取这两项，
不是自行固定模式；frame 模式不提交 SLICE/PRED_WEIGHTS，不能将 visl 输出的默认零值
误认为板端提交了零权重。`visl-video.c` 声明 HOLD_CAPTURE_BUF，与当前 T7 一致。
visl 能接受场请求，但没有真实场像素、colocated MV、canvas 或微码行为。

先运行未改 visl 的 slice 模式，再仅把上述两个默认值改成 T7 模式运行 frame 组。
`frame-defaults.patch` 保存该采证差异；构建后已撤回，不进入 topic 提交。
初次构建遗漏 V4L_TEST_DRIVERS 父选项、QEMU 默认 NIC 缺 ROM、一次输入清单未生成的失败
均保留日志；有效结果只引用下表五组。

| 组目录 | parser | v4l2codecs / codecs、codecparsers 依赖 | 模式 |
|---|---|---|---|
| all-slice2 | Khadas | 板端同 SHA 私有插件 / 官方源码构建依赖 | slice |
| all-frame | Khadas | 同上 | frame |
| khadas-frame | Khadas | 同 SHA 私有插件 / Khadas 包依赖 | frame |
| ubuntu-parser-frame | 官方 Ubuntu | 同 SHA 私有插件 / Khadas 包依赖 | frame |
| ubuntu-full-frame | 官方 Ubuntu | 官方 Ubuntu 插件及依赖 | frame |

五组各 17 条进程均返回 0，逐流 trace 的 overrun、commit overrun、dropped events 均为 0。
返回 0 只表示用户态管线完成，不等于帧数完整或解码正确。
[逐流请求数/输入哈希](data/2026-11-05-vdec-visl-controls.csv) 显示：前三组的 14 条各少一个
末 slice，后两组全部恢复；三条 MR 始终 300/300。单变量 parser 组足以定位末请求差异。

17 条原始位流与 slice/frame 两组已提交请求共 **102041 项公共标量及 field 位比较零差异**；
两种模式公共 SPS/PPS/scaling/decode_params/DPB（忽略跨进程 timestamp 数值）一致。
比较按解码顺序，只覆盖实际提交的前缀；缺失尾 slice 单列，没有用 zip 截短掩盖缺失。
该计数不包括 MMCO 重演、POC 推导、完整参考列表及所有数组，不应表述为全部控制逐字段已证明。
CAWP5 slice 模式有效 P slice 的 luma/chroma 权重、偏移及分母 **5020 项零差异**；
frame 模式权重仍由原始位流交给微码，不由主机 PRED_WEIGHTS 控制下发。

## 厂商差异与 LTR 下一步

对照厂商 `common_drivers` 提交 `31619c527655514b4c89516ef609b6db1dd47db6`，
路径 `drivers/media_modules/frame_provider/decoder/h264_multi/`：

| 路径 | 已确认的差异或一致点 | 结论边界 |
|---|---|---|
| vmh264.c config_decode_buf / h264.c h264_config_decode_buf | 厂商以每场 is_long_term 分别设置 buffer info bit4/5；当前驱动对 LONG_TERM 一律置两位，current canvas 分支不采首场 DPB 的 LTR | 是场参考差异，但 MR3/4/5 都是逐行帧，不能解释这三条 Fail；不为此盲提交 |
| h264_dpb.c reorder_long_term / 当前 reorder_long_term | 都按 LongTermPicNum 查找、插入并从后续列表去重；当前从未重排副本查找，避免覆盖源 | 静态未发现三条 MR 的确定性差异，继续按请求核 MMCO 与列表 |
| h264_dpb.c update_pic_num / V4L2 reflist builder | 短期 FrameNumWrap 与长期 LongTermFrameIdx 分开；GStreamer LTR 的 pic_num/frame_num 映射符合此语义 | MR3 第4个解码图像后 frame1 转 LT0，下一请求 DPB 的 POC2、pic_num0、frame_num0 可对应；不代表全流 MMCO 已验 |
| 权重 | 厂商通过原始 slice/微码解析，不存在应照搬的逐请求主机权重表写入 | CAWP5 已有用户态末 slice 问题，不能以未写 PRED_WEIGHTS 为驱动缺陷 |
| field/MBAFF colocated | MV 偏移分支、nearest POC 选场已对照；MODE_8X8_FLAGS 是固件解析值，不能直接把 SPS 位位置当固件位位置 | visl 不验证这些硬件路径，保持待像素证据 |

优先继续 MR3/MR4/MR5 的 MMCO/长期参考逐请求分析。当前没有经证明的修复，因而没有
新增 KUnit 或 W=1/sparse/checkpatch 修复验证可报告；QEMU visl 构建不替代这些门禁。
14 条先按[待批准板窗](2026-11-05-vdec-parser-ab-plan.md)取得两组像素输出。
