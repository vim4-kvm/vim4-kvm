# 错题本

适用范围随实现变化；历史证据见 [上板记录](docs/bringup-log.md)。
修改相关实现后重新验证，不把观察当永久结论。

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| 向 Ubuntu 根目录直接解内核包，动态程序失效 | tar 替换 /lib 符号链接。安装必须带 --keep-directory-symlink，并保留 Stock 启动项 | [内核安装](docs/kernel.md)、tools/kernel-install.sh |
| sudo 管道混用 heredoc，密码写进配置 | sudo 缓存改变 stdin 消费行为。配置先 scp 再 sudo cp，不与密码共用 stdin | [部署](docs/subsystems/deployment.md) |
| 串口超时后立刻发下一条命令 | 板上命令可能仍在执行。长任务后台运行并轮询结果，确认 shell 空闲 | tools/uart-run.py |
| sudo -b 启动长期程序，SSH 不退出 | 后台进程持有会话描述符。用 nohup setsid 并重定向三路标准流 | [部署](docs/subsystems/deployment.md) |
| 多任务并发使用编码器 | 硬件和 /tmp/vpu_mutex.map 共享。协调独占，以 khadas 运行，不删除活跃锁文件 | [应用](docs/subsystems/application.md) |
| 30fps 编码预算配 60fps 输入 | 旧 amlvenc 造成实际码率偏大。修正插件并传入输入帧率；预算不是采集节奏 | [音视频](docs/subsystems/video.md) |
| 把像素回读完成时间当网络延迟 | 4K 回读和 JS 调度扰动测量。低频采样并分报回读成本；并行测试结果作废 | [测量方法](docs/latency.md) |
| 用 game_mode 0 当作关闭低延迟的实验对照 | 0 恢复自动策略，实际模式可能是 0xb。核对驱动 state 中的当前模式，不能仅看全局参数；完整帧模式使用 0x3 | [采集延迟对照](docs/latency.md#board-side-isolation-and-completed-frame-mode) |
| 认为 USB-C 供电必须另接 VIN 才能传键鼠 | 本项目已验证开机 PD 协商后单线供电和 HID，不代表所有供电、热插拔场景 | [USB-PD](docs/usb-pd.md) |
| 把 video71 当 HDMI 输入 | vdin1 是输出回写；无 HDMI 输出时用 vdin0 → vfm_cap，HDMI RX 为 port 1 | [硬件](docs/hardware.md) |
| HDMI 有音频包、WebRTC 已连接但始终静音 | TDM-B 默认读外部引脚。HDMI 服务 ExecStartPre 在 ALSA restore 后选 hdmirx，再允许 NanoKVM 启动；零峰值录音不能证明声音正常 | [功能与音频状态](docs/feature-status.md)、packaging/ubuntu/check-audio-startup.py |
| 直接用 OOWOW /shell/write 或未经核对流式刷盘 | 项目曾遇到 GPT 被清空。使用专用校验刷机脚本，重装需用户确认 | tools/oowow-flash.sh、上板记录 |
| USB 功能重新绑定后关闭 /dev/hidg*，内核 list_del panic | 5.15 f_hid 在 hidg_bind 中重新初始化等待队列，仍注册在 epoll 的 fd 会破坏链表。重新枚举前关闭 HID 文件；内核侧修复前不要在 gadget 切换时保持 HID 打开 | hid.Reenumerate、logs/uart-mic-crash.log |
| 部署后不久内核 panic，刚装的 sudoers 变成 0 字节 | 根分区 data=writeback，未刷盘的新文件会被清零。部署后 sync；崩溃后用 dpkg --verify 检查 conffile，再按包内容恢复 | [上板记录](docs/bringup-log.md) |
