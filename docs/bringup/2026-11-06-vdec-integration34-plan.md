# 2026-11-06：.34 厂商HEVC序列与MPEG-2诊断计划

本轮只离线准备，**未排板票、未部署**。申请一张FIFO sampling票，目标15分钟、
上限30分钟、一次候选启动；完成封包与计划后交协调者批准。正式默认仍为
7.3.1-vim4-20261105（fd41fb5），不改默认启动项。

## 来源与验证

独立工作树`/home/deepdream/src/linux-7.3-vdec-integration34`从
5dd4f646bcd8af7b9749bf1396c2a9a2ebf04e5f依次no-ff合入：

1. quiet-power `efe8d3689a77ec36a3d02556bb6601cb9a22acef`。
2. HEVC vendor-port最终尖`2a622cf6204e6c3f67678cadcc6dbe5c58a074f4`（厂商序列f21dfc47之上补secure MMU swap选择/overlay保存及读回）。
3. MPEG-2 `743d43ff09d195a6121ac2edfdeb8944893b0daa`：在1c711971诊断之上，缺前向参考的B将REF0指向已解析的后向anchor canvas。

最终源码`439af2beb038fbbdfdb0aea9d2866f5c31e372ca`，tree
`b895c97496d1da51c1d50fbe634fa0cb028666f3`，无冲突、无未提交内核草稿。
实际合并顺序为quiet→f21dfc47→1c711971→743d43ff→2a622cf6，最后两项在各次构建
完全退出后才合入。HEVC恢复自动NAL，并按
[vendor-port差异表](2026-11-06-hevc-vendor-port.md)补T7 workspace、输入/启动顺序、
输出寄存器与状态处理；这是一组待硬件验证的修改，不声称是已定位根因的单变量修复。

生产O=复用`/home/deepdream/build/vdec-sequence/kernel`，QEMU复用
`/home/deepdream/build/hwdecode-parity-kunit`；共享visl未动。
按协调者同意，生产W=1 Image/DTB/modules的实际模块编译同时作为分支尖W=1门禁，
不重复另一套全树模块构建；QEMU KUnit独立运行，不能混装其配置下的模块。
生产使用正式kernel.config，含CONFIG_DYNAMIC_DEBUG，不加调试片段。
未改binding/DTS；逐提交sparse/内建/strict系列审查留合入前，本轮不重复。

原始产物、脚本和日志在`build/hwdecode-parity/integration34/`。
初始组合cc3f6a7b的完整构建/封包及QEMU在pre-leading-b/，追加743d43ff后的40d21b38
增量W=1及QEMU在pre-swap/，两次QEMU均29/29。它们不是最终身份，不用于上板；
原O=对象保留以增量重建，不重复全树冷编译，不把中间结果继承到最终尖端。

最终439af2be增量W=1 Image/DTB/modules、外部模块与统一封包完成；日志零warning/error，
实际重编并链接解码模块。初始全树W=1仍有1366条其他目录warning（含kernel-doc），
解码目录零诊断，不能写成全树零警告。最终arm64 QEMU KUnit重新运行29/29通过、
无跳过，原始输出为tip.kunit.log/json及tip.qemu.log；生产完整日志为build34.log。
构建前后cmp确认正式配置不变。

| 最终产物身份 | 值 |
|---|---|
| release | `7.3.1-vim4-20261106.34` |
| GNU build ID | `c56c33dc2abc3d1843012ba8ecb43f18a35bdb12` |
| RAM candidate.tar SHA256 | `ad053ffcc258a86010d567e976148faad5fb90aa1bce669b36482595b4667c33` |
| package manifest SHA256 | `e49495d803c78dce746758ce7210634e4d2c1d58619d67885973c1192ac9a731` |
| config SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA256 | `ac070e75a479638dcf3e54270906b63e73599d17dbe03fce5ac311a36b69cfa4` |
| 生产未压缩aml-vdec-drv.ko SHA256 | `1c65d69ee43a0a0c92b3391ab19d89459eafdf637245f5dc66ab93461ba80da5` |

VM最终包在`/home/deepdream/build/vdec-sequence/bundle34/`。Mac副本与VM原件逐项哈希
一致，artifact-identity.json保存复制源；sources34.toml只锁候选，正式sources.toml未改。
finalize.py已校验完整RAM包、最终源码、manifest/build ID、baseline身份与2372项
protected_files逐项相等；计划使用r72，无旧run路径，video.py实际存在且哈希核对。
baseline沿用r71已恢复验证的正式身份，入场须再实测，不把离线等同当当前板端证明。
资产复用r71、逐项校验16个工具/插件及码流归档；执行草稿默认离线路径通过。
原始输出见copy-artifacts.log、offline-validation.log、window-offline.log与
diagnostics-check.log。最终候选未上传、未上板，不能把分支尖通过写成硬件通过。
初始cc3f6a7b中间包核来源和哈希、保留manifest后已清理，明细在
pre-leading-b/retired-package.json；最终bundle34未动。
提交前主仓库全套实际607项检查OK（11项跳过），原始输出为main-tests.log。

## 窗口顺序与预算

入场 → stateless compliance/DOS step=0 → H.264三条 → MPEG-2四条 → HEVC短清单 → 恢复。
软预算为入场上传/启动180秒、compliance90秒、H.26460秒、MPEG-2180秒、HEVC180秒；
恢复/视频/归档420秒绝对保留，690秒为可借用余量。HEVC只在剩余≥3+7分钟时开始。
单条Fluster与HEVC首帧捕获各30秒；既有进程树watchdog与日志游标失败门禁不变。

入场要求uptime≥300秒、连续UART无复位、前后boot_id相同，正式proof、保护文件、
视频和空间门禁通过。先在宿主显式传私有PLAYWRIGHT_MODULE/BROWSERS_PATH完成冒烟。
候选SSH的release、build ID、APPEND和新boot_id须逐项匹配，UART保存启动/复位证据。
冷复位不追加候选启动，最多观察两次自然恢复；恢复失败停下交协调者。

像素Fail留证后继续；Timeout、BUG/WARN/Oops、设备/DMA/停机异常、采证失败或
恢复预算不足立即收尾。HEVC失败只停HEVC并恢复，不改变前面格式结论，不换输入重试。
保护文件由本次baseline.json生成并逐项核对，计划不得引用旧运行目录。

## compliance、H.264与MPEG-2

先关闭aml_vdec.c、aml_vdec_hw.c、h264.c、mpeg12.c、hevc.c的dynamic debug。
stateless media/video带流compliance须通过，增量journal的DOS step必须0，非0停窗。
WARN/ERROR不被过滤，不把生产配置回归当锁/内存调试验收。

H.264使用同一官方parser和私有插件，跑MR3_TANDBERG_B、BA1_FT_C、
cabac_mot_picaff0_full，保留MR3输出/trace；均为r71通过项，不替代全集复验。

MPEG-2顺序sony-ct1、sony-ct2、sony-ct3、mcp10ccett；固定原mpeg2-fixed库，
gst-inspect路径、ldd解析、SHA身份门禁不符就跳过此段。开启mpeg12.c/aml_vdec.c +p，
核对三个拒绝/完成诊断点实际为=p，段后关闭；aml_vdec_hw.c保持关闭。
保留完整ioctl、QBUF/DQBUF、I420/ISO、动态调试状态和增量journal原文。

[r71](2026-11-06-vdec-r71-handshake.md)已证实sony-ct1 ts=1000/2000进入微码完成错误。
新候选依据[完整宏块统计与ISO反事实验证](2026-11-06-mpeg2-r71-leading-b.md)，
只对没有前向预测的B补有效REF0，保留真实后向anchor及错误返回；尚未证明微码接受。
两条Sony分别须有60/24显示帧；ts=1000/2000（ioctl tv_usec=1/2）应REF0=REF1、
完成为PIC_DONE/SEQ_END而非DATA_EMPTY、无PICINFO_ERROR且两队列无ERROR。
ERROR_COUNT照原值记录，期望0，下降不等于通过。
四条全流均按原ISO容差逐帧验证，ct3/mcp必须不回退；单列Sony首两帧各平面首错、
最大差和差值>2的位置，不能因错误帧消失改判整流Success。
sony-ct1帧2起对照r71，sony-ct2对照r70；旧的小像素差可能仍导致Fail。
ERROR或相同DATA_EMPTY即判该候选未解决，不现场试其他参考替换；普通像素Fail
保存后继续既定清单，统一窗口判停不变。错误缓冲的非零内容不当有效像素。

本轮采证改读run_fluster新建的**逐流kernel.log**，不再读results/kernel.log。
已用r71真实日志和ioctl回放：新路径匹配1000/2000，旧路径复现误停；缺失/部分诊断、
无ERROR、损坏时间戳路径也检查。Sony ERROR仍无对应诊断则保存证据、停止MPEG-2段，
后续项记未运行；不得带着静默错误继续猜参考策略。执行过的r71脚本保留原样。

## HEVC自动NAL短清单

遵循[厂商序列上板清单](2026-11-06-hevc-vendor-port.md#t48t3k-单次上板清单)。
只开hevc.c +p，固件/电源预检后使用原hevc-intra.vhdr；首AU5999字节、skip=0、
前缀和参考保持原锁定身份。保留源码/模块/固件/fixture SHA、起始IRQ和有效输入证据。

固件日志预期为`HEVC secure firmware load: format=0x32363553 core=2 swap=1 a0=0`，
并记录非零secure overlay地址，核启动各阶段的swap/imem_dma读回。
若a0非零并走format=17/core=0/swap=0 fallback，保留两次加载日志，照常按f21dfc47
行为执行短清单；不得把fallback算swap验证成功。固件预检后立即保存firmware-load.json，
解码阶段的再次加载及overlay读回仍保存在原始journal；secure monitor不提供活动固件
哈希，磁盘包SHA不能独自证明实际secure代码身份。

预期首次search=0x200008，**不要求09**；期待08/RPM→SOURCE_CHANGE，CAPTURE就绪后
同AU重投，再05→0a/CAPTURE完成。把格式探测和实际解码两遍分开记录；r71的四次09
只证明手动头路径，不作为这次自动模式通过条件。

仅compliance和有效输入/自动NAL证据通过后捕获同一首AU一帧，256×256 I420、
98304字节；保存可见平面、capture日志及整帧/Y/U/V哈希，与原软件参考逐平面比较。
若不等，宿主离线量化最大误差，不提高容差，不扩P/B、10bit、DV或其他流。
compliance失败就不捕获，SOURCE_CHANGE/IRQ数/非零缓冲都不能替代像素通过。

任何timeout、WARN/Oops、非请求复位、ERROR缓冲、错误像素、AXI停机失败即停HEVC。
保存before/after reset、after-start、IRQ/RPM/header-reply/timeout、UART及停机证据，
记录厂商序列下是否越过r71的slice阶段。未知状态不盲ack，不现场改寄存器再试。

## 恢复与交付

按r71/r60流程恢复正式默认，清理helper前检查并在缺失时重传；核2372项保护文件、
完整模块身份和实际视频推进，按owned清单与哈希只清本任务候选/固件。正式模块及
应用数据不动。归档Mac逐项核验后删除板端本轮目录，结束释放票、清本任务O=对象，
保留封包/日志和共享visl。

输出逐流通过/Fail/Timeout/未运行、compliance、原始诊断、IRQ/事件、像素哈希及
恢复proof/视频。记录每次Linux启动和非请求复位间隔；不因短窗口无复位宣称稳定。
当前仅供审核，未授权新板窗。
