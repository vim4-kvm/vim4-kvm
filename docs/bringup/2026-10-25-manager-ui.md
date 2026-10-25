# 2026-10-25：管理面板前端重构验收与部署

## 版本与范围

管理器 main 合入提交 `719ab65e369ea0a8f807f305649abebdb4ac7750`，已推送；
整合重构、Claude polish 与用户截图验收修正，并保留 main 的 HDR 输出开关及透传音频 xrun 修复。
真实服务发现登录页默认 favicon 请求 404，补修 `b44a4b8` 后 main 与重构分支均已推送。
实现和完整本机证据见
[管理器验收记录](../../vim4-manager/docs/ui-refactor/verification.md)。

- destructive 文字改为 `#ca3135`，白底 5.25:1、10% 浅红底 4.51:1；深色最弱的 15% 底为 4.53:1。亮红圆点与仪表填充保留。
- 文件大小/日期使用共享固定右对齐列，桌面隐藏操作不占列宽，触屏使用行尾 Radix 菜单；删除确认无自动关闭，取消后恢复菜单焦点。
- 共享 action helper 统一抑制已由 InlineError 呈现的相同错误 toast；成功提示保留。
- 侧栏实际滚动视口保持全高；长截图中的一屏高度是 fixed 元素的截图表现。
- 没有业务文案变更。唯一自定义样式文件 `index.css` 为 150 行。

## 本机与隔离验证

`pnpm --dir web typecheck`、`build`、管理器根 `go build ./... && go test ./...` 通过。
全部 19 个 `web/tests/*.mjs` 入口通过，包含 15 个行为回归、2 个 fixture 和 2 个截图入口；
auth 含 22 场景。截图额外跑 phase3，phase1/2/3 的 after 图共 362 张，均已提交。
取消 body 解码回归使用显式同步，覆盖生产懒加载顺序；Tailscale 独立 HTML harness 用既定 Vite 开发入口。

helper Python 回归 212 项：200 通过、12 跳过。主仓离线回归 257 项：247 通过、10 跳过。
本机构建总产物 910.1 kB / gzip 297.7 kB；管理页首屏 JS gzip 154.7 kB。
详细本机日志保存在 `/tmp/vim4-ui-final/`。

## 上板过程与自动核验

部署及其真实服务核验使用 `/usr/bin/lockf /tmp/vim4-board.lock` 与
`/usr/bin/lockf /tmp/vim4-heavy.lock` 串行持锁，等待 UU 会话释放硬件。
通过 `tools/ubuntu-build.py package/verify --component manager` 构建并隔离验证，
再经 `tools/board.py deploy --exclusive` 安装 manager 单组件包。
此路径仅重启管理器，不操作 KVM、HDMI、gadget、EDID、启动项或音量设置；不测试声音，不保留回退副本。

最终部署 **`2.5.1+vim4.20261025.9`**，管理器源码为
`b44a4b812cb9b2bcceab023b472c6747144f2624`，主仓构建来源为
`64c0ec18d18de1d119e305e70a4558cbd9849ad2`。两份源码均从干净固定提交构建，
ARM64 包隔离验证通过，SHA256、ELF、依赖、sudoers、配置保留和损坏文件拒绝均通过。
主仓 `workspace.toml` 已固定管理器最终提交。

首次自动开发包因沿用较早 release tag，排序低于板上版本，被降级门禁在停服务前拒绝；
随后从干净提交构建 `.8` 正式包。真实浏览器核验发现 `login.html` 缺少图标声明，
浏览器请求 `/favicon.ico` 得到 404。补上与管理页相同的 SVG 声明，重跑 typecheck、build、
22 个认证场景及 Go 构建/测试，再构建和部署最终 `.9`。未把两次未完成核验记作最终通过。

最终真实服务核验通过：登录页、全部 12 个管理页面的读取接口均为 HTTP 200，
桌面 1280px 与关键手机 390px 页面均无横向溢出；**控制台错误 0、页面异常 0**。
除登录外只发 GET/HEAD，不修改任何设置，不进入 KVM 视频会话，不测试声音。
HDMI 输出接口与页面一致：running，3840×2160 60Hz，HDR10/BT.2020，未缩放且未转 SDR；
HDR 与透传开关按接口状态校验。

部署前后 One-KVM、HDMI、gadget、tvserver 的 MainPID 与启动单调时间完全一致：
One-KVM 195244、HDMI 1096、tvserver 1075，gadget 为已完成的 oneshot（MainPID 0）。
仅管理器重启，运行内核仍是 `5.15.137-vim4kvm-hdrdual6`。

证据均已提交：

- [自动核验结果与 16 张截图清单](2026-10-25-manager-ui/verification.json)
- [HDMI 输出桌面](2026-10-25-manager-ui/output-light-1280.png)、[手机深色](2026-10-25-manager-ui/output-dark-390.png)、[登录页](2026-10-25-manager-ui/login-light-1280.png)
- [透传状态](2026-10-25-manager-ui/passthrough-state.json)、[构建来源](2026-10-25-manager-ui/sources.json)
- [部署前服务指纹](2026-10-25-manager-ui/services-before.txt)、[部署后服务指纹](2026-10-25-manager-ui/services-after.txt)
- [只读浏览器核验脚本](2026-10-25-manager-ui/check.mjs)（设置 `MANAGER_PASSWORD`、`PLAYWRIGHT_MODULE`，传截图输出目录后运行；上板时仍须持双锁）

完整构建、安装、验证日志在本机 `/tmp/vim4-ui-final/`，最终安装日志为 `final-deploy/operations.log`。
