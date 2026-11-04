# VIM4 新内核基线

本页管主线源码、整包升级与维护；安装只读[身份](#源码与配置)、[升级合同](#正式构建与整包升级)，占板另读[短窗口](board-window.md#占板时间最短化)。
当前身份唯一来源：[sources.toml](../packaging/kernel/sources.toml)；tested_build/retained_runtime是验收与保留状态，package是下一包，不能混用。
[最新日期构建与清理验收](bringup/2026-11-04-kernel-731-vim4-20261104.md)：20261104 build 1 已通过用户指定的最小冒烟并保留为 Mainline，旧 uhd7 已退役；首次工具中止与恢复过程保留在同一记录。已验源码的[正式部署](bringup/2026-11-03-kernel-731-deploy.md)限定更广范围证据；本次不重做完整回归；已发布[Release](https://github.com/vim4-kvm/linux/releases/tag/v7.3.1-vim4-20261104)。
导航：[路线图](#通用内核路线图) · [审查](#审查边界与后续验证) · [补丁维护](#补丁维护方法) · [隔离](#wave5-隔离告警) · [历史](#相关记录)。

## 源码与配置

- 身份、上游/Armbian版本、补丁与验收产物：见[来源锁](../packaging/kernel/sources.toml)、[配置](../packaging/kernel/kernel.config)及[发行收据](../packaging/kernel/releases)；不要复制历史SHA作为当前版本。
- VM工作树与worker操作见[工作区](workspace.md#构建)。检出锁定revision，必须用独立Linux大小写敏感文件系统；不重做rc7导入、不覆盖已有工作树。
- 主线与厂商构建入口见[packaging/kernel](../packaging/kernel)；已验旧release/配置不追改，同次完整模块与用户态不能混装。编译成功不表示补丁已硬件审查。

## 构建

### 正式构建与整包升级

命令/参数、命名与文件清单分别以[build.sh](../packaging/kernel/build.sh)、[package-unified.py](../packaging/kernel/package-unified.py)、[register-runtime.py](../packaging/kernel/register-runtime.py)为准；构建环境见[工作区](workspace.md#构建)，release/tag规则见[代码规范](code-standards.md)。

1. 先核锁定源码干净、输出为空且在源码外；使用打包日对应的来源锁，候选用独立锁，不提前改正式来源。validate-only通过不等于编译或部署。
2. 构建同次Image、DT与完整模块，保留最终配置、来源、编译器和产物哈希；失败保留日志/现场，手工续建或换新空目录，不自动清理。构建不连接板子或修改启动项。
3. 封包核同次完整基础/外部模块、vermagic、BTF和build ID。任务私有暂存只移除modules_install的build/source链接，不改原始构建；启动器须包含精确新release和受控平台/HDMI/gadget入口。已有同release包拒绝覆盖，应递增构建序号。
4. 独占板窗取得当前基线proof后安装；已有Mainline精确登记是前提，不能只看uname。先核外层/包内完整文件集合与模块，再预检启动和根分区空间：按完整候选启动文件及新模块/运行时/固件预算，同设备合并，不能只算Image大小差额。
   跨重启的验收与恢复脚本留在控制主机，经 SSH stdin 执行或在每次启动后重传；板上 /tmp 会在重启时清空，不能作为跨重启工具存储。
5. 保留默认标签、其他启动入口与原release目录，不创建额外备份。固件核来源后复制；新启动文件写独立目录逐项核验，双内核用户态入口临时写入、fsync再原子替换。
6. 模块、固件、启动文件和入口核验并sync后，先原子写运行时登记，最后单次替换Mainline启动指针，默认标签不变。启动提交前进程即使死亡也应正常启动原Image/DT/模块；遗留候选目录不自动删，非空模块目录复用须完整清单一致。
7. 按[部署门禁](subsystems/deployment.md#内核开发流程与部署门禁)验收后保留候选，并在对应源码SHA建release tag；本地tag不授权push。失败才指回仍保留的整包并重新登记，清理旧内核另核引用及授权。

RAM候选的基线准入与恢复证明只在[短窗口](board-window.md#当前正式基线)维护，不沿用正式安装步骤。

## 通用内核路线图

目标是追平厂商5.15全部适用能力，核心进入DRM/KMS、V4L2、ASoC、genpd等主线框架，
外围可先移植后整理；绕过和保护不能作为终态。完整范围、固定源码/DT行号、缺口依赖、
工作量与硬件见 [厂商能力对照与总体规划](parity/README.md)，其固定版本对照不能当最新验收。
以下顺序与F0–F5一致，不代表硬件验收通过。

| 优先级 | 方向 | 当前边界与下一步 |
|---|---|---|
| F0，最高 | KVM采集与音频稳定性 | FDET分类、PCM XRUN与资格重开已正式保留；TOP测量空窗误判已有同链路定位并正式修复，更多源及长期连续性待覆盖 |
| F1，最高 | Wave5恢复与HEVC尺寸正式实现 | 正式分支已含[genpd循环与固件冷加载](bringup/2026-10-23-wave5-runtime-window.md)，失败保留DMA；[P0-3审查](bringup/2026-10-31-wave5-real-hang-safety.md)确认真实挂死注入尚无安全证据。保持尺寸保护/AVC回退，先补安全注入再验恢复 |
| F1→F2 | 本地显示M1+与采集共存 | M0 simpledrm已过，M1由现有任务承接；统一共享VCBUS/MMIO/时钟归属，后续原生DRM modeset/EDID/HPD、多平面及HDMI声音，不以固定handoff当终态 |
| F2 | 输入格式完整化与硬件解码 | HLG与12bit动态路径已实现但真源未验；隔行仍需去隔行实现。解码沿[既有VDEC门禁](bringup/2026-10-22-vdec-mdec-offline.md)，先安全平台层和H.264正确帧，再扩codec/位深/多实例 |
| F2→F5 | 全部音频路由 | HDMI-TX播放先行，再I²S/PCM/SPDIF/PDM/EXTN/loopback/ASRC/effect/VAD/DSP；当前RX采集不代表输出、eARC或全部厂商路由可用 |
| F3 | 电源、调压、挂起与唤醒 | 按[PM审查](bringup/2026-10-22-p2-suspend-audit.md)先设备quiesce/恢复，再解除临时常开/CRG EBUSY；GPU逐频电压表不足，禁止猜值；本轮不做整机挂起 |
| F3 | KASLR/启动随机种子 | 晚期hwrng不能补早期KASLR；按[SD安全方案](bringup/2026-10-22-uboot-sd-recovery.md)先可恢复启动验证，不刷共享板引导区 |
| F4 | NPU与通用外围 | 先确认新板ADLA/旧板NNA及匹配SDK，再驱动/标准接口；补PCIe、BT、USB真实声音/Windows网卡、存储与MCU/IR/ADC等；Wi-Fi/P2P另行验收 |
| F5 | MIPI与图像处理 | DRM DSI/面板/背光，V4L2 CSI/ISP/sensor、GE2D/GDC/DI/writeback及高阶色彩；需准确扩展硬件，不能套用C3支持当T7完成 |
| 条件受限 | Dolby Vision、HDCP/安全媒体、密钥/TA与闭源SDK | 缺授权/固件合同的功能明确受限，不以普通文件、软件回退或伪造能力替代；具备条件后仍接标准框架 |
| 不做接口兼容 | 旧厂商私有ABI | 功能仍在追平范围；以DRM/V4L2/ASoC/dma-buf等标准接口交付，闭源旧消费者另列兼容条件 |

## 2026-10-19 首轮构建结果

[rc7 导入与首轮构建快照](archive/kernel-rc7-import.md)保留导入命令、bundle、产物哈希与未验范围。

## 启动固件预检与模块准备

[首次启动记录](bringup/2026-10-19-edge-firstboot.md)；U-Boot shared clone 依赖原对象库，不可单独删除其 `~/src/u-boot`。

## 审查边界与后续验证

原始 164 个 Armbian 补丁涉及 108 个文件，未修改 HDMI RX、VDIN、Wave5 或 USB gadget 路径。
后续本地 CRG 实验驱动及验证范围见 [适配记录](archive/kernel-edge-porting.md#crg-实验驱动2026-10-19)。
GPU 纯调频已完成[专项验证](bringup/2026-10-21-edge-gpu-devfreq.md)及上述合并部署；
音频输出和显示输出仍需上板验证，不能用编译成功替代。

- `0097`：GPU 800 MHz、IO coherent；需验证 Panfrost、内存压力和持续负载。
- `0100/0101/0111`：音频控制器与 HDMI 输出声卡，不代表 HDMI 输入音频采集。
- `0106`：HDMI TX 驱动声明 TMDS ≤600 MHz、RGB 8-bit、双声道 I²S、无 HDCP；不是完整 HDMI 2.1 能力。
- `0088`：PCIe DMA 依赖固件 SMC 保护窗口；需验证板上固件兼容性。
- `0103/0146`：保持显示及 USB/SDIO/eMMC 电源域，涉及功耗与恢复行为，需测试挂起恢复。
- `0073–0080`：USB Host 接入，不是 HID/虚拟介质需要的 CRG UDC。

基础启动结果见上述首次启动记录；下一阶段依赖与验收见
[USB 与音视频适配拆解](archive/kernel-edge-porting.md)。
新板 `kvim4n` 的硬件差异和启动固件要求也必须核对，不能直接复用厂商 DTB。

## 补丁维护方法

正式 `vim4-kvm-7.3` 只接已通过门禁的提交；`topic/*` 保存可独立评审的小系列，
并写明 DT、clock 和 pwrc 依赖。`integration/next-日期` 固定目标、系列清单与配置，
定期记录冲突、构建和测试成本；`experiment/*` 隔离私有 ABI、故障注入和受控上电。
保留原作者和提交签名，先吸收上游已有实现，再删除对应下游补丁。

逐提交运行 strict checkpatch、宿主 fixture、binding 和 DT 实例检查，再用同次配置构建
Image、DTB 和完整模块。保留失败、跳过和产物哈希；宿主 fixture 不能代替 KUnit 或硬件验收。
`packaging/kernel/maintain.py` 提供 inventory、forward 和 verify；具体用法、
厂商对照与音频基线依赖见[维护快照](archive/kernel-patch-inventory.md#主题序列与一键离线验证)。
forward 遇冲突须保留现场，解决后对完整结果运行 verify；构建成功不能覆盖其他阶段失败。
离线检查通过后按[部署门禁](subsystems/deployment.md#内核开发流程与部署门禁)安排独占回归；
全局改动仍需九类回归和性能配对，离线通过不代表可部署。

## Wave5 隔离告警

隔离后保留DMA内存/映射，只能重启清除；先尝试受控genpd循环/固件冷加载，旧实例报错、新实例重开，复位失败才隔离。
[运行时复位](bringup/2026-10-23-wave5-runtime-window.md)、[软件注入](bringup/2026-10-23-wave5-isolation-final.md)不证明真实固件挂死可恢复；[编码边界](bringup/2026-10-23-wave5-parity-window.md)中的合入也不代表正式安装。

状态字段、文件位置与默认策略见[监控器](../board/vim4-wave5-monitor.py)、[单元](../board/vim4-wave5-monitor.service)。启用自动重启也须确认所有KVM应用已停止、虚拟介质为空且持续空闲；运行中但空闲的One-KVM不能作“无需求”证明，clients未覆盖UU/RTSP/录屏。
读取失败取消空闲计时，同启动只尝试一次；不能覆盖管理员的自动重启配置。部署接入见[final-window](../packaging/kernel/final-window.py)，板端实测范围以专项记录为准。

## 相关记录

- [RX同链路对照与修复](bringup/2026-10-23-hdmirx-vendor-comparison.md)：TOP测量VALID空窗曾误判失锁，恢复状态不能直接归因源/线缆；短测不证明长期稳定。
- [M0](bringup/2026-10-23-display-m0-r4.md)、[PCM/SARADC](bringup/2026-10-23-kvm-audio-capture-stability-deploy.md)、[SARADC取证](bringup/2026-10-22-saradc-timeout-audit.md)：静态handoff仅当前布局，原生切模式/4K显示器未验；旧音频/重启证据不算本轮重测。
- [uhd6正式验收](bringup/2026-10-31-uhd6-formal.md)、[尺寸/QP/GPU批量验证](bringup/2026-10-30-kernel73-gap-validation.md)、[复验](bringup/2026-10-30-kernel73-gap-r3.md)：逐轮通过/失败范围，不与现行身份混用。

- [Wi-Fi 整包安装](bringup/2026-11-02-wifi-sdio-formal.md)、[.217 固件对照](bringup/2026-11-02-wifi-fw217.md)：BCM43752 构建输入、连接与回退；[PHY trap 排查](bringup/2026-10-21-edge-wifi-fps.md)保留转储，内部根因未确认。
- [管理器与 WPA3](bringup/2026-10-21-manager-mainline-status.md)、[Wi-Fi Direct](bringup/2026-10-21-edge-wifi-p2p.md)：WCC/AKM 与 P2P 适配，真实对端传输未验。
- [双内核运行时](bringup/2026-10-21-dual-kernel-integration.md)：应用数据与切换验证；此前的[独立实验网关](bringup/2026-10-20-edge-lan-gateway.md)使用回环 8082，不代表正式入口。
- [实验 HID](bringup/2026-10-20-edge-hid-integration.md)、[USB 功能接入](bringup/2026-10-21-edge-usb-functions.md)：早期独立准备器、助手和数据目录的验证范围；当时 USB 串口未启用。
- [NanoKVM 迁移快照](archive/nanokvm-migration.md)、[迁移前功能差异](archive/nanokvm-feature-review.md)、[旧功能表](archive/feature-status.md)、[One-KVM 审查](archive/one-kvm-audit.md)：历史应用基线，不代表现行功能。
- [高码率实验](bringup/2026-10-14-4k60-high-bitrate-experiment.md)、[HEVC 画质模式](bringup/2026-10-27-hevc-quality.md)、[UU 文件传输](bringup/2026-10-25-uu-files.md)：应用能力的原始验收边界。
- [看门狗运行时复位](bringup/2026-10-23-wave5-parity-window.md)：停止喂狗后的串口与恢复证据，不覆盖睡眠期硬锁。
- [7.x 缩放与硬件 MJPEG](bringup/2026-10-21-edge-scaling-jpeg.md)：VDIN 下采样、HCODEC/OP-TEE 接入与 4K 帧率边界。
- [UHD 清晰度复核](bringup/2026-10-20-edge-uhd-detail.md)：Mac 实际渲染栅格、原生单像素细节与 1080p 放大负对照。
- [7.3 HDMI 音频](bringup/2026-10-20-edge-hdmi-audio.md)：独立 ALSA 声卡及网页 Opus；[动态 LPCM](bringup/2026-10-22-edge-hdmi-audio.md)记录 ACR/AIF 检测、七档采样率、重采样缓冲与无链路恢复。
- [7.x 逐行刷新](bringup/2026-10-20-edge-cyclic-refresh.md)：固定 UHD60 的周期关键帧、呈现间隔与重复对照。
- [7.x 状态查询与端到端](bringup/2026-10-20-edge-status-latency.md)：去除实时查询的 20ms 等待、校准时钟与测量开销。
- [7.x HDMI 真实时序](bringup/2026-10-20-edge-input-timings.md)：标准 V4L2 查询、测量帧率与动态重配的剩余限制。
- [7.x 失锁查询与队列锁](bringup/2026-10-20-edge-queue-lock.md)：状态/停流锁分离，格式与缓冲生命周期回归。
- [7.x 动态分辨率](bringup/2026-10-20-edge-dynamic-modes.md)：RGB8 1080p60/4K60 的 PHY、音频、队列和应用重建，以及孤儿缓冲回收。
- [7.3 HDMI 输入模式覆盖](bringup/2026-10-22-edge-hdmi-modes.md)：实测时序分档、原生 YUV/深色转换和 DMA 行对齐；[最终复核](bringup/2026-10-22-edge-hdmi-modes-final.md)记录浏览器覆盖、HEVC 回退与恢复证据。
- [VDIN 直接 DMA](bringup/2026-10-20-direct-dma-benchmark.md)：持有/隔离语义、本地回归与 4K60 应用 CPU 对照。
- [7.3 One-KVM 接入](bringup/2026-10-20-onekvm-wave5.md)：独立后端、网页 4K60 与重配回收故障。
- [7.3 CPU 性能定位](bringup/2026-10-20-onekvm-performance.md)：真实应用基线、压缩码流缓存和剩余原始帧复制开销。
- [7.3 HDMI 1080p60](bringup/2026-10-19-hdmirx-dma-ring.md)：实验私有 DMA 环、V4L2 MMAP 复制队列及剩余接入缺口。
- [7.3 HDMI DMA-buf](bringup/2026-10-19-hdmirx-dmabuf.md)：此前的连续导出、缓冲跨驱动重载及软件 H.264 校验。
- [7.3 Wave521 与 4K60](bringup/2026-10-19-wave521-uhd.md)：固定 RGB8 输入、NV12、H.264/H.265 硬编码与实测边界。
- [HDMI 恢复路径对照](archive/hdmi-recovery-review.md)、[UU 虚拟屏恢复](bringup/2026-10-15-uu-virtual-screen-recovery.md)：显示器恢复故障的源码审查与现场取证。
