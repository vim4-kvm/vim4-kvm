# 2026-10-23：M0 音频复核与正式部署回退

基线使用直接 AudioData 的严格检查通过，两段 44.1 kHz 稳态及采样率切换无失败窗。
候选九类功能回归通过，但最终健康检查发现新增 ASoC -67 日志，严格门禁回退。
本条记前三轮回退；后续见[第四轮](2026-10-23-display-m0-r4.md)。
布局、时钟、电源、内存及首轮恢复证据见 [M0 实验](2026-10-23-display-m0.md)。

## 音频判定

`final-regression.py` 原音频项调用 `browser-rates.py → browser-audio.mjs`，仍是旧
WebAudio Worklet；`final-manager-check.mjs` 只检查 manager 页面，不包含音频观察器。
本轮仅替换音频入口为 `tools/one-kvm-audio-continuity.mjs --exclusive --headed`，
其余回归的夹具和判据保持原样。新工具直接读解码音轨及标签页输出的 AudioData，
严格 step/RMS/频率阈值保持不变；观察器假阳性机制及对照见
[P1 第二轮](2026-10-22-p1-browser-audio.md)。

音源与采样率工具继续用 prepare 固定哈希的快照；失败也先设置 48k、等待板端 RX
确认 48k/2ch LPCM，再停止本任务音源。新增离线测试覆盖采样失败、恢复失败的清理。

首次新工具检查返回 1，但不能作为纯音频判据：05:13:11 UTC 外部 UU 接入时
One-KVM 关闭本地 H.264 会话（`After close_all_sessions`），05:13:18 重建 H.265
会话。同期直接音轨/标签页测到静音，SSRC 改变；后续只有标签页数据。
原日志 `logs/display/m0-r2/baseline-audio.log`、`baseline-audio-journal-early.log` 保留，
该组作受干扰失败，不计通过，也不归入 Worklet FIFO 假阳性。

UU 断开后独占重跑，在 baseline build ID `3a61b75bccf8c46e9411dee92928999884bbfc7f`
上完成 48→44.1→48→44.1→48 kHz，每段 30 秒；切换后五秒起取 100ms 稳态窗：

| HDMI kHz | 直接音轨窗口数 | 标签页窗口数 | 失败窗 |
|---|---:|---:|---:|
| 48 A | 252 | 252 | 0 |
| 44.1 A | 253 | 253 | 0 |
| 48 B | 252 | 253 | 0 |
| 44.1 B | 253 | 252 | 0 |
| 48 C | 252 | 253 | 0 |

实际非 headless Chrome；无 legacy Worklet、无 trace、无额外 Opus 解码 sink。
每段两端点齐全且无观察器错误，输出 `AUDIO_RESTORED_48000`、`CHECK_PASSED audio`。
日志 `logs/display/m0-r2/baseline-audio-2.log`。命令：

```sh
AUDIO_RATES=48000,44100,48000,44100,48000 AUDIO_SECONDS=30 \
  /usr/bin/lockf -t 15 /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u packaging/kernel-edge/final-regression.py run \
  --destination build/display-m0/baseline-regression --id audio
```

本轮新观察器没有复现首轮 44.1k 失败，旧 Worklet 数据不再作为产品播放回归证据；
没有旧窗对应 trace，不能反推每个历史失败都已证明属于同一 FIFO 事件。
软件渲染回环也不能代替物理扬声器或外部 DAC 验收。

## 正式配置与发布范围

内核 `vim4-display-m0` 的 `47878a0c611d1e1deb3699c4f225963a37a218c0` 是正式分支
`0196fe22ecf0104d96b7ef0fa497ca2317bd20bb` 的直接后继，差异仅 DTS Makefile 和
独立 display-m0.dts 两个文件，没有 vdec 改动；本轮门禁未全通过，不快进正式分支。
VM 主工作树不修改、不切分支。用户态仍为 One-KVM `382efb70e7ebb`、manager `4ea748426935`。

本板候选安装选择 `amlogic-t7-a311d2-khadas-vim4-display-m0.dtb`，落到
`/boot/edge/vim4.dtb`。没有把 generic/audio-test DTS 改成静态显示布局；它仍是匹配
当前 pd-handoff、HDMI 已连接且无 MIPI 的专用 profile，不是任意启动环境的默认值。
`package-final.py --dtb amlogic-t7-a311d2-khadas-vim4-display-m0.dtb` 支持显式选取，
缺省仍为 audio-test。候选完整配置存 `build/display-m0/final.config`；正式 uhd1.config
及 sources.toml 保持基线版本，显示配置继续用独立 fragment。

复用首轮已完整构建并上板的同一匹配 Image/DTB/完整模块包，没有把不同构建混装，
也没有为了本轮重新编译相同源码。release `7.3.0-vim4kvm-uhd1+`，build ID
`f483ea42fee88be39ea67c43478638be67334d6e`，模块 2334 个，保留 BTF。
配置 SHA256 `bca0e45df6eb43177bd82f251b4133c0468dd05195b7bae8ed8f639ba21f971c`；
Image SHA256 `4906f02df730a28d78d2f877542ea2f5611d2d98d2e53bfdfa6e9c9973d8a77d`。
其余完整哈希在 `build/display-m0-r2-2.bundle/{manifest,runtime-proof,deployment}.json`。

正式窗口使用新增显式选项：`stage --kernel-only --framebuffer-console --require-all-checks`。
tty0 写入 FullKvm 后与匹配 Image/模块一起登记，串口仍是最后一个 console；不修改
其他启动项，不绕过 manager 的启动参数匹配。任一回归或最终健康检查失败均回退，
旧 bundle 的非关键项策略保持原样。离线测试覆盖音频失败不得 finalize 的事务边界。

```sh
AUDIO_RATES=48000,44100,48000,44100,48000 AUDIO_SECONDS=30 \
  python3 -u packaging/kernel-edge/final-window.py window \
  --bundle build/display-m0-r2.bundle \
  --backup /var/backups/vim4-display-m0-retained \
  --logs logs/display/m0-r2/final-window \
  --archive-remote-to /var/tmp/vim4-pre-display-m0-retained --execute
```

final-window.py 自行持 board/heavy 双锁，备份六文件到 Mac 并比较 SHA256 后才安装。
初次启动身份、全部模块身份与健康检查通过，`NEW_WARNINGS []`、taint=0。
普通 Chrome 复用用户的摄像头授权与 8766 服务，实际开机截图
`logs/display/m0-r2-boot-console.png` 显示 `Ubuntu 24.04.3 LTS Khadas tty1 / Khadas login:`；
这是系统 getty 自然输出，没有写入测试标记。完整日志 `logs/display/m0-r2/final-window.log`。

首个正式窗口在 raw 模式8（1440×900）单次 S_FMT 返回 EAGAIN 后自动回退，
输出 `BASELINE_RESTORED 3a61b75b…`；0–7档已通过，未执行后续八类。
原日志及 source/RX 诊断保留，不删除失败。驱动时序查询允许在计数变化、链路切换
期间返回 EAGAIN，夹具没有对 S_FMT 重试；目前不能证明该次失败的具体根因。
恢复基线后，以完全相同判据跑完整19档全部通过，并验证真实 HID。
对照日志 `logs/display/m0-r2/baseline-video.log`、`baseline-hid-after-rollback.log`。
第二个候选窗口另用 `build/display-m0-r2-2.bundle`、
`/var/backups/vim4-display-m0-retained-2`、`logs/display/m0-r2/final-window-2`，
先前远端暂存归档为 `/var/tmp/vim4-display-m0-retained-failed-1`；没有改矩阵或放宽判据。

## 会话中断与恢复

第二窗口通过 hdmi-modes、h264、h265、4k60 后，API 503 导致父进程终止；最后输出
`CRITICAL_HEALTH_VERIFIED f483ea42…`。候选仍在运行，锁已释放，音频子进程成为孤儿。
孤儿输出不作为发布门禁结果。续跑先核对原 bundle、原基线备份和当前构建身份，
不重新执行 save/install，避免把候选误备份成基线；保留前四项通过记录，重新执行
audio、hid、media、gpu、manager，每项后调用原 Window.verify，最后 health/finalize。
监督进程通过 `Popen(start_new_session=True)` 脱离会话，stdin 为 DEVNULL，日志落盘，
全程由它持有 board/heavy 双锁。日志 `logs/display/m0-r2/final-window-2-resume.log`，
状态在 `final-window-2/resume-status.json`；失败路径调用原 Window.rollback 并测实际 HID。

这不是 SIGKILL/主机关机自动恢复机制。进程异常消失后先只读确认当前 build ID、
服务、进程树和锁占用，勿并行启动第二个窗口，也勿覆盖原备份。不能确认完整通过时，
使用对应原 bundle/backup 回退（logs 必须是尚不存在的新目录）：

```sh
python3 packaging/kernel-edge/final-window.py rollback \
  --bundle build/display-m0-r2-2.bundle \
  --backup /var/backups/vim4-display-m0-retained-2 \
  --logs logs/display/m0-r2/manual-rollback --execute
```

该入口自行持双锁，restore、正常重启、verify-restore 核对 3a61b75b…、完整模块、
启动参数与文件身份；还应另持双锁运行实际 HID 检查。SSH 不返回时停止重复重启，
按串口/OOWOW 恢复流程处理，不能宣称回退成功。

## 续跑结果与停止发布

`regression-results.json` 九项均 passed：19档 HDMI、H.264/H.265 往返、4K60，加上
本次重跑 audio、真实 HID、只读虚拟介质/主机 eject、GPU 渲染与 runtime-resume、manager。
候选直接音轨/标签页稳态窗口依次为 253/253、253/252、253/253、253/252、252/253，
五段均零失败窗、无观察器错误，稳态丢包/隐藏样本均为0；最大 step 为0.00586/0.00639。
工具按原设计排除每次切换后5秒，不能据此宣称瞬时无缝切换或物理扬声器通过。
摘要 `logs/display/m0-r2/candidate-audio-summary.json`，完整输出 `final-window-2/audio.log`。

最终 health 的模块身份、manager、failed units、taint、hwrng、IR 注册、风扇、GPU
governor、PD 均通过；IR 未用遥控器实按。唯一失败项 new_warnings：

```text
t7-hdmirx fe398000.hdmi-receiver: ASoC error (-67): at snd_soc_dai_hw_params() on t7-hdmirx-audio
 TODDR-t7-hdmirx-audio: ASoC error (-67): at __soc_pcm_hw_params() on TODDR-t7-hdmirx-audio
```

持久 journal 定位两条日志在 **05:36:55 UTC、启动后350秒**，早于本次05:53续跑，
不是新观察器的 Worklet 假阳性。同期应用先报 HDMI audio format changed，重建 PCM
时返回67，随后报 source not ready。驱动 hw_params 会传播 read_audio 的 ENOLINK，
也会在两次格式资格确认不一致时返回 ENOLINK；无同步 RX 快照，不能确定具体分支，
也不能归因于 M0。后续应在基线对照音源启动/格式切换时的 AIF/ACR、audio_generation、
link_ready 与 PCM 重开时序，再决定资格等待或错误处理；本轮不忽略错误或放宽门禁。
证据 `final-window-2/{health.json,resume-failure-board.log,audio-hwparams-previous-boot.log}`。

严格健康断言失败后没有 finalize，使用原 Window.rollback（restore/reboot/verify-restore）
自动回退，输出：

```text
BASELINE_RESTORED 3a61b75bccf8c46e9411dee92928999884bbfc7f
active
active
configured
0
CmaTotal: 524288 kB
CmaFree: 505208 kB
```

真实 HID 再测通过 keyboard down/up、绝对/相对鼠标、点击、滚轮；证据
`final-window-2/{baseline-after-rollback.log,hid-after-rollback.log}`。状态 rolled-back，
监督进程退出、双锁释放。正式内核仍0196fe22ecf0，未推送47878a0c；sources.toml、
workspace.toml、正式配置保持基线。候选开机 getty 截图为 `logs/display/m0-r2-boot-console.png`，
不是保留部署截图。离线189项测试通过、5项跳过；diff 检查通过。

## 4K 及通用 handoff 的已知限制

4K 显示器实物尚未复测，不能宣称 4K 显示已验收。U-Boot 源码复核：
`cmd_osd.c:do_osd_open()` 调用 `video_hw_init(RECT_MODE)`；`osd_fb.c:550–592`
从 fb_width/fb_height 取帧尺寸，从 display_width/display_height 取输出窗口；
`video_scale_bitmap():1587–1627` 用前者配置 scaler 输入、后者配置输出。
`osd_hw.c:1944–1954` 按 fb_height×对齐行宽决定帧偏移，不按输出 VIC 决定。
`kvim4.h:CONFIG_DUAL_LOGO` 只有 MIPI 分支会改这两个 fb 环境变量，HDMI 4K 不改。
`fb_for_4k2k` 是扫描/scaler workaround，并非把 fb 扩为 4K。
摘录存 `logs/display/m0-r2/uboot-layout-source.log`。

没有从该匹配固件正常 HDMI 启动路径找到“4K 自动改变 fb 地址/尺寸”的依据，
因此不因 VIC 非16而禁用固定1080p节点；仍须实物确认 freescale 输出。
持久环境、MIPI、不同固件/启动路径均不在本次静态布局合同内。通用方案仍应让
U-Boot 从最终 OSD 配置动态 fixup /chosen/framebuffer 和保留内存；本轮不刷 U-Boot，
没有实现动态 handoff、热插拔、模式切换或 HDMI-OUT 音频。
