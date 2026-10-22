# 2026-10-22：P2 GPU 电压表复核

结论：找到 T7 实际五档频率和 VDDGPU PWM 稳压器，但没有找到可信的逐频电压表。
不把未使用的厂商 `1150` 字段转换成微伏，不写 opp-microvolt，不改板子电压。
本项没有候选分支、提交、构建或调压负载验收；这与允许“无可靠来源则说明缺口”的范围一致。

## 本轮源码证据

只读核对 VM `/home/deepdream/src/linux`：

- 主内核 `80a07ad5406d57855c996285ae75a50a1b9147ae`。
- common_drivers `4cfb128d36f8511b2db1bd13c08d5704347ded49`。
- 当前 7.3 `e0346697f25035c7eaa77fa44641a54d6e31e327`。
- U-Boot pd-handoff `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`。

| 来源 | 本轮核对到的事实 | 可支持的结论 |
|---|---|---|
| common_drivers `arch/arm64/boot/dts/amlogic/mesont7.dtsi:4744` | GPU tbl 指向 250/400/500/666/800 MHz，800 档重复用于 preheat | 这五档是实际 DVFS 表 |
| 同目录 `mesong12a-bifrost.dtsi` | 各 dvfs*_cfg 的 voltage 都为 1150 | 没有按频率变化，也未证明单位和有效范围 |
| 主内核 `drivers/gpu/arm/midgard/platform/devicetree/mali_clock.c` | voltage 被读入、打印；Linux ≥4.4 的 critical_clock_set 只切换时钟 | 这些数值不是已执行的电压设置 |
| 厂商 .config | `CONFIG_MALI_MIDGARD_DVFS=y`、`CONFIG_MALI_DEVFREQ` 未启用 | 不能把另一张通用 OPP 表当作当前硬件调压依据 |
| U-Boot `board/khadas/configs/kvim4.h:19` 和 `firmware/timing.c:1037` | `AML_VDDGPU_INIT_VOLTAGE=830`，GPIOE_4 / PWMAO_E / VDDGPU | 证明有启动供电设定，不提供逐频电压表 |
| 7.3 VIM4 DTS `regulator-vddgpu` | SY8003ADFC，AO_EF channel 0，period 1500ns，700000–922000µV，反向 duty | 有可调供电模型，不代表任意范围内电压都已验证 |

先前[GPU 调频记录](2026-10-21-edge-gpu-devfreq.md)的限制本次仍成立。
`1150` 直接解释为 1150µV 显然不是运行电压，乘 1000 解释为 1.15V 又超出当前 regulator
声明范围；没有证据支持任何一种转换，更不能用 CPU OPP 电压或启动 830mV 填满 GPU 表。

## 当前板子的只读状态

```sh
ssh vim4 'cat /sys/class/devfreq/fe400000.gpu/available_frequencies;
  sudo cat /sys/kernel/debug/regulator/regulator_summary;
  sudo cat /sys/kernel/debug/pwm'
```

实际结果摘录：

```text
250000000 400000000 500000000 666666666 800000000
VDDGPU ... 859mV ... 700mV 922mV
fe400000.gpu-mali
pwm-0 (regulator-vddgpu): requested
requested configuration: enabled, 416/1500 ns, normal polarity
actual configuration: enabled, 415/1498 ns, normal polarity
```

859mV 是现有 PWM regulator 模型推算值，不是 ADC/万用表测量。
未写 governor、频率、PWM 或 regulator；没有执行 glmark2 或负载来暗示调压已验收。
既有基线包含纯频率 OPP 和 Panfrost 供电接入，本轮保留原状。

缺口是：VIM4/T7 板型适用、明确微伏单位的 GPU 频率—电压表，芯片分档/温度约束，
以及与实际 PWMAO_E 电路相符的电压标定。拿到后才可在独立 Linux 分支加 OPP 电压，
先做定向 schema/构建，再持锁临时部署、五档往返与实际负载/电压验证，结束恢复基线。
当前不能安全完成这一条件分支。

本地证据：`logs/p2-20261022/gpu-source.txt`、`pm-gpu-detail.txt`、
`gpu-pm-readonly.txt`。最终基线与真实 HID 核对见
[P2 收尾](2026-10-22-p2-kaslr.md#基线恢复与范围)。
