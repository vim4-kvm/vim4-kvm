# 2026-10-28：One-KVM 终端浮层与断线提示

标签：application deployment board

终端第二轮继续前端覆盖部署，无服务重启和提交。
当前 ttyd 的 Preact Terminal 组件通过 `body.__k` 下的 `__c.xterm` 持有客户端对象，
前端将这些版本相关细节集中在 `One-KVM/web/src/lib/ttydClient.ts`。

- 关闭 `resizeOverlay`、`reconnect`、`doReconnect`，隐藏原生 overlayNode，并以空函数替换 showOverlay。
- showOverlay 是 @bind 修饰的只读 getter，必须用 Object.defineProperty 覆盖，直接赋值会抛异常。
- disableReconnect 本身仍保留断线 Enter 重连：移除原生 socket close 监听，关闭时释放 ttyd 输入监听，
  改由面板按钮重新加载 iframe。socket readyState 直接驱动连接状态，不再读取浮层文本。
- 初始 iframe 在适配完成前不可见，避免首次 resize 提示闪现；不依赖 iframe load 事件发现 xterm。
- ttyd 的配置包类型为 ASCII '2'，可在 frame load 后才到达。收到并应用原生配置后重新同步用户字号与主题。
- 断线栏固定 32px，内容半透明并隐藏光标；重连按钮 disabled + spinner。头部固定 36px。
- 移动按键行两端内边距 8px，24px 渐隐提示随实际可滚动方向显示，使用 proximity scroll snap。

验证入口为 `One-KVM/web/tests/terminal-panel.browser.mjs`，设置 TERMINAL_TEST_ROUND2=1。
截图与测量写入 `/tmp/okvm-ui/term-r2/`；所有浏览器与 iframe 拦截 HTTP/WebSocket/WebRTC HID 出站。
手机使用 Chrome 触屏和合成 visualViewport，未覆盖真实手机 OS 软键盘。
