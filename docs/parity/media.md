# HDMI 输入、编码与解码

本页管对应能力差距与验证条件；当前身份见[主线入口](../kernel-mainline.md)。
固定高刷与原生色彩按各行证据判断；无真实 HLG、隔行、像素重复、真深色或 VRR 源则暂缓对应硬件验收。
导航：[能力与边界](#能力与边界)；[范围和依赖](README.md)。

## 能力与边界

| ID / 厂商能力及来源 | 7.3 状态 | 差异、现有证据 | 路线、依赖与验证条件 |
|---|---|---|---|
| R01 HDMI RX/DDC/EDID/HPD 与自动恢复 | 部分对齐 | E3 标准 EDID/时序接口、源端读回与 19 档通过；仍有 FDET 无效快照触发错误停流。[模式](../bringup/2026-10-22-edge-hdmi-modes-final.md)、[停流审计](../bringup/2026-10-22-wave5-first-failure-audit.md) | 重写/完善 V4L2 subdev＋source events；承接现有音频/采集稳定性任务，统一活动租约测量错误分类，不能靠反复 HPD 自愈；可切分辨率/断信号 HDMI 源，浏览器运动源 |
| R02 VDIN0 DMA、MMAP/dma-buf/缩放 | 部分对齐 | E2/E3 已有直接 DMA、帧一致性、缩放和回收；仍是 test 驱动/独占整窗 VCBUS，固定参数与局部资源管理不是终态。[DMA](../bringup/2026-10-20-direct-dma-benchmark.md)、[缩放](../bringup/2026-10-21-edge-scaling-jpeg.md) | 重写标准 media graph、vb2/PM/资源所有权；与 M1 共享资源方案合并一次，D01/R01；HDMI 双向接线、运动一致性图案、DMA 压力 |
| R03 HDR10 与 HLG 输入/色彩 | 部分对齐 | [uhd4](../bringup/2026-10-31-uhd4-formal-smoke.md)的HDR2 PQ→709 NV12、VUI、同源色准p99=0、4K60与双向DMA恢复已验；HLG已实现、无真实源未验。8bit映射不等于原生HDR10远传 | 完善标准V4L2 HDR controls/原子更新与真实HLG验证；原生十位另走hdr10-remote，需rebase到uhd4；R01/R02；真HLG/PQ源、灰阶/色卡 |
| R04 隔行、像素重复与传统时序 | 缺失 | E3:977,1035 拒绝隔行/像素重复；19 档逐行不覆盖 480i/576i/1080i。[模式范围](../bringup/2026-10-22-edge-hdmi-modes.md) | 重写 field/场序/时序＋V4L2 去隔行，保留拒绝直至 D08 可用；8–15（不含 D08）/ H / 真隔行 HDMI 源、场标记 |
| R05 深色 RGB/444/422/420、12-bit | 部分对齐 | **不是一律拒绝 12bit**：E3:903 解析并配置 8/10/12bit。12bit 请求实际发送444/8；422容器/GCP=0也不能证明源精度12bit。真实 RGB 深色、422 SDR 仍缺覆盖；输出 NV12 为8bit。[实际格式](../bringup/2026-10-22-edge-hdmi-modes-final.md) | 重写/完善标准格式协商、packing/截位/抖动；先真12bit输入，再按厂商核对原生高位深 DMA/P010 是否可实现；可强制 RGB/422/444 10/12bit 的发生器/分析仪 |
| R06 原生 4:4:4 采集 | 部分对齐 | 8bit SDR YCbCr444 以标准 YUV24 交付，4K60 3600 帧 59.998fps、最大间隔 17.484ms，横纵单像素色度与三处帧号一致；严格帧号重复/跳号判为源端呈现。缓冲池上限、导出 fd、回 NV12 未上板。已合入正式 `4111568841bd` 并持久安装三模块，来源和加载身份见[部署记录](../bringup/2026-11-03-mainline-modules.md)及[运行时锁](../../packaging/kernel/sources.toml)。[窗口](../bringup/2026-11-02-hfr-yuv-window.md)、[厂商444](../bringup/2026-10-16-4k60-yuv444-raw-capture.md) | 补池上限/导出 fd/回 NV12；10/12bit 444 随 R05；单像素色度/同帧标记源 |
| R07 多路 RX、特殊 PHY/板型 | 部分对齐 | E2 固定 input-port=1，实际板载输入可用；其他 T7 RX port 并无本板连接验收。不能把 SoC 全端口列成 VIM4 多物理输入 | 重写 PHY/端口/标准路由描述；先查板图和实际接线，无布线端口不做产品入口；两版 VIM4、原理图/可接端口夹具 |
| E01 MultiEnc AVC/HEVC、码率/GOP/IDR/逐行刷新 | 部分对齐 | E4 标准 V4L2 M2M 可达4K60，IDR/profile/刷新已有回归；未覆盖厂商全部控制、多实例/高位深。[Wave5](../bringup/2026-10-19-wave521-uhd.md)、[IDR](../bringup/2026-10-20-onekvm-wave5.md) | 重写/完善 V4L2 controls、调度和固件协议；E02/E03 后做厂商参数逐项等效，固定录制输入、参考解码、双实例与运动场景 |
| E02 非8对齐 HEVC 可见尺寸 | 完全对齐 | 内核已有标准 selection、内部 padding/conformance window；[十组 NV12/NV12M 码流、1366×768 非零 crop](../bringup/2026-10-23-wave5-parity-window.md#e02b-帧与多实例)逐帧解码通过，含行列补边和 drain。正式 `4111568841bd` 保留该实现，Wave5 已[持久部署](../bringup/2026-11-03-mainline-modules.md) | 限偶数 4:2:0 可见矩形；One-KVM 正式 vim4 已含 `1d4c7816`、`307e0fd5`、`3649a8c8`，按 V4L2 格式/裁剪探测与插件能力放行，旧内核或探测失败仍回退 AVC。[第四轮](../bringup/2026-10-30-kernel73-gap-r3.md)720/900/4K 三轮均 HEVC 推进，三组非8对齐夹具解码通过；共享同 fd 多 plane 非零 offset 等布局另验，不扩张本行范围 |
| E03 Wave5 超时隔离、取消与恢复 | 部分对齐 | [P0-3离线复核](../bringup/2026-10-31-wave5-real-hang-safety.md)：正式 dc220366 已含39d42b恢复，全部宿主夹具通过；[软件注入](../bringup/2026-10-23-wave5-runtime-window.md)、[E01多实例/同页恢复](../bringup/2026-10-23-wave5-e01-window.md)不能证明真实挂死恢复。真实注入安全证据不足，本轮未上板，保护保持。10-31用户决定搁置：厂商5.15 `vpu_hw_reset()`为空操作、挂死只能重启，7.3已“先恢复、失败隔离到重启”，不再作为替换5.15的门槛；线上统计自然挂死，出现真实挂死或取得厂商资料后重启 | 先取得安全测试固件及T7总线合同，再验≥5次真实停滞、DMA停止/回收、冷加载及300秒真实解码。失败仍保留DMA；不以job_finish替代DMA停止证据。串口、受控故障注入 |
| E04 HCODEC/JPEG 静态与连续编码 | 部分对齐 | E5 V4L2 M2M/TEE固件加载、DMA导入与缩放已过；UHD60吞吐/画质边界、厂商全部格式/质量档未齐。[JPEG](../bringup/2026-10-21-edge-scaling-jpeg.md) | 重写/完善 V4L2 M2M controls 与标准内存模型；Q01、R02，禁止用超频替代正确性；运动源、参考JPEG解码、固定输入哈希 |
| E05 HCODEC AVC 与旧 venc ABI | 缺失 | 已加载 amvenc_multi/jpegenc；未证明旧 amvenc_avc 在 T7 实际承担编码。不能因 Kconfig 有H264就再算一个已验AVC硬核 | 先查真实消费者/芯片条件；功能由 Wave5 标准 AVC 提供，旧 ioctl ABI 不做。调查2–4，确认独立HCODEC AVC后另估厂商基准镜像/真实旧程序；禁止抢占JPEG域 |
| C01 H.264 单/多实例、MVC | 部分对齐 | V4L2 Request/stateless 已在正式内核：JVT-AVC_V1 129 Success / 1 Fail / 5 Known unsupported（官方 parser；FMO、SP 不支持），CVFC1 驱动输出裁剪后逐字节正确、仅 GStreamer 忽略 crop 致套件 Fail。驱动按 1080p 声明（`aml_t7_video_formats`），厂商报 4k30；MVC、多实例、S4、L1[0] 占位、HOLD+FLUSH、High profile 子集未做或未验。[全集](../bringup/2026-11-06-vdec-r69-joint.md)、[汇总](../bringup/2026-11-05-vdec-avc-final.md) | 放开至 4K 前先核 4k30 的 canvas/DPB/CMA 预算并补 4K 样本；FMO/SP 按固件能力确认后实现或保持拒绝；多实例走同一硬件占有路径，见[架构](../vdec-architecture.md)；MVC 另5–10 / H / 4K 与 MVC 样本、双实例、调试锁/内存内核 |
| C02 HEVC/VP9/AV1/AVS2 | 部分对齐 | 仅 HEVC：stateful 解码，JCT-VC 8bit 全集 129/132，可见尺寸至 4096×2304。VPSSPSPPS 根因未明；LTRPSPS_A、WPP_D 属固件限制、快速报错。Main10 被拒绝（无保留十位的输出），8K 未做；VP9、AV1、AVS2 无驱动。[HEVC 修复与板验](../bringup/2026-11-08-hevc-remaining5.md)、[逐流](../bringup/2026-11-07-vdec-integration42-pd-results.md) | HEVC 先 Main10/P010（依 C04 输出路径），再按 T7 上限扩尺寸；随后 VP9→AV1→AVS2，复用 HEVC 核时钟/固件与 stateful 层；每codec 8/10bit 标准全集、4K sink、错误流/多实例；固件依赖Q01 |
| C03 MPEG1/2、MPEG4/Xvid、MJPEG、VC1、AVS | 部分对齐 | MPEG-2 与 MJPEG 已在正式内核，均按 1080p 声明。MPEG-2 最近一次全集 18/43；之后同候选复测 23 条旧失败为 4 Success / 19 Fail，sony-ct1/ct2 起始 B 已修但像素仍 Fail，全集未在同一候选重跑；6 条 MPEG-1 码流未协商到请求接口。MJPEG 仅 3 样本通过。MPEG4/Xvid、VC1、AVS 无驱动。[MPEG-2 全集](../bringup/2026-11-05-vdec-full-conformance.md)、[复测](../bringup/2026-11-06-vdec-r69-joint.md#mpeg-229-次均完成)、[矩阵根因](../bringup/2026-11-06-mpeg2-visl.md)、[JPEG](../bringup/2026-11-08-vdec-dos-regmap-deploy.md) | 先在同一候选重跑 MPEG-2 全集取当前基数，再查剩余像素根因并决定 MPEG-1 是否纳入；MJPEG 扩样本/尺寸；MPEG4、VC1、AVS 沿 stateless 平台逐个实现，每codec5–15，VC1/AVS私有协议可能更大 / H / 参考解码器、逐帧样本、隔行片源 |
| C04 解码10bit、隔行、4K/8K、错误流/多实例 | 部分对齐 | 已有：H.264 场/PAFF 码流在官方 parser 下逐字节正确；HEVC 4K 8bit；整流不可解时快速报错、无内核超时。缺：全部 codec 的 10bit/P010 输出、8K、多实例；HEVC/MPEG-2 隔行未单独验证、长期稳定和调试锁/内存。无 5.15 同条件解码基线：厂商内核一次性启动即 hard LOCKUP，对照按用户决定暂停，性能不能宣称对齐。[5.15 中止](../bringup/2026-11-05-vdec-full-conformance.md#515-一次性启动与中止)、[未决项](../issues.md#采集与编码) | 主线 V4L2 formats/controls、fence/DPB/PM；先 P010 输出路径，再多实例与错误流；5.15 对照恢复前先解决厂商内核启动 LOCKUP，否则只报 7.3 绝对吞吐 / H / 真高位深素材、输出校验、内存压力与串口恢复 |
| C05 受保护解码与闭源微码替换 | 无法做到 | 已有匹配微码不等于能重写其源码或绕过BL32验证；缺密钥/TA或分发授权时无法交付等价安全解码。非安全标准解码仍应做。[固件明细](../bringup/2026-10-22-vdec-hardware-audit.md) | 当前不做闭源微码/信任链替代；合法固件可经TEE加载并保留标准V4L2。Q01/D11，确认3–7，受限实现厂商授权固件/安全样机 |
| C06 RealVideo、VP8、AVS3等跨芯片模块 | 缺失 | V3开关/旧加载列表有额外codec | 不做无T7硬件证据的驱动承诺；调查厂商T7报告/真实样本。若后续证明可用，重新纳入目标；软件解码可另用但不是硬件对齐 |

R07、E05、C06 是范围边界行，计数表示当前没有对应完整交付，不表示厂家已在本板验证。
核心编码正式实现必须仍保护 DMA 所有权；超时后提前归还 vb2 缓冲会造成硬件写已释放内存，
不能用 `job_finish` 或 queue_error 单独宣称已隔离。12-bit 的当前事实优先于任务列举中的旧描述。
