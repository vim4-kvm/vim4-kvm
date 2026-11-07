# 2026-11-07：复用 .42 二进制的正式部署准备

**仅离线包和计划已完成，未部署。** 复用已实测 `.42` 的完整组件归档，Image、DTB和模块不重编；
当前正式默认仍是fd41fb5及已采用的固件PD B状态。部署窗等用户交出Mac约50分钟、协调者再批准。
旧5a9cb11e包及fd41fb5回退整包均保留，没有删除任何历史证据。

## 已核对的封包身份

[身份、逐项核验摘要与空间原始来源](data/2026-11-07-deploy42-preparation.json)为本次机器可读索引。
源码 `3facfaa37284f7193508c2a16fbf5162c6242616`，release `7.3.1-vim4-20261107.2`，
build ID `fa5a9fa53dc3f84802722702f18623730ab81d83`；同[.42实板验收](2026-11-07-vdec-integration42-pd-results.md)。
656129404字节的完整组件包SHA256：
`8fb7c55fce771a1ef076a4aa0014b35c5c76c596b78b09067632965f38842fa8`。

原归档复制前后SHA不变，Mac和VM副本一致；未重新封入不同二进制或为同release制造另一个包。
外层24文件及模块目录2354文件逐项核SHA，2341模块逐个实际运行modinfo/readelf核vermagic、BTF及build ID。
Image、实测DTB和完整模块目录全部与原RAM包trial.json逐项一致，10份运行时文件符合原manifest。
拒绝AppleDouble、包内链接和modprobe/modules-load配置。生产config不变，原.42构建与67/67 KUnit
仅引用原始证据，本轮没有重跑编译或KUnit，不将复制包称为新构建。

仅新建本工作树 `build/deploy-42/` 和VM `/home/deepdream/build/deploy-42`；旧VM输出只读。
原始命令/输出在 `package-verification.log`、`copy-verification.log`、`module-verification.json`。
完整计划交付 `~/.local/state/herdr-workers/deploy-42.plan.md`，不提前改正式sources.toml或发行收据/tag。

## 正式cmdline和只读盘点

从当前Mainline登记项经 `register-runtime.py:mainline_append`生成APPEND，结果与原登记相同；
保留`${eth_mac}`，展开后与当前/proc/cmdline逐字一致。原文见机读摘要及本地
`formal-append.txt` / `formal-cmdline.txt`。只保留`module_blacklist=fusb302`，
无线开启，不带brcmfmac/hci_uart/btbcm黑名单、SDIO initcall屏蔽、bluetooth.service mask或RAM私有init。
不改功耗、CPU策略、应用配置、默认标签和Vendor入口，不saveenv。

只读FIFO1637核当前正式身份、2372保护文件、boot_id、UDC和空间，未上传/安装/重启/发HID或改EDID。
UDC configured，brcmfmac/hci_uart/btbcm在位、Bluetooth active。

| 位置 | 实际可用B | 本次含20%余量需求B |
|---|---:|---:|
| /boot | 104448000 | 69625254 |
| 根分区及/var/tmp（同设备） | 6343634944 | 4133577507 |

启动需求按全部7启动文件及原子替换开销计算，非Image差额；根分区估算含新包/外层解包、
完整新模块/运行时、回退包、解码输入多份暂存及夹具余量。
最终执行器封存资产后和正式入场时均重新计算，空间不足拒绝，不删除旧包/证据。

## 正式PD门禁的实际来源与工具修正

按后续授权再只读采SSH内核/服务和本机loopback curl manager状态，未开启浏览器或控制Mac。
成功观测为FIFO1639，期望源保存在[pd-b-state.json](../../packaging/kernel/pd-b-state.json)，
包含时间及完整原始采证文件SHA。1638首次读状态后仅注销临时会话因Content-Type缺失返回415，
失败输出保留；采集器修正后重采并成功注销该次临时会话，没有改服务或硬件状态。
与先前空间观测boot_id相同，无新增启动。

实际B内核条件：fusb302未加载、无Type-C端口、服务active/exited、Result=success、ExecMainStatus=0，
日志明确bootstrap skipped。ConditionResult=yes：是程序按条件跳过，不伪称systemd unit条件为false。
manager仍返回kernelPD unavailable/contract null，固件当次timedOut/typecFallback、Rp3A、无ioError/hardReset。
依据Overview源码，kernelPD优先导致固件详情被隐藏；这是API及源码推断，未做现场浏览器截图。
协调者明确裁决其为采用B时已有的显示问题、非本次内核回退、不阻断部署；已登记issues另修，
本任务没有修改manager或vim4pd。

`final-manager-check.mjs`改为实际B内核/服务条件及固定接口字段检查，运行时原始板状态和power全对象
保存到manager-pd-state.json。power顶层键集合严格保持，无lastContract等新键，vbusPresent/bootContract=null，
kernelPD保持unavailable/null；固件handoff必须存在且ioError=false、hardReset=false。
U-Boot每次协商的合同/Rp/标志等只存原始证据，不做相等比较，允许获得更好的5V3A固件合同。
真实采证回放、驱动/端口/缺黑名单、unit失败/I²C回退、I/O错误/hardReset/Linux合同及额外历史字段拒绝，
以及更好固件合同通过共5个Node用例实际通过。完整离线617项：600通过、17跳过。
这里只验证检查工具，没有将尚未运行的新包浏览器/管理页验收计为通过。

## 板窗计划与未执行范围

实际读取fd41fb5..3facfaa3的git log --stat：62提交；最终49文件、11298增/2823删。
范围是VDEC四格式/分层/输出修复、共享DOS仲裁、media Kconfig及HEVC DT/binding资源；
共享运行期硬件与电源要求九类回归，不以仅media目录降级。

协调者明确沿用deploy-hevc缩减范围：HDMI只测1080p/4K/无信号，编码H264/H265各4K10秒和600秒真运动；
缺失19档HDMI、9档H264、11档H265夹具记未覆盖，不能称矩阵通过，恢复留后续有Mac时另做。
其余类别、HEVC12代表/compliance和K9不减。

顺序为自然默认启动→九类缩减范围→编码器在位的K9→独立解码冒烟→立即重载编码器及最后CAPTURE DQ门禁。
K9要求三方自然绑定、4K推流时三decoder open均EBUSY、板端Wave5 CAPTURE DQ≥57fps/≥570次每10秒、
零ERROR/丢事件；该段不卸载编码器。之后只在解码段停应用、卸载wave5/t7_jpeg并保留decoder绑定，
完成后普通modprobe重载、按原配置启动应用；最后统计不达标或probe失败/EBUSY即回退fd41fb5。
不加入永久modprobe/所有权切换配置，不沿用已删除的bring-up门或结束时卸载decoder的旧断言。

解码包含H264三流、MPEG2四流、JPEG三样本，对.42实际输出长度/整流/逐帧SHA，保留Sony/JPEG既有参考差异；
HEVC全I56/56及首帧/EOS/事件合同，另[12代表逐项清单](data/2026-11-07-deploy42-hevc-smoke.csv)对发布者参考，
精确帧数/逐帧MD5/status0/LAST/零ERROR，每流30秒。12条原.42实测用时合计67.784秒，仅作预算来源。
正式无线cmdline下的新实测尚未运行，不用既有无线屏蔽窗口代替。

计划为一张50分钟sampling票，测试43分钟截止、420秒回退绝对保留；分阶段预算合计3000秒，
冷复位记录UART/boot_id及Linux起点到ROM时间。任何一次420秒内不能自然恢复即留证据/释放票/报协调者，
不主动循环重启。窗口级错误或剩余预算不足即停止并回退，核当前B状态2372 proof及原视频推进。
未知场景在任何HID/EDID/安装之前正常退出，不执行无关cleanup；helper跨重启缺失时只重传本任务副本。

旧deploy-hevc编排只作为已审方法来源，新身份/执行顺序/正式守卫及最后DQ门禁须在下一阶段按计划适配并
通过离线失败路径后才可入场。本轮不运行旧window.py，不声称新部署执行器已验。
本轮未安装、重启、操作HID/EDID、跑硬件回归、改默认或创建发行tag；所有部署票仍待用户交出Mac与新批准。
