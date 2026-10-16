# 2026-10-15：UU Mac 身份的键盘错码

用户切换并登录 Mac 身份后报告 Backspace 输入字符 3。板端确认配置为 macos，
旧输入路径却统一解析 Windows VK；macOS Backspace 的虚拟键码 0x33 在 Windows
命名空间恰好为 Digit3。按房间绑定的设备身份分别解析 Windows VK 与 macOS
虚拟键码，后者依据本机 Apple SDK HIToolbox/Events.h 的物理键位表。
同时覆盖按下、松开、点击及左右修饰键；未知 Mac 键码不回退到 Windows。
Mac 的显示桌面、锁屏与任务菜单分别发送 Command+F3、Control+Command+Q、
Command+Option+Escape（强制退出窗口）。Fn、媒体及部分 JIS 专用键尚未覆盖。

597 项 Rust 测试与 ARM64 release 通过，新增相同线协议键码在两个身份的
Backspace/Digit3 区分、Command+C、断线释放及未知键码不污染修饰键状态的回归。
隔离包验证通过，包含真实 dpkg 升级、配置保留及认证更新 API。
仅更新 One-KVM 到 `2.5.1+vim4.20261015.5`，重启后 active、HTTP 200、
dpkg -V 无差异、UU host online，保留 macos 身份与 vim4-kvm 名称及登录。
尚待用户用实际 UU 客户端确认输入效果，自动测试不作为端到端键盘验收。

制品位于 `build/packages/2.5.1+vim4.20261015.5/`，deb SHA256：
`d1079d52fc76cc7c937122d8c8ea3fec85bb5045f7ac79d628575cfee590a5ea`。
UU 改动仍在原有未提交功能工作树，sources.json 记录源树摘要。
证据：`logs/uu-remote/mac-keyboard-{tests,release,package-verify,deploy,after-deploy}.log`。
