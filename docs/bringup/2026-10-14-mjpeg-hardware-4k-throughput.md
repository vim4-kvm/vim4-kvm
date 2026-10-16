# 2026-10-14：MJPEG 硬件编码与 4K 运动画面吞吐

原 NanoKVM / One-KVM 的 VIM4 路径使用软件 jpegenc 并主动限制到 10fps。
新增 vim4jpegenc，通过 /dev/jpegenc 编码 NV12/NV21 DMA 输入，质量支持 1–100。
厂商 amljpegenc 直接 DMA 输入实测只输出 4 帧后停滞：NEW_CMD 路径未归还
导入的采集缓冲。新插件使用 CONFIG_DMA_INPUT / RELEASE_DMA_INPUT 管理逐帧
导入；异常时关闭硬件后释放输入。没有改内核或超频，缺少新插件时仍回退软件 10fps。
NanoKVM 取消原应用 30Hz 轮询限制；One-KVM 在缩放后使用单帧队列重叠缩放与编码，
状态接口按实际帧数计量，并沿用公共接口的百分之一帧存储单位。

HDMI 输入 3840×2160、约 60Hz，以 tools/latency-source.swift 的 --motion
模式生成全屏运动网格，编码器保持原 666MHz。每组 240 帧，统计剔除起始 10 帧：

| 输出 / JPEG 质量 | 板端编码 fps | 编码数据 Mbps |
|---|---:|---:|
| 2160p / 50 | 51.17 | 393.49 |
| 2160p / 80 | 51.22 | 582.93 |
| 2160p / 100 | 47.19 | 1290.96 |
| 4K 缩至 1080p / 80 | 40.78 | 188.33 |
| 4K 缩至 720p / 80 | 43.62 | 110.18 |
| 再次开启 2160p / 80 | 51.21 | 583.57 |

各组首尾 JPEG 均成功解码，重复关闭、开启通过。缩小分辨率包含 GE2D 成本，
不能用原生小分辨率性能解释这些结果；51fps 是当前路径实测，非芯片理论上限。
Q100 的数据量超过千兆网络容量，不能承诺该质量下的完整帧率交付。

`.19` 实机 Chrome 在相同 4K/Q80 运动画面下，One-KVM 初次连接 / 刷新收到
50.84 / 50.75fps，约 579Mbps；NanoKVM 为 42.60 / 39.59fps，约 488 / 454Mbps。
此处统计 HTTP 收齐的完整 JPEG 帧，不是显示器实际呈现帧数。另用真实 One-KVM
网页验证 MJPEG 图像尺寸为 3840×2160。首次部署发现状态显示单位不符，将真实
约 51fps 显示为 0.51fps，后续修正不影响编码或收帧路径。

最终 `.20` 完整包校验及部署通过，Chrome 再次连接 / 刷新收到 50.90 / 50.79fps，
状态接口分别为 50.77 / 50.64fps，确认显示单位修复。记录见
browser-one-final.jsonl、verify-fps.log、deploy-fps.log；编码器固定 a99edf0，
NanoKVM c6ad206、One-KVM 84172cdf，部署根源码固定 7463ca3。

构建验证：NanoKVM VIM4 Go 测试、One-KVM 561 项 Rust 测试、两套前端构建、
根仓库 42 项测试及组件包隔离升级校验通过。插件以 -Wall -Wextra -Werror 构建。
One-KVM 二进制保留此前 `.17` 已部署的 VNC Tight JPEG 兼容改动，包内 sources.json
记录其精确未提交补丁，未改动原工作树的该文件。JetKVM 不提供 MJPEG，此次未新增。

证据位于 logs/mjpeg-hardware/：motion-final.jsonl、browser-one.jsonl、
browser-nano.jsonl、one-ui-smoke.log、one-fps-build.log、nano-final-build.log。
测试后恢复 One-KVM 选择及原 MJPEG 模式；USB disk.img 挂载保留，HDMI 服务未重启。
