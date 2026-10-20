# 2026-10-20：7.x Wave5 逐行刷新与卡顿对照

实验 One-KVM 已将 H.264/H.265 改为 GOP 0、逐行刷新，保留新观看者和恢复时的完整
关键帧。固定 4K60、30Mbps 运动负载下，H.264 周期关键帧从 120 个/120 秒降到 0，
超过 50ms 的呈现间隔减少；仍有零星短顿，未宣称完全流畅或已达到 5.15 全场景性能。

## 实现与版本

Linux `4f00b3cca175ac5e97bf43f442e1fb08c3cae6ca` 为 Wave5 加入标准 V4L2
`INTRA_REFRESH_PERIOD` 和 cyclic 类型控制。固件参数按实际高度向上取整为每帧
刷新行数，保证在请求周期内覆盖全帧；只启用当前 codec 的刷新字段，0 关闭。
One-KVM `414e88b98b50f8e16c296c58100334ea52e72d18` 使用周期 45，UHD 对应 AVC
每帧 3 行 MB、HEVC 每帧 1 行 CTU，编码启动前查询驱动能力，拒绝缺少控制的旧模块。

当前部署保留音频已验证的 `375bfd949dd5f` Image 和其他模块，仅覆盖 Wave5。
该覆盖只改变 Wave5 内部结构和代码，内核公共头文件与配置保持相同。
模块使用普通版本/符号加载检查，未使用 force；关闭依赖另一 vmlinux 的 split BTF，
不将新 Image 的 BTF 模块混装到旧 Image。板上模块为 intree，加载后 taint=0。

在完成同配置的 4f00b3c 构建后，模块单独生成：

```sh
make O=/home/deepdream/build/kernel-edge-uhd1-test \
  CONFIG_DEBUG_INFO_BTF_MODULES= -j8 drivers/media/platform/chips-media/wave5/wave5.ko
```

若该目标已有带 BTF 的旧产物，先移走该目标再构建，确认新 ELF 无 `.BTF`，再
`strip --strip-debug`、XZ 打包。主配置 SHA256 为
`39f2c5c008bba1032913abafdde2a992d9cd2ecf2b4c6f4fc9b27330d0ba9d2c`。
对应源码与模块摘要记在 [实验源码锁](../../packaging/kernel-edge/sources.toml)。
覆盖前停止实验应用，确认 Wave5 引用为 0、DMA-buf 为 0，再卸载；备份旧模块、
应用和清单，加载新模块后查询控制并核对 taint，最后启动应用。

| 部件 | SHA256 |
|---|---|
| 保留 Image | `1e789cb30023745ec11af89389eef0177b55087a61c765b4ec364759e040772c` |
| Wave5 模块归档 | `210dc9c14772c1bd1c56d36a959e637e39f4c4e7ba569bc51b72d924d4de401a` |
| One-KVM | `b7da44e63065bfdaafc420a3b4085efd09a5bae3d6af58bf9781cfbb5fc62243` |

## 同条件 A/B/A/B

Mac 原生 3840×2160 栅格、物理 HDMI 桌面 `latency-source.swift --motion`，单观看者，
Chrome 155.0.8059.85 headless；固定尺寸、30Mbps、60fps，音频始终开启但信源静音。
每轮预热 15 秒。A2 与 B 使用相同编码器模块，仅切换应用的 GOP/刷新策略；
A1 期间构建器尚在编译，因此另做不含编译负载的 A2 复核。

| 顺序 | 测量秒数 | 解码 fps | 新关键帧 | 呈现 P99/max ms | >50ms 次数 |
|---|---:|---:|---:|---:|---:|
| A1 周期 GOP60 | 120 | 59.996 | 120 | 55.6/75.4 | 111 |
| B1 逐行刷新 | 120 | 59.999 | 0 | 48.7/63.1 | 36 |
| A2 恢复 GOP60 | 120 | 59.999 | 120 | 53.1/72.2 | 91 |
| B2 再次逐行刷新 | 60 | 60.031 | 0 | 45.5/59.0 | 12 |

四轮零新增 packetsLost、framesDropped、freeze、PLI。回调漏采 A1/B1/A2/B2 分别为
791/1139/994/380，不能把它们当作视频丢帧；呈现回调间隔也不是光学显示测量。
视频使用独立于音频的同步组，实际视频缓冲均值仍约 2.8ms，未通过增加播放缓冲隐藏停顿。
只消除了周期完整关键帧，不表示所有剩余间隔都由同一原因造成。

## 验证边界与启动问题

新整包 Image `4f00b3c` 两次启动遇到 HDMI PHY 等待输入超时，Mac 随后退回兜底显示器；
回到 5.15 可恢复 RTK 连接，回到 375bfd9 则恢复实验 UHD60 和音频。
接收器模块 `.text` 在两次构建中摘要相同，目前未确定整包启动失败的原因，
不将其归因于 Wave5 改动，也不将该整包作为已验证默认。保留串口、Mac 显示日志与
失败构建；当前使用已验证 Image 加独立编码器覆盖，5.15 默认及生产文件未改动。

离线 ASan/UBSan 覆盖刷新控制、codec 切换、部分底行、关闭刷新与行预算；
原 DMA/关闭/profile 回归、719 项 Rust 测试和 ARM64 release 通过。
本地 buffer benchmark 的 `--kernel-source` 现在也运行 profile 和刷新检查。

H.265 预热 15 秒、采样 60 秒为 59.997fps、零新增关键帧/丢包/丢帧/freeze，
呈现 P99/max 为 46.4/58.9ms，2 次超过 50ms，回调漏采 213。没有旧 H.265 的
同条件对照，不用这轮证明它相对原版的收益。
独占采集另以 GOP0/刷新45，在第 60、120 帧后分别请求完整关键帧，两种编码
均实际输出于第 62、122 帧。各 180 帧原生 3840×2160 视频全部离线解码，
三高度运动帧号一致、连续推进且颜色检查通过；测试默认 AVC 为 Constrained Baseline、
HEVC 为 Main。这是功能验证，不把 Python 测试管线的 pad 耗时当作原生驱动基准。

最终以保留 Image 加新 Wave5 模块重启一次：实验应用、LAN 网关、USB 服务自动
启动，HID online、模块摘要吻合、taint=0；Mac 保持 3840×2160 原生栅格。
网页再次解码 4K 约 60fps，10 秒无新增丢帧/丢包/freeze，实际 WebRTC 音频峰值
0.10126。主仓库 116 项离线测试通过，5 项因环境跳过。

原始采样在忽略的 `logs/kernel-edge/edge-cadence-{matched-a,refresh-b,periodic-a2,refresh-b2}.*`。
