# HDMI 输入、编码与解码

本页 18 个审计项，其中16项计入追平目标；固定路径/行号见 [证据索引](sources.md)，
范围与计数见 [总表](README.md)。
H/M 是高/中风险；估算为一人有效人日，等待固件/现场窗口另计，共用依赖不能重复累加。

2026-10-23 重计按已提交窗口：E02 单列“已上板验证待部署”；E01 动态参数、
LTR、分层 GOP 与多实例恢复已有[实际码流证据](../bringup/2026-10-23-wave5-e01-window.md)，
但 ROI、任意 GOP、VUI/SEI 和真实固件硬锁仍欠账。C01 最新候选有 IRQ/超时诊断，
尚无正确首帧；合入源码时 VDEC DT 和试验参数仍默认关闭。

| ID / 厂商能力及来源 | 7.3 状态 | 差异、现有证据 | 路线、依赖 / 人日 / 风险 / 验证硬件 |
|---|---|---|---|
| R01 HDMI RX/DDC/EDID/HPD 与自动恢复；V1:541–594 | 部分对齐 | E3 标准 EDID/时序接口、源端读回与 19 档通过；仍有 FDET 无效快照触发错误停流。[模式](../bringup/2026-10-22-edge-hdmi-modes-final.md)、[停流审计](../bringup/2026-10-22-wave5-first-failure-audit.md) | 重写/完善 V4L2 subdev＋source events；承接现有音频/采集稳定性任务，统一活动租约测量错误分类，不能靠反复 HPD 自愈；4–8 / H / 可切分辨率/断信号 HDMI 源，浏览器运动源 |
| R02 VDIN0 DMA、MMAP/dma-buf/缩放；V1:1858，V2:codec_io | 部分对齐 | E2/E3 已有直接 DMA、帧一致性、缩放和回收；仍是 test 驱动/独占整窗 VCBUS，固定参数与局部资源管理不是终态。[DMA](../bringup/2026-10-20-direct-dma-benchmark.md)、[缩放](../bringup/2026-10-21-edge-scaling-jpeg.md) | 重写标准 media graph、vb2/PM/资源所有权；与 M1 共享资源方案合并一次，D01/R01；8–15 / H / HDMI 双向接线、运动一致性图案、DMA 压力 |
| R03 HDR10 与 HLG 输入/色彩；V1:541,2078 | 部分对齐 | E3:949 对非合格 PQ 扩展色域拒绝，HLG 临时拒绝；PQ/BT.2020 的受限映射已过，桌面白/长期映射仍有限。[HDR](../bringup/2026-10-20-edge-hdr-optimization.md) | 重写 V4L2 colorimetry/HDR controls 与 HDR2 EOTF/矩阵/曲线原子更新；R01/R02 后补 HLG→SDR，不能把“SDR 回退”算完成；8–15 / H / 真 HLG/PQ 10bit 源、灰阶/色卡与测色工具 |
| R04 隔行、像素重复与传统时序；V1:541，V2:multi-di | 缺失 | E3:977,1035 拒绝隔行/像素重复；19 档逐行不覆盖 480i/576i/1080i。[模式范围](../bringup/2026-10-22-edge-hdmi-modes.md) | 重写 field/场序/时序＋V4L2 去隔行，保留拒绝直至 D08 可用；8–15（不含 D08）/ H / 真隔行 HDMI 源、场标记 |
| R05 深色 RGB/444/422/420、12-bit；V1:541,1858 | 部分对齐 | **不是一律拒绝 12bit**：E3:903 解析并配置 8/10/12bit。12bit 请求实际发送444/8；422容器/GCP=0也不能证明源精度12bit。真实 RGB 深色、422 SDR 仍缺覆盖；输出 NV12 为8bit。[实际格式](../bringup/2026-10-22-edge-hdmi-modes-final.md) | 重写/完善标准格式协商、packing/截位/抖动；先真12bit输入，再按厂商核对原生高位深 DMA/P010 是否可实现；5–12 / M / 可强制 RGB/422/444 10/12bit 的发生器/分析仪 |
| R06 原生 4:4:4 采集；V1:1858，厂商 vfm_cap 扩展 | 缺失 | 5.15 4K60 原始444已验；E3 VDIN 只暴露 NV12/RGB24，RGB24转换不能当原生444 planes。[厂商444](../bringup/2026-10-16-4k60-yuv444-raw-capture.md) | 重写 V4L2 YUV444/NV24 等真实 DMA 布局及 CPU access 同步；R02/R05；5–10 / M / 单像素色度/同帧标记源、原始文件检查 |
| R07 多路 RX、特殊 PHY/板型；V1:541 port_map，V2:HDMIRX | 部分对齐 | E2 固定 input-port=1，实际板载输入可用；其他 T7 RX port 并无本板连接验收。不能把 SoC 全端口列成 VIM4 多物理输入 | 重写 PHY/端口/标准路由描述；先查板图和实际接线，无布线端口不做产品入口；3–6 / M / 两版 VIM4、原理图/可接端口夹具 |
| E01 MultiEnc AVC/HEVC、码率/GOP/IDR/逐行刷新；V2:2566，V3:149–179 | 部分对齐 | E4 标准 V4L2 M2M 可达4K60，IDR/profile/刷新已有回归；未覆盖厂商全部控制、多实例/高位深。[Wave5](../bringup/2026-10-19-wave521-uhd.md)、[IDR](../bringup/2026-10-20-onekvm-wave5.md) | 重写/完善 V4L2 controls、调度和固件协议；E02/E03 后做厂商参数逐项等效，8–15 / H / 固定录制输入、参考解码、双实例与运动场景 |
| E02 非8对齐 HEVC 可见尺寸；V3:155/161，V5 | 已上板验证待部署 | 内核已有标准 selection、内部 padding/conformance window；[十组 NV12/NV12M 码流、1366×768 非零 crop](../bringup/2026-10-23-wave5-parity-window.md#e02b-帧与多实例)逐帧解码通过，含行列补边和 drain。正式 eeddb005 不含该能力 | 限偶数 4:2:0 可见矩形；One-KVM `20d8010d` 无旧内核探测，保持功能分支和生产 AVC 回退。待匹配内核批次；共享同 fd 多 plane 非零 offset 等布局另验，不扩张本行范围 |
| E03 Wave5 超时隔离、取消与恢复；V5:436,1390,3421 | 部分对齐 | 正式 eeddb005 含[受控 power-cycle/固件重载](../bringup/2026-10-23-wave5-runtime-window.md)，失败仍保留 DMA；[E01 候选](../bringup/2026-10-23-wave5-e01-window.md)验证 SET_PARAM、多实例注入及同页恢复、失败隔离。健康固件注入不代表真实挂死已解决 | V4L2 M2M/genpd：继续真实硬锁的 DMA 停止、总线状态和长期多实例验收；不可用 job_finish 提前归还缓冲。10–20起 / H / 串口、独立复位、受控故障注入 |
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
