# 2026-10-21：7.x 音画测量校准与漂移复核

完成 [HDR 稳定性记录](2026-10-21-edge-hdr-stability.md) 中音画疑点的软件端点复核。
H.265 十分钟、H.264 五分钟均未观察到超过本机约 25ms 测量尺度的稳态首尾增长；
这不是无限期零漂移或光学/声学校准保证，也没有通过切换 5.15 做回退对照。
旧工具的独立音轨观察器不能代表网页播放器，首尾中位差也不能单独作为时钟漂移证据。
本轮修改测量工具和验收记录，内核、应用、音频缓冲、EDID 和 5.15 启动项不变。

## 测量链修正

原工具把接收音轨交给单独的 `MediaStreamAudioSourceNode`，轮询 128 样本的
Analyser。它可证明声音存在，但这条独立音频消费路径与网页播放器的音频时序不同。
视频又使用提交合成时间，与音频输出时钟不在相同播放端点。

新工具 [one-kvm-av-sync-check.mjs](../../tools/one-kvm-av-sync-check.mjs) 与
[av-sync-probe.mjs](../../tools/av-sync-probe.mjs) 观察专用测试标签页的播放输出：

- 只捕获当前测试标签页，拒绝屏幕/窗口捕获，不打开麦克风；关闭回声消除、自动增益和降噪。
- 播放器音频开启，标签页回环抑制本地扬声器输出；AudioWorklet 按样本位置识别音调起点，
  不用 UI 线程回调到达时间当作音频时间。观察器输出为零，避免反馈。
- 映射音频输出时钟，与视频 `expectedDisplayTime` 比较，同时保留提交时间、媒体时间、
  RTP 时间戳、像素回读耗时和音频时钟记录。正数表示音频晚。
- 丢弃前 15 秒；每个两秒脉冲最多匹配一次，缺失声音或匹配不足直接失败。
- 保留实际 RTP 统计，包括音频补偿/隐蔽样本、缓冲停留时间、视频丢帧/冻结及 SSRC。
  测试退出恢复原编码、关闭浏览器，不重启服务或改 EDID。

根据 [Web Audio 时间戳定义](https://www.w3.org/TR/webaudio-1.0/#dom-audiocontext-getoutputtimestamp)
和 [视频回调定义](https://wicg.github.io/video-rvfc/#dom-videoframecallbackmetadata-expecteddisplaytime)，
这是浏览器软件播放端点；预计显示时间仍非面板光子时间。标签页回环与观察 AudioContext
增加了延迟，必须先测偏置。不能将回环的原始差值直接归因于板子。

Chromium 对远端 MediaStream 的媒体元素音频源没有在本轮产生可测 PCM，所以直接
`createMediaElementSource(video)` 的试验保留为失败，没有把静音计作同步通过。
标签页回环需要关闭 Playwright 默认的 `--mute-audio`；只取消 HTML muted 不够。
两条失败路径的日志保留，不作为产品音频故障。

## 已知偏差校准

同一 Chrome 156.0.8078.47、默认 48kHz 输出、48kHz AudioContext；标签页捕获实际
协商 44.1kHz，浏览器重采样。用 60fps、每两秒闪白 250ms 与 440Hz 音调的 MP4：
零偏差片段 190 秒，另外两段 26 秒分别让声音延后、提前 120ms。
所有统计在离线汇总时统一剔除前 15 秒；短片仅验偏差方向，不用于漂移斜率验收。

| 已知音频偏差 | 有效脉冲对 | 减去已知偏差后的中位 | 范围 |
|---|---|---|---|
| 0ms | 87 | 50.32ms | 46.72–64.72ms |
| +120ms | 5 | 55.87ms | 55.57–56.47ms |
| −120ms | 5 | 61.51ms | 60.91–62.01ms |
| 0ms，最终启动次序复验 | 5 | 42.28ms | 42.18–43.18ms |
| +120ms，最终启动次序复验 | 5 | 47.85ms | 47.15–48.15ms |
| −120ms，最终启动次序复验 | 5 | 54.77ms | 54.67–55.07ms |

因此这条回环链自身约有 42–62ms 偏置；含最终启动相位复验的总范围约 23ms，不能承诺
毫秒级绝对精度。已知 ±120ms 被正确区分，校正后残差都落在同一校准范围。
零偏差片段的首尾一分钟中位差 **−12.7ms**：即使源片段完全同步，显示调度与
输出时钟观察也会产生约一帧的首尾变化，不能把一次首尾差或短窗拟合线外推为累积漂移。
最终实现先建立回环再取消播放器静音，避免启动短音泄漏；重启相位也会影响观察器偏置。
本轮保守采用约 25ms 的经验测量误差尺度；它是本机本配置的校准范围，不是统计置信区间。

生成片段的参考命令（在有 FFmpeg 的机器上运行，不与板端测量并发）：

```sh
ffmpeg -f lavfi -i 'color=black:s=640x360:r=60:d=190,drawbox=color=white:t=fill:enable=lt(mod(t\,2)\,0.25)' \
  -f lavfi -i 'aevalsrc=if(lt(mod(t\,2)\,0.25)\,0.1*sin(2*PI*440*t)\,0):s=48000:d=190' \
  -c:v libx264 -preset ultrafast -c:a aac -movflags +faststart -shortest zero.mp4
ffmpeg -i zero.mp4 -c:v copy -af adelay=120 -c:a aac -t 26 -movflags +faststart plus120.mp4
ffmpeg -i zero.mp4 -c:v copy -af 'atrim=start=0.12,asetpts=PTS-STARTPTS,apad' \
  -c:a aac -t 26 -movflags +faststart minus120.mp4
node tools/one-kvm-av-sync-check.mjs --calibrate=zero.mp4
node tools/one-kvm-av-sync-check.mjs --calibrate=plus120.mp4 --expected-ms=120
node tools/one-kvm-av-sync-check.mjs --calibrate=minus120.mp4 --expected-ms=-120
```

校准模式只读指定本地文件并监听随机 loopback 端口，不登录或访问板子。
上板模式仍需要工具目录规定的 Playwright、统一登录环境和 `--exclusive`，配合
物理 HDMI 桌面的 `latency-source.swift --motion --verify-coherence --no-labels
--hdr-chart --sync-audio=VIM4-UHD-60`；HDR 开关由调用者准备和恢复。

## 上板版本与证据

Linux `c4e982bf80cd0cc8b2f988fd2f6de34017a1838c`，运行版本
`7.3.0-rc7-vim4kvm-uhd1+`；One-KVM `edc426a17e7d5036b2c33b588dca993d79a8d90c`，
ELF SHA256 `9a5094e2587abfa5cac27b622190243e0e09a9ca5315f6b3263df69e782f54b5`。
HDR10 4K60、曲线 203/1000、编码预算 30000kbps，Mac 经有线 LAN 访问网关 8080。
负载是运动网格、三带帧号、HDR 灰阶与音画脉冲，不是高熵游戏压力。

H.265 先做三分钟预检查，再做同一连接十分钟复核。预检查首尾差 +4.0ms；
十分钟并未按该短窗斜率继续扩大。15 秒预热后 293 对脉冲、中位 57.92ms，
原始范围 50.21–75.74ms；扣除本次校准的经验偏置范围后，中位约 −7 至 +16ms。
这些范围不是物理 HDMI/扬声器的独立标定，也不是精确的统计置信区间。

十分钟的首尾一分钟中位为 72.31→55.83ms（−16.48ms），整体拟合 −0.19ms/分钟。
音频 RTP 同期记录到 600 个加速补偿样本（12.5ms），目标缓冲从启动约 42ms
向约 20ms 收敛，说明起始调整包含实际的播放缓冲变化，不能全部归为观察器误差。
排除前两分钟后，首尾一分钟为 59.04→55.83ms（−3.21ms），全程处于一帧左右的
调度波动尺度，没有出现旧短窗数值所暗示的单向累积增长；拟合线仍不能外推为无限期零漂移。

RTP 稳态增量：音视频同一 SSRC、丢包均 0，视频解码 60.001fps、丢帧/冻结均 0；
音频 concealedSamples 没有增加。音频/视频平均 jitter-buffer 停留约 31.63/0.22ms。
这两个内部均值不能相减冒充音画偏差。像素回读平均 3.86ms，最大 9.5ms；
此轮是音画探针验收，不用它宣称无探针播放性能提高。

H.264 运行 300.6 秒、143 对有效脉冲，原始中位 61.72ms、范围 55.88–77.48ms；
扣除校准经验偏置范围后，中位约 −3 至 +20ms。首尾一分钟为 57.08→70.54ms
（+13.46ms）；排除前两分钟后为 60.62→70.54ms（+9.92ms）。该变化没有超过
校准片段约 23ms 的自身范围，不能把它外推为已确认的硬件漂移，也不宣称精确零漂移。
音视频 SSRC 保持，稳态丢包/音频 concealedSamples 增量均 0，视频丢帧/冻结均 0，
解码 60.001fps；音频/视频平均 jitter-buffer 停留约 20.00/0.33ms。
像素回读平均 3.29ms、最大 8.1ms。

本轮关闭的是“未经校准的独立音轨测量是否证明驱动故障”这一疑点。现在有可复现的
播放输出观察、已知偏差校准和有限时长的漂移边界；没有证据需要改内核或通过增加
视频缓冲补偿。30 分钟以上耐久、隔夜、物理扬声器/面板以及用户暂缓的整机睡眠，
仍按原任务分别验收，不以本轮结果代替。

本机原始记录 `logs/kernel-edge/av-calibration-*`、`av-sync-tab-*`，
汇总 `logs/kernel-edge/av-sync-calibrated-summary.json`；前一条记录的旧数值仍保留，
不能与本轮不同观察路径直接相减来宣称性能改善。

逐样本脉冲匹配回归覆盖已知偏移、缺失脉冲、部分启动音、负偏差与漂移斜率，
Node 三项通过。主仓库离线 128 项中 123 通过、5 跳过；新增工具的浏览器校准及两种
编码上板实测通过。内核和应用未修改、未重新构建，也没有切换或部署 5.15。

结束时源 HDR 偏好关闭、默认 H.265、音频健康且没有观看者；DMA-buf 归零，
taint/sensor_fault 为 0，48°C、风扇 11%。5.15 Image、应用和默认启动项哈希与测试前一致。
板端 manifest 保留旧原始测量并标为历史独立音轨观察，新增 `runtime_tests.av_sync_playout`
记录本轮校准与验收范围；原 manifest 和汇总备份到
`/var/backups/vim4-onekvm-edge-20261020/hdr-stability/av-calibration/`。
