# 2026-11-06：r79入场UART旧缓存触发停止

**零上传、零候选启动、零重启，FIFO1495已释放。** 无线屏蔽变体没有被运行，
解码全部未运行。正式fd41fb5的2372项proof通过，视频59.749447fps、零新增
丢帧/冻结/丢包。停止发生在服务和板端UDC采证之前，不冒称这两项已验。

本窗起拓扑为Mac→用户USB-C功率计（型号待补）→VIM4，仍同时供电与HID。
用户报告供电能力显示15W、平时约3W，并确认Mac侧HID可识别；不是同步电流波形证据。
插拔功率计导致一次未计入既有冷复位统计的正式断电启动。

入场SSH两次boot_id均为`7be4d8b5-c0f1-4b95-8704-8925d7da60ba`，
uptime从354.70秒增加到364.37秒，宿主观测9.667097667秒。
UART仅收到255字节，从NUL及`T7:BL:`到残缺的`OTP_LIC00 : 0f03`，没有Linux启动。
旧门禁从接收偏移0检查ROM标记，因而停止；协调者结合boot_id/uptime确认这是
功率计插拔后残留的串口缓存，不计新冷复位，.36仍6次/4复位。

原始证据：`logs/hwdecode-parity-r79/{uart.raw,uart-chunks.jsonl,entry-uptime.json,
observed-baseline.json}`；UART SHA256为
`9b6173866ea052ca38c86505d7c288351a70c447e1c5c92b2ee047a69b0cfc4a`。
`build/hwdecode-parity/run79/entry-stop/`保留停止前编排器、计划、窗口与视频日志。

协调者批准替代票r79b：仍同一变体、一次启动、冷复位不重试，入场先排空UART一次，
保留排空字节数/SHA及原始字节，不计入后续continuity门禁；再采boot_id和uptime。
不丢弃候选启动/解码阶段数据，不改共享UART工具的默认行为。其余按
[无线变体计划](2026-11-06-vdec-integration36-no-radio-plan.md)，短回归仅全I加一条P/B，
全过且剩余≥630秒批预算+420秒恢复才运行全集第1批18条。
