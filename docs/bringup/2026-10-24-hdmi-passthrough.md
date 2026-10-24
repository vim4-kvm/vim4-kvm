# 2026-10-24：HDMI 透传第二阶段实现记录

进行中的记录：目标持续采集前置条件通过，**未完成透传交付**。
架构与所有权合同见 [设计文档](../hdmi-passthrough-design.md)；
根因及厂商对照见 [周期量化调查](2026-10-24-hdmi-capture-quantization.md)，
计量器现场及持续采集数据见 [稳定性复测](2026-10-24-hdmi-capture-stability.md)。
保留默认eeddb005与manager974ab40，不合入正式内核、不正式部署。

| 范围 | 当前状态 |
|---|---|
| 采集稳定性 | 真实源/自环1080p60及4K60共四档各约610秒、36601帧，0 ERROR/观测失锁 |
| 无换线一次性启动 | 原生720p回退及保留区首帧接管已实现，68项离线测试通过，完整构建中 |
| VDIN→VD1、60fps、退休/fence | 尚未进入实现，保留原退休期 |
| 能力探测ABI | 尚未定义已实现能力，不以NV12枚举单独宣告支持 |
| 参考验证工具 | 原生V4L2持续采集/ERROR比例/运动标记工具已实现；透传工具待开发 |
| RX→TX音频 | 待验证；自环禁回送 |

## 离线与上板边界

VM `~/src/linux-7.3-hdmi-passthrough` 的 `vim4-hdmi-passthrough` 基于c24465df，
没有切换原内核主工作树。稳定性候选 `41c31fc123935` 包含七个小提交：诊断、完成帧元数据、
正常STREAMOFF误计数、FDET量化和有界TOP计量器重测。68项host fixtures、
七提交strict checkpatch和Image/DTBs/2339模块构建通过。
主仓新增 [hdmirx-soak.c](../../tools/hdmirx-soak.c)，已登记工具目录；Mac全套243测试通过
（7跳过），Linux故障注入和C严格编译通过。

用户通过need-user/user-done协议确认暂停KVM使用及随后自环接线，回复已归档并删除。
Mac双锁覆盖当前批量窗口。一次未完成暂存即重启的无效尝试已如实保留，未覆盖默认文件；
后续只有stage退出0并发布完整目录后才选择候选。
原始证据、构建、源程序、模式快照和保护文件哈希在 `logs/hdmi-passthrough/`。

后续需保持单一采集所有者：独立参考工具占用VDIN时不能同时启动第二个One-KVM采集队列。
正式应用下一轮从同一个捕获帧租约分发显示与编码；管理器不直接创建采集队列。
本条尚未记录最终恢复或验收完成，不能当作可部署结论。

## 自环启动接管（待新候选上板）

保持自环接线，以旧候选一次性启动取得现场：U-Boot无EDID回退720p60 RGB8，
ENC2 totals1649/749、TX active1280×720，OSD fetch仍1920×1080 RGB888、stride5760。
实际frame地址为 `0x3f800000`，原合同只允许另一个boot frame `0x3fdeec00`；
两者均在DT已严格要求的 `0x3f800000+0xc00000` no-map保留区内。
旧候选的显示驱动和TX bridge均按原合同拒绝，仅发布GPU card；这是预期对照，不是新内核崩溃。

`86c2ea484d38d` 仅给原生ENC2且管理OSD SRAM的完整所有者增加已知720p时序，
TX仍对只读固件接管路径保持1080p限制；`cf6e2381164af` 进一步只为该回退配置允许
保留区首帧地址。fetch几何/stride/格式、AFBC、simplefb冲突、外部RDMA及SRAM安全检查保留。
新C测试先在旧实现失败，修复后通过；两个配置的九项fetch/timing扰动、AFBC及
不完整所有权均拒绝。68项host fixtures和两提交strict checkpatch通过，最终完整构建进行中。
不支持任意未经验证的固件布局，不写eMMC启动环境。

串口曾在发送重启前由macOS返回Device error，未改工具代码；用户按文件协议重插Mac端
Sipeed双UART后恢复，随后完成旧候选对照。证据 `selfloop-old-boot-uart-2.log`、
`selfloop-old-boot-registers.json`，仍保持自环等待新候选。
