# 2026-10-20：7.x HDR10 链路与元数据观测

已用原 5.15 HDR EDID 在 Mac 开启 HDR，7.x 接收端锁定并读到有效 HDR10 / PQ、
BT.2020、YCbCr420 10bit。**HDR 视频采集与 HDR→SDR 映射仍未完成**；新选项只供
接收端观测，未将未处理的 PQ 图像送进现有 RGB8/NV12 路径。正常服务仍使用原 SDR EDID。
前一任务的完整模式切换与回收验收见 [动态模式记录](2026-10-20-edge-dynamic-modes.md)。

## 版本与实现

Linux `e4a30e3b21505326280d600562e08cb032412a2e`，tree
`734f59e2db36bacad30da7f142d2582e3f598100`。完整 2333 个 BTF 模块包 SHA256
`1e5ebb4f84d179bee7fadf220a4813cba4ff8b2fd88e405286d111d6ea19cafd`，Image 与前轮
字节一致，build ID 仍为 `cd0b47762bd10b4c02dbf43b369b57ab182d1fb5`。
新 RX build ID `fc6203bebbf55302a4da53732c62d158764951d2` 已在板上核对。
One-KVM、私有 GStreamer 插件、实验 DTB、默认 5.15 启动项及生产文件均不改。
完整前版模块备份在 `/var/backups/vim4-onekvm-edge-20261020/hdr-probe/`。

新增只读 `hdr_probe=1`，要求 `dynamic_modes=1`，启动仍用已验证 SDR EDID。
现有 FHD/UHD 的 148.5MHz 参考之外，允许 92.8125MHz 附近、SCDC 1:40 的试验链路；
T7 的 PHY_BW_4 与当前 UHD 使用的模拟系数和 PLL 分频相同。稳定采样后锁定，
保持已有 DMA 租约排他性；格式不受支持但物理已对齐时不反复复位 PHY/PCS。
返回 SDR 时重新资格检查并更新 TMDS meter，避免 ALSA 用旧 HDR 时钟校验 N/CTS。

COR 的 unrecognized-packet 寄存器选择类型 0x87，读取静态 HDR 数据，不启用额外
包 DMA。core 关闭时恢复原选择；debugfs 增加原始 AVI 和 DRM candidate 字节，
不承诺任意时刻的包一致性或新鲜度。现有深色/YUV 拒绝条件保留，HDR 下查询返回
ENOLINK，不能取得采集租约。物理锁定不等于已支持 HDR 视频。

十组真实 C 回归和完整 Image/dtbs/modules 构建通过。扩展测试覆盖额外时钟的
opt-in、SCDC/频率边界、已锁定探测信号不循环重置、HDR 拒绝采集、返回 SDR 重新
资格检查，以及包选择寄存器恢复。没有修改 5.15 的 HDR 驱动或曲线。

## 源端与硬件结果

试验复制板上 `/etc/tvconfig/hdmi/port1_20.bin` 的原始 256 字节 EDID，SHA256
`886ed6b97e3a00b129b543d53e2bf3a024654cf160406937d15cb3bbd200923c`，文件自身不改。
该表声明 HDR 和多种模式，不能直接作为目前 7.x 完整能力清单。
只在停止观看与采集后临时写入接收端 EDID RAM，Mac 对应 `AML TV` 可开启 HDR。
测试结束恢复该显示器原先关闭的 HDR 偏好、原 SDR EDID 和 KVM 服务。

早期 f30 驱动仅看到约 92.81MHz 参考，无 PLL/PCS 锁定；它不能据旧 AVI/GCP
寄存器缓存判断源格式。新驱动的自动化检查取得下列已锁定样本：

| 项目 | 观测 |
|---|---|
| cable / TMDS | 92,812,500 / 371,244,140Hz |
| PLL / PCS | 均锁定，两次间隔采样保持 |
| AVI | `82020d5472e86061000000000000000000`，校验和有效 |
| 色彩 / 时序 | AVI 声明 YCbCr420、BT.2020、VIC97；GCP 深色码 5（10bit） |
| DRM | `87011a5c0200…`，版本 1、长度 26，校验和有效，EOTF=2（PQ） |
| 原始计数 | 1920×2160、总数 2200×2250；420 的半宽计数，不能当作 1080p 图像 |
| 采集保护 | `VIDIOC_QUERY_DV_TIMINGS` 返回 errno=67/ENOLINK，capture_users=0 |

这是静态 HDR10 元数据接收证据，不是 HDR10+ 动态元数据、HLG、Dolby Vision 或
HDR 图像质量验收。原始计数的含义需在后续格式路径归一化，不能只放宽宽高检查。

手动观测曾触发 90 秒探测期限，板上 finally 已自动恢复 EDID 和服务；Mac 的 AML
HDR 偏好随后单独恢复。之后的自动化流程正常结束，校验源格式、元数据、采集拒绝、
返回 SDR 锁定和原偏好恢复，避免把超时观测记为完整流程通过。
临时 modprobe 配置在首次测试启动后移除，常用启动默认不启用 hdr_probe。

HDR 观测正常退出后，H.264/H.265 各完成一次 FHD60↔UHD60 往返，同连接保留，
新鲜截图尺寸匹配，音频峰值非零，结束后 DMA-buf 归零。每个模式 5 秒解码结果：

| 运行配置 | 1080p60 fps / 音频峰值 | 4K60 fps / 音频峰值 |
|---|---|---|
| hdr_probe=1，H.264 | 59.975 / 0.1023 | 59.955 / 0.1024 |
| hdr_probe=1，H.265 | 59.962 / 0.1024 | 59.955 / 0.1017 |
| 再次重启、hdr_probe=0，H.265 | 59.963 / 0.1021 | 59.966 / 0.1010 |

最后一轮确认默认选项关闭、临时配置不存在、原 UHD EDID 与 Mac mode 16 恢复，
H.265/4K60 服务可用。最终 CmaFree 505192KiB、DMA-buf=0、taint=0、VDIN fault=0；
音频 enabled/streaming、无错误。5.15 Image、应用与默认启动项摘要仍与部署前一致。
主仓库离线 124 项结束：119 通过、5 跳过。

## 接下来需要补齐

1. 按 AVI/深色和新鲜 DRM 元数据管理输入格式；失锁和停止发送 HDR 后丢弃旧状态。
2. 接通 420/10bit 的视频展开与 VDIN 输入，归一化 4K 几何，保持编码尾部容量和 DMA 租约。
3. 配置 HDR2 的 PQ 解码、BT.2020→BT.709 矩阵、色调与 SDR 编码 LUT，SDR 保持直通。
4. 复用 [5.15 曲线](../hdr.md) 的 SDR 白/高光参数与管理页，用灰阶、色块和高光图
   验证像素，并验证 HDR↔SDR、音频和同网页连接恢复，再声明对应 EDID 能力。

证据在 `logs/kernel-edge/edge-hdr-*`，包含完整构建、串口、原始手动观测、超时恢复、
自动化元数据与采集保护检查，以及 SDR 恢复后的网页检查。没有把之前 f30 的五轮
模式切换结果重新标成此版本的长期或 HDR 视频证明。
