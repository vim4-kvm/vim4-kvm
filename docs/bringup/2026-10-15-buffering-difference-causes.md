# 2026-10-15：不同系统缓冲差异的原因调查

源码与接收统计拆分见 [延迟差异调查](../kvm-delay-causes.md)。NanoKVM/JetKVM 发送
playout-delay 0/0，One-KVM 未发送，PiKVM 非零 GOP 时允许 0–10 秒自适应播放范围。
最后一项不是固定延迟 10 秒；0/0 也不是实际端到端零延迟。

用 NanoKVM `.89`、H.264、4K60 做浏览器协商 A/B：只在 B 的 offer 去掉该扩展，
每轮 60 秒，含 25 秒真实 HDMI 全屏运动。60Mbps A/B/A 末段缓冲 0.28/15.94/0.34ms，
但 B 有 566 个统计丢包，故补做 12Mbps 对照。12Mbps A/B 都无丢包、丢帧、freeze，
末 20 秒实际缓冲 0.26/19.26ms，解码 3.53/3.52ms，target 26.48/26.57ms。
这确认播放策略本身可以产生约 19ms 的等待差异；不是对每个应用承诺固定收益。

没有修改生产应用或安装包。结束后恢复 One-KVM、NanoKVM 12000kbps，安全弹出测试盘，
停止本轮恢复定时器；HDMI InvocationID 与 EDID 哈希不变，board check 通过。
原始数据、探针、汇总、UDP 目的地址短采样和检查日志位于 `logs/kvm-delay-causes/`。
