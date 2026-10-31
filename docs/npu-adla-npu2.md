# ADLA npu2 离线修复与下一窗口

本轮不访问板子，GPU上板会话独占。正式源码/部署锁与旧npu1产物不变。
内核在VM `~/src/linux-7.3-npu`、分支`vim4-npu-adla`；
新输出`~/build/npu-adla2`，载荷`~/build/npu2-candidate`，
release为`7.3.0-vim4kvm-npu2+`。
软复位失败保留可能仍被DMA使用的页是**用户已于 2026-10-30 接受**；
不是已经获得的用户许可，也不计作全部资源回收通过。

## 资源对照

以下内核路径均相对VM候选源码，绑定为
`Documentation/devicetree/bindings/misc/amlogic,t7c-adla.yaml`。

| 项目 | DT/binding | 实际获取路径与结论 |
|---|---|---|
| IRQ | binding:26，T7 dtsi:32–33，名字adla、SPI185高电平 | `adlak_platform_config.c:269`改用platform_get_irq_byname，保留负错误码，包括-EPROBE_DEFER；不再读IRQ资源表 |
| MMIO/SRAM | binding:19–24，T7 dtsi:29–31，adla_reg/adla_sram | 同文件:228、:240以IORESOURCE_MEM取名，7.3 OF仍提供reg资源，`adlak_io.c:55`用ioremap；无需仿照IRQ更换API |
| 四路时钟 | binding:29–36，T7 dtsi:34–45 | 同文件:292、:311、:314、:317使用devm_clk_get，四路错误均向上传播；parent1不再只告警吞掉defer |
| AXI时钟 | binding没有adla_axi_clk，T7C AXI共享计算时钟 | 删除多余devm_clk_get请求，clk_axi置NULL；运行频率仍由核心时钟路径维护，不增加不存在的DT输入 |
| 供电 | VIM4 dts:222、:535–537，vddnpu-supply指向vdd_npu | `adlak_regulator.c:21`用devm_regulator_get("vddnpu")，错误传播；890000 µV单工作点及devres成对禁用保持 |
| 电源域 | T7 dtsi:46，PWRC_T7_NNA_TOP_ID | `drivers/base/platform.c:1502`在probe前由平台总线attach；ADLA通过runtime PM get/put，`adlak_platform_config.c:449`起；无需私有aml电源调用 |
| reset | binding/DT没有reset；`amlogic-t7-reset.h:56`有RESET_ANAKIN=47，但无本板独立复位时序证据 | 不据ID存在便添加reset_control_get或声称恢复成功；`adlak_hw.c:221`硬复位返回-EOPNOTSUPP，软复位路径保持 |
| 内存 | binding不声明第三个reg或memory-region，内部MMU＋DMA API | 老的可选adla_reserved_memory查询在该DT必然缺省，不参与候选内存分配；`adlak_platform_device.c:225`设置34位DMA mask，未引入ION/厂商SMMU框架 |

`adlak_platform_config.c`完整路径为
`drivers/misc/adla/drv/port/platform/linux/adlak_platform_config.c`；
regulator、platform_device、io文件位于同目录。
T7 dtsi为`arch/arm64/boot/dts/amlogic/amlogic-t7.dtsi`，
VIM4 dts为`amlogic-t7-a311d2-khadas-vim4.dts`。
厂商T7C节点及新binding均不含adla_smc_cmd；addon的可选SRAM SMC分支保持不执行，
不添加未经证明的SMC号；供电域的固件通信仍由标准meson secure genpd负责。
宿主test_platform.py执行实际IRQ获取代码，覆盖有效映射、缺失IRQ和延迟probe，
并继续覆盖启钟/设父/设频及供电失败回滚。

## HDMI根因与修正

npu1与正式基线213f271505411之间的t7-hdmirx驱动源码diff为空，
同次.config对uhd1的差异不涉及接收器配置。
接收器的`phy_test/core_test/uhd60/dynamic_modes/audio_test/hdr_probe/hdr_capture`
均为默认false的只读模块参数（`t7-hdmirx.c:152–177`）。
保存的npu1日志先出现启动5.16秒receiver ready，再出现服务的参数不匹配。
这是模块先以默认值被udev冷插拔加载、服务随后modprobe不能重设参数的集成缺口，
不是ADLA代码改动了HDMI寄存器。不能据此推断所有已安装正式包也同样失败。

一次性包原先只带模块，没有覆盖首次加载的HDMI/VDIN参数；
display-once.py现只在NPU候选APPEND加入与one-kvm-edge-prepare:34–35相同的
`t7_hdmirx.<参数>`及EDID路径、`t7_vdin_test.nv12=1/direct_dma=1`。
kmod手册明确支持从内核命令行取模块参数；已在VM私有挂载命名空间绑定测试
/proc/cmdline并用modprobe --showconfig验证这些选项，不加载真实模块。
候选启动仍须实测sysfs参数及HDMI/VDIN probe，源码分析不能替代硬件结论。

五个运行时助手仅增加npu2 release白名单，5.15路径保持。
因此复用已采集的5.15模型/输入/探针/全部张量和计时基线；
下一窗口需要更新助手备份和**当前stage身份/文件哈希证明**，不重跑5.15推理。
若SDK、探针、输入或模型哈希变化则停止使用旧基线。

## 产物与门禁

内核提交`8f8fa2c449ecf`，主仓运行时代码提交`2018fae`。
完整Image/dtbs/modules通过；build ID为`d59175ac6cd704edf7a5b79f7b2d6c810026505f`，
Image SHA256为`3e8a8aa7c8176e2af074bdced54de1560add9cf6ec7df06eb4024aa01ebfcd76`。
strict checkpatch为0 errors/0 warnings/0 checks；四个Python宿主harness、bounds与ABI C测试通过。
W=1/sparse实跑24个CHECK，无新改行诊断；厂商存量类型、声明、格式、kernel-doc等告警保留，
不宣称整个厂商驱动零告警。binding和DT检查完成，无匹配schema错误。
日志保留在`~/build/npu-adla2/{full,verified-build,w1-sparse,host-tests,schema,dtbs-check,checkpatch,package}.log`。
Linux VM一次性启动9项测试通过；主仓unittest 305项，7项跳过，其余通过。
新载荷含2338个匹配模块，归档内逐文件SHA已独立复核；静态PID1 ELF/release检查通过。
本机副本在`build/npu-r5/candidate/`，VM载荷为上述`~/build/npu2-candidate`。
旧`~/build/npu1-candidate`不覆盖；新载荷含静态一次性PID1、五份运行时助手及哈希、
修正的独立UAPI探针、三模型工具/清单，模型与输入二进制不入git。
最终可stage的bundle必须等下一窗口取新证明后prepare，不能把旧证明改哈希冒充现场状态：

```sh
python3 packaging/kernel-edge/display-once.py prepare \
  --payload ~/build/npu2-candidate --init ~/build/npu2-candidate/npu-once-init \
  --baseline baseline-current.json --output ~/build/npu2-once \
  --release 7.3.0-vim4kvm-npu2+ \
  --baseline-release 5.15.137-vim4kvm-hdrdual6 \
  --baseline-id 4a9b69d62ba7b3a5adeb41b213f7f3e573006165
```

baseline ID/release须现场重新核对；若GPU窗口改变默认内核，不能硬套本例。
证明包含root_partuuid、当前cmdline和五个助手安装后的哈希；prepare/stage仍拒绝身份变化。

## 下一轮7.3窗口：预算30分钟

| 累计时间 | 操作与门槛 |
|---|---|
| 0–4分钟 | 等GPU释放板/媒体/编码器锁，核对备份和现状；安装npu2助手并刷新证明、prepare/stage；不跑5.15模型 |
| 4–8分钟 | UART RAM sysboot；核对release/build ID、/dev/adla0、IRQ计数、四路时钟与vddnpu、HDMI/VDIN参数和服务。probe失败立即回退 |
| 8–13分钟 | 同一探针/输入各101轮三模型，逐轮全部字节比对旧5.15输出；报告均值/P50/P99/max与退化≤5%；ATTACH和正向/负向profiling独立有界运行 |
| 13–19分钟 | runtime PM空闲门控再唤醒；受控wait超时、cancel、kill/close后再次正常推理，记录页/IOVA/上下文计数。不得盲写寄存器强制真实硬挂死 |
| 19–25分钟 | 同一HDMI运动源与Wave5消费者，NPU关/开各最多2分钟，比较帧推进、编码错误、丢帧及NPU延迟；不启动第二编码器 |
| 25–30分钟 | 普通重启回窗口原默认5.15，恢复助手，核对启动文件哈希/服务/UDC；保存证据并释放锁 |

每个子项外层timeout不超过5分钟；只用脚本/计数器、不发HID、不测声音、不ptrace视频进程。
没有运动源就记录该并行项条件不足，不操作Mac mini M6补出运动。
跨窗口旧基线支持既定5%比较，不能声称新增了同时段交替配对证据。
任何oops、输出差异、DMA错误或不可自动恢复的失联都停止本项；预留回退时间优先。
