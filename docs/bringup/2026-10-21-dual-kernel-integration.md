# 2026-10-21：双内核完整系统集成

用户要求：7.x 运行完整 vim4-manager 和四种 KVM，在面板切换应用、切换内核，
同一应用在 5.15 / 7.x 之间继续使用配置与数据。UAC2 实际录音暂缓验收。
本次已完成运行时整合、组件包部署与实机双向切换验收，边界见末节。

## 当前实现

完整 manager `:80`、登录网关 `:8080`、四种应用的回环 `127.0.0.1:8081` 均接入。
`vim4-kvm-run` 根据 5.15 / 匹配的 7.3 选择厂商或 V4L2/Wave5 后端和独立插件缓存。
正式 One 服务共用 `/var/lib/one-kvm`，板载音频名称和 NV12/NV21 在内存转换，
保存仍用兼容 5.15 的名称。Nano/Jet/Pi 保留各自原目录；账户、网络、数据盘、NAS 共用。
四套不同数据库不合并，跨应用介质通过原有共享目录访问。待导入实验镜像目录为空。

共享插件 `vim4v4l2src` / `vim4wave5enc` 按设备名定位，NV12 单 DMA 分配拆成两个
平面引用并持有父缓冲租约；1080p 的 UV 偏移和编码器 1088 行对齐分别处理。
编码输出先复制至缓存内存，再解析 NAL；保留 H.264/H.265、码率/GOP/关键帧控制。
完整 NULL 清理释放子管线。私有 V4L2 插件按锁定源码与四个补丁重新构建。

内核补齐标准 G/S_EDID 与安静风扇曲线。相同 EDID 不触发 HPD；不同表/禁用 DDC
在 DMA 租约存在时拒绝 EBUSY。三个 KVM 的原生 EDID 操作释放采集后重新连接；
manager 则停止/恢复当前应用。HDR 曲线在线写。风扇默认 60/80/100，故障下限 15%，
100°C 全速保护保留。新增 `VIM4-1080P60-SDR8`，不改原始厂商/上传的 EDID。

## 启动与回退

`Default` 保留 `5.15.137-vim4kvm`，新 `FullKvm` 使用 `7.3.0-rc7-vim4kvm-uhd1+`。
FullKvm 屏蔽厂商 TV/audio、旧 Android binder/串口蓝牙初始化和三个实验单元；
内核 HCI 与 BlueZ 正常启动。只在 rc.local SHA 与原厂原文一致且已有 SSH 主机密钥时
屏蔽该旧 LED/权限脚本；自定义 rc.local 不自动屏蔽。5.15 不使用这些新屏蔽项。
原 OneKvmTest、实验目录与 ELF 保留。
`vim4boot` 在选择前校验 root 清单、Image/DTB/完整模块 SHA256 和全部启动参数，再
原子修改 DEFAULT。切换需要重启，没有自动失败启动回退。挂载虚拟盘时拒绝切换。

`register-runtime.py inventory` 从同次构建生成完整证明；安装后 `register` 在板上
核对模块全量再登记清单，保留当前默认项。它不安装、不启用应用、不重启。
应用依赖 `vim4-runtime-api-1`，编码插件提供 `vim4-wave5-api-1`，须先更新配套平台。

板上 `/var/backups/vim4-dual-kernel-20261021` 保存原启动配置、ELF、服务/助手、
SQLite 在线备份、小配置和旧完整 7.x 模块/Image。5.15 Image SHA256 仍为
`e689f0b003375663d19643fbf3dcc6c54185966d3f4bc7ebae38dd24a6fdfdd1`。
Stock 和 SPI OOWOW 保留；普通回退在面板选择 5.15 重启。启动失败需串口或 OOWOW，
不能声称无人值守自动恢复。

## 本次上板记录

日志在本机 `logs/dual-kernel/`。以下不替代以前延期项目。

| 前缀 | 通过内容 |
|---|---|
| `manager-mainline-first` | 完整面板/网关、4K59.999 输入及音频状态、风扇写回恢复、EDID/Jet 配置、存储/NAS/Wi-Fi 状态接口 |
| `switch-mainline-first` | 四应用共 8 次切换，每轮 4K 约 60fps；Jet 首轮 1 帧丢弃，其余零丢弃，丢包均零；结束 DMA=0、taint=0 |
| `kernel-roundtrip-ui-fixed` | 面板确认 7→5→7，7 保存 1080p/5 实际播放，5 保存 720p/7 实际播放；两侧各上传 64KiB 临时镜像，ID/名称/大小/SHA 往返一致，最后恢复并清理 |
| `one-shared-hid` | 正式 One 的键盘、绝对/相对鼠标、点击和滚轮，限定本机接收窗口 |
| `jet-mainline-features3` | 原生 H.265 4K、G.722 实际解码 peak=0.1115、键鼠；500 个音频包，视频零丢包/丢帧 |
| `one-shared-media` | RO/RW 虚拟盘、1MiB 写回哈希/fsck、应用重启保留挂盘、主机弹出；挂盘时应用/内核/USB 变更拒绝、LUN 不变 |
| `one-native-board-sdr8-forward` | 原网页 SDR8 FHD→厂商 UHD→RTK UHD 恢复，每轮 1.5s 约 90 帧；HDR 曲线写回恢复 |
| `one-scaling-yuv444-fix` | 运动 H.264/H.265、UHD/FHD/720p 缩放、MJPEG；三处帧号一致且递增，UHD WebRTC 约 60fps，结束 DMA=0；此轮尚无三原色断言 |
| `one-scaling-colors-fixed` | 修正最终 Y/Cb/Cr 顺序后，以上全部模式加入 RGB 三原色校验通过，运动标记一致，结束设置恢复、DMA=0 |
| `kernel-packaged-all-apps-ready` | 正式包 7→5→7，每个内核各 8 次四应用切换，全部零丢包/丢帧；两文件双向哈希一致、两次启动零失败服务；最后恢复 One、2160p/跟随输入帧率、清理两文件 |
| `one-packaged-h264-final` / `one-packaged-h265-final` | 最终内核与正式入口 3840×2160，分别 59.97 / 60.06fps，零冻结/丢帧/丢包；实际 Opus 解码 peak=0.1012 / 0.1020 |
| `one-packaged-hid-final` | 最终内核往返后的 One 原生键盘、绝对/相对鼠标、点击与滚轮 |

往返测试中 One 故意设为 1080p30（5.15）和 720p30（7.x）以验证配置互通，
其余三应用保持 4K60；原始 One 设置为 `{height:2160,fps:0}`，最终已恢复。
Pi 完整功能测试 10s 解码 600 帧，生命周期累计丢弃 7 帧，不能写成该轮全程零丢帧。

## 构建、部署与最终清单

七组件开发包为 `2.5.1+vim4.20261018.44.dev.1.g111d83b.dirty`；
PiKVM 为 `2.5.1+vim4.20261018.16.dev.2.g391a6eb`，均在主仓库 `build/packages/`。
all 包的 dirty 来自 Jet 助手测试生成的 Python 缓存，源码已提交，构建明确排除该缓存；
该标记保留，未冒充正式发布版本。Pi 修正包源码清单干净。

`ubuntu-build.py package/verify` 完成 ARM64 构建、源码/包哈希、ELF/动态库、sudoers、
配置保留、损坏包拒绝与更新流程检查；`board.py deploy --exclusive --kernel
7.3.0-rc7-vim4kvm-uhd1+` 实际安装，记录 `deploy-all-packaged`、`deploy-pikvm-ui-packaged`。
主仓库最终 146 测试通过、5 项环境跳过；One 730 通过、2 忽略；Go 两目标与 PiKVM
部署测试、Wave5 平面测试、接收器 13 个回归和风扇策略均通过。

Linux 固定 `ec7d1869b2aafea7e2c4b075f2e10b1f5133b5dc`，Image build ID
`7aa593508a6e987e754de0e343498dbbc8c2edd7`。完整 2334 模块保留 BTF，
模块包 SHA256 `01d58c2f1fc7c68ba7c7757eed79a546919b35b8218506450b466d51495034cf`。
准确配置归档为 `packaging/kernel-edge/uhd1.config`；空目录 olddefconfig 重放后仍为
`610ff17daf5bb40085ca657f40a7436c1ff257c57aabb65367fb2aa3a4709ae9`。
应用版本在 workspace.toml，完整运行时插件/ELF 在 sources.toml 的 integrated_runtime。

板上 `/etc/vim4-kvm/kernels.json` 校验两套启动文件；
`/etc/vim4-kvm/runtime-build.json` 记录最终包、ELF/插件哈希、运行内核、实际 build ID、
数据库 quick_check=ok、零 taint、空闲 DMA=0、测试介质清零和 One 设置。
本机副本为 `logs/dual-kernel/runtime-build.json`。独立实验目录的 deploy.json 保留为历史记录。

One 介质测试写回 SHA256：
`bd8a5183fdafb052402b7f52480145004a781b927f0d376e4fbd922da44f6926`。
仅写专属 EDGEUSB21 FAT 夹具的上传副本，未写用户盘。UAC2 组合可配置不等于录音通过。

## 调试失败与修正

- 首次运行时换 EDID 后 UHD HPD 未升高：core 已运行时补齐 HPD 恢复，并加回归。
- RTK EDID 使 Mac 输出 YUV4448；新增严格 BT.709 limited 识别和租约格式区分。
  内容校验继而发现 native 444 为 Cr/Y/Cb，不能沿用 420 展开后的 Y/Cb/Cr。
  三原色还检出第一次修正的 Cb/Cr 互换；最终 0x255 映射三原色与全部模式复测通过。
- 原厂 FHD EDID 允许 10-bit，Mac 发出 185.625MHz，不在当前接收器支持范围；
  新 SDR8 预设仅清除 VSDB 深色标志并重算校验和，保留时序和音频。
- 首次内核面板请求 400、未重启：前端把 fetch options 当 JSON body，修正后真实往返通过。
- `one-native-board-sdr8` 是测试 Chrome 的局域网权限拒绝，回环 SSH 转发后通过。
- strip 安装使模块字节改变，完整证明拒绝只替换两个文件；随后安装匹配的全部
  2334 模块并重新登记通过，没有关闭 BTF 或绕过哈希校验。
- Jet 全量编译检出未公开的 NativeInterface 状态方法，改为后端持锁暂停，防止并发
  启动/调参抢占采集；VIM4 全量 Go 测试及两目标 vet 通过。
- PiKVM 曾对 taskset 执行 --features，改成实际 ustreamer 并补行为测试。
- PiKVM 挂载 ISO 时暴露已有的前端 `images is not defined`：镜像分组被放进分区
  更新函数，移回镜像选择器并等待 drive/images 都到齐，新增 Node 行为回归。
  重新打包后的 `pikvm-packaged-features-fixed` 通过音频、键鼠、主机读盘/弹出、
  挂盘切换保护、4K MJPEG 和调参/重连，网页无未捕获异常；Janus 调参期间短暂 502 后恢复。
- Jet `reconnectHostDisplay` 实测暴露 DDC 禁用恢复后丢失 PHY 端口选择；重新启用时
  明确选择当前单一端口，保持原始卸载快照。实际 DDC MMIO 回归和原网页恢复均通过，
  记录 `jet-packaged-reconnect-fixed`，不是仅检查 RPC 返回成功。
- 原 board.py/check 与包验证仍写死厂商设备和旧的两应用互斥；改为内核对应设备检查、
  四应用互斥和统一启动器。7.x 原厂 binder/蓝牙/rc.local 失败已按启动项修正，重启后零失败单元。
- 首轮带四应用循环的往返在恢复 One 后过早请求配置，验收脚本收到 502；
  加入就绪等待与基线记录，按任务前 SQLite 备份恢复原输出并按哈希清理本次文件，
  再完整往返通过。没有用覆盖数据库恢复用户数据。
- Jet 首次声音夹具已到时退出；HID 首次是屏保层夹具遮住接收窗口。重建较高层窗口
  并检查前台 PID 后通过，失败日志保留。

## 验收边界

UAC2 实际录音、Windows/RNDIS、Wi-Fi 客户端联网未验收；历史 Wi-Fi 固件崩溃根因
未证明修复。整机睡眠物理操作此前延期。HDR10 旧路径保留，本次在线曲线测试为 SDR，
不冒充重新完成 HDR 全部画质/延迟测量。ATX/外接显示屏未连接，仍显示未配置。

## 起点

- 主仓库 `e7f396da275ec3ad216f5dbf1e748e66e227726e`，Linux `694ea2b5ce0ddf9a816c929a75863e42118b4b36`。
- One-KVM 起点 `a8136d9c53c16e05b152199dd6026c567206fabf`；其余应用当时走厂商采集/编码。
- 5.15 Image、Stock 启动项及恢复环境保留。部署前备份应用、服务、配置与数据库。
- 不清空 eMMC，不覆盖用户镜像或网络凭据，不强制弹出主机正在使用的虚拟介质。

