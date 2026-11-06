# 2026-11-06：.39 对照任务的 .38 同包补基准

H.264/MPEG-2/JPEG **补测于 .38 同一包**，不是借 r73/r75 的结果。
r97 完成补采并恢复正式。恢复期间正式内核冷复位一次，随后自然恢复，
2372 proof 与被动 4K 视频通过；本任务累计冷复位 1 次。
本记录不代表 .39 已构建或通过板验。

## 身份与范围

使用原 .38 无线屏蔽 RAM 包，不重编：

- 源码 `d177f0dc1ca40a33dadee38f95c08fa332236f69`。
- release `7.3.1-vim4-20261106.38`；build ID
  `e34c889d8c58b34d847bf8ae7fa1f388e59d44af`。
- RAM SHA256 `b897dfb7e7b967d3c8b198b5228f6789191d5419a6a3aa744654448bd38d6702`。
- 旧适配器提取自 r92 board-upload.tar 并与其清单逐项核验；SHA256
  `8cf59e8c92550cb81509964c0a834d0a8c157a51326a4df84bccbfa2aa3c3ebe`。
- 官方 parser、stateless 私有插件、MPEG-2 修正库和原有限范围 JPEG 参考均沿用封存输入。
  HEVC 插件仍是系统 video4linux2，stateless 是 v4l2codecs；未替换系统库。

本轮不 HID、不切 EDID/显示内容、不部署、不改默认、不 saveenv。
VBUS 拓扑仍为 Mac → 用户 USB-C 功率计 → 板，型号未补，不把功率读数当峰值测量。

## r96：宿主准备缺口拒绝

首张 FIFO 1582 因新工作树没有 logs 父目录在宿主退出，零板端动作。
修正目录创建后，FIFO 1583 使用新目录 run96，原包启动成功，零冷复位。
解码前身份门禁发现继承计划列出的 full_batch.py 没有上传；
compliance_observation.py 同样属于未上传的无用 HEVC 辅助项。
没有跑 compliance 或码流，不能计入格式通过数。

恢复 fd41fb5、2372 proof/视频通过，上传归档核 SHA 后删除。
随后在宿主用实际 tar 成员和直接上传文件重建最终路径→SHA 表，逐项核计划文件；
删除补基准不使用的两个继承要求，回放原 r96 缺项确实在宿主拒绝。
协调者批准新目录续补；没有修改仓库工具或内核来放宽板端门禁。

## r97：补采结果

FIFO 1585，全程 sampling；等待前序 heavy 释放后入场。
节点实测：video0=t7-vdin-test，video1=aml_dev_drv，video2=aml_jpeg_decoder，
video3=aml_hevc_decoder；stateless media 为 /dev/media0。

| 项目 | 实测 |
|---|---|
| stateless 带流 compliance | 60/60，零失败/警告 |
| media | 8/8，零失败/警告 |
| JPEG 带流 compliance | 60/60，零失败/警告 |
| H.264 MR3_TANDBERG_B / BA1_FT_C / cabac_mot_picaff0_full | 三条 Success；保留完整硬件输出 |
| MPEG-2 sony-ct1 / sony-ct2 | 原 ISO 参考仍 Fluster Fail；实际硬件 .out 与历史校核 SHA/大小一致 |
| MPEG-2 sony-ct3 / mcp10ccett | Success；实际 .out 与历史校核一致 |
| JPEG mjpeg-420 / mjpeg-no-app / mjpeg-1080p | 各 16 帧；最大误差均2；最小逐帧逐平面PSNR分别52.1880/52.1880/52.4472dB |
| DOS step | 0 |

JPEG 硬件输出 SHA256：前两条均为
`59fd681d126f530b7b96aa6104b2e9935ff25a9e768657f5053e11043123ebd3`（5652480 字节），
1080p 为 `90aa034add7ef2d1d76bf87342dbc34707108e90deec9bfb6cf9e8413fc2c66a`
（49766400 字节）。全部十条硬件输出的布局、帧数、整流 SHA 和逐帧 SHA
已冻结到 build/hwdecode-parity/baseline38/short.json，原始输出留在 run97/archive/results。
MPEG-2 的历史对照只用来校核这次新实测输出，.39 基准取这次实际 .out。

## 恢复与冷复位

r96：一次候选启动、一次请求恢复正式，无冷复位。
r97：一次候选启动正常；请求恢复正式后，该正式启动在 Linux banner 后
**7.369467 秒**返回 T7 ROM（若从 Linux version 行计为7.368151秒），随后正式自然启动成功。
末条内核日志为 `[4.901161] brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM43752/2 …`；
末阶段另见 systemd NetworkManager-dispatcher 启动附近输出，没有 panic 证据。
不推断供电或解码根因。原始 UART 主机时间戳存在分块粒度误差，
起点取 Booting Linux 首标记，终点取 ROM 标记的接收分块时间。

恢复后 2372 protected_files 全同、无线恢复、候选模块挂载点和本任务固件副本清理完成。
被动 WebRTC 视频：3840×2160 H.265，59.7677 fps，解码帧计数 5→304，
丢帧/冻结/丢包计数没有增加。只证明视频传输与解码推进，不声称改变了源画面。
本任务累计第 1 次冷复位，按批准允许继续；第 2 次即停。

## 原始证据

证据均在 integration39 工作树，不入库：

- build/hwdecode-parity/run96：window.log（宿主目录失败）、window-retry.log、
  execution.log、board-upload.tar、board-upload-files.json、brief.json。
- build/hwdecode-parity/run97：inventory-failure-replay.log、execution.log、
  board-upload.tar 与清单、archive/results、brief.json。
- logs/hwdecode-parity-r96 与 r97：连续 uart.raw/uart-chunks.jsonl、入场/恢复身份、
  radio、owned-firmware、returned-video、complete.json。
- r97 UART SHA256：
  `17a01b543957af447a565f7e52a379e1f0fa5143dbfc0af3ae8e00975eb2c8fe`。
- .38 HEVC 132 条冻结/核验在 build/hwdecode-parity/baseline38/expected.json、verification.json，
  12 条失败 I420 均与原归档清单一致；本窗没有重复跑 HEVC。
