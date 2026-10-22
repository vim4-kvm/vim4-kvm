# 2026-10-22：7.3 HDMI 动态 LPCM 与无链路恢复

本轮使用独立 Linux/One-KVM 分支 `vim4-hdmirx-audio`，基于正式版
`vim4-kvm-7.3-final` 的 `71df93e289bb3` 与 One-KVM `2083cecf`。
七档原生采集与重采样、断链/模式恢复和无链路日志检查已完成。
网页少量异常短窗仍未定位，不能宣称逐样本连续或“完全无爆音”。
不改 U-Boot、Wi-Fi/P2P，不推送，主仓库不提交。

## 实现与边界

Linux HEAD `a320aa8ecb6fb`（另含 `3fa6ad8e95cc4`、`e830c4eaacccf`、
`14cb2fd3fdcfe`、`8ed682307b66f`、`abdad5bf9d850`、`9e38f3d662d79`）：双读 N/CTS、AIF 和通道状态，
校验 AIF 头、校验和、声明采样率与实测 ACR 一致性，识别
32/44.1/48/88.2/96/176.4/192kHz，按实测值的 ±1% 归入标准速率。
100ms 工作者在两次一致观察后公布格式；单次不一致快照保留旧状态，连续三次失败才停采，
两组 ACR 必须落入同一标准速率，允许 CTS 的正常微小量化变化；
仅比较通道状态中的格式位，避免无关状态位触发重试。真实链路丢失仍立即停采。
变化或失锁先停 FRHDMIRX 输出，
以 XRUN 终止旧 PCM，要求关闭后重新协商。原生 ALSA startup 约束为当前速率，
hw_params 再核对真实输入，防止旧约束与新信号的竞态。

四个只读 ALSA 控件 `HDMI RX Audio Rate / Channels / Generation / State`
提供格式与 VALUE 通知，使用实际控件 numid，避免全为 0 的事件被 ALSA 队列合并；
State 为 0 无可用格式、1 支持的 LPCM、2 不支持的格式。
应用读取代次前后两次，避免拼接不同格式的控件值。debugfs status 另保留原始 AIF、
ACR 和格式诊断，应用不依赖 debugfs。

厂商依据为 VM `~/src/linux/common_drivers` 中
`drivers/media/vin/tvin/hdmirx/hdmi_rx_hw.c` 的 `rx_get_aud_info`、`rx_aud_pll_ctl`，
以及 `sound/soc/amlogic/auge/frhdmirx_hw.c`。T7 FRHDMIRX 只有一条立体声 lane，
没有其他芯片的多声道 PAO 路径；本轮仅接收双声道 LPCM，S16_LE 输出，
压缩/HBR、多声道布局或非零通道分配会明确拒绝。未臆造新的寄存器路由。
RTK EDID 的 LPCM SAD 为 `09 7f 07`，本身只公布双声道。

One-KVM HEAD `382efb70e7ebb5e7fb8c9b13f1e6da5a161c84d1`
（含 `6e884729`、`91ed324b`、`7720ec1a`）：
仅识别到 VIM4HDMIRX 新控件时使用原生 `hw` 和五个完整 20ms DMA 周期，
非 48kHz 输入由板上已有 GStreamer `audioresample` 转到双声道 48kHz，
48kHz 不经转换。转换保持跨块滤波状态与按累计原生帧数计算的时间戳，
不在 ALSA DMA 环中插入重采样余量；输入积压超过半秒报错重建，不无限增长或阻塞 stop。
采集前查询链路/格式，变化后退出旧采集，
由既有恢复控制器重开。无源时每 250ms 只查询控件；真实失败采用 1/2/4/8/16/30 秒
有上限退避。旧内核没有控件时保持既有采集路径，并受通用退避保护。
现有 WebRTC 音轨重绑采集时，用空 Opus sample 补齐停采期间的单调时钟间隔，
推进 RTP 时间但不发送虚假音频包或消耗序号；离线包化测试核对 3 秒间隔和连续序号。

ASoC 的 `snd_soc_ret` 只静默 EPROBE_DEFER、ENOTSUPP、EOPNOTSUPP，ENOLINK
会被 DAI 与 PCM 两层记录。本轮不替换错误码或改全局 ASoC 行为，避免掩盖真实失锁；
用应用预检消除长期无链路时的 hw_params 重试。格式切换竞态仍可能报告一次真实错误。

## 离线验证

14 项 ASan/UBSan 测试覆盖实际 C 函数：七档 ACR/AIF、坏包、布局拒绝、原生约束、
格式通知、旧 PCM 拒绝重启、失锁恢复、PLL/时钟失败回收与重复清理。
One-KVM 最终 vim4 库测试 738 通过、2 跳过，ARM64 release 构建通过（19 条既有警告）。
GStreamer 转换测试覆盖所有非 48kHz 输入、跨不等长读取的连续音、
双声道不混合、有限流帧数误差至多一帧和破碎 PCM 拒绝。
额外 desktop 无 vim4 检查被构建镜像缺少 RKMPP FFmpeg 扩展阻塞，不能算通过。
Mac CoreAudio 公布全部七种速率，原速率 48kHz；每次按设备名显式设置 nominal rate，
仅向这个 HDMI 设备发送测试音，不改系统默认输出。切换会短暂重新锁链，
测试等待 `link_ready=1` 且驱动速率等于目标值，不使用固定短延时作为就绪证明。

## 原生与重采样录音

最终内核 build ID `b399826e95babd0b84e0f70a7dd0babfeb8c60a8`。
在双锁窗口内停止 One-KVM，以 440Hz、0.1 幅度真实 Mac 音源逐项录制：

```sh
timeout -k 3 8 arecord -q -D hw:VIM4HDMIRX,0 -f S16_LE -c 2 -r 32000 \
  --period-size=640 --buffer-size=3200 -d 3 /var/tmp/vim4-hdmi-audio/native-32000.wav
```

| 实测 Hz | N / CTS | 3 秒帧数 |
|---|---|---|
| 32000 | 4096 / 594000 | 96000 |
| 44100 | 6272 / 659999 | 132300 |
| 48000 | 6144 / 594000 | 144000 |
| 88200 | 12544 / 660001 | 264600 |
| 96000 | 12288 / 593999 | 288000 |
| 176400 | 25088 / 659994 | 529200 |
| 192000 | 24576 / 593999 | 576000 |

两声道均测得 440Hz；分析中间两秒，峰值 3277，RMS 2317.02–2317.07，
所有 10ms 窗 RMS 均在 2292–2342。原生最大相邻样本差随速率由 283 降至 48，
未观察到静音短窗或异常跳变。日志 `logs/kernel-edge/hdmi-audio/native-rates-qualified.log`，
对应 WAV 在同目录。只是每速率三秒的有限采样，不代表无限期连续性保证。

整周期约束前，32→48kHz 的 ALSA rate 插件做相同源、各 20 秒 A/B：
`plughw` 的 4096/960 客户缓冲对应 2730/640 原生缓冲，每次环回损坏样本；
去掉首秒后最大相邻差 4349，超过 500 的跳变有 1389 个。
4800/960 对应 3200/640，最大差仅 189、异常跳变 0。
证据 `plug-buffer-check.log`、`plug-4096.wav`、`plug-4800.wav`。

## 网页动态采样率

网页执行 48→32→44.1→48→88.2→96→176.4→192→48kHz，每项约 15 秒。
CoreAudio nominal、ACR、原生 hw_params 吻合；ALSA 四个实际 numid 均有 VALUE 通知。
Mac 重新配置时允许约 3 秒停采，保留音轨/SSRC 后重开，不要求切换无缝。
观察专用标签页实际播放，禁止麦克风/屏幕捕获和房间播放；产品音量滑块为 100%。
每 100ms 测波形，剔除切换前后启动窗口。旧的宽容阈值漏掉环回跳变，
`browser-rates-buffer-final.log` 只作为故障定位记录，不作为最终通过证明。

即使应用请求五周期缓冲，ALSA rate 插件仍可能在原生侧增加插值余量：
96kHz 实际得到 9602/1920、176.4kHz 得到 17642/3528、192kHz 得到 19204/3840。
96kHz 的 18 秒原生 9600/1920 录音最大相邻差 95、跳变 0；
`plughw` 的 9602/1920 则在每次约 100ms 环回处跳变，扩大缓冲后仍存在。
绕过 rate 插件，原生 9602/1920 的 RW 与 MMAP 各 9 秒同样失败（79/83 次跳变），
原生 9600/1920 的 MMAP 最大差 95、跳变 0，排除了仅浏览器或 rate 算法的问题。
因此在 HDMI DAI startup 加入 ALSA PERIODS 整数约束，防止应用或插件协商非整周期 DMA 环。
此处仅描述实测边界。
定位证据 `plug-rates-final.log`、`isolate-high-rates.log`、`native-buffer-test.log`；
前者在 96kHz 失败停止，不能写成七档全部通过。

整周期约束后还出现过 48kHz 稳态误停采，约 3 秒后恢复（`browser-rates-native.log`）；
随后改为按标准速率比较 ACR、仅检查格式状态位，保留失败轮次。

## 最终组合验证

最终原生采集后 `audioresample quality=8` 每档录音 10 秒，输出 48kHz，
最大相邻差 189–191，超过 500 的异常跳变均为 0。
192kHz 首轮误与小型 C 测试编译重叠，标为受干扰；
独占重录仍为最大差 189、跳变 0。证据 `gst-rates-qualified.log`、`gst-192-exclusive.log`。

最终应用的九步网页切换均恢复，原生 hw_params 为当前速率与五周期 DMA 环。
高采样率的周期性环回故障已未复现，但严格播放探针仍失败：32kHz 有两个 100ms 窗，
过零计数 570/550Hz、最大差 0.0568/0.0525；末次 48kHz 一窗最大差 0.0226。
这些窗口的格式代次稳定、RTP 零丢包，NetEQ 补偿计数没有同步变化，不能归因于 NetEQ。
保留 `browser-neteq-qualified.log`、`rate-status-v5.log`，没有放宽阈值把失败改成通过。
临时诊断程序直接编译应用的采集、重采样与 Opus 编码源码，外围仅替代生命周期/日志类型，
在板上对 32/48kHz 各录 30 秒：PCM 最大差 191/189、本地 Opus 解码 192/190，
异常跳变均 0（`probe-production-path.log`）。排查范围缩小至后续 RTP/播放器/观察链路，
没有把这项局部验证当作完整 One-KVM 或网页无爆音证明。
同一标签页观察器另测本地连续 440Hz PCM 30 秒，稳态异常窗为 0
（`calibration-continuous-tone.log`）；仍未解释远端异常，不能据此排除观察链路。

最终组合另通过 HPD 断链 32 秒、720p60→720p50→4K60 恢复，
并在 HPD 低时重启应用再观察 30 秒：PCM closed，ASoC 错误增量 0。
证据 `browser-recovery-v5.log`、`idle-startup-v5.log`。
同一浏览器用 0/+120/−120ms 片段各取得 5 对脉冲，校准残差中位
41.79/49.11/44.02ms；4K60 H.264 网页实播 60 秒，22 对有效脉冲，
原始音频晚中位 56.60ms、范围 55.57–76.67ms。稳态 RTP 丢包、音频隐蔽样本、
视频丢帧/冻结增量均 0，解码约 60.01fps。
这是有限时长的软件播放端点测量，不是长期漂移或光学/声学验收。

## 上板与恢复

独立输出 `~/build/kernel-hdmi-audio`，完整匹配 Image/DTB/2335 模块。
临时正式版门禁按 [正式版上板方法](2026-10-22-edge-7.3-final-board.md) 处理。
SHA256：Image `c6cdcdc9d5e66d305bef08191805f710074c8ade95537fd124025919abc69b8a`，
DTB `e0ebe345dba968f811136de69412cc58846814775ce4d4f3ac440ee5d32961c5`，
模块包 `daa5cba82ba244f5d53bd0ff730678a5e8a1bc3d8ae6241ff2cebab311f1f935`，
One-KVM `5d0924d3a24c319a6b0fc24a151290cb1b0d3f25334d933b98bb7ce947911dd3`。
板上完整模块哈希及已加载 ID 验证通过，HDMI RX ID 为
`0dd49c9041edfcd7786fe5829219bc5847ecef46`，日志 `reinstall-v5.log`。

实际独占窗口命令：

```sh
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/kernel-edge/hdmi-audio/board-window.py --reuse-backup
```

窗口内顺序安装整包、重启核验、执行 `finish-verification.py`，实际输出
`REMAINING_FINAL_VERIFICATION_PASSED`；网页严格短窗失败另列，不包括在这条输出中。
Wave5 调用均有 TERM/KILL 超时保护，持续 D 状态会抓栈并停止自动重启；未发生内核卡死。
未复现已知危险的非 8 像素对齐 HEVC。
末态 `taint=0`、风扇/VDIN 正常；严格零新增 warning 检查失败：
两次切换/恢复各产生一组 ASoC `-EAGAIN`（两层共四条），应用随后恢复。
`final-health.log` 保留失败，没有把有限竞态错误计成无链路刷屏或静默丢弃。

从 `/var/backups/vim4-hdmi-audio-20261022` 恢复 Image/DTB、模块、应用、SQLite、
运行门禁与 inventory，再重启。`board-window-final.log` 实际输出：

```text
Original running kernel build ID: ['52d5e46fb006230785110a1fa5ba0dd1383b732f']
Baseline loaded module: wave5 ccf41f01d1b624738912ca6e55a8b47d72156fe4
Baseline loaded module: t7_hdmirx 4acd39b5bd849a03382f78ba917ec962bcfbafed
Baseline loaded module: t7_vdin_test b8cbea260ce5108b216d5cee75091015a73cfb27
tainted: 0; one-kvm: active; original application hash: OK
vim4-manager: active; original boot links and command line: OK
BASELINE_RESTORED
```

原 EDID SHA256 及原始模块全树也核对一致。多声道、压缩/HBR、长时耐久与物理声学验收未完成；
网页异常短窗仍待定位，不能把本轮写为完整无爆音验收。
