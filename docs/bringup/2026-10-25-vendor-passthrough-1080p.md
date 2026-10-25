# 2026-10-25：厂商 5.15 真实 1080p60 EDID 跟随

结论：用户明确回复“可以测试”后，持双锁完成真实 4K→1080p60→4K 往返。
RX、vfm_cap 帧、TX 均跟随到 1920×1080，输出不缩放；恢复原 RTK-CONTROL 后回到
3840×2160 / 2160p60。两次从发起 EDID 切换到透传 running 均约 5.85 秒，
373 次采样中两路 OSD 持久屏蔽始终为 1。没有请用户操作 Mac 或 UU 客户端。

接续 [OUT 热插拔恢复](2026-10-24-vendor-passthrough-hpd.md)。本轮仅临时改输入 EDID，
没有更新透传脚本、内核、启动项、manager 前端或 One-KVM；没有降低编码参数。
One-KVM 内部采集管线在输入重新协商时自动重建，服务没有重启，UU 同一会话保持连接。

## 授权、锁与恢复保护

- 授权：用户明确同意临时 EDID 1080p 测试；不再重复请求物理操作或客户端操作。
- `/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock ...`
  无超时取得双锁后才操作；其他 One-KVM 部署会话按同一锁协议隔离。
- 运行内核 `5.15.137-vim4kvm`；透传修复为 manager main `5cfaf7e` 的脚本。
- 原表及名字、已加载 EDID 记录备份到
  `/var/backups/vim4-passthrough-r8-20261025-001325/`，权限 0700。
  原表 SHA256：`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。
- 通过现有 `/usr/libexec/vim4-edid apply PASSTHROUGH-R8-1080P60` 加载测试表；
  finally 调用 `vim4-edid preset RTK-CONTROL`，随后等待 4K 恢复并逐字节核对原表。
  未改 JetKVM 私有配置或 manager 预设清单；结束时 selected/active/savedName 均为 RTK-CONTROL。
- 测试结束释放双锁，没有遗留板上采样进程。

## 为什么不用现有“1080p”预设直接证明

板上 `edid-decode /usr/share/vim4-kvm/edid/1080p60-sdr8.bin` 显示，虽然首选 1080p60，
HDMI VSDB 仍带 HDMI VIC 1–4，即 3840×2160 24/25/30 和 4096×2160 24；
CTA 也包含其他低分辨率/刷新率。因此其名字不能证明输入一定被限制为 1080p60。

本轮从该表构造一个仅供测试的 256 字节表，不安装成日常预设：

1. 清除 base established timings 和 standard timings，只保留首个 1920×1080p60 DTD。
2. 把另一个 720p DTD 和宽范围描述替换为 dummy descriptor，保留名称/色度等参数。
3. CTA Video Data Block 仅保留 native VIC 16；不放 CTA DTD；保留原音频、扬声器、VCDB。
4. HDMI VSDB 改为 `03 0c 00 10 00 80 1e`，不声明 HDMI VIC、3D 或深色，最大 TMDS 150MHz。
5. 重算两个 128 字节块的校验和；`edid-decode` 确认只有 1080p60 DTD 和 VIC 16，
   没有 720p、4K、其他刷新率或 established/standard timing。

测试表 SHA256：`b0a14d37512dccb56d7699c7442c0fed4515fe46dc2f76864e5c6dbfc168175c`。
准确字节保存在上述备份的 `1080p60-only.bin`，以及本机原始 JSONL 的首条 `edid_hex`；
它是刻意限制模式的实验表，不把本次源端可接受当成所有 EDID 兼容性/规范检查均已通过。

## 现场时间线与透传验证

时间为 UTC。采样约每 250ms 一次，每约一秒只读获取一次 UU 状态；EDID helper
异步执行，采样覆盖其执行期间。helper/status 路径不调用透传 tick，不额外写 TX。

| 项目 | 4K→1080p60 | 1080p60→原 4K |
|---|---|---|
| 发起 EDID 切换 | 00:13:28.082 | 00:14:34.071 |
| TX 设置目标模式 | 00:13:33.721 | 00:14:39.741 |
| VD1 on | 00:13:33.762 | 00:14:39.782 |
| 首个目标尺寸 running 采样 | 00:13:33.924 | 00:14:39.913 |
| 发起到 running | 5.844 秒 | 5.844 秒 |
| 连续 running 观察 | 60.14 秒 | 20.05 秒 |

这给出控制链恢复/黑屏窗口的上界，采样分辨率约 250ms；没有光学测量屏幕黑场持续时间。
watch 仅各做一次 modeset，内核窗口也只有两次 `hdmitx_set_dispmode`，各对应一次真实输入变化。
没有用周期重设碰运气恢复。

1080p 稳态的真实数据：

- RX Hactive/Vactive=1920/1080、Frame Rate=5998（59.98Hz）、YUV444、SDR。
- vfm_cap signal_info width/height=1920/1080，8-bit NV21，sizeimage=3112960。
  不存在先把输入采集成 4K、再用缩小输出冒充 1:1 的中间尺寸。
- TX sname=1080p60hz、h/v active=1920/1080、h/v_freq=67500/60000、TMDS=148500，
  attr=444,8bit、ready=1；VD1 axis=`0 0 1919 1079`。
- manager state=running，input/output 均 1920×1080，output.refreshHz=60、scaled=false。
  这里 1:1 指几何尺寸不缩放，不声称 NV21/YCbCr 转换是逐字节透明路径。
- 60.14 秒收到/交付/显示均推进 3609 帧，约 60.006fps；frames_dropped 始终为 0。

恢复原表后的真实数据：

- RX 和 vfm_cap 均回到 3840×2160；RX 约 59.98Hz，8-bit NV21 sizeimage=12443648。
- TX=2160p60hz、3840×2160、YCbCr444 8-bit limited、ready=1，manager running、scaled=false。
- 20.05 秒收到/交付/显示推进 1203 帧，约 60.011fps；frames_dropped 仍为 0。
- 原 EDID 字节及 SHA256 完全恢复，helper activeKnown=true、jetkvmSynced=true。

## 控制台遮挡与 KVM / UU

373 次采样里 osd0/osd1 的持久 blank 全部为 1，透传 state error 全部为空；
最后 DRM state 中两路 OSD enable 均为 0，包括 fbcon 所在 osd0。
结合驱动每次 atomic-check 强制禁用的既有路径，确认本次重新协商没有重新启用控制台图层。
这不是用户额外目视/逐帧录像确认；本轮按要求不再请求用户操作。

One-KVM PID 58916、透传 PID 77955、manager PID 50691 前后不变，均 active、NRestarts=0。
UU 始终 online、connection_count=1，同一 Session，ICE/WebRTC connected、H.265；
原尺寸、60fps、20000kbps 设置没有改变。

EDID 会使输入真实失锁，两次都出现 One-KVM 的 `HDMI capture stalled`/capture timeout 日志，
随后原服务自动重建对应尺寸的 H.265 管线；不把这段写成无中断连续视频。
UU 发送间隙最大分别为 4.159 秒和 4.210 秒，含切换的发送窗口短暂降至 27/17fps，随后恢复。
排除跨切换窗口后的稳态发送约为：1080p 59.981–60.014fps；恢复 4K 后 59.997–60.001fps。
UU 接收反馈累计丢包与 NACK 均为 0、FIR=0，PLI 随两次恢复从 3 增至 7。
官方客户端自报 1080p received/decode/render 均约 59fps；恢复 4K 后首个窗口约 58fps，
不能把发送端 60fps 自动写成客户端每帧均 60fps。没有重新开展十分钟 UU 性能验收。

厂商 TX 仍有既有的 `Should run disable_mode before enable new mode` 日志；
两次之后均恢复目标模式，没有新增 Oops/panic；日志有文字不等于 OSD 显示了文字。

## 证据、范围与遗留项

本机 `logs/passthrough-515/`：`r8-baseline.log`、`r8-edid-follow.py`、
`r8-edid-follow.jsonl`（PASS，373 次采样、完整测试 EDID、服务与 UU 前后状态）、
`r8-1080p-capture.log`、`r8-kernel-services.log`、`r8-restored-live.log`、
`r8-final-planes-services.log`。这些是本机原始证据，不冒充已随源码推送的附件。
本轮仅提交文档，不需要新的驱动、manager、One-KVM 构建或部署。

已完成真实 1080p60 1:1 跟随与恢复 4K；尚未完成真实 1080p 十分钟/长期稳定性、
连接状态长期无黑屏、HDMI IN 物理拔插、音频直通、管理面板实际开/关动作。

对用户原问题的回答：Mac 报告“1080p”但 RX 仍为 3840×2160 时，是 Mac 桌面逻辑缩放后
仍发送 4K 时序；透传显示器继续 4K 正确。只有实际输入时序变为 1080p，输出才跟随为 1080p。
