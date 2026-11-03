# 2026-11-01：vim4-manager HTTPS 部署验收

vim4-manager `70aa76da270bb15ab4dc130edbcb9741c1f0fbc5`（main）已部署：管理面板 :443、KVM 网关 :8443，
本机 CA 叶证书与 Tailscale 证书按 SNI 选择，HTTP 开关默认保留。证据：`logs/https-manager-20261101/final-window/`。

## 部署

只替换 manager 与 helper，并按新包手工建立 `/usr/sbin/vim4-manager -> /opt/vim4-manager/vim4-manager`，
仅重启 vim4-manager。SHA256：manager `5b09c77820724ef14de878209dc6db0581ba69389203c4f83d18525e82d2284b`，
helper `e9eb506cc5c17d675423a119895f95cf9ae94eadc025441947f70e7fd6f4a444`。
票据 `58c6403f04094713918ac3b08f6927ec`，持板 181.7s。此前 88faba4 两次短窗口因验收脚本误判停止，证据保留在同目录。

## 结果

| 检查 | 结果 |
|---|---|
| 监听 | 80/8080/443/8443 由同一 manager 进程监听；内核日志无新条目 |
| 证书 | CA 匿名下载两端一致；`curl --cacert` 两端通过；叶 SAN 含 LAN IP、Khadas、Khadas.local；私钥 0600，证书 0644（公开内容） |
| Tailscale | Running，CertDomains `khadas.tailb66bbe.ts.net`，API issued，到期 2027-01-30 |
| HTTP 关闭 | :80→:443、:8080→:8443 均 308 并保留路径与查询；板内回环不跳转；HTTP 页面关闭请求 409 `https_required`；无 HSTS |
| 恢复命令 | `sudo vim4-manager set-http on` 1.3s 内恢复 HTTP，进程未重启 |
| MCP | 原 HTTP :8080/api/mcp initialize、tools/list、截图正常 |
| 打开 KVM 链接 | HTTPS 管理面板的概览与应用页链接为 `https://<host>:8443/?kvm=onekvm`；跟随后 One-KVM 页面 `isSecureContext=true`、`getUserMedia` 可用；HTTP 页对照为 false |
| 网络页 | 真实数据下 HTTPS 卡片与 Tailscale 地址行正常（桌面、手机） |

## 边界

- Mac 浏览器只能经 SSH 转发访问板子（本机网络隐私限制），WebRTC 媒体走直连 UDP，HTTP 与 HTTPS 对照均显示
  WebRTC Connection Failed；HTTPS 下视频与麦克风实际使用需在可直连板子的浏览器中确认。
- Mac 到 Tailscale IP 的 `curl --resolve` 超时，系统信任链未在本机验证。
- 磁盘：/ 与 /var 同一分区，29G 中 15G 已用；只删本任务上传的临时文件（约 28MiB）。
  `one-kvm-audio-dae5089`、运行中的 `one-kvm-usb-ffc6130` 与 `before-onekvm-usb-*` 备份仍被启动器或 JSON 引用，保留。
- 最终 HTTP 开启、One-KVM 运行、麦克风开启；未发送 HID、未录放音频、未改 Tailscale 设置。
