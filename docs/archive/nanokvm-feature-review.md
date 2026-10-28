# NanoKVM 功能差异评估

> 归档快照（2026-10-13）：固定版本的NanoKVM 功能差异评估，不代表当前状态，现行入口见 [应用](../subsystems/application.md)。

2026-10-13：官方 https://github.com/sipeed/NanoKVM 的 main 已浅克隆到
`NanoKVM/`，提交 `d0ff328db81c8d08a9133639ce63d32cba54f172`。
对比当前 `NanoKVM-Pro` 的 VIM4 提交 `60afb9e`。仅静态阅读源码、路由和更新记录，
没有运行 NanoKVM，也没有更改板子。目录独立于主仓库，暂不加入生产构建清单。

## 值得引入的功能

| 功能 | 当前差异 | VIM4 接入方式与优先级 |
|---|---|---|
| 鼠标有效区域 | NanoKVM 支持自动检测黑边、手动框选、原始尺寸预设；当前 Pro 没有对应区域模型 | 高：复用 geometry、区域 UI 和坐标映射；保留现有旋转、滚轮、按键释放修复。先验证手动区域，再启用自动检测 |
| 手机相对鼠标手势 | NanoKVM relative.tsx 有轻点、长按、双击拖动、双指滚动；当前相对模式没有触控事件处理 | 高：复用手势逻辑，合并当前生命周期释放机制；验证 touchcancel、失焦、菜单打开不会留下按下状态 |
| 键盘锁定灯 | NanoKVM 读取 HID Output report，通过 WS 显示 Caps/Num/Scroll Lock；当前没有回传链路 | 高：读键盘 hidg 输出报告，适配当前设备生命周期；USB 重新绑定前也必须关闭新增 reader，并在恢复后重新读取。无需额外物理 LED |
| 视频状态与失败重试 | NanoKVM 有 capture-status 覆盖层、信号状态、WebRTC 失败原因与重试；当前 Pro 部分失败仍只写 console | 高：保留 VIM4 编码管线，补齐无信号、切换分辨率、编码失败、ICE 失败状态。原厂负错误码不能直接当 VIM4 状态 |
| MCP 服务 | NanoKVM 提供截图、文本、按键、移动、点击、滚动工具，API Key 和设置入口；当前 Pro 无 MCP 路由 | 高：复用协议层；截图接现有 Snapshot，输入接 HID；一起接入控制权协调，避免人工与 Agent 同时输入 |
| 多用户与会话撤销 | NanoKVM 有 admin/user、用户管理、HttpOnly Cookie、tokenVersion 和 WS 会话撤销；当前只有单账户接口 | 中：迁移网页身份存储及所有 VIM4 路由的权限检查，独立于 Ubuntu 账户；保留用户既定免登录选项，不自动更改密码 |
| PicoClaw | NanoKVM 有聊天侧栏、模型配置、历史会话及控制权切换；当前 Pro 是独立的 AI 助手实现 | 中：属于新增 AI 方案，不是当前助手缺失全部功能。需替换 ARM64 下载包、/root 路径和 SysV 脚本，使用应用数据目录及 systemd |
| 镜像下载取消与预期摘要 | NanoKVM 有下载取消及可选 SHA-256；当前 Pro 已有下载后校验接口，但下载请求没有预期摘要和取消入口 | 中：沿用当前完整下载后才发布文件的处理，补上下文取消与摘要比对；不能把校验已有文件等同下载前指定摘要 |
| DNS 设置 | NanoKVM 提供 DHCP/手动 DNS 与有效配置显示；VIM4 静态 IP 辅助程序仅保留已有 ipv4.dns | 中：复用界面/校验，后台通过 NetworkManager 配置；不照搬 udhcpc hook 或覆盖 resolv.conf |

## 性能与维护改进

- NanoKVM 的 `server/service/stream/h264_source.go` 将 Direct/WebRTC 接到同一
  H.264 源，用有界订阅队列隔离慢消费者，并等待关键帧恢复。当前 VIM4 的
  WebRTC 发送循环逐客户端写入，值得用慢客户端场景验证后再改。
  这不是无损加速：拥堵时主动丢弃滞后帧以降低延迟，不能宣称所有客户端零丢帧。
  VIM4 还需保留采集 PTS、H.265、音频和当前会话释放行为，不能直接替换整个模块。
- NanoKVM Direct 有解码积压恢复与硬件解码偏好，可对照当前 worker 改进；
  需要独立测试 H.264/H.265、关键帧请求、网络抖动，不凭更新记录宣称更低延迟。
- 自动黑边检测每秒在最大 640×360 的画布上采样，连续三次一致才采用。
  暗色桌面仍可能被误判为黑边；即便缩小采样，4K 视频回读也需实测成本。
  应保留手动区域与关闭选项。

## 已有能力与不应直接替换的部分

- WOL、终端、脚本、镜像管理、Tailscale、更新源/离线包等当前已有，不能算新增。
- 当前 VIM4 还有 H.265、HDMI 音频、麦克风、4K60 编码和自定义 EDID；NanoKVM
  主线的 SG2002 采集、编码和系统包不是这些能力的升级替代品。
- 当前 Ubuntu deb 更新有依赖预检、sudoers 校验和 sync，应该保留；只评估其
  下载取消、空间检查和重启期间锁生命周期等具体改进，不替换为原厂 tar 更新流程。
- 当前无查看者会释放视频编码器；NanoKVM 进一步停止 HDMI 采集的策略，可能影响
  Mac 的 HPD/显示器状态和新会话启动，暂不作为默认优化。
- ATX、OLED、原机电源管理仍需要对应硬件；仓库有实现不代表 VIM4 可直接启用。

## 主要源码入口

- NanoKVM：`CHANGELOG.md`（2.5.0/2.5.1）、`web/src/pages/desktop/screen/` 下的
  `geometry.ts`、`auto-region.tsx`、`manual-region.tsx`，以及 `mouse/relative.tsx`。
- NanoKVM：`server/service/hid/leds.go`、`service/ws/keyboard_led_status.go`、
  `web/src/pages/desktop/capture-status/`、`screen/h264-webrtc.tsx`。
- NanoKVM：`server/router/{mcp,control,auth,download}.go`、`server/authn/`、
  `server/service/{mcp,inputcontrol,controlmode,picoclaw}/`、`service/network/dns.go`。
- 当前 Pro：`server/router/platform_vim4.go`、`server/common/snapshot_vim4.go`、
  `server/service/stream/webrtc/manager.go`、`service/storage/{download,checksum}.go`、
  `web/src/pages/desktop/mouse/`、`deploy/vim4/vim4-system`。

建议顺序：输入区域/触控/锁定灯和视频错误反馈 → MCP 与控制权协调 → 下载/DNS →
按需求引入多用户或 PicoClaw。慢客户端优化单列性能回归，避免与功能移植混测。
