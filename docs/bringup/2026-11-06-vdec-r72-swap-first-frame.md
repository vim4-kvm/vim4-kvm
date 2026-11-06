# 2026-11-06：r72 HEVC首帧与MPEG-2起始B修复验证

**HEVC streaming compliance 56/56，首帧逐字节正确，但捕获进程等待EOS失败。**
MPEG-2 sony-ct1/ct2的起始B错误缓冲消失，前两帧对ISO差值均≤2；整流仍Fail，
后续原有像素差异未变。H.264三条与两条MPEG-2对照通过。正式恢复时冷复位一次，
自然恢复成功，2372项保护文件和视频通过。没有部署或追加候选启动。

## 身份与执行

按[.34计划](2026-11-06-vdec-integration34-plan.md)，FIFO1456，一张30分钟sampling票。
源码`439af2beb038fbbdfdb0aea9d2866f5c31e372ca`，release `7.3.1-vim4-20261106.34`，
build ID `c56c33dc2abc3d1843012ba8ecb43f18a35bdb12`；RAM包SHA256
`ad053ffcc258a86010d567e976148faad5fb90aa1bce669b36482595b4667c33`。
HEVC尖2a622cf6、MPEG-2尖743d43ff，完整组成和离线构建证据见计划。
入场uptime2675.23→2684.15秒、boot_id相同，正式proof/视频通过；候选SSH身份匹配。
私有浏览器import冒烟与插件路径/库解析/SHA门禁通过，未替换系统插件。

按最新批准，执行草稿对Fluster Error或DQBUF ERROR立即收尾，普通像素Fail继续。
三条H.264均开ioctl追踪，四条MPEG-2逐流读取自己的kernel.log；入场前用r71真实
ERROR记录离线验证停止路径，并验证干净结果和普通Fail继续，保留error-stop-check.log。
这是build/下本轮编排草稿的调整，没有改仓库工具或内核源码。

## compliance与H.264

stateless media 8项、video带流60项全部通过，零警告，DOS step=0。
MR3_TANDBERG_B、BA1_FT_C、cabac_mot_picaff0_full均Success。
MR3为300帧、11404800字节，与参考逐字节相等，MD5
`dd1091f75ac15d3ae70485295b0a116e`。MR3及四条MPEG-2保存的trace丢事件均0。
本次只是三流回归，不改写r65+r69全集129S/1F/5KU；AVC主线5dd4f646仍未部署。

## MPEG-2：起始B完成正常，整流像素仍Fail

sony-ct1/ct2的timestamp1000/2000均REF0=REF1=00050504，PIC_DONE out=1、errors=0，
info分别00022000/0002f000；两队列均零ERROR。前两显示帧逐平面对ISO最大差≤2，
差值>2字节数均0，证实REF0后向anchor别名修复了这两条流的起始B错误完成。
这不等于整流一致性通过，也不能从本轮推广到所有单向B流。

| 码流 | Fluster | 输出字节/帧数 | 后续像素证据 |
|---|---|---|---|
| sony-ct1 | Fail | 7096320 / 60（352×224） | 显示帧2起与r71逐字节相同，差值>2仍7字节 |
| sony-ct2 | Fail | 12165120 / 24（704×480） | 显示帧2起与r70逐字节相同，差值>2仍2字节 |
| sony-ct3 | Success | 3628800 | 与r70逐字节相同 |
| mcp10ccett | Success | 2488320 | 与r70逐字节相同 |

sony-ct1整文件MD5为`eb29cb43047e76ed236b78a306343687`，sony-ct2为
`85c563f951082107d347c0e66d3423cb`。完整逐帧/逐平面差值与首差位置保存在
summary.json、pixel-evidence.json；本轮2S/2F，不是MPEG-2全集复验。

## HEVC：自动NAL到首帧已通，EOS未通过

实际日志为`HEVC secure firmware load: format=0x32363553 core=2 swap=1 a0=0x0`，
overlay为0x6a2f000，没有fallback。reset前后swap=06a2f000、imem_dma=00000000。
启动后swap读回b72d0000也原样保留，不将跨时刻寄存器读数解释为原子状态。
有效首AU5999字节、skip=0、WAIT初值0、自动search=0x200008，输入证据检查通过。

HEVC streaming compliance **56/56、零警告、退出0**。Linux IRQ从0到135；按journal
__CURSOR去重后，08状态70次、05命令65次、0a状态65次。自动模式没有09；捕获日志
确认SOURCE_CHANGE已取出，08/RPM→SOURCE_CHANGE→05→0a路径实际推进。

compliance通过后才捕获全I首帧：256×256 I420，stride256/128/128，98304字节，
与宿主保存的软件参考`integration32/hevc-first.i420`逐字节相等。

| 范围 | SHA256（输出与参考相同） |
|---|---|
| 整帧 | `45f7799c139bd16f32def71d02a08ec07ee7d248ef8181ac3d1803664f7d3307` |
| Y | `6a2c99651e8c31993a7677d46d493758f6f965322910cc0cfe7b52b33453145c` |
| U | `01c2936975a2e93bdf1ad5d7543c2d2397aa506536b42204b28c13c3cc964c37` |
| V | `e91e2f15ef9b2c43a3c1006558e2ceac70529e70709eac6e33cf4596b7602d88` |

但捕获工具随后等待sample/EOS约5秒失败，报`Capture stopped or timed out at frame 1/1`
和`Captured 1 frames; status 1`。执行草稿因此标记HEVC stopped并恢复，未重试；
复合断言`capture/size failure`不代表尺寸错误。进程整体失败与离线首帧像素正确须分开。
原始ioctl可见DECODER_CMD成功、DQEVENT成功（参数指针未解析）、CAPTURE index0
带KEYFRAME|LAST且无ERROR，随后DQBUF EPIPE；日志约2.169秒开始drain，2.230秒
SOURCE_CHANGE，2.242秒allocator报告last buffer，7.246秒拆管线时才Done draining。
未见内核解码timeout或ERROR缓冲，尚不能归因驱动或用户态EOS处理。
phases.json保留stopped；编排器捕获异常后退出0不表示HEVC段全通过。

本轮没有HEVC标准全集、P/B帧、10bit或5.15有效对照；生产配置不能替代锁/内存调试
验收。HEVC topic未合主线，不宣称完整5.15 parity。

## 恢复、冷复位与证据

连续UART覆盖326.651秒，共三次Linux启动：

| 次序 | 内核/路径 | Linux起点→非请求ROM | 末条内核日志/结果 |
|---|---|---|---|
| 1 | .34 RAM候选 | 无 | `[161.291876] watchdog: watchdog0: watchdog did not stop!`；请求恢复 |
| 2 | 正式fd41fb5 eMMC | 7.333898166秒 | `[4.537418] brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM43752/2 ... FWID 01-e47f9a86` |
| 3 | 正式fd41fb5 eMMC自然恢复 | 无 | `[4.770944] brcmfmac: brcmf_c_process_txcap_blob: no txcap_blob available (err=-2)`；成功 |

候选Linux起点monotonic_ns=690669201625708，请求恢复时间690827083560833，相距
157.881935125秒；正常重启的ROM行残缺，之后已看到正式Linux起点690841171227250，
再于690848505125416冷复位。因此不能把这个ROM归到候选或报告候选179秒冷复位。
自然恢复Linux起点690858928114833；没有额外主动重启。
正式eMMC统计从≥31/6更新为**≥33次/7复位**，正式RAM仍2/1；.34为1/0、.33为1/0、
.32为1/0、.31为5/1、.28为9/2。不据小样本归因或推断稳定性，RESET/VBUS/PD待测。

最终正式release/build ID与baseline一致，2372项保护文件逐项一致。视频推进297帧、
59.374fps，丢帧/冻结/丢包无新增。清理前重传helper，核归属和哈希清固件与RAM候选，
正式模块未动。complete.restored=true；957项归档核哈希后删除板端本轮上传并释放票。
已清本任务O=对象，保留封包/日志，不动共享visl，明细object-cleanup.json。

原始证据在`logs/hwdecode-parity-r72/`和`build/hwdecode-parity/run72/`：
UART/chunks、SSH身份、proof、video、board-upload.tar/清单、archive/results逐流日志、
summary.json、pixel-evidence.json、按cursor去重的hevc-messages.log及一次性分析脚本。
UART SHA256 `566bd6c35200c5dccb36c80fb9ab4a9406e3e3efe8e1561b326ef74e51166751`。
提交前主仓库全套实际运行607项，OK（11项跳过），输出保存在run72/main-tests.log。
