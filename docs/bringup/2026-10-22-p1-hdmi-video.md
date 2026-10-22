# 2026-10-22：P1 HDMI 帧率、恢复与 CMA 复核

720×400 的历史 23–30 fps 未复现；1366×768 H.264 在重新锁定后稳定约 60 fps。
恢复初期低帧率已取得采集停顿/重建证据。CMA 各窗口分配释放配对、停流位图一致，
不能把 `CmaFree` 的 16 KiB 差异当成 HDMI 缓冲泄漏。
音频分段统计、分支与应用提交见[音频记录](2026-10-22-p1-hdmi-audio.md)。

## 基线与命令

使用原部署 Linux `e0346697f2503`、One-KVM `382efb70`、manager `7a69ced`。
没有安装新内核、加载/卸载模块或触发非 8 对齐 HEVC；1366×768 只使用 H.264。
物理 HDMI 桌面运行带三处帧号/校验和与三原色的运动源，禁止并行构建。
每三秒记录浏览器 decoded frames、应用编码 FPS、VDIN IRQ/stream_frames。
API 的 FPS 是上一个编码统计窗口，不能将它直接当成当前三秒区间的采集平均值。

```sh
VIM4_TEST_MODES=0,1 P1_WINDOWS=10 P1_CODEC=h265 \
  /usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/p1-hdmi/video-window.py
VIM4_TEST_MODES=7 P1_WINDOWS=45 P1_CODEC=h264 \
  /usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/p1-hdmi/video-window.py
VIM4_TEST_LOSS=1 P1_TRACE_RX=1 P1_WINDOWS=10 P1_CODEC=h264 \
  /usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/p1-hdmi/video-window.py
```

0/1/7 分别是 640×480、720×400、1366×768。每组结束恢复原 EDID、原 codec 和应用。
临时 trace instance `p1-cma` 使用每 CPU 512 KiB 环，仅启用 CMA 分配/释放，
小于等于四页的分配才请求调用栈；结束关闭并删除本任务的 instance。
后续等待共享锁使用 `build/p1-hdmi/locked.py`：每次只等待一秒重型构建锁，
未获得便释放板锁，避免其他任务编译时长期占住板子。

## 帧率与内容

720×400 H.265：640→720→720→640，720 两段各十个 3 秒窗，浏览器
59.63–60.61 fps，应用编码约 59.22–60.21 fps，实际输入约 70 Hz、输出上限 60。
同一 SSRC，结束快照、三处帧号与三原色通过，没有浏览器丢帧计数增长。
VDIN 持续推进，没有 faulted/stream_error。不能定位未复现的历史 23–30 fps，
这不是修复证明。证据 `logs/p1-hdmi/video-720.log`。

1366×768 H.264：两段各 45 个 3 秒窗，累计 270.35 秒净采样，连同窗口间状态
查询约五分钟。初次重新锁定前两窗为 45.94/53.60 fps，随后 88 窗为
59.57–60.01 fps；应用编码约 59.77–59.80 fps，同一 SSRC、浏览器丢帧计数 0。
前两窗 VDIN 从 running 变 idle 并重建，不能归因于浏览器单独慢解码。
两次内容/快照均通过。证据 `video-1366.log`、`video-1366-journal.log`。
这是一轮约五分钟测试，不是隔夜耐久或所有码率的保证。

## HDMI 恢复爬坡

HPD 低五秒、写入 640×480 无音频 SAD 的 EDID，再同尺寸切回带音频的 EDID。
第一次恢复首个 3 秒窗为 3.67 fps，之后九窗约 59.89–60.01；同尺寸切回的
十窗约 59.64–60.28。原始证据 `video-recovery.log`、
`video-rx-1792680482.jsonl`、`video-journal-1792680482.log`。

墙钟 1792680501.728 秒 RX 首次 `link_ready=1`；约 0.8 秒后原始
`frame_ticks=16777215 (0xffffff)`，VDIN 停在 14–15 帧；随后两次 capture_users
降到 0、DMA idle，流计数重置。应用 14:48:22.570 与 14:48:24.155 UTC 各记录：

```text
VIM4 video: ... gst_v4l2_object_poll ... poll error 1:
Inappropriate ioctl for device (25)
```

`capture_vim4()` 的总线错误返回到 `run_vim4()`，每次执行十个 100 ms 的有界退避。
14:48:25.344 后采集稳定推进，后续浏览器恢复约 60 fps。这解释本次“已经出画面
但首窗仍很低”：RX 的首次 ready 早于持续稳定采集，期间发生采集错误和重建，
不是编码器逐渐升频或仅浏览器追帧。GStreamer 的错误文本不能单独证明哪个 ioctl
导致硬件失稳；不将旧 errno 25 当作已定位的寄存器根因。
没有凭这次瞬态擅改 PHY 参数或缩短安全恢复等待。

## CMA 生命周期

三组窗口 `cma-1792679810.trace`、`cma-1792680076.trace`、
`cma-1792680482.trace` 分别记录 230/105/120 次成功分配，以及相同数量的释放，
按 PFN 配对无遗留；没有小于等于四页的 CMA 分配。各轮停止 One-KVM 后
`Total 0 objects, 0 bytes`，CMA used/bitmap_used 都为 4770 页，位图 SHA256
均为 `131492b63db5b0d01b7638d69082b8b41a4f5486a21ae369d04e356067b77724`。

实际停流输出：

```text
CmaTotal: 524288 kB
CmaFree:  505192 kB
used: 4770 pages
outside_bitmap_flags: {"0x400": 126298, "0x0": 4}
resident_count: 0
```

4770×4=19080 KiB；按位图可用量应为 505208 KiB，正好比 CmaFree 多 16 KiB。
位图外四页没有 BUDDY 标记，其余 126298 页均有；没有 LRU、SLAB、MMAP、ANON
标记。随后在双锁下停止应用，经 `/dev/dma_heap/reserved` 各申请/关闭一个
16 KiB 和 1 MiB 缓冲，不导入任何设备。`cma-pcp-proof.log` 实际输出：

| 阶段 | 位图占用页 | CmaFree KiB | 位图外无 BUDDY 标记的页 |
|---|---:|---:|---:|
| 初始 | 4770 | 505208 | 0 |
| 持有 16 KiB | 4774 | 505192 | 0 |
| 关闭 16 KiB fd | 4770 | 505192 | 4 |
| 持有 1 MiB | 5026 | 504184 | 0 |
| 关闭 1 MiB fd | 4770 | 505208 | 0 |

源码对应 `mm/cma.c::__cma_release_frozen()` 先释放页再清位图；
`mm/page_alloc.c::free_prepared_contig_range()` 经 `__free_frozen_pages()` 将允许
进入 PCP 的小阶页缓存到每 CPU 空闲链表，CMA 在 PCP 中按 MOVABLE 处理。
`account_freepages()` 的 NR_FREE_CMA_PAGES 统计 buddy；后续连续分配路径
`alloc_contig_range` 调用 `drain_all_pages()`。因此四页已经释放，暂时不计入 buddy
空闲量，连续分配会收回。这是页分配器缓存差额，既不是新泄漏，也不是需永久保留的
16 KiB HDMI 分配；无需修改驱动或强制每次停流排空全系统 PCP。

## 颜色与信号覆盖

持双锁运行 `build/p1-hdmi/colors.py` 和 `--rgb-hdr` 补测，仅临时修改 EDID RAM，
停止应用后读取两张原生 NV12 帧。按实际 AVI/GCP/DRM 判断格式，不把 EDID 请求
或脚本用例名当成真实信号。证据 `color-coverage.log`、`color-rgb-hdr.log`。

| 请求 | 实际输入与结果 | 覆盖边界 |
|---|---|---|
| RGB deep colour SDR | 清除 VSDB 的 DC_Y444 后，720p RGB、GCP depth=5（10-bit），link_ready=1；帧号 128→147，三处标记一致、三原色通过 | 补齐 RGB 10-bit SDR 原生采集；没有扩展到所有时序/浏览器编码 |
| RGB deep colour HDR / RGB12 HDR | 720p RGB、depth=6（12-bit）、BT.2020、PQ DRM；两轮均 link_ready=0 | 信号已产生，当前基线拒绝 RGB/2020 HDR，不算 12-bit 成功采集 |
| 444 12-bit SDR | 源回落到 720p 444 8-bit，两个帧号及三原色通过 | 不算 12-bit 覆盖 |
| 422 SDR | 去掉 HDR 宣告后源选择 4K 444 8-bit SDR，两个帧号及三原色通过 | 未产生 422 SDR |
| HLG | 仅宣告 HLG EOTF 后 Mac 报 hdr_modes=false；实际 4K RGB 8-bit，无 DRM，两个帧号及三原色通过 | 未产生 HLG |
| BIOS 文本 | Mac 桌面可输出 720×400 时序 | 没有实际 PC BIOS/UEFI 文本信号，不以桌面时序代替 |

第一次 RGB 请求仍带 DC_Y444，实际得到 444 10-bit，未计入 RGB 覆盖。
按厂商 `hdmitx_edid_parse.c` 的 VSDB 定义清掉 bit 3 后才得到上述 RGB 10-bit。
RGB12/PQ 拒绝与源码一致：`t7_hdmirx_hdr_input()` 只接受 YUV 的 BT.2020/PQ，
注释明确 RGB/2020 需要不同输入矩阵；`t7_hdmirx_read_color()` 拒绝不支持的
扩展色域。不能把该结果泛化为所有 12-bit 都不支持，也没有直接打开未经验证的矩阵。

`colors.py --12bit` 追加结果见 `color-12bit.log`：44412/PQ 能力声明仍使源选择
RGB12/PQ，接收端拒绝；RGB12/PQ 后关闭 HDR，源回落 RGB8（depth=4），
帧号 130→149、三原色通过。不能将关闭 HDR 前的位深用于 SDR 通过结论。

剩余验证需要能显式固定色彩编码/位深/EOTF 的 HDMI 信号源或 GPU 驱动：
12-bit SDR / YUV PQ、422 SDR、HLG（EOTF=3 且有效 DRM）；BIOS 需要真实 PC
固件启动输出或能重放该信号的发生器。EDID 只是能力声明，不能强迫当前 Mac 选择
每一种组合。未做现场物理插拔、额外设备或伪造测试结果。

## 恢复与交付

每组测试 finally 恢复原 EDID、源端 SDR、原应用及 codec；音频测试恢复 48k。
没有部署候选内核。最终持双锁运行 `build/p1-hdmi/final-window.py`，比较运行中
GNU build ID、Image/DTB 哈希和两个服务的 `/proc/PID/exe` 哈希，并验证 EDID
debugfs 与硬件 RAM 均为原始内容。实际 HID 使用
`tools/one-kvm-usb-check.mjs --exclusive --hid-only`，只在原生临时窗口注入事件。
原始证据 `logs/p1-hdmi/final-health-hid.log`，补测后再次验证见
`final-health-hid-last.log`。

```text
RUNNING_BUILD_ID 3ed254bfa838ab50732fdce1c5134400a1663fd5
RUNNING_SERVICE_SHA_OK one-kvm 72db30c07aa2351a27499e06d2ac28ccde3a74e1cb18d0927766a7ba35d37b0d
RUNNING_SERVICE_SHA_OK vim4-manager ad7b8aa3e068cb4f5e4ef8e8c2fb6df623c791a1c4ed82949e616cd6fd01f67c
UDC {'fdd00000.usb': 'configured'}
HDMI_BASELINE link_ready=1 width=3840 height=2160 audio_rate=48000 audio_channels=2 audio_pcm=1
P1_BASELINE_VERIFIED tainted=0 EDID_RAM=original diagnostics=removed
native-hid: keyboardDown=1 keyboardUp=1 absoluteMouse=true click=true wheel=true
relativeBefore=[0.6999959309895833,0.5999891493055556]
relativeAfter=[0.7099039713541667,0.6117332175925926]
```

服务均为 active，VDIN faulted/stream_error 均 0；本任务的统计环境覆盖与 CMA
trace instance 已删除。没有用旧的 round3 备份覆盖基线：该目录的备份是升级前
内容；本任务临时安装前另存原 ELF，恢复后按正式保留记录的 SHA256 校验。
构建/应用测试日志在 `logs/p1-hdmi/app-{tests,build,helper-tests}.log`。
临时测试脚本和完整采样保留在 `build/p1-hdmi/`、`logs/p1-hdmi/`，未加入主仓；
应用诊断提交在独立分支，主仓仅新增本轮两份记录和索引，没有提交或推送。
主仓必跑命令 `python3 -m unittest discover -s tests -p 'test_*.py'`：
163 tests，OK（skipped=5），日志 `logs/p1-hdmi/main-tests.log`；应用工作树和
VM 内核工作树均干净，文档 diff 空白检查通过。
