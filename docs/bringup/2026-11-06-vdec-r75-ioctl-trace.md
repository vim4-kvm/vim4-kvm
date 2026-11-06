# 2026-11-06：r75全I回归与ioctl采证误停

**.36本轮无冷复位，H.264三条通过，MPEG-2四条实际输出与r73逐字节相同。**
HEVC全I compliance 56/56、首帧逐字节正确且status 0；自动顺序门禁却因strace
拆行误报失败，三条inter流全部未运行。保留原始失败结果，不重试、不把未运行算通过。
正式fd41fb5恢复、2372项proof和视频通过，FIFO1476已释放。

## 身份与入场

沿用[批准的integration36计划](2026-11-06-vdec-integration36-plan.md)，单张sampling票，
上限30分钟、恢复绝对预留420秒，只启动一次候选，没有现场修改参数。
源码`943198734a1c803d780af845a49ed04fa2e933d6`，release `7.3.1-vim4-20261106.36`，
build ID `355061dc85a2fd695429b501c0c2b87078cf1f89`，RAM SHA256
`ac15a2d07aaa58eb1d1b47d03ac30fb154f696e2aade40a13babea72bcb3fc84`，manifest SHA256
`47e6faf309e33147f7b789ddce490ca44aa3bc44b431fd27744416ebac50fa1b`。
与r74同包，入场前重核包/归档输入，三条inter输入在板端重新核SHA256与CSV一致，
原始hevc-input-checks.json已归档。这次SSH逐项核对候选release/build ID/cmdline和新boot_id通过。

正式入场uptime398.61→407.34秒，boot_id保持f05970e7-b62c-427e-8032-3e1ce32e0f62，
连续UART观察8.836秒无复位；proof/视频和私有浏览器依赖冒烟通过。没有再次等待五分钟。

## 解码结果与边界

| 项目 | 本轮结果 |
|---|---|
| stateless compliance | media 8/8、video 60/60，零错误/警告；DOS step=0 |
| H.264 | MR3_TANDBERG_B、BA1_FT_C、cabac_mot_picaff0_full均Success |
| MPEG-2 | sony-ct1/ct2仍为像素Fail，sony-ct3/mcp10ccett为Success；四条实际`.out`均与r73逐字节相同 |
| HEVC全I | compliance 56/56、零警告；98304字节首帧与参考逐字节相同；Captured 1 frames; status 0 |
| HEVC inter | cip_B_NEC_3、MERGE_E_TI_3、TMVP_A_MS_3全部Not run，原因是下述采证误停 |

H.264/MPEG-2/HEVC本轮八份ioctl日志经拆行合并检查，OUTPUT/CAPTURE均零ERROR缓冲。
MR3与四条MPEG-2的trace丢事件数均为0。MR3输出11404800字节、300帧，MD5
`dd1091f75ac15d3ae70485295b0a116e`与参考一致。本轮不是H.264全集重跑。

| MPEG-2实际输出 | 字节数 | 与r73实际输出 |
|---|---:|---|
| sony-ct1 | 7096320 | 相同 |
| sony-ct2 | 12165120 | 相同 |
| sony-ct3 | 3628800 | 相同 |
| mcp10ccett | 2488320 | 相同 |

比较对象是驱动`.out`，不是`_ref.yuv`。ct1/ct2超过±2的分量差仍分别7/2个，
既有像素限制未消除，不能将“回归输出相同”写成ISO参考一致性通过。

HEVC ENUM_FMT含COMPRESSED|DYN_RESOLUTION，首帧SHA256为
`45f7799c139bd16f32def71d02a08ec07ee7d248ef8181ac3d1803664f7d3307`；逐平面SHA256：

- Y：`6a2c99651e8c31993a7677d46d493758f6f965322910cc0cfe7b52b33453145c`
- U：`01c2936975a2e93bdf1ad5d7543c2d2397aa506536b42204b28c13c3cc964c37`
- V：`e91e2f15ef9b2c43a3c1006558e2ceac70529e70709eac6e33cf4596b7602d88`

参考仍为integration32/hevc-first.i420。GST日志记录等待/取出初始SOURCE_CHANGE、
Done draining及最终status 0；内核去重后08×70、0a×65、05命令×65。
这些证据支持DBLK_CFGB改动后的本条全I回归，不能外推到尚未运行的P/B像素或EOS。

## strace拆行误停与离线回放

原始phases.json将hevc.all_i记为Failed，停止原因为
`Initial event not consumed before CAPTURE setup, or CAPTURE restarted`。
原始结果不改写；实际hevc-first-debug-ioctl.log中：

| 原始行号 | 事件 |
|---:|---|
| 134 | PID2783 DQEVENT开始，`<unfinished ...>` |
| 135 | PID2782 DECODER_CMD开始，`<unfinished ...>` |
| 136 | PID2783 ioctl resumed，返回0，DQEVENT完成 |
| 137 | PID2782 ioctl resumed，返回0 |
| 169 | 第一次非零CAPTURE REQBUFS |
| 186 | 唯一CAPTURE STREAMON |

旧解析要求DQEVENT与` = 0`在同一行，得到空事件列表；真实完成顺序136<169<186，
初始事件先于CAPTURE建立，没有重建CAPTURE。误停属于宿主一次性编排脚本解析缺陷，
不是此次驱动EOS回归。按判停规则未继续三条inter，也未现场修脚本补跑。

离线仅修build/hwdecode-parity/integration36模板：按PID配对unfinished/resumed，保留完成行的位置，
拒绝孤立resume、重叠pending及截断未完成调用；队列ERROR检查也使用完整调用。
实际执行的run75/window.py、remote.py和原始日志保留不变，旧模板另存。
回放真实捕获：r72仍拒绝（事件186晚于首次分配166，且STREAMON两次），
r73通过（135<167<184），r75通过（136<169<186）；截断/孤立resume拒绝，
r71 Sony ERROR仍停。输出见run75/ioctl-replay.json、ioctl-replay.log、buffer-check.log。
这是宿主采证逻辑回放，不是新增内核Python/mock测试，也不代表修订模板已重新上板。

## 启动统计与恢复

UART覆盖309.128453042秒，本轮没有非请求冷复位。

| 启动 | Linux起点monotonic_ns | 后续ROM | Linux→ROM/性质 |
|---|---:|---:|---|
| .36 | 700026303428333 | 700180243261791 | 153.939833458秒，执行器请求的正常恢复reboot，不计冷复位 |
| 正式fd41fb5 | 700190500385166 | 无 | 正常恢复，无后续复位 |

候选末条内核日志为`[152.518277] watchdog: watchdog0: watchdog did not stop!`，
处于请求reboot收尾。正式末条为`[5.893756] brcmfmac: brcmf_c_preinit_dcmds: ... FWID 01-e47f9a86`。
正式eMMC累计≥36次/7非请求复位，正式RAM仍2/1；.36累计2/1（r74复位，r75未复位）。
.28为9/2、.31为5/1、.32/.33/.34/.35各1/0，均未变，不据小样本判断稳定性。

恢复正式release 7.3.1-vim4-20261105、build ID bdbfa439f298e92b5bad092528d11119a974f262，
2372项保护文件与baseline逐项相同；视频推进298帧、59.565fps，丢帧/冻结/丢包无新增。
清理前重传helper，按归属和哈希删除任务固件副本及RAM候选，正式模块未动。
962项归档核对后删除本轮板端上传，complete.restored=true，sampling票已释放。
本任务O=对象清理后为0，封包、日志和共享visl保留。未部署，不自行追加窗口。

## 原始证据

- `logs/hwdecode-parity-r75/`：UART/chunks、身份/proof、视频和complete。
- `build/hwdecode-parity/run75/`：board-upload.tar、逐文件清单、archive/results、
  hevc-input-checks.json、summary/pixel-evidence、ioctl-replay、执行脚本和object-cleanup。
- UART SHA256：`13d45c2c22c5dd81301e200995a5965d53996c6abe13824f56ca87f92793dbec`。

提交前主仓库全套实际607项OK（11项跳过），原始输出见run75/main-tests.log；
一次性模板的真实日志回放单独保存如上。
