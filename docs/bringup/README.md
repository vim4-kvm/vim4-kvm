# 上板记录索引

- [原生HDR10 r3离线候选](2026-10-31-hdr10-remote-candidate.md) — kernel video application offline candidate

每条记录一个文件，位于 `bringup/日期-主题.md`。先按日期或标签在本页找到条目，只打开需要的文件；
不要通读整个目录。标签：board、kernel、video、audio、usb、application、pikvm、uu、manager、deployment。

新记录：新建 `bringup/YYYY-MM-DD-英文短名.md`，首行 `# YYYY-MM-DD：标题`，并在本页对应日期下追加一行。

## 按任务查找

- 内核：[启动](2026-10-19-edge-firstboot.md) → [合入](2026-10-23-mainline-integration.md) → [差距](2026-10-28-kernel73-parity-audit.md)。
- 音视频：[双路径](2026-10-25-native-hdr-dual-path.md)、[HDR](2026-10-26-all-kvm-hdr.md)、[延迟](2026-10-27-current-video-latency.md)。
- USB：[PD](2026-10-12-pd-boot-init.md)、[组合](2026-10-21-edge-usb-functions.md)、[介质](2026-10-18-nas-storage-usb-disk.md)。
- 应用：[切换](2026-10-13-nanokvm-deploy-jetkvm-switch.md)、[登录](2026-10-18-unified-auth-gateway.md)、[UU](2026-10-25-uu-protocol-audit.md)。
- 部署：[组件](2026-10-13-component-deploy-loop.md)、[双内核](2026-10-21-dual-kernel-integration.md)、[回退](2026-10-22-edge-7-3-final-deploy.md)。

以下保留完整日期索引。这些里程碑记录的是历史证据；查找当前架构和约束时，仍应先读对应子系统入口。

## 2026-10-31

- [原生HDR修复包复验与同源5.15码流](2026-10-31-hdr10-remote-r7.md) — kernel board video application
- [原生HDR r6十位DMA、Panfrost与编码caps阻塞](2026-10-31-hdr10-remote-r6.md) — kernel board video application gpu
- [7.3原生远程HDR离线调查与分阶段门禁](2026-10-31-hdr10-remote-offline.md) — kernel video application uu offline
- [uhd4正式完整构建、短烟测与队列工具修正](2026-10-31-uhd4-formal-smoke.md) — kernel board video hdr npu gpu deployment
- [uhd4正式准备与旧heavy锁阻塞，未上板](2026-10-31-uhd4-formal-preparation.md) — kernel deployment
- [HDR2双向恢复分解、uhd4r3细采样与长尾门禁](2026-10-31-hdr2-recovery.md) — kernel board video hdr application npu gpu
- [MCP与ICE定位、uhd4 PQ门禁及恢复速度余项](2026-10-31-hdr2-mcp-ice-pq.md) — kernel board video hdr application
- [uhd4主题整理与SDR回归，MCP/接收端门禁阻断](2026-10-31-hdr2-uhd4-gate.md) — kernel board video hdr npu gpu

## 2026-10-30

- [HDR2a5产品DMA恢复、逐代退休与4K60门禁](2026-10-30-hdr2a5-window.md) — kernel board video hdr application
- [HDR2a3的VUI、色差、4K60与退休/产品恢复余项](2026-10-30-hdr2a3-window.md) — kernel board video hdr
- [HDR2a2的MCP、4K60与VUI/色准余项](2026-10-30-hdr2a2-window.md) — kernel board video hdr
- [MCP开启PQ与HDR2编码协商阻断](2026-10-30-hdr2-unified-window.md) — kernel board video hdr
- [HDR2 PQ的SDR基线与受限shadow诊断](2026-10-30-hdr2-pq-window.md) — kernel board video hdr
- [uhd3 GPU候选与HDR离屏窗口A](2026-10-30-gpu-hdr-window-a.md) — kernel board video benchmark
- [NPU与nodebug正式uhd3合入、回归及manager EDID部署](2026-10-30-uhd3-formal-regression.md) — kernel board video manager deployment
- [nodebug两启动对门禁与绑核尺寸曲线](2026-10-30-nodebug-paired-gate.md) — kernel board benchmark video
- [nodebug消除tmpfs写入差距与60fps回归](2026-10-30-nodebug-memory-window.md) — kernel board benchmark video
- [YOLO端到端差距定位到文件写入](2026-10-30-npu-e2e-window.md) — kernel board benchmark
- [GPU同块回跳修复与快轮询窗口](2026-10-30-gpu-repair-window.md) — kernel board video benchmark
- [uhd2四启动对性能门禁仍不确定](2026-10-30-npu-boot-pairs.md) — kernel board benchmark
- [保留循环候选、正确性与冷恢复实测](2026-10-30-gpu-loop-window.md) — kernel gpu board benchmark
- [uhd2集成输出与并行通过，DenseNet性能阻断pin](2026-10-30-npu-uhd2-acceptance.md) — kernel board benchmark video
- [Mesa展开候选与10ms调频配对窗口](2026-10-30-gpu-candidate-window.md) — kernel gpu board benchmark
- [npu4三模型、取消与视频并行门禁通过](2026-10-30-npu4-acceptance.md) — kernel board benchmark video
- [GPU 性能差距分解窗口](2026-10-30-gpu-diagnosis-window.md) — kernel gpu board benchmark
- [npu3 视频恢复与 YOLO缓存合同、恢复后延迟失败](2026-10-30-npu3-acceptance.md) — kernel board benchmark video
- [npu2 双模型通过与 YOLO/视频门禁失败](2026-10-30-npu2-acceptance.md) — kernel board benchmark video
- [GPU 三栈上板验收](2026-10-30-gpu-acceptance.md) — kernel gpu board benchmark
- [ADLA 首次上板验收与 npu1 probe 失败](2026-10-30-npu-adla-acceptance.md) — kernel board benchmark
- [私有 Mesa 26.2.6 离线运行时](2026-10-30-gpu-runtime.md) — kernel gpu packaging
- [GPU 完整性审查与默认降频候选](2026-10-30-gpu-parity.md) — kernel gpu audit
- [7.3 保留运行时与发布锁同步](2026-10-30-kernel73-retained-pin.md) — kernel deployment application
- [第三轮尺寸与原生 GPU 定向复验](2026-10-30-kernel73-gap-r3.md) — kernel video manager deployment
- [7.3 差距补齐批量验证](2026-10-30-kernel73-gap-validation.md) — kernel video usb manager deployment

## 2026-10-29

- [管理面板中英文界面](2026-10-29-manager-i18n.md) — manager application deployment
- [One-KVM 新图标](2026-10-29-onekvm-icon.md) — application deployment
- [One-KVM 连接统计的采样精度](2026-10-29-onekvm-connection-stats.md) — application deployment board

## 2026-10-28

- [One-KVM 控制台面板、虚拟键盘与 WebRTC 套接字耗尽](2026-10-28-onekvm-console-panels.md) — application deployment board
- [One-KVM 终端浮层与断线提示](2026-10-28-onekvm-terminal-polish.md) — application deployment board
- [One-KVM 板子终端侧栏](2026-10-28-onekvm-board-terminal.md) — application deployment board
- [管理器界面体验整理](2026-10-28-manager-uiux.md) — manager application deployment board
- [7.3 对当前 5.15 功能的差距复核](2026-10-28-kernel73-parity-audit.md) — kernel video audio usb application audit
- [低频原生音频诊断](2026-10-28-audio-diagnostics.md) — audio application board
- [源端空闲时非静音音频与数字静音恢复](2026-10-28-source-idle-audio.md) — audio uu application board
- [UDP 同帧批量发送候选与延迟对照](2026-10-28-udp-batch-latency.md) — video application board benchmark

## 2026-10-27

- [当前 One-KVM 延迟与 SDR 缩放瓶颈](2026-10-27-current-video-latency.md) — video application board benchmark
- [HEVC 无损与固定 QP](2026-10-27-hevc-quality.md) — video application deployment board
- [共享编码的 SRT 与 RTMP 输出](2026-10-27-shared-broadcast.md) — video audio application deployment board
- [NPU 真实推理与分类、文字识别验证](2026-10-27-npu-inference.md) — kernel application board benchmark
- [UU 分辨率请求被 HDR 能力检查阻塞](2026-10-27-uu-resolution-hdr-preference.md) — uu video application deployment board
- [管理器资源趋势 GPU 使用率](2026-10-27-manager-gpu-trends.md) — manager application deployment board
- [信号变化自动恢复与切换停顿](2026-10-27-signal-recovery.md) — video application deployment board benchmark
- [UU 原生 HDR 能力与非对齐行宽修复](2026-10-27-uu-hdr.md) — video uu application deployment board
- [UU HDR 降分辨率的 GPU 缩放](2026-10-27-uu-hdr-scale.md) — video uu application deployment board benchmark
- [四套 KVM 共用 HDR GPU 缩放](2026-10-27-all-kvm-hdr-scale.md) — video application deployment board benchmark
- [超宽屏 SDR 硬件缩放与尺寸控制](2026-10-27-sdr-scale-controls.md) — video application pikvm deployment board benchmark

## 2026-10-26

- [四套 KVM 的远程 HDR 接入](2026-10-26-all-kvm-hdr.md) — video application manager deployment board
- [Chrome 与 Safari 的远程 HDR 兼容性复核](2026-10-26-hdr-browser-compatibility.md) — video application board
- [远程 HDR 全局默认与源端切换](2026-10-26-hdr-global.md) — video manager uu application deployment board
- [GPU 转换、DMA Main10 与网页真 HDR 60fps](2026-10-26-hdr-gpu-pipeline.md) — video application deployment board benchmark
- [HDR 分段测量与私有 Mali Vulkan 驱动](2026-10-26-hdr-gpu.md) — video kernel deployment board benchmark
- [远程 HDR 像素修复与 SDR 自动选择](2026-10-26-remote-hdr-pixels.md) — video application kernel deployment board
- [远程 Main10 HDR 与高刷超宽屏](2026-10-26-remote-hdr-modes.md) — video kernel uu application deployment board
- [统一 RTK UHD HDR 入口](2026-10-26-rtk-unified.md) — video application manager board deployment
- [VRR 范围声明纠正与 4K 输入验证](2026-10-26-vrr-range-4k.md) — video kernel application board
- [真实 VRR 输入与 One-KVM 连续画面](2026-10-26-vrr-live.md) — video kernel application board
- [VRR 输入候选部署与 KVM 回归](2026-10-26-vrr-input.md) — video kernel application manager board deployment
- [5.15 1080p120 候选部署](2026-10-26-1080p120.md) — video kernel application board deployment
- [厂商编码器码率峰值与 VBV 对照](2026-10-26-encoder-vbv.md) — video board benchmark

## 2026-10-25

- [VIM4 SRTP HMAC 后端正式接入](2026-10-25-srtp-openssl-hmac.md) — video application board benchmark
- [RTP 发送离线基准与板端 CPU 回放](2026-10-25-rtp-send-benchmark.md) — video application board benchmark
- [交帧之后的编码、发送与浏览器分段](2026-10-25-video-downstream-latency.md) — video application board
- [显示与采集交付边界核实](2026-10-25-video-front-boundaries.md) — video kernel application board
- [One-KVM 同帧分段延迟](2026-10-25-video-stage-latency.md) — video application board
- [VDIN1 逐缓冲交付与 RDMA 时序核实](2026-10-25-vdin1-frame-handoff.md) — video kernel board
- [5.15 / 7.3 视频延迟对照与 Wave5 启动修复](2026-10-25-kernel-video-latency.md) — video kernel application deployment board
- [原生 HDR 双路径的四应用采集修复](2026-10-25-native-hdr-all-kvm.md) — video application pikvm deployment board
- [管理面板前端重构验收与部署](2026-10-25-manager-ui.md) — manager application deployment
- [UU 协议审查与 P1 修复验收](2026-10-25-uu-protocol-audit.md) — uu application video audio usb audit
- [UU P1 修复部署与自动验证](2026-10-25-uu-p1-validation.md) — uu onekvm video board
- [UU 缩放 CMA 生命周期与工具连接](2026-10-25-uu-cma-tools.md) — uu onekvm video board
- [UU 限定板子文件传输](2026-10-25-uu-files.md) — uu onekvm usb application board
- [厂商 HDR 输入黑屏、采集位深与输出域](2026-10-25-vendor-passthrough-hdr.md) — kernel video audio manager board
- [厂商原生 HDR 与 SDR KVM 双路径交付](2026-10-25-native-hdr-dual-path.md) — kernel video audio onekvm board
- [原生 HDR 正式部署与 AVI 色域恢复](2026-10-25-native-hdr-production.md) — kernel video manager onekvm board
- [原生 HDR↔SDR 采集颜色跟随与独立曲线](2026-10-25-native-hdr-color.md) — kernel video uu onekvm board
- [HDMI 输出 HDR 偏好与独立显示映射](2026-10-25-passthrough-hdr-switch.md) — kernel video manager deployment board
- [透传音频 xrun 原地恢复与连续 TX](2026-10-25-passthrough-audio-recovery.md) — audio video manager deployment board
- [厂商 VAPB 最低需求修复、60fps 与默认内核部署](2026-10-25-vapb-clock.md) — kernel video audio uu deployment board
- [厂商 5.15 HDMI 音频桥与 KVM 共存](2026-10-25-vendor-passthrough-audio.md) — audio video manager deployment board
- [音频寄存器只读诊断触发重启](2026-10-25-audiobus-read-abort.md) — audio kernel deployment board uu
- [厂商 5.15 真实 1080p60 EDID 跟随](2026-10-25-vendor-passthrough-1080p.md) — video manager uu deployment board
- [UU 缩放生产合入与时钟失败降级](2026-10-25-uu-scaling-production.md) — video application uu deployment board

## 2026-10-24

- [UU 缩小输出的 GE2D 时钟与流水线修复](2026-10-24-uu-scaled-60fps.md) — video application uu deployment board
- [厂商 5.15 透传 OUT 热插拔恢复](2026-10-24-vendor-passthrough-hpd.md) — kernel video manager deployment board
- [厂商 5.15 透传 TEE 离线设计](2026-10-24-vendor-passthrough-design.md) — kernel video audio manager deployment
- [厂商 5.15 周期黑屏诊断与修复](2026-10-24-vendor-passthrough-blackout.md) — video manager deployment board
- [厂商 5.15 HDMI 透传交付与待验证项](2026-10-24-vendor-passthrough.md) — kernel video audio manager deployment board
- [颜色候选交付门禁失败与管理器预览](2026-10-24-display-color-user-handoff.md) — kernel video usb manager deployment board
- [HDMI 透传第二阶段暂停与恢复入口](2026-10-24-hdmi-passthrough.md) — kernel video deployment board
- [7.3颜色与透传源码合入及默认开关](2026-10-24-hdmi-integration.md) — kernel video deployment
- [HDMI 采集 ERROR、周期量化与厂商对照（进行中）](2026-10-24-hdmi-capture-quantization.md) — kernel video deployment board
- [HDMI RX 计量器与持续采集复测（进行中）](2026-10-24-hdmi-capture-stability.md) — kernel video deployment board
- [HDMI OUT 颜色自环校准与厂商基准](2026-10-24-display-color-loop.md) — kernel video deployment board

## 2026-10-23

- [统一合入主线，保留稳定 KVM 部署](2026-10-23-mainline-integration.md) — kernel application deployment board
- [RX 阶段收尾：矩阵残留问题与稳定 KVM](2026-10-23-hdmirx-lowclock-closeout.md) — kernel video usb deployment board
- [M3 4K 显示器窗口：链路与出声，颜色和 GPU 阻塞](2026-10-23-display-m3-window4.md) — kernel video audio usb deployment board
- [HDMI 模式切换失锁：基线对照与稳定判定](2026-10-23-hdmirx-lowclock.md) — kernel video deployment board
- [Wave5 正式批次：HDMI 模式门禁失败并回退](2026-10-23-wave5-formal-deploy.md) — kernel video audio usb application deployment board
- [M3 HDMI 离线验证与一次性启动清单](2026-10-23-display-m3-hdmi-validation.md) — kernel video audio deployment
- [M2 第三窗口：物理颜色对照、TX 录音与 HPD 修复](2026-10-23-display-m2-window3.md) — kernel video audio deployment board
- [M3 HDMI HDR、10-bit、420 与跳行缩放（候选，HDR 与颜色阻塞）](2026-10-23-display-m3-hdmi-color.md) — kernel video audio deployment
- [M3 VD1/VD2、PPS 与 NV12 atomic scanout（离线候选，未上板）](2026-10-23-display-m3-video-planes.md) — kernel video deployment
- [T7 H.264 FIFO 修正、43 次 IRQ 与全零帧现场结果](2026-10-23-vdec-timeout.md) — kernel video usb deployment board
- [T7 H.264 启动链与安全微码审计明细](2026-10-23-vdec-timeout-audit.md) — kernel video
- [T7 VDEC 多 fd 所有权与分级解码窗口](2026-10-23-vdec-multifd.md) — kernel video usb deployment board
- [M3 视频 MIF、PPS 相位与 VD2 SRAM（离线，尚无 video plane）](2026-10-23-display-m3-video-parameters.md) — kernel video deployment
- [T7 VDEC p0 访问通过、compliance 阻塞与 RX 停顿归类](2026-10-23-vdec-p0-window.md) — kernel video usb deployment board
- [M3 DMA 边界修复、启动接管与剩余视频路径合同（离线）](2026-10-23-display-m3-dma-contracts.md) — kernel video deployment
- [T7 VDEC 外部控制寄存器全量差分](2026-10-23-vdec-register-diff.md) — kernel video usb deployment board
- [M3 多层退休、SRAM 所有权与 OSD overlay/cursor（离线）](2026-10-23-display-m3-layers.md) — kernel video audio deployment
- [VDEC APB 候选第九步仍失败，看门狗恢复](2026-10-23-vdec-apb-window.md) — kernel video usb deployment board
- [Wave5 E01 动态控制、分层 GOP 与 LTR 上板窗口](2026-10-23-wave5-e01-window.md) — kernel video usb deployment board
- [厂商 H.264 活体对照与物理时钟检查候选](2026-10-23-vdec-vendor-live.md) — kernel video usb deployment board
- [Wave5 E01 动态参数、LTR 与多层 GOP（离线）](2026-10-23-wave5-e01-runtime-gop.md) — kernel video
- [Wave5 E01 ROI、任意 GOP 与 VUI/SEI 剩余合同](2026-10-23-wave5-e01-metadata-abi.md) — kernel video
- [T7 GCLK 十三步远程窗口：首次读失败、看门狗恢复](2026-10-23-vdec-gclk-window.md) — kernel video usb deployment board
- [M3 首批离线实现：OSD 原子属性与标准 CEC，其余显示层待开发](2026-10-23-display-m3.md) — kernel video audio deployment
- [T7 GCLK_EN 访问条件与分步候选（离线）](2026-10-23-vdec-gclk-offline.md) — kernel video deployment
- [T7 VDEC MDEC 远程分级窗口](2026-10-23-vdec-mdec-window.md) — kernel video usb deployment board
- [M2 颜色修正与第二个一次性窗口：共存通过，物理颜色和 TX 音频待验](2026-10-23-display-m2-window2.md) — kernel video audio deployment board
- [M2 首次一次性上板：60Hz 翻页、PRIME 上屏，颜色错误阻塞验收](2026-10-23-display-m2-window1.md) — kernel video audio deployment board
- [Wave5 编码器批量窗口与 T7 硬件看门狗](2026-10-23-wave5-parity-window.md) — kernel video deployment board
- [Wave5 E02 可见尺寸与 E01 标准控件离线候选](2026-10-23-wave5-encoder-parity.md) — kernel video
- [Wave5 E01 全量参数与标准控件映射](2026-10-23-wave5-encoder-controls.md) — kernel video
- [Wave5 E01 公共、动态与逐帧参数协议附表](2026-10-23-wave5-encoder-protocol.md) — kernel video
- [M2 原生 ENC2 模式切换：PLL/VENC/PHY、SCDC 与厂商参数对比（离线）](2026-10-23-display-m2-modeset.md) — kernel video audio deployment
- [HDMI RX 同链路 7.3 / 厂商 5.15 十分钟对照](2026-10-23-hdmirx-vendor-comparison.md) — kernel video audio deployment board
- [M2 RDMA 翻页与独立 TX 音频：离线实现，原生 modeset 仍缺失](2026-10-23-display-m2-rdma-audio.md) — kernel video audio deployment
- [厂商5.15一次性启动往返与GPU用户态识别](2026-10-23-vendor-boot-gpu.md) — kernel deployment board
- [M1 合入与 M2 离线开发：HPD、EDID、线性 PRIME 和音频接口](2026-10-23-display-m2.md) — kernel video audio deployment
- [Wave5 运行时恢复：五轮注入、失败隔离与一次性启动窗口](2026-10-23-wave5-runtime-window.md) — kernel video deployment board
- [M1 第七窗口：一次性启动、RMFB、翻页与 Panfrost](2026-10-23-display-m1-window7.md) — kernel video deployment board
- [HDMI 音频与采集稳定性：27轮自动恢复与EAGAIN残留](2026-10-23-kvm-audio-capture-stability.md) — kernel audio video application deployment board
- [HDMI 音频 PCM 生命周期修复与 SARADC 正式部署：九类通过](2026-10-23-kvm-audio-capture-stability-deploy.md) — kernel audio video application deployment board
- [T7 DRM M1 固定输出、RMFB 崩溃与离线修复](2026-10-23-display-m1.md) — kernel video audio usb deployment board
- [M1 一次性启动与恢复安全网](2026-10-23-display-m1-safety.md) — kernel deployment
- [T7 DRM M1 共存接管设计](2026-10-23-display-m1-design.md) — kernel video audio
- [Wave5 独立电源域复位与固件冷重载（离线候选）](2026-10-23-wave5-genpd-recovery.md) — kernel video power deployment
- [Wave5 运行时硬复位地址冲突与拓扑保护（仅离线，恢复受阻）](2026-10-23-wave5-runtime-recovery.md) — kernel video
- [Wave5 隔离正式窗口复验](2026-10-23-wave5-isolation-final.md) — kernel video audio usb manager deployment board
- [Wave5 超时隔离与十轮验收（第二轮）](2026-10-23-wave5-isolation.md) — kernel video application deployment board
- [Wave5 恢复前置修复与厂商复位审查（未上板）](2026-10-23-wave5-recovery.md) — kernel video
- [M0 第四轮音频归因与发布](2026-10-23-display-m0-r4.md) — kernel video audio usb manager deployment board
- [HDMI RX 音频 ENOLINK 基线对照](2026-10-23-hdmirx-audio-enolink.md) — kernel audio application board
- [M0 音频复核与正式部署回退](2026-10-23-display-m0-deploy.md) — kernel video audio usb manager deployment board
- [U-Boot framebuffer 的 simpledrm 接管实验](2026-10-23-display-m0.md) — kernel video audio usb manager deployment board
- [7.3 T7 HDMI 显示输出可行性调查](2026-10-23-display-feasibility.md) — kernel video audio board
- [T7 显示硬件与源码明细](2026-10-23-display-hardware-audit.md) — kernel video audio

## 2026-10-22

- [手动 PD 协商合同持久化并保留](2026-10-22-pd-manual-contract.md) — usb deployment board
- [SARADC channel 2 超时取证与离线候选](2026-10-22-saradc-timeout-audit.md) — kernel board
- [Wave5 首轮部署采集停止复核](2026-10-22-wave5-first-failure-audit.md) — kernel video board
- [Wave5 尺寸与关闭路径防护正式部署](2026-10-22-edge-wave5-deploy.md) — kernel video audio usb manager deployment board
- [Wave5 HEVC 防护候选现场验证并恢复原模块](2026-10-22-wave5-hevc-field.md) — kernel video usb deployment board
- [U-Boot 现场复位分析与 microSD 安全验证](2026-10-22-uboot-sd-recovery.md) — usb kernel deployment
- [7.3 ramoops/pstore 正式部署并保留](2026-10-22-edge-pstore-deploy.md) — kernel deployment board
- [P1 浏览器音频观察器复核](2026-10-22-p1-browser-audio.md) — audio application board
- [PD 热重启历史合同卡片](2026-10-22-pd-warm-carryover.md) — usb manager deployment board
- [7.3 T7 标准硬件解码可行性调查](2026-10-22-vdec-feasibility.md) — kernel video board
- [T7 解码硬件、固件与主线差异明细](2026-10-22-vdec-hardware-audit.md) — kernel video
- [Wave521C GET_VPU_INFO 实机取证](2026-10-22-vdec-wave5-capabilities.md) — kernel video board
- [T7 stateless 解码离线准备](2026-10-22-vdec-t7-offline.md) — kernel video
- [T7 H.264 完整离线候选与现场恢复脚本](2026-10-22-vdec-candidate.md) — kernel video deployment
- [T7 解码候选现场分级验证与恢复](2026-10-22-vdec-field.md) — kernel video usb deployment board
- [T7 VDEC SError 离线修正与分级上电门禁](2026-10-22-vdec-power-fix.md) — kernel video deployment
- [T7 VDEC 第二次现场：单读通过、compliance panic与恢复](2026-10-22-vdec-field2.md) — kernel video usb deployment board
- [T7 MDEC SError 离线排查与安全策略、单读门禁](2026-10-22-vdec-mdec-offline.md) — kernel video deployment
- [P2 PD Request＋KASLR 合并固件候选](2026-10-22-p2-uboot-combined.md) — usb kernel deployment
- [P2 有界持久 journal 部署并保留](2026-10-22-p2-journal-deploy.md) — deployment board
- [P2 ramoops 候选与正常重启验证](2026-10-22-p2-pstore.md) — kernel deployment board
- [P1 HDMI 音频分段定位](2026-10-22-p1-hdmi-audio.md) — kernel audio application board
- [P1 HDMI 帧率、恢复与 CMA 复核](2026-10-22-p1-hdmi-video.md) — kernel video board
- [P2 USB 音频、组合与 RNDIS 核对](2026-10-22-p2-usb-audio.md) — usb audio application board
- [P2 KASLR、随机数与 U-Boot 离线候选](2026-10-22-p2-kaslr.md) — kernel deployment board
- [P2 GPU 电压表复核](2026-10-22-p2-gpu-voltage.md) — kernel
- [P2 挂起与唤醒离线审查](2026-10-22-p2-suspend-audit.md) — kernel usb
- [P2 持久日志与 ramoops 方案](2026-10-22-p2-persistent-logs.md) — kernel deployment
- [v7.3 正式版第三轮部署并保留](2026-10-22-edge-7-3-final-retained.md) — kernel video audio usb manager deployment board
- [U-Boot 固定 5V USB PD Request（离线候选）](2026-10-22-uboot-pd-request.md) — usb deployment

- [Wave5 非对齐 HEVC 挂起离线分析与局部修复候选](2026-10-22-wave5-hevc-hang-analysis.md) — kernel video
- [v7.3 正式部署尝试与自动回退](2026-10-22-edge-7-3-final-deploy.md) — kernel video audio usb manager deployment board
- [BCM43752 固件转储离线分析（原样本缺失）](2026-10-22-wifi-coredump-analysis.md) — kernel
- [v7.3 正式版运行时、PD-USB 与部署离线准备](2026-10-22-deploy-7-3-final-prep.md) — usb manager deployment kernel
- [HDMI 动态 LPCM 与无链路恢复](2026-10-22-edge-hdmi-audio.md) — kernel audio application deployment board
- [7.3 日志分级与 T7 硬件随机数](2026-10-22-edge-diag.md) — kernel usb deployment board
- [7.3 正式版 rebase 与整包回归](2026-10-22-edge-7-3-final.md) — kernel deployment board video usb
- [7.3 正式版整包上板回归](2026-10-22-edge-7-3-final-board.md) — kernel deployment board video usb
- [PD 热重启原因与主动查询风险审查（未刷写）](2026-10-22-pd-warmboot-audit.md) — usb manager deployment board
- [U-Boot PD 交接刷写与双内核验证](2026-10-22-pd-firmware-deploy.md) — usb manager deployment board
- [U-Boot PD 交接与管理器候选（第一轮离线准备）](2026-10-22-pd-firmware-handoff.md) — usb manager deployment board
- [7.3 HDMI RX 输入模式泛化](2026-10-22-edge-hdmi-modes.md) — kernel video application deployment board
- [HDMI 模式最终产物复核](2026-10-22-edge-hdmi-modes-final.md) — kernel video application deployment board

## 2026-10-21

- [7.3 GPU/IR 合并内核正式部署](2026-10-21-edge-gpu-ir-deploy.md) — kernel deployment board video usb
- [7.3 IR 开机自动加载 Khadas 键表](2026-10-21-edge-ir-autoload.md) — kernel deployment board
- [7.3 IR、板载按键与 SPI NOR 节点](2026-10-21-edge-ir-keys-spinor.md) — kernel board
- [7.x Panfrost 调频与 GPU 供电](2026-10-21-edge-gpu-devfreq.md) — kernel deployment board
- [7.x Wi-Fi Direct 创建、扫描与并发建组](2026-10-21-edge-wifi-p2p.md) — kernel deployment board
- [7.x 管理器状态、界面与 WPA3 适配](2026-10-21-manager-mainline-status.md) — manager kernel usb application deployment board
- [双内核完整系统集成与往返验收](2026-10-21-dual-kernel-integration.md) — application kernel video usb deployment
- [7.x USB 功能接入与主机传输](2026-10-21-edge-usb-functions.md) — usb application kernel deployment board
- [Wi-Fi 固件排查与 MJPEG 帧率分段](2026-10-21-edge-wifi-fps.md) — kernel video application deployment board
- [7.x VDIN 缩放与硬件 MJPEG](2026-10-21-edge-scaling-jpeg.md) — kernel video application deployment board
- [7.x 音画测量校准与漂移复核](2026-10-21-edge-av-calibration.md) — video audio application board
- [7.x HDR 切换与稳定性](2026-10-21-edge-hdr-stability.md) — video audio application deployment board

## 2026-10-20

- [One-KVM 接入 7.3 V4L2/Wave5](2026-10-20-onekvm-wave5.md) — application kernel video board
- [One-KVM 7.3 CPU 性能定位](2026-10-20-onekvm-performance.md) — application kernel video board
- [本地基准与 VDIN 直接 DMA](2026-10-20-direct-dma-benchmark.md) — application kernel video board
- [驱动原生基准、AVC profile 与采集内存](2026-10-20-driver-profile-memory.md) — kernel video board
- [实验 One-KVM 局域网登录入口](2026-10-20-edge-lan-gateway.md) — application manager board
- [7.3 One-KVM HID 接入](2026-10-20-edge-hid-integration.md) — application usb audio board
- [7.x UHD 清晰度与 Mac 渲染分辨率](2026-10-20-edge-uhd-detail.md) — application video board
- [7.3 HDMI LPCM 与 One-KVM 音频](2026-10-20-edge-hdmi-audio.md) — kernel audio application board
- [7.x Wave5 逐行刷新与卡顿对照](2026-10-20-edge-cyclic-refresh.md) — kernel video application board
- [7.x 输入状态等待与端到端延迟](2026-10-20-edge-status-latency.md) — kernel video application board
- [7.x 安静风扇曲线](2026-10-20-edge-quiet-fan.md) — kernel video deployment board
- [7.x BCM43752 SDIO Wi-Fi](2026-10-20-edge-wifi.md) — kernel deployment board
- [7.x 启动风扇与 HDMI 恢复](2026-10-20-edge-recovery.md) — kernel video audio application deployment board
- [7.x HDMI 真实输入时序](2026-10-20-edge-input-timings.md) — kernel video audio application deployment board
- [7.x 失锁期间的状态查询与队列锁](2026-10-20-edge-queue-lock.md) — kernel video audio deployment board
- [7.x 1080p60/4K60 自动切换与缓冲回收](2026-10-20-edge-dynamic-modes.md) — kernel video audio application deployment board
- [7.x HDR10 链路与元数据观测](2026-10-20-edge-hdr-observation.md) — kernel video deployment board
- [7.x HDR10 采集与 HDR→SDR](2026-10-20-edge-hdr-capture.md) — kernel video audio application deployment board
- [7.x HDR 高光与连接优化](2026-10-20-edge-hdr-optimization.md) — video audio application deployment board

## 2026-10-19

- [7.3 edge 首次启动](2026-10-19-edge-firstboot.md) — kernel deployment board
- [7.3 CRG UDC 与最小 HID 实测](2026-10-19-crg-udc.md) — kernel usb board
- [7.3 CRG 真实 HID 与只读虚拟盘](2026-10-19-crg-composite.md) — kernel usb board
- [7.3 HDMI RX 资源与源端 5V 实测](2026-10-19-hdmirx-resources.md) — kernel video board
- [7.3 HDMI RX EDID 与源端 DDC 读回](2026-10-19-hdmirx-ddc.md) — kernel video usb board
- [7.3 HDMI RX 固定频率 PHY PLL 实测](2026-10-19-hdmirx-phy.md) — kernel video board
- [7.3 HDMI RX 1080p 完整视频帧](2026-10-19-hdmirx-frames.md) — kernel video board
- [7.3 HDMI V4L2 连续取帧](2026-10-19-hdmirx-v4l2.md) — kernel video board
- [7.3 HDMI 私有 DMA 环与 1080p60](2026-10-19-hdmirx-dma-ring.md) — kernel video board
- [7.3 HDMI DMA-buf 与软件 H.264](2026-10-19-hdmirx-dmabuf.md) — kernel video board
- [7.3 Wave521 硬编码与 4K60](2026-10-19-wave521-uhd.md) — kernel video board

## 2026-10-18

- [One-KVM 原生指针默认样式](2026-10-18-onekvm-native-cursor.md) — application deployment
- [One-KVM UU 远程终端与卡片重设计](2026-10-18-onekvm-uu-terminal.md) — application uu usb deployment

- [NAS 网络存储与 NAS 文件夹 U 盘](2026-10-18-nas-storage-usb-disk.md) — manager usb kernel
- [One-KVM H.264 每秒停顿](2026-10-18-onekvm-h264-periodic-stutter.md) — application video
- [One-KVM MCP Fit 截图提前“超时”](2026-10-18-onekvm-snapshot-fit.md) — application video deployment
- [管理器统一登录与 8080 KVM 网关](2026-10-18-unified-auth-gateway.md) — manager application deployment

## 2026-10-17

- [One-KVM 设备端带声音录屏](2026-10-17-onekvm-device-recording.md) — application video audio

- [One-KVM HID 队列修复部署](2026-10-17-hid-queue.md) — usb uu application deployment
- [UU 视频诊断统计部署](2026-10-17-uu-video-metrics.md) — uu video application deployment

- [供电信息只读验证](2026-10-17-power-telemetry.md) — usb manager board

- [Tailscale 管理修复部署](2026-10-17-tailscale-management-fixes.md) — manager application deployment
- [U-Boot 取消启动风扇测试](2026-10-17-uboot-quiet-fan.md) — kernel deployment
- [管理器 Wi-Fi 网络管理与热点模式](2026-10-17-wifi-client-hotspot.md) — manager deployment

## 2026-10-16

- [RTK UHD HDR 4K60 成为各应用内置 EDID](2026-10-16-rtk-uhd-hdr-builtin-edid.md) — video
- [CRG EP0 重复入队导致重启](2026-10-16-crg-ep0-double-queue-reboot.md) — kernel usb
- [共享虚拟介质状态与等待切换](2026-10-16-shared-media-state-wait-switch.md) — usb manager
- [管理器已有虚拟磁盘管理](2026-10-16-manager-virtual-disk.md) — usb manager
- [虚拟介质独立页面与跨应用介质状态](2026-10-16-virtual-media-page-cross-app.md) — usb manager
- [共享数据盘管理与四套 KVM 目录部署](2026-10-16-shared-data-disk-four-kvm.md) — usb manager
- [UU 信令与输入生命周期更新部署](2026-10-16-uu-signaling-input-lifecycle.md) — uu
- [4K60 8-bit YUV444 原始采集实测](2026-10-16-4k60-yuv444-raw-capture.md) — video
- [4:4:4 采集接口实现与生命周期修复](2026-10-16-yuv444-capture-interface-lifecycle.md) — video kernel
- [4:4:4 全帧处理优化至 4K60](2026-10-16-yuv444-full-frame-4k60.md) — video
- [4:4:4 编码能力核验与错误声明修复](2026-10-16-yuv444-encoder-capability.md) — video
- [PiKVM HDMI 音频周期性爆音](2026-10-16-pikvm-hdmi-audio-pops.md) — pikvm audio
- [数据盘交互修正与管理器动效](2026-10-16-data-disk-ui-motion.md) — manager
- [开发版本规则与管理器正式版部署](2026-10-16-development-release-versions.md) — manager deployment
- [四套 KVM 正式包部署](2026-10-16-kvm-release-deployment.md) — applications deployment

## 2026-10-15

- [PiKVM 隔夜降帧：采集线程与 CPU0 中断争用](2026-10-15-pikvm-overnight-fps-cpu0-irq.md) — pikvm video
- [部署 One-KVM UU 远程开发版本](2026-10-15-onekvm-uu-dev-deploy.md) — uu
- [UU 输出设置与缩放吞吐检查](2026-10-15-uu-output-scaling-throughput.md) — uu video
- [UU 网页输出控制、名称与系统身份](2026-10-15-uu-output-controls-identity.md) — uu
- [UU Mac 身份的键盘错码](2026-10-15-uu-mac-identity-keycodes.md) — uu usb
- [UU 滚轮方向默认值与手动覆盖](2026-10-15-uu-scroll-default-override.md) — uu usb
- [UU 连接初期体感延迟诊断](2026-10-15-uu-initial-latency.md) — uu
- [UU H.265 协商与封包修正](2026-10-15-uu-h265-negotiation-packetization.md) — uu video
- [UU H.265 出画面与周期性发送阻塞](2026-10-15-uu-h265-picture-send-stalls.md) — uu video

- [Screen Sharing 退出后物理桌面未恢复：同步取证](2026-10-15-screen-sharing-desktop-not-restored.md) — video
- [管理器 EDID 预设接口验证](2026-10-15-manager-edid-preset-api.md) — manager
- [部署 EDID 管理器，并保留 UU 虚拟屏故障现场](2026-10-15-edid-manager-deploy-uu-virtual-screen.md) — manager uu
- [UU 虚拟屏恢复故障定位](2026-10-15-uu-virtual-screen-recovery.md) — uu video
- [UU 与网页滚轮对照及采样干扰](2026-10-15-uu-web-scroll-sampling-interference.md) — uu usb
- [管理器侧边栏、风扇曲线调节与 EDID 界面](2026-10-15-manager-sidebar-fan-edid-ui.md) — manager
- [PiKVM H.265 菜单与 Direct 实板部署](2026-10-15-pikvm-h265-menu-direct.md) — pikvm
- [PiKVM Direct 周期停顿与绘制延迟](2026-10-15-pikvm-direct-stalls-paint-latency.md) — pikvm video
- [One-KVM UU 会话链路展示与鼠键反转核对](2026-10-15-onekvm-uu-session-path-input-swap.md) — uu
- [UU 会话卡片界面整理](2026-10-15-uu-session-card-ui.md) — uu
- [RTK EDID 音频与 One-KVM 运动后延迟](2026-10-15-rtk-edid-audio-onekvm-motion-latency.md) — audio application
- [跨 KVM 运动播放与积压恢复](2026-10-15-cross-kvm-motion-playout-backlog.md) — video
- [不同系统缓冲差异的原因调查](2026-10-15-buffering-difference-causes.md) — video
- [One-KVM 尽快播放策略对照](2026-10-15-onekvm-asap-playout-comparison.md) — video application
- [One-KVM 正式启用低延迟播放](2026-10-15-onekvm-low-latency-playout.md) — video application
- [PiKVM 尽快播放策略部署与对照](2026-10-15-pikvm-asap-playout.md) — pikvm video

## 2026-10-14

- [HDR 输入映射到 SDR](2026-10-14-hdr-to-sdr.md) — video
- [HDR 审查修复与部署](2026-10-14-hdr-review-fix-deploy.md) — video
- [JetKVM 默认 EDID 改为 4K60 并部署](2026-10-14-jetkvm-default-edid-4k60.md) — application video
- [One-KVM VIM4 与三套界面切换](2026-10-14-onekvm-integration-three-ui.md) — application
- [One-KVM 输入状态与流设置](2026-10-14-onekvm-input-stream-settings.md) — application
- [One-KVM 虚拟盘初始化修复](2026-10-14-onekvm-virtual-disk-init.md) — application usb
- [One-KVM 本地扩展、看门狗与包更新](2026-10-14-onekvm-extensions-watchdog-update.md) — application
- [One-KVM HID 功能配置与 USB 组合](2026-10-14-onekvm-hid-usb-profiles.md) — application usb
- [4K60 高码率编码实验](2026-10-14-4k60-high-bitrate-experiment.md) — video
- [三套 KVM 自定义 60 Mbps 部署](2026-10-14-custom-60mbps-deploy.md) — video application
- [One-KVM 高码率连接偶发退化到 10fps](2026-10-14-onekvm-high-bitrate-10fps.md) — application video
- [Wave521 时钟与编码耗时](2026-10-14-wave521-clock-encode-time.md) — video
- [4K60 编码链路抖动与丢帧检查](2026-10-14-4k60-encode-jitter-drops.md) — video
- [WebRTC 视频分段卸载发送（.23）](2026-10-14-webrtc-segmentation-offload.md) — video
- [NanoKVM Wi-Fi 扫描空列表](2026-10-14-nanokvm-wifi-empty-scan.md) — application
- [提交工作区积累改动并部署 .24](2026-10-14-workspace-commit-deploy-24.md) — deployment
- [PiKVM VIM4 构建、集成和上板验证](2026-10-14-pikvm-build-integrate.md) — pikvm
- [PiKVM 切入检查补漏](2026-10-14-pikvm-switch-check-gaps.md) — pikvm
- [PiKVM HEVC、卡顿定位与全新 Ubuntu 组装](2026-10-14-pikvm-hevc-stutter-fresh-ubuntu.md) — pikvm deployment
- [PiKVM 卡顿：ICE 选路与实际收包接口](2026-10-14-pikvm-ice-path-receive-interface.md) — pikvm video

- [MJPEG 单帧耗时与 NanoKVM 分辨率菜单](2026-10-14-mjpeg-frame-time-resolution-menu.md) — video application
- [MJPEG 硬件编码与 4K 运动画面吞吐](2026-10-14-mjpeg-hardware-4k-throughput.md) — video
- [JetKVM 码率控件部署](2026-10-14-jetkvm-bitrate-control.md) — application
- [NanoKVM 码率菜单样式修正](2026-10-14-nanokvm-bitrate-menu-style.md) — application
- [NanoKVM 码率滑块部署](2026-10-14-nanokvm-bitrate-slider.md) — application

## 2026-10-13

- [编码可靠性与关键帧实验](2026-10-13-encoder-controls.md) — video

- [组件包部署闭环验证](2026-10-13-component-deploy-loop.md) — deployment
- [无人值守部署](2026-10-13-unattended-deploy.md) — deployment
- [保持画质的低延迟验证](2026-10-13-low-latency-quality.md) — video
- [键鼠输入延迟与行为](2026-10-13-input-latency-behavior.md) — usb
- [HDMI 静音修复及重新打包验证](2026-10-13-hdmi-mute-fix-repack.md) — audio
- [补齐原 NanoKVM 功能缺项](2026-10-13-nanokvm-missing-features.md) — application
- [HID 生命周期与部署可靠性](2026-10-13-hid-lifecycle-deploy-reliability.md) — usb kernel
- [采集分辨率菜单部署](2026-10-13-capture-resolution-menu.md) — application video
- [H.265 默认开放](2026-10-13-h265-default.md) — video
- [KVM 界面管理面板](2026-10-13-kvm-manager-panel.md) — manager
- [JetKVM 完整功能接入](2026-10-13-jetkvm-full-integration.md) — application
- [NanoKVM 正式部署与 JetKVM 往返切换](2026-10-13-nanokvm-deploy-jetkvm-switch.md) — application
- [NanoKVM 终端、镜像上传与可写 U 盘](2026-10-13-nanokvm-terminal-upload-writable-disk.md) — application usb
- [虚拟显示器退出后 HDMI 桌面未恢复](2026-10-13-virtual-display-hdmi-not-restored.md) — video

## 2026-10-12

- [串口、OOWOW 与 Ubuntu 首次启动](2026-10-12-initial-serial-oowow-ubuntu.md) — board
- [自编内核与 `/lib` 事故](2026-10-12-custom-kernel-lib-symlink.md) — kernel
- [HDMI 输入采集](2026-10-12-hdmi-input-capture.md) — video
- [采集→编码链路与 USB gadget](2026-10-12-capture-encode-usb-gadget.md) — video usb
- [Mac USB HID 实测与描述符修复](2026-10-12-mac-hid-descriptor-fix.md) — usb
- [PD 开机初始化固化](2026-10-12-pd-boot-init.md) — usb
- [WebRTC 网页 KVM](2026-10-12-webrtc-web-kvm.md) — video
- [4K 视频输出](2026-10-12-4k-video-output.md) — video
- [自动风扇和 Wave521 提频](2026-10-12-auto-fan-wave521-clock.md) — kernel video
- [应用主线调整为 NanoKVM-Pro](2026-10-12-switch-to-nanokvm-pro.md) — application
- [NanoKVM-Pro 首阶段部署](2026-10-12-nanokvm-pro-first-deploy.md) — application
- [NanoKVM 原版视频控件、MJPEG 与 VDIN 缓冲区释放](2026-10-12-nanokvm-video-controls-mjpeg-vdin.md) — application video
- [NanoKVM 终端、脚本、网络唤醒与镜像管理](2026-10-12-nanokvm-terminal-scripts-wol-images.md) — application
- [NanoKVM HDMI 音频、Ubuntu 管理与应用更新](2026-10-12-nanokvm-hdmi-audio-ubuntu-update.md) — application audio
- [4K60 编码预算与局域网 RTP 分包](2026-10-12-4k60-encoder-budget-rtp.md) — video
