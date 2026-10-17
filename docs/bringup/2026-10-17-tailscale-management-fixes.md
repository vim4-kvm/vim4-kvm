# 2026-10-17：Tailscale 管理修复部署

## 部署来源

工作区 `b6a132e`，管理器 `4b6bd03`，NanoKVM `4fd6617`。两个组件均从干净源码
通过 `ubuntu-build.py package/verify` 构建并隔离验证，再依次用
`board.py deploy --exclusive` 部署，没有发布或推送。

| 组件 | 安装版本 |
|---|---|
| vim4-manager | `2.5.1+vim4.20261017.28.dev.1.g4b6bd03` |
| vim4-nanokvm | `2.5.1+vim4.20261017.24.dev.1.g4fd6617` |

部署前没有其他板级测试进程，安装锁空闲，虚拟介质未插入。NanoKVM 包升级期间
暂停应用，结束恢复原选 One-KVM。系统未重启；HDMI、USB gadget 和 tailscaled
服务的进程及启动时间保持一致。`dpkg --audit`、两包 `dpkg --verify` 和失败服务检查均无输出。
旧 `/usr/libexec/vim4-tailscale` 与 `/etc/sudoers.d/vim4-tailscale` 均不存在。

## 实板回归

- 管理器以 khadas 运行，通过只读 LocalAPI 正常读取状态；没有配置 operator。
  设备列表响应不再包含 `curAddr`。
- 非法 Host 在首页和 API 均返回 403；跨站写请求返回 403。
  使用板上现有 Tailscale IPv4、IPv6 地址绑定 HTTP 客户端源地址，分别验证只读状态、
  `writable: false` 和全局 POST 拒绝。此项验证实际 RemoteAddr 判断，不代替外部网络 ACL 测试。
- 未确认断开返回 400；切换控制服务器缺少确认或确认的旧 URL 已失效时失败，原配置不变。
- 经局域网 SSH 发起确认断开，状态进入 Stopped，再连接成功回到 Running。
  官方控制服务器、DNS 接管关闭、主机名偏好和 Tailscale 地址保持一致。
- 已安装 Tailscale 时再次提交安装，独立 systemd 任务成功结束；重启管理器后仍能读取完成记录。
  此项未卸载或重新下载 Tailscale，也未模拟板上 APT 安装中途升级管理器。
- Chrome 经 SSH 隧道访问真实网络页：连接状态正常，断开前出现确认框，取消不发送写请求。
  1440 和 390 宽截图已保存，移动端无横向页面溢出，没有页面脚本异常。

板上 Tailscale 为 1.104.1，现有登录使用官方控制服务器。没有切换现有账号到 Headscale，
Headscale 实机登录与重连仍待具备对应账号时验证；此次实板验证了保留现有偏好的重连路径。
按用户要求未新增管理认证，局域网仍是受信任来源，设备元数据仍可读取。
本轮未验证视频解码、音频、HID、介质读写或延迟。

构建、隔离验证、部署、前后状态、实板 API 脚本及网页截图位于
`logs/tailscale-fix-deploy/`。
