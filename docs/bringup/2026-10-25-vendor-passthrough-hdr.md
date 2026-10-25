# 2026-10-25：厂商 HDR 输入黑屏、采集位深与输出域

## 结论与范围

已定位三个独立问题：用户态主动拒绝 HDR；NV21 内存仍为 8-bit 却被重新标为 10-bit，
导致 vfm_cap 安全检查丢弃全部帧；VDIN0 已将 HDR 映射到 SDR，但仍把源 HDR 元数据送给
VPP，造成重复映射。不能靠删除拒绝条件、改 TX HDR 标志冒充原生 HDR。

本轮候选恢复的是 **HDR10 输入 → VDIN0 硬件 HDR→SDR → 1:1 SDR 显示**，
包括显示器本身支持 HDR 的情况。原生 10/12-bit HDR10/HLG 输出、DRM 元数据逐值传递
尚未实现，不应宣称原任务完整通过。Dolby Vision 明确拒绝画面、声音独立继续。

默认内核保持 `5.15.137-vim4kvm-vapb1`；通过串口 RAM sysboot 一次性启动
`5.15.137-vim4kvm-hdr1` 做验证，不更改默认配置。One-KVM 源码、安装及编码偏好未修改。

## 故障取证（UTC）

- 02:50 RX 为 3840×2160、59.98/59.99Hz、YUV422、PQ；厂商字符串拼错为
  `SMPTE_ST_2048`，实际表示 ST2084。YUV422 的 `Color Depth:8` 不能证明有效精度仅 8-bit，
  厂商源码本身也指出接收器无法由该值区分 422 的有效位深。
- 老 provider 抛出 HDR 拒绝错误后丢失 input，或因 fmt_valid=0 报 no-signal；
  音频 worker 又要求视频 running，导致声音一并停止。原始错误实际文本为
  `HDR 透传尚未验证，请使用 SDR 输入`。
- `vdin0/state`：format_convert=YUV_NV21、canvas_w=3840、canvas_h=2160、
  source_bitdepth=10、color_depth_config=0。canvas 实际总大小约 12.44MB。
- 内核每帧报 NV21 10-bit、sizeimage=24,883,200，但 canvas 约 12,441,600，
  触发防越界丢弃，fmt_valid=0。One-KVM 实际 encoded=0、每约四秒超时重建，
  不能把日志中“capture started H265”当成仍在正常出流。
- 02:53 通过已审阅的 `color_depth 8` 和一次软件 RX HPD 重取信号，fmt_valid 恢复1；
  没有修改 One-KVM，UU 实际回报约60fps、sequence_gaps=0。启动脚本之前只设置
  `color_depth_support 0x1`，但 HDR 分支会无条件提升内部 source_bitdepth，覆盖该意图。

原始证据在忽略目录 `logs/passthrough-hdr/`，不含密码或用户凭据。

## 最小修复

common_drivers 候选 `bb2d0dd72`：

- `vdin_set_bitdepth()` 对 NV21/NV12 存储固定为实际支持的 8-bit，不改 422 10-bit 路径，
  不移除 vfm_cap 越界保护。板级启动同时显式 `color_depth 8`。
- VDIN0 真正执行 HDR10/HLG→SDR 配置后保存 `hdr_sdr_output`；只读 `vdin0/hdr_sdr`
  报告该事实，不读 MMIO/LUT、不用源 HDR 标签猜测输出。
- 对已经映射的帧改为 BT.709 SDR signal_type、AVI colorimetry，并清除 mastering/
  content-light/HDR10+/DRM/EMP 元数据；RX 原始 HDR 状态不改变。VPP 不再把这些帧
  当 PQ 进行第二次 HDR→SDR。
- host C fixture 编译真实函数，覆盖 HDR NV21/NV12 8-bit、422 10-bit 保留、SDR 元数据清理；
  Mac/ARM64 VM 通过，接入 CI。共享时钟与 USB EP0 既有回归通过。

manager：

- 规范化 PQ/HLG/Dolby Vision 输入类型；捕获格式失败与 RX 失锁分开，保留真实 input。
- 确认驱动 hdr_sdr=1 后才允许 HDR 映射画面输出，output.hdrToSdr=true，保持 SDR TX；
  旧内核没有该事实接口时明确报 unsupported-format，不伪造成功。
- 新状态 unsupported-format、video-error 及 reason 给出中文解释；声音可在这两种状态及
  视频 starting 时独立工作，仍对断信号、无显示器、受保护输入停止。
- 异常只在内容变化时记录，避免每秒重复同一句错误；status 仍只读，modeset 单写入者不变。
- 布局/CSS 不改。已先向用户列出“暂不支持此输入格式”“画面暂不可用”及说明文案供审阅。

## 厂商原生 HDR 路径与能力缺口

厂商 tvpath 的正常 HDR 显示依赖未被输入映射的高位深 vframe：
`hdmirx HDR data → vdin_set_drm_data(signal_type/master_display_colour/drm_if) → amvideo →`
`amcsc hdr_policy_process/hdmi_packet_process → hdmitx_set_drm_pkt`。
VPP 可按 sink 能力做 HDR bypass 或 HDR→SDR，再由 TX 发对应 AVI/DRM。

目前 KVM 与显示共享 VDIN0 的 **8-bit SDR NV21**。入口已经丢失 HDR 精度/高光，
事后加 BT.2020/PQ infoframe 既不恢复信息，也会误导显示器。因此此次没有写伪 HDR DRM，
没有将映射后的画面称为 HDR passthrough。
4K60 444 10/12bit 超出普通 594MHz TMDS 预算；将来可在 sink 明确允许时优先
422 12bit（或经验证的420 10bit），且须同时确认 vframe/formatter/实际 TX 精度。

独立原生显示+SDR采集还需另立驱动路径验证：现板 DTS 没有 vdin_export_id，
VDIN1 被驱动归为 lite，通常用于 VIU writeback，frontend 的 open/close、RX main port、
属性通知也共享。不能只加第二条 map 或启动第二个 tvserver 来承诺安全的双 RX 4K60。
VDIN1 writeback 会把 KVM 绑定 OUT 时钟、拔插和输出缩放，也不能悄悄替代现有采集。
已先向用户说明需拆分路径及可能的 KVM 接入改动，未修改 One-KVM。

## 候选启动与寄存器验证

完整 Image、匹配 DTB/模块/vfm_cap 从独立 VM 树构建，release hdr1，内核 build ID
`461d54d88a63fb6ddffcca1139e4e1836cd5b047`。候选 tgz SHA-256：
`0ece8abb3e01b43705c5c54acda00a31aa33346f44045a86f869024a6540cb98`。
候选路径 `/var/lib/vim4-kvm/hdr-passthrough/candidate/`，模块单独安装到 hdr1 目录；
资格白名单追加精确 aml_media note 哈希，同时保留旧默认和回退条目。
03:16 RAM sysboot 后约29.02秒到登录；manager 启动早于应用，首次查询 One-KVM inactive，
随后03:17:06正常自动启动，不能把早期查询当成应用失败。UDC configured。

只读单个已审阅 VCBUS 控制寄存器，不读通用 regmap 或 LUT 自增端口：

| 状态 | VDIN0 HDR CTRL / I / O | VD1 HDR CTRL / I / O | TX |
|---|---|---|---|
| 故障路径 | 0xe05e / 1 / 1 | 0xe05e / 1 / 1 | SDR |
| 修复候选 | 0xe05e / 1 / 1 | 0x1c040 / 1 / 0 | 444 8bit、BT.709 limited、VIC97、DRM EOTF SDR |

说明：VDIN0 负责唯一一次映射；VD1 HDR 核关闭 LUT、仅保留矩阵，不再双重映射。
输入 RX 保持 PQ，输出2160p60、scaled=false、hdrToSdr=true、audioState=running；
vfm_cap 越界错误计数0。该证据说明配置域一致，不是用不可靠采集卡证明色差≤2。

## 自动验证与未测项

Mac 是源机，直接运行现有时钟标记/灰阶/短音源，不更改系统默认声音、不要求用户操作客户端。
60秒网页 H.264 4K60 窗口：59.9949fps，drop/lost/freeze/PLI 增量均0，音频峰值0.1041；
呈现 p95约33.2ms、最大35ms，无>50ms间隔。回调漏418不等于编码丢帧，记录两者不同口径。
接收帧灰阶从黑到白持续递增，仅作为 KVM 映射初查，不以浏览器截图验证 HDMI TX 颜色。

OUT 软件 fake_plug 重测从重新置高到音视频均 running 为 **7.657秒**；每次采样两路
OSD blank 均1，HDR 输入、SDR 输出与声音恢复，无控制台策略解除。服务未重启。
03:22–03:23 UU 已有真实会话，sender 约60.0fps、sequence_gaps=0，RTCP累计丢包0、
回报年龄0–183ms，不能用重启前陈旧报告冒充。源灰阶三帧0、17、34…236、252，
通道差0，均单调；这不替代 HDR 高光/色域或 TX 色差校验。

最终一次 need-user 回复原话 **“画面恢复了 看起来是正常的”**；未回答 HDR 标志，
记录为未反馈，不能推定用户确认原生 HDR。原回复已读后删除，无第二次物理/目视请求。
manager 已合入推送 main `381fe28`（实现 `d397f9b`）；驱动已合入推送
`vim4-kvm-5.15@28b3dfef6`。部署 manager 为合入后 main 构建，仍保留原 manager/助手备份
`/var/backups/vim4-hdr-20261025/before.tar`。默认配置 SHA-256 核对未变，
**目前运行一次性 hdr1；重启回默认 vapb1 时本地 HDR 显示仍须候选驱动，不能宣称已永久修复。**
正式安装/设默认已另行征询，未获明确回复之前不操作。One-KVM 无源码或安装改动。

manager Python全量203项通过、12跳过，Go全量/vet通过，前端构建和48张状态截图回归通过。
common_drivers 三项离线fixture及完整内核构建通过；checkpatch为0错误、1警告
（新增Python测试未加SPDX头，按任务不添加许可头）。主仓全量244项通过、7跳过，提交前再跑。

未实现项必须保留：
原生 HDR10/HLG 10/12-bit 1:1输出及元数据逐值透传、真实 SDR 显示器、真实HLG源、
Dolby Vision输入现场拒绝、长时稳定和跨格式热插拔组合。HLG/DV分支目前只有离线测试。
