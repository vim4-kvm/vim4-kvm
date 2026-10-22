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

成功日志必须包含 `PD bootstrap complete`，并且 UDC 应进入 `configured`。
`active (exited)` 表示这次初始化完成，不表示程序仍在管理 PD。

## 供电信息

`usb-pd-init --status` 复用控制器锁，只读器件 ID 和 STATUS0 的 VBUSOK，
输出 `vbusPresent`。不读清零型中断寄存器/FIFO，不写配置、不重新协商。
VBUSOK 只表示检测到 USB-C 电压，不是电压实测值，也不能判断 USB-C/VIN
哪一路承担整板供电。内核驱动已占用、初始化持锁或 I²C 出错时查询失败。

管理器概览分别显示该实时状态与本次开机、最近一次初始化的协商额度。
协商日志按 systemd InvocationID 隔离；新工具记录最终请求电流，旧工具若在
初始化期间收到新的 Source_Capabilities，则不展示无法确认的旧请求额度。
额度不是实际电流或功耗。当前没有可用的整板电流采样接口。
7.x 当前没有 Linux TCPM 驱动，沿用 U-Boot 初始化，板级 PD 服务不重新协商。
因此该内核下只有只读 VBUS 检测，没有新的 Linux 启动协商额度；面板分别显示这两种状态。
FUSB302B 的比较器粗测电压需要写配置，本实现不启用；完整 TCPM 接管也未验证。

依据：[FUSB302B 手册](https://www.onsemi.com/pdf/datasheet/fusb302b-d.pdf)、
[MCU 寄存器表](https://dl.khadas.com/products/vim4/tools/mcu/vim4-mcu-register-description-en-v1.0-230520.pdf)。

## 边界

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
