# 未解决 issue

修复时在同一提交删除对应条目；新发现按 [代码与协作规范的分流规则](code-standards.md#审查)决定是否登记。
本文件是仓库唯一的未解决 issue 清单；上板记录保留历史证据，不随问题关闭改写。

## 内核与部署

- 解码评审系列保留 Kövér-Draxl 的 MPEG-2、MJPEG、HEVC 原作者，但原提交 `b1bdea695746b`、`37b50c957b4b1`、`0204da89aa08d` 缺原作者 Signed-off-by。只加整理者自己的签署；strict checkpatch 的 nominal-author 签署错误按失败保留。上游提交前需原作者补 SoB，或按 DCO (b) 完成来源说明；短期不提交上游、不联系作者，不代签、不改作者。整理者签署身份 `localhost-copilot` 不是真实姓名，上游前也须换成真实身份的 SoB。
- `fd41fb5950b9` 在arm64 QEMU/KASAN/PROVE_LOCKING下跑额外上游DMA-BUF压力组，单CPU/300秒与双CPU/900秒均在fence-chain的test_wait_forward slow提示后超时，未定位TCG性能或内核等待问题；双CPU竞争用例通过，不能将未完成项记通过。不是实板故障证据，本任务不修改核心实现。[两次配置、原始输出与边界](bringup/2026-11-05-integration-build-results.md#dma-buf-压力复验超时)
- MMC `Invalid wait context` 修复原分支 `f911e1d8817fb`、v2 `5deb393be1501` 离线通过；集成生产`.90`与正式`.3`同窗各600秒328.88/342.08 Mbit/s，同窗-3.86%，通过不超过10%的性能门槛，未改回硬IRQ。此前`.93`相对历史-11.52%不能归因MMC或PD。A仍cold_boot，debug_locks/eMMC调试门禁未完成。[同窗结果、生产配置与恢复](bringup/2026-11-05-integration-wifi-control.md)；[集成边界](bringup/2026-11-05-debug-splat-integration.md)
- ADLA mutex错误合类修复原分支 `53d7db5f377e8` 的真实API QEMU+KASAN+lockdep测试1/1、模块/内建检查完成；v2 `e8c40f17b20ea` 合并到已有5-case独立suite，strict 0/0/0，编译/QEMU待集成窗口。`.83` 没有绑定/lockdep快照，不能判硬件门禁通过。[修复](bringup/2026-11-05-adla-mutex-pd-timing.md#adla-修改与来源)；[冲突处理与未验项](bringup/2026-11-05-debug-splat-integration.md#adla-冲突如何解决)
- cold_boot原因未明；正式fd41fb5也复位，非解码系列独有。RAM对照仍2次/1复位，eMMC默认累计≥34次/7复位：r72正式恢复在7.333898166秒复位后自然恢复成功；r73候选/正式均无非请求复位，proof/视频通过。[r65–r68逐启动间隔](bringup/2026-11-06-vdec-r68-coldboot.md)、[r69间隔](bringup/2026-11-06-vdec-r69-joint.md)、[r72时间线](bringup/2026-11-06-vdec-r72-swap-first-frame.md)、[r73最新计数](bringup/2026-11-06-vdec-r73-eos.md)。`.28`仍9次/2复位，`.31`五次/1非请求复位，`.32`、`.33`、`.34`、`.35`各一次/0复位，不据小样本判断稳定性；[r60分路径统计](bringup/2026-11-05-vdec-coldboot-ab-r60.md)保留。下一步物理测量沿[RESET/VBUS/PD闭环方案](bringup/2026-11-05-vdec-reset-measurement-plan.md)，可能需用户在场，未排板；不猜改PD。此前FUSB302 v1的`.92`仍复位、未达门槛，[旧验证](bringup/2026-11-05-pd-fifo-validation.md)、[状态机与历史统计](bringup/2026-11-05-tcpm-coldboot-audit.md)保留。
- PWM 跨 chip 的 prepare_lock/nonatomic_lock 建模已按协调者授权在独立分支提交 `0a35577b8de2` 增加独立 key，arm64 QEMU 锁依赖回归 1/1；regulator 与 Wi-Fi 使用不同 chip，但 debugfs/初次 request 的 Wi-Fi 硬件查询仍有同实例真实 ABBA，保留未解决，实板零 splat 待验。[锁链、拓扑与修复边界](bringup/2026-11-05-debug-splat-fixes.md#pwm-锁依赖分析与修复边界)
- ADLA DMA SG 上限修复 `4c4126df2f8a` 已离线构建并在集成基线中；`.81/.83` 未见旧超限特征，但cold_boot前未取得绑定/流量/零告警完整门禁。W=1+sparse既存vendor诊断仍保留。[根因](bringup/2026-11-05-debug-splat-fixes.md#adla-dma-路径)；[最新实板边界](bringup/2026-11-05-adla-mutex-pd-timing.md#83-实板与新的-pd-尾部)
- 主线应用程序与插件位于整包和组件包都不提供的 `/opt/vim4-kvm` 私有目录（`hdr10-r14e`、`one-kvm-usb-*`），重刷或新板安装主线后须另行安装这些运行时，否则启动器 exec 失败。[启动器](../board/vim4-kvm-run)
- 内核升级在写入 kernels.json 后、切换 extlinux 前中断，会使面板报告 Mainline 不可用并拒绝选择；U-Boot 仍启动旧整包，重新登记可恢复面板。[安装器](../packaging/kernel/register-runtime.py)
- board-window 在新刷 5.15 镜像使用 `LINUX /Image` 符号链接布局时拒绝基线，因为要求路径含 release；当前板的版本化路径不受影响。[预检](../tools/board-window)
- 厂商内核正式打包只接受 `5.15.137-vim4kvm`，板上实际 Vendor 是 `5.15.137-vim4kvm-hdrdual6`；按现有脚本重建厂商内核会得到不同 release，需要先统一厂商命名再重建。[打包脚本](../packaging/kernel/package.sh)
- EDID 撤回后重新发布遇 RAM 读回失败，若 previous_size=0 或回滚也失败，ddc_active 被清除，解绑可能遗漏恢复 probe 前快照。[审计](bringup/2026-11-01-hdmirx-edid-serror-audit.md#登记-issue不修)；[后续复核](bringup/2026-10-31-uhd6-edid-review.md)

## 采集与编码

- `.31`在r65+r69、官方parser下H.264为129S/1F(CVFC1)/5已知不支持，旧110/58通过集均无回退，AVC评审版已快进内核主线至5dd4f646；MPEG-2整理系列6cf9a04e/091d19b9经r73四流实际输出与r72逐字节相同后，由协调者快进内核主线至091d19b9；均未部署。[全集与MPEG-2矩阵对照](bringup/2026-11-06-vdec-r69-joint.md)。r72的`.34` H.264三流仍Success；MPEG-2 REF0后向anchor别名使sony-ct1/ct2起始B两队列零ERROR、前两显示帧对ISO差值均≤2，但整流仍2Fail，显示帧2起分别与r71/r70逐字节相同，差值>2仍7/2字节。sony-ct3和mcp10ccett均Success且输出不变；修复边界是起始B错误完成，剩余像素问题未解决。[r72逐流证据](bringup/2026-11-06-vdec-r72-swap-first-frame.md)；[r70旧ERROR](bringup/2026-11-06-vdec-r70-integration32.md)、[r71拒绝诊断与采证缺口](bringup/2026-11-06-vdec-r71-handshake.md)保留。 r73整理版091d19b9四条实际输出经宿主逐字节核对均等于r72、零ERROR，H.264三流仍Success；板端草稿误选参考文件的采证缺口及实际输出证据见[r73](bringup/2026-11-06-vdec-r73-eos.md)，Sony剩余像素Fail仍未解决。
- `.28` H.264 原环境全集仍110/135套件通过（旧58项无回退）、20Fail、5已知不支持，实际Error/Timeout历史不抹去。r61在官方parser下另确认14条驱动像素正确，当时MR3/4/5两parser均Fail；不改写原环境统计。[缺口参考修复](bringup/2026-11-05-vdec-gap-references.md)及存储归属修复在[r64](bringup/2026-11-06-vdec-r64-storage.md)使MR3/4/5各300帧逐字节正确、两队列零ERROR，7条对照无回退；这三条的已复现故障已验证修复，候选未部署，不能推广到整个LTR集合。S4仅离线验证，L1[0]占位仍拒绝；调试锁/内存、HOLD+FLUSH、High profile子集和5.15有效对照未验，不能宣称完整parity。[最终汇总](bringup/2026-11-05-vdec-avc-final.md)、[r61逐帧证据](bringup/2026-11-05-vdec-r61-parser-ab.md)
- Khadas `2:1.24.2-1ubuntu4` h264parse漏末slice是用户态问题，非内核：r61的13条隔行和CAWP5用官方Ubuntu同版本parser全部Success，Khadas组均少一个显示帧且其余像素逐帧正确；具体影响清单/MD5见[r61](bringup/2026-11-05-vdec-r61-parser-ab.md)。两条Sharp现亦在[r65+r69官方parser](bringup/2026-11-06-vdec-r69-joint.md)下各15帧逐字节正确，不改写Khadas原环境成绩。修复方向可选换官方包或向Khadas报告，由用户决定；当前只在任务私有前缀验证，未替换系统库、未对外发送报告。
- 历史 `.25` stateless/JPEG compliance 各 60/60，MPEG-2 标准流18/43；后续 H.264 多 slice、隔行已推进至上述`.28`结果。MPEG-2与HEVC未决问题未由本轮H.264验收解决。[失败聚类](bringup/2026-11-05-vdec-failure-groups.md)
- `.27` r49 隔行子集四条转通过，Sharp_MP_Field_1_B/Sharp_MP_PAFF_1r2 仍像素 Fail，全集待重跑。CVFC1 驱动输出 50 帧按 `(26,60)` 裁剪后逐字节等于参考，MD5 `9fdb17e17d332b5d9752362c9c7ff9b0`；GStreamer 1.24.2 v4l2codecs 忽略 crop 偏移，从原点裁剪复现套件错值 `d2aeaea0b9da3509442377a849cc2ff1`。登记驱动通过/套件 Fail，不改插件。[原始证据与代码位置](bringup/2026-11-05-vdec-field-lifetime.md#cvfc1-的一次性证据工具)
- 两条 Sharp 各少一帧，其余输出逐字节正确；r54 零丢事件 trace 证实最后 slice 未进 OUTPUT。r56 的 md5/仓库/安装历史确认 Khadas `2:1.24.2-1ubuntu4` 系统 h264parse 排空限制，未发现安装后覆盖；官方无 epoch 包不同，不归咎官方原包，不改插件。套件仍 Fail；HOLD+FLUSH 释放未单独实测。[队列证据](bringup/2026-11-05-vdec-r54-sharp-trace.md)、[来源闭环](bringup/2026-11-05-vdec-r56-fmo-parser.md)
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

- One-KVM HDMI 重采样有限输入测试在整包全量运行时出现一次输入队列超过半秒音频量的保护失败；独立复核和未改源码的全量库测试重试均通过。需进一步区分并行调度与测试输入生产速度，不能据此判定实板采集停滞。[TWCC 打包记录](bringup/2026-11-04-uu-twcc.md)
- M6 测试源只记录绘制或 vsync 回调，缺实际呈现回执；重复/跳号无法可靠归因采集端，严格连续性门禁受限，需对照 presentedTime 与采集帧号。[高刷与 444 记录](bringup/2026-11-02-hfr-yuv-window.md)
