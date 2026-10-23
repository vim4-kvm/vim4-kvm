# 显示、VPU 与图像处理

固定比较基线、V/E 路径和行号规则见 [证据索引](sources.md)。本页 13 项计入 [总表](../vendor-parity.md)。
路线“重写”指进入主线框架，不承诺补丁已被上游接收；工作量是一人有效人日，含定向验证，
不含文档/授权等待。H=高风险，M=中风险；每行估计不可直接相加，依赖可共用。

| ID / 厂商能力及来源 | 7.3 状态 | 差异、现有证据 | 建议路线、依赖 / 人日 / 风险 / 验证硬件 |
|---|---|---|---|
| D01 固定 HDMI 亮屏；V1:1788,1848，V2:amhdmitx | 部分对齐 | M0 simpledrm/tty0 已过；依赖固件已设定的静态 framebuffer，不能控制真实模式。[M0](../bringup/2026-10-23-display-m0-r4.md)，E2 display-m0 | 重写 DRM/KMS；承接正在进行的 M1 固定模式/共存任务，M0 为临时；共享资源归属→atomic scanout。剩余 5–12 / H / HDMI-OUT 采集卡、1080p sink、运动源 |
| D02 EDID、HPD、原生 modeset、多分辨率；V1:1848，V2:amhdmitx | 部分对齐 | E7 有 TMDS bridge，但 M0 的 native VPU disabled；M1 固定 sink 也不是动态 HPD。[显示调查](../bringup/2026-10-23-display-feasibility.md) | 重写 DRM connector/bridge/PHY/CCF；D01 共存通过后 M2，补无屏启动、反复插拔/切模式、4K/SCDC；4–8 / H / 两类 sink、可人工插拔、4K60 采集卡 |
| D03 多 OSD/视频平面、缩放、AFBC、VPP/RDMA/色彩；V1:1788,2078，V2:rdma/vpu/amlvecm | 部分对齐 | E7 有部分 T7 OSD/VENC 代码，部署只保留 M0；未验 atomic planes、AFBC、HDR 输出、multi-vout。VOUT2/3 节点不证明板上有三路屏 | 重写 DRM planes/atomic/color properties；D01/D02＋DMA/fence/共享 VCBUS；15–30 / H / 4K/HDR sink、测试图/多平面播放器。逐项清点可路由输出，禁止以 DTS 节点数承诺多屏 |
| D04 HDMI 输出高级链路与色深；V1:1848，V2:amhdmitx | 缺失 | E7 限 TMDS≤600MHz、RGB8、无 HDCP；厂商 HDMITX21/DSC 开关跨 SoC 共用，不能据名称承诺 T7 FRL/DSC/VRR。当前缺 444/422/深色与完整 infoframe 验收 | 重写 DRM HDMI helpers/色彩、PHY；先按厂商 T7 分支确认硬件能力，再 D02/D03；10–25 / H / HDMI 分析仪、10/12-bit HDR sink；若某协议无 T7 实现则从目标剔除并附证据 |
| D05 CEC 与 ARC 控制；V2:2438（enabled，AO mailbox） | 缺失 | E1/E7 没有本板已接通/验收的 CEC adapter；普通 HDMI 图像不证明 CEC 工作 | 重写 CEC framework，复用厂商 T7 寄存器/固件协议；D02、mailbox/唤醒归属；5–10 / M / 支持 CEC/ARC 的电视、CEC 分析器 |
| D06 VDIN1 输出回写/截图；V1:1877，V0:1792 | 缺失 | E2 只有 VDIN0；simpledrm 读缓冲不等价于 VDIN1 writeback，旧 video71 不是 HDMI 输入 | 重写 DRM writeback connector 或 V4L2 capture；D01/D03 与 VDIN 仲裁；6–12 / H / HDMI-OUT 图案源、独立采集器 |
| D07 GE2D blit/缩放/格式转换；V2o:3354，V1:2237 | 部分对齐 | E 树有 `drivers/media/platform/amlogic/meson-ge2d`，没有本板 T7 使能/验收证据；VDIN 缩放已过不能替代任意内存 blit。[缩放](../bringup/2026-10-21-edge-scaling-jpeg.md) | 重写/扩展标准 V4L2 M2M，按 T7 DMA/时钟/域核对；genpd＋dma-buf fences；8–15 / M / VIM4、离线图案与 DMA 压力 |
| D08 DI 去隔行、cadence/后处理；V2:multi-di，C drivers/media/di_multi/Kconfig:8 | 缺失 | E3 明确拒绝隔行，未接 DI。不能把拒绝危险输入作为厂商能力对齐 | 重写 V4L2 M2M 去隔行，先 weave/bob 再运动自适应；R04、DI 固件/时钟和共享 VPU；15–30 / H / 真 480i/576i/1080i 源、场序图案 |
| D09 HDR/色彩增强与 LUT；V1:2078，V2:lut_dma/amlvecm | 部分对齐 | 只实现限定 RX PQ→SDR HDR2；厂商 VECM、输出色彩管理、其他 LUT 未对齐。[HDR](../bringup/2026-10-20-edge-hdr-capture.md)，E3/E7 | 重写 V4L2 colorimetry＋DRM color pipeline；避免私有 sysfs 成为终态；R03/D03，10–20 / H / PQ/HLG 源、校色仪/HDR sink |
| D10 Dolby Vision 算法/授权播放；V1:807，V2:dolby_fw，C enhancement/amdolby_vision/Kconfig:10 | 无法做到 | 当前缺授权算法、有效证书/安全世界闭源服务的完整交付条件。节点 okay/CONFIG_DOLBYVISION=y 不代表可合法复现完整处理 | 当前不做算法重写；先取得授权及可用固件/用户态合同，再评估 DRM/V4L2 集成。资料确认 2–5，实施无法估计 / H / 授权 DV 源、sink、合规测试设备 |
| D11 HDCP/安全视频端到端；V1:216,807，V2:vpu_security，V2:340 | 无法做到 | E7 无 HDCP；现有 OP-TEE/JPEG 不证明密钥、受保护显示链与 DRM 内容授权可用。缺 provisioned keys/TA 文档，不能生成或导出厂商密钥 | 当前不做密钥/TA 替代；取得厂商支持后经 DRM content protection＋安全 DMA 路线，依赖 Q01/Q04。确认 3–5，实施不可估 / H / 有授权源/sink、专用测试机 |
| D12 旧 amvideo/VFM/ION/UVM/videotunnel/私有显示 ABI；V1:308,789–929，V2:meson_uvm/video_composer | 缺失 | E2/E3 用 V4L2 dma-buf；E7 用 DRM。旧闭源用户态的 ABI/时序行为不能视为已有兼容能力；KVM 应用已走独立后端 | 不做旧 ABI 兼容，保留功能目标：DRM GEM/PRIME、dma-heap/dma-buf、V4L2、显式同步。消费者梳理 2–4 / M / 真实旧应用和标准替代程序；闭源仅认旧 ABI 时需厂商改用户态 |
| D13 GDC/dewarp/CVE 图像处理；V2o:3400,3417；V2:cve/amlgdc | 缺失 | 两板型节点不同，E1 无对应启用链，不能把 C3 ISP 或 GE2D 当 T7 GDC | 重写标准 V4L2 M2M controls；先取厂商畸变网格/系数协议、确认 CVE 消费者，D07/ISP 内存生命周期；12–25 / H / 标定网格、对应摄像头/镜头 |

D10/D11 的“无法做到”限定为当前开放代码、授权与固件条件，**不是**断言硅片永远不能做。
外围功能可以移植厂商实现后整理；本页显示、采集后处理和核心 DMA 生命周期应直接收敛到
DRM/V4L2/genpd。相关安全加载可保留经过核对的厂商协议后端。
