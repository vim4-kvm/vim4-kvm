# 2026-11-04：开机 PD 接入 Linux TCPM

build 3 已部署并保留为默认，使用标准 FUSB302 / TCPM 管理开机及后续协议，
保持固定 sink、USB device、5V 策略，不调整 CPU performance、idle 或电源域。
完整构建、一次性热启动和正式部署后十分钟4K H.265冒烟通过，内核实际建立5V/3A合同。
用户知悉验证边界后授权部署；冷启动、异常恢复和电源变更的九类全回归仍未完成。

## 基线与硬件

开始本轮时默认是[USB 挂起修复](2026-11-04-pm-typec-parity.md)的 build 2。
本轮只读核对完整启动/模块身份后，板端日志显示固件超时、Linux 跳过协商，
没有 `/sys/class/typec`；四服务 active、UDC configured、两簇 performance。
原始输出和完整 proof 在忽略目录 `build/boot-pd-tcpm/`。
采证脚本最后的 `ls` 因预期不存在的 Type-C 目录返回非零；此前身份核验已通过，
这不是板子故障或新内核测试结果。

[Khadas V13 原理图](https://dl.khadas.com/products/vim4/schematics/vim4-sch-v13.pdf)
第9、10图纸确认 FUSB302 位于 AO I²C、地址0x22，USBCC_INTn 接 GPIOY_4。
中断编号按 T7 pinctrl 的 Y bank 映射计算，不使用 GPIO 编号代替 IRQ 编号。
Type-C 的 VBUS 经硬件输入优先电路供整板，USB-A 输出开关不是它的 VBUS source。
当前板只用 USB-C 供电，不安排拔线或让供电主机睡眠。

## 实现与边界

独立 VM 工作树 `/home/deepdream/src/linux-7.3-boot-pd-tcpm`，基于已部署
`ac47cb60d4848a3a402dfd24e638fce6830b6f80`；未修改其他内核工作树。

- `88cd54506f5be`：FUSB302 binding 仅对明确的 sink 放宽输出 regulator 要求。
- `9263ab94502ef`：固定 sink 缺少 VBUS source 时可 probe；仍传播供电延迟和 I/O
  错误，拒绝无 regulator 的 source-on 请求，保留 source/dual 原有路径。
- `2662456a1a636`：VIM4 声明控制器、中断和 USB-C connector，固定外设 profile
  启用，普通 OTG profile 保持禁用，避免没有 role switch 时宣告与数据控制器不符的角色。

使用标准 sink PDO 与 op-sink-microwatt 描述请求上限和工作预算；较弱来源由 TCPM
限制请求电流并设置 mismatch，不是物理限流或功耗实测。不声明 self-powered，不提供 source PDO、
角色交换或虚构 VBUS regulator。CRG 保持固定 peripheral，不新增轮询守护进程。
内核已有 TCPM 模块配置，不需要改整机配置。

板级 Python 按设备树确认内核所有权，在 probe 延迟或失败时也不退回原始 I²C。
C 工具同时拒绝已实例化但尚未绑定驱动的设备；I2C_RDWR 本身不会替应用检查地址所有权。
旧内核没有启用该节点时，仍保留原有有限开机修复和历史合同处理。
内核部署时管理器仍读取固件/历史合同；本轮验收直接读取标准sysfs，
不能把旧历史卡片当成本次合同证据。后续已更新并部署管理器。

TCPM 原有热启动恢复会先尝试 Soft_Reset，非自供电 sink 还会主动请求能力；
恢复失败仍可进入 Hard_Reset，可能让单线供电整板重启。没有通过禁止标准恢复
来伪造无断电保证。首次上板须一次性 RAM 选择候选，保留已验默认；
这也不证明冷启动、所有来源或异常恢复都通过。

## 离线验证

实际驱动 C 夹具在 Mac Clang、VM GCC 通过，覆盖无 source 的 sink、
probe defer / I/O 错误、供电开启拒绝和已有 source/dual regulator 生命周期。
三个独立源码差异 strict checkpatch 无 error/warning/check；binding 文档 schema 通过。
Linux 旧工具与 C 边界测试按 `-Wall -Wextra -Werror` 编译通过。
主仓523项测试通过、10项跳过，包括内核所有权、禁用节点/父总线、
旧厂商总线路径和 probe 前禁止用户态协商。

完整 Image、DT 和2338基础模块构建通过，三份外部模块按同次内核构建并封装。
配置哈希与build 2一致；编译中的ADLA警告位于未改代码，FUSB302没有新增警告。
对编译后的display-m0 DTB执行FUSB302和USB-C connector schema检查，无诊断输出；
回读确认节点enabled、中断133/低电平和固定5V sink PDO。

## 一次性实板窗口

通过 `tools/board-queue run` 持板，先核对无挂载虚拟介质、PID1 watchdog，
采集5秒视频基线。`display-once.py` 使用完整模块和独立namespace生成RAM候选，
`board-window boot-candidate` 只在本次U-Boot内存中选择它，没有写FIP或默认启动项。
完整输入、窗口脚本、日志和结果保存在 `build/boot-pd-tcpm/`，串口在
`logs/boot-pd-tcpm/`。

| 项目 | 本轮结果 |
|---|---|
| 候选 release | `7.3.1-vim4-20261104.3` |
| 源码 / GNU build ID | `2662456a1a636f668454ab04a1c63f567206a592` / `e595ad243d663f6c33b92678a4de6e0b78ec16d5` |
| 完整包SHA256 | `dda222dfc7038485cbf657ad4a4dce2e82f16c0ad4f4befd5b1130eb950202f1` |
| manifest SHA256 | `12bd899a508e56c78a0a6bb0ecab115ed565d288a33b38f2e66c5d580200992c` |
| 内核合同 | `port0`为sink/device、`usb_power_delivery`；对应`tcpm-source-psy-1-0022`为online，5000000µV、3000000µA |
| 中断 / 驱动 | GPIO IRQ133已处理11次；FUSB302、TCPM、Type-C、CRG加载notes与本包逐项匹配 |
| 视频 | 3840×2160 H.265，五分钟平均60.00955fps；丢帧、冻结、丢包增量均0 |
| CPU / USB | 两簇performance、UDC configured、三个hidg字符节点存在 |
| 内核日志 | 无BUG/Oops/WARNING/Call trace，taint仍为4096 |

FUSB302软件日志记录约6.24秒的Soft_Reset/Accept，随后Source_Capabilities、
Request、Accept和PS_RDY；末次约6.32秒，未记录PD硬复位。这与sysfs完成状态相互印证，
不是电压仪表或线上的协议分析仪记录。驱动的通用日志文字`start drp toggling`
也用于固定sink的检测，不能据这行文字推断启用了DRP。

新Python入口以实际运行DT分别调用bootstrap和底层包装器，都报告kernel TCPM所有权并
退出，没有发送用户态PD报文；这是临时加载源码验证，没有安装板级文件。
板上既有服务仍按旧固件快照跳过，候选合同完全由内核建立。

验证结束正常重启回`7.3.1-vim4-20261104.2`，完整原文件/模块/加载身份与基线匹配，
恢复后的5秒H.265接收约59.77fps。默认项、内核登记及应用未变，板锁已释放。
为候选保留了相同哈希的版本化Wi-Fi固件和私有RAM包，没有覆盖旧固件或模块。
没有安装新的板级Python/C工具、刷U-Boot、发送HID、挂载介质、测试音频或让主机睡眠。

## 后续部署尝试

用户知悉上述冷启动和全回归缺口后要求部署。先安装主仓`f0a31db`的Python/C
所有权保护，随后完整包安装器因`/boot`空间不足在写入新内核前拒绝安装。
该分区可用约45MiB，而完整候选启动文件约56MiB；没有缩减整包或跳过空间检查。
默认仍为build 2，恢复重启后核对完整启动/模块身份和服务通过，
五秒4K H.265视频约59.76fps，UDC configured、两簇performance。
新所有权保护保留在板上，已更新runtime-build中对应文件的哈希，兼容未启用TCPM的build 2。

已核对build 1启动目录没有extlinux或内核登记引用，但清理旧内核需要另行授权。
已向用户提出仅删除该目录、保留build 2整包与厂商5.15的方案；首次尝试未删除。
部署失败、串口和恢复证据在`build/boot-pd-tcpm/deploy-space-failure*`及
`deploy-recovered-*`，启动空间和引用记录在`boot-space.log`、`boot-refs.log`。

## 清理后正式部署

用户随后明确授权清理并部署。再次核对build 1目录的完整文件集合及哈希、
启动配置、登记和符号链接引用后，仅删除`/boot/kernels/7.3.1-vim4-20261104`，
释放约56MiB，启动分区可用104402944字节；build 2整包和厂商5.15保留。
删除前逐文件哈希在[清理凭据](../../packaging/kernel/releases/7.3.1-vim4-20261104.3/cleanup.json)，
删除未改启动项或登记，也未删除旧模块与固件。

安装所有权保护后，整包安装器核验并安装2341个模块和配套启动文件，原子更新Mainline。
正常重启到build 3，服务明确记录`controller reserved for kernel TCPM`，
不再运行用户态协商。启动与末次采证均为sink/device、5V/3A、UDC configured、
五项服务active、两簇performance；完整模块、加载notes/BTF和启动身份匹配。
十分钟3840×2160 H.265平均60.00642fps，解码推进36004帧，丢帧、冻结、丢包增量均0；
无BUG/Oops/WARNING/Call trace，taint保持4096，中断计数保持10。

本轮成功后保留默认build 3，没有回退；板端runtime-build已记录内核和独立安装的
PD所有权保护身份。[源码锁](../../packaging/kernel/sources.toml)与
[验收凭据](../../packaging/kernel/releases/7.3.1-vim4-20261104.3/validation.json)
记录部署范围，完整本地日志在`build/boot-pd-tcpm/deploy*`。

## 尚未验收的范围

冷上电、其他供电源、插拔、软/硬复位异常路径、实际键鼠输入和端到端延迟未验。
本轮热启动和单路视频不能代替[电源改动部署门禁](../subsystems/deployment.md#内核开发流程与部署门禁)
要求的九类全回归；管理器实时合同另见上述后续部署记录。
用户在知悉这些缺口后授权并完成部署；不能把本次冒烟记为九类全回归通过。
部署时仅本地提交并建立release tag；用户随后授权push，内核源码已推送到
`boot-pd-tcpm-review`任务分支，来源锁同步指向该分支，未推送tag或发布Release。
