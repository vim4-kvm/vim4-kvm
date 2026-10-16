# 2026-10-12：Mac USB HID 实测与描述符修复

PD 实验后 Mac 已枚举复合设备，板上 UDC 为 `configured`，但这不代表 HID 可用。
`kvm-gadget.sh` 使用 `/bin/sh`，Ubuntu 的 dash 不解析 `printf '%b'` 的
`\xNN` 转义，实际 report_desc 是 ASCII 文本。之前在 bash 下验证 printf
不能证明该脚本正确。改为 Python `bytes.fromhex()` 写二进制，并修正键盘
Usage Maximum 的两字节项目前缀（`2a ff 00`）。此项取代 [采集编码链路与 USB gadget](2026-10-12-capture-encode-usb-gadget.md) 关于 printf 的结论。

通过串口部署后，板上脚本 SHA-256 与本地一致；三个描述符分别为 65、76、62 字节。
重启 gadget 服务后，Mac hidutil 注册了一个键盘和两个鼠标，实测：

- 相对鼠标：发送 X=12，Mac 光标从 (905,1055) 移至 (913,1055)。
- 键盘：按住右 Shift，Mac NSEvent.modifierFlags 为 131072；释放后为 0。
- 绝对鼠标：发送 X=Y=16384，Mac 光标到 (960,540)。
- 板上 `usb0` 原为 DOWN，手动启用后 Mac `en8` 从 inactive 变为 active。
  IPv4 LAN SSH 和 USB IPv6 SSH 在本次运行环境均报 No route to host，未验证 NCM 的 IP 通信。

PD 程序仍是实验工具，尚未作为开机服务安装；整机重启自动协商未验证。
本次只重启 gadget 服务，未重新协商 PD，也未重启板子。
