# 错题本

这里只放跨子系统的教训；子系统专属错题在对应 [子系统文档](docs/subsystems/) 末尾的「错题」一节，
随路由按需读取。适用范围随实现变化，修改相关实现后重新验证；历史证据见 [上板记录索引](docs/bringup/README.md)。
新教训先判断归属：只影响一个子系统的写进该子系统文档。

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| U-Boot 主机测试通过便刷入 eMMC，随后早期循环复位 | 主机 mock 不覆盖上电顺序、总线不返回或供电复位。候选先从 microSD 验证，失败断电拔卡回退；FUNCTION+RESET 依赖 eMMC U-Boot 到达按键检测，早期故障须拔 SD、按住 FUNCTION 冷上电进 OOWOW | [现场失败与恢复](docs/bringup/2026-10-22-p2-uboot-combined.md) |
| 为抓滚轮写入而对正在传视频的 One-KVM 使用 strace，UU 明显卡顿 | 即使按 HID fd 过滤输出，ptrace 仍会干扰多线程视频进程；本轮发送降至约 23–34fps，解除跟踪后恢复 60fps。实时音视频进程优先使用程序内有界计数、低频汇总或独立接收窗口，不能把过滤日志当作低开销采样 | [UU 滚轮调查](docs/uu-scroll.md) |
| sudo 管道混用 heredoc，密码写进配置 | sudo 缓存改变 stdin 消费行为。配置先 scp 再 sudo cp，不与密码共用 stdin | [部署](docs/subsystems/deployment.md) |
| 串口超时后立刻发下一条命令 | 板上命令可能仍在执行。长任务后台运行并轮询结果，确认 shell 空闲 | tools/uart-run.py |
| sudo -b 启动长期程序，SSH 不退出 | 后台进程持有会话描述符。用 nohup setsid 并重定向三路标准流 | [部署](docs/subsystems/deployment.md) |
| 多任务并发使用编码器 | 硬件和 /tmp/vpu_mutex.map 共享。协调独占，以 khadas 运行，不删除活跃锁文件 | [应用](docs/subsystems/application.md) |
| 把像素回读完成时间当网络延迟 | 4K 回读和 JS 调度扰动测量。低频采样并分报回读成本；并行测试结果作废 | [测量方法](docs/latency.md) |
| 在接收机性能采样期间并行编译下一个候选版本 | CPU/GPU/网络环境不再可比；PiKVM 0/10ms 轮次在编译重叠期间出现丢包和解码停止，不能据此归因播放策略。先完成构建，再独占采样；保留失败数据，检查整个采样窗口是否推进 | [PiKVM 对照](docs/kvm-delay-causes.md#pikvm-正式启用低缓冲策略与限制) |
| 直接用 OOWOW /shell/write 或未经核对流式刷盘 | 项目曾遇到 GPT 被清空。使用专用校验刷机脚本，重装需用户确认 | tools/oowow-flash.sh、上板记录 |
| 他人正在构建同一工作区时修改共享接口 | 构建读取工作树，半成品会使对方打包失败。跨仓库接口改动一次写完再保存，或先在独立 worktree 中修改 | logs/nanokvm-migration-package.log |
| 在板上同时运行 NFS 服务器并 loopback 挂载自己做测试 | 板子整机卡死需 RESET，日志未保留。NAS 测试的服务器放在 Mac/OrbStack VM；冻结用 docker pause 或 VM 内 nft 丢包 | [NAS 存储与 U 盘](docs/bringup/2026-10-18-nas-storage-usb-disk.md) |
