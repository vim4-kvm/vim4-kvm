# 2026-11-06：.38 HEVC 第二轮修复复测

独立132条已全部执行：**120 Success /10 Error /2 Timeout，零Fail、零未运行**。
较.37新增RPS_B、RPS_E两条通过，原118条Success零回退。定向与全集分别计数。
来源、身份与授权见[.38计划](2026-11-06-vdec-integration38-plan.md)，
对照为[.37独立全集118/132](2026-11-06-hevc-integration37-results.md)。
未部署、未合并、未push，正式默认仍fd41fb5。

## 最终总表

| 阶段 | Success | Fail | Error | Timeout | Not run |
|---|---:|---:|---:|---:|---:|
| .37独立132条 | 118 | 1 | 11 | 2 | 0 |
| .38定向14条 | 2 | 0 | 10 | 2 | 0 |
| .38独立132条 | 120 | 0 | 10 | 2 | 0 |

[独立全集CSV](2026-11-06-hevc-integration38-full.csv)和
[定向CSV](2026-11-06-hevc-integration38-targeted.csv)逐条保存旧判定、新判定、窗口、
期望/实际帧数、首错或首个缺失索引（从0计）、MD5、LAST/status/ERROR及原始证据路径。
四条超尺寸8bit仍Known unsupported未执行，Main10十一条不在本轮范围，132条中没有
Not available。未新增unsupported结论，不宣称5.15 parity或所有失败已修复。

## 身份与方法

源码 `d177f0dc1ca40a33dadee38f95c08fa332236f69`，release
`7.3.1-vim4-20261106.38`，build ID `e34c889d8c58b34d847bf8ae7fa1f388e59d44af`，
无线屏蔽RAM SHA256 `b897dfb7e7b967d3c8b198b5228f6789191d5419a6a3aa744654448bd38d6702`。
独立O=生产W=1、QEMU KUnit39/39及离线门禁见计划，未覆盖旧候选或共享visl。
同一内核/模块/DTB，只修改候选三项无线屏蔽启动参数；正式cmdline与默认项未改。
VBUS仍Mac→用户USB-C功率计→VIM4，型号未补，本轮没有新增功率读数或物理测量。

复用已封存JCT-VC-HEVC_V1输入与发布者参考，无新增下载。官方1.24.2 h265parse
私有前缀，系统video4linux2提供v4l2h265dec，每窗锁库路径/版本/SHA及输入SHA。
Success要求逐帧/整流MD5、精确帧数/字节数、进程退出0、Captured N frames; status 0、
LAST和零ERROR全满足；Error不能以“不再-EINVAL”通过。定向与全集各阶段不重跑失败。

上一轮118条Success名单和其CSV摘要随计划上板，任何阶段退步都立即停止系列。
完整hevc.c动态调试仅在定向14条开启，逐组保存实际控制状态；全I/短流/代表/全集
关闭RPM大日志，仅保留固件加载窄范围诊断。初始全I用锁定输入、精确像素及事件证明，
不依赖debug字符串。420秒恢复绝对保留，内核timeout先恢复，再从下一未运行项续跑。

## 窗口与门禁

| 窗口 | FIFO | 已完成及停止点 | 正式恢复 |
|---|---:|---|---|
| r92 | 1524 | 全I、三短流、额外compliance通过；定向13条2S/10E/1T，LTRPSPS_A超时，WPP_D及12代表未运行 | 正式前两次启动冷复位，第三次自然启动成功；2372 proof、59.565 fps；1028文件归档核SHA后清板端 |
| r93 | 1525 | HEVC compliance56/56；WPP_D仍内核timeout，定向14条收齐2S/10E/2T，12代表未运行 | 正式一次正常恢复；2372 proof、59.755 fps；820文件归档核SHA后清板端 |
| r94 | 1526 | 12代表全部Success，独立全集52条50S/1E/1T；LTRPSPS_A超时后停止，旧Success无回退 | 正式一次正常恢复；2372 proof、60.361 fps；1585文件归档核SHA后清板端 |
| r95 | 1528 | 补齐独立80条70S/9E/1T，最后WPP_D超时后收尾；全集120S/10E/2T | 正式一次正常恢复；2372 proof、59.753 fps；1787文件归档核SHA后清板端 |

r92 stateless streaming60/60、media8/8、DOS step=0；HEVC全I compliance56/56、
原首帧98304字节及三平面精确、status0、SOURCE_CHANGE先于CAPTURE、仅一次STREAMON。
cip_B_NEC_3、MERGE_E_TI_3、TMVP_A_MS_3各5/8/17帧逐帧/整流、LAST和status0通过，
额外一轮select+epoll也56/56。此后按批准顺序采14条；没有先改寄存器或替换参考。
加上r93/r94/r95，本候选HEVC streaming compliance共5次，均56/56；四窗stateless
均60/60、media均8/8、DOS step均0。旧epoll错误未复现，不据此宣称全部竞态已消除。

## 定向的实际收益与剩余证据

r92的RPS_B、RPS_E各300帧逐帧/整流摘要全同、status0、LAST与零ERROR，定向转Success。
SLIST_B/D、RPS_D、RAP_B、五条输出标志/bumping及VPSSPSPPS仍Error，LTRPSPS_A与WPP_D仍Timeout。
12条原Success代表已在r94全部通过，此后才在同一启动及原预算内进入独立132条。
独立全集在r94+r95补齐132条，RPS_B/E各300帧精确及完整EOS/接口判据再次通过；
两个阶段结果一致。两条的收益来自同一四提交候选，不拆成未经单变量验证的逐提交收益。

新诊断实际排除了一些先前猜测：

- SLIST_B/D的首slice flag=1、addr=0；crop分别为`1:1/24576/0/120`和
  `1:1/57344/0/120`，因此首slice原地址不是这次现场拒绝原因；完整RPM保留。
- RPS_D输出40/68帧、首错或首个缺失索引30（从0计），不再停在旧POC260处，但
  在POC847/type1/refs2/0拒绝，RPS开头`aa 60 aa 60 4b 40 00 80`；不能算已修复。
- RAP_B现有80/80帧，仍从显示索引67不一致且捕获/EOS判据失败；不以帧数够就通过。
- BUMPING、NoOutPrior_A/B、OPFLAG_B/C首错仍为4/22/22/39/20；VPSSPSPPS仍0/6帧。

audit-rpm.py实际核对所有已采RPM读取均为四行`00/20/40/60`、每行64字节，即128个u16完整。
r92各流读取数依次为1、1、46、301、301、93、60、50、51、101、101、1；
LTRPSPS_A当前AU尚无08，所以0次RPM不是日志缺失。Error停止时只记录实际已解析部分，
不把RPM读取数当显示帧数，也不承诺输出错误后的未解析尾部。原始kernel.log、journal
JSON/error和rpm-audit.json/log保留；未猜输出标志ABI或宣告固件/硬件不支持。
r93的WPP_D补采5次RPM读取共20行，全部完整；两个阶段不变更输入或超时值。
全集阶段完全关闭RPM大日志，剩余失败集合与定向相同，12条各阶段原始I420均留存，
包括两个超时的空文件。不能将RPS_D多出部分帧或RAP_B达到80帧算作Success。

## 复位、恢复及边界

r92候选正常进入acceptance，无候选冷复位；请求恢复正式后，正式前两次Linux启动
分别在7.382813秒、7.289075秒回T7 ROM，随后被动第三次启动成功。没有主动追加reboot，
没有在同票重启候选。UART连续保存，正式2372项和视频最终通过，不能据此归因供电。
入场前正式boot_id与.37 r91结束时相同，离线构建间没有观测到新的启动。
r93候选和正式均正常，无新冷复位；完整UART摘要
`83c5b89f125ae51baded879d2553d609486f0c74406e3e60a94a4fdf3e8d8747`保留。
r94候选与正式也均正常；实际回归/全集的hevc动态调试站点15处均关闭，已完成
kernel.log未见RPM大日志，debug-scope.log及每组控制快照保留。
r95候选与正式同样正常。本轮候选4次Linux启动/0冷复位；正式恢复6次/2冷复位，
均在r92（两次失败后自然成功）。从.37后的正式≥55/10追加为≥61/12；.37候选5/1、
.36原变体6/4和无线屏蔽变体7/0保留独立口径。各窗间boot_id与上窗恢复值相同，
没有额外观测启动。没有功率/RESET/VBUS同步测量，不据小样本和无线屏蔽推断根因。

每次自然恢复后在票外从已验证的正式运行身份保守等待，再按实际uptime≥300及
boot_id连续性入场。Mac Data少于8GiB停报，本轮未自行删历史证据。清理前重传helper，
只按归属和SHA清本任务固件/候选，正式模块目录不动；上传先归档逐文件核摘要再删板端。

## 证据与交付

产物/构建日志build/hwdecode-parity/integration38/；编排与汇总hevc38/；逐窗runNN/
archive/results及logs/hwdecode-parity-rNN/，均在build/hwdecode-parity下（logs在仓库根）。
r92 UART SHA256 `4d323f2856af4299d685ee6ee2ada2156617d048ebf78ddf746af63d89312666`。
verify-final.py实际核对132项唯一覆盖、120条逐帧/整流摘要及接口状态、12条失败原始
I420与归档清单摘要、12代表和零旧Success退步；四窗正式proof/视频、无线恢复/阻断、
DOS=0均通过。实际控制快照证明定向组15处hevc调试站点全部开启，其余组全部关闭；
13条实际产生RPM的定向流每次读取均完整128个u16，LTRPSPS_A无08明确未产生RPM。
verification.json/log、rpm-audit.json/log保留输出，主仓库最终测试日志为
build/hwdecode-parity/hevc38/final-main-tests.log。r95 UART SHA256为
`b47dc481b018d538b5a721e1e56eea3e84092357d64ba8bbe60c6c42dc703620`。
所有票已释放，上传逐文件核SHA归档后清理板端，最终Data约32GiB；本轮未自行删历史。
正式sources.toml仍fd41fb5。本worker未改驱动/固件、未部署、未合并、未push、不saveenv。
生产配置窗口不证明锁/内存调试检查、5.15有效对照、10bit、超尺寸、性能/共存或长期稳定性。
