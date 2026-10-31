# 7.3 本地 HDMI 透传与声音：uhd4 起点

最新执行约束及移植进度见[离线移植](passthrough-73-offline.md)：另行通知前禁止所有上板与MCP，
本页上板清单只作未来门禁，不是当前执行授权。

r1先完成离线候选资源门禁；r2已申请首窗，因OUT无HPD/EDID停止候选启动。
P0 尚未通过，不改默认启动、正式版本锁或前端。
主仓基于 `470da38`，分支 `passthrough-73`；VM 独立源码
`~/src/linux-7.3-passthrough-73` 同名分支基于 `8bca939d6bbd3`。
One-KVM 基线 `db848a52`。内核已有实现与验收边界见
[合入记录](bringup/2026-10-24-hdmi-integration.md)和[帧所有权设计](hdmi-passthrough-design.md)。

## 差距与证据

| 项目 | 5.15 产品证据 | uhd4 差距 / 所需实现 |
|---|---|---|
| 本地与远程共存 | [TEE、4K H.265 十分钟](bringup/2026-10-24-vendor-passthrough.md) | 正式 DT 为 M0 simpledrm，native VPU disabled；M3-video 的 VD1 reader/退休已在源码中，未验硬件。需独立常驻服务拥有唯一 V4L2 队列，用 PRIME/KMS 显示并向所选应用分发 |
| 色彩 / 60fps | [颜色闭环](bringup/2026-10-24-display-color-loop.md)有短样本；[失败交付](bringup/2026-10-24-display-color-user-handoff.md)不能算通过 | M3-video 开关未启用；颜色不能只靠压缩采集卡。历史 RX ERROR 后有独立修复，仍须验当前 uhd4 + native 显示 |
| 音频 | [EXTN→SPDIF](bringup/2026-10-25-vendor-passthrough-audio.md)、[xrun 原地恢复](bringup/2026-10-25-passthrough-audio-recovery.md) | M2/M3 有 TX 997Hz 与 RX/TX RUNNING 历史；M0 无 TX。7.3 RX PCM 不能被桥与 One-KVM重复独占，需在唯一采集者分发；TX 走 ASoC/hdmi-codec/ELD |
| 跟随 / HPD | [1080p 真时序](bringup/2026-10-25-vendor-passthrough-1080p.md)、[HPD](bringup/2026-10-24-vendor-passthrough-hpd.md) | KMS TEST_ONLY + source-change / connector 恢复；不重写 RX EDID，不周期 modeset；[抖动黑屏修复](bringup/2026-10-24-vendor-passthrough-blackout.md)的中值/滞回语义需保留 |
| HDR 偏好 / API | [hdr 与 hdrToSdr 合同](bringup/2026-10-25-passthrough-hdr-switch.md)；[早期映射缺口](bringup/2026-10-25-vendor-passthrough-hdr.md)已被后续双路径扩展 | uhd4 HDR2 输出 SDR NV12，不能再贴 PQ 标签。hdr=true 的原生输出仍缺高位深扫描/独立显示处理；hdr=false 可共享真实 SDR 映射帧。后端实际读回，保留 enabled/audio/hdr 部分更新语义，UI 不改 |
| 性能 | 有原始/扫描计数与远程约60fps，尚无同条件光学延迟全量对照 | 分报帧就绪→提交→锁存→退休、接收 fps/间隔尾部、CPU/CMA、理论带宽；压缩采集卡与软件时间不冒充 glass-to-glass |

## 资源审计与路线

### r2 架构决定：独立常驻采集与分发服务

硬约束：四款应用任选、零远程客户端、编码停止及切换应用都不能停本地透传。
撤销r1“把显示消费者放进One-KVM”的产品接入方案。推荐(b)：独立常驻服务拥有唯一
V4L2队列和KMS提交，KVM应用只是可断开的dma-buf消费者；manager只控制本地显示/声音，
不随应用服务生命周期停止采集。没有本地/远程消费者时才允许停采集。

| 标准 | (a) 内核VDIN→VD1所有权 | (b) 独立用户态V4L2/PRIME服务（推荐） |
|---|---|---|
| 功能独立性 | 可做到，但必须让VDIN脱离vb2应用STREAMON/STREAMOFF；现有VD1 reader/退休只保护KMS导入，并不是内核自动路由 | 本地显示订阅长期存在；四款应用订阅/退订不动采集队列，应用切换不切本地显示 |
| 就绪→锁存 | 可省DQBUF/用户态调度，理论较低；仍需等下一vblank，不能省安全退休 | 增加DQBUF/事件循环/atomic提交调度；不整帧复制，不刻意多等一帧，需量化分布后才与5.15比较 |
| CMA | 内核常驻池与vb2导出生命周期重构，若另建池会超过预算 | 沿用一个≤192MiB池，所有订阅共用导出；pending最多一帧，已提交帧不能靠超时回收；14块能否容纳扫描/退休/编码仍须压力实测 |
| 上游与维护 | media到DRM内部耦合、跨子系统锁/热拔插/模块卸载，缺标准自动路由ABI；可能变成新的VFM私有框架 | V4L2/dma-buf/DRM标准内核ABI；服务IPC是用户态可版本化协议，维护额外进程与各应用适配，但避免内核私有跨栈路由 |
| HDR2/hdr10 | 两条采集/映射路径与显示调度强耦合；需同时改采集所有权 | 服务保留原始色彩/位深及generation；HDR2 SDR和未来hdr10高位深是不同stream描述，不给SDR贴HDR标签；高位深VD1仍待实现 |

原[设计](hdmi-passthrough-design.md)事实上已画出单一采集broker→DRM/Wave5，
不是已实现的内核VDIN→VD1自动路线。沿用其reader/退休合同，选择用户态broker作为所有者。
服务初期先实现有界租约核心与确定性离线测试，后续接真实DQBUF/EXPBUF、SCM_RIGHTS、
KMS/fence等待及systemd；不把纯核心测试称为硬件实现。

应用改动面（在各自新分支实施，当前不改其它工作树）：

- NanoKVM：7.3原生采集/GStreamer输入改接broker source；编码及远程会话保持应用所有。
- JetKVM：同样替换7.3视频输入适配；重配仅更新订阅，不能STREAMOFF主队列。
- One-KVM：将V4L2输入换为导入broker dma-buf的GStreamer source，归还由GstBuffer最终引用与编码读取完成共同控制，保留UU/录屏共享编码。
- PiKVM/uStreamer：替换7.3V4L2抓帧入口，JPEG/H.26x消费者从broker拿帧；停止推流只退订。

优先共用一个GStreamer source给前三款；PiKVM使用同一小型IPC客户端库。
四款音频同理改接独立音频所有者，PCM源不能被独占重复打开。5.15路径不变。
后续API需同时报告capture服务、本地实际扫描、远程订阅，不能把进程active等同于透传running。

- uhd4 `sources.toml` 选 `display-m0.dtb`。M1→M2→M3-video 的显式 profile
  才关闭 simplefb、启用 native ENC2、split-vcbus、VD1 和独立 TX 声卡；不能只改 Kconfig。
- `t7-vdin-test.c:t7_vdin_map_regs` 的 split 窗口包含 VDIN0 HDR2
  `0xff004800+0x400`、reset 字 `0xff009c80+4`、仲裁 `0xff009e88+8`、
  top `0xff01042c+0xc`。M0 的整个 VCBUS 租约不能与 native 显示同时申请。
  reset/仲裁字只更新所属位；地址不重叠也不能证明时钟、供电、位级访问共存。
- 192 MiB 是整个 VDIN vb2 池的上限，不是显示额外预算；4K NV12 最多16块，
  uhd4 GStreamer 实测申请14块。显示当前帧与退休帧从同池持引用，必须先证明
  最坏 encoder/scanout 持帧数能留下采集工作缓冲，不能无界追加或触发深拷贝。
  CMA 同时供 Wave5 工作/参考帧和 GPU；[DMA 合同](hdr2-dma-contract.md)继续适用。
- uhd4 为 Panfrost；不改 kbase/hdr10 工作树。未来组合 DT 必须只绑定一种 GPU 驱动；
  KMS PRIME 不依赖选择哪一种 GPU，导入/fence 必须单独验。HDR10 未来输出不能复用已映射的8bit帧伪装 HDR。
- 主线 DRM/KMS、V4L2/dma-buf、ASoC/hdmi-codec/ELD 为接口。
  handoff 独立入口和 split-vcbus 属性是现有临时隔离方案，收敛为 meson-drm 资源所有权；
  manager 不接厂商 VFM/sysfs 到新内核，不推 blob。

## 分阶段门禁与板时

| 阶段 | 离线交付 / 门禁 | 上板门禁（单次≤30分钟，预留回5.15） | 预计板时 |
|---|---|---|---|
| 1，本轮 | 实现读取真实 DTB 与内核 split 资源表的候选预检，拒绝 M0、simplefb 冲突、GPU 双驱动、VDIN/显示区间重叠；对 uhd4 M0/M3-video 实跑，已有显示/HDR2 C fixtures。它只批准进一步测试，不宣告 supported | 后续首窗口：确认实际 OUT 接线/EDID，RAM 候选身份、native/VD1/TX 枚举、4K60 采集/编码短烟测；错误立即回退 | 20–25分 |
| 2 | 唯一采集者分发给编码与 PRIME 显示；一次 EXPBUF，实际 pitch/offset，DQBUF 后提交；READ fence 退休后才 QBUF。确定性覆盖取消、120帧推进、旧 generation、故障 pin；对象编译/checkpatch | SDR 1080p/4K60、三高度动态帧号、60次地址更新、零 ERROR/撕裂；与 One-KVM H.265 4K60 同跑，最多10分钟/段，CMA归还 | 2×25分 |
| 3 | ELD 约束、唯一音频采集者→Opus/TX，有界队列/漂移、xrun 持续 TX；mode/source-change 状态机，GET 只读，单写入者；后端 API 测试 | RX/TX 同时 RUNNING；250/750ms 暂停桥后原句柄恢复，TX prepare/modeset 零增量；44.1/48k、无源恢复。只查状态/计数，不放测试音 | 2×25分 |
| 4 | hdr 偏好按真实像素域选择；原生 HDR 高位深路径与 hdr10 线接口评审后集成；API output.hdrToSdr 由映射事实读回 | MCP先截图，仅M6布置，HDR off/on/off；包/颜色寄存器读回，恢复设置并截图。EDID真1080p跟随、软件HPD（若具备已审阅接口）恢复；需物理插拔则停止说明 | 2×25分 |
| 5 | 正式候选干净整包、新release、全量所需回归；性能汇总按版本/输入/采样端点拒绝混比 | 当日同哈希5.15基线复用；透传关/开各测CPU、远程fps、frame间隔、延迟分段；稳定性每段≤10分钟。无光学硬件时明确保留光学门禁 | 2–3×25分 |

所有编译/C fixture 经 `tools/board-queue run --heavy --who passthrough --purpose build -- ...`，
在Mac共用队列；不持板编译，sampling 阻塞 heavy。上板用 board-queue run 包围 window 脚本，
经 board-window boot-candidate/mcp/receiver/collect/return-baseline，批次结束核对5.15与启动文件哈希。
有人等待则让出，不立即重取。无需本轮用户物理动作；历史 RTK 显示器记录不证明当前接线。

## 第一阶段交付与下一批清单

预检入口（Linux VM 内执行，路径替换为本次构建的实际文件）：

```sh
python3 packaging/kernel-edge/passthrough-preflight.py \
  --kernel-source /home/deepdream/src/linux-7.3-passthrough-73 \
  --dtb /home/deepdream/build/hdr2-uhd4/arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-display-m3-video.dtb
```

退出0只表示静态资源门禁通过，1为明确拒绝，2为输入/工具失败；报告永远
`runtime_verified=false`。调用方负责提供同次构建源码与DTB，源码revision/dirty和DTB SHA
仅是审计标识，不替代构建清单匹配。正式 `sources.toml` 不变。

本轮结果：原 uhd4 M0 SHA `3b8b423f…c19e30` 被拒绝；同一归档构建的
M3-video SHA `f42db15b…7f12f1` 通过。既有 KMS fixture 另确认46个
显示bank与采集互不重叠、15个独占域，仍不证明共享时钟和供电实际安全。
主仓全套353项、13跳过，其余通过；新增6项覆盖真实DT编译/解析、整窗租约冲突、
HDR2边界、disabled祖先、GPU双节点、simplefb与损坏DTB。

定向内核12个fixture通过（video-sync、producer-layout、HDMI atomic、video KMS、
VDIN、HDR资源/池预算、color、buffer-layout、export-identity、source-events、audio、HLG），
并对真实M3-video DT跑资源fixture。首轮producer-layout因uhd4增加的字段/辅助函数
缺失而编译失败；修复夹具，断言generation/ticket随首次取帧建立、同槽重arm不重新发号，
保留8组VDIN与8组Wave5真实布局检查。strict checkpatch 零error/warning/check。
一次编排误写两个fixture文件名，未执行，保留失败日志；更正为实际入口后通过。
原始离线日志在本worktree `logs/passthrough-73/`，不含上板证据。

r1没有构建新Image、运行KUnit、访问板子或部署。内核仅修测试夹具，不需要重编模块；
内核分支 `passthrough-73@e49cc60ac6203`，可复现补丁随主仓保存于
[producer fixture补丁](../packaging/kernel-edge/passthrough-producer-fixture.patch)。
阶段2之前仍需实现产品显示消费者，预检不能替代它。下一批具体上板门禁：

1. `collect`读取当前release/默认项与已审阅的OUT connector/EDID，确认实际接线；
   若现有状态不能证明连接目标则停止记录，不要求用户临时换线。保护5.15文件哈希。
2. 从uhd4构建清单准备显式M3-video的RAM payload，先过上述预检和prepare的全量模块匹配；
   `boot-candidate`后确认新boot ID、源码/模块身份、native KMS/VD1、VIM4HDMITX/ELD。
3. 同一One-KVM H.265 4K60会话短接收：有效帧与framesDecoded推进、ERROR、CPU、CMA、
   IRQ/温度、oops/taint增量；此时无显示消费者，不能记作透传共存通过。
4. 产品消费者实现后才做双路径连续帧、逐行一致性、scanout退休/fault pin与零拷贝计数；
   音频只查RX/TX RUNNING、ELD/Audio InfoFrame与计数器，不启动可听测试音。
5. 每个窗口末 `return-baseline` 核5.15、启动文件哈希、服务和UDC；HDR若有布置必须关并截图确认。

## r2进度

[首窗记录](bringup/2026-10-31-passthrough73-r2.md)保存OUT断开读回及未启动边界。
[阶段2核心与适配合同](../packaging/passthrough73/README.md)已实现有界分发、
disconnect后保留硬件读者、跨代拒绝及fault pin，8项确定性测试通过。
每消费者按in-flight上限+1 pending保守计槽，另留2块采集工作槽；
One-KVM现有12下游lease不能再直接叠加显示，14/16池需降低远程持帧预算后再接适配层。
真实V4L2/KMS、SCM_RIGHTS IPC、四应用与音频适配仍未实现；不宣称已能常驻透传。
