# 2026-10-23：M2 第三窗口——物理颜色对照、TX 录音与 HPD 修复

M2 的四档模式与 M0 同图、同采集卡相对颜色对照通过；物理录音测得 997.06Hz，
修复 HPD 初始化后，用户拔插能报告 disconnected / connected。通过的 M2 源码已快进
合入 `vim4-kvm-7.3@2cc04af44e3d4`，**没有正式部署，也没有更新部署锁**。
矩阵有效路由和 AVI packet bank 的逐项硬件验收尚未完成，不能宣称完整颜色管线已验收。

接续 [第二窗口](2026-10-23-display-m2-window2.md)。用户在场提供 Chrome 授权与拔插，
通过 `/tmp/codex-kernel/need-user.txt` / `user-done.txt` 单条指令握手。
原 HDR 离线工作先保存在内核 `wip/display-m3-hdr-20261023@330acaa9965cd`，
主仓文档暂存为 `display-m3 HDR offline draft before user physical window`，窗口后续接。

## 版本与一次性启动

窗口开始 fetch 的正式源码为 `9d33f6ad27898`。M2/M3 功能先 rebase 到此基线，
使用独立工作树 `/home/deepdream/src/linux-7.3-display-m3`、
`O=/home/deepdream/build/kernel-display-m3`，完整 Image、DTB、2334 个模块同次构建。

实际默认部署以窗口开始时读取的文件和 runtime 为准：内核源码 `b1300eb808f43…`，
build ID **`eeddb005df059a850853876d52ef603aa1af192b`**，M0 simpledrm。
它不是早期记录的 `7b8372b8…`；没有把旧恢复目标覆盖到当前部署。

| 候选 | 源码 / build ID | 用途 |
|---|---|---|
| 第一轮，M3 源码 + M2 DT | `74c6b03e1578b` / `81f6bb9fa2c211c8fb186a952e9e6ec1bd34ecaa` | 重现颜色映射错误与 HPD 缺失；取得物理 TX 录音 |
| 修复轮，纯 M2 | `2cc04af44e3d4` / `95dd3a0c4258ce7b347889ea638274b261d3cea5` | 四模式颜色、HPD、TX/RX PCM 与采集共存 |

修复轮 Image SHA-256 为
`89aef4d9f83e18181399e5c12f876b5f572fb5ae4b2de1b8562c5afc213efcdb`；
原始 M2 DT 为 `5f26bba298349058ccb1cfb7a525cb39871b5449085d805350d838aa2275d21f`；
带板级 MAC 的候选 DT 为 `e495f38b075aab561bc808e90c9575b8ada6b2973162aac21b5b4ea23dfe58b1`；
模块包为 `20aad8ec2123f9723f18ab73dfe23a404aad04d3dfdb904375f61f336b632a61`。

窗口始终持有两把锁，结束释放。候选使用既有 `display-once.py` 校验 / stage 和 UART
当次 RAM `sysboot`；没有 saveenv、刷 U-Boot 或改默认启动项。两轮均正常重启回默认，
启动文件、runtime、模块挂载恢复核对通过。为处理现场发现的两项错误增加一次构建，
窗口约 45 分钟，超出原先 30 分钟目标；未继续扩展 NV12/GPU/HDR 测试。

## 修复与离线验证

| 提交 | 说明 |
|---|---|
| `4a3e269bcc916` | binding 描述 formatter / 可选 OSD matrix 窄窗口 |
| `2920f646d12f1` | 明确 HDMI component pre-map=3、T7 formatter，并写入厂商矩阵系数 |
| `2cc04af44e3d4` | `drmm_kms_helper_poll_init()` 启用 bridge connector 的 HPD 回调 |

第一候选 HDMI_SETTING 读回 `0x0000000e`，缺少厂商 ENC2 所需 pre-map=3，
灰条严重偏色。修复后 `0x271b=0x0003000e`，`0x2743=0x00800408`，
与厂商 T7 的 component mapping / 8-bit YUV444 formatter 表达式一致。

HPD bridge 虽有 GPIO worker，但 connector 的 HPD enable 依赖 KMS poll 初始化。
此前缺少初始化，首次用户拔插期间 sysfs 始终 connected。补用标准 managed helper 后，
退出清理由 DRM 管理，不自行引入另一个生命周期。

三项提交 strict checkpatch 均为 **0 errors / 0 warnings / 0 checks**。
完整构建通过，M1 RMFB/退休、M2 HPD/DDC/audio/颜色、vendor PLL/VENC 参数比较、
RX/Wave5 离线回归、binding 与 DT schema 检查通过。颜色 host 测试编译执行
厂商原始 formatter、mapping 和矩阵函数，与实际驱动写入比较；这不证明该矩阵在
T7 上实际处于有效路由，下面保留反例。

## 物理颜色与 EDID

采集设备 EDID 名称 `HDMI TO USB`，33 个模式，最大 TMDS 300MHz，不声明 SCDC。
普通系统 Chrome 打开 `http://localhost:8766/`，视频为采集卡经浏览器转换后的
1920×1080 PNG。采集链路含 MJPEG/YUV422、量化范围和采集卡自身转换，不能用它
证明 HDMI 原始 RGB 精度。用户在第二次拔插反馈中明确改用同卡相对对照。

测试图案为 libdrm modetest SMPTE。每块取内部区域 RGB 中位数，避开边界与缩放过渡。
原始绝对门限（通道误差≤16、灰差≤8）在候选和 M0 上同样失败，因此保留原始失败
JSON，但不再用它判定候选错误。相对比较以 M0 1080p60 同图为参考，记录观测差，
不把事后观测上限伪装成预先设置的绝对精度门限。

| 输出 | modeset / 物理图案 | 相对 M0 七块色条最大通道差 |
|---|---|---|
| 720p50 | 通过，关闭 / RMFB 返回 0 | 1/255 |
| 1080p50 | 通过，关闭 / RMFB 返回 0 | 0.5/255 |
| 1080p60 | 通过，关闭 / RMFB 返回 0 | 0.5/255 |
| 4K30 | 通过，采集卡输出缩放为 1080p | 2/255 |
| 720p60 / 1440p60 / 4K60 | EDID 无对应模式，跳过 | 未测 |

1080p60 参考 M0 的七块 RGB 中位数为：
`(194,194,194), (196,214,0), (0,229,201), (0,249,0), (206.5,0,218), (208,0,0), (5,0,225)`。
候选仅洋红 R 为 206，其余相同。没有出现第一候选的通道错位或明显偏色。

**证据限制：** 活动时只读 `/dev/mem` 取得 pre-map / formatter 和所选矩阵窗口，
但 `0x3910..0x391d` 全零；WRAP `0x3d60…` 有既有系数，enable 也为零。
没有读到 HDMI COR 的 AVI packet bank。因此本窗口不满足“有效矩阵与 AVI 逐项
硬件读回一致”的全部条件。后续厂商审查发现 `osd_fb.c:osd_t7` 没有打开
`osd_rgb2yuv`，T7 RGB OSD 实际颜色路径涉及每层 HDR2，不能把通用 0x3910 函数
的系数一致当成 T7 路由成立。此缺口在 M3 中阻止 BT.2020/HDR 接受，见
[M3 HDMI 离线记录](2026-10-23-display-m3-hdmi-color.md)。

## TX 录音、拔插与采集共存

第一候选执行 `speaker-test -D hw:VIM4HDMITX,0 -c2 -r48000 -F S16_LE -t sine -f997`，
普通 Chrome 只选择 `BUER Digital (345f:2131)` 音频输入，关闭 AGC、降噪和回声消除。
四段独立 Opus 录音解码为 48kHz mono，取中间 1.7 秒 Hann FFT：

- 主峰均 **997.0588Hz**（FFT bin 分辨率约 0.588Hz）。
- RMS **0.39956..0.39993**，峰值 **0.57376..0.57780**。
- 987..1007Hz 带内功率占比 **99.980..99.989%**。

这是 HDMI-OUT → USB 采集卡 → Mac 录音的物理证据；不只是 ALSA write 成功。
第一、第二候选播放时 TX 与 HDMI-IN 的 PCM 均 RUNNING，48kHz、S16_LE、2ch；
ELD 正确列出 sink LPCM 2ch、32/44.1/48kHz、16/20/24-bit。
第二轮音调时页面 15 分钟录音已结束，重开晚于音调区间，**没有第二轮物理录音**。
TX 音频实现未在两轮之间变动，不据此声称完整音频连续性已验。

用户在 **19:36:48** 反馈拔下 HDMI-OUT 约 10 秒再插回。修复后轮询捕获
28 个 disconnected 样本，再回 connected；EDID 恢复 33 个模式，modetest 关闭返回 0。
首次未修复的失败样本同样保留。此次拔插没有重新测量输入采集全区间连续性。

第二候选在 TX 播放区间并行跑 30 秒 One-KVM 采集 / 解码：H.265、3840×2160，
**59.8878fps**，freeze / dropped / packet-loss / PLI 增量均 0。
第一次错误地传入脚本不支持的 `--mode=h264` 得 HTTP 400，未记为通过；重试使用现有
H.265 会话。这不是模式切换全过程的连续性统计，也没有独立 tmds-invalid 计数器增量。
本次未重新测 GPU、60Hz 翻页或 M3 NV12 video plane；历史证据不冒充本次结果。

## 回默认、清理与交付

最终重启回默认 build `eeddb005df059a850853876d52ef603aa1af192b`。实际输出：

```text
one-kvm: active
vim4-manager: active
vim4-wave5-monitor: active
UDC: configured
isolated: 0
taint: 0
protected_files: Image=true, DTB=true, extlinux=true, kernels.json=true, runtime=true
```

M0 图案作为颜色参考可见。回基线 30 秒 H.264 3840×2160 解码 **59.9903fps**，
freeze / dropped / loss / PLI 增量均 0；HID 原生方向键按下/释放各 1、绝对鼠标、
相对移动、点击、滚轮通过。dmesg 无新增 oops/BUG；现有 wireless extensions 提示保留。
恢复原 ALSA state 时 UCM 配置缺失提示已记录，不影响上述活动状态。

确认候选目录未被 mount/cmdline 引用后，仅删除本窗口的两个 build-ID stage 和
`/var/tmp/display-m2-window-3`，目录本地 fsync；不调用可能等待 CIFS 的全局 sync。
没有删除其他任务回退点。清理后根盘 **11G/29G，剩余18G，38%**；boot 剩余13M。
自己的抓帧 server 已停止，原临时页面 / server 文件恢复；两把锁已释放给等待任务。

未入库原始证据位于主仓 `logs/display/m2/window-3/`（fixed 子目录为修复轮）：
构建、UART、逐模式 PNG、EDID、寄存器、HPD 样本、录音 FFT、恢复 health 与冒烟输出。
M2 源码推送前再次 fetch，正式 HEAD 仍为 `9d33f6ad27898`，fast-forward 至
`2cc04af44e3d4`；通过源码不改变本次恢复后的实际部署。
