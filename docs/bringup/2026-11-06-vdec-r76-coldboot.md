# 2026-11-06：r76候选及首次正式恢复冷复位

**.36在Linux起点后7.439606458秒冷复位，首次正式自然恢复也在7.555985083秒复位；
第二次正式自然启动成功。** 没有重试候选或主动reboot循环。2372项保护文件与视频通过，
759项归档核验后清理，FIFO1478已释放。所有本轮解码项未运行，不补跑；后续交协调者
与用户决定冷复位测量，不再自行追加启动。

## 批准范围、身份与离线核验

按[.36计划](2026-11-06-vdec-integration36-plan.md)及r76追加授权，单张sampling票，
目标15分钟、上限30分钟、一次候选启动，420秒恢复绝对保留。
省略已在[r75同包验证](2026-11-06-vdec-r75-ioctl-trace.md)的H.264三流与MPEG-2四流；
顺序为stateless compliance/DOS=0、HEVC全I全门禁、三条inter逐帧MD5、恢复。
任何HEVC失败停止后续流；早期冷复位只被动等待正式默认，最多观察两次自然启动。

复用.36，不重建、不更换内核或输入：

| 身份 | 值 |
|---|---|
| 源码 | `943198734a1c803d780af845a49ed04fa2e933d6` |
| release | `7.3.1-vim4-20261106.36` |
| 封包build ID | `355061dc85a2fd695429b501c0c2b87078cf1f89` |
| RAM SHA256 | `ac15a2d07aaa58eb1d1b47d03ac30fb154f696e2aade40a13babea72bcb3fc84` |
| manifest SHA256 | `47e6faf309e33147f7b789ddce490ca44aa3bc44b431fd27744416ebac50fa1b` |

宿主重核包和输入归档SHA，protected_files与baseline逐项相等；生成新run76路径，
没有引用旧运行目录。使用r75修复后的按PID合并unfinished/resumed ioctl解析，实际
run76脚本离线回放r72仍拒绝、r73/r75通过、截断/孤立resume拒绝、r71 ERROR仍停。
私有Playwright/Chromium和receiver Chrome离线冒烟通过。此次未进入采证流程，
**不能称修订解析器已在新板窗完成验收**，离线回放证据仍有效。

入场uptime687.64→696.52秒，boot_id保持086781f4-c9b5-4184-bc4d-9ee5fbaa4789，
连续UART观察8.978秒无复位；正式proof、视频与空间门禁通过。
候选启动前板端重新核三条输入，结果保存在归档hevc-input-checks.json：

| 输入 | 字节 | SHA256 |
|---|---:|---|
| cip_B_NEC_3 | 13228 | `786e5bd6ac5418f1e4950fc9c5251826128b15d94eda29679b72a4f79d8a77f7` |
| MERGE_E_TI_3 | 15971 | `e5f1f706176e91b72d13686b8864fe1c8e8be764faa417e3cabbf0df1cf78af0` |
| TMVP_A_MS_3 | 17238 | `33556aa42355ba43575a6e6f1b579420a9217f576fc0ae07ee57fa2750a38d52` |

## 实际启动与判停

UART记录.36的Linux版本和匹配模块挂载提示，但候选未完成SSH身份核验和acceptance；
表中的build ID来自封包，不冒充候选运行时读回。执行器停止原因为
`Selected Linux returned to T7 ROM`。归档没有results目录，没有解码输出。
stateless compliance/DOS、HEVC全I及三条inter均Not run；H.264/MPEG-2为授权省略，
仅引用r75历史结果，不增加本轮通过数。

| 启动 | Linux起点monotonic_ns | 后续ROM monotonic_ns | Linux→ROM | 末条内核日志 |
|---|---:|---:|---:|---|
| .36候选 | 701002092045333 | 701009531651791 | 7.439606458秒 | `[5.582817] warning: 'iwconfig' uses wireless extensions ... use nl80211` |
| 正式fd41fb5自然恢复1 | 701019974671125 | 701027530656208 | 7.555985083秒 | `[5.023345] brcmfmac: brcmf_c_preinit_dcmds: ... FWID 01-e47f9a86` |
| 正式fd41fb5自然恢复2 | 701037782020333 | 无 | 无复位，成功 | `[6.211786] brcmfmac: brcmf_c_preinit_dcmds: ... FWID 01-e47f9a86` |

唯一requested-boot事件为.36，monotonic_ns=700994917523250；后两次均为被动自然启动。
连续UART覆盖177.330400875秒，复位前未见panic/Oops；末行仅记录观测位置，不归因
iwconfig、Wi-Fi或解码器。iwconfig弃用提示不是内核WARN splat。恢复轮询中一次manager
尚未active的proof失败随后恢复，不是第三次冷复位；未为此主动reboot。

| 路径 | 已覆盖Linux启动/非请求复位 |
|---|---|
| 正式fd41fb5 eMMC默认 | ≥38 / 8（r75后≥36 / 7，本轮加两启动、一复位） |
| 正式fd41fb5 RAM对照 | 2 / 1，未变 |
| .28 | 9 / 2，未变 |
| .31 | 5 / 1，未变 |
| .32、.33、.34、.35 | 各1 / 0，未变 |
| .36 | 3 / 2（r74、r76复位；r75正常） |

正式包与候选在同窗均早期复位，再次说明非解码系列独有；仍不足以定位硬件/固件/
软件原因。下一步只沿[RESET/VBUS/PD闭环方案](2026-11-05-vdec-reset-measurement-plan.md)
交协调者与用户决定，可能需要物理测量；未排新板窗、不修改PD/MMC/PWM/ADLA。

## 退出证明、清理与证据

恢复正式7.3.1-vim4-20261105、build ID bdbfa439f298e92b5bad092528d11119a974f262，
2372项保护文件与baseline逐项相同。视频推进298帧、59.561fps，丢帧/冻结/丢包无新增。
清理前重传helper，按归属/哈希删除本任务固件副本及RAM候选，正式模块目录未动。
759项归档逐文件核验后删板端run76上传，complete.restored=true，sampling票已释放。
本轮没有构建产生新的O=对象；保留既有封包/日志和共享visl，不清其他worker资产。

- `logs/hwdecode-parity-r76/`：UART/chunks、入场、execution-error、passive-recovered、
  returned-baseline-identity、returned-video、complete。
- `build/hwdecode-parity/run76/`：board-upload.tar与清单、summary.json/log、执行脚本、
  ioctl-replay.json/log、browser-smoke.log；宿主准备日志为同级prepare-run76.log。
- UART SHA256：`a65a458cd061658c6320a68849c0f76dc59e32f415dce942191c92d2d86f5fec`。

提交前主仓库全套实际607项OK（11项跳过），原始输出保存在run76/main-tests.log。
