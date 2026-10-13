# NanoKVM 基线切换

2026-10-13：应用仓库切换到 [vim4-kvm/NanoKVM](https://github.com/vim4-kvm/NanoKVM)，
基于官方 main `d0ff328db81c8d08a9133639ce63d32cba54f172`，工作分支为 `vim4`。
旧 NanoKVM-Pro 工作树及未完成修改保留，不再参与默认构建。

保留 NanoKVM 原有桌面、菜单、账户/角色、MCP、PicoClaw、控制区域、移动端手势、
共享视频源和 Direct 流控。VIM4 采集、编码、音频、HID、虚拟介质、EDID、
Ubuntu 网络/系统和 deb 更新通过平台适配接入。前端沿用原布局，添加已有 VIM4 控件。

安装继续使用 `vim4-nanokvm` deb、`nanokvm.service`、`/opt/vim4-nanokvm`，
保留原有设置、网页账户和免登录选择，不更改 Ubuntu 密码。PicoClaw 的官方资源位于
`kvmapp/picoclaw`，打包到应用目录的 `picoclaw`；ARM64 helper 安装到 `/usr/libexec`。
旧更新器的 `nanokvm_pro_*.tar.gz` 命名保留，包内容仍是完整、校验过的应用 deb。

## 验证入口

- VIM4 与默认 Go 全套测试、两个后端构建；默认目标通过会 abort 的 ABI stub 检查，
  硬件调用不能伪装成模拟通过。
- VIM4/默认前端 TypeScript 与生产构建；仍有上游的大 chunk 提示。
- `NanoKVM/web/tests/input.mjs`：失焦释放、旋转坐标、裁剪拖拽、取消触摸和键盘释放。
- `NanoKVM/web/tests/menu.mjs`：原版设置/MCP、分辨率与帧率标注、打开菜单不覆盖设置。
- `NanoKVM/web/tests/audio.mjs`：独立音频使用服务端 ICE 配置，协商 Opus 双向音轨。
- Ubuntu helper 测试 30 项（1 项平台限制跳过），工作区测试 40 项。
- 组件打包/检查：`tools/ubuntu-build.py package/verify --version VERSION`。

浏览器测试使用独立测试页和模拟接口，不向被控 Mac 注入输入。硬件视频、音频、
USB 重绑定、重启和新镜像首次启动需在独占板子时另做回归；旧版 4K60/延迟记录
不自动成为新基线的通过证明。账号组网与 AI 模型调用还需要用户凭据。

并行任务可能修改 JetKVM 工作树，完整打包需从固定提交创建独立、干净的构建目录，
不能重置他人的工作树或把未完成的修改混入应用包。构建结果的 `sources.json`
记录各仓库提交与内容摘要。
