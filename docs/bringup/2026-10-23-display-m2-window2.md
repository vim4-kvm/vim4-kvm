# 2026-10-23：M2 颜色修正与第二个一次性窗口

接续 [首次窗口](2026-10-23-display-m2-window1.md)。本窗口只临时启动候选，
不正式部署；正式恢复目标为 RX 修复 `b1300eb808f43`、build ID
`eeddb005df059a850853876d52ef603aa1af192b`，见
[当前正式部署](2026-10-23-hdmirx-vendor-comparison.md)。

## 颜色根因与输出约定

厂商 common_drivers `4cfb128d36f8` 的 `osd_hw.c:set_vpp_osd1_rgb2yuv()`
采用 `RGB709_to_YUV709l_coeff`，将 RGB framebuffer 转成 BT.709 limited；
`hdmi_tx_hw.c:config_hdmi21_tx()` 固定输入为 YUV444 limited，输出 YUV444 时
CSC0/1 bypass。旧 M2 保留了 OSD/VPP 矩阵，却假定 VPP 是 RGB，并发送 RGB AVI；
首次窗口的灰条偏红、黑色偏青与此不一致路径相符。

修复保留厂商 YUV444 limited 路径，CSC0/1 仍旁路；桥输入总线改为
`MEDIA_BUS_FMT_YUV8_1X24`，AVI 指明 YUV444、BT.709、YCC limited，RGB Q 使用
default。OSD framebuffer 仍是 RGB888/XRGB8888/XBGR8888，和 TX 总线编码不同。
没有写共享 VPP 矩阵、VDIN 仲裁或采集时钟。

当前仅支持这一输出组合；原生 connector 的 `color format` 属性仅提供 AUTO 和
YCbCr444，AUTO 也只能选择 YCbCr444。不暴露 `Broadcast RGB` 或可切换 colorspace
属性，不能通过属性声称支持 RGB full/limited。EDID 不支持 HDMI YUV444 的接收端
在 `mode_valid` 返回 `MODE_BAD` 并给出原因，包含 RGB-only、DVI、422/420-only。
后续 RGB 输出需要实现并测试独立 CSC，不能只切 AVI 元数据。

`test_hdmitx21_color.py` 编译执行实际 CSC 配置和 AVI 构造函数，覆盖 32 种
HDMI/格式能力组合，以及 720p/1080p/4K、scrambling 开关下的矩阵旁路和范围声明。
原 PLL/VENC harness 同时验证实际 `mode_valid` 拒绝 RGB-only 与 DVI。

## 物理比较方法

使用普通 Chrome 的 localhost 抓帧页，禁止用 Playwright 请求摄像头或麦克风。
计划对 SMPTE 上方七条与 GPU GLES 八条已知 RGB 色条，取各条内部 16×16 像素中位数，
避开边界缩放和 4:2:2 色度插值。预先规定每通道误差不超过 16/255，灰条三通道
差不超过 8；GPU 黑条不超过 8。该容差包含 HDMI→UVC→浏览器转换，不能代表
总线级精确色度计量。不同分辨率必须分别核验，不用一张“有画面”截图代替。

本轮尝试用 `eglSwapBuffers` interposer 注入 GPU 色条，但 glmark2 的函数加载路径
没有调用该 hook，日志中没有注入标记。因此实际 GPU 测试只覆盖 glmark2 场景及
Panfrost/GBM/PRIME/page-flip 路径，不覆盖已知 RGB 色条。下次应直接使用 GLES
色条客户端或私有场景 shader，先核对执行标记再采样。

TX 音频通过 BUER USB 采集卡录音；页面先核对 audio track 标签，拒绝未知输入，
禁用回声消除、降噪和自动增益。MediaRecorder 录制两秒 Opus 片段，再离线解码
48k 单声道并 FFT，区分 TX 997Hz 与 HDMI-IN 440Hz。PCM RUNNING 不能代替物理证据。

## 窗口结果

### 构建与一次性启动

`vim4-display-m2` 已 rebase 到 `origin/vim4-kvm-7.3` 的
`cb3b9f1a69051a0263dd448d88c944e4a495d9f2`（包含 RX 修复 `b1300eb808f43`）。
四个已合入的 HPD/EDID 提交被跳过，保留 16 个原生 M2 提交和本轮颜色修复
`bb20f254c6dd41806c6b59257b9568c6cf53a39d`，功能分支已推送。
独立源码 `~/src/linux-7.3-display-m2`、输出 `~/build/kernel-display-m2`。
Image、全部 DTB 和 2334 个模块构建通过；显示 transport/DDC/audio/HPD、RDMA、
NULL fb/timeout、PLL/VENC/PHY 厂商对照、RX/Wave5 离线测试和 binding/schema
均通过。17 个提交逐个 checkpatch，全部 0 errors、0 warnings；一次性启动 Linux
测试 6 项通过。候选 build ID 为 `1006b91489503a61db13695b238b5408ae26db6d`。

| 文件 | SHA256 |
|---|---|
| Image | `b66fd445bb5bbf4922b7cd47ff356be0cd298bc89ee1c6eb32d0d263df6e26f4` |
| 原始 M2 DTB | `8235b78e032b0c90bee426f4736ca814a295aae93b4c416830b6a87364725c31` |
| 修正板级 MAC 的安装 DTB | `2e011ba6e03438a89d43df4256cda15007d5343a281f308bde0c3e757bd88789` |
| 模块归档 | `7dfa19bc114976a7ebc3678280479f99342e9b3cea5339fd591b86acfe0c647d` |

等待另一 Wave5 窗口释放锁后，全程持有 Mac `vim4-heavy.lock` 与 `vim4-board.lock`。
候选模块只读 bind；默认 Image/DTB/extlinux 和运行时登记没有改动。串口仅执行 RAM 命令：

```text
sysboot mmc 1:2 any ${pxefile_addr_r} /var/lib/vim4-kvm/display-m1/1006b91489503a61db13695b238b5408ae26db6d/extlinux.conf; reset
AUTOBOOT_INTERRUPTED
BOOT_LOGIN_REACHED
```

本窗口开始前正式系统已启用 [硬件看门狗](2026-10-23-wave5-parity-window.md)。
候选串口确认 PID 1 使用 `/dev/watchdog0`、30s 超时；恢复后仍为 Runtime 30s、
Reboot 60s，设备由 PID 1 持有。本轮没有主动触发 RESET 或看门狗超时，验证的是
正常重启离开 RAM 一次性入口后回默认基线。

### 针对性结果与证据边界

HPD connected，EDID 256 字节、monitor `HDMI TO USB`。DRM `color format` 枚举为
`AUTO=0 / YUV 4:4:4=2`，默认 AUTO。该采集卡不提供本次目标中的 720p60、1440p60、
4K60，且没有 SCDC、最大 TMDS 300MHz，因此没有强制表外模式。

| 输出模式 | 结果 |
|---|---|
| 1280×720p50 | atomic modeset、关闭/RMFB 返回 0；无新物理帧 |
| 1920×1080p50 | atomic modeset、关闭/RMFB 返回 0；无新物理帧 |
| 1920×1080p60 | atomic modeset、关闭/RMFB 返回 0；无新物理帧 |
| 3840×2160p30 | atomic modeset、关闭/RMFB 返回 0；无新物理帧 |
| 720p60 / 1440p60 / 4K60 | SKIP_NOT_IN_EDID；4K60/SCDC 未验 |

示例板上命令（connector 39、CRTC 37、plane 35）：

```sh
modetest -M meson-t7-handoff -a -F smpte \
  -s39@37:1920x1080-60@XR24 -P35@37:1920x1080@XR24
```

1080p60 翻页运行 20s，19 个速率样本为首个 60.55Hz、随后 60.01Hz 和 17 个
60.00Hz；关闭返回 0，没有 NULL fb、锁存超时或 oops。第一次 fixture 因启动样本
60.56 超过 60.5 阈值而失败；仅排除首个启动区间后重跑通过。此处是 flip 事件速率，
不能代替采集卡上相邻物理帧确实交替的证明。

GPU 为 `Mali-G52 r1 (Panfrost)`、Mesa 25.2.8、OpenGL ES 3.1，1920×1080。
glmark2 的 build/texture 各 10s，分别 60/61fps，分数 **59**，退出 0。
strace 可见 card0 `PRIME_HANDLE_TO_FD` → renderD128 `PRIME_FD_TO_HANDLE`、
`ADDFB2` 和 page flip，支持 GPU 缓冲直接 scanout 路径。带 vsync、strace 的短跑
分数不作为性能基线；没有物理 GPU 画面颜色证据。

TX 用卡 ID 避免与 HDMI-IN 混淆，开启 FRDDR_A 与 TOHDMITX 路由后执行：

```sh
speaker-test -Dhw:VIM4HDMITX,0 -c2 -r48000 -FS16_LE \
  -tsine -f997 -p20000 -b80000 -l3
```

播放约 18s、退出 0；TX 与 RX PCM 同时 RUNNING，TX 为 48kHz/S16_LE/2ch，
ELD 声明 LPCM 2ch、32/44.1/48kHz。没有 Mac 音频录制或 FFT，不能据此判定 TX 出声。

模式切换、翻页、GPU 和 TX 测试期间，HDMI-IN 输入为动态 4K60 与 440Hz 音频。
180s H.264 WebRTC 采样为 3840×2160、**59.992495fps**，冻结、丢帧、丢包、PLI
增量均 0。211 个 RX/VDIN 监测样本中 `stream_stops=0`、`stream_error=0`，
末尾 `stream_frames=12235`、`direct_dma=1`、`stream_copy_bytes=0`；内核日志
`tmds-invalid` 次数为 **0**，无新增 oops/BUG/WARNING/锁存超时。
VDIN 混合原因计数 `invalid_frames` 从 0 到 5539，不能将它当作 TMDS 失锁次数或
声称该计数也为零。候选未开启浏览器解码音频采样，只证明 RX PCM 工作，不证明其波形连续。

### 物理抓帧阻塞

使用 `open -a "Google Chrome" http://localhost:8766/` 打开普通 Chrome；本窗口
服务器没有收到任何新图像、音频片段或页面错误 POST，旧帧停留在前一窗口。
Chrome AppleEvent 查询超时，System Events 无辅助功能权限，无法无人值守完成页面
状态诊断。未使用 Playwright 打开摄像头/麦克风，也没有改系统权限或重启用户 Chrome。
因此每种模式的 RGB 数值、GPU 物理颜色、TX 997Hz 均标记 **未验证**，没有填造测量值。
预设颜色比较脚本仅在前一窗口偏色灰条上验证能拒绝（最大通道误差 65），没有本轮正样本。

NEED_USER：回到 Mac 后确认普通 Chrome 抓帧页的采集卡视频及 BUER 音频轨道可用，
再安排短窗口；重新上传图像和音频后才运行 RGB 比较与 FFT。用户离开期间热拔插按要求跳过。

### 恢复、清理与合入结论

正常重启回默认后确认 build ID `eeddb005df059a850853876d52ef603aa1af192b`，
对应已部署 `b1300eb808f43`。`/boot/edge/Image`、`/boot/edge/vim4.dtb`、
`/boot/extlinux/extlinux.conf`、`kernels.json`、`runtime-build.json` 五项哈希均与窗口前一致。
候选只读模块挂载消失，模块重新来自板上根分区。原 ALSA state 恢复且 SHA256 一致。

恢复后动态 4K60 H.264 连续 300s 为 **59.999253fps**，冻结、丢帧、丢包均 0，
WebRTC 解码音频峰值 0.100708。真实键盘按下/抬起、绝对/相对鼠标、点击及滚轮通过。
`one-kvm`、`vim4-manager`、`vim4-wave5-monitor` 均 active，UDC configured，
isolated=0、taint=0，无新增 oops。这里的画面证据来自 KVM 接收端，不是 HDMI-OUT 截图。

停止本窗口输入源、恢复原 `/tmp/display-grab/server.py` 服务及原页面文件；普通 Chrome
自动关闭窗口失败，可能仍留有测试页，需用户自行关闭。只删除本窗口候选目录和
`/var/tmp/display-m2-window-2`，释放约 193MB；根分区余量约 18GiB，
`/var/backups/vim4-kvm-*` 仅保留当前正式回退点 `vim4-kvm-tmds-final`，保留其依赖目录。
双锁均已释放。

主仓基于 `33d02e7` 执行 `python3 -m unittest discover -s tests -p 'test_*.py'`：
227 项，217 通过、10 跳过；`git diff --check` 通过。

本轮代码已推送 `vim4-display-m2`，但物理颜色门禁尚未满足，**没有将原生 M2/颜色/TX
音频提交提升到 `vim4-kvm-7.3`**；该分支保持既有已验 HPD/EDID 前缀，不部署候选。
收尾 fetch 时正式分支已由另一任务推进到 `0afc754640260`，新增 13 个 Wave5 提交；
本候选不包含该批提交，下一次候选须 rebase、重建并重跑离线测试后再进入窗口。
下一窗口先确认 Mac 实时图像和音频上传，再一次性启动：四个 EDID 模式逐个 RGB 比较、
GPU 已知色条、997Hz 物理录音、60Hz 物理翻页及 RX 共存；用户在场时增加 HPD 拔插。

离线原始证据保存在主工作区忽略目录 `logs/display/m2/window-2/`：`build.log`、
`build.json`、`oneshot-linux-tests.log`、`candidate-uart.log`、`mode-results.json`、
`native-1080p60-flip.json`、`gpu.log`/`gpu.trace`、`audio-live-state.log`、
`candidate-coexistence.log`、`candidate-monitor.jsonl`、`baseline-uart.log`、
`restored-smoke.log`、`restored-hid.log`、`restored-final-health.log`、`cleanup.log`。
