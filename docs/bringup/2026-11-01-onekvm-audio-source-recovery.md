# 2026-11-01：One-KVM 音频源变化与稳定设备名修复

用户手测报告：7.3 切换 HDR 出现 `Audio device lost: hw:0,0`，音频输入列表也与
5.15 不一致。限定修改 One-KVM，不动内核、其他应用或 M6，不播放测试音或额外录制。
**修复已独立复审、部署；真实 API 和现有采集健全检查通过。后续用户明确授权直接合入并停止，
见[合入记录](2026-11-01-p0-hdr-final-merge.md)；这不代表用户已经确认 HDR 切换/听测通过。**

## 固定来源与根因

- 仓库 `One-KVM`，分支 `p0-5-native-hdr`。
- 基点 `50f0b4d433c0ebb8c83f806f49084622547afe99`。
- 修复终点 `dae5089fc59aa069399539fa304412c37f0c3f08`，已 push。
- 独立只读复审 `/tmp/herdr-workers/review-audio-source.result.md`：无乘积 ≥5 缺陷。

修复前现场 API：列表 `hw:0,0`、配置 `hw:VIM4HDMIRX,0`、恢复后 status `hw:0,0`。
UTC 12:07:34、12:08:00/29/40 的 HDMI link readiness revoked 后，分别出现
device_lost 告警，再约 1.2 秒恢复采集。证据是日志关联，不将每次隐藏的 capture 内部状态
都声称为已经实板跟踪的 SourceChanged。

代码根因：capture 已区分 `CaptureState::SourceChanged`，streamer 却在主循环及
接收超时出口将它合并为 Error，recovery 因此发送 DeviceLost 告警并增加故障退避。
枚举只返回数字卡号，恢复首选的 named ID 匹配失败又改回数字卡号；忙碌设备匹配也不一致。

修复保留独立 SourceChanged，经源稳定资格检查后打开同一输入，不枚举替换到别的麦克风。
真实 control/PCM 错误仍升级为健康错误和 DeviceLost，并按 1/2/4/8/16/30 秒退避。
列表、显式保存、选择和恢复使用实际 ALSA card ID，旧 `hw:N,M` 只解析实际 N 对应声卡并
保留 M，不假定 N=0 是 HDMI。存在但忙碌或暂不能探测的输入保留，未知能力返回空数组。

## 离线验证与边界

- VIM4 全量 Rust lib：830 通过、4 忽略；日志 `build/p0-5/audio-fix-final-tests.log`。
- 音频 53 项通过；补充后的 recovery 9 项通过，含真实 worker 遇到不存在的 ALSA control、
  虚拟时钟下 1000/2000ms 退避；日志 `audio-fix-test.log`、`audio-fix-build.log`。
- streamer 两个出口、清理后原因保留、重复源变化、恢复失败升级、取消后迟到错误、
  数字卡号指向 USB 时不迁移为 HDMI 均覆盖。
- 重复源变化测试在硬件打开前用 disabled 配置结束；PCM 失败升级测试直接调用失败处理。
  它们是软件回归，不能替代连续实板源切换或真实硬件 PCM 失败验收。
- 独立 reviewer 实跑上述音频 53 项与数据库跨内核兼容 1 项，全部通过。
- ARM64 Ubuntu 部署助手 unittest：37 通过（需提供工作区 `VIM4_BOARD_DIR`），日志
  `audio-fix-helper-linux.log`。初次容器缺少兄弟 board 目录、macOS 运行 Linux 助手失败均保留日志，未算通过。
- 非 VIM4 `cargo check --lib` 在既有 ARM RKMPP FFmpeg SDK 缺失
  `AV_HWDEVICE_TYPE_RKMPP` 处失败，不能标记通过；不扩展修改硬件编解码依赖。
- release 增量构建通过，2m31s；未构建内核或修改前端资源。
- 主仓完整 unittest：451 项、15 跳过，其余通过；日志 `audio-fix-root-unittest.log`。

AS-1（2×2=4，仅登记）：旧缓存仍为数字卡号时，不带 device 的部分 PATCH 响应可保留数字名，
GET/枚举已为稳定名。现有网页提交完整字段，本次实际配置已为 named ID；按复审要求本轮不扩改。

## 封包与最小部署

候选 `build/p0-5/one-kvm-audio-dae5089-r1.tar.gz`，SHA256
`70e961e33abb57f0362b56e1b4f6f2455c7d37ceb3ab0143b4a27a21621ae12d`。
程序 SHA256 `a7942537db1504a57969011cfc5df8ab0529eaa744c52328ba38d6d7176e1e8a`。
安装到 `/opt/vim4-kvm/one-kvm-audio-dae5089/one-kvm`，只替换原启动器中 uhd6 的
One-KVM 程序路径一行，保留 kbase 包装器及 r14e 私有 GStreamer 插件路径。
当前真实启动器 SHA256 `80d366ce7786329fd73a9f671174b3c8bcd42d3089e54b26a5f71b221c604f5c`。

FIFO 票据 `04cd45f456a948cd9cbc184f1900ce93`，持票 **69.116 秒**，已释放。
仅重启 `one-kvm.service`，未重启板子、HDMI、管理器或 gadget，未向 M6/M4 发 HID。
备份 `/var/lib/vim4-kvm/before-onekvm-audio-1793537529771486683`。
`/etc/vim4-kvm/one-kvm-audio.json` 及 runtime-build 的 overlay/commit/程序哈希记录实际新身份。

原 `/opt/vim4-kvm/hdr10-r14e` 全部 40 文件与封存收据逐项不变；内核仍为正式
`f951e2d24d32d5df0e701e7c355b3db4c91eaf74` / uhd6 / GNU ID
`48106f6f9fb09b12d1eaf6a5fe91953dba53d9cb`，默认 FullKvm、kbase；/lib 符号链接保留。
MAC generator、原 r14e 收据、extlinux 哈希不变，MAC 仍 `c8:63:14:74:70:0d`。
5.15 程序与启动选择路径不变。完整先前身份见
[r14e 安装](2026-11-01-hdr10-r14e-installed.md)、[MAC 修复](2026-11-01-ethernet-mac-handoff.md)。

## 实际自动检查与手测交接

| 检查 | 实际结果 |
|---|---|
| 运行程序 | 服务 cgroup 中真实子进程 PID 6222，/proc/exe SHA 匹配新程序 |
| 枚举 / GET / status | 均为 `hw:VIM4HDMIRX,0`；列表 `HDMI input (in use)`，能力未知为空 |
| 旧配置正常入口 | 实际 PATCH `hw:0,0` 保存与 POST 选择成功；重载后稳定 ID 未漂移 |
| 用户设置 | enabled=true、quality=high、原设备恢复；全量 config GET 同步一致 |
| 数据库 | 只读 SQL 核对仍为 `hw:AMLAUGESOUND,0`，沿用原跨内核可移植 HDMI 别名；7.3 缓存解析成 VIM4HDMIRX，非改错声卡 |
| 现有采集 | 60.003s、2,879,040 帧、XRUN=0，PCM RUNNING，hw_ptr 0→2,962,560 |
| 告警 | 本短窗 journal 无新增 Audio error / DeviceLost；未主动制造物理源变化 |
| 服务 / USB | One-KVM、manager、HDMI、gadget active，UDC configured；taint=4096 为既有 kbase 外部模块位 |

本次源为数字静音（非零样本数 0），没有订阅者；不证明远端声音质量、实际 HDR 切换后的
音轨恢复或连续多次物理源变化已通过。没有加入软件注入后门或额外录制。
源变化/真实错误升级的自动证据来自离线生产代码状态链路回归，须与实板现有状态观察分开。

手测入口 **http://192.168.50.210** → One-KVM → 音频输入选择 HDMI input。
请用户正常播放自己的内容并切换 HDR，确认不再误报设备丢失、切换后声音恢复、设备选择不漂移。
原“用户确认前不合产品主线”的限制由上述后续明确授权更新；听测仍未记录为通过。
原 r14e 的 Pi/kbase/UU/CMA 等未验边界不因本音频修复改变。

原始证据 `logs/one-kvm-audio-source-fix/`：before-api.json、before-journal.txt、
source-transition-journal.txt、installed-api-sanity.json、saved-database-audio.json、
before-identity.json、after-identity.json。部署 stdout 为 `build/p0-5/audio-fix-window.log`。
