# 2026-10-31：原生 HDR 第二阶段离线接入候选

P0-5 延续 [r13 已验主路径](2026-10-31-hdr10-native-final.md)，本记录只登记新增的
离线实现，**不是完整替换 5.15 的验收结论**。主仓独立 worktree 为 `vim4-kvm-p0-5`，
六个子仓也各有独立 worktree，分支均为 `p0-5-native-hdr`。未修改内核或其他会话工作树。
四项审查缺陷已修复并离线验证，见修复记录。
下文旧归档仅保留历史证据；窗口补审修复后，后续候选须改用r14c。

## 来源与共享接口

完整提交和用户态文件 SHA 见[候选清单](../../packaging/hdr10/phase2-sources.json)。
正式 workspace/tested_build 锁未更新；这些提交需要在两种 GPU 栈实测后才能推广。

| 仓库 | 提交前缀 | 改动 |
|---|---|---|
| gst-plugin-venc | 3a74cc9 | 公共 Wave5/Main10/SEI，追加metadata丢AU后的IRAP恢复 |
| gst-plugin-vfmcap | b2df852 | Vulkan P010→SDR NV12 分支、height-only 按比例缩放 |
| One-KVM | 50f0b4d4 | 原生 P010 同源截图阀门，按请求 GPU tone map 后沿用 SDR JPEG 转换 |
| NanoKVM | 0525dea | 探测公共源能力，截图请求借用同一 raw pad，取消/重开不另开 VDIN |
| JetKVM | 166719c | 删除应用层对 Wave5 的提前排除，依据公共源探测 |
| uStreamer / PiKVM | 97eb951 | 共用能力探测/VDIN所有者，追加共享SDR策略快照与退避修复 |

供采集 broker 对接的合同：公共 `vim4h265src` 的 `raw` request pad 在 READY 前申请，
原生时输出 P010/PQ/BT.2020 limited，映射时为 NV12/BT.709。VideoMeta 的真实 stride、
UV offset、可见尺寸与缓冲租约必须完整保留。JPEG 前接 `vim4pq2sdr`；截图阀门放在
有界队列之前，空闲时关闭，不为截图重开 VDIN。切换先完整停旧 bin，再重开；
仍沿用模式变化 bus error，不在活动队列中 S_FMT。

能力来自 AMLY 枚举、HDR10 compound controls、无缓冲的 HEVC/Main10/P010/colorimetry
协商与实际插件 caps，不按内核 release 放行。公共源每个 AU 读新鲜 HDMI metadata；
在 IRAP 或 metadata 变化时插入 137/144，替换同类旧消息、保留其他 SEI；过期时丢弃原生 AU。
软件非零夹具不能作为真实 HDMI 非零 metadata 的证据。

SDR 分支使用相同 Vulkan DMA 导入/完成合同和两个独立 NV12 缓冲，不修改原生编码器的
P010。读取全局白点/峰值；保持 sRGB 中间调并压缩高光。没有 CPU 色调映射或上传后备；
JPEG 阶段保留既有 SDR 裁剪、缩放和压缩。持续 JPEG 对 GPU 带宽及主流帧率的影响仍待测。

## 离线验证

| 门禁 | 结果 |
|---|---|
| 采集插件 | 7 项 Meson 通过，包含启动回滚、比例/上限、SDR 协商与曲线偏好 |
| 编码插件 | DMA 生命周期、8 项公共源合同、实际 Main10 控制选择、3 项 HDR10 测试通过 |
| 色调映射 | 实际 SPIR-V 在 llvmpipe 下与独立 double 参考对照；6 组含 padding/UV offset，最大差 1 个八位码值 |
| NanoKVM / JetKVM | VIM4 Go 全套测试及程序构建通过；Nano 含同源截图三次开阀、取消与视频继续推进测试 |
| One-KVM | Rust 822 通过、4 忽略，release 构建完成 |
| PiKVM 后端 | uStreamer/Janus 构建及 RTP 包回归完成；未运行声音测试 |
| 主仓 | 首批365项；追加后381项、14跳过，其余通过；最终日志 root-phase2-final-tests.log |
| 四入口接收器 | 本机 Chrome 实际 RTP 收流/解码，含 One-KVM HTTP offer/close；160×96 VP8 约30fps、零 dropped，错误编码/PQ/停帧拒绝；不是三应用 ARM 后端或板上 HEVC 证明 |
| 窗口/分析回归 | 16项通过：真实 OCR、收证失败仍恢复、转发替换、精确配置恢复、监控失联拒绝、模块清单/哈希、SEI非零夹具/转义/重复/截断、SPS字段缺失/冲突 |
| 独立码流解析器 | VM FFmpeg 重新解析保留 r13 前缀，Main10/10-bit/PQ/BT.2020 limited 与 SEI137/144→HDMI逐字节一致；源仍全零，不计新增实板或非零源验收 |

原始日志与用户态封存档在本 worktree 的 `build/p0-5/`；`manifest.json` 明确
`hardware_validated=false`，不含 Image/DTB/模块，**不能直接作为 RAM 启动候选**。
私有标准 V4L2 插件复用 r13 的 b9269d05…，没有重编已通过组件或完整内核。
恢复会话时核对无本任务遗留票据/VM构建；验证容器已停止，保留归档与构建缓存。

## 无人值守窗口与离线干跑

`phase2-window.py` 已串起 M6 空闲截图、逐屏 HDR 开关/恢复、两 GPU 链式启动、28段真实接收、
One-KVM 原生期间 SDR 截图、应用原生/缩放/映射/恢复、官方 UU CLI 与新鲜 Receiver Report、
CMA 回收、首个 WARN/fault 停负载、collect、单次 return-baseline、精确视频配置恢复。
每次 RAM 启动及回5.15均重建自己的 SSH 转发，避免旧 SSH 进程仍存活但通道已断。
恢复步骤独立执行，收证失败不跳过回基线或 M6 恢复；HDR 动作失败不自动重放。
截图 OCR 使用 r13 的真实截图夹具，General→Displays、HDR 行移动、Chrome 拒绝及恢复均有测试。
只允许截图确认的 M6 布置操作，不操作 M4。稳定性默认180秒，整个采样期阻止 heavy。
结束后释放板票，再用 heavy 票据运行独立 FFmpeg SPS/VUI 和 SEI/HDMI 字节比对。

内核组装输入是归档路径和来源 SHA，不重编内核、不混 BTF；完整静态 ARM64 PID1 编译与归档复验
已用正式 uhd5 包实际干跑，两包各2341模块，包含大小写不同的 xt_DSCP/xt_dscp。静态 PID1 的
names/targets 由当次 runtime inventory 生成，复用其 GPU/板级启动器，应用/私有插件只做候选 bind。

| 制品 | SHA256 |
|---|---|
| 用户态 r14a | `08286d72f264da183a3b5581545e1c2aa390b124d8e9c009e8100f6b89e52175` |
| 输入 uhd5-final-r12.tar.gz | `174cf528c8e12a4fa71c5adbf42c95bc39ba987e4ba6133db7b5912e2da85b0b` |
| Panfrost 干跑 RAM | `ace1a43ac3bd7ad5fabe54e9988a402ba71258632e3e33890051467a252d6720` |
| kbase 干跑 RAM | `c172dfc315838500bb1da0eae7ee11aeb20d011d7412db2af642c200ed075ca1` |

这两份 RAM manifest 均为 `dry_run=true, hardware_validated=false`，窗口命令拒绝上板。
归档及其 JSON 证明在 `build/p0-5/ram-dry/`；实际记录为 `assembly-dryrun2.log`、`phase2-plan.json`、
`receiver-local-r3.log`、`phase2-window-tests.log`。接收器本机自测使用 heavy 排队，不干扰他人采样。
测试不调用 M6 MCP 或板上 SSH；构建 VM 仅访问本任务目录，没有遍历 Mac 共享目录。

uhd6 发布后，先在 Linux ARM64/独立构建目录组装，每种 GPU 一份（dry-run 时才加该参数）。
以下命令在协调主机 `tools/board-queue run --heavy` 已管理的 ARM64 构建进程内运行，不能在VM另取独立锁：

```sh
python3 packaging/hdr10/assemble-phase2.py --kernel "$KERNEL_ARCHIVE" --kernel-sha256 "$KERNEL_SHA" \
  --userspace "$USERSPACE_ARCHIVE" --userspace-sha256 "$USERSPACE_SHA" --baseline "$BASELINE_IDENTITY" \
  --gpu panfrost --payload-id phase2-panfrost-r14 --output "$PAN_ARCHIVE"
```

另一份改为 `--gpu kbase`、唯一 payload-id 与输出名。baseline identity 须含已验证 root PARTUUID；
baseline-files JSON 列表沿用 board-window 的保护文件合同，不把候选 bind 程序放进去。
Swift observer 已编在 `build/p0-5/screen-observe`；可重建 `swiftc packaging/hdr10/screen-observe.swift -o <输出>`。
认证沿用管理器环境变量（不打印），所有准备完成后，只执行这一条无人值守命令：

```sh
python3 packaging/hdr10/phase2-window.py \
  --panfrost "$PAN_ARCHIVE" --panfrost-sha256 "$PAN_SHA" \
  --kbase "$KBASE_ARCHIVE" --kbase-sha256 "$KBASE_SHA" \
  --observer build/p0-5/screen-observe --baseline-files build/p0-5/baseline-files.json \
  --ffmpeg packaging/hdr10/ffmpeg-vm.py --window hdr10-phase2-r14
```

加 `--plan-only` 可复现本次 uhd5 离线校验，不取板票。实际执行会 fetch main 并严格核对 uhd6
release/build ID/内核归档哈希/Image 哈希，预检管理器认证、UU 空闲与唯一目标，不接管已有 UU 会话。
正常预算：布置/恢复约2分钟、两次候选启动/传输及回基线约4分钟、接收与180秒稳定性约7分钟、
应用切换/UU及状态检查约2分钟，合计目标15分钟；硬上限30分钟。
D1预算修复后，工作最迟18分45秒截止，并按实际恢复顺序保留完整预算。

官方 CLI 没有 HDR 设置参数，脚本尊重官方客户端能力和 enable_hdr 请求；若未请求原生，PQ 门禁失败。
新鲜 RR 加共享 Main10/PQ 码流只能证明官方端收到 RTP，**不能冒充官方客户端解码或持续 HDR 显示**。
该项仍需客户端可观测证据才能完成 P0-5；不会通过管理接口强开来绕过客户端协商。

## 上板结果与余项

| 本轮门禁 | 状态 |
|---|---|
| 官方 UU 客户端原生 HDR | 未验；已确认官方 uuyc-cli 可自动连接，不能以协议模拟器替代 |
| 三应用原生 HDR、切换、缩放 | 未验，未全局部署或开放正式能力 |
| 原生期间 SDR 截图 | 实现/离线合同通过，GPU 实际画面未验 |
| 非零静态 metadata | 未取得真实源；逐字节透传未验 |
| HLG / 动态 metadata | 无真实源，未验 |
| kbase / Panfrost + 稳定性/CMA/taint/WARNING | 本候选未上板；不能沿用 r13 或 llvmpipe 结果计通过 |

最新 main 在核对时为 16f3280，已同步其工具更新；tested_build 仍为 uhd5，尚未登记可复用的统一 uhd6。
同步 main 后的全量回归单独保存在 `root-phase2-main-tests.log`。
未取板票等待它，也未使用不匹配模块/BTF。下一步取 P0-1 固定 uhd6 归档/哈希，复用已封存用户态
生成正式候选，再执行上述命令；板上失败收证据并释放，离线修复后重排，不持板编译。

无需用户操作或新授权；当前仍是未完成的 P0-5 候选阶段，不请求放宽实板门禁。
