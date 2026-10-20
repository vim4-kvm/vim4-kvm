# 2026-10-20：实验 One-KVM 局域网登录入口

摘要：7.3 实验版通过现有 vim4-manager 登录网关提供局域网访问，入口为
`http://192.168.50.210:8080/`，沿用原管理面板账户。One-KVM 的托管后端仍只
监听 `127.0.0.1:8082`；管理器控制面仅监听 `127.0.0.1:18080`。
从 Mac 直接经过局域网网关登录，H.264 3840×2160 约 60 fps，20 秒观察窗口内
解码丢帧、网络丢包和 freeze 均为 0。不代表完成其他客户端或长期稳定性验收。

## 配置与安装

新增 [one-kvm-edge-gateway.service](../../packaging/kernel-edge/one-kvm-edge-gateway.service)，
复用板上 `/opt/vim4-manager/vim4-manager` 及 `/var/lib/vim4-manager` 的账户和会话。
不修改后端的 managed 鉴权约束，也不重置账户。网关只在匹配的 7.3 内核且启动
参数包含 `vim4.one_kvm=1` 时启动，没有生产管理器的风扇恢复或存储迁移前置命令。

`WantedBy=one-kvm-edge.service` 使网关随实验后端启动；Requires/PartOf 使后端
停止或重启时同步停止或重启网关。安装并启动：

```sh
scp packaging/kernel-edge/one-kvm-edge-gateway.service vim4:/var/tmp/
ssh vim4 'sudo -n install -m 0644 /var/tmp/one-kvm-edge-gateway.service /etc/systemd/system/one-kvm-edge-gateway.service'
ssh vim4 'sudo -n systemd-analyze verify /etc/systemd/system/one-kvm-edge-gateway.service'
ssh vim4 'sudo -n systemctl daemon-reload && sudo -n systemctl enable --now one-kvm-edge-gateway.service'
```

本轮未重启实验后端，PID 保持 1274；生产管理器仍为 runtime masked。
没有修改 5.15 的服务、默认启动项、应用二进制或内核。回到 5.15 后仍使用原来的
生产服务；没有通过重启再次验收该回退路径。取消实验局域网入口可运行
`sudo systemctl disable --now one-kvm-edge-gateway.service`，SSH 隧道仍可访问后端。

## 验证与边界

板子内核为 `7.3.0-rc7-vim4kvm-uhd1+`，内核源码提交 `46f8489461869`。
部署的 manager 二进制 SHA-256 为
`4956b8d34189b61a4d42f7029063a8341d47aec013d986580c242c5cd0f9df27`。

- systemd 单元校验通过；网关和实验后端均 active，自动重启计数均为 0。
- `8080` 监听所有接口，`8082` 与管理控制面 `18080` 仅监听回环。
- Mac 直连登录页面 HTTP 200；未登录 HTML 首页 302 到登录页，应用 API 401。
  Mac 直连板子 `8082` 被拒绝。
- 使用原管理器账户经网关登录，Chrome 155 H.264 WebRTC 连接成功。
  预热 8 秒后观察 20 秒，3840×2160 解码约 60.032 fps，丢帧/丢包/freeze 为 0；
  呈现间隔 p99 33.7 ms、最大 46.2 ms，回调漏采 104 次。
  该窗口没有运行运动标记，不据此声称内容推进或光学延迟通过。
- 本轮没有验证 H.265、键鼠、音频、管理器应用切换或多客户端并发。
  7.x 的应用功能缺项沿用 [实验接入记录](2026-10-20-onekvm-wave5.md)。

证据：`logs/kernel-edge/lan-gateway-h264.json`、
`lan-gateway-h264.stderr` 和 `lan-gateway-status.log`。

网关运行时管理器会采样板级状态；新的独占驱动 benchmark 应先停止实验后端及
其网关，结束后恢复。生产 5.15 的普通管理器和实验网关不能同时占用 8080。
