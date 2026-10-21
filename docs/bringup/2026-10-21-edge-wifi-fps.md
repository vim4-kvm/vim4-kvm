# 2026-10-21：Wi-Fi 固件诊断与 4K MJPEG 50fps

摘要：JPEG 驱动改为 cached 输出并补齐 DMA 所有权同步，质量 80 的 4K 动态网页流
已超过 50fps；完整多轮结果见下文。原生无队列管线约 49fps，不能与应用的单帧预取
管线混算。HCODEC 等待约 18.8ms，本轮未达到 4K MJPEG60。Wi-Fi 已确认一个 P2P
接口创建兼容问题；历史固件崩溃尚未找到根因，新增的转储保存用于保留下次现场。

## 部署版本

- Linux `vim4-kvm-7.3`：`a8cab9050101d224466886591cc221ab951d2906`。
  JPEG 修改前为 `50e811ce861f0acfc64d788b7627cd5b13569e46`。
- One-KVM `vim4`：`c1e7b88d91cf5ff90560cc8a2f832a652da0827b`，ELF SHA-256
  `9520b8005a94a553fd544fc36fa0415e0eb71e1fd0c9c40c2bad34f017cf89c7`。
- 运行 release `7.3.0-rc7-vim4kvm-uhd1+`，Image SHA-256
  `4f997c98c9a33c74cb50272be8a0e9156ddc493282ef1d90cf9be124f2e9e192`，
  build ID `35304001d6fe5954bb550b8eb7ed2b3b839f0dfb`；config SHA-256
  `610ff17daf5bb40085ca657f40a7436c1ff257c57aabb65367fb2aa3a4709ae9`。
- 完整 2334 模块包保留 split BTF，SHA-256
  `71722326d05ea306580254a6adfcd908947eef44daeeba7a5e913a1204a244ea`。
  JPEG 在同一输出目录针对当前 vmlinux 做正常 in-tree 重编译，Image 没有改变；
  最后只替换 JPEG 模块，模块 SHA-256
  `fb5f2487ca14af509bd9dc2e7bbb7e9fd68a12c08afb9fb61f6a5d993b1f91ae`，
  intree=Y、taint=0。没有使用外部模块构建代替匹配的 BTF 基线。
- 当前板 DTB SHA-256 `471fc2881ed6c83726ac1db85277aaeadbb63eb6b608d821f2e0bc177d96a567`，
  包含本板 MAC，不能原样分发给其他板。
- JPEG 插件 `gst-plugin-venc` 的 `a61a49726cfc2a7c242deba1a9be328e5cf40c34`，
  ELF SHA-256 `bc21e64cdaf932d7eb25712bcd9e41bd476ad7858de1bbe9e72a202cab5c730b`；
  固件 SHA-256 `59e242bd63d6372d6462d2a2d6815e7bdea1a2cd12cd29fac093f38e73294e4b`。

只更新私有 7.x 服务，旧版 5.15 的默认启动项、Image、应用、启动器、服务和系统 JPEG
插件按六项保护清单核对。备份在板上
`/var/backups/vim4-onekvm-edge-20261021-wifi-diagnostic-retry`。
`/boot` 只有约 13MiB 空闲，放不下第二个 edge Image；第一次暂存因空间不足失败，
清理自建的未完成暂存后恢复。第二次先核实根分区备份，再替换 edge Image，未动默认 Image。

## 分段定位与缓存优化

HDMI 输入为 3840×2160、约 60Hz，Mac 物理运动标记；HCODEC 保持 666666656Hz。
CPU0–3 capacity=1024，CPU4–7=577，均为 performance governor。
一次测试只运行一种媒体负载。私有 `one-kvm-edge.service` 加 `CPUAffinity=0-3`，
避免 JPEG 读取落到较慢核心，未改变系统其他服务的亲和性。

新工具 `tools/edge-jpeg-profile.py` 使用一帧真实 NV12，不经过 GStreamer、网络和采集。
输入 SHA-256 `9b523ecf4d1ddfeff4b714ff37f59d4b818d17d5e7e89315c5afd5810fc959c2`。
质量 80、120 测量帧、10 预热帧，旧 WC 映射的阶段中位数如下：

| 项 | CPU2 | CPU6 |
|---|---:|---:|
| 等待编码完成 | 18.78ms | 18.78ms |
| 读取压缩输出 | 1.08ms | 2.85ms |
| 带读取/哈希的 wall FPS | 48.80 | 44.60 |
| 跳过输出读取的 wall FPS | 52.86 | 52.82 |

`--no-copy-output` 仅是诊断上限，不生成可用视频。哈希计入 wall FPS，不计入各阶段计时。
这些结果证明读取路径和 CPU 选择有影响，也说明缓存优化本身不足以达到 60fps。

JPEG 驱动改用 noncoherent cached pages 与 `dma_mmap_pages`，输入、CPU-only header
及输出按页隔开。首次 DMA 交出分配器清零的完整输出区；之后仅把上次返回的输出范围
交回设备，完成、停止输入引擎并同步 IRQ 后，再把本次实际输出交给 CPU。
同步范围对齐 cache line，未读取的 ring 尾部保持设备所有权。诊断输入区单独同步，
实际 DMA-buf 输入继续由 attachment/exporter 管理，不增加原始帧 CPU 复制。
错误退出仍先完成安全断电，再释放输入和 DMA；失败隔离策略保持原样。

最终固定帧输出 SHA-256
`82a143750c2a6357badabcde9e3c9537efee5135e6c46dc779d0f25c9f97bef9` 与旧驱动一致；
Pillow 解码为 3840×2160。缓存读取阶段降到约 0.16ms。
诊断工具走系统内存输入，新增输入所有权同步让 command/output ioctl 各约 1.8/1.7ms，
wall FPS 约 43.45；不能把它当作实际 DMA 导入路径的性能回退。

## 运动画面与实际帧率

原生 `vim4-driver-bench.c` 使用 `v4l2src ! vim4jpegenc ! fakesink`，质量 80，
30 预热帧、600 测量帧，不读取/解析有效载荷，不写录像。插件自身读取压缩输出仍计入。

| 管线条件 | 三轮 fps | 进程 CPU（单核 100%） |
|---|---|---|
| 旧 WC，未固定核心 | 47.05 / 47.05 / 44.54 | 7.33–15.29% |
| 旧 WC，CPU0–3 | 46.73 / 46.67 / 46.73 | 7.25–8.01% |
| cached，CPU0–3，最终模块 | 48.76 / 48.76 / 48.90 | 3.19–3.29% |

首次 cached 模块为 48.91 / 48.91 / 49.11fps；上表记录显式 cache-line 对齐后的最终模块。
最终三轮 CMA 回到 505200KiB、taint=0，编码 sink→src 中位约 19.16ms。
原生工具没有 One-KVM 的单帧预取队列，因采集节奏和缓冲回收而低于网页管线。
临时加 leaky queue 的原生试验被工具的「输入丢失」检查拒绝，没有用失败结果计算性能，
该试验修改未保留；不能直接关闭丢帧检查让有意丢弃的管线冒充原生一进一出基准。

网页通过网关 8080，请求 60fps；使用应用既有的单帧 leaky 预取队列，不修改应用源码。
`one-kvm-scaling-check.mjs --exclusive --pause-idle-uu --mjpeg-max-rate --mjpeg-only --mjpeg-frames=600`
逐档读取 600 个实际 JPEG part，并解码抽样图像核对上/中/下三条动态标记一致且持续前进。
UU 仅在空闲时暂停，退出恢复模式、质量、尺寸和 UU，等待 DMA-buf 归零。

| 输出 | 质量 | 最终模块网页第一轮 | 第二轮 | 第三轮 |
|---|---:|---:|---:|---:|
| 1920×1080 | 80 | 60.063fps | 60.017fps | 60.011fps |
| 1280×720 | 50 | 60.060fps | 60.066fps | 60.033fps |
| 3840×2160 | 80 | 51.675fps | 51.693fps | 51.719fps |

这是限定场景、多轮十余秒采样，不是长时间所有内容的最低帧率保证，也不是屏幕实际
呈现帧率或端到端延迟。旧 WC 模块同网页请求的短测约 49.67fps。
要稳定 60fps，整个编码周期必须低于 16.67ms；本轮等待仍约 18.8ms。
未通过降低 4K 输出分辨率、降低质量或超频制造 60fps 结果。
另用固定录制帧对照质量 50/100，各 60 测量帧，等待中位仍为 18.78/18.98ms；
仅降低质量没有消除 60fps 所需的硬件时间差。

Wi-Fi 诊断内核、旧 JPEG 模块的完整浏览器矩阵也通过：H.264/H.265 4K≈60fps，
缩放和返回原生模式正常。最终模块第三轮同时跑完八档 H.264/H.265 往返矩阵，
4K 约 59.76–60.08fps。另一次 12 秒 H.264 音视频采样为 59.97fps、零丢帧/丢包/freeze，
呈现回调 P99 19.6ms、最大 20.9ms，解码音频峰值 0.104。该短测不代替音画漂移验收。
最初两次完整矩阵因切模式时 WebRTC 尚未就绪/视频暂不可读失败；采样前补齐状态等待，
最终完整矩阵通过，失败日志仍保留。未把旧 profile 的 HDR、音画漂移或长测升级为当前证明。

## Wi-Fi：确认的问题与未确认的崩溃

本轮早期旧配置在板端 14:35:46 记录 `Firmware has halted or crashed`，SDIO 自动
移除、重新枚举并重新加载固件。该 Image 未启用 devcoredump/BRCMDBG，没有保留 RAM
dump 和固件 console，因此不能据此确认触发条件，也不能声称已经修复。

安装的是 BCM43752/2 SDIO、AP6275S NVRAM，固件 18.35.387.23.88，构建日期
2021-11-12，FWID `01-16e134aa`。STA/APSTA/P2P 三个文件实际完全相同，
820071 bytes，SHA-256 `af7310c6c44da2690ea9f666eea8477a48e906810a1246a5fa207d3788fdf309`。
换文件名并不等于换了版本；本轮没有安装另一份所谓「新固件」，也没有改校准、地区或 NVRAM。

固件宣称 P2P 能力，但 `apsta=1`、`p2p_disc=1` 返回成功后，没有收到预期的 P2P
IF_ADD，只看到主接口 bss0/STA 事件；1.5 秒后接口创建超时。
临时用 `feature_disable=16` 禁用 P2P 后，该超时消失，STA/AP 能力仍在。
恢复默认参数后超时再现。这个对照未证明它导致上述历史崩溃，所以没有持久化禁用。

普通扫描确认可见 2.4/5GHz 网络。早期连续 8 次成功；诊断内核一组 20 次请求中
前两次成功、后 18 次返回 EBUSY，稍后单次重试正常，不能记成 20 次扫描通过。
最后按每次扫描后间隔 2 秒重测 8 次，全部成功、覆盖双频，未出现新的固件崩溃。
随机 MAC 扫描返回 EOPNOTSUPP，不是通过。无客户端 SSID/凭据，未测关联、DHCP、
吞吐、热点连接或漫游；以太网默认路由保持原状。

## 下次崩溃证据与验证入口

新配置启用 `CONFIG_ALLOW_DEV_COREDUMP`、`CONFIG_DEV_COREDUMP`、`CONFIG_BRCMDBG`。
默认 debug=0、console_interval=0，不持续记录附近 SSID 或原始扫描内容。
debugfs 可按需读 console/forensics，设备恢复后 phy 编号会变化。

配套保存器和 udev 规则已安装，镜像集成时需执行同样两步并 reload：

```sh
install -m 0755 packaging/kernel-edge/save-wifi-coredump.py /usr/libexec/vim4-edge-save-wifi-coredump
install -m 0644 packaging/kernel-edge/90-vim4-edge-wifi-coredump.rules /etc/udev/rules.d/
udevadm control --reload
```

只处理 7.x/brcmfmac 转储；SDIO 自动恢复导致 failing_device 已消失时，按本板专用
`mmc2:0001:1` symlink 识别。每份限 16MiB，私有目录 0700、文件 0600，保存二进制、
哈希和 release，fsync 文件与目录后才释放内核副本，最多保留两份成功记录。
保存失败或超限不确认释放。未主动触发固件崩溃，尚无真实 crash 的端到端收集验收。
五项离线测试覆盖保留、驱动/内核过滤、失败不释放、超限及设备消失竞态。

本地原始证据在不入库的 `logs/kernel-edge/`：

- `jpeg-phase-profile.log`、`jpeg-cpu-affinity-profile.log`：旧映射分段与核心对照。
- `fps-native-repeats.log`、`jpeg-pinned-repeats.log`、`jpeg-cached-native-results.jsonl`：原生三轮。
- `jpeg-cache-final-install.log`：最终模块、intree/taint 和固定帧哈希。
- `jpeg-cache-final-native-results.jsonl`、`jpeg-cache-final-native.log`：最终原生三轮及质量对照。
- `jpeg-cache-final-browser-1.jsonl`、`jpeg-cache-final-browser-2.jsonl`：最终模块逐档 600 帧。
- `jpeg-cache-final-browser-3.jsonl`：第三轮及最终完整 H.264/H.265/MJPEG 矩阵。
- `jpeg-cache-final-audio.jsonl`：最终 H.264 与非静音 WebRTC 音频短测。
- `jpeg-cache-module-cohort.log`：完整包 2334 个模块逐一与板上 SHA 比对通过。
- `wifi-final-browser.jsonl`：诊断内核、旧 JPEG 的完整媒体矩阵。
- `wifi-debug-events.log`、`wifi-debug-filioctl.log`：P2P 事件/固件命令，含私有扫描数据，勿公开。
- `wifi-post-debug-scans.jsonl`：包含 EBUSY 的 20 次扫描请求，未过滤失败。
- `wifi-spaced-final-scans-fixed.jsonl`：间隔扫描 8 次成功；networks 字段按 BSS 文本出现
  次数统计，可能包含其他 BSS 字段，不能作为去重 AP 数量。
- `wifi-diagnostic-uart.log`：本轮诊断 Image 的启动记录。

JPEG 离线 ASan/UBSan 检查全部 100 档质量、命令/地址边界、首次与每帧缓存交接、
变化长度及导入/内存输入；import 回归检查 producer fence、错误清理与 1000 轮生命周期。
构建和 checkpatch 通过；主仓库 135 项离线测试，130 通过、5 项因依赖缺失跳过。
该记录不代替真实休眠恢复、HDR 长测或 5.15 同条件性能对照。
