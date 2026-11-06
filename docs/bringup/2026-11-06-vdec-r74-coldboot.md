# 2026-11-06：r74候选早期冷复位与自然恢复

**.36在Linux起点后7.439730416秒回到T7 ROM，解码清单全部未运行。**
按计划没有重试、追加启动或现场改参数；首次自然启动回正式fd41fb5成功。
2372项保护文件和视频检查通过，759项归档核验后清理板端资产，FIFO1474已释放。
这次不能给HEVC inter像素、EOS或回归结论，也不能仅据一次启动归因新增驱动改动。

## 身份与入场

按[.36计划](2026-11-06-vdec-integration36-plan.md)，单张30分钟sampling票，实际只启动
候选一次。源码`943198734a1c803d780af845a49ed04fa2e933d6`，release
`7.3.1-vim4-20261106.36`，封包build ID `355061dc85a2fd695429b501c0c2b87078cf1f89`，
RAM SHA256 `ac15a2d07aaa58eb1d1b47d03ac30fb154f696e2aade40a13babea72bcb3fc84`。
主线f7b59cb3加HEVC inter三提交8c0cc027，未部署，不改默认启动项。

入场uptime4692.86→4701.75秒，boot_id均e7eb3411-c014-43b9-a780-979a6c0135bf，
连续UART无复位；正式proof、视频、空间门禁通过。私有Playwright/Chromium及receiver
离线冒烟通过。候选包上传校验后由UART看到.36的Linux版本，但**未完成候选SSH身份
核验和acceptance**；不能把包内build ID写成已读到的候选运行时build ID。

候选启动前，三条HEVC完整输入已在板端解包后重新读取并核对CSV的字节数/SHA256：

| 输入 | 字节 | 板端SHA256 |
|---|---:|---|
| cip_B_NEC_3 | 13228 | `786e5bd6ac5418f1e4950fc9c5251826128b15d94eda29679b72a4f79d8a77f7` |
| MERGE_E_TI_3 | 15971 | `e5f1f706176e91b72d13686b8864fe1c8e8be764faa417e3cabbf0df1cf78af0` |
| TMVP_A_MS_3 | 17238 | `33556aa42355ba43575a6e6f1b579420a9217f576fc0ae07ee57fa2750a38d52` |

原始hevc-input-checks.json保存在board-upload.tar根目录。这只证明输入传输正确，
不证明解码正确。stateless compliance/DOS=0、H.264三流、MPEG-2四流对r73输出、
HEVC全I回归和三条inter逐帧MD5 **全部Not run**；归档无results目录，无像素输出，
不存在可计为Pass/Fail的本轮码流结果。

## UART时间线与恢复

连续主机时间戳UART覆盖146.880秒。执行器记录的停止原因为
`Selected Linux returned to T7 ROM`，之后只被动等待正式默认，没有第二次请求启动。

| 启动 | Linux起点monotonic_ns | 后续ROM monotonic_ns | Linux→ROM | 末条内核日志/结果 |
|---|---:|---:|---:|---|
| .36候选 | 699480619577250 | 699488059307666 | 7.439730416秒 | `[5.565178] Bluetooth: hci0: BCM4362A2 'brcm/BCM4362A2.hcd' Patch` |
| 正式fd41fb5自然恢复 | 699498493090000 | 无 | 无 | `[4.753149] brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM43752/2 ... FWID 01-e47f9a86`；成功 |

唯一requested-boot事件为.36，monotonic_ns=699471949303083。复位前未见panic/Oops，
最后一行Bluetooth消息只作为时间线记录，不据此归因蓝牙或固件。候选未完成SSH核验，
没有模块加载/参数快照；不臆测解码模块是否加载或其电源状态。
恢复就绪轮询期间出现一次vim4-manager尚未active的检查失败，随后完整proof通过；
不是第二次冷复位，没有为此主动reboot。

| 路径 | 已覆盖Linux启动/非请求复位 |
|---|---|
| 正式fd41fb5 eMMC默认 | ≥35 / 7（此前r73为≥34 / 7） |
| 正式fd41fb5 RAM对照 | 2 / 1，未变 |
| .28 | 9 / 2，未变 |
| .31 | 5 / 1，未变 |
| .32、.33、.34、.35 | 各1 / 0，未变 |
| .36 | 1 / 1，本轮新增 |

正式内核已有同类早期冷复位证据，见[r72](2026-11-06-vdec-r72-swap-first-frame.md)，
但本次不能靠相似时点排除或确认某个软件原因。后续仍需协调者决定是否重排窗口或
做[RESET/VBUS/PD测量](2026-11-05-vdec-reset-measurement-plan.md)，本轮不追加样本、不改PD。

## 退出证明、清理与原始输出

最终正式release为7.3.1-vim4-20261105，build ID
`bdbfa439f298e92b5bad092528d11119a974f262`，2372项保护文件与baseline逐项一致。
视频推进298帧、59.573fps，丢帧/冻结/丢包无新增。清理前重传helper，核归属/哈希
只删本任务固件副本和RAM候选，正式模块未动。759项归档逐文件核哈希后删除本轮
板端上传，complete.restored=true，释放sampling票。本任务O=对象已清理，封包/日志
和共享visl保留，清理明细在object-cleanup.json。

原始证据位于`logs/hwdecode-parity-r74/`：UART/chunks、入场uptime、停止原因、
passive-recovered/returned-baseline-identity、视频和complete；以及
`build/hwdecode-parity/run74/`：board-upload.tar/逐文件清单、summary.json、summary.log、
执行过的window.py/remote.py与一次性分析脚本。UART SHA256为
`0605e0b02eb4dfc81f5d3ff9a472e1a1487fb0cbd5e9687e15afedbc69890bb6`。
提交前主仓库全套实际607项OK（11项跳过），原始输出为run74/main-tests.log。
