# 2026-11-05：H.264 隔行支持设计要点（未实现）

按协调决定先验证多 slice；隔行 SPS 的 52 条失败排在其后。这是完整的新能力，
不能只删除 `FRAME_MBS_ONLY` 检查。以下是实现前的设计审查材料，没有新增隔行
支持提交，也没有宣称实板通过。分组证据见[失败聚类](2026-11-05-vdec-failure-groups.md)。

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
