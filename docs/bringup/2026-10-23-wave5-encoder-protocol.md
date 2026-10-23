# 2026-10-23：Wave5 E01 公共与逐帧参数协议附表

离线补充 [131 项 EncVpParam 映射](2026-10-23-wave5-encoder-controls.md)。
源码身份、候选和测试范围见 [编码器记录](2026-10-23-wave5-encoder-parity.md)。
下表的字段存在性与固件可用性分开；未将 MPEG4/H.263/VP9/SVAC 通用接口算作 T7 能力。
标准 codec 控件名省略 `V4L2_CID_MPEG_VIDEO_`。

## 公共库接口

SDK `multiEnc/amvenc_lib/include/vp_multi_codec_1_0.h:115–181`：

| vl_encode_info_t 字段 | 对应与当前状态 |
|---|---|
| width, height, img_format | OUTPUT S_FMT 存储布局 + selection CROP 可见区域；CAPTURE S_FMT 选择 codec，尺寸由驱动返回。 |
| frame_rate, bit_rate, gop | S_PARM、BITRATE、GOP_SIZE；序列建立后拒绝静态改参，动态 API 尚未实现。 |
| prepend_spspps_to_idr_frames | PREPEND_SPSPPS_TO_IDR 已有。 |
| qp_mode, forcePicQpEnable, forcePicQpI, forcePicQpP, forcePicQpB | FRAME_RC_ENABLE / BITRATE_MODE=CQ 与各 codec 的 I/P/B_FRAME_QP、*_FRAME_MIN/MAX_QP；本轮新增逐帧型标准控制。 |
| enc_feature_opts | bit0 ROI、bit1 动态 change、bits2–6 GOP preset/层级、bit7 LTR，分别见下文；不能把这个私有位图公开成标准控件。 |
| intra_refresh_mode, intra_refresh_arg | CYCLIC 标准刷新周期换算连续行；列/步进/adaptive 未开放。 |
| profile | H264/HEVC_PROFILE；内部位深随 profile，保留 legacy AVC ID 翻译。 |
| frame_rotation, frame_mirroring | ROTATE、HFLIP、VFLIP；修正 flip 取消，90/270 的尺寸与 crop 有离线旋转测试，仍须实测像素方向。 |
| bitstream_buf_sz, bitstream_buf_sz_kb | CAPTURE sizeimage 与 REQBUFS，非 CPB/VBV；不混淆物理码流缓冲容量与码率模型。 |
| multi_slice_mode, multi_slice_arg | MULTI_SLICE_MODE/MAX_MB；模式2依赖 slice/字节组合未开放。 |
| cust_gop_qp_delta | 自定义/层级 GOP QP 差，尚未实现；已有 HIERARCHICAL_CODING_* 标准控制可继续接。 |
| strict_rc_window, strict_rc_skip_thresh | `libvpmulti_codec.c:296–326,404–407,860,1074` 在用户态滑窗统计并请求 skip；不是固件独立 CBR 位。候选没有复刻用户态调度/丢帧策略，不保证厂商“严格 CBR”。 |
| vui_parameters_present_flag, video_full_range_flag, video_signal_type_present_flag, colour_description_present_flag, colour_primaries, transfer_characteristics, matrix_coefficients | 格式 colorimetry 有标准 S_FMT 字段；候选尚未保证相应 VUI 写入。厂商在 `libvpmulti_codec.c:416–477,599–665` 软件解析/重写 SPS；主线 stateful 规范明确不推荐驱动软件生成/改写 header，本轮不照搬。 |

`qp_param_t:234–246` 的 `qp_min/qp_max`、`qp_I/P/B_base`、`qp_I/P/B_min/max`
分别映射 codec 全局上下界、固定帧型 QP 和帧型上下界；全部已有候选映射。
`vl_param_runtime_t:223–232` 的 idr → FORCE_KEY_FRAME；bitrate/frame_rate 的运行中变更
尚未实现；enable_vfr/min_frame_rate 是用户态节流策略；nr_mode 也未开放。
`vl_video_encoder_update_qp_hint/change_bitrate/change_qp/change_gop/change_multi_slice/
longterm_ref/skip_frame/change_strict_rc` 覆盖 ROI、动态参数、LTR 和用户态丢帧，
不能据静态同名控件就宣称这些函数已对齐。

## EncParam：45 项逐帧/运行参数

`multiEnc/vpuapi/include/vpuapi.h` 至 4329 行；真实命令写入在
`enc_driver.c:1880–1886`：PIC_PARAM bit1 启用强制 QP，I/P/B 分别从 bit2/8/14 开始，
bit20 强制帧型，bit21 起帧型3表示 IDR。候选只写已有字段，未在内核改写输出码流。

| 字段 | 标准接口或边界 |
|---|---|
| sourceFrame, srcIdx, picStreamBufferAddr, picStreamBufferSize | OUTPUT/CAPTURE QBUF、索引与已验证的 DMA 地址/容量；不向用户提供物理地址控件。 |
| forceIPicture, forcePicTypeEnable, forcePicType | FORCE_KEY_FRAME 请求 IDR；不开放任意逐帧 I/P/B 强制。forceIPicture 是通用老 codec 参数，不能等同任意 Wave521C 能力。 |
| forcePicQpEnable, forcePicQpI, forcePicQpP, forcePicQpB, quantParam | RC 关闭/CQ 时使用协商的 I/P/B QP；本轮新增 PIC_PARAM QP 编程。quantParam 为通用旧接口，不另公开。 |
| skipPicture, srcEndFlag | 显式逐帧 skip 未开放；EOS 用标准 ENCODER_CMD STOP/drain，不能把 skip 当作 EOS。 |
| fieldRun | 候选只接收逐行 RAW，非逐场接口。 |
| codeOption | 固件隐式生成完整帧及首帧 headers；AU_DELIMITER、PREPEND_SPSPPS_TO_IDR、HEADER_MODE=JOINED。独立 header/EOS/EOB NAL 菜单未开放。 |
| useCurSrcAsLongtermPic, useLongtermRef | 没有通用 stateful 逐帧 LTR 标记/引用 ABI，未开放；不得复用 stateless decoder DPB 结构。 |
| pts | OUTPUT timestamp，按固件 enc_src_idx 关联到重排后的 CAPTURE；本轮测试覆盖 I/B/P → I/P/B。 |
| codRoiEnable, codRoiPicAvgQp, roiQpMapAddr, nonRoiQp, customMapOpt | ROI/custom lambda/mode/coef-drop map 未开放；新增标准 ABI 前要定义 map layout、逐帧绑定、DMA 所有权和错误处理。 |
| wpPixSigmaY, wpPixSigmaCb, wpPixSigmaCr, wpPixMeanY, wpPixMeanCb, wpPixMeanCr | weighted-prediction 统计未开放，无通用等价控制。 |
| forceAllCtuCoefDropEnable | 未开放，不能用 FORCE_KEY_FRAME 或 frame-skip 代替。 |
| userFilterLevelEnable, lfFilterLevel, sharpLevel, lfRefDeltaIntra, lfRefDeltaRef0, lfRefDeltaRef1, lfModeDelta | 通用结构的其他 codec filter 参数，不计为 AVC/HEVC 对齐结果。 |
| svcLayerFlag, OffsetTblBuffer | SVAC/SVC 专用路径，未提供 T7 AVC/HEVC 能力证据。 |
| qosEnable, qosConfig, qosValVcore0, qosValVcore1, canvas | 厂商资源/输入布局机制；主线用标准缓冲、DMA 和 PM，不新增 canvas/QoS 私有控制。 |

`VpCustomMapOpt` 另含 roiAvgQp、customRoiMapEnable、customLambdaMapEnable、
customModeMapEnable、customCoefDropEnable、addrCustomMap；整组未开放。
prefix/suffix SEI 寄存器接受 payload 地址/长度，但任意 SEI 没有通用标准 stateful payload ABI。
H264_SEI_FRAME_PACKING 等标准子集存在，尚未实现；应先补标准子集，不能笼统称所有 SEI 缺 ABI。

## EncOpenParam：68 个声明项（含 codec union）

结构至 `vpuapi.h:4175`。为区分通用 SDK 与 Wave521C，全部按用途列出：

| 字段组 | 对应或限制 |
|---|---|
| bitstreamBuffer, bitstreamBufferSize, bitstreamFormat, ringBufferEnable, lineBufIntEn, ringBufferWrapEnable | CAPTURE 缓冲/codec；主线固定 line-buffer 模式，未开放 ring 模式私有 ABI。 |
| picWidth, picHeight, frameRateInfo, vbvBufferSize, bitRate, rcEnable, gopSize, idrInterval | selection、S_PARM、BITRATE、FRAME_RC_ENABLE、GOP_SIZE；AVC CPB_SIZE 新增 KiB→毫秒换算。HEVC 保留继承的 VBV_SIZE 接口但不声称该控件原始 MPEG1/2/4 定义适用于 HEVC。 |
| cbcrInterleave, cbcrOrder, packedFormat, srcFormat, outputFormat, srcBitDepth, nv21 | 标准 OUTPUT 像素格式、plane 布局；不单独暴露内部排列位。 |
| frameEndian, streamEndian, sourceEndian, bwbEnable, cacheBypass, linear2TiledEnable, linear2TiledMode | 驱动/平台布局与总线实现参数，非用户视频控制；保持主线资源所有权。 |
| coreIdx, virtAxiID, enablePTS, lowLatencyMode, enableNonRefFbcWrite, sourceBufCount, streamBufCount, streamBufSize, rcWeightFactor, srcReleaseIntEnable | 资源/调度模式，候选固定既有安全路径，时间戳由 V4L2 管理；未新增私有切换模式。 |
| bitRateBL, picWidthBL, picHeightBL | base-layer/SVC 相关，未提供该 T7 AVC/HEVC 路径能力证据。 |
| MESearchRangeX, MESearchRangeY, rcGopIQpOffsetEn, rcGopIQpOffset, MESearchRange, frameSkipDisable, meBlkMode, sliceMode, intraRefreshNum, ConscIntraRefreshEnable, userQpMax, maxIntraSize, userMaxDeltaQp, userMinDeltaQp, userQpMin, MEUseZeroPmv, intraCostWeight, rcIntraQp, userGamma, rcIntervalMode, mbInterval, rcInitDelay | 通用非 Wave5/旧 codec 配置集合，不能直接转成 Wave521C 寄存器；对应 Wave5 实际控制应使用 EncVpParam。旧结构出现搜索范围不证明 Wave521C 支持标准 MV_H/V_SEARCH_RANGE。 |
| mp4Param, h263Param, avcParam, vpParam, EncStdParam | codec union 成员与外层声明；本表 T7 路径的合同是 vpParam，不能把 union 中各 codec 参数相加当作全部可用。 |

VUI 子结构 `HevcVuiParam` 的 vuiParamFlags、vuiAspectRatioIdc、vuiSarSize、
vuiOverScanAppropriate、videoSignal、vuiChromaSampleLoc、vuiDispWinLeftRight/TopBottom
对应部分 SAR、色彩和显示窗口语义；主线命令目前关闭 VUI_HRD，未确认直接 VUI
路径在 legacy 固件可用。E02 conformance window 使用独立的 CONF_WIN 寄存器，
不依赖这组 VUI 参数，也不依赖厂商用户态 SPS 改写。
