# 本地 VRR／帧锁定透传审查

下文是实施前审查。后续[离线准备](vrr-preparation.md)已修正RX基准帧率解析、
应用预算与部分TX范围/寄存器问题；控制器与本地输出启停仍未完成，尚无真实VRR验收。

本轮只读源码和既有上板证据；未访问板子、改模式、构建或测量新候选。
目标是降低 HDMI RX→HDMI OUT 的板内显示延迟，不是降低编码或 UU 网络延迟。
建议先做固定 1080p60 的小范围行时序锁定，再做真正的可变刷新率；不同时引入120Hz。

## 版本与结论

- 我们的 common_drivers：`f3b34664e477ab5e8a4a0796bcca76fa5161f832`。
- 对照 StreamBox common_drivers：`9baca1e54f68c1e87b46da807772247f914fdb24`；
  tvserver：`9fc8bf022c2611ea62de930e22f0debbdf3dc2d8`。
- 当前5.15主链路是 VDIN0 10-bit→amvideo→TX，VDIN1 同源独立 HDR→SDR→KVM。
  详见[原生双路径](bringup/2026-10-25-native-hdr-dual-path.md)。此隔离使显示侧行级读取有研究价值，
  但 VDIN1 仍必须按完整帧交给编码器。
- 我们有 VRR/vlock 框架，没有 StreamBox 的 `LL_FRAMELOCK` 扩展；不是只改启动参数即可获得该能力。
- 给定网页的“禁用 one-buffer”已不能描述他们当前主线。后续
  [979099977](https://github.com/aml-streambox/common_drivers/commit/97909997759b9abaf9c8a4d82980a829ee9e951e)
  在强制低延迟模式下重新强制使用同一物理缓冲，并绕过 `dbg_force_one_buffer=2`。
  这会使“保留上一帧即可安全采集”的前提失效，不能整体移植到 vfm_cap 采集模式。

## 先分开两种功能

| 功能 | 源与输出行为 | 合理的第一步 |
|---|---|---|
| 固定频率的内部帧锁定 | 源仍约60Hz，TX在小范围调整垂直总行数以跟随源的晶振漂移；不向源声明新VRR能力 | 仅对已验证显示器、同尺寸同频率透传启用；TX不伪造VRR EMP |
| 原生VRR透传 | 源持续改变帧周期，输出须在显示器声明的范围内跟随，并正确处理VRR EMP | 在固定帧锁定通过后，独立验收EDID能力交集、实际VTEM状态、范围边界与退回固定刷新率 |

StreamBox 的 `CTv::CheckAndApplyAutoVrr()` 按实际 `VDIN_VRR_BASIC` 区分两者，
不只看 FreeSync 能力位：原生输入选择内部 mode2＋TX GAME EMP，固定输入选择 mode1。
源码同时对 TX 能力做门控，故网页“普通设备也能强制VRR”不能视为任意显示器兼容证明。
具体地，TX注册仍要求 `vrr_max>=100 && vrr_min<=48` 才设置设备enable，
`vrr_drv_func_en()` 对设备enable=0直接拒绝，即使选择LL_FRAMELOCK也不绕过。
若研究普通sink的固定帧锁定，须另立已验时序资格，不能把VRR能力位伪造为支持。
debug写入口没有传播底层启用失败，必须读回实际enable/state，写入成功不算已启用。
[tvserver策略](https://github.com/aml-streambox/aml_tvserver_streambox/blob/9fc8bf022c2611ea62de930e22f0debbdf3dc2d8/libtv/CTv.cpp#L1388)。

## 最小候选的改动点

路径以下均相对 common_drivers；行号以本轮基线为准。

| 层 | 当前实现／缺口 | 候选范围 |
|---|---|---|
| 显示设备注册 | `drivers/media/vout/hdmitx21/hdmi_tx_vrr.c:1237` 的 vfreq min/max 对调；主要从 uboot 模式初始化注册 | 修正能力字段，在 `hdmitx_common/hdmitx_mode_set.c` 模式设置完成后刷新当前ENC实例；非VRR能力不得参与除法，范围计算先乘后除 |
| 行时序控制 | `drivers/media/vrr/vrr_drv.c` 已有 ENCP 控制、line_dly 与设备索引 | 增加默认关闭的固定帧锁定状态；StreamBox 用名义 vtotal±2 行，仅作为初始候选，不当通用安全范围 |
| line_dly生效 | 当前读取用了已经带offset的reg再加一次offset；crop未变时新延迟值不写入 | 分离并验证地址修正、延迟更新与状态切换；禁止无边界的任意调参 |
| 帧锁定策略 | `drivers/media/enhancement/amvecm/frame_lock_policy.c:406` 读 LCNT；已有 VRR/vlock 切换 | 核对T7真实字段后验证上游改为高13位的修正；延迟取当前ENC实例，而非任意首个同compatible节点 |
| 显示帧地址 | `drivers/media/vin/tvin/vdin/vdin_drv.c:3088,3768`：one-buffer及Game Mode2交帧 | 若实验采用行级共享，限VDIN0、原生显示路由，核实RDMA生效地址与VPP读地址；完整帧消费者存在时不得开启 |
| 用户态所有权 | `vim4-manager/deploy/vim4-passthrough` 已独占管理显示模式和恢复 | 由该服务持有模式租约、判断资格、退回原模式；不另起与tvserver争写的常驻控制器 |

对应实现可分片审阅：[VRR驱动](https://github.com/aml-streambox/common_drivers/blob/9baca1e54f68c1e87b46da807772247f914fdb24/drivers/media/vrr/vrr_drv.c)、
[模式注册](https://github.com/aml-streambox/common_drivers/blob/9baca1e54f68c1e87b46da807772247f914fdb24/drivers/media/vout/hdmitx_common/hdmitx_mode_set.c#L225)。
不能整个 cherry-pick `c64271e87`：它还混入视频全局调度、V4L2回写及TVPro DTS修改。
其中“每次VSYNC只能toggle一帧”会改变所有显示路径的追帧策略，必须独立证明需要。
TVPro引脚、内存、音频DTS不属于VIM4帧锁定候选。

## Game Mode 与缓冲条件

`tools/hdmi-setup.sh` 写的 `game_mode 3` 是 **attr接口的十六进制掩码0x3**，
即 BIT0|BIT1，完整帧Game Mode1。`vdin_drv.c` 的全局 `game_mode=3` 则映射到
BIT0|BIT2，即Game Mode2；两者数字相同但意义不同。`vdin_debug.c:4103` 会写
全局 `vdin_force_game_mode`，不能假定向vdin0 attr写值就只影响VDIN0。

因此实现前必须完成：

1. 将候选生效条件限定到 index0、normal显示工作模式、原生 `vdin0 amvideo` 路由；
   VDIN1 start/stop/reopen仍保持现有V4L2及RDMA语义，不继承显示实验的全局强制值。
2. 进入one-buffer前确认没有vfm_cap等完整帧消费者持有VDIN0 DMA-buf；这些消费者
   不能靠多等一帧保证安全，因为旧逻辑帧与当前写帧可能是同一物理地址。
3. 显示读取必须落后写入足够行数，且不在帧边界追过写入；line_dly需包含颜色处理、
   缩放和总线竞争余量。先原尺寸SDR，不从带缩放/HDR配置直接猜安全值。
4. 退出时先让显示停止读取活动写缓冲，再停用帧锁定并恢复各缓冲原地址、原模式及扫描；
   不能只清软件标志就立即复用原地址。需核对one-buffer flag、canvas及VPP退休状态。
5. 原生HDR元数据和KVM SDR颜色不得被候选覆盖；只挑选VRR相关hunks，保留我们已有
   TX SDR时清除旧DRM包的修复。

VDIN1实际 `N提交→N+1地址生效→N+2交帧` 已有逐缓冲证据，不能借本项目删掉其等待。
见[交付时序核实](bringup/2026-10-25-vdin1-frame-handoff.md)。

## EMP与非VRR显示器的具体限制

StreamBox 的 `hdmi_tx_main.c:vrr_mode_store()` 增加配置包与启停操作，
`hdmi_tx_vrr.c:vrr_init_game_para()` 改为使用配置中的VRR_EN。
但关闭分支设置 `para.vrr_enabled=0` 后调用 `hdmitx_vrr_enable()`，后者又将同字段置1；
VSYNC handler还在该字段为0时直接返回。按源码，这不能证明100ms等待期间确实发出OFF包。
移植应把“发送一个关闭声明”与“停止周期发送”分开，并对最终硬件EMP读回做验证。
[关闭入口](https://github.com/aml-streambox/common_drivers/blob/9baca1e54f68c1e87b46da807772247f914fdb24/drivers/media/vout/hdmitx21/hdmi_tx_main.c#L2514)、
[发送开关](https://github.com/aml-streambox/common_drivers/blob/9baca1e54f68c1e87b46da807772247f914fdb24/drivers/media/vout/hdmitx21/hdmi_tx_vrr.c#L1364)。

固定帧锁定不应向不支持VRR的sink持续发送VRR_EN=1，也不应自动把源EDID改成支持VRR。
微调±2行仍是物理时序变化，非VRR显示器可能重新锁定或黑屏；必须按sink身份和时序验证，
换显示器、失锁、HDR/分辨率变化时退出候选。若前一状态确实启用过EMP，固定模式不能
简单跳过TX控制而遗留旧EMP；先有明确的关闭和读回，再切换策略。

上游 `vrr_ll_framelock_adj` 是可写int module parameter，没有源码范围校验；
负值、过大值与unsigned vtotal运算会产生错误范围。产品入口应限制到已验范围并检查
合法vblank，第一阶段不向网页暴露此调试参数。

## 分阶段验收

| 阶段 | 操作与通过标准 |
|---|---|
| 离线 | 只改候选分支；验证当前ENC选择、min/max与空EDID、固定/原生VRR转换、重复启停、VDIN1不继承显示模式。构建匹配Image/DTB/模块，逐项review相关hunks |
| 基线 | 独占窗口记录运行版本、RX/TX实际时序、game_mode实际掩码、canvas地址、VDIN1序号、声音参数及所有服务PID；同源动态标记，上中下帧号一致 |
| 固定1080p60 | 原模式A→小范围帧锁定B→A，至少三轮；先完整帧显示策略，再单独启用经审核的行级共享。用接收/输出帧同步、读写行相位及物理输出观察确认收益，无撕裂/失锁/重复模式设置 |
| 并行KVM | 同时H.264/H.265观看、MJPEG和应用切换；测VDIN1完整帧、时间戳、sequence、浏览器帧号一致性、丢帧/冻结和编码段。网络延迟单独报告，不从TX相位推算 |
| 恢复 | OUT拔插/换sink、IN失锁、源分辨率/59.94↔60切换、开关透传、服务重启；恢复原掩码、独立地址、时序及EMP状态。网页观看者生命周期不触发EDID/HPD |
| 扩展 | 固定4K60 SDR→HDR显示/SDR采集→1080p120（先完成其独立链路验证）；最后真实VRR源/sink的上下界、跨界和VRR关闭。每一组合单独登记资格 |

建议每档先短测失败即回退，通过后做至少30分钟漂移观察；覆盖KVM空闲/活动及CPU/网络负载。
600行@4K60、vtotal2250约4.44ms只是行数换算，不是测得的RX→面板延迟。
若没有外部光学/视频测量，只能报告板内扫描相位；源绘制→浏览器测量不能代替本地输出。
本地视频缩短后要复核音画差：当前音频桥有约26.7ms播放队列，视频更快可能暴露音频滞后。
见[音频桥测量口径](bringup/2026-10-25-vendor-passthrough-audio.md)。

## 7.3边界

7.3采用独立VDIN/V4L2采集和实验DRM VD1显示消费者，不能套用厂商VFM/VRR sysfs补丁。
已有M3-video设计仍要求显示读退休后才能归还采集缓冲；OUT_FENCE只代表锁存。
先完成固定频率透传及缓冲所有权验收，再设计DRM驱动的可变vblank/VRR能力和原子状态。
本轮没有验证或改变7.3的显示能力，见[已合入范围与剩余步骤](bringup/2026-10-24-hdmi-integration.md)。
