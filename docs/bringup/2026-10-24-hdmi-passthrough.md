# 2026-10-24：HDMI 透传第二阶段实现记录

本轮已按用户决定停止7.3上板工作，转由另一会话推进厂商5.15透传及默认启动切换。
7.3目标持续采集前置条件通过，**VDIN→VD1透传尚未上板验收**。
架构与所有权合同见 [设计文档](../hdmi-passthrough-design.md)；
根因及厂商对照见 [周期量化调查](2026-10-24-hdmi-capture-quantization.md)，
计量器现场及持续采集数据见 [稳定性复测](2026-10-24-hdmi-capture-stability.md)。
本轮7.3测试保留默认eeddb005与manager974ab40，不合入正式内核、不正式部署。

| 范围 | 当前状态 |
|---|---|
| 采集稳定性 | 真实源/自环1080p60及4K60共四档各约610秒、36601帧，0 ERROR/观测失锁 |
| 无换线一次性启动 | 自环720p回退接管成功，随后1080p60/4K60重新modeset与短测通过 |
| VDIN→VD1、60fps、退休/fence | reader/退休及地址更新实现已提交；69项离线测试通过，尚未上板 |
| 能力探测ABI | 尚未定义已实现能力，不以NV12枚举单独宣告支持 |
| 参考验证工具 | 原生V4L2持续采集/ERROR比例/运动标记工具已实现；透传工具待开发 |
| RX→TX音频 | 待验证；自环禁回送 |

## 离线与上板边界

VM `~/src/linux-7.3-hdmi-passthrough` 的 `vim4-hdmi-passthrough` 基于c24465df，
没有切换原内核主工作树。提交按RX、启动接管、视频退休分组，见下表。
RX候选41c31fc及启动候选cf6e238均完成Image/DTBs/2339模块构建；最终VD1提交仅完成
受影响arm64对象编译和69项host fixtures，未做最终整包构建、KUnit或上板。
主仓新增 [hdmirx-soak.c](../../tools/hdmirx-soak.c)，已登记工具目录；Mac全套243测试通过
（7跳过），Linux故障注入和C严格编译通过。

用户通过need-user/user-done协议确认暂停KVM使用及随后自环接线，回复已归档并删除。
Mac双锁覆盖已结束的批量窗口。一次未完成暂存即重启的无效尝试已如实保留，未覆盖默认文件；
后续只有stage退出0并发布完整目录后才选择候选。
原始证据、构建、源程序、模式快照和保护文件哈希在 `logs/hdmi-passthrough/`。

后续需保持单一采集所有者：独立参考工具占用VDIN时不能同时启动第二个One-KVM采集队列。
正式应用下一轮从同一个捕获帧租约分发显示与编码；管理器不直接创建采集队列。
本记录不能当作透传可部署结论。

## 采集根因及四个长测

正式基线eeddb005同样存在ERROR标记：约10秒运动标记窗口中601个完成帧、462有效、
139 ERROR（23.13%，有效46.099fps）；139个ERROR的三处图案标记均完整。
该段与文件传输部分重叠，不能作为公平性能对比；另一段无像素读取窗口为15.31% ERROR。
浏览器H.265约60fps不能证明原始帧有效，也不能据此断言One-KVM已静默跳过这些帧。

已定位两类测量拒绝：FDET双快照精确相等会拒绝1–2 tick量化抖动；TOP meter则在
5V/SQO/alignment正常时出现VALID低脉冲。180秒只读采样捕获936次，观测低电平
约0.58–1.10ms，p50 0.716ms、p99 1.083ms。两窗口重测仍在151.190秒遇到1 ERROR；
两个8192参考时钟窗口不足以覆盖该脉冲。四窗口版本最多等待约1.37–1.57ms，
每轮重新检查物理链路，必须取得新VALID及匹配时钟；持续无效、真实失锁仍返回错误。
FDET修复沿用原500ppm租约容差并校验两次快照，不放宽几何/色彩准入或硬件PHY阈值。

四窗口候选 `41c31fc123935`，build ID `890406629692236532d2cfaa2346ee052fa85755`：

| 输入 | 有效帧 / ERROR | 持续时间 | 有效fps | 观测失锁 |
|---|---|---|---|---|
| Mac mini 3840×2160p60 SDR/444/8bit | 36601 / 0 | 610.019695s | 59.998063 | 0 |
| Mac mini 1920×1080p60 SDR/444/8bit | 36601 / 0 | 610.019815s | 59.998051 | 0 |
| 自环1920×1080p60 RGB full | 36601 / 0 | 609.949290s | 60.004988 | 0 |
| 自环3840×2160p60 RGB full | 36601 / 0 | 610.009797s | 59.999036 | 0 |

合计146404个有效完成帧、约2440秒。每档1Hz状态ready均1，invalid_frames、stream_stops、
faulted、stream_copy_bytes均0，source_changes保持各自入场值。
真实源三高度标记坏帧0，但存在源帧号重复；自环为静态图案，前后各三帧颜色最大误差1。
这不等于逐像素全程无损，也不是VDIN→VD1透传或光学延迟验收。
四档IRQ frame-done→DQBUF的p99分别0.188/0.171/0.174/0.172ms；完整分布与边界见
[稳定性复测](2026-10-24-hdmi-capture-stability.md)。

真实源已重现旧测量拒绝，它不是自环独有；基线与颜色候选共有RX算法，未发现这类ERROR
为颜色候选独有回归。历史lowclock 36/38剩余QUERY失败没有同等现场，不能宣布同源或已修复。

### 可独立合入的RX/KVM采集候选

`c24465df..41c31fc123935` 的七个RX/VDIN提交仅涉及采集诊断、元数据和测量策略，
对7.3 KVM采集本身有价值，不依赖VD1显示消费者或透传管理开关。
恢复工作时可单独评审、摘取到正式采集基线并做KVM回归；不要整体合入带颜色/显示实验的分支。
**本轮没有合入vim4-kvm-7.3，没有正式部署。**

## 自环启动接管（已上板）

保持自环接线，以旧候选一次性启动取得现场：U-Boot无EDID回退720p60 RGB8，
ENC2 totals1649/749、TX active1280×720，OSD fetch仍1920×1080 RGB888、stride5760。
实际frame地址为 `0x3f800000`，原合同只允许另一个boot frame `0x3fdeec00`；
两者均在DT已严格要求的 `0x3f800000+0xc00000` no-map保留区内。
旧候选的显示驱动和TX bridge均按原合同拒绝，仅发布GPU card；这是预期对照，不是新内核崩溃。

`86c2ea484d38d` 仅给原生ENC2且管理OSD SRAM的完整所有者增加已知720p时序，
TX仍对只读固件接管路径保持1080p限制；`cf6e2381164af` 进一步只为该回退配置允许
保留区首帧地址。fetch几何/stride/格式、AFBC、simplefb冲突、外部RDMA及SRAM安全检查保留。
新C测试先在旧实现失败，修复后通过；两个配置的九项fetch/timing扰动、AFBC及
不完整所有权均拒绝。68项host fixtures和两提交strict checkpatch通过，完整构建通过。
不支持任意未经验证的固件布局，不写eMMC启动环境。

串口曾在发送重启前由macOS返回Device error，未改工具代码；用户按文件协议重插Mac端
Sipeed双UART后恢复，随后完成旧候选对照。证据 `selfloop-old-boot-uart-2.log`、
`selfloop-old-boot-registers.json`。

最终候选cf6e238 build ID `42039aac307c0bef9366ec380abcaa8a9fb6d153` 保持OUT→IN接线，
U-Boot仍无EDID并回退720p，内核成功发布meson-t7-handoff显示card。
随后标准atomic TEST_ONLY/modeset到1080p60及4K60，各601个有效完成帧、0 ERROR，
三帧颜色抽样最大误差均1；默认启动文件保护哈希、私有模块匹配、taint=0均确认。
这证明无需换线即可启动并重新设置已支持模式，未宣称支持任意U-Boot布局。
证据 `boot-fixed-final.log`、`boot-fixed-{1080,4k}*`。

## VD1离线实现与提交

每个prepare_fb创建独立context的dma_resv READ fence，先调用标准GEM producer fence准备，
同一reservation去重。取消尚未提交的状态只signal自己的reader；提交后由scanout持有。
旧帧仍保留到原来锁存后完整扫描周期结束，IRQ只处理fence，framebuffer引用在进程上下文释放。
两阶段重配沿用同一reader；超时/缺少退休边界时保留所有可能在DMA中的帧，迟到IRQ也不能释放。

孤立VD1的三个地址字更新允许锁存后完成atomic依赖，旧帧的额外扫描退休期保持不变。
混合平面、布局重配、启停仍保守同步等待。真实C测试覆盖120代更新、跨计数回绕、
空闲退休、别名、取消/部分失败及故障pin；速率用例在旧实现失败、修改后每vblank推进一次。
**尚未上板，不宣告60fps能力或完整fence硬件验收。**

| 组 | 提交（按顺序） | 验证范围 |
|---|---|---|
| RX诊断与完成帧元数据 | 1cb9654e3fb0f、0758b280a2ca6、99093e68cb8b6、059b1d8117a97 | 离线及候选上板 |
| FDET与TOP窗口 | 03cabbd5cd714、131fbdf603eee、41c31fc123935 | 含两窗口失败、四窗口四档长测 |
| 自环启动接管 | 86c2ea484d38d、cf6e2381164af | 离线与无换线启动、两档短测 |
| reader/退休 | d4e7e46533b37、8e0c1a641c061 | 仅离线及arm64对象编译 |
| 地址更新流水 | 06ba4ba9f2e27 | 仅离线及arm64对象编译 |

全部12个小提交strict checkpatch为0 error/warning/check，工作树干净，无需另存WIP。
分支入口：[vim4-hdmi-passthrough](https://github.com/vim4-kvm/linux/tree/vim4-hdmi-passthrough)。

## 停止时的清理与恢复入口

停止前所有采集已结束，显示测试进程（包括最后PID2089）已正常退出，625秒限时监控已到期；
本轮没有创建板上定时器，自环期间始终未开启音频回送。Mac模式保持进程与运动源进程也已结束。
原RTK EDID及Mac原模式此前已恢复；最后接线仍是OUT→IN。

中断释放了本会话双锁，离线收尾确认原锁进程91336已消失，5.15会话已持有两把锁。
一次非阻塞清理检查因锁忙未执行SSH；此后未访问板子、恢复服务或重启。
中断前最后确认运行的是cf6e238一次性候选，One-KVM暂停、manager974ab40运行；
**中断后的实际运行状态、服务恢复与默认切换由5.15会话负责**。
保留的惰性候选目录在 `/var/lib/vim4-kvm/display-m1/`，本轮数据在
`/var/tmp/hdmi-passthrough-20261024`，临时厂商入口为
`/boot/hdmi-passthrough-vendor-20261024.conf`；未在对方占锁时删除或改动它们。

恢复7.3时从本分支HEAD与本文开始，先确认当前5.15任务状态和锁，再做以下工作：

1. 优先单独评审RX七提交，在正式采集基线上验证One-KVM实际有效帧率/ERROR及编码回归。
2. 对VD1三提交做最终整包构建，一次性启动后验证NV12真实stride/UV offset、60fps地址更新、
   所有行的帧一致性、原退休期及fault pin；现有离线通过不能替代这些硬件检查。
3. 实现并记录单一能力探测ABI；旧内核也枚举NV12，不能仅凭格式判定透传支持。
   当前没有新增能力属性。参考方向为标准DRM属性/IN_FORMATS/PRIME与采集所有者实际EXPBUF组合。
4. 开发tools中的零拷贝参考工具与源变化恢复。每缓冲只EXPBUF一次并共享同一fd/reservation；
   DQBUF后才提交，UV用实际stride×可见高度，不能从带尾部填充的sizeimage反推。
   提交后导出WRITE等待方向的sync_file以等待所有READ退休；OUT_FENCE只证明锁存，不能据此QBUF。
5. 批量完成Mac两档各≥10分钟透传、热插拔、分辨率恢复和独立48k/S16_LE/2ch ALSA路由。
   自环仍禁音频回送。参考工具与One-KVM不能各占一个VDIN队列；下一轮在原生采集者内
   以generation感知的帧租约分发编码/显示，管理器只控制该所有者。
