# 2026-10-17：管理器 Wi-Fi 网络管理与热点模式

## 部署来源

管理器基于 `4b6bd03` 加 Wi-Fi 改动构建（随后提交为 `da6ed18`），`ubuntu-build.py package/verify --component manager`
隔离验证后用 `board.py deploy --exclusive` 部署（manager 模式，不重启 KVM 应用和 HDMI）。
最终安装 `2.5.1+vim4.20261017.28.dev.8.g4b6bd03.dirty`，与 `da6ed18` 的源码一致。dev.2–dev.7 是同一轮中间版本：
dev.5 修复分段选择器悬停时选中项文字不可见；dev.6 修复无已保存网络时无法从热点切回客户端；
dev.7 加入热点二维码和图标按钮；dev.8 为密码输入框加入显示/隐藏切换。
部署前后 One-KVM、HDMI 采集保持运行，`dpkg --audit` 与 `dpkg --verify vim4-manager` 无输出。

## 平台事实

- wlan0、wlan1 是同一 Broadcom dhd 无线芯片（phy#0）的两个接口；驱动支持 AP，NetworkManager 只报告 2.4 GHz AP 能力。
  wlan1 无法连接 wlan0 自己发出的热点，不能用作板上热点客户端测试。
- NetworkManager 1.46 使用 netplan 设置插件：连接的持久来源是 `/etc/netplan/90-NM-<uuid>.yaml`，
  `/run/NetworkManager/system-connections/` 下的 keyfile 由其生成。改写 keyfile 再 `nmcli connection load`
  只改运行时配置，重启后丢失；经 D-Bus `Settings.Connection.Update`/`AddConnection` 写入才会持久化。
- `nmcli connection edit` 从标准输入设置密码会去掉首尾空格、改写反斜杠；不能用于密码。
- `nmcli device disconnect` 对未激活设备返回 6；回退路径必须容忍。
- `nmcli -t device show` 的值（MAC、IPv6）不转义冒号，与 `-g`/`-t` 列表输出不同。
- dbus-python 在参数编组失败时把整个设置字典（含 PSK）写到 stderr；管理器把助手 stderr 显示到网页和事件中，
  助手需关闭 `dbus` 日志记录器。`copy.deepcopy` 会丢失空 `dbus.Array` 的签名，导致 Update 被拒绝。

## 实板验证

经有线 eth0 的 SSH 隧道访问 80 端口，无线切换不影响测试会话。

- 状态读取、扫描（约 3 秒列出 14–18 个网络，去重排序）、非法 SSID/密码/UUID/信道、跨站写请求（403）、
  模式切换期间的并发写（409）均符合预期。
- 开启热点：wlan0 进入 AP 模式，`10.42.0.1/24`，NetworkManager dnsmasq 提供 DHCP。
- 修改正在运行和未运行的热点：名称、信道、开机启动及含首尾空格和反斜杠的密码均原样写入 netplan，
  `nmcli connection reload` 后保持；只改信道时保留原密码。
- 热点 → 客户端：没有已保存网络时约 3 秒恢复热点并返回原因；`force` 时停止热点不回退。
- 向真实周边网络提交错误密码：约 16 秒失败，删除新建连接并恢复热点。
- 真实网页（1440 宽浅色、390 宽深色）列出附近网络、展开加入表单、模式切换确认框，取消不发送写请求，
  无页面错误和横向溢出。
- 经有线访问、无已保存网络时从热点切回客户端（dev.6）：约 5 秒完成并列出 14 个网络，不恢复热点。
- 热点二维码（dev.7）：从真实页面截取并解码连接码，名称和密码与板上热点一致；页面不请求外部资源。

未验证：手机扫码或手动连入热点并经板子上网（本机 Wi-Fi 在用、wlan1 不可用）、成功连接一个已知密码的客户端网络
及其自动重连、连入设备列表、经 Wi-Fi 访问时的 viaWifi 提示、热点开机自启的实际重启。测试结束后删除了测试热点，
板子恢复为仅有线连接、无保存的无线配置。

构建、隔离验证、部署日志、浏览器脚本和截图位于 `logs/wifi-hotspot-deploy/`。
