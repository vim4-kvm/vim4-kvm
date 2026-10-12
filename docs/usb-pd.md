# USB-C 开机协商

VIM4 的 FUSB302B 位于 `/dev/i2c-6` 的 0x22。U-Boot 初始化 PHY 后，Linux
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
