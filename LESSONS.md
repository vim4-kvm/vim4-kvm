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
| USB 功能重新绑定后关闭 /dev/hidg*，内核 list_del panic | 5.15 f_hid 同时重置等待队列和仍被打开的 cdev。必须同时修复队列生命周期（dbcef7c1f）与独立 cdev 分配（b86c7e5bd）；只修前者实测仍会崩溃。保留应用保护，重启进入新 Image 才生效 | hid.Reenumerate、tools/hid-rebind-check.py、[内核](docs/kernel.md) |
| 部署后不久内核 panic，刚装的 sudoers 变成 0 字节 | 原根分区 data=writeback、commit=600。新部署配置 ordered/commit=5；所有组件安装成功前 sync，网页更新复核文件后再重启。它不保证升级原子性，也不证明其他文件没有损坏 | tools/rootfs-policy.py、[上板记录](docs/bringup-log.md) |
| 沿用上游设备固件代码，在 Ubuntu 上以 khadas 运行时功能静默失败 | 设备固件默认 root 与自带工具（写 /proc/sys、tailscale set --login-server、reboot）。逐条走一遍特权路径，改经 sudo 助手；只有单元测试不足以发现 | kvm/VIM4.md、tools/jetkvm-smoke.mjs |
| 他人正在构建同一工作区时修改共享接口 | 构建读取工作树，半成品会使对方打包失败。跨仓库接口改动一次写完再保存，或先在独立 worktree 中修改 | logs/nanokvm-migration-package.log |
| 两个 KVM 共用 8080，切换后绑定失败或仍显示旧界面 | systemd Conflicts 不保证旧进程退出后才启动新进程。助手先等待 stop 完成再启动，失败时不启动替代程序；管理器链接区分应用，NanoKVM 首页禁用缓存 | vim4-manager/deploy/test_helper.py、tools/kvm-switch-check.mjs |
| 从 HDR 分支构建管理器后，已部署的趋势图表消失 | 图表在另一工作树的未提交改动中。部署前同时核对固定分支与已部署功能，合并到同一可构建提交；保留原工作树不等于保留线上功能 | vim4-manager onekvm 分支、logs/one-kvm/manager-final.png |
| GE2D 缩放单次成功，切编码后进程报 safe_close EBADF | 厂商 DMA 分配器把同一个 fd 同时交给 GstDmaBufMemory 和附属 qdata 释放。One-KVM 使用私有兼容分配器，fd 只由标准 GStreamer memory 关闭；需验证重复切换与缓冲区持有周期 | One-KVM/deploy/vim4/test-dma-allocator.c、tools/one-kvm-settings-check.mjs |
| 厂商 JPEG 插件直接输入 DMA 后只出 4 帧 | JPEG NEW_CMD 的直接 DMA 路径未释放导入，耗尽 VDIN 的 4 个采集缓冲。vim4jpegenc 使用 CONFIG_DMA_INPUT / RELEASE_DMA_INPUT 管理每帧生命周期，异常时先关闭编码器再归还输入；验证连续帧和重复启停 | gst-plugin-venc/tests/jpeg-hardware.py、logs/mjpeg-hardware/ |
| 编码器超频后帧率提升，就以为可用 | 750/800 MHz 下同一输入的码流已不再一致，但不报错、帧数正常。超频必须重复编码同一段录制输入并比较码流哈希，同时用低频对照排除时钟源问题 | [编码实验记录](docs/encoder-experiments.md#wave521-时钟与-4k-编码耗时2026-10-14) |
| PiKVM 原有视频能播放，但重新连接找不到共享内存 | 普通用户服务不能依赖登录会话的 IPC 生命周期。整组服务使用私有 /dev/shm，验证音频启停与 MJPEG/WebRTC 重连 | kvmd/deploy/vim4/vim4-pikvm.service、logs/pikvm/full-smoke-rate.log |
| HDMI 输入稳定，编码器却不断重建 | sysfs 的 centi-Hz 测量在 5998/5999 等值之间抖动。速率变化检测需要容差；MJPEG 测试必须匹配真实输入尺寸，不能把离线占位图判为成功 | ustreamer/src/ustreamer/vim4.c、tools/pikvm-smoke.mjs |
| USB 主机卸载卷后仍不能弹出 PiKVM 镜像 | unmount 不清除 SCSI 防弹出锁；必须 host eject。厂商内核 host eject 不发 configfs inotify，需要在现有轮询中核对 LUN file | kvmd/kvmd/plugins/msd/otg/__init__.py |
| 给 pion SettingEngine.SetNet 包装 UDP 套接字后进程空闲占满 3 核 | mDNS 的 ipv4.PacketConn 需要具体的 *net.UDPConn，包装后读取持续出错且非 ErrClosed，读循环空转。只包装单播套接字，部署前查空闲 CPU 与 pprof | NanoKVM service/stream/webrtc/batch_vim4.go |
