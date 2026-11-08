# 未解决 issue

修复时在同一提交删除对应条目；新发现按 [代码与协作规范的分流规则](code-standards.md#审查)决定是否登记。
本文件是仓库唯一的未解决 issue 清单；上板记录保留历史证据，不随问题关闭改写。

## 内核与部署

- 冷复位（cold_boot）原因未明：正式内核同样在 Linux 起点约 7–9 秒复位，非解码系列独有。正式默认已加 `module_blacklist=fusb302`（B 状态），A/B 首轮 A2/10、B0/10（Fisher p≈0.47）不足以归因 VBUS/PD；黑名单不证明物理断电，失败末段 TCPM 日志与物理 VBUS 均未观测。后续复位继续记入[事件表](bringup/data/2026-11-05-tcpm-coldboot-events.csv)，按[RESET/VBUS/PD 闭环方案](bringup/2026-11-05-vdec-reset-measurement-plan.md)推进，不猜改 PD、不据小样本或拓扑变化归因。[正式切换](bringup/2026-11-07-pd-firmware-default.md)、[A/B](bringup/2026-11-07-pd-takeover-ab.md)、[最新累计](bringup/2026-11-06-vdec-integration42-results.md#冷复位恢复与停止边界)、[r60](bringup/2026-11-05-vdec-coldboot-ab-r60.md)、[历史审计](bringup/2026-11-05-tcpm-coldboot-audit.md)
- [.42 首次正式启动](bringup/2026-11-07-deploy42-default.md)60 秒 receiver 无帧，复验通过，原因未定位；[.43](bringup/2026-11-08-vdec-dos-regmap-deploy.md)首次即通过不说明已修复，其九类回归未运行。无客户端时 device_busy 不能断定 DOS 冲突。
- 解码评审系列中 Kövér-Draxl 的原提交 `b1bdea695746b`、`37b50c957b4b1`、`0204da89aa08d` 缺原作者 Signed-off-by，strict checkpatch 按失败保留；整理者身份 `localhost-copilot` 也非真实姓名。上游前需原作者补 SoB 或按 DCO (b) 说明来源，并换真实身份签署；短期不提交上游、不代签、不改作者。
- 上游 DMA-BUF 压力组在 arm64 QEMU/KASAN/PROVE_LOCKING 下于 fence-chain test_wait_forward 超时（单 CPU 300 秒、双 CPU 900 秒），未区分 TCG 性能与内核等待；非实板故障证据，不记通过。[配置与输出](bringup/2026-11-05-integration-build-results.md#dma-buf-压力复验超时)
- MMC `Invalid wait context` 修复（v2 `5deb393be1501`）已过同窗 -3.86% 的性能门槛，但 debug_locks/eMMC 调试门禁未完成。[同窗结果](bringup/2026-11-05-integration-wifi-control.md)、[集成边界](bringup/2026-11-05-debug-splat-integration.md)
- ADLA mutex 错误合类修复 v2 `e8c40f17b20ea` 离线 strict 0/0/0，编译/QEMU 待集成窗口；实板缺绑定/lockdep 快照，硬件门禁未过。ADLA DMA SG 上限修复 `4c4126df2f8a` 已在集成基线，实板未见旧超限，但绑定/流量/零告警门禁未完成。[mutex](bringup/2026-11-05-adla-mutex-pd-timing.md#adla-修改与来源)、[SG 根因](bringup/2026-11-05-debug-splat-fixes.md#adla-dma-路径)、[冲突与未验项](bringup/2026-11-05-debug-splat-integration.md#adla-冲突如何解决)
- PWM 跨 chip 锁依赖建模已修（`0a35577b8de2`），但 debugfs/初次 request 的 Wi-Fi 硬件查询仍有同实例真实 ABBA，实板零 splat 待验。[锁链与边界](bringup/2026-11-05-debug-splat-fixes.md#pwm-锁依赖分析与修复边界)
- 主线应用程序与插件位于整包和组件包都不提供的 `/opt/vim4-kvm` 私有目录（`hdr10-r14e`、`one-kvm-usb-*`），重刷或新板安装主线后须另行安装这些运行时，否则启动器 exec 失败。[启动器](../board/vim4-kvm-run)
- 内核升级在写入 kernels.json 后、切换 extlinux 前中断，会使面板报告 Mainline 不可用并拒绝选择；U-Boot 仍启动旧整包，重新登记可恢复面板。[安装器](../packaging/kernel/register-runtime.py)
- board-window 在新刷 5.15 镜像使用 `LINUX /Image` 符号链接布局时拒绝基线，因为要求路径含 release；当前板的版本化路径不受影响。[预检](../tools/board-window)
- 厂商内核正式打包只接受 `5.15.137-vim4kvm`，板上实际 Vendor 是 `5.15.137-vim4kvm-hdrdual6`；按现有脚本重建厂商内核会得到不同 release，需要先统一厂商命名再重建。[打包脚本](../packaging/kernel/package.sh)
- EDID 撤回后重新发布遇 RAM 读回失败，若 previous_size=0 或回滚也失败，ddc_active 被清除，解绑可能遗漏恢复 probe 前快照。[审计](bringup/2026-11-01-hdmirx-edid-serror-audit.md#登记-issue不修)；[后续复核](bringup/2026-10-31-uhd6-edid-review.md)

## 采集与编码

- HEVC 8bit `.42` 全集 127/132 Success、3 Error、2 内核 Timeout：RAP_B 像素全对但 SOURCE_CHANGE/CAPTURE 建立不满足非 DRC 事件合同；RPS_D 68 帧未交齐；VPSSPSPPS 首 AU invalid RPM、零帧；LTRPSPS_A/WPP_D 零输出超时。未证明是固件或私有 ABI 限制，不宣称 5.15 parity。10bit/Main10/超尺寸、全面性能、长期稳定及调试锁/内存未验；r80/r81 的 epoll OUTPUT#15 间歇故障未证明消失。[.42 逐流结果](bringup/2026-11-07-vdec-integration42-pd-results.md)、[.38 原始失败](bringup/2026-11-06-hevc-integration38-results.md)、[架构约定](vdec-architecture.md)
- H.264 `.31`（官方 parser）129 Success、1 Fail（CVFC1）、5 已知不支持；MR3/4/5 经[存储归属修复](bringup/2026-11-06-vdec-r64-storage.md)各 300 帧逐字节正确，不能推广到整个 LTR 集合。S4 仅离线、L1[0] 占位仍拒绝，调试锁/内存、HOLD+FLUSH、High profile 子集和 5.15 有效对照未验。[全集](bringup/2026-11-06-vdec-r69-joint.md)、[最终汇总](bringup/2026-11-05-vdec-avc-final.md)
- CVFC1 驱动输出按 `(26,60)` 裁剪后逐字节等于参考；GStreamer 1.24.2 v4l2codecs 忽略 crop 偏移导致套件 Fail。登记驱动通过/套件 Fail，不改插件。[证据](bringup/2026-11-05-vdec-field-lifetime.md#cvfc1-的一次性证据工具)
- Khadas `2:1.24.2-1ubuntu4` 系统 h264parse 排空时漏末 slice，13 条隔行、CAWP5 和两条 Sharp 各少一帧；官方 Ubuntu 同版 parser 全部正确，属用户态问题。换官方包或向 Khadas 报告由用户决定，未替换系统库、未对外报告。[r61](bringup/2026-11-05-vdec-r61-parser-ab.md)、[队列证据](bringup/2026-11-05-vdec-r54-sharp-trace.md)、[来源闭环](bringup/2026-11-05-vdec-r56-fmo-parser.md)
- MPEG-2 sony-ct1/ct2 起始 B 错误完成已修（零 ERROR），但显示帧 2 起剩余像素差 >2，整流仍 2 Fail。[r72](bringup/2026-11-06-vdec-r72-swap-first-frame.md)、[r73](bringup/2026-11-06-vdec-r73-eos.md)
- 厂商 `5.15.137-vim4kvm-hdrdual6` 一次性启动在解码前发生 DRM vblank WARNING、CPU 2 hard LOCKUP panic；102 条对照均未运行，已恢复 `.3`。按用户决定暂停对照。[启动与恢复证据](bringup/2026-11-05-vdec-full-conformance.md#515-一次性启动与中止)
- debugfs frame 入口未统一 YUV3 的源资格检查；开发者用该入口采集不合格源时，可能绕过 V4L2 队列的格式限制。[V4L2 采集记录](bringup/2026-11-02-hfr-yuv-window.md#yuv444-和未验项)
- 新鲜 DRM 与普通 AVI 信息不一致时，YUV3 源资格可能误判为 SDR，影响采集颜色解释；验收需保存两者实际记录。[V4L2 采集记录](bringup/2026-11-02-hfr-yuv-window.md#yuv444-和未验项)
- 5.15 专用 VDIN1 插件将百分之一 Hz 读数取整，分数帧率输入会得到不准确的 caps；One-KVM 直开设备的路径不受影响。[vim4_vdin1_caps](../gst-plugin-vfmcap/src/gstvim4vdin1src.c)
- 管线重建与 M6 从 1080p120 切到 1440p120 重叠时，编码器和采集源可能读到不同模式，漏加 QHD AVC 的 60 fps 限额。[编码器 configure](../gst-plugin-venc/wave5/gstvim4wave5enc.c)；[采集源 change_state](../gst-plugin-venc/wave5/gstvim4v4l2src.c)
- 1440p120 HEVC 请求 level 5.1，实际 SPS 却报 5.0，超出该级别样本率上限；尚未区分控件设置与固件夹取，可能影响解码兼容性。[码流与测量](bringup/2026-11-02-hfr-yuv-window.md)
- 5.15 amlvenc 只把默认 2048 KiB 输出缓冲裸指针交给 SDK，未传容量；关键帧加参数集超出容量可能越界，返回后查长度太迟。[离线调研](bringup/2026-11-03-amlvenc-on-demand-research.md#登记-issue)
- 5.15 amlvenc 按请求类型标记 SYNC_POINT，自发首帧可能被标为非同步帧，下游 parser 只能部分修正，影响起播判定。[离线调研](bringup/2026-11-03-amlvenc-on-demand-research.md#登记-issue)
- 5.15 amlvenc 的 encode_data_len 始终为 −1，无效 metadata 错误日志无法报告实际长度，妨碍诊断。[离线调研](bringup/2026-11-03-amlvenc-on-demand-research.md#登记-issue)
- NanoKVM、PiKVM 放宽 GOP 下限后，5.15 vendor 后端也接受手动 GOP 0；源码支持但该配置未在 5.15 上板验证，按需关键帧行为待确认。[离线调研](bringup/2026-11-03-amlvenc-on-demand-research.md#登记-issue)

## 应用与 USB

- One-KVM 在 r36 基线检查时曾因 SQLite `disk I/O error` 自动重启；根分区当时约 404 MB 可用。r38 只清理已归档的解码上传后增至约 696 MiB，视频恢复，但未建立低余量与错误的因果关系，未改数据库/WAL。[只读检查与清理证据](bringup/2026-11-05-vdec-independent-fluster.md#本任务旧上传清理与-sqlite)
- 官方 Mac UU 的 H.265 会话协商了 transport-cc，但只统计到音频确认；修复估算器补报/乱序过滤后，10 分钟复验仍为零视频确认，RR 回退稳定。同期 H.264 实流有视频确认且吞吐正常，本地 H.265 SRTP 回环也通过。仍需对照原始反馈与接纳计数定位 H.265 差异，不能仅凭汇总计数归因于官方客户端。[TWCC 复验](bringup/2026-11-04-uu-twcc.md#审查修复版部署与复验)
- One-KVM MCP `type` 输入长命令可能丢空格或字符；uhd7 与 7.3.1 均复现，输入法与零按键保持时长的各自影响未分清；US 输入源逐键保持 50ms 可绕过。[复现](bringup/2026-11-03-kernel-731-deploy.md#继续验收与最终状态)
- PATCH 完整原 USB 配置重建 gadget 时，HID 配置值不变可能跳过 backend 重载，后续写入报 endpoint shutdown；切换 profile 再恢复可绕过。[复现](bringup/2026-11-03-kernel-731-deploy.md#继续验收与最终状态)
- One-KVM 从 MJPEG 切入 WebRTC 时可能先保存编码偏好，随后模式转换失败，使保存值与实际状态不一致。[审查记录](bringup/2026-11-03-wave5-avc-default.md#登记-issue)
- One-KVM 网页按请求编码比对就绪事件；硬件因几何限制选择安全编码时，两者不一致，网页可能无法确认就绪。[审查记录](bringup/2026-11-03-wave5-avc-default.md#登记-issue)

## Wi-Fi 与 SDIO

- brcmfmac NVRAM 上游修复 `17d29954473b6` 的真实解析器 KUnit 在 arm64 QEMU+KASAN通过3/3；`.23` 和 `.81` 均确认固件初始化、未见旧越界，但新的锁错误/冷复位使整轮调试验收未完成，不能声称流量回归通过。[来源](bringup/2026-11-05-debug-splat-fixes.md#上游核对与-brcmfmac)；[最新实板边界](bringup/2026-11-05-debug-splat-board-validation.md#a-实板结果与新锁报告)
- meson-gx-mmc 错误恢复在停止超时后仍归还缓冲区，可能在硬件仍访问时复用内存；缺当前已修证明，保留待核对。[主机路径审查](bringup/2026-11-02-wifi-sdio-host-path.md#改动)
- meson-gx-mmc 的 dma_map_sg 失败路径可能写越界，影响映射失败后的内存安全；缺当前已修证明，保留待核对。[主机路径审查](bringup/2026-11-02-wifi-sdio-host-path.md#改动)
- brcmfmac 未检查 OOB 路由写失败，设备配置失败时可能继续使用未就绪中断，影响收发；缺当前已修证明，保留待核对。[主机路径审查](bringup/2026-11-02-wifi-sdio-host-path.md#改动)

## 测试工具

- [formal-gates.py](../packaging/kernel/formal-gates.py) 已将[deploy-73](bringup/2026-11-05-integration-formal-deploy.md#九类验收范围)的受限九类工具化；19 档 HDMI 与 9/11 档编码矩阵夹具仍缺，需由 [hdmi-mode-fixture.py](../packaging/kernel/hdmi-mode-fixture.py) 重建并核验；缺失矩阵不记通过。
- One-KVM HDMI 重采样有限输入测试在整包全量运行时出现一次输入队列超过半秒音频量的保护失败；独立复核和未改源码的全量库测试重试均通过。需进一步区分并行调度与测试输入生产速度，不能据此判定实板采集停滞。[TWCC 打包记录](bringup/2026-11-04-uu-twcc.md)
- M6 测试源只记录绘制或 vsync 回调，缺实际呈现回执；重复/跳号无法可靠归因采集端，严格连续性门禁受限，需对照 presentedTime 与采集帧号。[高刷与 444 记录](bringup/2026-11-02-hfr-yuv-window.md)
