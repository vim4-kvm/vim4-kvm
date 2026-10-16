# 4:4:4 采集

`tools/hdmi-setup.sh` 接受 `HDMI_CAPTURE_FORMAT=NV21`（默认）或 `YUV444`。
该设置属于共享 HDMI 服务，变更需要重启服务，不能当作单个 UU 会话的选项。
YUV444 要求新版 vfm_cap，报告 `VUY3`：8-bit 单平面 Cr/Cb/Y，stride 来自 canvas。
新版 vfmcapsrc 将其重排为 GStreamer `v308`（Y/Cb/Cr），保留全部色度；
此路径需要 CPU 拷贝，NV21 等现有路径仍是 DMA-BUF 零拷贝。

已有原始 DMA 采集 4K60 实测，不代表重排、编码或网络端到端达到相同帧率。
驱动的 CPU 映射现为只读可缓存页，每次导出完成帧时按需执行缓存失效；
CPU 读取必须使用 DMA_BUF_IOCTL_SYNC READ，禁止写入共享帧。
插件融合复制与 NEON 重排，并复用输出缓冲。旧 write-combine 映射下仅约 13.2fps，
优化后 4K 全帧读取、重排到 appsink 已实测约 60fps；细节和帧连续性见上板记录。
现有 KVM 硬件编码路径继续使用 NV21；在编码器与客户端验证前不开放真彩开关。
编码实测：现有 libamvenc 接受 RGB 但 H.264 输出 High/yuv420p，H.265 输出
Main/yuv420p；不能用输入格式或插件 caps 证明真彩。插件已移除未经支持的
4:4:4/4:2:2/10-bit profile 声明。软件编码未达到 4K60，详见上板记录。
驱动的 `test_lifecycle.c` 用于独占测试 close、STREAMOFF、REQBUFS(0) 后的
DMA-BUF 生命周期；测试结束应确认模块引用归零并可正常卸载。
