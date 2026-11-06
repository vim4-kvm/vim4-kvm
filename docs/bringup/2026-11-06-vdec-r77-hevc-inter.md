# 2026-11-06：r77 HEVC三条P/B短流逐帧通过

**.36的全I门禁和三条HEVC inter短流全部通过。** cip_B_NEC_3、MERGE_E_TI_3、
TMVP_A_MS_3分别5/8/17帧，共30帧MD5与锁定参考逐帧一致，总MD5与发布者一致，
全部status 0、CAPTURE LAST、零ERROR。stateless compliance通过、DOS step=0。
本窗只启动一次候选，无冷复位；正式fd41fb5恢复、2372 proof和视频通过，FIFO1480
已释放。没有部署，不把三条短流结论扩大为完整HEVC或5.15 parity。

## 授权、身份与离线准备

沿用[.36计划](2026-11-06-vdec-integration36-plan.md)和r76的HEVC专项清单，H.264三流、
MPEG-2四流已由[r75同包回归](2026-11-06-vdec-r75-ioctl-trace.md)覆盖，本窗授权省略。
单张sampling票，目标20分钟、上限30分钟，420秒恢复绝对保留。
新授权仅允许候选在acceptance前、任何解码执行前冷复位且预算充足时再启动一次，
候选最多两次；acceptance之后或解码中失败不重试。本次未触发该条件。

新增背景来自用户：板子唯一USB-C口同时供电和HID，连接Mac；疑似Mac口供电上限，
**尚未测量，不作为复位归因或已证实限制**。本轮没有修改供电/PD或进行物理测量。

| 身份 | 值 |
|---|---|
| 源码 | `943198734a1c803d780af845a49ed04fa2e933d6` |
| release | `7.3.1-vim4-20261106.36` |
| build ID | `355061dc85a2fd695429b501c0c2b87078cf1f89` |
| RAM SHA256 | `ac15a2d07aaa58eb1d1b47d03ac30fb154f696e2aade40a13babea72bcb3fc84` |
| manifest SHA256 | `47e6faf309e33147f7b789ddce490ca44aa3bc44b431fd27744416ebac50fa1b` |

入场前重核原包/归档SHA、输入字节数/SHA和2372项protected_files；板端解包后及逐流
执行前再核输入。三条输入身份与[CSV](2026-11-06-hevc-inter-vectors.csv)相同，输出
参考与[逐帧CSV](2026-11-06-hevc-inter-framemd5.csv)相同，没有新生成样本或替换系统插件。
修复后的ioctl拆行解析回放r72仍拒绝、r73/r75通过，截断/孤立resume和ERROR仍拒绝。

一次性宿主执行器将重试循环限制在boot阶段，acceptance启动在循环外；重试预算保守
取1080秒，包含120秒正式恢复、120秒重新暂存、120秒候选启动、90秒compliance、
180秒HEVC、420秒最终恢复与30秒余量。恢复/重新暂存后再次核剩余预算。
离线36组次数/阶段/冷复位/预算边界检查通过，原始retry-check.json/log保留；
这不是内核mock测试，也不证明冷复位重试路径已实板验证。公共工具默认行为未改。

入场uptime2534.00→2542.90秒，boot_id保持372609e2-d258-4674-852d-44ce05c7d9e1，
连续UART观察9.010秒无复位，正式proof/视频/空间及浏览器依赖冒烟通过。
候选SSH release/build ID/cmdline/新boot_id逐项一致；acceptance-start标记为attempt 1。

## 实际结果

| 项目 | 结果 |
|---|---|
| stateless compliance | media 8/8、video 60/60，零失败/警告 |
| quiet-power | DOS step=0 |
| HEVC全I compliance | 56/56，零失败/警告，退出0 |
| HEVC原首AU | 98304字节，与原参考逐字节相同；Captured 1 frames; status 0 |
| cip_B_NEC_3 | 5/5帧MD5一致，748800字节；Captured 5 frames; status 0 |
| MERGE_E_TI_3 | 8/8帧MD5一致，1198080字节；Captured 8 frames; status 0 |
| TMVP_A_MS_3 | 17/17帧MD5一致，2545920字节；Captured 17 frames; status 0 |
| H.264/MPEG-2 | 按授权省略，不增加本轮通过数 |

全I首帧SHA256为`45f7799c139bd16f32def71d02a08ec07ee7d248ef8181ac3d1803664f7d3307`，
与integration32/hevc-first.i420逐字节比较一致，板端逐平面SHA也通过。
ENUM_FMT为COMPRESSED|DYN_RESOLUTION，原始ioctl完成行：DQEVENT135、CAPTURE
REQBUFS167、唯一STREAMON184。初始SOURCE_CHANGE先于CAPTURE建立，不再误停。

| inter输入 | 总MD5 | DQEVENT / CAPTURE分配 / 唯一STREAMON行号 |
|---|---|---|
| cip_B_NEC_3 | `1315714c7b3f3237b469259f66d9b7aa` | 134 / 167 / 186 |
| MERGE_E_TI_3 | `6e74dbd450123246c22bf01b389bbe11` | 134 / 169 / 200 |
| TMVP_A_MS_3 | `168f8096e56b8a8c1aa03fa5fffdfd23` | 134 / 167 / 198 |

三条都完整输入、未截流、未提前EOS；I420按可见行紧凑导出，不含stride/底部padding。
逐流comparison.json记录零ERROR、LAST=true、退出0、一次SOURCE_CHANGE和一次
CAPTURE STREAMON。宿主从归档capture.i420重新计算全部30帧MD5及总MD5，与计划和
板端比较JSON一致；每条capture.log均有对应帧数/status 0，保存GST/ioctl/内核日志。
每流外层30秒限制和无帧/EOS超时未触发；没有WARN/Oops/BUG/AXI门禁失败。

本轮证明三条8bit短流的P/B重建、显示顺序及EOS，覆盖reorder=0的I/P、reorder=3的
I/B与TMVP/col读取。三条不触发新增MV容量边界，该边界只有既有KUnit证据。
完整HEVC标准全集、10bit、途中DRC、CRA/RASL、长时START/STOP、性能/共存、5.15有效
对照及锁/内存调试仍未验证。不能将短清单通过写成全格式parity或生产部署验收完成。

## 启动时间线与恢复

| 启动 | Linux起点monotonic_ns | 后续ROM | Linux→ROM/性质 |
|---|---:|---:|---|
| .36 attempt 1 | 703682879745583 | 703753401921333 | 70.522175750秒，测试完成后请求的正式恢复reboot，不计冷复位 |
| 正式fd41fb5 | 703763657864125 | 无 | 正常恢复，无非请求复位 |

requested-boot分别为候选703675828483291、正式703749394733458；只有一个候选attempt，
acceptance-start=703697332714750。UART覆盖205.648153375秒。候选末条
`[70.035075] watchdog: watchdog0: watchdog did not stop!`位于请求reboot收尾；
正式末条`[4.733734] brcmfmac: brcmf_c_preinit_dcmds: ... FWID 01-e47f9a86`。
累计正式eMMC默认≥39启动/8非请求复位，正式RAM仍2/1；.36累计4/2，.28为9/2、
.31为5/1、.32/.33/.34/.35各1/0均未变。不据本轮无复位判断供电或系统稳定性。

最终正式release 7.3.1-vim4-20261105、build ID bdbfa439f298e92b5bad092528d11119a974f262，
2372项保护文件与baseline逐项相同；视频推进299帧、59.761fps，丢帧/冻结/丢包无新增。
清理前重传helper，核归属/哈希删除任务固件副本、RAM候选及本轮上传，正式模块未动。
825项归档核验，complete.restored=true，sampling票释放。本轮未构建，无新O=对象，
封包/日志及共享visl保留。不追加板窗、不部署。

## 原始证据与提交检查

- `logs/hwdecode-parity-r77/`：连续UART/chunks、candidate-attempt、acceptance-start、
  SSH身份、入场/退出proof、returned-video和complete。
- `build/hwdecode-parity/run77/`：执行脚本、board-upload.tar与清单、archive/results、
  input checks、summary.json/log、pixel-evidence.json/log、retry-check、ioctl-replay、browser-smoke。
- UART SHA256：`5da76f5af44fe829100021f8eba3f6e110c2da842f23d7f4055bb78d7b176d3e`。

提交前主仓库全套实际607项OK（11项跳过），原始输出保存在run77/main-tests.log。
