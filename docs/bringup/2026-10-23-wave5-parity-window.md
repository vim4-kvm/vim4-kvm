# 2026-10-23：Wave5 编码器批量窗口与 T7 硬件看门狗

前置为
[编码器离线 series](2026-10-23-wave5-encoder-parity.md)与
[一次性启动安全网](2026-10-23-display-m1-safety.md)。用户授权非 8 对齐可见尺寸、
B 帧、多实例、新控件及 One-KVM 冒烟；候选只一次性启动，不正式安装内核。

## 窗口与看门狗

Mac 长驻 lockf 进程先拿 `/tmp/vim4-heavy.lock` 再拿 `/tmp/vim4-board.lock`，
两把锁覆盖看门狗测试、完整构建、候选启动、采样、恢复与清理。未改变其他任务工作树。
UTC 18:43:46–20:13:07 持锁 89.35 分钟，超出原估计；完整构建及现场修正重建占主要增量。
主仓原工作树有其他任务未提交改动，pull --rebase 拒绝后改在独立文档 worktree
pull --rebase；没有 stash 他人文件。

入场默认内核 build ID `eeddb005df059a850853876d52ef603aa1af192b`，
五个启动/登记文件、One-KVM/manager 二进制哈希保存于
`logs/wave5-parity/board/baseline.json`。服务 one-kvm、vim4-manager、vim4-wave5-monitor
active，UDC configured，isolated=0、taint=0。内核分支 fetch 后为 `cb3b9f1a69051`，
候选九提交 rebase 后 HEAD `f48844c1e5dd6`。使用 display-m0 DTB，保持正式显示路径。

正式基线已有 `/dev/watchdog0`，内核未打开 WATCHDOG_SYSFS 属性，因此不能用缺少
identity/timeout/state 文件判断设备未注册。通过 WDIOC_GETSUPPORT 确认
`Meson GXBB Watchdog`；初始 RuntimeWatchdogUSec=0，无进程持有设备。

小 C 程序 open → GETSUPPORT → SETTIMEOUT(15) → KEEPALIVE 一次 → 保持 fd 打开 pause，
不再喂狗、不发送 magic close。启动前本地根文件系统 sync；不改 nowayout 或寄存器。
第一次证实复位后，再以 CLOCK_REALTIME 和串口接收时间补采精确计时：

```text
ARMED identity=Meson GXBB Watchdog timeout=15 monotonic=121.191862761 pid=1548
REALTIME=1792781260.170665098
WATCHDOG_RESET_SECONDS 15.035753011703491
loginSeconds 36.86680483818054
reboot_mode : watchdog_reboot
```

resetSeconds 从程序最后一次喂狗后记录时刻计至 Mac 收到 `T7:BL:`，包含串口传输；
loginSeconds 至串口登录提示，不等同于应用就绪。两次均无 systemctl reboot、panic
或人工 RESET；第一次重启后五文件、应用哈希、cmdline、build ID 与入场逐项相同。
精确计时的第二次用 `/run/systemd/system.conf.d/99-watchdog-test.conf` 临时关闭
已安装的 RuntimeWatchdog，重启后该临时文件自动消失。

授权正式安装 `board/60-vim4-watchdog.conf`：Runtime 30s、Reboot 60s，
不超过 T7 的 16bit 毫秒计数器 65 秒直接范围。board/install.sh 与 Ubuntu board
组件包使用同一文件，两种内核共用，不按 release 分叉。daemon-reexec 与后续重启实测：

```text
RuntimeWatchdogUSec=30s
RebootWatchdogUSec=1min
/dev/watchdog0: 1
Using hardware watchdog 'Meson GXBB Watchdog', version 0, device /dev/watchdog0
Watchdog running with a timeout of 30s.
```

测试程序、原始串口和计时 JSON 在忽略的 `build/wave5-parity/board/`、
`logs/wave5-parity/board/`；配置生成/打包离线测试为 `tests/test_board_watchdog.py`。
本轮没有启动 5.15，不能称厂商驱动停止喂狗也已验收；全局 PID 1 配置会在其启动生效。

## 候选与现场修正

使用 `display-once.py` 的准备、stage、preflight；私有副本仅把预期正式 build ID
调整为入场的 eeddb005，保留全部哈希、启动及服务检查。串口 RAM sysboot 选择私有
extlinux，默认 Image、DTB、extlinux、kernels.json、runtime-build.json 不覆盖。
Image、DTB、2334 个模块在独立 O= 目录同批构建，无替换单个模块。

最终候选 HEAD `0afc754640260`，build ID
`9f0f3552bb1bf60afe0f3cc1c191b3f8a5c7daba`；相比离线九提交增加四个小修正：

| 提交 | 实测问题与修正 |
|---|---|
| d7f34a537d878 | 空 QP 区间返回 ERANGE，保持失败设置的原值，满足控件 ioctl 合同 |
| 594b8c6d66d0c | drain 已完成且无持有 source 时 STREAMOFF 仍需销毁固件实例；否则同 fd 下一轮 S_FMT 被旧 STOP 状态拒绝。第二次 STREAMOFF 保持 NONE |
| d74a7b6d7d80c | 撤回新增 HEVC level 5.2 菜单。寄存器已请求 156，固件 SPS 仍输出 150；不发布未经证实的能力 |
| 0afc754640260 | AVC/HEVC 全局 MIN_QP 默认改为 0，允许 MAX_QP 设置其合法最小值；显式空区间仍拒绝 |

第一候选复现上述问题后均先回默认基线，再离线测试、重建、一次性启动。
最终非 streaming `v4l2-compliance -d /dev/video1`：

```text
Total for wave5-enc device /dev/video1: 46, Succeeded: 46, Failed: 0, Warnings: 0
```

这不是完整 streaming compliance；下面以真实 MMAP 队列、码流及像素验证补充。
13 提交分别 Signed-off-by、checkpatch --strict 零 error/warning/check；全量构建、
最终 Wave5 W=1 构建及驱动目录全部 `test_*.py` 通过。

## E02、B 帧与多实例

小 C 工具协商 CAPTURE/OUTPUT、设置 OUTPUT CROP、MMAP、STOP/drain、STREAMOFF，
验证 OUTPUT 全部归还、CAPTURE ERROR/LAST、时间戳、BFRAME 和忙态 ioctl。
图像含 8px 边框、左右不同亮度/色度、逐帧移动条；所有输出用 ffprobe、独立 SPS
解析器和 ffmpeg 解码抽样 Y/U/V 验证，不能仅以 DQBUF 成功判断尺寸正确。

最终候选十组各 24 帧全部通过：

| 可见尺寸 / 输入布局 | SPS coded / 可见裁剪 |
|---|---|
| 720×400 NV12 | 720×400，无裁剪 |
| 722×402 NV12、NV12M | 728×408，右/下各 6px |
| 1366×768 NV12、NV12M | 1368×768，右 2px |
| 1440×900 NV12 | 1440×904，下 4px |
| 1680×1050 NV12M | 1680×1056，下 6px |
| 1920×1080 NV12、3840×2160 NV12M | 可见尺寸相同，无裁剪 |
| 720×400 NV12，额外 raw 高度 8px | 720×400，确认 UV 基址使用完整 raw 存储高度 |

独立 SPS 的 HEVC conformance window 以 4:2:0 的 2px 单位转为上表像素值。
`ffprobe width/height` 与所有解码像素尺寸相同；最大采样平均误差约 Y 0.062、UV 0.111。
最终候选另测 left=2、top=4 的 1366×768 crop，通过边框和移动内容检查；
ffmpeg 对非零左裁剪须显式 `-flags +unaligned`，避免解码器默认指针对齐舍入影响验证。

最终候选同 fd 重复五轮 AVC 720×400 NV12M + HEVC 722×402 NV12，均 B=1，
共 240 帧，十轮 drain/STREAMOFF/REQBUFS(0)/重设格式全部成功。
另以两个进程均分配完成后由 START_GATE 同时放行，五轮并发 AVC B=0 + HEVC B=1，
1280×720 NV12M 各 48 帧，共 480 帧、十个码流，全部解码内容正确。
短至三帧的 HEVC B=1 drain 也通过；24 帧 HEVC 有 12 个 B 标记，AVC 有 11 个，
显示顺序图案与 source 时间戳相符。这些是功能/并发证据，不是多实例吞吐基准。

七组控件组合均产生正确的 24 帧：HEVC RC/VBV/全局与 picture QP 交集、CQ quality
20/90、high tier/PU/merge、AVC High/VBR/CPB、AVC fixed I/P/B QP+B、HEVC 多 slice。
实际 high-tier SPS flag=1，CQ=90 比 CQ=20 码流大；未逐 slice 验证实际 QP 或严格码率。
HEVC level 5.2 扩展撤回；既有 level 选择仍受固件行为限制（请求 AVC 4.1 曾输出 3.1），
不能据控件读回宣称 level 完全对齐。动态改参、复杂 GOP、多 B、ROI/LTR、VUI/SEI
依用户指示等后续离线轮次，本轮不扩展。

补测 722×402 的 ROTATE=90/270：SPS coded=416×736，ffprobe/解码可见 402×722，
24 帧 Y/UV 内容、边框与移动条均通过。现有固件命令 90 实际逆时针、270 实际顺时针，
与宏名 CLOCKWISE 相反；像素验证分别按实际方向建坐标，保留原映射，不宣称方向问题已修复。
AVC/HEVC 各 32 帧、GOP=1000，分别在输出第 6、12 帧后强制 IDR，
初始加两次请求均有 KEYFRAME，逐帧图案正确。
尚未单独覆盖共享同一 DMA-BUF fd 的多 plane 非零 offset；NV12/NV12M MMAP 与
One-KVM 实际输入链路已覆盖，不能把二者当作该特殊布局的验收。

## One-KVM、恢复与失败兜底

RAM EDID fixture 18 回读正确，Mac 物理 HDMI 持续运动图案；manager 输出原尺寸、60fps。
H.264 3840×2160 采样 15s：59.941 fps、零丢帧、freeze=0，前后像素哈希不同。
切 HEVC 后写 `timeout_command=256`，不刷新网页、不重启服务：

```text
[400.557512] send_firmware_command: command: 'W5_ENC_PIC', timed out
[400.559229] power cycle and firmware reload complete; reopen old instances
automatic-reopen: driverMs=600 decodeMs=1827 pid=2968
```

内核日志间隔为 1.717ms；600ms 是 SSH 轮询到恢复日志的主机观测耗时，不是硬件复位本体。
1.827s 后 4K 图像继续解码，One-KVM PID 未变。恢复后连续 HEVC 300s：

```text
framesDecoded 229 -> 18230; 3840x2160; same SSRC
fps=60.00101210277234; dropped=0 -> 0; freezes=1 -> 1
pixelHash=1990289475 -> 3568113187
```

freeze=1 为此前故障注入留下的累计值，五分钟期间没有新增。
随后 `recovery_fail_step=2` + `timeout_command=256`：

```text
[703.345777] W5_ENC_PIC timed out
[703.346145] power-cycle recovery failed: -5
[703.346358] isolated: command acknowledgment timeout, command 0x100; DMA storage retained until reboot
```

isolated=1、taint=0、SSH/manager API 可用、One-KVM PID 仍为 2968。
原生 HID 窗口实收键盘 down/up、绝对及相对移动、点击、滚轮；UDC configured。
隔离后正常 reboot，RAM 再选同一候选补测上面的旋转/IDR，确认隔离关机路径没有卡住。
本轮无真实固件硬锁、无新增 Oops/WARN；超时及失败均由既有一次性注入触发。

代表性命令（均在外层两把 lockf 内执行；测试工具及原始输出保留在忽略目录）：

```sh
ssh vim4 'sudo /var/tmp/wave5-watchdog-expire'
ssh vim4 'sudo /var/tmp/wave5-parity-encode /dev/video1 h265 722 402 24 0 0 1 /var/tmp/crop'
ssh vim4 'sudo v4l2-compliance -d /dev/video1'
python3 build/display-m1/window-7/boot-once.py default logs/wave5-parity/board/final-default-uart.log
```

看门狗实际通过 nohup/setsid 启动并由串口计时脚本记录，fd 保持打开。
看门狗已由 PID 1 正式持有后，不可直接再次运行该独占测试程序。

## 恢复与交付

最终正常重启回默认 build ID `eeddb005df059a850853876d52ef603aa1af192b`，
五个受保护文件、cmdline、两个应用二进制哈希与入场相同；one-kvm、vim4-manager、
vim4-wave5-monitor active，UDC configured，isolated=0、taint=0。
systemd 看门狗 Runtime 30s / Reboot 60s、PID 1 持有跨重启保留。
最终状态及串口在 `restored.json`、`final-default-uart.log`。
回基线动态 HEVC 3840×2160 30s：59.988 fps，零新增 freeze/drop/loss；
键盘、绝对/相对鼠标、点击、滚轮再次通过。初次运动源沿用候选 EDID 名称未启动，
改用基线实际显示器名 RTK UHD HDR 后重跑通过。候选和临时文件清理后再次逐项核对基线，
见 `final-state.json`，两把锁已释放。

过期 PCM 回退点与中间目录先归档至 Mac，SHA256
`944b57520921515eaed659fcf4d8da516e6efa7c15ee49994cb4b752d240a1df`，核对无进程引用后删除。
保留唯一正式内核回退 `/var/backups/vim4-kvm-tmds-final`，及其 rollback.sh 实际引用的
`/var/tmp/vim4-deploy-7.3-final`；不误删回退依赖，不改 U-Boot/PD 备份。
本轮候选、测试程序与码流先取证再清理；不改变 sources.toml/workspace.toml 已部署锁。

主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：227 项，10 skipped，217 通过。
内核已 atomic push，remote 实查 `vim4-wave5-encoder-parity` 与 `vim4-kvm-7.3`
均为 `0afc7546402608f52ce99596d0f153a519be3e81`。主分支从 cb3b9f1a 正常快进，
功能分支 rebase 以精确旧值 force-with-lease 更新；未切换主工作树，未正式部署候选内核。
