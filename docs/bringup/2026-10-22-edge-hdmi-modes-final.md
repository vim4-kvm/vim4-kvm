# 2026-10-22：HDMI 模式最终产物复核

续接[首轮实现与故障](2026-10-22-edge-hdmi-modes.md)。本轮不扩展 HDMI 音频功能，
只定位无输入时的日志来源。实测已结束并恢复基线；未覆盖项与异常如下。

## 产物与应用回退

内核独立分支 `vim4-hdmirx-modes`，HEAD `87d0423e74a219983dd4e2e105beb1d391aa4c0f`，
工作树 `/home/deepdream/src/linux-7.3-hdmi`，独立输出 `~/build/kernel-hdmi-modes`。
Image build ID `4086bbfe5035e5c3f318fb26107e4ad668fc70fe`；完整 2335 个模块包 SHA256
`a0ab3644c1774468b7c1436d45eea14fed4d33d58c6a2b403269eeaf25b17d1c`。
Wave5 模块 build ID `2645a1dec0123f47261aaf33cc4d17bb01fcde8d`；完整文件清单在
VM `~/build/hdmi-modes-payload9/manifest.json`。Image/DTB/配置哈希同首轮记录。

One-KVM 独立工作树 `build/kernel-edge/hdmi-modes/One-KVM`、同名分支，新增提交
`283fe239`、`2083cecf`；HEAD 为后者。最终 ELF SHA256
`30c4d9bd558e3a1ec98321b7174b9169e4c40a55b487830da5c76a93486c92d4`。
按缩放后的可见尺寸判断 HEVC 的 8 像素约束；启动或源变化不满足时，在打开 HEVC
之前停止旧管线，改用 AVC，并通知浏览器重新协商 SDP。API 返回实际编码格式。
1366×768、1440×900、1680×1050 原尺寸回退 H.264，回到对齐模式后保持 H.264，
用户可重新选择 H.265。5.15 厂商后端不应用此限制。

补测首次连接发现另一处顺序问题：创建管线可能回退编码器，但 SDP 曾提前读取旧 codec。
`2083cecf` 改为创建管线后再读取；显式选择编码也先按实测几何求兼容格式，再判断是否
无需变更。已运行的 H.264 管线不会因重复请求不兼容的 H.265 而重建。

应用库测试 `cargo test --locked --features vim4 --lib`：732 passed、2 ignored；
release 构建成功，19 条既有编译警告。新增测试覆盖源尺寸和缩放后尺寸的约束边界。
内核最终 Wave5 五组离线测试通过。未推送，未在主仓提交，原工作树未修改。

## 独占窗口与恢复要求

用户现场 RESET 后，本会话只读复核基线、manager/One-KVM active、tainted=0。
PD 会话先使用共享板；排队取得双锁后再次检查基线，保留 PD 更新后的 U-Boot。

```sh
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/kernel-edge/hdmi-modes/board-window.py \
  --reuse --interactive --baseline-audio
```

复用首轮完整基线备份；安装匹配 Image/DTB/完整模块和应用，重启核验加载 build ID。
浏览器监督进程超时后 TERM、5 秒后 KILL；临时服务 TimeoutStopSec=5。测试只给对齐
尺寸请求 HEVC，不再进入已知危险的 1366×768 HEVC。若出现持续 D 状态，采集线程栈
和 dmesg，立即停止，不重复重启。结束恢复基线文件、原应用和 EDID，再重启核验。

## Wave5 待修问题

前两次 1366×768 HEVC 均留下不可正常退出的线程，第二次使用正确的专用插件与
Main/5.1 caps，timeout 在 45 秒返回 255，gst-launch 主线程显示 Zl，其他线程仍等待。
两次均拖延普通重启，第二次需现场 RESET。不能安全保证复现退出，本轮不再次触发。
复位前未取得 `/proc/<pid>/task/*/stack`；板子无持久 journal，复位后无法补取旧内核栈。
保存的 `candidate-journal.log` 未给出决定性错误，不能断言固件的具体失败原因。

疑似等待链为 `v4l2_m2m_streamoff/ctx_release → v4l2_m2m_cancel_job` 等待活动任务结束；
Wave5 编码器未实现 job_abort，`wave5_vpu_enc_finish_encode()` 在
`wave5_vpu_enc_get_output_info()` 失败后直接返回，没有 job_finish。若完成中断或结果
丢失，可能让退出等待无法结束；这只是源码推断，尚无现场栈证明。后续应在独立窗口
采集完成 IRQ/firmware 状态、线程栈，设计有界取消，并保持固件仍持有的 DMA 生命周期。

## 实际验收

最终产物已完整核验加载的内核/模块 build ID。原始日志目录
`logs/kernel-edge/hdmi-modes/`；以下先列应用 `283fe239` 的矩阵，再列最终应用复核。

- `retest-raw.py`：19 个模式全部通过，与首轮表格相同，包括两种 50Hz、1080p24/25/30、
  非对齐宽高、1440p60、4K30/60。每组两帧检查实际 stride、三条帧号/校验和、推进和
  三原色。DMA-buf 每次回到 0，CMA 全程 505208 KiB，faulted=0；40 条 SOURCE_CHANGE。
  日志 `raw-modes-87-final3.jsonl`、`source-events.jsonl`。
- `run-browser.py h264 0,1,5,7,8,10,14,17,18`：低分辨率、三个非对齐模式、两种 50Hz、
  4K30/60 共 18 次往返通过。实际 video/H264、同一 SSRC，帧号/颜色、JPEG 200、
  约 60/50/30fps 均通过；70Hz 输入输出约 60fps。日志 `browser-h264-87-final2.jsonl`。
- `run-browser.py h265 0,1,5,11,14,16,17,18`：640×480、720×400、720p50、1080p24/50、
  1440p60、4K30/60 共 16 次往返通过；实际 video/H265、同一 SSRC，内容、JPEG 和
  帧率通过。仅选宽高为 8 倍数的模式。日志 `browser-h265-87-final.jsonl`。
- `run-browser.py h265 fallback`：0→7→8→10→0 再反向，共 10 次通过。
  初始 video/H265，进入非对齐模式后自动改为 video/H264，返回对齐模式保持 H.264；
  内容和帧率通过。日志 `browser-fallback-87-final.jsonl`。
- 最终应用 `2083cecf` 的 `run-browser.py h265 cold-fallback`：无浏览器时先选择
  H.265，再切到 1440×900；连接前 API 仍为 h265，首次实际 RTP 是 video/H264。
  再请求 h265，API 返回 h264；往返两次内容、JPEG 和约 60fps 均通过。
  日志 `browser-cold-fallback-87-final.jsonl`。此前未等首次连接就立即请求的测试失败，
  日志 `browser-fallback-request-87-final.jsonl` 保留，不计通过。

两次 raw 失败是就绪检查误用不列 SDR 屏幕的 HDR 工具，改用完整 NSScreen 列表。
H.264 首轮切换后立即 snapshot 返回 503；改在持续解码后检查，上述 18 次均直接 200。
失败数据保留，不计通过。

最终应用 `2083cecf` 又按同一命令重跑：H.264 18 次内容和持续帧率均通过；H.265
16 次内容、尺寸、JPEG 均通过，15 次达到目标帧率。720×400@70 前向一次为
28.3/30.7/31.5fps（三个连续 3 秒窗口），反向恢复 60.5fps；因此不能把该轮写成
全模式持续满帧。两个矩阵仍各保持同一 SSRC。日志 `browser-h264-2083-final.jsonl`、
`browser-h265-2083-final.jsonl`；低帧率采样保留，后续定点复测另记。
`run-browser.py h265 0,1` 定点往返四次内容均通过，两次 720×400 分别为
60.2/61.5fps，日志 `browser-70hz-2083-recheck.jsonl`。这证明可恢复约 60fps，
没有定位此前瞬时低帧率的根因，不能据此声称长期稳定性问题已修复。
最终应用回退矩阵再跑 10 次全部通过，日志 `browser-fallback-2083-final.jsonl`；
1366/900/1050 均为实际 video/H264，对齐模式首次为 video/H265，返回后保持 H.264。
同 codec 的 H.264、H.265 矩阵各自回到 640×480 时，DMA-buf 都保持
18 objects / 188620800 bytes，CMA 前后同为 319616 KiB；没有随切换累积。

### 颜色请求的实际输入

`colors.py --extra` 的两组原始 NV12 均通过两帧的三条帧号带、推进及理想三原色阈值，
结束 DMA-buf=0、VDIN faulted=0。日志 `colors-extra-87-final.jsonl`：

| EDID 请求 | 实际 AVI / GCP | 内容结论 |
|---|---|---|
| 4K60 420 SDR8 | space=3、depth code=0，即 420/8 | 原始帧通过 |
| 720p60 444 12bit | space=2、depth code=0，即 444/8 | 原始帧通过；没有取得 12bit |

12bit 仅有解析/配置离线覆盖；422 固定容器不能用 GCP code=0 推断源精度。
RGB 深色、422 SDR、物理 BIOS 固件画面未实测，HLG 当前拒绝。

最终应用 `run-browser.py h264 colors` 六组全部通过实际 WebRTC 内容、三条一致帧号带、
理想三原色阈值、JPEG 200 和约 60fps，同一 SSRC。日志
`browser-colors-2083-final.jsonl`；每组保留 AVI、GCP、实际 RTP codec 和颜色读数。

| 浏览器测试 | 实际输入 | 结果 |
|---|---|---|
| 422 PQ | 422 固定容器，源精度未知 | 通过 |
| 420 PQ10 / SDR10 | 两者均实际 420/10 | 通过 |
| 444 SDR10 | 实际 444/10 | 通过 |
| 420 SDR8 | 实际 420/8 | 通过 |
| 444 SDR12 请求 | 实际 444/8，requestSatisfied=false | 内容通过，12bit 未覆盖 |

最初颜色轮次在 420 SDR10 停止：测试硬编码了首轮基线的偏色读数，而这次实际读数为
R=(255,0,2)、G=(18,255,0)、B=(0,7,255)，符合三原色阈值。测试随后区分理想原色和
历史基线参考；上述六组均为前者，没有靠历史参考放宽通过。源端 HDR/显示偏好可能
影响结果，不将其解释成新增驱动色准修复；失败日志 `browser-colors-87-final.jsonl` 保留。

### 失锁与期末资源

最终应用 `run-browser.py h264 loss` 将 HPD 拉低 5 秒，实际 link_ready=0、capture_users=0，
之后同一 SSRC 恢复帧号/三原色和 JPEG。恢复初期三次 3 秒采样为 12.6/5.3/46.3fps，
再次切同尺寸后为 4.0/54.6fps；不能据此宣称失锁恢复后立即满帧。
日志 `browser-loss-2083-final.jsonl`。该失锁 EDID 未带音频能力，与主矩阵保留 SAD 的
EDID 不同；是否关联尚未证明，不在本轮猜测或修改音频。

`idle-check.py` 停应用后实际为 `Total 0 objects, 0 bytes`、faulted=0、stream_error=0，
CMA 505192 KiB，比 raw 矩阵的 505208 少 16 KiB，差异未定位；导出 DMA 已清空，
不能据此证明全部内部 CMA 分配回到起点。重新启动应用后完整模块清单、已加载 build ID、
最终 ELF 哈希、manager/One-KVM active、taint=0 均核验通过；
`New unexplained warnings: []`、`HEALTH VERIFIED`。日志 `idle-2083-final.log`。

## 无有效输入时的音频日志

先在原基线、原应用下做停启对照，未改音频格式或驱动。状态为 source_5v=1、
PHY locked、link_ready=0：线上有 Mac 的 422/PQ 数据，但原基线不接纳该输入，
不能把这次现场描述成物理拔线。无有效视频 link 时音频 hw_params 返回 ENOLINK。

`audio-log-probe.jsonl` 实际计数：应用运行 4 秒 8 条 `ASoC error (-67)`；
停止 One-KVM 后 5 秒 0 条；重启应用后 4 秒 8 条。应用日志同步显示每秒重新枚举、
`Starting audio stream: hw:0,0 @ 48000Hz`，随后 snd_pcm_hw_params errno 67。
One-KVM `src/audio/recovery.rs` 的 RETRY_DELAY=1 秒；
`t7_hdmirx_audio_hw_params_locked()` 在动态 link 未 ready 时返回 -ENOLINK，
ASoC 的 DAI 与 PCM 层各记一条。同一次打开失败对应两条，并非驱动自行每秒调用。
应用自己的错误节流不影响内核两层输出。恢复策略与预期失锁错误的日志处理留到音频轮次，
本轮没有改动音频功能。

## 最终恢复

同一双锁窗口内执行 `board-helper.py restore`、重启、`board-helper.py verify-restore`；
日志 `board-window-final.log` 实际输出：

```text
NEW_BOOT_ID e7af7612-28af-4151-bf4a-baccabb4b671
All original module files and symlinks: OK
Original running kernel build ID: ['52d5e46fb006230785110a1fa5ba0dd1383b732f']
tainted: 0; one-kvm: active; original application hash: OK
vim4-manager: active; original boot links and command line: OK
RESTORED after reboot
BASELINE_RESTORED
```

已加载 Wave5/RX/VDIN build ID 与基线逐一相等；原 Image/DTB、全模块、启动链接、
原应用、kernels/runtime 清单和 RTK EDID 哈希均匹配。临时服务超时覆盖已移除，双锁释放。
主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：147 tests、5 skipped、OK，
日志 `main-tests-final.log`。
