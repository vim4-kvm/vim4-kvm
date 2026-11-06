# 2026-11-06：.39 解码分层重构行为验收

HEVC独立132条全部完成：**120 Success、10 Error、2 Timeout，未运行0**，
与.38逐项等价。120条逐帧/整流MD5、帧数/字节相同；12条失败保留的I420均逐字节相同，
首错/缺失索引与失败类别不变。其他格式输出及compliance亦与补采.38一致。
客户端合法收尾差异按协调者裁决离线归一化，未改驱动、未重跑求通过。

所有窗口已恢复正式fd41fb5，2372 proof与被动视频通过；本任务一次冷复位发生在
正式恢复启动，.39七次候选启动均无复位。**未部署、未合并、未push**，部署任务仍暂停。
这证明本次重构对照范围，不代表12个既有失败已解决，也不宣称5.15 parity。

## 候选与离线验证

| 项 | 实际值 |
|---|---|
| 源码 | `0ae8beaa56d3a798e8078c5f727c34ed3acafd9c` |
| tree | `50d9610fcec8630bf46064a8c8995a1a5b26c929` |
| release | `7.3.1-vim4-20261106.39` |
| GNU build ID | `76042204fe7ec153b8e42f77372d037b4d065740` |
| 生产配置SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| 无线屏蔽RAM SHA256 | `a204f1b03b3600f4cd507316d3cc2ba4be28699cf6820ab36539cf98dbb9f5e7` |
| manifest SHA256 | `8325346600ba61c70f317bdf5d8da678a063b1fb469c111bfca4bd655c1cd397` |
| 完整组件包SHA256 | `930206b3fe64a9e5d4176e7b94e5c24cc478e164d82f16102a2375d5b94f30f7` |

独立源码`linux-7.3-vdec-integration39`、独立
`O=/home/deepdream/build/vdec-integration39/kernel`；KUnit在同根独立kunit目录。
生产首包直接执行`make … W=1 Image dtbs modules`，实际编译命令留存；
1168条既存告警与.38一致，VDEC零告警、零新增。完整2341个模块（2338基础+3外部）
由统一封包器核身份、BTF/vermagic、清单与depmod。

.config逐字节匹配生产配置；auto.conf解码Kconfig字符串引号后所有有效值相同，
DEBUG_FS/DYNAMIC_DEBUG开启、未混入调试片段。独立arm64 QEMU **KUnit46/46**实际运行。
没有binding/DTS源修改，未另跑不相关schema检查。逐提交构建引用已审系列证据，
不声称本轮重跑逐提交门禁。

manifest、RAM描述和计划均声明`hevc_diagnostic_api=debugfs-v1`；预检实际访问
`/sys/kernel/debug/aml-vdec/fe320000.video-codec/{hevc_test,hevc_core_test}`。
2357个文件与普通RAM包相同，仅extlinux.conf/trial.json因无线参数及诊断声明变化。
每窗核secure swap固件format=0x32363553/core2/swap1/a0=0、非零overlay及DOS step=0。
默认三个bring-up门没有改变，不写modprobe/modules-load配置。

最初宿主可用约17GiB，协调者清理6个已被取代O目录后约35GiB，元数据保留在
`build/_pruned-meta`；未动历史证据、bundle、.38、deploy-hevc及正式fd41fb5包。
本任务未自行删除历史证据，每窗入场均满足8GiB下限。只清本任务可重建对象和
经过归档/哈希核对的板端上传、RAM暂存及固件副本。

## 接口和短回归

基准是[补测于.38同一包](2026-11-06-vdec-integration39-baseline.md)，不借r73/r75当作.38实测。

| 项 | .38补基准 / .39实测 |
|---|---|
| 节点 | video1 stateless、video2 JPEG、video3 HEVC、media0不变；video0仍t7-vdin-test |
| stateless streaming compliance | 60/60，零失败/警告 |
| media compliance | 8/8，零失败/警告 |
| JPEG streaming compliance | 60/60，零失败/警告 |
| HEVC streaming compliance | 56/56，零失败/警告 |
| 全I首帧 | 98304字节及三平面SHA全同，status0、LAST；初始SOURCE_CHANGE先于CAPTURE分配，仅一次CAPTURE STREAMON |
| HEVC cip / MERGE / TMVP短流 | 5/8/17帧逐帧与整流摘要相同，status0、零ERROR |
| H264 MR3 / BA1 / cabac_mot_picaff0_full | 三条Success，完整硬件输出和逐帧摘要全同 |
| MPEG2 sony-ct1/ct2/ct3 / mcp10ccett | 四条实际.out全同；Sony1/2仍为原ISO参考Fluster Fail，另两条Success |
| JPEG420 / no-app /1080p | 各16帧，完整输出和逐帧摘要全同；原IDCT最大误差2、最小PSNR52.188/52.447dB边界通过 |

compliance和首轮门禁在r98已过，后续按裁决不重复计数；r99补其余格式像素。
每窗仍核身份、无线状态、节点、插件/输入SHA、debugfs/固件/DOS与watchdog。
没有修改系统GStreamer库，HEVC为锁定系统video4linux2插件，parser为原官方私有前缀；
MPEG2用原修正库。所有输入宿主校验后上传，板上没有联网下载。

唯一有意的stateless selection变化符合预期：三条H264的video1原始trace中，
.38有27次G_SELECTION/EINVAL；.39为9次G_SELECTION/ENOTTY，随后用户态新增
18次CROPCAP/ENOTTY回退查询。video2/video3各18次G_SELECTION/EINVAL保持不变。
compliance总数没有改变。G_CROP没有单独采集errno，不将其写成独立实测。

## 独立132条与既有失败

[逐流CSV](data/2026-11-06-vdec-integration39-full.csv)包含实际窗口、帧数/字节、首错索引、
整流MD5和原始证据位置；[摘要JSON](data/2026-11-06-vdec-integration39-summary.json)封存身份与总数。
短回归不重复计入132条；每个全集输入只执行一次。

| 保留项 | 类别 | 实际/参考帧数 | 首错/缺失索引 |
|---|---|---:|---:|
| BUMPING_A_ericsson_1 | Error | 49/49 | 4 |
| NoOutPrior_A_Qualcomm_1 | Error | 40/40 | 22 |
| NoOutPrior_B_Qualcomm_1 | Error | 47/47 | 22 |
| OPFLAG_B_Qualcomm_1 | Error | 98/98 | 39 |
| OPFLAG_C_Qualcomm_1 | Error | 96/96 | 20 |
| RAP_B_Bossen_2 | Error | 80/80 | 67 |
| RPS_D_ericsson_6 | Error | 40/68 | 30 |
| SLIST_B_Sony_9 | Error | 0/65 | 0 |
| SLIST_D_Sony_9 | Error | 0/65 | 0 |
| VPSSPSPPS_A_MainConcept_1 | Error | 0/6 | 0 |
| LTRPSPS_A_Qualcomm_1 | Timeout | 0/500 | 0 |
| WPP_D_ericsson_MAIN_2 | Timeout | 0/48 | 0 |

这12条新旧保留I420用`filecmp.cmp(shallow=False)`逐字节核对，12/12一致；
不是拿参考YUV替代驱动输出。两次Timeout后立即收尾恢复，没有在同一次启动继续解码：
LTRPSPS两侧irq0a/status02/shift5f相同，PC采样da5→da1；
WPP_D两侧irq08/status05/pc6d9/shift318相同。超时类别与空输出均不变。
完整journal保留超时消息，不能仅看因异常尚未追加的逐流kernel.log。

## 窗口、停止和裁决

每窗一张FIFO sampling票、上限30分钟、候选最多一次启动，420秒恢复绝对保留。
没有HID/EDID/显示内容操作；密码只走stdin。节点、固件和保护文件门禁没有放宽。

| 窗口 / FIFO | 范围与首次收尾原因 |
|---|---|
| r96 /1583 | .38补基准前工具文件缺项拒绝，零解码；更早1582仅宿主logs父目录缺失，零板端动作 |
| r97 /1585 | .38同包补基准完成，正式恢复时一次冷复位后自然恢复 |
| r98 /1594 | .39接口/全I/cip通过，首次严格DQ计数差异停止 |
| r99 /1599 | 其余格式+全集52条，已知LTRPSPS内核超时收尾 |
| r100 /1605 | MAXBINS两帧正确，空LAST路径的末OUTPUT客户端未DQ而停止 |
| r101 /1606 | 再推进28条，RAP_B旧Error仅末OUTPUT未DQ而停止 |
| r102 /1608 | 再推进6条，RPS_D首错后客户端多发一次成功DECODER_CMD而停止 |
| r103 /1610 | 再推进43条，已知WPP_D内核超时收尾 |
| r104 /1611 | 只补此前未跑WPP_E/F，两条Success |

[裁决及原始顺序](2026-11-06-vdec-integration39-r98-drain.md)说明四次停止的离线重判：
新旧drain代码等价，旧.38已存在数据LAST/空LAST及末OUTPUT未DQ。
Success只对有原始证据的合法尾部归一化；Error只允许有首错交付后证明的客户端收尾差异，
CAPTURE、数据、首错/status、LAST/ERROR和内核错误串仍严格。旧失败转成功仍拒绝。
原始第一次停止及比较结果不改写，没有内核或插件修复，也没有重跑求通过。
最终离线复核133份comparison（含三个短流）及2份内核超时证明均成立。

r103额外留下WPP_E/F是我的编排疏漏：误沿初版顺序，没有落实WPP_D置末要求。
已保留失败计划，在宿主用实际r103计划回放确认新门禁会拒绝；
仅重新排列同一成员即与已执行.38 r95顺序一致，并增加末尾断言。
r104只补两条未跑项，不重试WPP_D。这个额外窗口不记成驱动问题。

## 冷复位、恢复和边界

本任务观察19次Linux启动：.38候选2/0复位、.39候选7/0、正式eMMC恢复10/1。
唯一复位为r97正式在Booting Linux后7.369467秒返回ROM，末条内核日志brcmfmac
固件加载4.901161；随后自然恢复，未触发累计第二次停止条件。
跨任务正式eMMC由至少61/12增加为至少71/13；.38无线变体累计6/0，.39为7/0。
Mac→USB-C功率计→板拓扑未变，没有新供电读数，不据此归因或排除供电。

九个实际板窗的2372 protected_files逐项相等，radio模块/蓝牙设备/网口清单均恢复为入场值，
候选模块挂载和本任务固件/上传清理完成。所有被动4K H265视频统计推进，约59.56–60.75fps，
丢帧/冻结/丢包未增加；仅证明传输/解码推进，不声称改变或验证了源画面运动。

完整原始kernel journal审计除两次既有超时外无新splat/DMA/IOMMU故障。
正常走到后续检查的流还保存node-after、runtime PM suspended和模块引用快照；
首次严格停止的流没有执行到该后续步骤。生产配置没有KASAN/kmemleak，
不将功能结果冒称为完整锁/内存/泄漏审计，也未验证S4或新增格式。

## 原始输出与提交检查

证据保留在本工作树（不入库）：`build/hwdecode-parity/integration39/`的build39.log、
offline-production.json/log、tip.kunit.json/log/qemu.log、artifact-identity、identity、
最终矩阵、failure-bytes.json、final-review.log、final-kernel-audit.json/log；
`baseline38/`保留原冻结值、派生裁决值、.38补基准及12条旧失败输出。
每窗run96–104都有board-upload.tar、逐项SHA清单及archive；logs对应目录有连续
uart.raw/uart-chunks.jsonl、实际身份、恢复proof/radio/视频。

仓库提交门禁执行`python3 -m unittest discover -s tests -p 'test_*.py'`，
原始输出保存为`build/hwdecode-parity/integration39/main-tests.log`；提交正文记录实际总数/skip。
受跟踪改动仅为计划、补基准、裁决、结果与问题计数；编排位于build并随上板清单归档。
sources.toml、正式默认及解码器三个默认门均未改动。
