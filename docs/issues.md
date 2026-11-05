# 未解决 issue

修复时在同一提交删除对应条目；新发现按 [代码与协作规范的分流规则](code-standards.md#审查)决定是否登记。
本文件是仓库唯一的未解决 issue 清单；上板记录保留历史证据，不随问题关闭改写。

## 内核与部署

- 联合调试 `.23` 在 `meson_mmc_irq → meson_mmc_post_req → debug_dma_unmap_sg` 报 `BUG: Invalid wait context`，随后约 18 秒串口转 BL2 并报 cold_boot，未保存到 panic；锁错误与冷复位因果未确定。候选已退出并恢复 `.3`，标准解码未运行；须先修复/定位启动问题才能验收调试解码。[原始堆栈与恢复证据](bringup/2026-11-05-vdec-joint-debug.md#实板结果)
- PWM 跨 chip 的 prepare_lock/nonatomic_lock 建模已按协调者授权在独立分支提交 `0a35577b8de2` 增加独立 key，arm64 QEMU 锁依赖回归 1/1；regulator 与 Wi-Fi 使用不同 chip，但 debugfs/初次 request 的 Wi-Fi 硬件查询仍有同实例真实 ABBA，保留未解决，实板零 splat 待验。[锁链、拓扑与修复边界](bringup/2026-11-05-debug-splat-fixes.md#pwm-锁依赖分析与修复边界)
- ADLA 启动时 DMA SG 超限已在独立分支提交 `4c4126df2f8a`，按设备现有上限切分，模块/内建及生产构建完成；W=1+sparse 仍有既存 vendor 诊断。已纳入 `.23`，但候选先遇 MMC 锁错误及冷复位，未完成 ADLA probe 与零 DMA-API 告警联合复验。[根因与验证边界](bringup/2026-11-05-debug-splat-fixes.md#adla-dma-路径)
- 主线应用程序与插件位于整包和组件包都不提供的 `/opt/vim4-kvm` 私有目录（`hdr10-r14e`、`one-kvm-usb-*`），重刷或新板安装主线后须另行安装这些运行时，否则启动器 exec 失败。[启动器](../board/vim4-kvm-run)
- 内核升级在写入 kernels.json 后、切换 extlinux 前中断，会使面板报告 Mainline 不可用并拒绝选择；U-Boot 仍启动旧整包，重新登记可恢复面板。[安装器](../packaging/kernel/register-runtime.py)
- board-window 在新刷 5.15 镜像使用 `LINUX /Image` 符号链接布局时拒绝基线，因为要求路径含 release；当前板的版本化路径不受影响。[预检](../tools/board-window)
- 厂商内核正式打包只接受 `5.15.137-vim4kvm`，板上实际 Vendor 是 `5.15.137-vim4kvm-hdrdual6`；按现有脚本重建厂商内核会得到不同 release，需要先统一厂商命名再重建。[打包脚本](../packaging/kernel/package.sh)
- EDID 撤回后重新发布遇 RAM 读回失败，若 previous_size=0 或回滚也失败，ddc_active 被清除，解绑可能遗漏恢复 probe 前快照。[审计](bringup/2026-11-01-hdmirx-edid-serror-audit.md#登记-issue不修)；[后续复核](bringup/2026-10-31-uhd6-edid-review.md)

## 采集与编码

- 解码 `.25` HEVC 等待 SOURCE_CHANGE 超时；按厂商尺寸条件限制 bit21 后仍超时，尚不能归类为固件能力限制。下一实验为 ACTION/CPU reset 顺序及读回。[实验记录](bringup/2026-11-05-vdec-full-conformance.md#hevc-bit21-单变量实验)
- 解码 `.25` stateless/JPEG compliance 各 60/60，完整标准流仅 H.264 58/135、MPEG-2 18/43 通过。`.26` 修复多 slice 生命周期后 11 条转通过，3 条单 slice 对照通过；隔行/cropping/FMO 的 7 Fail 和 FM1_FT_E 内核超时仍在，未重跑全套。[复验结果](bringup/2026-11-05-vdec-multislice.md#r47-实板结果)、[失败聚类](bringup/2026-11-05-vdec-failure-groups.md)
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

- brcmfmac NVRAM 注释解析越界已在独立分支移植上游修复 `17d29954473b6`；真实解析器 KUnit 在 arm64 QEMU + KASAN 通过 3/3。`.23` 串口确认 Wi-Fi 固件初始化成功、未见旧越界特征，但候选冷复位，整轮调试验收未完成。[修复来源与边界](bringup/2026-11-05-debug-splat-fixes.md#上游核对与-brcmfmac)
- meson-gx-mmc 错误恢复在停止超时后仍归还缓冲区，可能在硬件仍访问时复用内存；缺当前已修证明，保留待核对。[主机路径审查](bringup/2026-11-02-wifi-sdio-host-path.md#改动)
- meson-gx-mmc 的 dma_map_sg 失败路径可能写越界，影响映射失败后的内存安全；缺当前已修证明，保留待核对。[主机路径审查](bringup/2026-11-02-wifi-sdio-host-path.md#改动)
- brcmfmac 未检查 OOB 路由写失败，设备配置失败时可能继续使用未就绪中断，影响收发；缺当前已修证明，保留待核对。[主机路径审查](bringup/2026-11-02-wifi-sdio-host-path.md#改动)

## 测试工具

- One-KVM HDMI 重采样有限输入测试在整包全量运行时出现一次输入队列超过半秒音频量的保护失败；独立复核和未改源码的全量库测试重试均通过。需进一步区分并行调度与测试输入生产速度，不能据此判定实板采集停滞。[TWCC 打包记录](bringup/2026-11-04-uu-twcc.md)
- M6 测试源只记录绘制或 vsync 回调，缺实际呈现回执；重复/跳号无法可靠归因采集端，严格连续性门禁受限，需对照 presentedTime 与采集帧号。[高刷与 444 记录](bringup/2026-11-02-hfr-yuv-window.md)
