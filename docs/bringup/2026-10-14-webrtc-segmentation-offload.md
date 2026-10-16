# 2026-10-14：WebRTC 视频分段卸载发送（.23）

板端抓 eth0 出口包定位到 4K 大 P 帧（约 300KB）发送需 9.0ms（p99 24.7ms），
约 280 Mbps：pion 每包一次 sendto（约 12µs 内核 CPU）且 Chrome 协商到 AES-CM/HMAC。
NanoKVM 172ddab：应答时作 DTLS 服务端以选 AES-GCM；playout-delay 只加在首包；
每个视频连接的 UDP 套接字在写帧期间收集数据报，以 UDP_SEGMENT 成批发送。
首版包装了 mDNS 组播套接字，读循环空转占用约 3 核，已改为不包装组播套接字。

| 30 Mbps 运动 4K、Chrome | 改前 | 改后 |
|---|---|---|
| 大帧发送 p50 / p99 ms | 9.0 / 24.7 | 3.6 / 9.2 |
| 末包相对采集时钟 p99 ms | 25.2 | 10.3 |
| 浏览器帧间隔标准差 ms | 8.1 | 5.9 |

新路径下 12/6/3 Mbps 的帧间隔标准差为 3.6/2.4/1.8ms；剩余波动主要来自随帧
大小增长的编码耗时。GOP 600 在 30 Mbps 下无明显收益。均零丢包、零丢帧。

`.23` 只更换 NanoKVM：在干净临时工作区以 .22 的其余提交（One-KVM 套用哈希相同的
.22 未提交改动）打包，主检出中他人未提交的 EDID、kvm、管理器改动未打包。
package/verify、board.py deploy、board.py verify（HID、音频、4K 60.1fps）通过；
部署后空闲 CPU 0%。`tools/video-smoke.mjs` 的 h265/direct 模式在 .22 上同样失效
（选择 H.265 仍协商 H.264，Direct 超时），属于脚本与当前前端不匹配，未修。
证据：忽略入库的 `logs/encoder-jitter/`。
