# 2026-10-25：厂商 5.15 HDMI 音频桥与 KVM 共存

## 摘要

厂商 5.15 没有暴露可直接使用的 HDMI RX→TX 硬件音频回环。本轮实现独立低延迟
ALSA PCM 桥，经 EXTN 捕获、SPDIF 播放至 HDMI TX；不抢占 One-KVM 的 TDM-B 捕获，
不修改其视频/音频代码或编码设置。支持立体声 PCM 44.1/48kHz，16-bit 本地输出；
不支持压缩音频或多声道。manager 的声音偏好和真实工作状态分离，音频故障不阻塞视频。

部署在原 `5.15.137-vim4kvm`，不改内核、默认启动项、源 EDID 或 One-KVM 安装。
本轮诊断发生一次错误读寄存器导致的自动重启，详见
[事故说明](2026-10-25-audiobus-read-abort.md)，不得隐藏或归因给并行 UU 会话。

## 路由调查

源码基线 common_drivers `746f93e09`，主要依据：

- `sound/soc/amlogic/auge/card.c`：`HDMITX Audio Source Select` 只有 Spdif、Spdif_b、
  Tdm_A/B/C，没有 HDMI RX 输入项。
- `tdm_hw.c` 的 `i2s_to_hdmitx_ctrl` 选择 TDM 输出时钟/数据；FRDDR 播放消费内存 DMA，
  不能因名称出现 RX/DDR 就推断存在免内存回环。
- `HDMIIN Audio output mode` 是接收器的 SPDIF/I2S/TDM 输出选择，
  `Audio spdif_arc source` 是反向 ARC；loopback 模块用于采集/AEC，不等于 TX 直接转发。
- 板端 `AMLAUGESOUND`：DEV=0 为 One-KVM 的 TDM-B 输入；DEV=6 为独立 EXTN/FRHDMIRX
  捕获；DEV=1 为 SPDIF 播放。EXTN 在 open 时根据输入选择申请接收器 IRQ，因此必须先
  把初始无效选择 0 初始化为 FRHDMIRX 8，不能先 open 再改。

结论限于已提供的驱动接口，不能断言芯片物理上不可能实现硬件回环；目前不为该目标
引入未验证驱动补丁。选用一个 ctypes/libasound 进程直接 readi/writei，避免
`arecord | aplay` 的管道/额外缓冲，也不依赖本机 alsaloop 的异常协商行为。

## 实现与所有权

`vim4-manager/deploy/vim4_passthrough_audio.py` 随 manager 包安装，音频单元由视频服务
Wants 启动、PartOf 停止；独立 flock 保证只有一个音频协调者。PCM 子进程与视频模式
写入进程分离，后者不等待音频读写；status 不写硬件。

路由为 `FRHDMIRX → EXTN/TODDR → PCM 桥 → FRDDR/SPDIF → HDMITX`。
两个端点独占取得后才租用输出控件；不打开 DEV=0。仅在 ASRC 原本属于 FRHDMIRX 时
旁路它以使用原生采样率；TDMIN_B 等其他 ASRC 所有者不改。保存到
`/run/vim4-passthrough/audio-before.json`，退出时仍持有 PCM，再比较恢复原控件；
异常退出后也须重新取得两个端点才能清理，不能覆盖其他程序的路由。
EXTN 的 0→8 初始修正保留，不恢复到不能工作的 0；已有其他合法输入不抢占。

固定 S16_LE、双声道、256 帧周期、2048 帧缓冲、1536 帧启动阈值；必须协商精确整数周期，
否则拒绝运行，避免厂商 DMA 环非整数回绕的周期爆音。44.1/48kHz 不做软件变速。
启动/停止做短渐变；采样率变化两次确认后重开。端点忙、子进程退出、心跳停滞、异常
清理失败均隔离处理并退避重试，不退出视频服务。

只接受接收器报告的稳定立体声 PCM 且显示器声明对应采样率；无音频能力、AC3/non-audio、
多声道和其他速率时停止本地播放，保留声音偏好，不把压缩数据当 PCM 噪声输出。
实际压缩流、多声道、无音频物理显示器尚未现场注入，仅离线覆盖拒绝分支。

## 延迟口径

- 48kHz 稳态 ALSA `captureDelayFrames=0`、`playbackDelayFrames=1280`，队列约 **26.67ms**；
  44.1kHz 同为 1280 帧，约 **29.02ms**。这不是端到端扬声器测量。
- 加上接收器 FIFO、分块与 HDMI 音频打包，板内音频暂估约 **30–40ms**，显示器内部处理另计。
- `TVIN VIDEO DELAY` 读到 16–32ms，对应厂商 `vframe_walk_delay`，是完整 VDIN 帧就绪
  到 video toggle 的排队，不包含前面的采集与后面的面板。按 60Hz 一帧采集约 16.7ms、
  输出扫描 0–16.7ms，板内视频粗估 **33–66ms**（另有测量抖动与显示器处理）。
- 因此音频相对视频粗估约 -36 至 +7ms；±45ms 只是当前量级估算，尚无扬声器/光电
  同时采样，不能声称已客观证明目标。测试源的 440Hz 短脉冲与画面标记共用 Mac host clock，
  仅供最终主观确认，不把软件时钟一致当物理同步实测。

## 自动验证

时间均为 2026-10-25 UTC，证据在忽略目录 `logs/passthrough-515/audio-*`。

- Mac mini 就是 HDMI 源，本机直接选择唯一 `RTK UHD HDR` 音频设备播放测试音，
  不更改系统默认输出、不要求用户操作客户端。独立 EXTN 录音峰值 3277、RMS 约 2317，
  对应幅度 0.1 的 440Hz；原生 44.1kHz PCM 桥过零频率约 439.6Hz。
- RX ALSA 48kHz/两声道/PCM/stable；TX packet dump 的 Audio InfoFrame、ACR N=6144
  与 PCM 通道状态一致，TX 选择 Spdif，视频保持 2160p60 YCbCr444 limited。
- 48kHz 桥运行时网页 WebRTC 解码约 439.45Hz、峰值 0.1003，400 个音频包零丢失；
  视频 479 帧、零 drop/零 freeze。436 个 concealedSamples 包括启动阶段，不能写成零隐藏样本。
  最终 48kHz 回归为峰值 0.10077、439.45Hz、音频 400 包零丢失/零 concealed，
  视频 479 帧、零丢包/零 drop/零 freeze（八秒短窗口，不代表长测）。
- API 声音 off/on、视频 off/on 保留声音偏好、实际浏览器声音开关保存/回显通过。
  屏蔽音频单元注入失败返回 HTTP 500、`透传控制服务未响应`，无 sudo/私有路径泄露，
  不保存失败的新偏好，视频继续。恢复后声音重新运行。
- 现场还发现只读状态持有同一 mutex 时 POST 被 TryLock 错判为“另一项操作正在进行”；
  新增独立写入锁，设置等待短状态读取，只拒绝真实并发写入，离线调度/竞态测试覆盖。
- OUT `fake_plug` 低→高，两秒量级掉线后自动恢复视频与声音：从重新置高到双 running
  **8.996s**；IN `debug hpd0/1 1` 重测为 **4.153s**。每约 0.7s 采样一次，
  两路 OSD blank 始终为 1，视频与音频服务均未重启；采样证据不能代替逐帧物理观察。
  断开期间停止本地 PCM，插回后重开并恢复原 4K60 YCbCr444。
- 杀死 PCM 子进程故障注入后自动重建，首次新进度在 **7.510s**，视频保持 running；
  音频协调服务和 One-KVM PID 不变，无服务级重启。
- Mac CoreAudio 原生输出 48→44.1→48kHz，服务自动改用原生速率；44.1kHz 实测
  峰值 3277、RMS 2298.25、过零 439.57Hz、TX ACR N=9408，恢复 48kHz 后 N=6144。
  全程输出仍为 2160p60、未缩放；最后 Mac nominal/板端实际输入均恢复 48kHz。
  这不覆盖物理拔线听感或任意采样率/编码格式组合。

## KVM 限制与未验证项

44.1kHz 输入下，**桥已经关闭时** One-KVM 网页仍把 440Hz 解码为约 477.54Hz，
音频包 365、零丢包，视频 475 帧、零 drop/freeze；与 `48000/44100` 比例吻合。
这是厂商 5.15 One-KVM 固定 48kHz 采集的既有变调，不是本桥抢占造成；本轮没有为掩盖
该问题而修改 One-KVM。不能把“两个采集端点可共存”写成“所有源速率的 KVM 音频保真通过”。

事故后 UU 云端 online、客户端 sessions=0，不能宣称实际 UU 客户端恢复或端到端音频通过。
未绕过 macOS 辅助功能权限，也未请用户操作客户端；共享 WebRTC 音频仅由网页自动验证。
待办：UU 真实会话音频、One-KVM 44.1kHz 保真、长时无爆音、物理插拔听感、
扬声器/光电客观 A/V 延迟、多声道/压缩格式（当前明确不支持）。

## 部署与管理器

部署前备份 `/var/backups/vim4-passthrough-audio-20261025/platform-manager-before.tar`；
仅安装 manager、助手/模块和 systemd 单元，未改 One-KVM、内核或默认启动项。
新镜像/组件包同时安装 libasound2t64、alsa-utils 与音频模块、单元。
在「HDMI 输出」开启透传后打开「声音」，保存偏好为 `audio:true`；`audioState` 单独回报
实际的 off/starting/waiting/running/unavailable/error，无音频不应误报“输出中”。
页面布局/CSS 不变；已预先列出新增状态文字“正在连接声音…”与“声音暂不可用”供用户审阅，
失败提示复用已有中文“透传控制服务未响应”，底层详情留在 journal。

## 检查与交付

manager 实现提交 `f719c40`、`989f98f`（`passthrough-5.15-audio`）。
Python deploy 全量 197 项通过、12 项环境相关跳过；Go 全量与 vet 通过，
Passthrough 专项 race 通过；前端构建及浏览器 40 张状态截图回归通过。
主仓全量 243 项通过、7 项跳过。已部署的助手、音频模块与 manager 二进制哈希
和本地验证产物一致；持久偏好与实时状态均为透传/声音开启，四个相关服务 active。

唯一听感确认请求已通过 `/tmp/codex-kernel/need-user.txt` 发出，测试源三分钟后自动退出；
收到 `user-done.txt`，用户原话为 **“有声音”**，未反馈异常；没有逐项明确回答爆音或同步，
因此只登记“显示器可闻通过”，不能写成无爆音或 ±45ms 同步已经确认。回复已读后删除，
共享请求文件也已清理，没有再次请求用户操作。
manager 已合入并推送 main `8a1a456`，随后从该提交重建、安装正式 main 二进制；
音频无 common_drivers 修改，无需构建或安装新内核。
主仓打包与 manager 固定版本更新为 `259caa8`，避免 locked 构建取到没有音频模块的旧源码。
01:41 UTC 最后复核：manager HTTP 200，manager、One-KVM、视频/音频服务均 active；
偏好 `enabled:true,audio:true`，视频/声音双 running，输出 2160p60 YCbCr444 limited。
已装 manager 的 Go VCS 信息为 `8a1a456`、`modified=false`，二进制 SHA-256
`7a283ae0e4a7fb5c9e67c1b2c2d46891461c5f313d7795ac7a4bb0eb745e8582`。
01:28 UTC 起内核 `hdmitx_set_dispmode` 为 0 次（包含采样率回切和最终 manager 重启），
不能据此宣称声音已完成长时听感验收。测试源已自动退出；临时隧道、Vite 已停止，
完成提交后释放双锁，保留生产音频服务及用户开启偏好。
