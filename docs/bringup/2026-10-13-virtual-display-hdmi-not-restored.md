# 2026-10-13：虚拟显示器退出后 HDMI 桌面未恢复

用户确认已退出虚拟屏；Mac 的显示器枚举仍只有 1920×1080 虚拟显示器，
没有 AML TV。VIM4 此时报告 3840×2160、约 59.98Hz、FSM_SIG_READY、
no_signal=0、avmute_skip=0、ECC 计数为零；vfm_cap 接收与交付计数继续增长。
这些状态不能证明 HDMI 像素仍代表当前桌面。

没有更换 EDID 内容，也没有重启 NanoKVM、tvserver 或 HDMI 服务：仅对
/dev/hdmirx0 调用 HDMI_IOC_EDID_UPDATE_WITH_PORT（端口参数 2，即 RX port 1），
Mac 随后重新枚举 AML TV 4K60。该 ioctl 同时触发 HPD 和 RX 状态机重启，
所以它有效不能单独证明故障只在发送端或接收端。

恢复后在物理 HDMI 桌面绘制运动标记，Chrome 从实际解码像素读出 109 个有效标记，
无无效标记；12 秒测量约 59.98fps、framesDropped=0、packetsLost=0、freezeCount=0。
这是内容更新的证据，不只是收包速率。原始记录在 logs/hdmi-recovery/。

用户再次进入并退出虚拟屏后复现。持续内核日志没有记录到这次进出过程的 RX
失锁/重锁，退出后接收与采集状态仍正常，Mac 又只枚举虚拟显示器。
再次执行相同 ioctl 恢复连接。尚未找到板端可靠的自动触发条件；没有部署
周期热插拔或静止像素看门狗，不能宣称自动恢复已修复。
