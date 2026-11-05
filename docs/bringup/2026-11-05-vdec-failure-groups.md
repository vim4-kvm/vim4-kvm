# 2026-11-05：标准码流失败特性聚类

首要组是 H.264 的隔行 SPS：52 条全部像素 Fail，源码直接拒绝此 SPS 标志。
其次是多 slice：18 Fail、1 内核 Timeout，T7 的非首 slice 也有显式拒绝分支。
这两组有主机驱动侧缺口，不能归类为固件做不到。MPEG-2 没有一个特性能够
单独解释全部 19 条像素失败，须继续区分头部/矩阵传递与图像输出。

统计来自[完整结果及逐流清单](2026-11-05-vdec-full-conformance.md#完整结果与证据边界)。
原始 H.264 为 73 Fail/4 Error，其中三条 Error 有内核超时证据，表中单列 Timeout。
**分组可以重叠，不得把各行相加当失败总数。**

## 特性证据

在宿主对锁定输入执行 FFmpeg `trace_headers`，复制码流而不解码像素；逐输入
先核 SHA-256。扫描完整文件，保留每个字段的取值集合、每个 packet 的 slice
数量及 first_mb 顺序。分析不在内核中新增解析，不改变输入，也不新增 Python
测试。原始压缩 trace 在 `build/hwdecode-parity/features.tar.gz`，特性和分组
分别为 `features-complete.json`、`conformance-groups.json`，生成摘要为
`conformance-summary.log`。提取/汇总脚本在同一目录。

178 条中有 8 条 trace 非零退出；这些记录只证明已成功读出的字段，不用缺失
字段推断“不含该特性”。H.264 为 FM2_SVA_C；MPEG-2 为 MEI、MEI.stream16、
teracom_vlc4、tcela-16、tcela-18、tcela-19、ccm1。

## H.264

| 特性 | 通过 | Fail | Error | Timeout | 代表失败码流 |
|---|---:|---:|---:|---:|---|
| SPS 允许隔行（frame_mbs_only_flag=0） | 0 | 52 | 0 | 0 | cabac_mot_fld0_full、CAMA1_Sony_C |
| 实际 field picture | 0 | 31 | 0 | 0 | cabac_mot_fld0_full、CABREF3_Sand_D |
| MBAFF enabled | 0 | 27 | 0 | 0 | cabac_mot_mbaff0_full、CAMA1_TOSHIBA_B |
| 实际混合 frame/field（PAFF） | 0 | 13 | 0 | 0 | cabac_mot_picaff0_full、cama1_vtc_c |
| 一个 packet 中多 slice | 0 | 18 | 0 | 1 | BA1_FT_C、BASQP1_Sony_C、CABACI3_Sony_B |
| FMO（num_slice_groups_minus1>0） | 0 | 1 | 1 | 1 | FM1_BT_B、FM2_SVA_C、FM1_FT_E |
| 长期参考标记/MMCO 3 或 6 | 2 | 8 | 0 | 0 | MR1_BT_A、MR3_TANDBERG_B、MR4_TANDBERG_C |
| SPS cropping | 0 | 1 | 0 | 0 | CVFC1_Sony_C |

完整 trace 中没有发现同一 packet 内 first_mb 倒退，不能把多 slice 自动称为
ASO。当前套件未观察到 8×8 transform/scaling-matrix 标志；FR-EXT High 未运行，
不能由此声称覆盖或支持这些特性。

### BA1_FT_C 与覆盖面最大的两组

BA1_FT_C：profile_idc=66，frame_mbs_only_flag=1，num_slice_groups_minus1=0，
一个 packet 最多 12 个 slice，没有观察到 slice 顺序倒退。因此它属于逐行
多 slice，不属于 FMO 或场编码。

当前内核 `e7729c116550` 的
`drivers/media/platform/amlogic/vdec/h264.c:1868` 在
`aml_h264_get_stateless_ctrl_ref()` 直接拒绝 `FRAME_MBS_ONLY` 未置位的 SPS，
这解释了隔行组根本未获得完整解码支持；不应只删检查就宣称支持。还要核对
field/MBAFF 的尺寸、参考帧/场标志、POC、colocated MV 地址、两个场共享目标
缓冲与完成时机，再用受影响标准流证明行为。

同文件 `h264_threaded_isr_func():1734` 在 T7（has_dbus_ctrl）上遇到
first_mb_in_slice 非零即走 header_error。此分支与 BA1_FT_C 的实际头部特性
直接矛盾。修复必须保持一个 picture 内 canvas/参考缓冲的生命周期，不能
简单移除保护后走旧的逐 slice 释放/重新分配逻辑。需单独一组提交、单独验证。

剩余逐行单 slice 失败还包括 CAWP5_TOSHIBA_E、HCBP1/2_HHI_A、HCMP1_HHI_A、
LS_SVA_D、MR3/4/5_TANDBERG，不能套用上面两个原因。长期参考组也有两条通过，
须进一步查 DPB/POC 与参考列表变更。先处理最大隔行组，再收敛剩余根因。

## MPEG-2

| 特性 | 通过 | Fail | Error | 代表失败码流 |
|---|---:|---:|---:|---|
| interlaced sequence | 17 | 19 | 0 | att、mei_2stream、sony-ct4 |
| 自定义量化矩阵 | 13 | 16 | 0 | att、mei_2stream、sony-ct4 |
| nonlinear qscale | 12 | 12 | 0 | mei_2stream、sony-ct4 |
| alternate scan | 10 | 14 | 0 | mei_2stream、sony-ct4 |
| 实际 field picture | 3 | 6 | 0 | sony-ct4、sony-ct1、sony-ct2 |
| 头部 trace 不完整 | 0 | 1 | 6 | teracom_vlc4、MEI、tcela-16 |

att：progressive_sequence=0、picture_structure=3（帧图像）、progressive_frame=0、
frame_pred_frame_dct=0，加载 intra/non-intra 自定义矩阵；q_scale_type=0、
alternate_scan=0。它不是两个独立 field picture 配对的用例，也不是 alternate
scan 用例。其 ISO 参考比较有 23,959 个超容差位置。

核对 `mpeg12.c:114` 的 `mpeg12_write_headers()` 与匹配私有 GStreamer 的
`gstv4l2codecmpeg2dec.c:477,648`：两端都有矩阵传递和 picture-level 更新路径，
不能仅凭 att 带矩阵就断言漏传。下一步需比较实际控制值、重建头部及矩阵变化
时机；目前未证明是哪一端错误。自定义矩阵、alternate scan、field picture
都有通过项，修复应由具体差异驱动，不改全局容差或跳过失败用例。

## 后续验证约束

每组离线修复独立提交，正文/签名、format-patch strict checkpatch、W=1 与有效
sparse、模块/内建检查按规范执行；硬件未跑的提交不写成实板已验证。攒成同一
候选后按受影响码流复验，同时带上此前通过的相关对照。5.15 暂停，HEVC 的
ACTION/reset 顺序实验保持独立草稿，与这一轮的功能修复区分记录。
