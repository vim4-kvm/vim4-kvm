# 2026-10-14：NanoKVM Wi-Fi 扫描空列表

板上 Wi-Fi radio enabled、rfkill 未封锁，但 wlan0/wlan1 均无 UP 标志，
NetworkManager 仍报告 disconnected；`wifi-scan` 返回空数组，`iw dev wlan0 scan`
返回 Network is down。经有线 SSH 将 wlan0 置 UP 后扫描恢复，首次返回 17 个热点。
接口最初被关闭的原因未确定，未据此归因驱动。

NanoKVM 的 vim4-system 增加扫描前检查：radio 禁用时报错，不擅自开启；
radio 已开启而接口 DOWN 时恢复接口。命令 locale 改为 C.UTF-8，修复中文 SSID
被 nmcli 的 C locale 替换为问号。仅更新板上该助手，无需重启 NanoKVM；
更新后助手返回 13 个热点且保留中文名称。网络数量随扫描变化。
部署助手测试共 35 项，32 项通过、3 项跳过；未使用路由器密码测试实际关联。
