# 2026-10-28：One-KVM 控制台面板、虚拟键盘与 WebRTC 套接字耗尽

标签：application deployment board

One-KVM `8c4924e4` 正式打包为 `2.5.1+vim4.20261027.3.dev.8.g9bfea0f.dirty`。单独安装 onekvm 包
因依赖同版本的 board/vfmcap/amlvenc 而不可行，改为七包整体升级（PiKVM 未在本次集合中，保持 20261025.13）；
同时删除开发 drop-in `96-frontend-r1.conf` 与 `/opt/vim4-onekvm/frontend-r1`，恢复二进制内嵌网页。

## 界面结果（1440×900，默认布局）

- 连接统计：非模态角落卡片，无遮罩，视频中心仍可点击；详细图表进入右侧停靠栏，视频右缘与栏左缘对齐。
- 虚拟键盘：原样式选择器 `.vkb .simple-keyboard …` 从未命中，simple-keyboard 只给容器加主题类，
  页面一直是库默认的 40px 键与 #ececec 外框。改为 `.vkb .hg-theme-default` 后，停靠高度 433 → 263px，
  视频高度 427 → 597px；浮动窗口 1200px 起 → 860px，位置保存在浏览器。
- 修饰键一次性、双击锁定；关闭键盘或页面隐藏时松开全部修饰键。快捷键录制期间按键不发往目标机。

## 浏览器测试的 HID 隔离

目标机就是开发 Mac。虚拟键盘的按键经 `/api/ws/hid` WebSocket 发送，不走 WebRTC DataChannel；
只覆盖 DataChannel 不能阻断按键。测试同时：Playwright `routeWebSocket` 拦截 `/api/ws/hid`
并回送 RESP_OK（0x00，否则首个按键一直等待连接而被误判为丢失）、页面内丢弃该 socket 的 send
并记录字节、丢弃 DataChannel send 与 HID HTTP POST。各轮记录到的目标机出站均为 0。

## WebRTC UDP 套接字耗尽

测试期间 8080 间歇返回 404/502（管理器日志「KVM 界面未运行」）。one-kvm 打开 1021 个 fd，
软上限 1024，其中 975 个 UDP 套接字（局域网、mDNS 224.0.0.251、Tailscale、通配各约 244 个），
axum 报 `accept error: Too many open files`。同期编码器反复分配 DMA 失败，页面显示无视频信号。
重启 one-kvm 后 fd 为 24；单个测试会话结束约 10 秒内回收到 30，说明并非每个会话都泄漏，
触发条件未查明（可能与编码失败期间的会话有关）。待查 WebRTC 会话在客户端异常断开时的回收；
提高 `LimitNOFILE` 只能推迟症状。

验证：`npm --prefix One-KVM/web test` 26 项通过。

## 打包与部署

- 全量打包先后遇到：amlvenc 源码契约测试找不到本次构建的插件（`build.sh` 把
  `gst-plugin-venc/amlvenc` 加入 `GST_PLUGIN_PATH`）；NanoKVM 测试磁盘余量 7.3G < 8.95G
  （`docker builder prune` 回收 6.2G）；JetKVM rolldown 原生绑定缺失（npm 可选依赖偶发，重试通过）；
  管理器 NAS 测试磁盘不足（`docker container prune` 仅清已停止容器 3.2G）。dev.8 `verify` 全部通过。
- 首次部署撞上 unattended-upgrades 持有 dpkg 锁，安装未开始、one-kvm 停在 inactive，`dpkg --audit` 干净；
  等锁释放后重跑成功。`board.py deploy/check` 仍以失败退出，原因是与本次无关的
  `var-lib-vim4\x2dkvm-nas-video\x2d15189625.mount`（SMB 192.168.50.201，前一日起失败）。
- 部署后：七包均为 dev.8；one-kvm 环境无 `ONE_KVM_FRONTEND_DIR`，内嵌 ConsoleView 分块含新键盘代码；
  HID 全隔离的浏览器会话 10 秒解码 601 帧（60.1fps，3840×2160），预设快捷键条按 Windows 显示，
  目标机出站 0。fd 启动 24，会话结束 12 秒后 32。
