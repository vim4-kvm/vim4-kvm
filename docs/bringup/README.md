# 上板记录索引

每条记录一个文件，位于 `bringup/日期-主题.md`，均为历史证据；当前架构和约束先读对应子系统入口。
用 `grep` 按关键词或标签查本页，只打开命中的文件，不通读本页或整个目录。
标签：board、kernel、video、audio、usb、application、pikvm、uu、manager、deployment。

新记录：新建 `bringup/YYYY-MM-DD-英文短名.md`，首行 `# YYYY-MM-DD：标题`，并在本页对应日期下追加一行：标题链接到文件，后接“ — 标签”，不写摘要。
本目录只保留现行文档、代码或发布元数据引用的记录及最近记录；未被引用的旧记录与 `docs/archive/` 快照已于 2026-11-08 删除，
需要时用 `git show ba9972e:docs/bringup/<文件>` 或 `git show ba9972e:docs/archive/<文件>` 查。

## 按任务查找

- 内核：[启动](2026-10-19-edge-firstboot.md) → [合入](2026-10-23-mainline-integration.md) → [差距](2026-10-28-kernel73-parity-audit.md)。
- 音视频：[双路径](2026-10-25-native-hdr-dual-path.md)、[HDR](2026-10-26-all-kvm-hdr.md)、[延迟](2026-10-27-current-video-latency.md)。
- USB：[PD](2026-10-12-pd-boot-init.md)、[组合](2026-10-21-edge-usb-functions.md)、[介质](2026-10-18-nas-storage-usb-disk.md)。
- 应用：[切换](2026-10-13-nanokvm-deploy-jetkvm-switch.md)、[登录](2026-10-18-unified-auth-gateway.md)、[UU](2026-10-25-uu-protocol-audit.md)。
- 部署：[组件](2026-10-13-component-deploy-loop.md)、[双内核](2026-10-21-dual-kernel-integration.md)、[回退](2026-10-22-edge-7-3-final-deploy.md)。

以下保留完整日期索引。

## 2026-11-08

- [DOS regmap debugfs修复设为默认](2026-11-08-vdec-dos-regmap-deploy.md) — kernel video deployment
- [fusb302屏蔽时显示固件PD](2026-11-08-manager-pd-firmware-display.md) — manager usb

## 2026-11-07

- [.42 正式默认部署](2026-11-07-deploy42-default.md) — kernel deployment
- [复用.42正式部署准备](2026-11-07-deploy42-preparation.md) — kernel deployment
- [integration42 固件PD续验](2026-11-07-vdec-integration42-pd-results.md) — kernel video
- [固件PD正式默认](2026-11-07-pd-firmware-default.md) — kernel usb deployment
- [PD接管A/B](2026-11-07-pd-takeover-ab.md) — kernel usb

## 2026-11-06

- [MR3 存储归属修复实板计划](2026-11-06-vdec-mr3-storage-plan.md) — kernel video
- [r66 同包续跑计划](2026-11-06-vdec-r66-plan.md) — kernel video
- [integration42 K10共存与采证停止](2026-11-06-vdec-integration42-results.md) — kernel video
- [integration41 K9自然共存门禁](2026-11-06-vdec-integration41-results.md) — kernel video
- [.40解码修复板验](2026-11-06-vdec-integration40-results.md) — kernel video
- [HEVC 输出过程与单 AU 隔离](2026-11-06-vdec-fixes-b.md) — kernel video
- [DOS 运行期租约](2026-11-06-vdec-dos-runtime-lease.md) — kernel video
- [T7 DOS 窗口与 probe 资源审计](2026-11-06-vdec-dos-window.md) — kernel video
- [解码功能修复批 A](2026-11-06-vdec-fixes-a.md) — kernel video
- [.39解码分层重构验收](2026-11-06-vdec-integration39-results.md) — kernel video
- [r98/r100合法drain尾部裁决](2026-11-06-vdec-integration39-r98-drain.md) — kernel video
- [.39 重构行为对照计划](2026-11-06-vdec-integration39-plan.md) — kernel video
- [.39 对照的 .38 同包补基准](2026-11-06-vdec-integration39-baseline.md) — kernel video
- [解码分层重构系列](2026-11-06-vdec-refactor-series.md) — kernel video
- [HEVC正式部署准备与入场停止](2026-11-06-hevc-formal-deploy.md) — kernel deployment
- [.38 HEVC第二轮修复复测](2026-11-06-hevc-integration38-results.md) — kernel video
- [HEVC 一致性第三轮](2026-11-06-hevc-conformance-round3.md) — kernel video
- [.38 HEVC第二轮验收计划](2026-11-06-vdec-integration38-plan.md) — kernel video
- [HEVC 一致性第二轮](2026-11-06-hevc-conformance-round2.md) — kernel video
- [.37 HEVC一致性修复复测](2026-11-06-hevc-integration37-results.md) — kernel video
- [.37 HEVC一致性修复验收计划](2026-11-06-vdec-integration37-plan.md) — kernel video
- [HEVC 全集失败首轮修复](2026-11-06-hevc-conformance-fixes.md) — kernel video
- [HEVC 8bit全集结果](2026-11-06-hevc-full-results.md) — kernel video
- [r79b无线屏蔽与插件门禁](2026-11-06-vdec-r79b-no-radio.md) — kernel video
- [r79入场旧串口缓存停止](2026-11-06-vdec-r79-entry-stop.md) — kernel video
- [.36无线初始化屏蔽计划](2026-11-06-vdec-integration36-no-radio-plan.md) — kernel video
- [r78两次冷复位停止全集](2026-11-06-vdec-r78-full-stop.md) — kernel video
- [.36 HEVC 8bit全集计划](2026-11-06-vdec-integration36-full-plan.md) — kernel video
- [HEVC全集参考核验](2026-11-06-hevc-full-reference.md) — kernel video
- [r77 HEVC P/B短流通过](2026-11-06-vdec-r77-hevc-inter.md) — kernel video
- [r76候选及正式恢复冷复位](2026-11-06-vdec-r76-coldboot.md) — kernel video
- [r75全I回归与采证误停](2026-11-06-vdec-r75-ioctl-trace.md) — kernel video
- [r74候选冷复位与自然恢复](2026-11-06-vdec-r74-coldboot.md) — kernel video
- [.36 HEVC inter短流计划](2026-11-06-vdec-integration36-plan.md) — kernel video
- [HEVC P/B路径审查](2026-11-06-hevc-inter.md) — kernel video
- [HEVC 主线整理系列](2026-11-06-hevc-mainline-series.md) — kernel video
- [r73 HEVC EOS与整理版回归](2026-11-06-vdec-r73-eos.md) — kernel video
- [.35整理系列与EOS验收计划](2026-11-06-vdec-integration35-plan.md) — kernel video
- [r72 HEVC EOS定位](2026-11-06-hevc-r72-eos.md) — kernel video
- [r72 HEVC首帧与起始B验证](2026-11-06-vdec-r72-swap-first-frame.md) — kernel video
- [.34厂商HEVC序列与诊断计划](2026-11-06-vdec-integration34-plan.md) — kernel video
- [HEVC secure swap缺口](2026-11-06-hevc-firmware-swap.md) — kernel video
- [r71 MPEG-2 单向 B 候选](2026-11-06-mpeg2-r71-leading-b.md) — kernel video
- [r71 HEVC 08前定位](2026-11-06-hevc-pre08-analysis.md) — kernel video
- [r71 .33 手动头IRQ与请求拒绝](2026-11-06-vdec-r71-handshake.md) — kernel video
- [.33集成与诊断计划](2026-11-06-vdec-integration33-plan.md) — kernel video
- [HEVC厂商序列移植](2026-11-06-hevc-vendor-port.md) — kernel video
- [r70 MPEG-2 请求追踪](2026-11-06-mpeg2-r70-rejections.md) — kernel video
- [r70 .32短回归](2026-11-06-vdec-r70-integration32.md) — kernel video
- [MPEG-2 P 链算术定位](2026-11-06-mpeg2-rounding.md) — kernel video
- [.32集成与板窗计划](2026-11-06-vdec-integration32-plan.md) — kernel video
- [r69 MPEG-2 像素与单向 B 参考](2026-11-06-mpeg2-r69-analysis.md) — kernel video
- [r69联合验证与AVC收口](2026-11-06-vdec-r69-joint.md) — kernel video
- [r68候选冷复位与被动恢复](2026-11-06-vdec-r68-coldboot.md) — kernel video
- [r67启动识别修复](2026-11-06-vdec-r67-startup.md) — kernel video
- [r66插件身份拦截与恢复](2026-11-06-vdec-r66-identity.md) — kernel video
- [r65集成部分全集](2026-11-06-vdec-r65-joint.md) — kernel video
- [AVC评审版与三格式集成计划](2026-11-06-vdec-integration31-plan.md) — kernel video
- [MPEG-2 visl 矩阵根因](2026-11-06-mpeg2-visl.md) — kernel video
- [r64 MR3存储归属验证](2026-11-06-vdec-r64-storage.md) — kernel video
- [MR3 旧timestamp与存储归属](2026-11-06-vdec-mr3-storage.md) — kernel video
- [r63 缺口修复实板验证](2026-11-06-vdec-r63-gap.md) — kernel video
- [r62 入场依赖失败](2026-11-06-vdec-r62-entry.md) — kernel video

## 2026-11-05

- [HEVC 金标准轨迹离线方案](2026-11-05-hevc-golden-plan.md) — kernel video

- [MR3/4/5 缺口参考定位](2026-11-05-vdec-gap-references.md) — kernel video
- [r61 parser A/B 像素采证](2026-11-05-vdec-r61-parser-ab.md) — kernel video
- [冷复位 A/B r60](2026-11-05-vdec-coldboot-ab-r60.md) — kernel
- [RESET/VBUS/PD 闭环方案](2026-11-05-vdec-reset-measurement-plan.md) — kernel usb
- [冷复位同 RAM 封装 A/B 计划](2026-11-05-vdec-coldboot-ab-plan.md) — kernel
- [解码 v2 内部评审系列](2026-11-05-vdec-review-v2.md) — kernel video
- [H.264 全集最终汇总与评审边界](2026-11-05-vdec-avc-final.md) — kernel video

- [r56 FMO 停止与 Khadas parser 来源](2026-11-05-vdec-r56-fmo-parser.md) — kernel video

- [r54 Sharp 尾帧与队列跟踪](2026-11-05-vdec-r54-sharp-trace.md) — kernel video

- [7.3 集成内核与新 manager 正式部署](2026-11-05-integration-formal-deploy.md) — kernel deployment manager

- [完整 AVC/MPEG-2 一致性与 bit21 实验](2026-11-05-vdec-full-conformance.md) — kernel video
- [标准码流失败特性聚类](2026-11-05-vdec-failure-groups.md) — kernel video
- [H.264 场缓冲生命周期](2026-11-05-vdec-field-lifetime.md) — kernel video
- [独立格式 Fluster 与 HEVC 启动顺序](2026-11-05-vdec-independent-fluster.md) — kernel video
- [集成候选构建与 KUnit 复验](2026-11-05-integration-build-results.md) — kernel
- [T7 HDMI RX KUnit 迁移结果](2026-11-05-hdmirx-kunit-results.md) — kernel video audio
- [内核树测试迁移清单](2026-11-05-kernel-test-migration.md) — kernel
- [集成生产与正式基线同窗Wi-Fi对照](2026-11-05-integration-wifi-control.md) — kernel network
- [TCPM冷复位专项与正式启动统计](2026-11-05-tcpm-coldboot-audit.md) — kernel usb
- [启动修复重放到 KUnit 迁移基线](2026-11-05-debug-splat-integration.md) — kernel
- [ADLA 锁类修复与 PD 启动时序比较](2026-11-05-adla-mutex-pd-timing.md) — kernel network usb
- [启动修复实板复验与生产吞吐准备](2026-11-05-debug-splat-board-validation.md) — kernel network usb
- [风扇自适应温度对照](2026-11-05-fan-thermal-adaptive.md) — kernel manager
- [风扇标准 thermal 迁移](2026-11-05-fan-thermal.md) — kernel manager
- [调试启动 splat 离线修复与 PWM 锁拓扑](2026-11-05-debug-splat-fixes.md) — kernel
- [解码调试候选启动与门禁](2026-11-05-vdec-debug-boot.md) — kernel deployment
- [解码 KUnit 迁移结果](2026-11-05-vdec-kunit-results.md) — kernel video
- [解码测试迁移清单](2026-11-05-vdec-test-migration.md) — kernel video
- [HEVC 接口与固件模式](2026-11-05-hevc-interface-review.md) — kernel video

## 2026-11-04

- [开机 PD 接入 Linux TCPM](2026-11-04-boot-pd-tcpm.md) — kernel usb
- [USB 总线挂起修复部署](2026-11-04-pm-typec-parity.md) — kernel usb

- [UU 自动码率与 Wave5 在线更新](2026-11-04-uu-adaptive-bitrate.md) — uu video application
- [UU TWCC 发送端带宽估算](2026-11-04-uu-twcc.md) — uu video application

- [安全媒体移植首段与运行时清点](2026-11-04-security-media-port.md) — kernel board

- [日期内核构建、清理与最终验收](2026-11-04-kernel-731-vim4-20261104.md) — kernel deployment

## 2026-11-03

- [内核命名统一、旧产物清理与管理面板](2026-11-03-kernel-naming-cleanup.md) — kernel deployment manager

- [7.3.1整包部署与boot清理](2026-11-03-kernel-731-deploy.md) — kernel deployment video usb

- [uhd7 三模块安装与四应用会话验收](2026-11-03-mainline-modules.md) — kernel video application deployment

- [5.15 amlvenc 按需 IDR 离线调研](2026-11-03-amlvenc-on-demand-research.md) — video

- [Wave5 AVC 默认按需 IDR](2026-11-03-wave5-avc-default.md) — video board application deployment

- [Wave5 AVC 恢复帧 QP 与编码选择持久化](2026-11-03-wave5-avc-recovery-qp.md) — video board application deployment

## 2026-11-02

- [uhd7 固定高刷与原生 YUV444 窗口](2026-11-02-hfr-yuv-window.md) — kernel video board

- [uhd7 正式构建与 BCM43752 SDIO 部署](2026-11-02-wifi-sdio-formal.md) — kernel network board deployment

- [BCM43752 SDIO 主机路径优化与 5.15 同窗对照](2026-11-02-wifi-sdio-host-path.md) — kernel network board

- [BCM43752 下载吞吐与接收处理 CPU](2026-11-02-wifi-rx-cpu.md) — kernel network board

- [BCM43752 固件版本与 5.15 驱动协议对照](2026-11-02-wifi-fw217.md) — kernel network board

- [P0-2 性能与常开功耗合并窗口](2026-11-02-p0-2-pm-window.md) — video kernel board

## 2026-11-01

- [HDMI-RX EDID 撤回 SError 审计与 COR 复位竞争修复](2026-11-01-hdmirx-edid-serror-audit.md) — kernel video offline
- [HDR/r14e、MAC 与音频最终合入](2026-11-01-p0-hdr-final-merge.md) — application audio deployment
- [r14e持久安装与用户手测](2026-11-01-hdr10-r14e-installed.md) — deployment kernel application hdr10 kbase
- [HDR 第二阶段 uhd6 短窗](2026-11-01-hdr10-phase2-uhd6.md) — board video application uu

## 2026-10-31

- [原生HDR第二阶段离线接入候选](2026-10-31-hdr10-phase2-offline.md) — video application uu gpu offline
- [uhd6正式完整构建与验收](2026-10-31-uhd6-formal.md) — kernel video gpu deployment
- [uhd6 EDID恢复取证与修复门禁](2026-10-31-uhd6-edid-review.md) — kernel video deployment
- [P0-2分窗性能准备与接收预检](2026-10-31-p0-2-performance.md) — board video performance offline
- [P0-3真实挂死注入安全审查](2026-10-31-wave5-real-hang-safety.md) — kernel video offline safety
- [原生HDR最小主路径验收与合入](2026-10-31-hdr10-native-final.md) — kernel board video application hdr
- [uhd5 GPU正式来源锁与最小烟测合入](2026-10-31-uhd5-main-integration.md) — kernel gpu deployment
- [kbase r11厂商live DVFS策略与配对复测](2026-10-31-kbase-r11-policy.md) — kernel gpu board video
- [kbase r6 DMA追平、平台二分与thermal绑定](2026-10-31-kbase-r6-window.md) — kernel gpu board video
- [uhd4正式完整构建、短烟测与队列工具修正](2026-10-31-uhd4-formal-smoke.md) — kernel board video hdr npu gpu deployment
- [HDR2双向恢复分解、uhd4r3细采样与长尾门禁](2026-10-31-hdr2-recovery.md) — kernel board video hdr application npu gpu
- [MCP与ICE定位、uhd4 PQ门禁及恢复速度余项](2026-10-31-hdr2-mcp-ice-pq.md) — kernel board video hdr application
- [uhd4主题整理与SDR回归，MCP/接收端门禁阻断](2026-10-31-hdr2-uhd4-gate.md) — kernel board video hdr npu gpu

## 2026-10-30

- [7.3 kbase外部模块离线候选与ABI检查](2026-10-30-kbase-offline.md) — kernel gpu audit packaging
- [HDR2a5产品DMA恢复、逐代退休与4K60门禁](2026-10-30-hdr2a5-window.md) — kernel board video hdr application
- [HDR2a3的VUI、色差、4K60与退休/产品恢复余项](2026-10-30-hdr2a3-window.md) — kernel board video hdr
- [NPU与nodebug正式uhd3合入、回归及manager EDID部署](2026-10-30-uhd3-formal-regression.md) — kernel board video manager deployment
- [nodebug两启动对门禁与绑核尺寸曲线](2026-10-30-nodebug-paired-gate.md) — kernel board benchmark video
- [nodebug消除tmpfs写入差距与60fps回归](2026-10-30-nodebug-memory-window.md) — kernel board benchmark video
- [YOLO端到端差距定位到文件写入](2026-10-30-npu-e2e-window.md) — kernel board benchmark
- [GPU同块回跳修复与快轮询窗口](2026-10-30-gpu-repair-window.md) — kernel board video benchmark
- [uhd2四启动对性能门禁仍不确定](2026-10-30-npu-boot-pairs.md) — kernel board benchmark
- [npu4三模型、取消与视频并行门禁通过](2026-10-30-npu4-acceptance.md) — kernel board benchmark video
- [第三轮尺寸与原生 GPU 定向复验](2026-10-30-kernel73-gap-r3.md) — kernel video manager deployment
- [7.3 差距补齐批量验证](2026-10-30-kernel73-gap-validation.md) — kernel video usb manager deployment

## 2026-10-29

- [管理面板中英文界面](2026-10-29-manager-i18n.md) — manager application deployment

## 2026-10-28

- [7.3 对当前 5.15 功能的差距复核](2026-10-28-kernel73-parity-audit.md) — kernel video audio usb application audit
- [UDP 同帧批量发送候选与延迟对照](2026-10-28-udp-batch-latency.md) — video application board benchmark

## 2026-10-27

- [当前 One-KVM 延迟与 SDR 缩放瓶颈](2026-10-27-current-video-latency.md) — video application board benchmark
- [UU HDR 降分辨率的 GPU 缩放](2026-10-27-uu-hdr-scale.md) — video uu application deployment board benchmark

## 2026-10-26

- [四套 KVM 的远程 HDR 接入](2026-10-26-all-kvm-hdr.md) — video application manager deployment board
- [Chrome 与 Safari 的远程 HDR 兼容性复核](2026-10-26-hdr-browser-compatibility.md) — video application board
- [远程 HDR 全局默认与源端切换](2026-10-26-hdr-global.md) — video manager uu application deployment board
- [远程 Main10 HDR 与高刷超宽屏](2026-10-26-remote-hdr-modes.md) — video kernel uu application deployment board
- [统一 RTK UHD HDR 入口](2026-10-26-rtk-unified.md) — video application manager board deployment
- [VRR 范围声明纠正与 4K 输入验证](2026-10-26-vrr-range-4k.md) — video kernel application board
- [真实 VRR 输入与 One-KVM 连续画面](2026-10-26-vrr-live.md) — video kernel application board
- [5.15 1080p120 候选部署](2026-10-26-1080p120.md) — video kernel application board deployment
- [厂商编码器码率峰值与 VBV 对照](2026-10-26-encoder-vbv.md) — video board benchmark

## 2026-10-25

- [VIM4 SRTP HMAC 后端正式接入](2026-10-25-srtp-openssl-hmac.md) — video application board benchmark
- [RTP 发送离线基准与板端 CPU 回放](2026-10-25-rtp-send-benchmark.md) — video application board benchmark
- [交帧之后的编码、发送与浏览器分段](2026-10-25-video-downstream-latency.md) — video application board
- [VDIN1 逐缓冲交付与 RDMA 时序核实](2026-10-25-vdin1-frame-handoff.md) — video kernel board
- [管理面板前端重构验收与部署](2026-10-25-manager-ui.md) — manager application deployment
- [UU 协议审查与 P1 修复验收](2026-10-25-uu-protocol-audit.md) — uu application video audio usb audit
- [厂商原生 HDR 与 SDR KVM 双路径交付](2026-10-25-native-hdr-dual-path.md) — kernel video audio onekvm board
- [音频寄存器只读诊断触发重启](2026-10-25-audiobus-read-abort.md) — audio kernel deployment board uu

## 2026-10-24

- [UU 缩小输出的 GE2D 时钟与流水线修复](2026-10-24-uu-scaled-60fps.md) — video application uu deployment board
- [HDMI 透传第二阶段暂停与恢复入口](2026-10-24-hdmi-passthrough.md) — kernel video deployment board

## 2026-10-23

- [统一合入主线，保留稳定 KVM 部署](2026-10-23-mainline-integration.md) — kernel application deployment board
- [Wave5 E01 动态控制、分层 GOP 与 LTR 上板窗口](2026-10-23-wave5-e01-window.md) — kernel video usb deployment board
- [Wave5 编码器批量窗口与 T7 硬件看门狗](2026-10-23-wave5-parity-window.md) — kernel video deployment board
- [HDMI RX 同链路 7.3 / 厂商 5.15 十分钟对照](2026-10-23-hdmirx-vendor-comparison.md) — kernel video audio deployment board
- [厂商5.15一次性启动往返与GPU用户态识别](2026-10-23-vendor-boot-gpu.md) — kernel deployment board
- [Wave5 运行时恢复：五轮注入、失败隔离与一次性启动窗口](2026-10-23-wave5-runtime-window.md) — kernel video deployment board
- [HDMI 音频 PCM 生命周期修复与 SARADC 正式部署：九类通过](2026-10-23-kvm-audio-capture-stability-deploy.md) — kernel audio video application deployment board
- [M1 一次性启动与恢复安全网](2026-10-23-display-m1-safety.md) — kernel deployment
- [Wave5 隔离正式窗口复验](2026-10-23-wave5-isolation-final.md) — kernel video audio usb manager deployment board
- [M0 第四轮音频归因与发布](2026-10-23-display-m0-r4.md) — kernel video audio usb manager deployment board
- [HDMI RX 音频 ENOLINK 基线对照](2026-10-23-hdmirx-audio-enolink.md) — kernel audio application board
- [7.3 T7 HDMI 显示输出可行性调查](2026-10-23-display-feasibility.md) — kernel video audio board

## 2026-10-22

- [手动 PD 协商合同持久化并保留](2026-10-22-pd-manual-contract.md) — usb deployment board
- [SARADC channel 2 超时取证与离线候选](2026-10-22-saradc-timeout-audit.md) — kernel board
- [Wave5 首轮部署采集停止复核](2026-10-22-wave5-first-failure-audit.md) — kernel video board
- [U-Boot 现场复位分析与 microSD 安全验证](2026-10-22-uboot-sd-recovery.md) — usb kernel deployment
- [7.3 ramoops/pstore 正式部署并保留](2026-10-22-edge-pstore-deploy.md) — kernel deployment board
- [PD 热重启历史合同卡片](2026-10-22-pd-warm-carryover.md) — usb manager deployment board
- [T7 解码硬件、固件与主线差异明细](2026-10-22-vdec-hardware-audit.md) — kernel video
- [T7 MDEC SError 离线排查与安全策略、单读门禁](2026-10-22-vdec-mdec-offline.md) — kernel video deployment
- [P2 PD Request＋KASLR 合并固件候选](2026-10-22-p2-uboot-combined.md) — usb kernel deployment
- [P2 有界持久 journal 部署并保留](2026-10-22-p2-journal-deploy.md) — deployment board
- [P2 USB 音频、组合与 RNDIS 核对](2026-10-22-p2-usb-audio.md) — usb audio application board
- [P2 KASLR、随机数与 U-Boot 离线候选](2026-10-22-p2-kaslr.md) — kernel deployment board
- [P2 挂起与唤醒离线审查](2026-10-22-p2-suspend-audit.md) — kernel usb
- [v7.3 正式版第三轮部署并保留](2026-10-22-edge-7-3-final-retained.md) — kernel video audio usb manager deployment board
- [U-Boot 固定 5V USB PD Request（离线候选）](2026-10-22-uboot-pd-request.md) — usb deployment

- [v7.3 正式部署尝试与自动回退](2026-10-22-edge-7-3-final-deploy.md) — kernel video audio usb manager deployment board
- [HDMI 动态 LPCM 与无链路恢复](2026-10-22-edge-hdmi-audio.md) — kernel audio application deployment board
- [7.3 日志分级与 T7 硬件随机数](2026-10-22-edge-diag.md) — kernel usb deployment board
- [PD 热重启原因与主动查询风险审查（未刷写）](2026-10-22-pd-warmboot-audit.md) — usb manager deployment board
- [U-Boot PD 交接刷写与双内核验证](2026-10-22-pd-firmware-deploy.md) — usb manager deployment board
- [7.3 HDMI RX 输入模式泛化](2026-10-22-edge-hdmi-modes.md) — kernel video application deployment board
- [HDMI 模式最终产物复核](2026-10-22-edge-hdmi-modes-final.md) — kernel video application deployment board

## 2026-10-21

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
- [本地基准与 VDIN 直接 DMA](2026-10-20-direct-dma-benchmark.md) — application kernel video board
- [7.x 输入状态等待与端到端延迟](2026-10-20-edge-status-latency.md) — kernel video application board
- [7.x 安静风扇曲线](2026-10-20-edge-quiet-fan.md) — kernel video deployment board
- [7.x 启动风扇与 HDMI 恢复](2026-10-20-edge-recovery.md) — kernel video audio application deployment board
- [7.x 1080p60/4K60 自动切换与缓冲回收](2026-10-20-edge-dynamic-modes.md) — kernel video audio application deployment board

## 2026-10-19

- [7.3 edge 首次启动](2026-10-19-edge-firstboot.md) — kernel deployment board
- [7.3 HDMI RX EDID 与源端 DDC 读回](2026-10-19-hdmirx-ddc.md) — kernel video usb board
- [7.3 HDMI 私有 DMA 环与 1080p60](2026-10-19-hdmirx-dma-ring.md) — kernel video board
- [7.3 Wave521 硬编码与 4K60](2026-10-19-wave521-uhd.md) — kernel video board

## 2026-10-18

- [NAS 网络存储与 NAS 文件夹 U 盘](2026-10-18-nas-storage-usb-disk.md) — manager usb kernel
- [管理器统一登录与 8080 KVM 网关](2026-10-18-unified-auth-gateway.md) — manager application deployment

## 2026-10-17

- [U-Boot 取消启动风扇测试](2026-10-17-uboot-quiet-fan.md) — kernel deployment

## 2026-10-16

- [4K60 8-bit YUV444 原始采集实测](2026-10-16-4k60-yuv444-raw-capture.md) — video
- [PiKVM HDMI 音频周期性爆音](2026-10-16-pikvm-hdmi-audio-pops.md) — pikvm audio

## 2026-10-15

- [Screen Sharing 退出后物理桌面未恢复：同步取证](2026-10-15-screen-sharing-desktop-not-restored.md) — video
- [跨 KVM 运动播放与积压恢复](2026-10-15-cross-kvm-motion-playout-backlog.md) — video
- [One-KVM 正式启用低延迟播放](2026-10-15-onekvm-low-latency-playout.md) — video application

## 2026-10-14

- [Wave521 时钟与编码耗时](2026-10-14-wave521-clock-encode-time.md) — video

## 2026-10-13

- [组件包部署闭环验证](2026-10-13-component-deploy-loop.md) — deployment
- [HID 生命周期与部署可靠性](2026-10-13-hid-lifecycle-deploy-reliability.md) — usb kernel
- [JetKVM 完整功能接入](2026-10-13-jetkvm-full-integration.md) — application
- [NanoKVM 正式部署与 JetKVM 往返切换](2026-10-13-nanokvm-deploy-jetkvm-switch.md) — application

## 2026-10-12

- [串口、OOWOW 与 Ubuntu 首次启动](2026-10-12-initial-serial-oowow-ubuntu.md) — board
- [自编内核与 `/lib` 事故](2026-10-12-custom-kernel-lib-symlink.md) — kernel
- [HDMI 输入采集](2026-10-12-hdmi-input-capture.md) — video
- [PD 开机初始化固化](2026-10-12-pd-boot-init.md) — usb
