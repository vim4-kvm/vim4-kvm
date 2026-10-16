# HDMI 恢复路径对照

2026-10-13；源码审查，不代表新增硬件验证。复现记录见
[上板记录](bringup/2026-10-13-virtual-display-hdmi-not-restored.md)。

## 审查范围

- NanoKVM 官方基线 `d0ff328db81c8d08a9133639ce63d32cba54f172`。
- NanoKVM-Pro 官方基线 `3b013bb627a461846a6594f48e01d5a86729ef48`。
- VIM4 common_drivers `95e064470979afccb945bd32b862d348e3e8ea1f`。
- Linux 主线 [tc358743.c](https://github.com/torvalds/linux/blob/master/drivers/media/i2c/tc358743.c)
  当日读取版本，只比较行为，不照搬芯片寄存器或等待时间。

## NanoKVM 的自动恢复依赖什么

`support/sg2002/additional/kvm/src/kvm_vision.cpp` 的检测线程读取 LT6911
中断计数，按芯片型号选择上升沿/下降沿，读取 HDMI/CSI 尺寸。新尺寸设置
`reopen_cam_flag`；未知尺寸转入探测模式。其他模式根据 VI 状态重新探测。
这些分支处理输入状态和格式变化，没有在已审查路径中发现 Mac 虚拟屏退出事件
或判断“当前像素是否属于真实桌面”的机制。

`server/service/vm/hdmi.go` 的 ResetHdmi 关闭后等待 1 秒再开启。
底层 `kvmv_hdmi_control` 仅在 PCIe 硬件上切换 GPIO451；其他硬件返回 -1。
因此“官方有重置接口”不能推导为所有 NanoKVM 硬件都有相同的热插拔行为。

Pro 的 `server/service/vm/edid.go` 将预设或自定义数据写入
`/proc/lt6911_info/edid`，从 `edid_snapshot` 读取当前表。这层代码本身不描述
底层 HPD 时序，也不能证明 Pro 已解决本次虚拟屏恢复问题。

## VIM4 与 Linux 接收驱动

VIM4 的定时器运行 5V、HPD、EDID 监控；T7 进入 `rx_main_state_machine`。
FSM_SIG_READY 分支检测 TMDS 有效性、时序和 AVI 变化，并在异常时重新等待
锁定。不是缺少整个热插拔/失锁恢复机制。

`rx_ddc_active_monitor` 只在 FSM_WAIT_CLK_STABLE 且其他条件允许时处理
DDC 过滤状态。本次故障停在 FSM_SIG_READY，这条路径不会执行；这是待测差异，
不是应直接去掉状态限制的证据。

进一步追踪 `rx_need_ddc_monitor`：它明确对 T7 rev C 返回 false，因此本板
不会运行这段 DDC 过滤兼容逻辑，不仅是 READY 状态的限制。它不是通用 DDC
请求处理器；T7 初始化另有启用 HDCP DDC/SCDC DDC 的硬件寄存器配置，
`rx_clk_rate_monitor` 也读取 SCDC 时钟比例。不能把禁用该兼容监控解释为
“本板不回应 DDC”。在已检索的 HDMI RX/CEC 代码中未找到明确的 DDC/CI
MCCS 响应实现；是否有主机请求以及硬件如何应答，需要单独观测。

TC358743 在 EDID 存在后安排延迟 HPD（代码为 HZ/7，注释约 143ms），
5V 消失时撤销 HPD 并清除时序；格式变化通过 V4L2 SOURCE_CHANGE 通知消费者。
它同样基于可检测的输入状态，并没有“静止画面就重新热插拔”的策略。
该等待值不能直接替换 VIM4 的状态机计数。

## 已确认的适配缺口

当前 NanoKVM VIM4 的 `POST /vm/hdmi/reset` 路由返回 unconfigured，
`KvmVision.SetHDMI` 也是不支持占位；原生重置菜单只对 PCIe 显示。
恢复接口可以复用原有 UI 样式，但需独立实现 VIM4 重协商，并正确返回失败，
不能简单解除路由拦截，否则会调用占位函数。

VIM4 的 HasHDMISignal 只从 sysfs info 解析帧率，不能把它当成接收状态机
实时锁定的充分证明。本次同时读取过 FSM、vfm_cap 状态和推进计数，仍不能
证明内容有效；仅修正网页信号提示不会解决本次冻结。

## 下一轮实验应区分的变量

此前有效的 HDMI_IOC_EDID_UPDATE_WITH_PORT 同时执行 HPD 拉低、EDID 更新、
接收器重新配置和部分 SCDC 清理。因此目前不能把结果归因于 HPD 单一因素。

1. 在同一故障现场分别验证只恢复采集与重新协商的效果；每轮重新复现，
   不把已经恢复后的实验作为证据。
2. 在进入/退出虚拟屏时记录实际 HPD/5V、DDC/SCDC、时钟/锁定和帧推进。
   现有普通日志没有状态转换，不等于所有底层事件都未发生。
3. 用经过校验、能力不超过 VIM4 的替代 EDID 对照；若有效，再缩小到单一能力差异。
4. 只有找到可区分正常静态桌面和故障的条件后，才加入自动恢复。

重置接口属于人工恢复能力；完善它不能标记为“虚拟屏退出自动恢复已修复”。

## 控制状态采样工具

`tools/hdmi-control-watch.py` 在板端以 root 运行，默认 180 秒、最多 600 秒，
每秒输出一条 JSON。通过 debug 接口只发送固定的读寄存器命令，不发送
HPD/EDID 更新、复位或任意寄存器写入命令；读取 /dev/kmsg 不清除内核日志。

```sh
scp tools/hdmi-control-watch.py vim4:/tmp/vim4-hdmi-control-watch.py
ssh vim4 'sudo -n python3 /tmp/vim4-hdmi-control-watch.py --seconds 180' > control.jsonl
```

限定 VIM4 T7、HDMI RX port 1。DWC 标签是驱动打印名称：在 T7 上实际读取 COR。
固定采样 SCDC 的 sink/source version（0x301/0x302）、TMDS config（0x320）、
scramble status（0x321）、status flags0（0x340），以及 TOP 的
EDID_GEN_STAT_B（0x25）；同时采集 vfm_cap status/stats。
不读取中断状态或清零语义尚不明确的错误计数器，也不启用厂商 I2C debug 模式。

已在板子上完成两次连续采样，每次返回全部六个寄存器，帧计数继续推进。
这不是逐笔 DDC 抓包：一秒内的变化可能遗漏，状态寄存器也不能证明 ACK/NAK。
采样期间避免其他任务使用 debug 接口，输出应核对每条是否包含六项读数。
驱动的 `rx_i2c_dbg_monitor` 及配套 ACK/NAK 解码器仅支持 T3X，不能用在本板。
