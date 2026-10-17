# 2026-10-17：供电信息只读验证

## 结论

当前 VIM4、5.15.137-vim4kvm 内核无 hwmon，power_supply、powercap、typec
为空。MCU 公开寄存器没有电流或功率读数。没有找到可用的整板实时功耗接口。
FUSB302B 可以读 VBUSOK；只代表电压存在，不能据此判断 VIN/USB-C 的供电分担。
硬件能力与接口约定见 [USB-PD](../usb-pd.md#供电信息)。

## 本次验证

- 在板上临时编译 `tools/usb-pd-init.c`，只执行 `--status`，返回
  `{"vbusPresent":true}`。没有重新执行初始化，也没有改比较器或协商配置。
- 临时 helper 以新查询程序为探针，读取当前 systemd InvocationID 的日志，返回
  `{"vbusPresent":true,"bootContract":{"voltageV":5,"currentA":3.0}}`。
  原初始化日志含 PS_RDY、bootstrap complete、PDO1 5000mV 3000mA。
- USB UDC 在查询后仍为 configured；本轮未验证重新枚举、断电、睡眠唤醒。
- Linux 的 PD 请求边界测试、管理器 Go 测试、前端与 Go 构建通过；Linux helper
  全部 98 项测试通过。Mac helper 跳过的 12 项 FAT 测试在 Linux 上补齐。
- 浏览器使用板上状态快照与上述供电结果检查桌面、390px 手机布局，以及读数未知时
  清除旧额度。实时图表 resize 需要等布局稳定后检查宽度。

源码新增概览供电区，尚未安装新板级程序或部署管理器；未改内核、未重启板子。
完整 TCPM 接管、比较器粗测电压、VIN 检测及实际功耗采样均未实施或验证。
