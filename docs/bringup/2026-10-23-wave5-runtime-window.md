# 2026-10-23：Wave5 运行时电源循环恢复针对性窗口

前置：[复位合同与离线实现](2026-10-23-wave5-genpd-recovery.md)、
[一次性启动安全网](2026-10-23-display-m1-safety.md)。本轮按用户指定范围做五轮
软件超时注入、一次失败兜底和约五分钟冒烟；不使用会真实挂死固件的输入，不正式部署。

## 版本与窗口

拿锁时 fetch 的 `origin/vim4-kvm-7.3` 仍为 `c1315a95691e03153dcd9eb577a6352ecdb39147`，
feature 已基于它，无需 rebase。独立 worktree 为
`/home/deepdream/src/linux-7.3-wave5-runtime-recovery`，O 为
`/home/deepdream/build/kernel-wave5-runtime-recovery`；未修改或切换主内核工作树。

- 分支 `vim4-wave5-runtime-recovery`，候选 `39d42b6393f92c4a5bc4bf6d73877dcb83c7d257`。
- 三个功能提交：`740e2fb4dd9c9` 拒绝未排空双核拓扑、`6f1ab4a99e1d4` 验证 T7 Wave
  电源状态、`39d42b6393f92` 排空总线后独立 genpd 循环与冷加载。
- 本次重新构建 build ID `9bbf0b8cd8ed9ffc5b5816a2f90e083167f2dbba`，release
  `7.3.0-vim4kvm-uhd1+`，完整模块 2334 个；沿用 display-m0 DTB，与默认 DTB 哈希相同。
- 默认运行基线仍为 `aa2f875bec2fc`，build ID
  `7b8372b894c98ffae12e636a325c86f2b6c85e00`，One-KVM `382efb70e7ebb`、manager `9b141c5833c0`。

Mac 以 `lockf /tmp/vim4-heavy.lock lockf /tmp/vim4-board.lock` 的长驻持锁进程覆盖
构建、一次性启动、全部测量与恢复。14:40:14 UTC 拿到双锁；排队期间未改板子状态。
启动脚本从实际基线读取 build ID、cmdline、五个受保护文件哈希和应用可执行文件哈希。
`display-once.py` 使用该基线的精确检查（此次恰与工具内置值相同），不是放宽 gate。

## 命令与观察口径

构建在 VM 执行 `make O=… ARCH=arm64 -j4 Image dtbs modules`，随后运行所有 Wave5
`test_*.py`、`drivers/pmdomain/amlogic/test_secure_pwrc.py` 和相对主分支的严格 checkpatch。
通过 `package-final.py` 校验 modules.order 的完整清单；静态 PID 1 用 gcc 编译。
窗口脚本和原始证据分别保留在忽略目录 `build/wave5-runtime/`、
`logs/wave5-runtime/board-window/`，总日志 `logs/wave5-runtime/board-window.log`。

候选只暂存到私有根目录，经 UART 执行：

```text
sysboot mmc 1:2 any ${pxefile_addr_r} /var/lib/vim4-kvm/display-m1/9bbf0b8cd8ed9ffc5b5816a2f90e083167f2dbba/extlinux.conf; reset
```

实际输出 `AUTOBOOT_INTERRUPTED`、`RAM_SYSBOOT_SENT`、`BOOT_LOGIN_REACHED`。
不执行 saveenv；默认 Image、DTB、extlinux、运行登记和持久模块目录不替换。
候选 PID 1 在 systemd 前 bind 本次完整模块，重启即消失。

RGB8 3840×2160@60 RAM EDID fixture 18，Mac 物理 VIM4 显示器运行 motion source。
Chrome 接收 One-KVM WebRTC；每轮保持连接注入，不重启 One-KVM、不手工重开编码器。
轮次间交替 H.264/H.265，恢复后各采样 15 秒；解码帧数、SSRC、尺寸、codec 与
64×36 视频像素摘要共同检查。这里的“解码”指浏览器解码，未测 Wave5 硬件解码器。

```sh
ssh vim4 "sudo sh -c 'echo 256 > /sys/module/wave5/parameters/timeout_command'"
```

256 为 ENC_PIC；命令真实完成后模拟超时，触发实际总线排空、genpd OFF/ON、固件冷加载。
成功日志只有在 OFF/ON notifier、secure PWRC 状态、冷启动 PC、INIT/GET_VPU_INFO
检查通过后才打印。该注入不证明真正卡死时总线一定能排空，失败仍须隔离。

## 五轮结果

| 轮次 | 编码 | 内核超时→冷加载完成 | 主机观测驱动完成 | 主机观测解码恢复 | 恢复后解码 fps |
|---|---|---:|---:|---:|---:|
| 1 | H.264 | 1.686 ms | 642 ms | 1660 ms | 60.0113 |
| 2 | H.265 | 1.370 ms | 628 ms | 1646 ms | 60.0121 |
| 3 | H.264 | 1.351 ms | 641 ms | 1661 ms | 60.0088 |
| 4 | H.265 | 1.342 ms | 616 ms | 1638 ms | 60.0140 |
| 5 | H.264 | 1.398 ms | 625 ms | 1638 ms | 60.0185 |

内核耗时取 journal 单调时钟，包含恢复 worker 调度至完成；主机值从启动注入 SSH
计时，含 SSH、journal 查询和 250 ms 解码轮询，属于观测上界，不能混称裸硬件复位耗时。
注入前 60.0182 fps。五次恢复均保持 One-KVM MainPID，浏览器在同一连接恢复帧推进；
未通过刷新网页或服务重启代偿。第五轮后 `isolated=0`、`recovering=0`、taint=0，
`T7_DOS_WAVE on / fe310000.video-codec active`。CMA 剩余 252476 KiB 仅为单点观察，
不作为长期无泄漏结论。

内核第一轮原始输出：

```text
[50.957061] vdec fe310000.video-codec: send_firmware_command: command: 'W5_ENC_PIC', timed out
[50.958747] vdec fe310000.video-codec: power cycle and firmware reload complete; reopen old instances
```

## 冒烟、失败兜底与基线恢复

第五轮后保持同一 H.264 SSRC 连续 300 秒，解码 18001 帧、60.00155 fps，画面像素
摘要变化，截图 `smoke.png` 可见运动色块和计数条。然后注入一次失败兜底：

```sh
ssh vim4 "sudo sh -c 'echo 2 > /sys/module/wave5/parameters/recovery_fail_step; echo 256 > /sys/module/wave5/parameters/timeout_command'"
```

step 2 在总线排空后、断电前返回错误。主机 707 ms 观测到隔离，内核输出：

```text
[479.030723] vdec fe310000.video-codec: send_firmware_command: command: 'W5_ENC_PIC', timed out
[479.031006] vdec fe310000.video-codec: power-cycle recovery failed: -5
[479.031224] vdec fe310000.video-codec: isolated: command acknowledgment timeout, command 0x100; DMA storage retained until reboot
```

`quarantined.json` 确认候选 build ID、`isolated=1`、taint=0、三个服务 active、UDC
configured；One-KVM PID 不变，API 仍响应，流状态转为 no_signal。候选下真实键盘按下/松开、
绝对/相对鼠标、点击、滚轮全部通过。kernel journal 无 Oops/BUG/panic/WARNING，
仅有预期六次超时和一次失败隔离。未在板上逐项注入其余 recovery_fail_step。
应用 journal 在隔离后持续报 `Input/output error (os error 5)`，而不是阻塞在驱动等待。

为避免隔离后重启候选浪费窗口，顺序是五轮成功→五分钟冒烟→失败隔离→重启默认基线。
从正常 `systemctl reboot --no-block` 到 UART login 为 **25.466 秒**，无需强制复位。
`restored.json` 确认 build ID 回到 `7b8372b894c98ffae12e636a325c86f2b6c85e00`、
新 boot ID `f8195e3f-87dc-4500-8a6d-e8c507f8ee36`、原 cmdline（无 init override）、
`isolated=0`、taint=0、one-kvm/manager/monitor active、UDC configured。
五个受保护文件哈希和两个运行应用哈希逐项与入场一致。恢复后再次完成真实 HID 测试。

```text
FIVE_RECOVERIES_SMOKE_AND_FAILURE_FALLBACK_PASS
DEFAULT_REBOOT_SECONDS 25.46597712498624
DEFAULT_BASELINE_BUILD_FILES_APPS_UDC_HID_RESTORED
```

确认恢复后，仅删除本候选私有目录与 `/var/tmp/wave5-runtime-trial`，释放双锁。
本次持锁约 15 分钟（含构建、打包），未占满 60 分钟预算。恢复证据是交还板子时的快照；
后续采集任务可继续独立使用共享板子，不将其后来状态归入本窗口。

## 离线验证与交付边界

本次完整编译通过。Wave5 DMA 范围、32 项 cleanup、几何/关闭顺序、隔离与恢复生命周期、
冷加载八个失败边界及五种一次性注入、51 项 FIO/reset 顺序用例、secure PWRC 12 项
状态/失败用例与非目标域兼容通过。严格 checkpatch：0 errors / 0 warnings / 0 checks，
1344 行，只忽略新增文件的 FILE_PATH_CHANGES 提示。

全部针对性门禁通过、交还基线后，再次 fetch 确认主分支仍是原基点；以普通 fast-forward
推送将 `origin/vim4-kvm-7.3` 从 `c1315a95691e0` 推进到
[`39d42b6393f92c4a5bc4bf6d73877dcb83c7d257`](https://github.com/vim4-kvm/linux/commit/39d42b6393f92c4a5bc4bf6d73877dcb83c7d257)。
功能分支与主分支的远端 ls-remote 均为该提交，未另造 merge commit，未改本地主工作树。
原始推送输出在 `logs/wave5-runtime/board-merge.log`。主仓 pull 后全套测试 223 项通过、6 skipped，
本记录与索引提交到 main；没有将测试包正式安装到默认启动项。

未测真实固件死锁、双实例压力、长时间 DMA 泄漏、挂死的 secure SMC 调用、硬件解码器、
九类全量回归。本轮只允许全部针对性门禁通过后合入并推送，部署留给下一个窗口；
不更新 sources.toml/workspace.toml 已部署锁。
