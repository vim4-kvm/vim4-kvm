# 2026-10-24：HDMI 透传第二阶段实现记录

进行中的记录：前置稳定性尚未全部通过，**未完成透传交付**。
架构与所有权合同见 [设计文档](../hdmi-passthrough-design.md)，
根因、短测、厂商对照及候选证据见 [采集周期量化调查](2026-10-24-hdmi-capture-quantization.md)。
保留默认eeddb005与manager974ab40，不合入正式内核、不正式部署。

| 范围 | 当前状态 |
|---|---|
| 采集稳定性 | 已修复FDET量化拒帧；长测另现TOP meter暂不可用，有限重测候选待上板 |
| 无换线一次性启动 | 源码检查完成；仍需安全支持U-Boot自环720p回退 |
| VDIN→VD1、60fps、退休/fence | 尚未进入实现，保留原退休期 |
| 能力探测ABI | 尚未定义已实现能力，不以NV12枚举单独宣告支持 |
| 参考验证工具 | 原生V4L2持续采集/ERROR比例/运动标记工具已实现；透传工具待开发 |
| RX→TX音频 | 待验证；自环禁回送 |

## 离线与上板边界

VM `~/src/linux-7.3-hdmi-passthrough` 的 `vim4-hdmi-passthrough` 基于c24465df，
没有切换原内核主工作树。`03cabbd5cd714` 包含诊断、完成帧元数据、
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

## FDET修复后的长测与计量器重测

真实Mac mini 4K60、SDR/444/8bit、同一运动源，`03cabbd5cd714` 严格采集在
315.679115秒遇到首个ERROR后停止：18941个完成帧、18940有效、1 ERROR，
出队59.997634fps、有效59.994466fps、ERROR率0.0052796%。全部三处标记一致，
含该ERROR帧；19次源帧号重复，不能称为每帧均为新源内容。
IRQ frame-done→DQBUF：p50 0.121ms、p95 0.166ms、p99 0.185ms、最大1.325ms；
它仅为软件取帧时间，不是透传或光学延迟。

本次拒绝原因为 `tmds-measurement error=-11`，不是FDET差异：
cable=`0x8000c5ff`、HDMI meter=`0x000317fc`（计数保留、VALID清零），
PLL/SQO/alignment均1，RX ready保持1、stream_stops=0、VDIN faulted=0。
未把采样标记完整扩大为整幅图像已证明无损；该窗口**不通过零ERROR长测门禁**。
原始记录为 `fix-4k-long-1.jsonl`、同名dmesg及 `fix4k-monitor.jsonl`。

后续候选 `131fbdf603eee` 仅在TOP测量暂不可用时，按8192个参考时钟周期等待，
最多两轮后重新检查；24MHz下每轮342–392µs。只接受重新置VALID的匹配时钟，
每轮重新检查5V/alignment/SQO；不接受保留的旧计数，不改变2MHz时钟匹配阈值。
持续无效仍返回EAGAIN；真实失锁仍返回ENOLINK。正常路径不等待，恢复时限频记录轮数。
实际C故障注入覆盖第一/第二轮恢复、持续无效及等待期间失锁；68项host fixtures与
strict checkpatch通过，完整候选构建中，尚未取得该修复的上板结果。

两窗口候选build ID `40c03d84ae2210909c7ab458748c429928955c76` 上板后，
实际多次取得第一/第二轮有效测量，但严格4K长测仍在151.189963秒停止：
9072个完成、9071有效、1 ERROR，ERROR帧标记完整；没有失锁、stream_stops或fault。
这表明两个窗口的边界不足，不能以短测或个别重测成功宣布修复。

随后进行180秒**诊断采样**：`/dev/mem`只读映射已核对的RX TOP页，仅轮询
METER_CABLE_STAT/METER_HDMI_STAT及5V/SQO/alignment，不写寄存器、不复位meter。
同时持续采集以避免空闲link worker的周期重装干扰。1547722次采样捕获936个
VALID低脉冲：观测长度p50 715.720µs、p90 1063.184µs、p99 1082.726µs、
最大1101.935µs；采样粒度及调度会影响边界，不能当作精确硬件脉宽。
所有低脉冲的5V/SQO/alignment正常，HDMI原始计数仅 `0x317fc/0x317fe`，
恢复VALID后为 `0x317fc/0x317fd`。未确认硬件VALID内部判稳算法，不推测其精确语义。
本段同步11101帧、185.006075秒、59.998030fps、0 ERROR/坏标记，9次重复；
它带高频寄存器观察且不足10分钟，不是验收窗口，也不能覆盖前一段失败。

`41c31fc123935` 据实际观测将有限等待扩为四个meter窗口：三个覆盖已测低脉冲，
一个覆盖采样相位；24MHz时最多约1.37–1.57ms。保留新VALID、2MHz匹配阈值、
每轮物理检查及超时拒绝，未调整PHY或硬件meas_tolerance。
实际C测试覆盖四个允许恢复点和第五窗口超时；68项host fixtures和strict checkpatch通过。
完整构建进行中，真实源/自环长测仍待通过。原始证据 `meter-observe*`、`fix2-4k-long*`。
