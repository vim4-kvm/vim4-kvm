# 2026-10-12：PD 开机初始化固化

新增 `tools/usb-pd-init.c`、`board/vim4-kvm-pd.service`，详见 [usb-pd.md](../usb-pd.md)。
编译启用 `-Wall -Wextra -Werror`；测试覆盖 1.5A/3A 请求、电流上限、
拒绝非 5V、非固定 PDO 和零电流。`board/install.sh` 安装并启用服务，
下次启动在 gadget 创建之后进行有限的 20 秒 PD 交接，失败不自动重试。

保留同一根 Mac USB-C 供电/数据线，执行整机重启后验证：

- `vim4-kvm-pd` Result=success、ExecMainStatus=0。
- 主机返回 Accept、PS_RDY，日志记录 5V/3A 和 `PD bootstrap complete`。
- UDC 为 `configured`，Mac 自动重新注册一个键盘、两个鼠标。
- 右 Shift 按下/释放，Mac modifierFlags 为 131072/0；绝对坐标报告将光标移至 (480,810)。

启动日志保存于本地 `logs/pd-autoboot.log`（不入库）。本次通过串口部署和验证，
未刷写 U-Boot，未更改 PD 电压，未配置 NCM IP 网络。此验证覆盖正常重启，
不覆盖断电冷启动、主机休眠或不断电热插拔。
