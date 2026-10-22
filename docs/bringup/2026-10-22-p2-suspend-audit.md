# 2026-10-22：P2 挂起与唤醒离线审查

结论：7.3 暴露 s2idle/deep，但当前 CRG UDC 的系统 PM 回调无条件拒绝挂起；
仅绕开它仍缺 HDMI/编码链路的系统 PM 和经过验证的唤醒路径。
**没有向 /sys/power/state、mem_sleep、pm_test 写入，也没有调用 systemctl suspend/hibernate。**
本项只有源码审查和板端只读能力快照，没有分支、提交或“挂起通过”结论。

## 能力与首个阻塞点

当前 Linux `e0346697f25035c7eaa77fa44641a54d6e31e327`，运行 build ID
`3ed254bfa838ab50732fdce1c5134400a1663fd5`。只读结果：

```text
/sys/power/state: freeze mem
/sys/power/mem_sleep: [s2idle] deep
psci: PSCIv1.0 detected in firmware.
cmdline: ... no_console_suspend ... mem_sleep_default=s2idle ...
```

`drivers/firmware/psci/psci.c:582` 查询 SYSTEM_SUSPEND 支持后注册 platform suspend
ops；deep 出现只证明内核/固件报告这条入口，不能证明 DDR 自刷新、域上下文和恢复可用。
s2idle 也要经过设备系统 suspend 回调，并非绕过驱动的简单 CPU 空闲。

`drivers/usb/gadget/udc/crg/crg_udc.c:4689`：

```c
static int crg_udc_suspend(struct device *dev)
{
        return -EBUSY;
}
```

它同时接 `.suspend/.freeze/.poweroff`；没有检查 gadget 是否绑定。
因此只清空 UDC 并不能解除这一阻塞，只要该 platform driver 仍绑定就拒绝。
保持此保护；不能简单改成 return 0 或卸载来宣称产品具备休眠能力。

## 需要的 PM 工作

| 模块 | 当前实现 | 放开系统挂起前需要解决 |
|---|---|---|
| CRG UDC | 上述明确拒绝；既有 disconnect/stop 已有 IRQ/DMA 安全顺序 | 阻止新提交，停止端点/控制器并同步 IRQ，在 function 上下文存活时完成请求；保存/重建 event/TRB ring、EP0 地址/配置、端点和中断；决定 resume 重枚举及打开的 HID fd 如何恢复；停止超时仍须拒绝并保留 DMA |
| Meson USB parent/PHY | dwc3-meson-g12a 有 system suspend/resume，会 power_off/exit PHY、rearm reset；恢复重新 reset/init/power_on | 与 CRG 子设备按子先父后顺序协调；验证 T7 peripheral 路由、共享复位、PD/Type-C 与主机恢复；USB 主机 resume、gadget remote wake 不能混为一项 |
| T7 HDMI RX | probe 持 runtime PM 引用，没有专用 system PM 回调 | 停异步检测/IRQ 与音频联动，保存 EDID/HPD 策略，恢复时重建时钟/PHY/寄存器并确认输入锁定；不以重复脉冲 HPD 替代恢复 |
| T7 VDIN | 有流停止和电源域取得路径，没有 system PM 回调 | 拒绝或有序停止活动流、等待 DMA 安全停止、返回 VB2 缓冲/处理导出引用；恢复 DMA/ring/输入格式与应用重建，不允许挂起后继续向失效地址写入 |
| Wave5 | wave5_pm_ops 只有 runtime callbacks；legacy_firmware 的回调直接返回 0 | 系统挂起前排空/拒绝活动编码，按 T7 固件契约暂停 DMA/IRQ，处理 genpd 与时钟顺序，恢复固件上下文或明确让应用重建；现有 runtime 路径不能当作 system PM 已完成 |
| ALSA HDMI RX / AXG TODDR | ALSA/ASoC 通用流管理，加 T7 RX 提供的动态时钟/状态 | 核对 PCM suspend、TODDR DMA 停止、RX 采样率/路由恢复及两个驱动的通知顺序；通用 ASoC 代码不证明板级音频能恢复 |
| Panfrost | panfrost_device.c 已有 system PM，调用 runtime force suspend/resume，并处理 reset/供电 | 当前纯调频已验证的是 runtime PM；系统 deep 下 job quiesce、共享电源域/PWM 保持仍需另验 |
| MCU 风扇 | 已有 system suspend/resume，停止/恢复 worker | 与 I²C、温区重新注册及失败保底配合；恢复后重新取温，不能直接套用睡前温度 |
| eMMC/以太网/IRQ/clock/genpd | 使用现有通用及 Meson 驱动 | 审核存储 sync、MMC 恢复、网络/WoL、GIC 唤醒路由及供电域在 deep 下的固件契约，随后才是整机测试 |

相关函数证据保留在 `logs/p2-20261022/pm-source.txt`、`pm-gpu-detail.txt`、
`pm-pstore-source.txt`、`usb-pm-details.txt`；没有为省事关闭 PM 检查或改 IRQ/power sysfs。

## 唤醒源缺口

- 当前 Power 键是 `gpio-keys-polled`、GPIOD_4，每 20ms 轮询。该驱动明确拒绝
  wakeup-source；系统睡着后轮询不能唤醒。要用它必须有支持的 GPIO IRQ/AO 路径及
  固件路由，不能只加 DTS 属性。ADC 键同样不能仅凭能报输入事件推断具备唤醒能力。
- meson-ir 的 suspend 清除解码器 enable，resume 重新初始化；没有本轮已确认的
  Linux enable_irq_wake 路径。固件 AO IR 唤醒需单独核对 BL31/电源控制器及遥控码，
  不是注册 rc-khadas 键表就能保证。
- RTC alarm 是后续最适合先验证的定时唤醒候选，但需 IRQ、always-on 时钟和 deep 固件
  支持证据。本轮没有设置 alarm，也没把 sysfs 节点存在当作通过。
- Ethernet WoL 需要 MAC/PHY、wake IRQ 和电源保留共同支持；SSH 连接本身不是唤醒源。
  USB 唤醒需主机控制器与设备侧协议/PHY 支持；PD 快照仅是开机状态，不提供唤醒服务。
- 不把 Wi-Fi/P2P 纳入本轮实现或测试，不修改其配置。

后续顺序应是先实现设备 quiesce/recovery 和明确的唤醒源，再离线故障注入/构建，
具备现场恢复条件后才单独授权整机试验。当前保留 CRG -EBUSY，避免把 HID 核心能力
交给未实现的恢复路径。P2 两次重启只用于 KASLR；没有用重启或 GPU runtime suspended
冒充系统挂起/唤醒验证。
