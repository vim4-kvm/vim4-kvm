# 2026-10-27：四套 KVM 共用 HDR GPU 缩放

接续[UU HDR 缩放](2026-10-27-uu-hdr-scale.md)。NanoKVM、JetKVM、PiKVM 已使用
公共 `vim4h265src`，此次将其 HDR 分支的 CPU `videoscale` 移除，把请求高度交给
`vfmcapsrc height`。由 Mali 同时完成 AMLY 解包、双线性缩放与 P010 转换，
连续 DMA 直接送 Main10 编码；与 One-KVM/UU 使用相同采集实现。
保持 PQ/BT.2020；SDR 分支、全局开关和编码器退休顺序不变。

## 接口与验证边界

源插件按比例生成偶数宽，禁止放大，0 为原尺寸，非零高度向下取偶数且至少2。
缩放要求 Mali/DMA，缺失时明确失败；原尺寸的既有回退保持不变。
NanoKVM 的现有选择器支持720p、1080p、2160p；JetKVM、PiKVM 当前不传输出高度，
仍跟随输入尺寸。本次统一底层缩放能力，没有新增这两套应用的尺寸选择器。

ARM64 严格编译通过。Main10 DMA 输入生命周期套件通过；公共源6项通过，
其中真实采集插件与真实编码器类在 NULL 状态完整解析 HDR 管线，覆盖0、1、1701、2160请求。
平台构建显式加载同批采集插件执行该项，避免只测拼接字符串或因缺插件跳过。
采集包新增 `vim4-hdr-scale-api-1`；编码包和 One-KVM 包依赖它，防止混装旧采集插件。
平台打包、隔离安装校验及板端部署通过。

## 实际 HDMI 公共源

内核 `5.15.137-vim4kvm-hdrdual6`，3840×2160p60 PQ 输入。公共源18Mbps/60fps，
同时运行全尺寸硬件 JPEG 分支；每档预热60帧、测300帧，之后销毁重开。

| 请求高度 | 实际尺寸 | 编码吞吐 fps | 编码均值 ms |
|---|---|---|---|
| 1700 | 3022×1700 | 59.997 | 8.546 |
| 1440 | 2560×1440 | 59.997 | 6.075 |
| 1080 | 1920×1080 | 60.001 | 3.682 |
| 900 | 1600×900 | 59.996 | 2.784 |
| 720 | 1280×720 | 59.996 | 1.985 |
| 0 | 3840×2160 | 60.004 | 12.872 |
| 1700 重开 | 3022×1700 | 60.005 | 8.543 |

每档编码器均累计360个 DMA 输入、0个 CPU 输入，pending峰值1、结束0。
日志保留 SDK 的同步参数警告和系统无关插件扫描警告；没有因警告放宽帧率或忽略失败。
这些结果仅证明当前输入下的吞吐，不代表运动画质、屏幕光度或端到端延迟。

## Chrome 网页

同一4K60 PQ桌面输入；每组建立新会话，预热6秒后统计约10秒实际显示帧数。
WebRTC 同时核对 RTP 解码统计；Direct 核对原生视频轨道。浏览器帧均报告 PQ/BT.2020。

| 应用 | 模式 | 输出高度 | 实际显示 fps |
|---|---|---|---|
| NanoKVM | WebRTC | 720 / 1080 / 2160 | 60.02 / 60.03 / 59.93 |
| NanoKVM | Direct | 720 / 1080 / 2160 | 60.06 / 60.06 / 59.98 |
| JetKVM | WebRTC | 2160 | 59.95 |
| PiKVM | Janus WebRTC | 2160 | 59.95 |
| PiKVM | Direct | 2160 | 58.87 |

以上 WebRTC 解码丢帧均为0。Direct 不提供 RTP 解码统计，不能将其缺失值当作0；
PiKVM Direct 本轮显示略低于60，不把公共源吞吐当作其网页满帧证明。
这些是当前桌面负载下的短测；Safari HDR、任意输入时序和长时间运动负载未验收。

NanoKVM WebRTC/Direct（720p）、JetKVM WebRTC、PiKVM Janus/Direct（4K）各执行
保留 HDR→映射 SDR→保留 HDR：五组均通过，PQ/BT.2020与BT.709正确跟随；
WebRTC 每阶段均只有一个已连接的视频 Peer，Direct 在原生 HDR 视频和 SDR canvas 间恢复。
每阶段约4秒显示/解码吞吐59.93–60.67fps，不把短窗口高于60的计数视为额外源帧。
NanoKVM HDR期间四次独立 SDR JPEG 快照均通过，约164KiB。
PiKVM Direct 往返时解码约60fps；不替代上表原生视频显示帧数统计。

配套组件安装后额外回归 One-KVM：原生4K与3022×1700分别15秒解码901帧，
均60.04fps、0解码丢帧，实际PQ/BT.2020，协商 `profile-id=2`。
完整主仓库离线测试282项通过、7项跳过。

测完恢复原 One-KVM 选择，七份应用/全局配置 SHA256 与备份完全一致。
HDMI 服务 PID 仍1081，源端保持PQ；未改内核、EDID或 Mac 的 HDR 偏好。

## 部署

匹配平台包 `2.5.1+vim4.20261027.1`，仅更新板级、采集、编码三个包。
构建源：主仓库 `0746810`、编码 `7e64fe5`、采集 `d0bf013`；应用二进制未更改。
早期 dev 版本因低于板上已安装正式版本被部署器拒绝，未强制降级；随后使用上述候选版本。
备份在板端 `/var/backups/vim4-all-hdr-scale-20261027/`，含原插件、SDK和配置归档。

部署 SHA256：

```text
libgstvim4hevc10.so b9be1fd3d609a7fc7dec6b9acc7279b74624840b0ba86b2faf254973919b73b6
libgstvfmcap.so ce204fd7c9c2b0ea77c8fb818c031ae540b650c78044cbaddd522f99a148836b
libvpcodec.so 0f6d25c4bcb51d83b3f364a041ccb70e24b8c1894337570f84d3a2bfc1fd3ee2
libamvenc_api.so e72b61c3c955194250c905ae90ba03fca155009f93ea18baa5c47347e4e642b9
```

原始记录与复测程序在忽略目录 `build/all-kvm-hdr-scale/`：
`shared-scale-probe.c`、`shared-hardware-scale.log`、`app-probe.mjs`、`switch-probe.mjs`、
各应用 JSON、`browser-{apps,switch,one}.log`、配置前后哈希及 `platform-release-*.log`。
