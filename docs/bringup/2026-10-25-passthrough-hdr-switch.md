# 2026-10-25：HDMI 输出 HDR 偏好与独立显示映射

## 实现与范围

接续[原生 HDR 采集颜色修复](2026-10-25-native-hdr-color.md)。
管理器 HDMI 输出增加用户指定的 HDR 行，位于透传与声音之间，复用 SwitchRow；
没有新增卡片、图标、徽标或颜色。inactive 使用既有中性轨道，HDR 与声音一致。
文案、状态优先级、保存目标值与 spinner、窄屏布局均按用户规格。

`GET /api/passthrough` 的 `hdr` 是偏好，`output.hdrToSdr` 是实际读回结果。
`POST {"hdr":false}` 只改 HDR，保留 enabled/audio；透传关闭时也可预设。
偏好与原字段同存 `/var/lib/vim4-manager/passthrough.json`，旧文件缺失 hdr 时默认 true。
保存仍由 Go changeMu 串行化，helper 仅写请求，持 watch.lock 的 watch 是唯一硬件写入者。
status/页面轮询只读。HDR API 将内部故障映射为中文，前端另过滤 sudo、路径和异常文本。

原生双路径保持 VDIN0 原始 HDR、VDIN1 独立 HDR→SDR 采集，不重开 RX，不改 One-KVM。
仅调整 VPP 显示策略：开启时 `hdr_policy=1` 跟随源；关闭或 sink 不支持对应 EOTF 时，
`force_output=1(BT709)`、`hdr_policy=2` 强制 SDR。SDR 源仍旁路，不做 SDR→HDR。
HDR 源在两种偏好下保持 YCbCr422 12-bit，不因 EOTF 切换重设 HDMI 时序。
运行状态须通过 DRM/AVI 与扫描进度确认，不根据偏好推断成功。

厂商 TX 的 HDR→SDR worker 原本发零 DRM 后没有实际关闭包；补齐原有 1.5 秒过渡后
的 DRM 关闭，并保留对新 HDR 输入的检查。host 测试执行实际 worker，覆盖过渡中重新
切回 HDR 时不误删新包。T7 强制 SDR 的 VD1 复用完整 VDIN 用户 gain 表，
HDR10 显示与 KVM 使用同一 white/peak；HLG 保留与采集相同的厂商 HLG 曲线，
不在 UI 暗示 HLG 曲线可调。VDIN 专用表仍不受 VPP 动态表覆盖。

## 构建、部署与持久化

持有 board/heavy 双锁；不修改 EDID、Mac HDR 设置或 One-KVM 代码/编码设置。
候选 `5.15.137-vim4kvm-hdrdual6` 完整 Image、DTB、模块、initrd 一次性启动通过后，
使用 `packaging/kernel/promote.py --no-backup --native-hdr` 更新正式默认，再正常重启。
未新增备份、回退脚本或启动项；仅清理经 manifest/启动引用确认已无引用的 hdrdual2 boot 产物。

- 完整包 SHA256：`728ce5f797ce2a3f9037b746212af6cec3d64bbd973da8acfe158bc63daf4f03`。
- 运行 aml_media note SHA256：`af4f6f05224e27839c036bf6df9eaf88e55f9b0d4472a86e52010b449be7cbd1`。
- 在 HDR 输入下保存 hdr=false 后正常重启，实际回到 running、hdr=false、hdrToSdr=true，
  确认不是仅文件保存；随后恢复 hdr=true 作为最终偏好。
- One-KVM 保持 `24d35af8`；声音仅检查服务 active，不播放/采集测试音，不做听感验收。

## 自动验收

候选阶段直接点击真实页面 HDR 开关，保持同一 4K WebRTC 会话：
关/开两段解码速率分别 60.00/60.04fps，dropped/lost/freezes/PLI 都为 0。
API 点击至 running 与正确包读回分别约 4.00/2.82 秒，包含 HTTP、轮询与 SSH 采样成本，
**不是显示器光学黑屏时间**。无 TX modeset；HDR 恢复的 VPP mute 20 帧，
日志 mute-on→mute-off 约 350ms。SDR 方向先发零 DRM，约 1.5 秒后 DRM 完全关闭。
两个 OSD 持久 blank 均为 1，未解除控制台屏蔽；不将软件证据冒充用户目视确认。

正式默认内核再次点击开→关→开：关/开至正确 running 与包读回为 3.632/2.737 秒；
两段同一 WebRTC 会话分别 59.984/59.999fps，dropped/lost/freezes/PLI 均为 0。
15 次切换采样中 TX ready 恒为 1、disable_video 恒为 0、VDIN1 hdr_sdr 恒为 1，
两个 OSD blank 恒为 1；输出始终 2160p60、scaled=false。
关闭读回 BT.709、`DRM PKT not enable`，开启读回 PQ、BT.2020 与原始零静态元数据。
日志 VPP mute-on→mute-off 为 352.3ms，整个切换没有 `hdmitx_set_dispmode` 或 RX 失锁。

恢复 HDR 后保持动态图案与同一 WebRTC 会话 **600 秒**：解码 60.0004fps，
dropped/lost/freezes/PLI 均为 0。包含切换与稳定段的 650 秒只读健康监测共 651 样本，
TX modeset、RX 失锁、扫描停顿、ready 丢失全部为 0。One-KVM 的 127 个相邻约五秒
编码进度窗口为 59.989–60.007fps，整体 59.998fps，采样时 last_frame_ms 最大为 0。
这些是原始供帧/编码进度和浏览器解码端指标，不声称测到了未连接 UU 客户端的显示帧率。
测试结束关闭动态图案与浏览器，保留 HDR=true、默认 hdrdual6，服务保持 active。

common_drivers 主线合入并推送 `f3b34664e`，manager main 合入并推送 `1c6b26b`；
板上 manager 重建自该 main，前端无未提交构建改动。主仓固定相同源码版本。

离线：manager Go 全套测试、vet、前端构建；Python 运行 207 项（12 项按环境跳过，其余通过）；
浏览器回归覆盖 HDR 状态表每行、HLG 事实、pending 目标值、全局禁用和错误过滤，
总计 62 张截图。驱动 host 测试覆盖曲线选择、DRM 退场、AVI、元数据与 VDIN 双路径。
主仓离线全套运行 254 项，7 项按环境跳过，其余通过。

## 截图与证据

用户要求的七种状态各有桌面与 390px 窄屏图，目录 `logs/passthrough-hdr/ui/`：

| 状态 | 桌面 | 390px |
|---|---|---|
| HDR 输出中 | `hdr-output-desktop.png` | `hdr-output-mobile.png` |
| 已转为 SDR | `hdr-to-sdr-desktop.png` | `hdr-to-sdr-mobile.png` |
| 正在切换… | `hdr-pending-desktop.png` | `hdr-pending-mobile.png` |
| 透传开启后生效 | `hdr-preset-desktop.png` | `hdr-preset-mobile.png` |
| 显示器不支持 HDR | `hdr-no-support-desktop.png` | `hdr-no-support-mobile.png` |
| 输入为 SDR | `hdr-sdr-input-desktop.png` | `hdr-sdr-input-mobile.png` |
| 保存失败提示 | `hdr-failure-desktop.png` | `hdr-failure-mobile.png` |

同目录保留其余既有透传回归截图。真实页面开/关截图、原始 RX/TX/OSD 采样、
WebRTC 统计在 `logs/passthrough-hdr/hdr-switch-{candidate,default}*`；
构建、UART、promote、UI/Python 测试日志同前缀；板端健康采样位于
`/var/lib/vim4-kvm/hdr-switch/health.jsonl`，结束后复制到本机 logs。

## 边界

本轮物理源为 HDR10 PQ；HLG 的策略与 UI 有离线覆盖，但没有真实 HLG 源端验收。
无 HDR sink 的 UI/策略使用 mock 覆盖，没有更换显示器物理测试。
没有采集卡/光学黑屏探测器；OSD blank、TX/VPP 日志只能证明策略和链路状态，
不能替代显示器内部处理时长或最终光学颜色测量。
