# USB 与供电

先读 [USB-C 协商](../usb-pd.md)、[硬件接线](../hardware.md) 和
[应用集成](../../NanoKVM/VIM4.md)。

键鼠输入延迟、长按和 Mac 滚轮方向的测试入口见 [输入验证](../input-latency.md)。

板级 gadget 服务拥有 configfs，PD 服务负责开机有限协商。
应用使用 hidg0/1/2 对应键盘、绝对鼠标、相对鼠标，不重新创建 gadget。
虚拟介质与板级预设协调，不部署上游设备专用 USB 脚本。

One-KVM 的限定助手可暂时修改这个 gadget 的描述符与功能链接，并按需创建
hidg3 多媒体键、ECM/RNDIS 网络实例；不删除原有 HID 实例。应用停用后由
ExecStopPost 恢复原始配置，详情见 [One-KVM 适配](../../One-KVM/VIM4.md#hid-功能配置)。
最多 5 个 IN 端点；网卡占两个，其余每个 HID、UAC2、磁盘各占一个。

PD 不是完整 TCPM；单线供电时拔线会断电。启动枚举通过不等于睡眠唤醒、
运行中重置和 NCM IP 通信通过。改描述符或协商代码后运行相关边界测试，
再验证主机枚举和实际输入，避免干扰其他任务。
