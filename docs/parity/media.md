# HDMI 输入、编码与解码

本页 18 个审计项，其中16项计入追平目标；固定路径/行号见 [证据索引](sources.md)，
范围与计数见 [总表](README.md)。
H/M 是高/中风险；估算为一人有效人日，等待固件/现场窗口另计，共用依赖不能重复累加。

2026-11-03 按正式源码和持久部署刷新，E02 限定范围完全对齐，R06 部分对齐（见对应行）。E01 动态参数、
LTR、分层 GOP 与多实例恢复已有[实际码流证据](../bringup/2026-10-23-wave5-e01-window.md)，
但 ROI、任意 GOP、VUI/SEI 和真实固件硬锁仍欠账。C01 最新候选有 IRQ/超时诊断，
尚无正确首帧；合入源码时 VDEC DT 和试验参数仍默认关闭。

2026-11-02 用户确认没有、也不打算购买 HDMI 信号发生器；M6 无法可靠输出 HLG、隔行、
像素重复和真 12bit。R03 真 HLG、R04、R05 真 12bit 验收暂缓，状态不变，不排上板；
5.15 对这几项也只有代码、无 KVM 上板验收。R06 的 8bit 原生 444 采集可用 M6 验证，照常推进。

2026-11-02 固定高刷与 VRR：当时的候选 `hfr-yuv-73`（现已随[三模块持久部署](../bringup/2026-11-03-mainline-modules.md)进入正式 `4111568841bd`）上 1080p120 AVC/HEVC、1440p120 HEVC 吞吐约 119.9–120fps，网页解码无丢帧，QHD 生产 AVC 限 60；1440p HEVC 的 SPS level 低报 5.0 已登记。M6 经 HDMI 不提供 Variable 刷新率，即便 EDID 声明 HDMI Forum VRR 48–120 Hz；Gaming VRR 只有宿主回归，上板验收同样暂缓。[窗口](../bringup/2026-11-02-hfr-yuv-window.md)

| ID / 厂商能力及来源 | 7.3 状态 | 差异、现有证据 | 路线、依赖 / 人日 / 风险 / 验证硬件 |
|---|---|---|---|
| R01 HDMI RX/DDC/EDID/HPD 与自动恢复；V1:541–594 | 部分对齐 | E3 标准 EDID/时序接口、源端读回与 19 档通过；仍有 FDET 无效快照触发错误停流。[模式](../bringup/2026-10-22-edge-hdmi-modes-final.md)、[停流审计](../bringup/2026-10-22-wave5-first-failure-audit.md) | 重写/完善 V4L2 subdev＋source events；承接现有音频/采集稳定性任务，统一活动租约测量错误分类，不能靠反复 HPD 自愈；4–8 / H / 可切分辨率/断信号 HDMI 源，浏览器运动源 |
| R02 VDIN0 DMA、MMAP/dma-buf/缩放；V1:1858，V2:codec_io | 部分对齐 | E2/E3 已有直接 DMA、帧一致性、缩放和回收；仍是 test 驱动/独占整窗 VCBUS，固定参数与局部资源管理不是终态。[DMA](../bringup/2026-10-20-direct-dma-benchmark.md)、[缩放](../bringup/2026-10-21-edge-scaling-jpeg.md) | 重写标准 media graph、vb2/PM/资源所有权；与 M1 共享资源方案合并一次，D01/R01；8–15 / H / HDMI 双向接线、运动一致性图案、DMA 压力 |
| R03 HDR10 与 HLG 输入/色彩；V1:541,2078 | 部分对齐 | [uhd4](../bringup/2026-10-31-uhd4-formal-smoke.md)的HDR2 PQ→709 NV12、VUI、同源色准p99=0、4K60与双向DMA恢复已验；HLG已实现、无真实源未验。8bit映射不等于原生HDR10远传 | 完善标准V4L2 HDR controls/原子更新与真实HLG验证；原生十位另走hdr10-remote，需rebase到uhd4；R01/R02；8–15 / H / 真HLG/PQ源、灰阶/色卡 |
| R04 隔行、像素重复与传统时序；V1:541，V2:multi-di | 缺失 | E3:977,1035 拒绝隔行/像素重复；19 档逐行不覆盖 480i/576i/1080i。[模式范围](../bringup/2026-10-22-edge-hdmi-modes.md) | 重写 field/场序/时序＋V4L2 去隔行，保留拒绝直至 D08 可用；8–15（不含 D08）/ H / 真隔行 HDMI 源、场标记 |
| R05 深色 RGB/444/422/420、12-bit；V1:541,1858 | 部分对齐 | **不是一律拒绝 12bit**：E3:903 解析并配置 8/10/12bit。12bit 请求实际发送444/8；422容器/GCP=0也不能证明源精度12bit。真实 RGB 深色、422 SDR 仍缺覆盖；输出 NV12 为8bit。[实际格式](../bringup/2026-10-22-edge-hdmi-modes-final.md) | 重写/完善标准格式协商、packing/截位/抖动；先真12bit输入，再按厂商核对原生高位深 DMA/P010 是否可实现；5–12 / M / 可强制 RGB/422/444 10/12bit 的发生器/分析仪 |
| R06 原生 4:4:4 采集；V1:1858，厂商 vfm_cap 扩展 | 部分对齐 | 8bit SDR YCbCr444 以标准 YUV24 交付，4K60 3600 帧 59.998fps、最大间隔 17.484ms，横纵单像素色度与三处帧号一致；严格帧号重复/跳号判为源端呈现。缓冲池上限、导出 fd、回 NV12 未上板。已合入正式 `4111568841bd` 并持久安装三模块，来源和加载身份见[部署记录](../bringup/2026-11-03-mainline-modules.md)及[运行时锁](../../packaging/kernel/sources.toml)。[窗口](../bringup/2026-11-02-hfr-yuv-window.md)、[厂商444](../bringup/2026-10-16-4k60-yuv444-raw-capture.md) | 补池上限/导出 fd/回 NV12；10/12bit 444 随 R05；1–2 / M / 单像素色度/同帧标记源 |
| R07 多路 RX、特殊 PHY/板型；V1:541 port_map，V2:HDMIRX | 部分对齐 | E2 固定 input-port=1，实际板载输入可用；其他 T7 RX port 并无本板连接验收。不能把 SoC 全端口列成 VIM4 多物理输入 | 重写 PHY/端口/标准路由描述；先查板图和实际接线，无布线端口不做产品入口；3–6 / M / 两版 VIM4、原理图/可接端口夹具 |
| E01 MultiEnc AVC/HEVC、码率/GOP/IDR/逐行刷新；V2:2566，V3:149–179 | 部分对齐 | E4 标准 V4L2 M2M 可达4K60，IDR/profile/刷新已有回归；未覆盖厂商全部控制、多实例/高位深。[Wave5](../bringup/2026-10-19-wave521-uhd.md)、[IDR](../bringup/2026-10-20-onekvm-wave5.md) | 重写/完善 V4L2 controls、调度和固件协议；E02/E03 后做厂商参数逐项等效，8–15 / H / 固定录制输入、参考解码、双实例与运动场景 |
| E02 非8对齐 HEVC 可见尺寸；V3:155/161，V5 | 完全对齐 | 内核已有标准 selection、内部 padding/conformance window；[十组 NV12/NV12M 码流、1366×768 非零 crop](../bringup/2026-10-23-wave5-parity-window.md#e02b-帧与多实例)逐帧解码通过，含行列补边和 drain。正式 `4111568841bd` 保留该实现，Wave5 已[持久部署](../bringup/2026-11-03-mainline-modules.md) | 限偶数 4:2:0 可见矩形；One-KVM 正式 vim4 已含 `1d4c7816`、`307e0fd5`、`3649a8c8`，按 V4L2 格式/裁剪探测与插件能力放行，旧内核或探测失败仍回退 AVC。[第四轮](../bringup/2026-10-30-kernel73-gap-r3.md)720/900/4K 三轮均 HEVC 推进，三组非8对齐夹具解码通过；共享同 fd 多 plane 非零 offset 等布局另验，不扩张本行范围 |
| E03 Wave5 超时隔离、取消与恢复；V5:436,1390,3421 | 部分对齐 | [P0-3离线复核](../bringup/2026-10-31-wave5-real-hang-safety.md)：正式 dc220366 已含39d42b恢复，全部宿主夹具通过；[软件注入](../bringup/2026-10-23-wave5-runtime-window.md)、[E01多实例/同页恢复](../bringup/2026-10-23-wave5-e01-window.md)不能证明真实挂死恢复。真实注入安全证据不足，本轮未上板，保护保持。10-31用户决定搁置：厂商5.15 `vpu_hw_reset()`为空操作、挂死只能重启，7.3已“先恢复、失败隔离到重启”，不再作为替换5.15的门槛；线上统计自然挂死，出现真实挂死或取得厂商资料后重启 | 先取得安全测试固件及T7总线合同，再验≥5次真实停滞、DMA停止/回收、冷加载及300秒真实解码。失败仍保留DMA；不以job_finish替代DMA停止证据。10–20起 / H / 串口、受控故障注入 |
| E04 HCODEC/JPEG 静态与连续编码；V2:2541，V3:167 | 部分对齐 | E5 V4L2 M2M/TEE固件加载、DMA导入与缩放已过；UHD60吞吐/画质边界、厂商全部格式/质量档未齐。[JPEG](../bringup/2026-10-21-edge-scaling-jpeg.md) | 重写/完善 V4L2 M2M controls 与标准内存模型；Q01、R02，禁止用超频替代正确性；5–10 / M / 运动源、参考JPEG解码、固定输入哈希 |
| E05 HCODEC AVC 与旧 venc ABI；V3:149,155，V2:2541 | 缺失 | 已加载 amvenc_multi/jpegenc；未证明旧 amvenc_avc 在 T7 实际承担编码。不能因 Kconfig 有H264就再算一个已验AVC硬核 | 先查真实消费者/芯片条件；功能由 Wave5 标准 AVC 提供，旧 ioctl ABI 不做。调查2–4，确认独立HCODEC AVC后另估8–15 / H / 厂商基准镜像/真实旧程序；禁止抢占JPEG域 |
| C01 H.264 单/多实例、MVC；V4:237，V3:40–57 | 缺失 | E5 平台基线没有已验 T7 解码帧；独立 vdec 候选曾发生 MDEC SError，不能按能probe计部分解码。[最新门禁](../bringup/2026-10-22-vdec-mdec-offline.md) | 主线 V4L2 Request/stateless 路线；承接进行中的 vdec，先时钟/genpd/DBUS/TEE/安全退出，再1080p I/P/B逐帧参考；15–30（已有成果抵扣）/ H / 串口、现场RESET、B帧/MVC样本；MVC另5–10 |
| C02 HEVC/VP9/AV1/AVS2；V4:237，V3:58,64,100,106 | 缺失 | 厂商 T7 格式掩码包含；E5 TODO 未实现这些标准codec，Wave521C当前固件解码支持没有成立证据。[硬件表](../bringup/2026-10-22-vdec-hardware-audit.md) | 主线 V4L2 各codec controls/Request与DPB；C01平台层可共用，先 HEVC→VP9→AV1→AVS2；每codec15–30起 / H / 8/10bit标准样本、4K sink、错误流/多实例；固件依赖Q01 |
| C03 MPEG1/2、MPEG4/Xvid、MJPEG、VC1、AVS；V4:237，V3:8–38,70–99 | 缺失 | 这些在 T7 mask 内；旧 staging 驱动有部分codec不等于支持T7。模块加载不保证解码成功 | 主线 V4L2，沿 C01 平台按codec逐个实现；每codec5–15，VC1/AVS私有协议可能更大 / H / 参考解码器、逐帧样本、隔行片源 |
| C04 解码10bit、隔行、4K/8K、错误流/多实例；V4平台表 | 缺失 | 厂商泛化8K报告与level信息不构成可验证的全部帧率承诺；E无T7基本帧，不能直接承诺高阶能力 | 主线 V4L2 formats/controls、fence/DPB/PM；C01–03先单codec正确性，10–25/codec扩展 / H / 真高位深素材、输出校验、内存压力与串口恢复 |
| C05 受保护解码与闭源微码替换；V1:216，V2:340，V4 | 无法做到 | 已有匹配微码不等于能重写其源码或绕过BL32验证；缺密钥/TA或分发授权时无法交付等价安全解码。非安全标准解码仍应做。[固件明细](../bringup/2026-10-22-vdec-hardware-audit.md) | 当前不做闭源微码/信任链替代；合法固件可经TEE加载并保留标准V4L2。Q01/D11，确认3–7，受限实现不可估 / H / 厂商授权固件/安全样机 |
| C06 RealVideo、VP8、AVS3等跨芯片模块 | 缺失 | V3开关/旧加载列表有额外codec；V4的T7掩码**不含VP8/Real/AVS3**。这里只保留范围审计，不把它们当T7已知能力欠账 | 不做无T7硬件证据的驱动承诺；调查1–2 / M / 厂商T7报告/真实样本。若后续证明可用，重新纳入目标；软件解码可另用但不是硬件对齐 |

R07、E05、C06 是范围边界行，计数表示当前没有对应完整交付，不表示厂家已在本板验证。
核心编码正式实现必须仍保护 DMA 所有权；超时后提前归还 vb2 缓冲会造成硬件写已释放内存，
不能用 `job_finish` 或 queue_error 单独宣称已隔离。12-bit 的当前事实优先于任务列举中的旧描述。
