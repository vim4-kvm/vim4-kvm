# 2026-11-05：`.28` H.264 全集处置与合入评审边界

JVT-AVC_V1 套件通过从原 `.25` **58/135 提升到 110/135**，新增 52 条，原先
58 条全部保持通过。全集 135 条均已明确处置，**134 条实际解码，sp2_bt_b 因已证实
SP slice 不支持而预先跳过**；不能表述成 135 条都实际运行或全部通过。

最终按支持范围分类为 **110 Success / 20 Fail / 5 Known unsupported**。
允许进入 hwdecode-parity 的代码合入评审；**尚不能作为已对齐厂商 5.15、全功能验收通过
或立即部署的依据**。剩余功能缺口、调试验证和历史提交格式事项见下。

## 身份、覆盖与结果口径

源码 `960132382e00864f4944aee077cd621927a97bb0`，基于正式 `fd41fb5` 重放的
56 个提交；`.28` GNU build ID `81bb2f999ffffb38d549afbf8b15fb3048184c0f`。
生产配置与正式配置一致，无调试片段、无 HEVC 私有草稿；完整身份和逐提交验证见
[重放记录](2026-11-05-vdec-integrated-rebase.md)。四个有效解码窗口 r54、r56、r57、r58
使用同一候选、同一锁定 fluster commit/标准输入，不混入旧 `.27` 的结果。

| 口径 | Success | Fail | Error | Timeout | Known unsupported | 未实际运行 |
|---|---:|---:|---:|---:|---:|---:|
| `.28` 原始执行历史（保留内核超时分类） | 110 | 21 | 1 | 2 | — | 1 |
| 最终支持范围分类 | 110 | 20 | 0 | 0 | 5 | 其中 1 条 |

第二行不是改写第一行：五项不支持中，FM1_BT_B 曾 Fail、FM2_SVA_C 曾 Error、
FM1_FT_E 与 SP1_BT_A 曾内核 Timeout；sp2_bt_b 本基线未解码。原始 JSON、日志和
历史结果保留。最终没有未分类项；Known unsupported 不算通过。
[逐码流清单](data/2026-11-05-vdec-avc-final.csv) 同时列实际结果、支持分类、旧 `.25`
结果、特性、窗口和证据。分析脚本与汇总仅在 `build/hwdecode-parity/final-avc-summary.py`
和 `avc-final-summary.json`，不新增像素比对测试。

| 已观察特性（可重叠，不可相加） | Success | Fail | Known unsupported |
|---|---:|---:|---:|
| 多 slice | 16 | 1 | 2 |
| SPS 允许隔行 | 37 | 15 | 0 |
| 实际 field picture | 24 | 7 | 0 |
| MBAFF enabled | 18 | 9 | 0 |
| PAFF observed | 8 | 5 | 0 |
| 长期参考 | 7 | 3 | 0 |
| cropping | 0 | 1 | 0 |
| FMO | 0 | 0 | 3 |
| SP slice（Extended profile） | 0 | 0 | 2 |

特性来自已有原始 trace_headers，不按文件名分类。FMO 三项的
num_slice_groups_minus1>0；SP 两项实际 profile_idc=88、slice_type 集合为 [0,2,3]，
3 是 SP，未据此声称观察到 SI。SVA_FM1_E 的 slice group=0，正常运行并通过。
后续计划按 `known_unsupported` 逐项保存原因并跳过，不允许再次吞掉剩余码流窗口。

## 20 项 Fail：已知用户态与仍需定位的驱动路径

三条用户态限制仍计套件 Fail，不抬高 110 的套件通过数：

- CVFC1_Sony_C：完整 coded 输出按 (26,60) crop 后 50/50 帧与参考逐字节相等；
  v4l2codecs 忽略 crop 偏移。[证据和 MD5](2026-11-05-vdec-field-lifetime.md#cvfc1-的一次性证据工具)。
- Sharp_MP_Field_1_B、Sharp_MP_PAFF_1r2：已输出的 14 帧分别与对应参考帧相等，
  缺少最后解码图像；零丢事件 trace 证明最后 slice 没有进入 OUTPUT QBUF。
  当前 Khadas h264parse 在末尾 NAL10/11 后 current_off==size 时继续等待数据，
  官方 1.24.2 则完成 AU；不是内核收到完整输入后丢掉该图像。

Sharp 的系统库来源已由 dpkg MD5、APT policy、安装历史确认是 Khadas
`2:1.24.2-1ubuntu4` 包，非 sources.toml 私有 good recipe，也非私有 v4l2codecs。
未发现安装后文件覆盖；厂商精确源码补丁尚未取得，不虚构代码归属。
[来源和 SHA](2026-11-05-vdec-r56-fmo-parser.md)、[QBUF/DQBUF](2026-11-05-vdec-r54-sharp-trace.md)。
两条流实际以 OUTPUT/CAPTURE STREAMOFF 成功收尾并可继续后续解码；没有
VIDIOC_DECODER_CMD，因此 **HOLD 的 STREAMOFF 收尾有实证，HOLD+FLUSH 未实测**。
不能把没有 DQBUF 的缓冲算成已 DQBUF。[ioctl 原始证据](2026-11-05-vdec-r57-sharp-streamoff.md)。
不替换系统库，不打插件补丁。

其余 17 项按主要特性分组，以下不是已证明的根因：

- 13 项隔行：CABREF3_Sand_D、CAMA1_TOSHIBA_B、CAMA3_Sand_E、CAMANL1_TOSHIBA_B、
  CAMANL2_TOSHIBA_B、CAMANL3_Sand_E、CAPA1_TOSHIBA_B、CAPAMA3_Sand_F、
  CVMA1_TOSHIBA_B、CVMANL1_TOSHIBA_B、CVMANL2_TOSHIBA_B、CVPA1_TOSHIBA_B、Sharp_MP_PAFF_2r。
- 3 项长期参考：MR3_TANDBERG_B、MR4_TANDBERG_C、MR5_TANDBERG_C。
- 1 项加权预测：CAWP5_TOSHIBA_E（实际 weighted_pred_flag 含 1）。

这些失败不能笼统归因固件或私有 ABI，尚需逐帧和控制参数定位。5.15 对照因厂商启动
hard lockup 暂停，没有同输入的成功对照，不能声称与 5.15 支持格式或像素行为完全一致。

## r58 收尾与验证范围

r58 正常启动，stateless media/video compliance **8/0、60/0**；128–134 七条全部
Success，随后三条 FMO 与 sp2_bt_b 均记录 Known unsupported、没有解码命令及原始
逐流解码结果文件，跳过不计 Pass。原始目录：
`logs/hwdecode-parity-r58/validation-fluster-1793912516236753000/`。

新正式 `7.3.1-vim4-20261105` 的 build ID 和 2372 个保护文件全部匹配；
实际 4K H.265 302 帧、60.36 fps，零新增 dropped/freeze/lost。582 个上传文件
归档校验、复核板端未变后删除；`run58/upload-cleanup.log` 保存删除结果。
全部候选只作 RAM 一次性验证，正式默认未切成解码候选。
截至收尾 `.28` **8 次启动/2 次冷复位**，新正式下界 **13 次/0 次**；r54–r58
五次候选均未复位，不触发暂停重试条件，但不能据此排除已知冷复位问题。

56/56 逐提交模块/内建构建、有效 sparse、已有 KUnit 的逐提交运行和 DT binding
检查见重放记录；没有把未运行的 KUnit 或调试窗口算通过。新正式基线上的此次
streaming compliance 只覆盖 stateless 节点；JPEG/HEVC 不在本轮范围。
完整 H.264 验证尚不覆盖 JVT-FR-EXT High profile 子集、负 bottom POC 专项、
零告警调试内核下的锁/内存检查；本轮也没有推进 HEVC 和 MPEG-2 未决项。

## 合入评审建议

可以开始审查已提交的多 slice、隔行参考/MV/HOLD/sequence 系列：新增 52 条
一致性通过、旧 58 条无回退、compliance 通过、每个提交可构建验证，边界已有原始证据。
但不要把“进入评审”写成“同意合入生产”或“7.3 已完成 5.15 解码对齐”。

评审/合入前仍须处理：

1. 56 个历史提交中实际只有 14 个带 Signed-off-by，42 个旧提交需按已约定流程补正文/
   签名并保留作者，改写后核对 range-diff；本次没有擅自重写。
2. 明确 17 项残余像素失败和五项不支持的接受范围；known-unsupported 是验收计划的
   分类，不是新增了内核对非法/不支持请求的拒绝保障。
3. 若要求完整质量验收，补零告警调试内核、HOLD+FLUSH 和上述未覆盖集合；
   不用生产配置功能结果替代锁/内存证据。
4. HEVC 草稿继续不合入；MPEG-2、HEVC/固件接口与 5.15 parity 另行收口。
