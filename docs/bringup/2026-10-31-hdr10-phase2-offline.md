# 2026-10-31：原生 HDR 第二阶段离线接入候选

P0-5 延续 [r13 已验主路径](2026-10-31-hdr10-native-final.md)，本记录只登记新增的
离线实现，**不是完整替换 5.15 的验收结论**。主仓独立 worktree 为 `vim4-kvm-p0-5`，
六个子仓也各有独立 worktree，分支均为 `p0-5-native-hdr`。未修改内核或其他会话工作树。

## 来源与共享接口

完整提交和用户态文件 SHA 见[候选清单](../../packaging/hdr10/phase2-sources.json)。
正式 workspace/tested_build 锁未更新；这些提交需要在两种 GPU 栈实测后才能推广。

| 仓库 | 提交前缀 | 改动 |
|---|---|---|
| gst-plugin-venc | 1f29849 | 公共 vim4h265src 的 Wave5 后端、真实 Main10 控制、HDMI controls → prefix SEI |
| gst-plugin-vfmcap | b2df852 | Vulkan P010→SDR NV12 分支、height-only 按比例缩放 |
| One-KVM | 50f0b4d4 | 原生 P010 同源截图阀门，按请求 GPU tone map 后沿用 SDR JPEG 转换 |
| NanoKVM | 0525dea | 探测公共源能力，截图请求借用同一 raw pad，取消/重开不另开 VDIN |
| JetKVM | 166719c | 删除应用层对 Wave5 的提前排除，依据公共源探测 |
| uStreamer / PiKVM | 7d927ac | Janus 与采集共用能力探测；HEVC/JPEG 共用一个 VDIN 所有者 |

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
| 主仓 | unittest 365 项通过，14 跳过 |
| 三应用接收器 | application-receiver.mjs 仅语法检查；保存真实解码色彩/统计及关键帧的候选，尚未实板验证 |

原始日志与用户态封存档在本 worktree 的 `build/p0-5/`；`manifest.json` 明确
`hardware_validated=false`，不含 Image/DTB/模块，**不能直接作为 RAM 启动候选**。
私有标准 V4L2 插件复用 r13 的 b9269d05…，没有重编已通过组件或完整内核。
恢复会话时核对队列空闲、无遗留构建，两个保留验证容器仅运行 idle tail。

## 上板结果与余项

| 本轮门禁 | 状态 |
|---|---|
| 官方 UU 客户端原生 HDR | 未验；已确认官方 uuyc-cli 可自动连接，不能以协议模拟器替代 |
| 三应用原生 HDR、切换、缩放 | 未验，未全局部署或开放正式能力 |
| 原生期间 SDR 截图 | 实现/离线合同通过，GPU 实际画面未验 |
| 非零静态 metadata | 未取得真实源；逐字节透传未验 |
| HLG / 动态 metadata | 无真实源，未验 |
| kbase / Panfrost + 稳定性/CMA/taint/WARNING | 本候选未上板；不能沿用 r13 或 llvmpipe 结果计通过 |

最新 main 在核对时为 583e411，tested_build 仍为 uhd5，尚未登记可复用的统一 uhd6。
未取板票等待它，也未使用不匹配模块/BTF。下一步先取 P0-1 的固定归档/哈希和运行时合同，
把上述用户态提交纳入独立 payload；补完并离线验证 M6 逐屏截图门禁及完整无人值守窗口脚本。
脚本未就绪之前不排板窗。窗口目标≤15分钟、硬上限30分钟，采样前 sampling on；失败收证据、
停相关负载、回5.15、M6 HDR关与恢复前台、服务/UDC/保护哈希核验后释放。

无需用户操作或新授权；当前仍是未完成的 P0-5 候选阶段，不请求放宽实板门禁。
