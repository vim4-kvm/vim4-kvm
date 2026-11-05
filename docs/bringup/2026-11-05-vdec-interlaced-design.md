# 2026-11-05：H.264 隔行支持设计与离线实现

按协调决定先验证多 slice；隔行 SPS 的 52 条失败排在其后。这是完整的新能力，
不能只删除 `FRAME_MBS_ONLY` 检查。以下保留设计审查材料，并记录已完成的离线
准备提交；隔行入口仍关闭，尚未实板验证。分组证据见[失败聚类](2026-11-05-vdec-failure-groups.md)。

## 已完成的离线准备

| 内核提交 | 改动 | 实际验证 |
|---|---|---|
| `d85738cf7a151` | 先把 map-unit 高度展开为帧高，再做 canvas 对齐；序列面积使用完整帧宏块数 | arm64 QEMU KUnit 18/18 |
| `7eca35df43339` | 保留参考项 fields、对应场 POC 和长期参考标志；列表容量覆盖 32 个场参考 | arm64 QEMU KUnit 19/19 |
| `50378b37858bb` | 当前 POC 使用标准 reflist builder 的结果，frame 取 Min，field 取对应场；寄存器依次写 current/top/bottom | arm64 QEMU KUnit 20/20 |
| `549b933bc90d2` | 按原始 frame/field/MBAFF 结构计算 colocated MV 读写偏移；分配 MV 槽时保存结构 | arm64 QEMU KUnit 22/22 |

四个提交分别完成 W=1 模块/内建构建、实际 sparse CHECK，以及对 format-patch
输出运行 strict checkpatch。修改私有头声明的提交也运行 kernel-doc。原始日志位于
`build/hwdecode-parity/interlaced/`，分别以 `dimensions-`、`references-`、
`current-poc-`、`mv-` 为前缀；KUnit 原始串口为 `*-qemu.log`，结果为 `*-result.json`。
内建检查有既有的 arm64 vgetrandom 声明告警，vdec 检查无告警；没有修改 DT binding。
参考列表首次构建发现初始化循环越界，修正后重跑通过，失败日志保留为
`references-kunit-initial-build-failure.log`。

MV 偏移使用未做 canvas 对齐的 SPS 宏块宽度，将 field 行与 MBAFF pair 换算为
MV 槽位，再按普通/compact 布局换算字节。计算用宽整数，读写两侧均要求至少
一个完整 MB 单元落在缓冲内。KUnit 调用生产 helper，覆盖跨结构的非零行/列、
compact 最后一个合法单元、越界和大输入；图像结构由标准控制决定，保存到
已分配的 MV 槽，避免读参考时根据当前 SPS 猜结构。初轮编译发现参数名与内核
`current` 宏冲突，改名后重跑通过；原日志为 `mv-kunit-initial-build-failure.log`。

本提交只准备 MV 布局，尚未完成配对场视图：vendor `h264_dpb.c` 的
`dpb_combine_field()` 创建 frame view 时仍置 `coded_frame=0`，复用 top field
的 MV 槽。后续参考寄存器接线必须结合保存的原始布局与 reflist.fields 选择
field view，不能把合成帧误标为原生 frame，也不能只用首次分配场的奇偶性。

`50378b37858bb` 修正参考帧取 Min、当前帧仍取 top 的不一致：bottom < top 时
会影响 colocated POC 距离。测试调用真实参考列表配置函数，覆盖负 bottom POC、
top/bottom field 与 IDR；IDR 判断改为位标志判断，且在提前返回前完成当前 POC
计算。canvas/MV 仍以 top POC 查找身份，留待 timestamp 生命周期改动处理。

### 下个窗口的 POC 对照边界

对保存的 JVT-AVC_V1 全部特性 trace，结合全套结果与 r47 的通过结果，筛选
“此前通过、frame_mbs_only=1、包含 B slice、bottom POC 偏移非零”的交集为空。
一次性筛选脚本与输出保存在 `build/hwdecode-parity/interlaced/select-bottom-poc.py`、
`bottom-poc-controls.json`，扩展检查结果在 `all-bottom-poc.json`。

- `MR5_TANDBERG_C` 是逐行，top-to-bottom offset=-5，但只有 I/P slice，且之前失败，不能算所要求的 B 帧回归对照。
- `cama1_vtc_c` 包含 B slice、delta_pic_order_cnt_bottom=-1，但 SPS 允许隔行，作为隔行负偏移验收项，不冒充已通过的逐行对照。
- bottom POC 等于或大于 top 时，Min 与原来取 top 相同，因此这类已通过码流在此处的计算值不变。这是代码推理，不是新增实板通过记录。
- 下个窗口仍保留已通过的逐行 B 帧和多 slice 对照；按协调决定，不为交集为空硬凑码流。待 JVT-FR-EXT 子集运行时补负偏移逐行 B 帧；KUnit 不能替代这项实板像素证据。

本阶段没有上板。下一候选先跑三节点带流 compliance，再跑隔行受影响码流和
逐行/多 slice 对照；timestamp 所有权、配对场参考视图和 HOLD/sequence 尚待实现。

当前内核没有 `v4l2_m2m_release_capture_buf()`。HOLD 释放沿用
`v4l2_m2m_buf_done_and_job_finish()`、核心的 timestamp 不一致处理，以及
`v4l2_m2m_ioctl_stateless_decoder_cmd()` 的 FLUSH 路径。已审的 sequence 方向是
首次使用新的 CAPTURE 缓冲时编号，第二场复用 held 缓冲的编号；不能仅在第二场
完成时递增，否则核心直接释放时会漏计。该改动目前只在 build/ 准备，未入内核提交。

## 已定位的缺口与拟定边界

源码基于 `e7729c116550`，多 slice 提交 `adadb95ff898e` 没有开放隔行入口。

| 路径 | 当前行为 | 拟定改法及验证 |
|---|---|---|
| `h264_build_sps_params()`、控制合法性 | map-unit 高度当作 frame 高度；入口拒绝隔行 SPS | 按 `2-frame_mbs_only_flag` 计算帧高后对齐，区分固件 seq_info 的 map-unit 表示与 canvas/MV 的实际帧尺寸；KUnit 检查最大尺寸、对齐和越界 |
| `config_p_reflist()` / `config_b_reflist()` | 丢弃 `v4l2_h264_reference.fields`，固定 top POC；数组仅 17 项 | 使用标准参考列表构建器的场选择，容量覆盖 32 个场参考；按 top/bottom/frame 计算 POC、PicNum 和长期参考编号；对真实纯逻辑加 KUnit |
| canvas 与 colocated MV 所有权 | 按 top POC 识别图片，每个 request 分配当前 picture | 用 CAPTURE 缓冲身份/参考 timestamp 区分帧，两个场复用同一目标及 MV 空间；POC 用于排序，不作为唯一缓冲身份；实板检查第二场和错误恢复 |
| `h264_config_decode_buf()` | 当前 POC 固定 top，BUFFER_INFO 固定 frame，参考项 type=3 | 按 firmware 元数据和标准控制区分 frame、MBAFF、top、bottom；保存每个已解码参考的原始结构，避免仅由当前 SPS 猜参考结构 |
| colocated MV 地址 | 仅按 `96 * first_mb`，L1 原结构固定 frame | 区分 frame/field/MBAFF 的写偏移及跨结构读偏移，校验偏移与整块范围；从实际地址计算函数做 KUnit，标准 B 场/MBAFF 流验像素 |
| `vdec_job_finish()` | 每个 request 都递增 CAPTURE sequence | 以实际出队为边界；首场 HOLD 时不消耗 CAPTURE 序号，第二场合并完成；用带流 compliance 和 PAFF 标准流检查，不能用 vb2 mock |

不在内核新增 H.264 码流解析：继续使用 V4L2 stateless 控制与固件报出的 slice
信息。HEVC 仍是独立 stateful 节点，不受此设计影响。

## 厂商代码提供的硬件语义

`common_drivers/drivers/media_modules/frame_provider/decoder/h264_multi/vmh264.c`
的 `config_decode_buf()`：

- 约 4490 行写入 frame/top/bottom 三个 POC，而不是两次 top POC。
- 约 4533 行按 MBAFF/top/bottom/frame 选择 `0xf4c0/0xf400/0xf440/0xf480`。
- 参考表为 top/bottom/frame 分别设置 type 1/2/3。
- 约 4771、4880–4935 行区分当前与 L1 原始图像结构，计算 MV 偏移；
  `H264_CO_MB_RD_ADDR[31:30]` 分别表示 top/bottom/frame/MBAFF，bit29 选择参考场。

厂商代码只作为寄存器语义来源，不复制其无界等待、私有队列或内部码流解析器。
软件模式优先参照主线 `verisilicon/hantro_g1_h264_dec.c`、`hantro_h264.c` 和
`rkvdec-h264.c` 如何使用 `v4l2_h264_reference.fields`、POC、长期参考及 reflist
builder。Hantro 的表项/未配对场处理须在实现前完整核对。

GStreamer 仅在驱动声明 HOLD_CAPTURE 能力后按场提交。沿用 m2m 的 held buffer
生命周期，对照 Hantro/cedrus 与 `v4l2_m2m_release_capture_buf()` 的实际调用
条件处理场完成/释放，不能自建第二套场队列。

## 实现与验收顺序

拆成尺寸/参考元数据、MV 地址、HOLD 与 sequence、最后开放入口几个独立提交，
每个单独构建。先完成纯逻辑，再连接硬件寄存器；完整生命周期接好后才移除
入口拒绝。保留多 slice 的 picture 生命周期规则，不能在第二场或第二 slice
回收仍被 DMA 使用的映射。STREAMOFF/错误只在确认 DMA 停止后释放。

验收按三个子集分窗：MBAFF frame、独立 field、混合 PAFF；每组同时带已通过的
逐行与多 slice 对照。复验原 52 条并逐流报告，不以一条出帧代替完整支持。
Timeout/内核异常立即退出并恢复；像素失败继续收集。生产配置只证明功能/像素，
锁与内存结论仍需无告警的调试内核。没有新的 DT binding 变更计划。
