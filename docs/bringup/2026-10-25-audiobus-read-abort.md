# 2026-10-25：音频寄存器只读诊断触发重启

## 结论

本次 HDMI 音频调查中，执行者错误地把 debugfs 通用 regmap dump 当成安全只读接口，
在另一会话持有板锁期间读取 audiobus，触发 external abort 和自动重启，打断 UU 测量。
这是本次诊断造成的事故，不是 UU、One-KVM 或用户拔线引起；已向用户说明并致歉。
没有安装新内核、改变默认启动项或主动执行 reboot。

## 时间线与证据

时间均为板端 UTC，2026-10-25：

- 00:28:50 sudo journal 记录读取
  `/sys/kernel/debug/regmap/fe330000.audiobus/registers`，外层管道带 `head -18`。
- 00:28:51 内核最后保存的消息为
  `Internal error: synchronous external abort: ffffffff96000210 [#1] PREEMPT SMP`。
- 00:29:55 再次连通，仍为 `5.15.137-vim4kvm`；cmdline 含
  `reboot_mode=kernel_panic`。pstore 为空，不能据此编造具体故障寄存器或完整调用栈。
- 自动启动后的 manager、One-KVM、视频透传恢复 active，输入/输出恢复 4K60；
  UU 云端恢复 online，但客户端会话为 0，不能声称恢复了先前的实际观看会话。
- 已写 `/tmp/codex-kernel/hdmi-audio-incident.txt` 通知并行会话，重叠测量不能作为有效基线。

本地原始证据：`logs/passthrough-515/audio-regmap-reboot.log`、
`audio-regmap-pstore.log`（忽略目录，不随源码分发）。

## 约束修正

sysfs/debugfs 的 read 回调也可能直接访问 MMIO；未上电或受时钟门控的地址读取可能
引发同步 abort。通用 dump 的读取跨度由内核回调决定，管道 `head` 并不能限制 MMIO 访问。
本轮后续只使用已审阅的专用音频状态、具名 ALSA 控件、PCM 计数及 TX packet dump，
禁止再次读取通用 audiobus/regmap 寄存器范围。

锁协议也必须覆盖可能扰动硬件的诊断，不能因为命令表面上只有 `cat` 就绕过板锁。
后续音频实验持有 `/tmp/vim4-board.lock` 和 `/tmp/vim4-heavy.lock`；不再改 One-KVM，
也不通过绕过 macOS 辅助功能权限来重连 UU 客户端。

音频实现及后续验证见 [HDMI 音频桥](2026-10-25-vendor-passthrough-audio.md)。
