# HDR 输入映射

普通HLG的独立离线内核候选、厂商表/定点证据、PQ合并边界与统一上板清单见[HLG候选](hdr2-hlg.md)。
该候选尚未上板，不改变下文已验证范围或扩大正式EDID能力。

5.15 原生双路径的四套 KVM 均可选择保留远程 HDR10，见
[全应用 HDR 接入](bringup/2026-10-26-all-kvm-hdr.md)。以下默认 SDR 映射仍用于
H.264、JPEG、截图以及开启「HDR 转 SDR」的 H.265；HDMI OUT 偏好独立。

管理器「视频输入 → HDR 转 SDR → 启用 HDR 转 SDR」保存全局远程画面默认值。
开启时输出 SDR；关闭且输入为 PQ 时，四套应用的 5.15 H.265 可保留 PQ/BT.2020 Main10。
H.264、JPEG 和截图仍输出 SDR。NanoKVM、JetKVM 与 PiKVM 预先协商 Main10，
开关切换只重建采集编码，不更换 WebRTC 连接；One-KVM 沿用 profile 重新协商。
切换不改 EDID、不重启 HDMI；7.x 目前继续使用 SDR。
关闭转换不会自动切换编码，观看 HDR 仍需选择 H.265。
[浏览器兼容性复核](bringup/2026-10-26-hdr-browser-compatibility.md)确认 Chrome 156
收到真实 Main10 并保留 PQ/BT.2020；Safari 27.0.1 当前 WebRTC 帧变为八位 BT.709。
这不能视作 Safari 远程 HDR 已支持。
参数 `HDR_SDR_ENABLED=1|0` 与曲线共存于 `/etc/default/vim4-kvm-hdr`；
旧安装未保存此项时沿用原应用偏好。UU 的 HDR 设置只覆盖当前会话，
断开后恢复最新全局默认值，期间修改全局开关不会打断 UU 的临时设置。
仅支持八位的 UU 客户端在会话内自动使用 SDR。
One-KVM 页面不再提供 HDR 开关及白点/峰值控制；保存其输出分辨率、帧率和 JPEG
质量时保留当前 HDR 默认值。曲线和全局开关统一在管理器「视频输入」调整。

EDID 预设声明 HDR10/HLG，主机开启 HDR 时发送 PQ/HLG 10bit 信号。采集为 8bit，
未处理时画面发白。T7 的 vdin0 有独立 HDR2 核，内核在 HDMI 输入为
HDR10/HDR10+/HLG 时将其映射到 SDR，SDR 输入直通（`dmesg` 中
`vdin_set_hdr vdin0 fmt:N`，0=SDR、1=HDR10）。切换由驱动的信号变化处理完成，
不重启服务。显示与 KVM 共享的 NV21 帧已经是 8-bit SDR，不能只保留源 HDR 标签再向 TX
发送 HDR infoframe，否则会重复色调映射或把 SDR 冒充 HDR。HDR 修复候选同步清除映射后
帧的 HDR 元数据，输出 BT.709 SDR，并通过 `vdin0/hdr_sdr` 只读状态提供映射资格。
输入状态仍通过 RX 报告 HDR10/HLG，与实际输出域分开。原生 HDR 显示需要拆分 HDR 显示
与 SDR KVM 捕获；仅设置 `vdin1_bypass_hdr 1` 只会跳过后续配置，不证明已有 HDR 核已旁路，
VDIN1 回写又会把 KVM 绑定输出时钟/热插拔，不能直接当作已验证替代方案。
Dolby Vision 未支持，EDID 也不声明。

映射表由 `vim4-hdr-curve`（tools/hdr-curve.sh）生成：增益曲线 `oo_y_lut_hdr_sdr`
和 SDR 编码曲线 `oe_y_lut_sdr`。厂商增益曲线相当于 400 尼特映射为 SDR 白，
厂商编码为 gamma 2.2，macOS HDR 桌面会整体偏暗、暗部偏亮。
参数 `HDR_SDR_WHITE`（主机 SDR 白，默认 203 尼特，即 BT.2408 参考白；macOS HDR
灰阶实测 199）和 `HDR_SDR_PEAK`（高光保留到的亮度，默认 1000）保存在
`/etc/default/vim4-kvm-hdr`，与 NanoKVM 改写的 `/etc/default/vim4-kvm-hdmi` 分开。
5.15 在 SDR 白以下 95% 线性，其上用扩展 Reinhard 曲线压入顶部 5%；编码为 sRGB。
增益寄存器为 12 位（上限 4095），SDR 白低于 157 尼特会溢出反而变暗，故下限 160。

hdmi-setup.sh 在打开输入前写入；运行中由 vdin0 attr 的 `reload_hdr` 请求采集中断在帧边界重载，
不重启采集。vim4-manager 的“HDR 转 SDR”滑动条拖动时实时预览，松开后保存。
`oe_y_lut_sdr` 与 VPP/OSD 的 HDR→SDR 共用，将来接 HDMI 输出时同样生效。
HLG 输入仍用厂商 HLG 曲线。

原生显示双路径的新版5.15另有 `vdin_oo_y_lut_hdr_sdr`：完整149点写入后只供VDIN0/1
使用，避免VPP的动态映射/回落覆盖用户设定的增益曲线。`vim4-hdr-curve apply` 同时写入
此独立增益；原生模式还请求VDIN1在帧边界重载。VDIN1直接借用HDMI RX时由自己的V4L2
中断跟随颜色格式、范围、位深和HDR EOTF，而不是依赖仅为VDIN0运行的接收状态机。
切换残留和变暗的复现、实际寄存器及误差边界见
[HDR切换颜色修复](bringup/2026-10-25-native-hdr-color.md)。

7.x 的独立 edge 服务已接通 PQ / BT.2020 / YCbCr420 10bit 4K60，见
[采集与映射实测](bringup/2026-10-20-edge-hdr-capture.md)；HLG 等其他格式未适配。
`vim4-hdr-curve` 在此内核向平台设备 `hdr_curve` 一次原子提交两行表，由 IRQ 在安全帧边界
重载；参数文件与 helper 的预览/保存接口相同。

7.x 使用单独的高光曲线：保持 sRGB 编码 90% 以下不变，剩余 10% 码值使用对数肩部
压缩到 PEAK，衔接处斜率连续。默认约 160 尼特开始压缩，暗部、中间调不变；
HDR 桌面白会略暗，换取 400/600/1000 尼特的可辨层次。`tables-edge WHITE PEAK`
可离线输出这组表；`apply` 根据可写 edge 接口自动选择，`tables` 与 5.15 写入仍用
原曲线。验证与亮度限制见 [高光与连接优化](bringup/2026-10-20-edge-hdr-optimization.md)。

## 双路径采集与部署约束

5.15 原生显示模式 `aml_media.vdin0_native_hdr=1` 例外：VDIN0 保留10-bit HDR，
VDIN1 同源独立映射 SDR，四套应用由启动器选 `/dev/video71` 和私有标准 V4L2 插件。
该模式不是普通 vfm_cap NV21 采集：NanoKVM、JetKVM、PiKVM 及 One-KVM 的独立
MJPEG 分支使用公共 `vim4vdin1src`；One-KVM 的 H.264/H.265 保留原有 VDIN1 接入。
采集包提供 `vim4-vdin1-api-1` 和标准插件，须先于依赖它的应用部署；
`GST_V4L2_PREFER_CONTIGUOUS` 仅保留在厂商后端，7.3 启动器必须清除它：
否则 Wave5 选择单平面输入，拒绝应用提供的两个 DMA 平面视图，第一帧即失败。
实际 HDR10 4K60、元数据与默认部署见 [双路径交付](bringup/2026-10-25-native-hdr-dual-path.md)。

### 7.x 映射的验证边界

以下记录 7.x 路径的验证范围；基础采集格式与映射表提交接口见本文前节。
SDR 420 和 RGB 分别直通、矩阵转换。[高光与连接优化](bringup/2026-10-20-edge-hdr-optimization.md)
给 8bit 高光留出层次，并避免重复输入通知重建健康连接；HDR 桌面白略暗。
H.265 八轮、H.264 四轮 HDR 往返保持同一连接；HLG/其他格式及长期稳定性未验收。
后续 [切换与稳定性验收](bringup/2026-10-21-edge-hdr-stability.md) 补齐启动状态查询、
后台切换和界面遮罩的事件顺序回归；显示休眠与真实 HDMI 拔插能自动恢复。
整机休眠由用户暂缓，不能与显示休眠混为已通过。
音画偏差复核使用 [播放输出回环校准](bringup/2026-10-21-edge-av-calibration.md)，
先测已知偏移与观察器偏置；旧独立音轨探针的首尾差不能直接判作内核漂移。

## 相关记录

5.15 One-KVM 的远程 Main10 HDR 与扩展尺寸验收范围见[原始记录](bringup/2026-10-26-remote-hdr-modes.md)。
HDR降分辨率见[UU GPU 缩放](bringup/2026-10-27-uu-hdr-scale.md)及
[四应用公共路径](bringup/2026-10-27-all-kvm-hdr-scale.md)，不能套用原尺寸性能。
SDR 超宽屏硬件缩放及 JetKVM/PiKVM 尺寸入口见
[缩放与尺寸控制](bringup/2026-10-27-sdr-scale-controls.md)；5.15 统一使用连续 V4L2 DMA。
4K HDR 最初完整网页约34fps；后续[GPU/DMA 链路](bringup/2026-10-26-hdr-gpu-pipeline.md)
已实测真实 PQ Main10 网页约60fps。HLG、7.x Main10与本地新模式未验收。
后续[像素复核](bringup/2026-10-26-remote-hdr-pixels.md)修正 AMLY 解包花屏，
保留 HDR 偏好时 SDR 输入自动走八位 DMA；源端切换的 CMA 分配候选复测失败，已撤回。
[HDR GPU 前置验证](bringup/2026-10-26-hdr-gpu.md)补齐匹配的私有 Mali Vulkan 驱动；
现已接通小端 AMLY→P010 compute 与 Wave521 DMA_TYPE，固定双缓冲，保持输入退休后归还。
HDR 专用 SDR 快照通道单独缩减下游缓冲预算，保留原分辨率，避免挤占编码器连续内存。
后续[全局 HDR 默认与源端切换](bringup/2026-10-26-hdr-global.md)增加视频输入页开关，
结合主采集池预算、编码器优先预留及完整释放，修复5.15 PQ/SDR往返的CMA问题。
关闭全局转换不会自动把 H.264 切换为 H.265；码流、解码 HDR 与屏幕光度分别验收。
[全应用 HDR 接入](bringup/2026-10-26-all-kvm-hdr.md)将 NanoKVM、JetKVM 和 PiKVM
接入公共 `vim4h265src`，跟随同一全局开关；WebRTC 明确协商 Main10，Direct 原生视频
轨道保留 PQ，H.264/JPEG 继续 SDR。编码包新增 `vim4-hevc-hdr-api-1`，须先于应用部署。
