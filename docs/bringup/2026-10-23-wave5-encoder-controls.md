# 2026-10-23：Wave5 E01 厂商参数与标准控件对照

本表是离线接口审查，不是功能全部完成的声明。实现、测试和后续窗口见
[编码器候选记录](2026-10-23-wave5-encoder-parity.md)；公共封装、逐帧与非 Wave5 字段见
[协议附表](2026-10-23-wave5-encoder-protocol.md)。本轮没有访问板子。

## 来源与范围

5.15 内核 `80a07ad5406d`、common_drivers `4cfb128d36f8`：
`drivers/media_modules/frame_sink/encoder/multi/vpu_multi.c:1098` 起的 ioctl
管理 DMA、IRQ、实例和寄存器映射，并不提供编码参数的 V4L2 ABI。
参数合同来自本地 `build/encode444/vendor-src`，
encoder_libs_aml `4c38af2b398d00a906c26aa166d630a9f73d3f9e`：
`multiEnc/vpuapi/include/vpuapi.h` 的 `EncVpParam`（至 3405 行）、
`EncChangeParam`（至 3608 行）和 `multiEnc/vpuapi/enc_driver.c`。
只记录字段和行为，未复制厂商实现或固件。SDK 的通用结构包含非 Wave521C 功能，
字段存在不代表该固件实际支持；实际能力仍须 QUERY 与码流验证。

以下标准控件名均省略 `V4L2_CID_MPEG_VIDEO_`；“已有/新增”均指候选源码，
不是当前已部署内核。序列控件只在固件实例建立前可设置，之后返回 EBUSY，
不再静默写入不会生效的影子参数；FORCE_KEY_FRAME 保持运行中可用。

## EncVpParam：131 个顶层字段全量归组

| 厂商字段 | 标准接口、候选状态与缺口 |
|---|---|
| profile, enStillPicture, level, tier, internalBitDepth | H264/HEVC_PROFILE、LEVEL 已有；新增 HEVC_TIER、5.2 level。内部位深由 profile 决定；AVC/HEVC 参数现已独立，避免默认值串扰。格式仍不新增 10bit RAW。 |
| losslessEnable, constIntraPredFlag | HEVC_LOSSLESS_CU、HEVC_CONST_INTRA_PRED / H264_CONSTRAINED_INTRA_PREDICTION 已有。 |
| gopPresetIdx, gopParam | 新增 B_FRAMES=0..1，对应 IPP_SINGLE/IBPBP。任意 8 项 GOP、层级 GOP、2/3 个连续 B 尚未实现；有 H264/HEVC_HIERARCHICAL_CODING_* 标准控件可继续接，不能称 ABI 全缺。 |
| decodingRefreshType, intraPeriod, avcIdrPeriod | HEVC_REFRESH_TYPE/PERIOD、H264_I_PERIOD、GOP_SIZE 已有；零刷新周期的既有 fallback 保留。开放 GOP/IDR 实际间隔须码流检查。 |
| intraQP, minQpI, maxQpI, minQpP, maxQpP, minQpB, maxQpB | I_FRAME_QP 已有；新增 P/B_FRAME_QP 和两 codec 各 6 个 *_FRAME_MIN/MAX_QP。QP 范围改为标准 0..51。8 控件 cluster 校验 codec 全局与逐帧型范围交集，空交集 EINVAL 且不修改参数。 |
| forcedIdrHeaderEnable | PREPEND_SPSPPS_TO_IDR 已有；新增 HEADER_MODE，只支持 JOINED_WITH_1ST_FRAME，SEPARATE 不列入菜单。 |
| confWinTop, confWinBot, confWinLeft, confWinRight | OUTPUT selection CROP，新增 HEVC 内部 8 对齐与像素裁剪偏移，详见 E02 记录。 |
| independSliceMode, independSliceModeArg, avcSliceMode, avcSliceArg | MULTI_SLICE_MODE/SINGLE/MAX_MB 已有；HEVC 的标准 16×16 MB 数现换算成 64×64 CTU 数。 |
| dependSliceMode, dependSliceModeArg | 尚未实现；MAX_BYTES 标准控件存在，但 SDK 的依赖 slice 与独立 CTU slice 组合不能直接等同独立字节上限。需确认固件能力与边界。 |
| intraRefreshMode, intraRefreshArg, intraMbRefreshMode, intraMbRefreshArg | INTRA_REFRESH_PERIOD + TYPE=CYCLIC，已有按高度计算连续行预算。列/步进/HEVC adaptive 尚无等价标准模式；不把随机菜单项映射成厂商步进。 |
| useRecommendEncParam, scalingListEnable, cuSizeMode, userScalingListAddr | 推荐档位、CU 掩码、自定义 scaling list 未开放；没有等价通用 stateful 控件。后续须讨论标准 ABI，不能借用无关 quality 菜单。 |
| tmvpEnable, wppEnable, maxNumMerge, intraNxNEnable, strongIntraSmoothEnable | HEVC_TMV_PREDICTION/WAVEFRONT/STRONG_SMOOTHING 已有；新增 INTRA_PU_SPLIT，修正 MAX_NUM_MERGE_MV_MINUS1 为 0..1 → 固件 1..2（SDK 明确限制 1/2）。 |
| disableDeblk, lfCrossSliceBoundaryEnable, betaOffsetDiv2, tcOffsetDiv2 | H264/HEVC_LOOP_FILTER_MODE 与 H264_LOOP_FILTER_ALPHA/BETA、HEVC_LF_BETA/TC_OFFSET_DIV2 已有；修复 AVC/HEVC 状态互相覆盖。 |
| skipIntraTrans, saoEnable | transform skip 保持既有固定值，无对应通用开关；SAO 随 HEVC_LOOP_FILTER_MODE，补上向固件参数的遗漏复制。不能独立调 SAO。 |
| bitAllocMode, fixedBitRatio | 未开放。层级 bitrate 标准控件存在，但要先定义 GOP/temporal layer 的对应关系，再编程 bit-ratio；不能直接把 bps 填入比例字节。 |
| cuLevelRCEnable, mbLevelRcEnable, hvsQPEnable | FRAME_RC_ENABLE / MB_RC_ENABLE 已有；MB_RC_ENABLE 同时控制固件 CU/MB/HVS。不是三个独立可调旋钮。 |
| hvsQpScale, hvsMaxDeltaQp, initialRcQp, rcWeightParam, rcWeightBuf | 保持既有 scale=2、delta=10、initial=-1、weight=16/128；无逐项等价标准控件，尚未开放。 |
| roiEnable | 序列开关需与逐帧 map 一起设计；目前无通用 stateful ROI map 控件，未开放。见逐帧附表。 |
| numUnitsInTick, timeScale, numTicksPocDiffOne | S_PARM TIMEPERFRAME；本轮仍协商整数 fps，但返回真实协商值，拒绝实例建立后改变。完整有理数/VUI timing 未实现。 |
| chromaCbQpOffset, chromaCrQpOffset | H264_CHROMA_QP_INDEX_OFFSET 已有，同时设置 Cb/Cr；HEVC 独立偏移未开放。不能把 AVC 控件写入 HEVC 参数。 |
| nrYEnable, nrCbEnable, nrCrEnable, nrIntraWeightY, nrIntraWeightCb, nrIntraWeightCr, nrInterWeightY, nrInterWeightCb, nrInterWeightCr, nrNoiseEstEnable, nrNoiseSigmaY, nrNoiseSigmaCb, nrNoiseSigmaCr | 13 项 NR 未开放。NOISE_REDUCTION 的泛化用户控制不等价于这些 codec 调优表，不能无合同套用。 |
| useLongTerm, monochromeEnable, weightPredEnable | LTR 需逐帧引用标记 ABI，未开放；monochrome/weighted prediction 未开放。普通编码接口不能挪用 stateless decoder 的 DPB 控件。 |
| bgDetectEnable, bgThrDiff, bgThrMeanDiff, bgLambdaQp, bgDeltaQp | BACKGROUND_DETECTION 开关已有；4 项阈值/权重固定，缺标准细粒度 ABI。 |
| customLambdaEnable, customLambdaAddr, customMDEnable | 自定义 lambda/模式表未开放，无标准通用 map ABI。 |
| pu04DeltaRate, pu08DeltaRate, pu16DeltaRate, pu32DeltaRate | 四种 PU cost delta 未开放，无标准等价控件。 |
| pu04IntraPlanarDeltaRate, pu04IntraDcDeltaRate, pu04IntraAngleDeltaRate, pu08IntraPlanarDeltaRate, pu08IntraDcDeltaRate, pu08IntraAngleDeltaRate, pu16IntraPlanarDeltaRate, pu16IntraDcDeltaRate, pu16IntraAngleDeltaRate, pu32IntraPlanarDeltaRate, pu32IntraDcDeltaRate, pu32IntraAngleDeltaRate | 12 项 intra cost delta 未开放，无标准等价控件。 |
| cu08IntraDeltaRate, cu08InterDeltaRate, cu08MergeDeltaRate, cu16IntraDeltaRate, cu16InterDeltaRate, cu16MergeDeltaRate, cu32IntraDeltaRate, cu32InterDeltaRate, cu32MergeDeltaRate | 9 项 CU cost delta 未开放，无标准等价控件。 |
| coefClearDisable, rdoSkip, lambdaScalingEnable, transform8x8Enable, entropyCodingMode, s2fmeDisable | H264_8X8_TRANSFORM、ENTROPY_MODE 已有；RDO/lambda 保持固定，coef-clear/s2fme 未开放。 |
| svcEnable, svcMode, lumaDcQpOffset, chromaDcQpOffset, chromaAcQpOffset | SDK 标记 SVAC 专用，不计入 T7 AVC/HEVC 能力。 |
| vuiParam | 见协议附表：字段存在但不能据此承诺色彩 VUI 已写入码流。 |
| enReportMvHisto, reportMvHistoThreshold0, reportMvHistoThreshold1, reportMvHistoThreshold2, reportMvHistoThreshold3 | 条件编译 SUPPORT_VP5ENC_REPORT_MV_HISTO 的诊断输出，未开放，不属于标准视频像素/码流接口。 |

## 动态参数与未完成项

新增 BITRATE_MODE=CQ 与 CONSTANT_QUALITY=1..100；驱动用反向归一化 QP 51..0，
关闭 RC 后为三种帧型选择相同固定 QP。其他模式关闭 FRAME_RC_ENABLE 时使用
显式 I/P/B_FRAME_QP。这是主线接口上的质量刻度策略，不声称固件另有 CQ 模式。
CBR/VBR 只有 VBV 默认时长策略差异，不把厂商用户态 strict-RC 等同固件硬 CBR。

`EncChangeParam` 的 90 项绝大多数是上表字段的运行中变体；额外的
`enable_option`、`bitRate`、`vbvBufferSize` 对应 SET_PARAM change mask、码率和缓冲时长。
候选不实现运行中 SET_PARAM change。标准 BITRATE、QP、GOP、slice 控件有静态实现，
但运行中修改明确 EBUSY，不能宣称已对齐厂商 change API。

E01 仍未完成：动态改参、完整层级/自定义 GOP、多 B、VUI/HRD、标准 SEI 子集和
ROI/LTR/custom map ABI。优先补已有标准接口；只有标准确实缺失的复杂 payload
才提新控件/请求模型，需明确缓冲生命周期、逐帧关联、错误与多实例调度，不能新增
私有数字菜单作为正式替代。本轮没有新增 uAPI 定义。
