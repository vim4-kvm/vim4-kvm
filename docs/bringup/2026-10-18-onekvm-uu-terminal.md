# 2026-10-18：One-KVM UU 远程终端与卡片重设计

One-KVM `7af5e5ff` 让 UU 官方「终端远控」可用：终端连接（capture_type 8）独立于桌面会话，
新会话在终端内选择 KVM 板子、被控机串口或被控机 SSH，只开一项时直接打开。
三项默认关闭；串口支持 USB 转串口与新增的 USB ACM gadget（占 2 个 IN 端点）；
SSH 使用板子私有密钥与 known_hosts。设计与接口合约见不入库的 `logs/uu-terminal/design.md`。
网页 UU 卡片改为状态行、账号行与「连接 / 桌面 / 终端」页签，选中即保存，并移到第三方访问首位；
桌面宽度下卡片高度由约 1180px 降到约 440px。

代码审查发现的大输出断开、网络抖动后冻结、输入过载结束会话、登录失效未清理终端、PTY fd 泄漏
已在 `b75553c5` 修复。主仓库给 vim4-onekvm 显式增加 openssh-client 依赖。

部署包为 `2.5.1+vim4.20261018.1.dev.3.g7af5e5f.dirty`（dirty 为当时未提交的 package.py 依赖修改），
通过 `board.py deploy --exclusive` 安装，部署冒烟通过。开发版本基线低于板上 `20261018.1`，
因此在本地给 One-KVM `be5959d1` 补了同名 tag（未推送）。

验证结果：

- ARM64 Rust 库测试 672 项通过、1 项忽略；helper Python 测试 20 项通过；前端类型检查与构建通过。
- 浏览器截图检查新卡片桌面与 390px 宽度布局、三个页签与第三方访问排序。
- 板上已开启「KVM 板子」目标，状态接口返回终端状态。
- **未验证**：官方 Mac/Windows/手机客户端实际打开终端、选择器显示、错误文案、重命名、
  DETACH 回放；串口（板上当前无串口设备、ACM 未启用）与 SSH 实连；端点超限回滚。

日志位于不入库的 `logs/uu-terminal/`。
