# NanoKVM 基线切换

> 归档快照（2026-10-15）：固定版本的NanoKVM 基线切换，不代表当前状态，现行入口见 [应用](../subsystems/application.md)。

2026-10-13：应用仓库切换到 [vim4-kvm/NanoKVM](https://github.com/vim4-kvm/NanoKVM)，
基于官方 main `d0ff328db81c8d08a9133639ce63d32cba54f172`，工作分支为 `vim4`。
旧 NanoKVM-Pro 已退役并从工作区与 GitHub 移除，历史提交以 git bundle 离线归档。

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

## 本次构建结果

`2.5.1+vim4.20261013.4` 已从干净提交构建并通过包校验：NanoKVM
`a79114e7139a8bf8f5d1a7700a01cd768bfd0f41`，工作区构建代码
`391a87a37bbdc5f2abf568fc53627306cfa6be79`；其他仓库按清单固定版本。
产物在 `build/packages/2.5.1+vim4.20261013.4/`，`sources.json` 中
`development=false`。校验包含 ARM64 ELF/动态依赖、sudoers、原设置保留、
损坏文件拒绝、PicoClaw 资源/权限以及应用版本与 deb 版本一致性。

应用更新归档在 `build/releases/nanokvm-2.5.1+vim4.20261013.4/`；仅是应用
升级包，不是可刷入的整机镜像。本轮没有部署、重启或更改板子配置。

## 后续部署与切换验证

`2.5.1+vim4.20261013.5` 已将六个组件完整部署到 VIM4。NanoKVM 固定为
`93d8fc0edd5e75c65ff6f20d895381be37a14b06`，manager 固定为
`1575c432af8b8c320c3e94e1db2f342c19dd3067`，JetKVM 固定为
`1e469f5068618768973846985ef66abec2306443`。从干净提交构建，包校验通过。

Chrome 实机完成 NanoKVM → JetKVM → NanoKVM → JetKVM → NanoKVM，
每次采样 10 秒均为 3840×2160、约 60fps、零丢帧/丢包；切换到首帧
1.89–2.12 秒。这是当前桌面场景的切换恢复测试，不是端到端输入延迟或长时间
运动场景测试。最终 NanoKVM 启用，JetKVM 停用；详情见
[NanoKVM 正式部署与 JetKVM 往返切换](../bringup/2026-10-13-nanokvm-deploy-jetkvm-switch.md)。

## 移除旧 Smart Assistant

NanoKVM `d64833d` 删除旧助手菜单、翻译、安装/启动 API、Python 服务及其专用依赖，
保留 PicoClaw/MCP、截图和输入仲裁。安装包和手动安装入口共用旧助手清理脚本：
停止匹配旧脚本命令行的进程，移除 `/opt/vim4-nanokvm/assistant`、
`/var/lib/vim4-kvm/assistant` 和旧日志；不删除 PicoClaw 数据或系统 Python 包。

开发验证包 `2.5.1+vim4.20261013.6`（`--allow-dirty`）完成完整 Ubuntu 构建、
默认/VIM4 后端测试与构建、VIM4 前端构建及包校验；另跑默认前端构建和菜单浏览器回归。
迁移测试在隔离容器启动旧助手模拟进程，确认重复配置时进程终止、旧文件删除，
PicoClaw 与应用配置保留。宿主部署测试 28 项、1 项平台限制跳过。
日志为 `logs/remove-assistant-{helpers,package,verify}.log`。
本次仅修改源码与安装配方，未部署到板子；板子仍运行 `.5`。
