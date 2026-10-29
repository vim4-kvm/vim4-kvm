# 2026-10-28：One-KVM 板子终端侧栏

标签：application deployment board

One-KVM `vim4` 分支的前端终端从模态弹窗改成视频旁的常驻 iframe 侧栏；
构建包含工作区原有未提交的控制台工具栏改动，本次没有提交或重启服务。
部署仍使用 `/opt/vim4-onekvm/frontend-r1/`，服务的 `ONE_KVM_FRONTEND_DIR` 已指向此目录。

板上 ttyd 的实际接口与约束：

- `window.term.fit()` 可重新适配尺寸；DOM 容器是 `#terminal-container`。
- 此版本没有公开 `term.input()`，按键通过 `_core.coreService.triggerDataEvent(bytes, true)`
  进入原有 ttyd 输入链路；不能用会启用括号粘贴的 `paste()` 发送方向键等控制字节。
- 终端在 WebSocket 握手前已经存在，不能据此判定连接成功。服务器标题和 ttyd 的
  Connection Closed / Reconnecting / Press ⏎ to Reconnect 提示用于状态显示。
- 网关会将客户端 `close(1000)` 报成 1006，ttyd 会立即自动重连。断线验收关闭真实 socket，
  再模拟正常 close 事件，固定断线状态后检查手动重连；不停止服务。
- 浮动工具栏需要随视频剩余区域收窄和居中，否则会挡住终端标题与按钮。
- 移动端在 iframe 就绪、面板显示和尺寸变化后显式 fit；横屏触屏且高度 ≤500px 保留 sheet。

验收脚本：`One-KVM/web/tests/terminal-panel.browser.mjs`。
浏览器测试在所有页面和 iframe 中拦截 WebRTC、WebSocket 与 HTTP HID 出站；
只允许终端 shell 的无害命令，不向被控 Mac 发键鼠事件。
截图与测量位于 `/tmp/okvm-ui/term-r1/`，最终结果见该目录 `measurements.json`。
构建入口 `npm --prefix web run build`，单测入口 `npm --prefix web test`。

本轮通过 24 个桌面组合（1440×900 / 1920×1080，current / floating / sidebar，
中英文、明暗主题，每组另验真实 fullscreen）和 8 个移动组合（390×844 / 844×390），
生成 128 张截图，页面异常与 HID 发送尝试均为 0。
最后的连接状态保持修正后，另跑桌面与手机两组回归，包含断线后调整字号：
尺寸提示替换重连提示时仍保持断线状态。
默认面板宽 648 / 864px，视频右边与面板左边差为 0px；从 500px 拖宽到 700px，
`tput cols` 从 69 增到 97，刷新后保留 700px。
前端 12 项单测通过；工作区离线测试 291 项完成、跳过 10 项。

触屏验收使用 Chrome 浏览器模拟，不代表真实 iOS/Android 软键盘的实机测试。
