# 2026-11-06：.38 HEVC 第二轮一致性修复验收计划

按协调者授权自行排 FIFO sampling，不等待逐窗审批。先验证全 I、短流与14条定向及
12条回归代表，无退步再独立重跑132条；**上一轮118条Success在任何阶段退步均停止
整个系列**。候选行为与未证边界见[第二轮分析](2026-11-06-hevc-conformance-round2.md)，
对照为[.37实测全集](2026-11-06-hevc-integration37-results.md)。不改驱动、固件或参考求过。

## 源码与离线门禁

固定源码 `d177f0dc1ca40a33dadee38f95c08fa332236f69`，直接在已合主线的
`3cbab82167a1dc3de870165a5a01fd7c66d48a86` 后增加四提交：首slice地址推断、
LT跨POC周期匹配、连续CRA/重建参考池的顺序、RPM/DPB诊断。只改HEVC三个文件，
没有内核码流解析器、猜测输出标志位或按码流名特判，不增加私有uAPI。
独立工作树 `/home/deepdream/src/linux-7.3-vdec-integration38`，独立O=
`/home/deepdream/build/vdec-integration38/kernel`，独立QEMU O=同根kunit。
旧正式、.36/.37产物、日志和共享visl不覆盖；只读取.37 build.json作为元数据模板。
生产配置与正式kernel.config逐字节相同，含CONFIG_DYNAMIC_DEBUG；release
`7.3.1-vim4-20261106.38`。生产W=1 Image/DTB/modules及整包实际构建完成，解码目录
零诊断，全树1168条warning与.37规范化路径比较无新增独特文本；不称全树零警告。
独立arm64 QEMU KUnit39/39、无跳过，原始tip.kunit.json/log及tip.qemu.log保存。
heavy1522已释放，配置前后cmp一致；未修改DTS/binding，不重跑无关schema。

| 产物 | 身份 |
|---|---|
| 源码 | `d177f0dc1ca40a33dadee38f95c08fa332236f69` |
| GNU build ID | `e34c889d8c58b34d847bf8ae7fa1f388e59d44af` |
| 原RAM包SHA256 | `c1a3b39c87837e922943f0ff3ae2b63cc3fc54ae421c237b1b1c0297b722cdb8` |
| 无线屏蔽RAM包SHA256 | `b897dfb7e7b967d3c8b198b5228f6789191d5419a6a3aa744654448bd38d6702` |
| package manifest SHA256 | `26b4044e8c1a1abdb883a5483fd83490d7e8dd8dca83c9e3e598d69c9a712841` |

同[.37](2026-11-06-vdec-integration37-plan.md)制作仅候选cmdline变体：
追加brcmfmac/hci_uart/btbcm模块黑名单、mmc_pwrseq_simple_driver_init黑名单和
bluetooth.service mask；正式cmdline及默认项不改、不saveenv。逐文件比较只允许
extlinux.conf及trial.json对应摘要变化，其余2357文件不变。无线阻断采模块/设备/
pwrseq/deferred-probe/服务，不能据此称物理断电。VBUS仍Mac→USB-C功率计→VIM4，
型号待补，本轮不安排供电测量或追加物理操作。

离线工具/输入复用已封存归档，输入上板后再次核完整SHA256与字节数；不下载新流。
官方1.24.2 h265parse在私有目录，v4l2h265dec必须来自系统video4linux2插件；
gst-inspect路径/版本及库摘要为阻断门禁。所有计划的protected_files必须由正式
baseline.json生成且2372项逐项相同，源码/包/配置/build ID也逐项核对。
首窗r92已离线生成，尚未排板票。offline-check.log实际核对14+12顺序、原118条
Success及其CSV摘要、源码/包身份、2372保护清单及不一致时拒绝、工具摘要和默认离线。
真实.37失败捕获回放验证普通Fail继续、旧Success退步停止且后续未运行、外层timeout
停止不重跑；entry-replay验证配置或ExecStart变化在上传前拒绝。主仓库最终离线检查
原始输出为build/hwdecode-parity/integration38/main-tests.log。

## 单次窗口顺序与判据

每窗一张FIFO sampling票，目标20分钟、上限30分钟，只启动候选一次。入场先排空
UART再连续观察；实际uptime至少300秒、boot_id不变、uptime单调，正式proof、视频、
有线地址/SSH/HID及空间都通过。票外等待从最后已验证正式运行身份保守计时，不能
仅用可能残缺的UART单行。服务/配置与已审库存比较，变化先拒绝，不上传后再查。

1. stateless streaming 60/60、media 8/8、DOS step=0；节点/探测、secure swap固件
   加载format/core/a0及非零overlay为阻断门禁。
2. HEVC原全I streaming compliance至少56/56、零失败/警告；原首帧98304字节及三平面
   逐字节一致、Captured 1 frames; status 0，初始SOURCE_CHANGE先于CAPTURE建立，
   只一次CAPTURE STREAMON。以输入摘要与实际像素/事件作证，不为一条调试字符串开RPM。
3. cip_B_NEC_3、MERGE_E_TI_3、TMVP_A_MS_3分别5/8/17帧逐帧/整流MD5、LAST、
   status 0、零ERROR全部通过；任一退步停系列。再跑一轮select+epoll compliance并保留。
4. 定向14条严格按下表；仅此阶段`file hevc.c +p`采完整128个u16的RPM四行及失败DPB。
   每组保存实际dynamic_debug控制状态，离开定向阶段即关。固件加载窄范围诊断独立保留。
5. 原Success代表先WPP_A、DSLICE_A、CAINIT_G、DBLK_A、TILES_B、RPLM_B，再.37的
   DBLK_B、MERGE_E、TMVP_A、ENTP_A、TILES_A、SLIST_A。12项均全判据通过才进入全集。
6. 独立重跑相同132条Main/Main Still 8bit，不用定向结果凑全集数。定向和全集各阶段
   不重跑已尝试项。后续窗记录一次非阻断HEVC compliance，不重复已过全I/三短流。

| 顺序 | 完整码流 |
|---|---|
| 1–6 | SLIST_B_Sony_9、SLIST_D_Sony_9、RPS_D_ericsson_6、RPS_B_qualcomm_5、RPS_E_qualcomm_5、RAP_B_Bossen_2 |
| 7–12 | BUMPING_A_ericsson_1、NoOutPrior_A_Qualcomm_1、NoOutPrior_B_Qualcomm_1、OPFLAG_B_Qualcomm_1、OPFLAG_C_Qualcomm_1、VPSSPSPPS_A_MainConcept_1 |
| 13–14 | LTRPSPS_A_Qualcomm_1、WPP_D_ericsson_MAIN_2 |

每条要求发布者逐帧/整流摘要、精确帧数/字节数、退出0、Captured N frames; status 0、
LAST和零ERROR皆满足才Success，不能仅以“不再-EINVAL”通过。所有实际失败保留I420、
GST/ioctl/逐流kernel.log与拒绝诊断；kernel timeout前来不及写文本时，保留原始journal
JSON/error及宿主事后摘要。初始尺寸/RPM/引用拒绝原样记录，不补固件没报告的字段。

上一轮118条Success清单和其CSV SHA写入计划；像素Fail、接口Error、超时或后续节点
不可用只要涉及其中一条，立即停止后续流、恢复并结束系列。对于原14条失败，普通
像素/返回的接口失败继续；内核或外层Timeout、splat/DMA/IOMMU/挂死先结束当前窗恢复，
下一票从下一条未运行流续跑，不重跑失败。原Known unsupported四条超尺寸8bit仍未执行，
Main10十一条不在本轮范围；不新增unsupported结论。

## 预算、恢复与交付

1800秒内420秒恢复绝对保留，执行另留20秒退出余量。入场/上传/启动按180秒，
stateless90秒，全I/三短流180秒，额外compliance最多120秒；其余810秒给分组和余量。
每组开始前按所有流timeout+5秒之和预留，不能缩短单流timeout凑窗口。定向/代表最多
6条一组；全集沿用八批，足够预算时同窗连续跑。每流通常30秒外层，长流按原锁定
full-plan.json中的逐条放宽值；不现场增加timeout或扩输入。已知WPP_D在全集第8批末尾，
保证E/F先跑完，避免只补两个尾项再启动。每窗入场Data可用少于8GiB停报，不自行删历史。

冷复位记录后被动恢复正式，下一张替代票继续，同一批连续三次复位停止报告。
恢复失败、保护文件不符或视频不恢复停止系列。恢复目标为正式fd41fb5、release
7.3.1-vim4-20261105、build ID bdbfa439f298e92b5bad092528d11119a974f262，2372项proof
及视频推进/无新增掉帧、冻结、丢包；无线恢复也保存。清理前检查并重传helper，只删
本任务且核摘要的固件副本，正式模块不动。上传目录先归档逐项核SHA再清板端，释放票。

最后提交定向14与独立132两张逐流表、12代表、旧Success退步集合、未运行原因、
compliance及复位统计，跑主仓库全套。若因旧Success退步提前结束，明确剩余未运行，
不把停止包装成全集完成。不部署、不合并、不push；锁/内存调试、5.15对照、10bit、
性能/共存与长期稳定性不由本轮证明。
