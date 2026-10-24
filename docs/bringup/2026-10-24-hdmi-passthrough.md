# 2026-10-24：HDMI 透传第二阶段实现记录

进行中的记录：前置稳定性尚未全部通过，**未完成透传交付**。
架构与所有权合同见 [设计文档](../hdmi-passthrough-design.md)，
根因、短测、厂商对照及候选证据见 [采集周期量化调查](2026-10-24-hdmi-capture-quantization.md)。
保留默认eeddb005与manager974ab40，不合入正式内核、不正式部署。

| 范围 | 当前状态 |
|---|---|
| 采集稳定性 | 已定位一类伪ERROR并构建修复；真实源/自环长测待完成 |
| 无换线一次性启动 | 源码检查完成；仍需安全支持U-Boot自环720p回退 |
| VDIN→VD1、60fps、退休/fence | 尚未进入实现，保留原退休期 |
| 能力探测ABI | 尚未定义已实现能力，不以NV12枚举单独宣告支持 |
| 参考验证工具 | 原生V4L2持续采集/ERROR比例/运动标记工具已实现；透传工具待开发 |
| RX→TX音频 | 待验证；自环禁回送 |

## 离线与上板边界

VM `~/src/linux-7.3-hdmi-passthrough` 的 `vim4-hdmi-passthrough` 基于c24465df，
没有切换原内核主工作树。当前HEAD `03cabbd5cd714`，包含诊断、完成帧元数据、
正常STREAMOFF误计数修复和FDET量化修复；68项host fixtures、strict checkpatch与整套构建通过。
主仓新增 [hdmirx-soak.c](../../tools/hdmirx-soak.c)，已登记工具目录，Mac全套243测试通过
（7跳过），Linux故障注入和C严格编译通过。

用户通过need-user/user-done协议确认暂停KVM使用，已归档回复并删除user-done。
Mac双锁覆盖当前批量窗口。一次未完成暂存即重启的无效尝试已如实保留，未覆盖默认文件；
后续只有stage退出0并发布完整目录后才选择候选。
原始证据、构建、源程序、模式快照和保护文件哈希在 `logs/hdmi-passthrough/`。

后续需保持单一采集所有者：独立参考工具占用VDIN时不能同时启动第二个One-KVM采集队列。
正式应用下一轮从同一个捕获帧租约分发显示与编码；管理器不直接创建采集队列。
本条尚未记录最终恢复或验收完成，不能当作可部署结论。
