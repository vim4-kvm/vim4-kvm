# 2026-11-06：r70 .32 降噪与短回归结果

单次`.32`启动完成stateless compliance、H.264十条和MPEG-2六条。
**DOS step=0，H.264 10/10 Success，MPEG-2 4 Success/2 Fail；HEVC有效输入
compliance仍超时，首帧捕获未运行。**正式恢复、视频和清理完成，无非请求冷复位，
没有部署或追加候选。MPEG-2单向B修复未通过预期硬件判据，不能因KUnit通过而判修复有效。

## 身份、顺序与降噪

FIFO1421，单张30分钟sampling票；入场uptime3865.90秒，采证后3874.73秒，boot_id
一致。按[.32计划](2026-11-06-vdec-integration32-plan.md)，来源
6dd53c32b88975e6f962c65b785581d34e5c223e，release 7.3.1-vim4-20261106.32，build ID
e1a0cd5f0c6d1d166f3c877b52812ccc9ec6fe6a，封包SHA与获批计划相同。
SSH release/build ID/APPEND/新boot_id通过并留事件，UART版本完整。
连续UART时间线397.114秒；候选启动至请求恢复ROM为254.806843917秒，非冷复位。

实际顺序为compliance/降噪 → H.264 → MPEG-2 → HEVC → 正式恢复。
stateless media为8项、video带流为60项，均exit=0、零失败。关闭指定文件dynamic debug
后，compliance阶段增量journal的DOS step行数为0，quiet-power.json已保存；门禁通过。
这证明本次范围内降噪和队列无回退，不代表调试内核锁/内存验收。

## H.264

MR3/4/5和七条对照全部Success。MR三条各11404800字节、300帧，与原宿主参考逐字节
一致；MR3 MD5为`dd1091f75ac15d3ae70485295b0a116e`，MR4/5均为
`5f5f14beca549172487bb74c4d3ba8f9`。没有重跑全集，不改写r65+r69的129S/1F/5KU口径。
三条保存的V4L2 trace无丢事件。

## MPEG-2：参考修复仍未通过

r69 fixed组私有插件路径、ldd解析和SHA门禁通过；四条原通过对照
mcp10ccett、sony-ct3、bits_conf_lep_11、Tek-5.2_conf4仍Success。
sony-ct1/ct2仍是Fluster Fail，输出长度分别为7096320/12165120字节，即60/24帧。
ISO参考与r69逐字节相同，未改变容差。

两条的ioctl均仍显示`tv_sec=0,tv_usec=1/2`的OUTPUT和CAPTURE DQBUF带ERROR。
因此这些缓冲的内容不可信；“不全零”不能当作已成功解码。

| 码流/显示帧 | 是否全零 | 对ISO最大字节差 | 差值>2的字节数 |
|---|---|---:|---:|
| sony-ct1 / 0 | 否 | 232 | 118252 |
| sony-ct1 / 1 | 是 | 226 | 118254 |
| sony-ct2 / 0 | 是 | 230 | 506877 |
| sony-ct2 / 1 | 否 | 222 | 506500 |

两条从显示帧2到末尾均与r69 fixed**逐字节相同**，剩余ISO差值>2的位置仍分别为7/2。
整文件MD5分别为`c9c11f811814a3fe653cdb2f86d17a86`和`17ffb3eb4d16dc90b5a3ef2cb6bd36cb`。
本轮不能证明新的参考选择路径已消除原拒绝；具体失败返回点继续交MPEG-2 worker离线分析。

模块身份不是只看release：prepare_acceptance_decoder先卸载旧模块，modinfo定位到
`.32/kernel/drivers/media/platform/amlogic/vdec/aml-vdec-drv.ko.xz`，按package manifest
校验文件SHA后才modprobe；没有私有模块混装。生产build32.log含mpeg12.o实际重编和
模块链接，源码HEAD仍为获批6dd53c32。保留的生产未压缩模块SHA256为
`8a528fbff2c3c0847393729d92f05dfa8d7e6b9b97d7ed0e24c87ea72a919fa7`。
六条ioctl、QBUF/DQBUF、I420和ISO输出全部归档，trace统计均零丢失。

## HEVC：WAIT_FLAG=0 已实际写入，但仍无首帧

固件预检成功。日志确认有效首AU为5999字节（0x176f），前缀
`00 00 00 01 40 01 0c 01 ff ff 04 08 00 00 03 00`，skip=0，与锁定fixture一致。
compliance在streaming阶段失败；后续首AU像素捕获未运行，不更换输入重试。

| 时点 | WAIT读回 | PC | SHIFT | stream RD | mode_or_nal |
|---|---|---|---|---|---|
| before-reset | 0 | 0 | 0x08 | 0xb72e0400 | 0x80000001 |
| after-reset | 0 | 0 | 0x08 | 0xb72e0400 | 0x80000001 |
| after-start | 1 | 3 | 0x28 | 0xb72e0400 | 0x20 |
| timeout快照 | 1 | 0xa1f | 0x63 | 0xb72e0440 | 0x14 |

紧接快照的摘要再次读PC为0xa1d，两次读数分别保留。reset读回一直0，mailbox mask=1，
timeout IRQ/status=0；HEVC IRQ计数从0到0，没有观察到SOURCE_CHANGE/首帧。
启动后WAIT读回1只按观测记录，不据此单独推断固件内部行为。
后续记录`VDEC power state uncertain; retain lease until system reset`，终检触发timeout，
批次exit=1并正常reboot恢复；不把整窗标为全通过，不尝试再次开启HEVC。
原始寄存器和输入证据位于kernel-journal-0019.jsonl，interrupts前后文件保留。

## 恢复、计数与归档

本窗共两次Linux启动：`.32`一次，正式默认请求恢复一次成功；无非请求冷复位。
正式Linux起点为683176655965416ns。相对r69，正式eMMC已覆盖下界为≥30次/6复位；
`.32`为1次/0复位，`.31`仍5/1、`.28`仍9/2、正式RAM仍2/1，不作稳定性推断。

最终2372项保护文件一致；视频推进301帧、60.165fps，丢帧/冻结/丢包无新增。
helper重传，按归属/哈希清理候选和owned固件，正式模块未动；1020项任务文件
归档Mac逐项核验后删除板端目录，complete记录restored=true，板票释放。
按工作区规则清理本任务生产、模块验证和KUnit O=中的`.o`，保留Image、模块、
封包和日志，未动共享visl环境；数量及字节数见object-cleanup.json。

`logs/hwdecode-parity-r70/`保存UART/chunks、SSH身份、错误与恢复proof/视频。
UART SHA256为`aa9fb6c5d0fdf9e0036dbe12150cd47880ae2248aa4b3c31e0b8c0147fa326c2`。
`build/hwdecode-parity/run70/`保存计划、封包身份、execution.log、board-upload.tar/清单、
archive/results、summary.json与一次性summarize.py。错误缓冲不作为有效像素，
所有未运行项明确保留。本次不改驱动、不新增窗口，结果交两个topic继续离线定位。

提交前主仓库全套离线检查实际运行595项，OK（11项跳过，不计通过）；
原始输出保存于`build/hwdecode-parity/run70/main-tests.log`。
