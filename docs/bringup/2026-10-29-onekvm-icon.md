# 2026-10-29：One-KVM 新图标

标签：application deployment

One-KVM `8a39b619` 把位图图标（显示器加键盘剪贴画）换成 `web/public/favicon.svg`：白色圆角底、
深灰屏幕、蓝色指针，配色与 vim4-manager 标志一致；指针外圈留白，16 px 仍可分辨。
`favicon.png`（512 px）由 SVG 渲染，用于触屏图标和不支持 SVG 图标的浏览器；`BrandMark` 改用 SVG。

打包为 `2.5.1+vim4.20261027.3.dev.11.g040c56a`，七包整体升级，同时删除开发前端覆盖
`96-frontend-r1.conf` 与 `/opt/vim4-onekvm/frontend-r1`。部署后 one-kvm 以 `image/svg+xml` 提供图标，
浅色、深色控制台顶栏均显示新标志；HID 全隔离会话解码约 60 fps，数据通道往返 2.6–3.6 ms，35 个 ping 全部回包，
目标机出站 0。`board.py deploy` 仍因无关的 NAS 挂载单元失败返回 1。
