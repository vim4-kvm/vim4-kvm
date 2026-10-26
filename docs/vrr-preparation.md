# VRR 输入与本地输出：离线准备

2026-10-26，目标同时覆盖无 HDMI OUT 的远程 KVM 和 HDMI OUT 跟随输入 VRR。
目前没有可供测试的 VRR 显示器，OUT 未连接。本轮只改源码、运行离线回归和构建，
未加载新模块、修改板上 EDID、停启应用或重启。两种功能均未完成真实 VRR 验收。
后续部署候选复用已有 `RTK-1080P120` 实验表，加入HDMI Forum 48–60Hz声明并移除
原AMD 40–61Hz声明，不增加预设项。原始RTK表与当前保存选择不变；
下文的原范围描述与哈希为首次离线准备时的记录，当前候选与备份见
[部署准备](bringup/2026-10-26-vrr-input.md)。

## 已实现的基础修复

- RX Gaming VTEM 的 Base_Refresh_Rate 原来把低字节左移8位，与 QMS 分支的
  10-bit 字段布局不一致；现在两种 VTEM 使用同一个解码函数。
- `info` 保留原 `Frame Rate`（实测 centi-Hz），新增 `VRR enabled`、
  `FreeSync enabled`、`FreeSync active`、`Base Frame Rate`、`Capture Frame Rate`。
  固定输入的 capture rate 等于实测值；VRR 使用基准时序，避免周期变化被当成模式变化。
  FreeSync 支持位单独置位不算开启，enabled 与 active 分开报告。
- VRR 基准来自有效 VTEM，或已识别的 AVI VIC：1080p100/120、720p50/60、
  1080p50/60 和16:9 4K50/60。没有可识别基准时 capture rate 为0；没有从变化中的
  实测帧率猜上限。FVA、非 CTA 自定义 VRR 时序不在本轮支持范围。
- RX 格式分类、公共 VDIN1 插件、NanoKVM、JetKVM、One-KVM 和 PiKVM
  都使用 capture rate 配置采集/编码预算；旧驱动仍回退到原字段。
  One-KVM 输入状态继续显示实测刷新率，几何尺寸或真正的固定帧率变化仍会重建。
- TX 注册使用传入设备的 vinfo，修正 min/max 对调、无能力时除零和整数提前截断。
  最大垂直行数根据当前基准时序计算，不能用显示器最高刷新率代替当前模式；
  超过硬件16位行数范围不得启用。**原来的启用门槛仍保留**，没有借修复自动开启本地 VRR。
- T7 延迟寄存器读地址不再重复加 ENC offset；crop 不变时修改 line_dly 也会更新，
  增加延迟立即写，减小延迟保留 VSYNC 写入。

VDIN1 的完整帧交付、RDMA 和缓冲地址策略没有改变，没有引入 one-buffer。
上述代码属于5.15厂商链路；没有实现7.3 DRM VRR。

## EDID 策略与离线工具

`board/vim4vrr.py` 与 `tools/vrr-edid.py` 不访问板子，不安装预设，也不脉冲 HPD。
调用者必须显式提供候选接收范围和请求范围；工具不能把参数当成已验证硬件能力。

- 远程模式取接收范围与请求范围的交集，不依赖 HDMI OUT。
- 本地模式还必须提供 OUT 原始 EDID，并取同协议的显示器范围交集。
  当前 TX 只具备 HDMI Forum VTEM 路径，工具拒绝将 AMD FreeSync 当成本地 Forum 支持。
- 原 RTK EDID 只有 AMD FreeSync 40–61Hz，没有 HDMI Forum VRR 范围。
  1080p120 固定刷新率派生表也没有扩展该 FreeSync 范围。
- 只修改 VRR 声明，保留基表、SVD 顺序、音频、HDR 和详细时序；移除或清除另一协议的
  VRR 声明，避免源按旧的更宽范围协商。CTA 空间不足、错误校验和或畸形块直接报错。
  固定模式保留不代表这些模式的 VRR 组合均已通过，基表的模式/颜色资格需另行确认。
- 不覆盖已有输出文件。远程模式不接受 `--sink`；本地模式缺少 `--sink` 直接失败，
  不能在无显示器时生成声称已匹配本地显示器的候选。

例如，生成 **48–60Hz 实验候选**，不应用到板子：

```sh
python3 tools/vrr-edid.py board/edid/1080p60-sdr8.bin \
  --mode remote --protocol hdmi-forum --receiver 48 60 --request 48 60 \
  --output /tmp/vim4-vrr-48-60.bin
```

该示例基表仍声明其他固定模式；首次硬件实验应主动选择1080p60 SDR 8-bit，
不能只凭文件校验正确宣称 VRR、HDR 或所有时序已支持。
本地生成改用 `--mode local --sink /path/to/monitor-edid.bin`，其余范围仍显式指定。

## 离线验证与候选

构建产物与日志在忽略目录 `build/vrr/`。候选基于已部署1080p120修复继续增加本轮修改，
匹配主 Image SHA256 `6123de38fa741667b1f6c906d5a06ae7a4aa7ba4a16d7fc29e13ca406afaa780`。
模块 build ID `6e6eb9fe356d1aee355c83b4c145fc67436e0da7`，strip 后 SHA256
`7d0599faec01f5858d542d75dc86909bc7e98c03da146325596f73e99d8ca38d`。
构建后 VM 源码和模块输出均恢复原始基线，候选单独保存在 `build/vrr/aml_media.ko`。
One-KVM release 候选 `build/vrr/one-kvm` SHA256 为
`adbea7281e4633478f72e9f375189ba0e6a7dbb118cbd3c26d8784265958f6d0`。

已通过：主仓271项测试（7项跳过）、驱动4项实际C函数回归、采集插件全部2组Meson测试、
NanoKVM与JetKVM完整VIM4 Go测试、One-KVM完整Rust测试（776通过、2项忽略）及release构建、
uStreamer的VIM4核心构建（WITH_JANUS=0）与实际C解析函数回归。
One-KVM release 构建有21条编译警告；全仓 `cargo fmt --check` 在未修改文件上仍有格式差异，
没有为本轮任务批量格式化无关代码。Janus模块及前端未改，本轮未重建它们。

复现入口（各仓库命令分别在对应目录执行）：

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 common_drivers/drivers/media/vin/tvin/hdmirx/test_high_refresh.py
python3 common_drivers/drivers/media/vrr/test_vrr_bounds.py
# Linux ARM64 构建环境
meson test -C gst-plugin-vfmcap/build --print-errorlogs
# NanoKVM/server
go test -tags vim4 ./...
# kvm
go test -tags vim4 ./internal/native
# One-KVM
cargo test --locked --features vim4 --lib
# ustreamer
python3 tests/test_vim4_rate.py
```

驱动测试编译实际 C 函数，覆盖变动的48–120Hz帧周期、FreeSync enabled/active、
VTEM10位字段、空/反向范围、非整数频率、当前ENC选择、常量crop时延迟双向更新。
EDID测试覆盖同协议交集、不相交、原RTK协议区别、10位最大值、保留能力/DTD、
CTA越界与空间耗尽，以及CLI无显示器拒绝本地模式。
GStreamer 1.24.2 的离线 appsrc→videorate(drop-only)→appsink 实验中，
120fps预算、8.33–25ms不等间隔的7个输入帧全部保留原 PTS；没有据此删除 videorate。
软件实验不验证 HDMI DMA、编码器或浏览器的真实 VRR 行为。

## 尚未完成的链路

1. 远程：真实 HDMI VRR 源的 VTEM/SPD、RX锁定、变化的 Vtotal、VDIN1完整帧和时间戳；
   同时验证四套应用不反复重建、H.264/H.265内容更新及浏览器/UU播放。
2. 本地：由现有 passthrough 控制器独占策略；模式设置后刷新当前ENC注册；
   明确启停 ENCP VRR 与 TX GAME EMP，验证 OFF 包实际发出且不遗留，防止两个逻辑争写行数。
   本轮修正注册计算不等于这些控制已实现，也没有新增网页 VRR 开关。
3. 本地实测需 HDMI Forum VRR 源与显示器：范围上下界、非整数基准、输入失锁、
   OUT拔插/换屏、关闭/重开、HDR和分辨率变化，以及同步KVM时完整帧与音画关系。

保留原 EDID 和关闭的本地 VRR。没有显示器时不能验收输出跟随、关闭包、
撕裂、失锁或延迟收益；离线构建通过不能替代这些结果。
完整资格与缓冲约束见[本地VRR审查](vrr-passthrough-audit.md)。
