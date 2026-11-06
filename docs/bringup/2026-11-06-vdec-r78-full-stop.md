# 2026-11-06：r78两次候选冷复位，HEVC全集系列停止

**第1批尚未进入acceptance，两次.36候选分别在7.585144292秒、7.526488209秒冷复位。**
触发协调者明确的整个系列停止条件，不再排第2–8批票。两次正式自然恢复均成功，
最终2372项proof/视频通过，760项归档核验并清理，FIFO1492已释放。没有第三次候选
启动，没有解码结果，不因用户曾批准8窗而继续消耗启动样本。

## 授权与离线编排

沿用[全集计划](2026-11-06-vdec-integration36-full-plan.md)同一.36封包：源码
`943198734a1c803d780af845a49ed04fa2e933d6`，build ID
`355061dc85a2fd695429b501c0c2b87078cf1f89`，RAM SHA256
`ac15a2d07aaa58eb1d1b47d03ac30fb154f696e2aade40a13babea72bcb3fc84`。
本轮批准8批18/18/17/16/18/17/11/17；每批独立FIFO sampling，目标20分钟、上限30分钟，
420秒正式恢复保留。普通像素Fail继续；Timeout/挂死/splat/DMA/IOMMU/恢复异常、
同窗两次候选冷复位或Fail超过半批，立即停止整个系列。本次只开第1批r78。

一次性编排继续调用现有vdec-window、manifest、watchdog、kernel journal cursor及
bounded_process，不另建板端下载或默认执行路径。full_batch.py处理逐流MD5/字节数、
ioctl队列/EOS摘要、失败输出保留、成功输出删除；普通Fail继续，超时及严重故障停止，
下一流前查询节点并核恢复预算。DRC按参考的逐帧尺寸分割，不能用固定首帧大小。

排票前实际离线检查及原始输出保存在build/hwdecode-parity/hevc-full/：

- check-batch.log：真实r77 capture成功/像素错/退出错误/无帧超时判定、HM六尺寸分帧、
  恰好半批与超过半批边界、真实子进程超时终止，以及编排层像素Fail继续/Timeout不启动下一流。
- 初次检查暴露`IOMMU: Default domain type`被子串fault误判；改为词边界后真实r77
  kernel.log全部通过，保留check-batch-before-boundaries.log。不是内核缺陷或驱动mock测试。
- check-retry.log：36组实际谓词的次数/阶段/冷复位/预算边界；最多两次boot，acceptance
  位于重试循环外。批次630秒时要求剩余≥1590秒，恢复/暂存后再核预算。
- run78/ioctl-replay.log：r72拒绝、r73/r75通过，截断/孤立resume拒绝、r71 ERROR仍停。
  run78/window-offline.log及browser-smoke.log确认默认离线和私有浏览器依赖。

包与18条输入在宿主及板端重新核SHA，protected_files与baseline逐项相等。
入场uptime2232.89→2241.73秒，boot_id保持e6de86b5-ec56-4b65-8622-84881a644786，
连续UART观察8.947秒无复位，正式proof/视频/空间门禁通过。上述离线通过不能替代
本轮未执行的全集适配实板验证；板上只验证到早期重试与恢复路径。

## 启动时间线与重试边界

| 启动 | Linux起点monotonic_ns | 后续ROM monotonic_ns | Linux→ROM | 末条内核日志/性质 |
|---|---:|---:|---:|---|
| .36 attempt 1 | 706121485215541 | 706129070359833 | 7.585144292秒 | `[6.378357] zram: Added device: zram5`；冷复位 |
| 正式自然恢复1 | 706139328396541 | 706178506610416 | 39.178213875秒 | `[38.753036] watchdog: watchdog0: watchdog did not stop!`；已核proof后请求第二次候选，非冷复位 |
| .36 attempt 2 | 706182462291291 | 706189988779500 | 7.526488209秒 | `[5.620310] Bluetooth: hci0: BCM4362A2 'brcm/BCM4362A2.hcd' Patch`；冷复位 |
| 正式自然恢复2 | 706200417433000 | 无 | 无 | `[4.847112] brcmfmac: brcmf_c_preinit_dcmds: ... FWID 01-e47f9a86`；恢复成功 |

首次错误记录remaining=1646.1486秒，超过1590秒重试门禁；被动恢复正式默认并核
retry-baseline.json后，重新暂存/检查helper与预算才请求attempt 2。第二次错误记录
remaining=1585.1723秒、retry_eligible=false；即使仍有时间也不允许第三次启动。
两次候选均未完成SSH身份核验、无acceptance-start；build ID是包身份，不冒充运行时读回。
UART连续219.069846041秒，版本行局部字节丢失保留原样；正式身份另外由SSH proof确认。

| 路径 | 已覆盖Linux启动/非请求复位 |
|---|---|
| .36 | 6 / 4（r77后4/2，本轮加2/2） |
| 正式fd41fb5 eMMC默认 | ≥41 / 8（r77后≥39/8，本轮加两次自然恢复，无新增冷复位） |
| 正式fd41fb5 RAM对照 | 2 / 1，未变 |
| .28、.31 | 9/2、5/1，未变 |
| .32、.33、.34、.35 | 各1/0，未变 |

正式累计按实际Linux启动计数，第一轮正式启动虽用于过渡重试仍计入分母。
末条日志只是观测边界，不能据此归因zram、Bluetooth或brcmfmac。USB-C同时供电/HID
连接Mac及可能的峰值电流限制仍是未测量假设；没有改PD/MMC/PWM/ADLA或正式默认。

## 全集状态与恢复证明

第1批18条：Success=0、Fail=0、Error=0、Timeout=0、Not run=18；stateless compliance、
全I门禁也未运行。后7批114条Not run，未排票；目标136条的系列汇总为132 Not run、
4 Known unsupported（计划已确认超尺寸，非实板拒绝证据），Not available=0。
11条Main10保持范围外。不把启动冷复位计成某条码流Fail/Timeout，不抹去r77短流成功。
逐批简报为run78/brief.json及hevc-full/series-summary.json，原始包无results目录。

最终正式7.3.1-vim4-20261105、build ID bdbfa439f298e92b5bad092528d11119a974f262，
2372项保护文件与baseline逐项相等，视频推进299帧、59.773fps，丢帧/冻结/丢包无新增。
清理前重传helper，按归属/哈希删除任务固件副本和RAM候选，正式模块未动。
760项上传归档核验后从板删除，complete.restored=true，sampling释放；不再排新票。
本轮无内核构建，保留封包、参考、日志和共享visl，不清理其他worker资产。

## 证据与后续

- `logs/hwdecode-parity-r78/`：UART/chunks、两个attempt-error、retry-baseline、
  passive-recovered、returned-baseline-identity、returned-video、complete。
- `build/hwdecode-parity/run78/`：实际执行脚本、board-upload.tar/清单、输入核验、brief.json/log。
  `build/hwdecode-parity/hevc-full/`：编排源、离线失败路径日志、series-summary.json。
- UART SHA256：`87de1b6620e4c5aa441e6e3522b52bd998a2dd86d5c6b7cdf0cf9c5a1f915adc`。

按协调者新指示，后续仅离线核Wi-Fi/BT配置/加载/上电路径，准备候选启动参数变体，
另交批准；本记录不授权继续全集或重启。提交前主仓库实际607项OK（11项跳过），
原始输出保存在run78/main-tests.log。
