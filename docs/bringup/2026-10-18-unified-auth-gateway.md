# 2026-10-18：管理器统一登录与 8080 KVM 网关

vim4-manager 提供单一管理员账号密码登录，管理面板（80）与 KVM 界面（8080）共用会话；
四个 KVM 应用改为只监听 `127.0.0.1:8081` 并关闭自身网页登录，由管理器 8080 网关鉴权后反向代理。
行为说明见 [vim4-manager/docs/auth.md](../../vim4-manager/docs/auth.md)；设计稿与调研在不入库的 `logs/unified-auth/`。

提交：vim4-manager `adfe0f6`…`deeb7e8`（登录、登录页与账户页重设计、网关），NanoKVM `114b48e`、`e88e3bc`，
JetKVM `384e6d2`，One-KVM `912ca755`（`--auth-mode managed`），PiKVM `955f3c9f`，主仓库 `4ec065e`、`2d19500`、`1d633bb`。
部署包 `2.5.1+vim4.20261018.32.dev.11.g1d633bb.dirty`（七包）与 `2.5.1+vim4.20261016.1010.dev.1.g955f3c9`（PiKVM），
`board.py deploy --exclusive` 安装，冒烟通过。dirty 来自 vim4-manager 未跟踪的 `.DS_Store`。

开发板管理面板账户 admin/khadas-kvm（[默认账户](../hardware.md#默认账户开发环境)），板级浏览器工具用 `MANAGER_PASSWORD`。

板上结果（Mac 192.168.50.239 → 板子 192.168.50.210，有线局域网）：

- 监听：80、8080 为 vim4-manager；应用只在 127.0.0.1:8081；Mac 直连 8081 失败；8443/443 未监听。
- 未登录：8080 页面 302 到 `/__vim4/login`，API 与 WebSocket 升级 401，`/redfish` 404，无密钥 `/api/mcp` 401；跨站 POST 403。
- 登录：Argon2id 单次往返约 0.33 s；第 6 次错误密码返回 429（锁定 30 s）；管理器重启后会话保持。
- 吊销：「退出其他设备」后另一浏览器的 One-KVM `/api/ws` 5 ms 内断开，之后 API 401。
- 视频经网关：One-KVM WebRTC H.264 4K 20 s 60 fps、0 丢帧/丢包；kvm-switch-check 两轮 One-KVM/NanoKVM/JetKVM 切换均 4K 60 fps、
  首帧 3.3–6.2 s；PiKVM 页面无登录、WebRTC H.265 4K60、MJPEG 3 s 113 MB 数据、`/login` 302 到 `/`。
- 代理开销：NanoKVM H.264 direct（WebSocket）4K 30 s，经网关与 SSH 转发直连均 1800 帧；vim4-manager CPU 3.0% 对 0.2% 单核，
  NanoKVM 10.7% 对 10.3%（/proc utime+stime，30 s 窗口）。
- 键鼠（NanoKVM，input-check，经网关对 SSH 转发直连）：按键中位 4.57 对 5.02 ms，移动 3.39 对 3.22 ms，点击 3.29 对 3.71 ms，无多余重复。
- 端到端延迟（NanoKVM WebRTC H.264 4K，滚动画面，`VIM4_HDMI_DISPLAY=RTK`，各 20 s）：presentation 中位 65.0 对 64.5 ms，
  p95 74.1 对 73.2 ms，均 60 fps、0 丢帧/丢包。WebRTC 媒体不经网关，预期无差异。

**未验证**：虚拟介质上传经网关；PiKVM 键鼠（smoke 会操作 Mac 指针，未运行）；
JetKVM/NanoKVM 网页中隐藏账户入口的实板截图；Tailscale 来源的短有效期与未加密提示；首次设置流程在新刷镜像上的实际表现；网页更新路径升级各包。

日志：不入库的 `logs/unified-auth/`（board-*.log、perf-*.json、shots-board/）。
