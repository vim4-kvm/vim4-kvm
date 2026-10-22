# USB-C 开机协商

VIM4 的 FUSB302B 位于 AO-A I²C 控制器的 0x22；5.15 通常为 `/dev/i2c-6`，
7.x 为 `/dev/i2c-1`。工具按设备树物理控制器识别，不探测其他总线。U-Boot 初始化 PHY 后，Linux
的 `usb-pd-init` 请求固定 5V 的 USB 通信供电约定，并处理后续 20 秒内的
Source_Capabilities 和 Get_Sink_Cap。USB 键鼠描述符由 gadget 服务提供，
不是由 PD 报文提供。

安装依赖 `cc`、Python 3、systemd 和 i2c-dev。运行 `sudo sh board/install.sh`
会编译并安装工具、启用 `vim4-kvm-pd.service`；PD 服务在下次开机时运行，
安装操作本身不会重新协商当前供电。服务排序在 gadget 创建之后。

检查：

```sh
systemctl status vim4-kvm-pd
journalctl -b -u vim4-kvm-pd --no-pager
cat /sys/class/udc/*/state
```

实际重新协商成功日志包含 `PD bootstrap complete`；7.x 按快照跳过时记录
`PD bootstrap skipped:` 及原因。UDC 应进入 `configured`。
`active (exited)` 表示本次开机处理完成，不表示程序仍在管理 PD 或已建立新合同。

## 供电信息

`usb-pd-init --status` 复用控制器锁，只读器件 ID 和 STATUS0 的 VBUSOK，
输出 `vbusPresent`。不读清零型中断寄存器/FIFO，不写配置、不重新协商。
VBUSOK 只表示检测到 USB-C 电压，不是电压实测值，也不能判断 USB-C/VIN
哪一路承担整板供电。内核驱动已占用、初始化持锁或 I²C 出错时查询失败。

管理器概览分别显示该实时状态与本次开机、最近一次初始化的协商额度。
协商日志按 systemd InvocationID 隔离；新工具记录最终请求电流，旧工具若在
初始化期间收到新的 Source_Capabilities，则不展示无法确认的旧请求额度。
额度不是实际电流或功耗。当前没有可用的整板电流采样接口。

热重启历史展示（manager `pd-warm-carryover`）由板级 `vim4pd.py` 在合同确认后，
以同目录临时文件加 rename 原子保存 `/var/lib/vim4-kvm/pd-last-contract.json`。
记录电压、电流、RDO/USB comm、来源、bootId 与带板端时区的确认时间；Linux 成功初始化
覆盖更早的固件 PS_RDY 合同，未确认时不写、不删。查询仅给出不同 bootId 的完整记录，
损坏、缺字段或同次启动的记录不输出 `lastContract`。
本次 Linux、固件合同仍依次优先。仅固件超时、空 PDO、VBUS 存在时显示
「5V 3A · 沿用」（按实际额度格式化），detail 保留历史时间；无记录主值为「仅 Type-C」，
detail 为「本次未重新协商 · Rp …」。≤400px 的 PD 与开机时长各占整行，避免其它状态的
主值被截断；空趋势图只保留一条占位文案。
详情说明本次未收到来源能力，保留其他独立错误及历史记录 footer；不测实时合同或功耗，
不新增 PD 报文。安装 helper 前须先安装配套板级模块，安装时不重启 PD 服务。
热重启、视觉回归、部署与回退证据见 [热重启卡片记录](bringup/2026-10-22-pd-warm-carryover.md)。

7.x 没有 Linux TCPM 驱动，通常沿用 U-Boot 初始化；仅下面的开机修复条件允许重新协商。
旧 U-Boot 下该内核只有只读 VBUS 检测，没有新的 Linux 启动协商额度；面板分别显示这两种状态。
FUSB302B 的比较器粗测电压需要写配置，本实现不启用；完整 TCPM 接管也未验证。

当前正式版运行时包含 `vim4pd.py`：仅开机 PD 服务读取固件快照。v1、长度正确、
PS_RDY 已完成且非超时/Type-C 回退/I²C 错误，RDO 所选 PDO 有效并缺少 bit25
USB Communications Capable 时，运行一次现有 `usb-pd-init` 请求 USB 可通信的 5V 合同。
属性缺失、异常或已有该位均记录原因并跳过；不主动探测 PD 控制器。
`/run/vim4-kvm-pd-boot.done` 在判断前原子创建，跳过与失败也不在同次启动重试。
安装器不启动或重启 PD 服务，查询/运行时更新不重新协商活动链路。
单元测试通过；第三轮正式部署已保留，开机实际快照 flags=0xd0、RDO=0，验证了
超时/Type-C 回退时跳过并记录原因，PD 服务 active、UDC configured。
本轮没有 PS_RDY 有效合同，未实板触发缺 USB comm 位修复或已有该位的分支，也未测试插拔；
证据见 [正式版保留记录](bringup/2026-10-22-edge-7-3-final-retained.md)，版本和入口见
[正式版部署准备](bringup/2026-10-22-deploy-7-3-final-prep.md)。

启动固件交接候选使用 `/chosen/khadas,usb-pd-boot` 的 v1 快照（16 个大端 u32），
由最终 Linux DTB 的 board fixup 写入，包含 PS_RDY 完成标记、原始 Source PDO/RDO、
来源与请求的 PD 规范版本、附着时 Rp，以及硬复位、请求失败、超时和 I²C 错误。
查询只读 `/proc/device-tree/chosen`；缺失或损坏时保持旧文案。
当前管理器的 `power.firmwarePD` 与 Linux `bootContract` 分开，5.15 优先显示后者，
来源能力详情保留启动固件记录。合同额度从实际 RDO 最大请求解析，同时列出工作请求；
来源 PDO 列表是额定能力，不能直接当作合同或实际用电。
Battery 使用功率、Variable 使用电压范围；没有可确认的电压/电流时不拼造 V/A 合同。
Rp 默认档不换算成未经确认的电流；失败回退仅表示退出时没有确认的 PD 合同。
新 U-Boot 已在用户接受现场 OOWOW 恢复风险后刷写并保留；7.x 与 Stock 5.15 均启动，
属性与各次串口的 16 个 cell 一致。这三次固件初始化均未收到 Source_Capabilities，
记录为超时回退、Rp 3A；不能据此宣称成功 PD 合同或能力列表已实板验收。
5.15 随后的 Linux 初始化完成 5V/3A，候选页面正确优先显示 Linux 记录。
固件刷写会话曾将管理器恢复 b1e49a8；随后第三轮正式部署保留 `7a69cedb6d526`，
现网面板已显示 PD 卡，并正确呈现此次超时回退、Rp 3A 与无有效合同。
属性格式见 [交接实现](bringup/2026-10-22-pd-firmware-handoff.md)，
镜像、备份、回退方法与验证边界见 [刷写与双内核验证](bringup/2026-10-22-pd-firmware-deploy.md)。

热重启复核确认：Linux 工具先主动发送 Get_Source_Cap；现有 U-Boot 复位本地 FUSB302
后只被动等待约 200ms。历史日志同样没有能力评估打印，不能声称该固件此前完成过合同，
也不能仅凭这些日志确定 Mac 保存了什么合同。第三轮未增加主动查询：实际驱动函数的
主机复现发现接收中断乱序可丢掉能力报文、Soft_Reset 不回 Accept、Get_Sink_Cap 无回复，
且旧策略可选择 9V（上限 12V），不是严格 5V。Get_Source_Cap 本身不要求断电，
但对端在协议恢复失败时仍可能硬复位；单线供电下仅禁止本端发送硬复位不足以保证供电。
因此暂保留只读快照，不把失败回退包装为有效合同；原因、模拟边界及停止条件见
[热重启审查](bringup/2026-10-22-pd-warmboot-audit.md)。

依据：[FUSB302B 手册](https://www.onsemi.com/pdf/datasheet/fusb302b-d.pdf)、
[MCU 寄存器表](https://dl.khadas.com/products/vim4/tools/mcu/vim4-mcu-register-description-en-v1.0-230520.pdf)。

## 边界

以下限压、重试与协议服务边界适用于 Linux `usb-pd-init`；原 U-Boot 的缺口见上面的热重启审查。

新的 [U-Boot Request 离线候选](bringup/2026-10-22-uboot-pd-request.md) 已将选择限制为
非零电流的 Fixed 5V，工作/最大电流均为 min(源能力, 3A)，置 USB 通信和 No USB Suspend，
不因低于 3A 设置 Capability Mismatch；PDO1 为 5V/3A 时 RDO 是 `0x1304b12c`。
无可用 5V PDO 时沿原 wait-caps/超时回退，不请求高压。v1 快照格式不变。
这取消了该驱动原 12V/6A 充电策略；主机测试、Linux 函数对比与构建通过，尚未刷写。
接收中断乱序、Soft_Reset、合同后协议服务和热启动无 Source_Capabilities 的缺口仍在，
不能将修正 Request 等同于完整 PD 接管或实板 HID 验收。

- 仅用于 ID 为 0x91、已由 U-Boot 配置为 PD2 sink/UFP 的控制器。
- 不切换电源角色、不请求超过 5V 的 PDO，电流取主机声明值与 3A 中的较小值。
- 检测到内核驱动已绑定就退出；文件锁防止本工具重复运行。
- I²C 失败、发送失败、主机拒绝或硬复位均报错退出；没有自动重试服务，避免供电重启循环。
- 这是启动时的有限交接工具，不是完整的 TCPM 实现；不保证运行期间再次插拔、
  主机睡眠唤醒或后续 PD 重置的恢复。仅 USB-C 供电时，拔线会使板子断电。
- NCM 的 IP 地址和路由不在这个服务中配置。

报文常量核对依据：[Linux USB PD 定义](https://github.com/torvalds/linux/blob/master/include/linux/usb/pd.h)。
请求边界测试在 Linux 上运行：

```sh
cc -Wall -Wextra -Werror tests/pd-request.c -o /tmp/pd-test
/tmp/pd-test
```
