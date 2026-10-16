# 2026-10-14：One-KVM HID 功能配置与 USB 组合

最终 One-KVM 源码 `98ba6784`，主仓库打包基线 `f71b586`，安装
`vim4-onekvm 2.5.1+vim4.20261014.10`。仅更新 One-KVM；管理器保持 `.4`，
JetKVM `.2`、NanoKVM `20261013.10`。包 SHA256：
`1be7a813d56373cd9e41c12cf1b873ca673b6c03097844b7a965fb95e1104a50`。

- HID 配置接入板级 gadget 的原有实例与链接；增加 hidg3 多媒体键及专用 udev
  权限。重枚举前释放按键并关闭设备，助手等待 udev 权限生效。描述符、磁盘名称、
  UAC2、NCM/ECM/RNDIS 可配置，网络使用独立 NetworkManager DHCP/NAT 连接。
- 端点预算为 5 个 IN，保存预留启用虚拟盘的一个端点，挂载时再校验。超限请求
  未破坏现有配置。禁用全部 HID 后重新启用通过；修复重复解除已解绑 UDC 返回
  ENODEV 的恢复问题。绝对鼠标单独启用时按钮/滚轮不再被丢弃。
- API 与网页保存通过，设备名写入实际 configfs。主机键盘 Shift、鼠标定位、
  只读 ISO 内容读取、弹出后键鼠恢复通过。切换虚拟盘开关时也使用包内 Ventoy
  资源目录，避免重新初始化时错误回到数据目录。
- UAC2 在板上 ALSA 和 macOS 枚举，认证 WebSocket PCM 触发实际 ALSA 消费进度。
  macOS 设备显示 `Capture Inactive`，厂商 One-KVM。录音终端权限状态为未授权；
  零波形不算音频验收通过，完整主机录音仍待授权。未修改系统默认输入。
- NCM/ECM/RNDIS 均分配板侧 `10.42.0.1/24`，停止服务后删除本应用网络连接，
  恢复原始 VID/PID、名称及 HID×3+NCM。Windows 驱动与完整 NAT 数据流未验收。
- One-KVM → NanoKVM → JetKVM → One-KVM → JetKVM → NanoKVM，再恢复 One-KVM，
  每轮 3840×2160、约 59.66–60.05 fps，所测区间未观察到丢帧或丢包。
  HDMI InvocationID 始终 `5adb6d1c9b494584996befd0f64d2877`。
  NanoKVM 的既有预设在切换时自动挂载了其 512 MiB 虚拟盘，结束后在主机安全弹出、
  从 gadget 卸载，恢复测试前的未挂载状态；没有删除镜像或改其持久配置。
- Rust 560 项、Python 助手 15 项、工作区 42 项通过；前端与 ARM64 release 构建、
  包校验、隔离容器完整在线升级测试通过；板上 dpkg 校验与 audit 无错误。

证据：`logs/one-kvm/usb-api-final.log`、`usb-input-media-final.log`、
`usb-switch-final.log`、`usb-package-final-verify.log`、`usb-settings.png`。
暂不支持多 LUN、任意磁盘目录和以太网桥接，界面给出组合限制及说明。
