# 2026-11-04：T7 MJPEG 解码接口

接续 [MPEG-2 场对修复](2026-11-04-mpeg2-request.md)。MJPEG 接入标准
`V4L2_PIX_FMT_MJPEG`，每个 OUTPUT 缓冲是一张完整 JPEG，无私有控制。
当前仅接受 8-bit sequential 4:2:0，CAPTURE 为单缓冲、有限范围 I420。
三组运动样本共 48 帧完整输出；相对同范围软件参考最大误差为两个码值。
H.264 和 MPEG-2 切换回归通过，正式启动不变；完整厂商格式仍未对齐。

## 实现与消费者

[MJPEG 草案](https://lore.kernel.org/all/20261025192507.210058-7-christian.koever-draxl@student.uibk.ac.at/)
的 codec 文件保留原作者与历史；实现提交为
`a02a63ad145db894ff6783b20e30d4da4db321fa`。T7 通过安全固件加载和内部 canvas
配置三平面，沿用公共工作线程的 DMA 停机确认；IRQ 只通知结果，不归还缓冲。
数据不足、超时、异常状态或输出索引报告错误；停机无法确认时保留 DMA 直到重启。

JPEG SOF 在启动 DMA 前检查精度、采样和图像尺寸，拒绝超过协商缓冲的图片。
输入长度检查先于标记读取，暂存区增长检查溢出。固件会跳过 SOI 后第一个段，
因此缺少 APP/COM 的 JPEG 先插入 COM，避免把量化表跳过。

GStreamer 的标准 `v4l2jpegdec` 在选定 codec 前枚举原始格式。JPEG 与无状态
H.264/MPEG-2 分开注册 video 节点，各自从首次枚举起提供匹配的格式，复用
同一个 m2m 调度器与物理解码器。两个 media 接口都连接同一 DMA 输入/输出
实体，不伪造第二套硬件拓扑；提交 `531376f885dd52e9d03e521984f21636ebce16d6`。
采用标准 STOP/START 排空，保留真实末帧的有效载荷，空排空只返回零长度末尾标记。

可见尺寸提交 `adeffe6717d3f260ec33460117525aec4a22ab7e` 在按 canvas 对齐之前
保留图像宽高，通过 CAPTURE COMPOSE 报告。GStreamer 可以区分 1080 行图像与
1088 行存储，避免把对齐填充带入输出。此接口目前仅对 MJPEG 提供。

## 接口与采样纠错

第十八轮的混合节点同时声明 JPEG 和 stateless decoder，compliance 拒绝。
第十九轮分开节点后，JPEG 节点缺少 media 接口与物理实体的连接，排空检查仍
失败。第二十轮补齐拓扑，两节点各 47 项 compliance 全通过、零警告。

第二十轮普通 filesink 把 GStreamer 存储填充也写入了文件，不能按可见尺寸
切帧。新增 [原生采样器](../../packaging/kernel/vdec-capture.c)，通过 GstVideoFrame
映射 GstVideoMeta，按实际 stride 与 plane offset 只保存可见区域；不转换像素。
实际 C 回归用有填充、有偏移的缓冲验证输出。第二十一轮采齐全部帧，但 JPEG
像素仍错误；采样成功本身没有被当作解码通过。

## 第二十二轮：T7C pscaler 重排与输出范围

离线定位第二十一轮输出：每组八字节反序；平坦区域亮度符合全范围到有限范围
转换。仅在诊断中反序并转换参考后，首帧各平面最大差一个码值。
厂商 T7C 子型号表启用 `is_mjpeg_endian_rematch`，JPEG `init_scaler()` 除 canvas
之外还设置 `PSCALE_CTRL2` 字节重排；此前遗漏此设置。修复提交
`b9cd73837bac7dcf41773d66243da1f2fe27bccf` 补齐硬件重排，并明确 OUTPUT 全范围、
CAPTURE 有限范围。采样器仍直接输出硬件像素，没有软件反序补偿。

[样本工具](../../packaging/kernel/vdec-fixtures.py) 保持 JPEG 编码为全范围，生成
有限范围软件参考用于此次 CAPTURE 合同；原全范围样本与参考哈希保存在旧轮次。
范围转换显式记录在 manifest 的 `reference_format`，不是放宽误差门限。
普通与移除 APP/COM 两组压缩输入均与前轮哈希一致；两组硬件输出逐帧相同，
证明缺少前导元数据时插入 COM 的路径正确。

| 运动样本 | 帧数 | 最大绝对误差 | 最低逐帧逐平面 PSNR |
|---|---:|---:|---:|
| JPEG 640×368 | 16 | 2 | 52.19 dB |
| JPEG 去 APP/COM | 16 | 2 | 52.19 dB |
| JPEG 1920×1080 | 16 | 2 | 52.45 dB |
| MPEG-2 场对回归 | 16 | 3 | 57.91 dB |
| H.264 Baseline 回归 | 32 | 0 | 逐字节一致 |

两节点 compliance 各 47 项通过；JPEG 三组正常 EOS。JPEG 残余差异包含 IDCT
和范围转换舍入，尚未与同板 5.15 输出比较，不能称位精确或完整格式一致。
驱动实际 C 测试 42 项通过，编译及 strict checkpatch 通过；主仓库 531 项
检查通过、11 项跳过。Mac 缺 Linux 头文件，驱动测试在 Linux VM 实际执行。

第十八至二十二轮均正常恢复原内核及完整文件身份。末轮五秒 4K H.265 接收
59.97 fps，无新增丢帧、冻结、丢包；performance 与 USB 配置不变。短测只证明
恢复，不能代替长期共存验收。证据在 `build/hwdecode-parity/run18/` 至 `run22/`，
串口在对应 `logs/hwdecode-parity-r*/`。末轮沿用第十八轮 Image，其 build ID
为 `80135ef7605a307c4bc9c55b21c757325ba09512`；私有模块 build ID 为
`7d2888325ecd56d99e1102ced78b311cfce81d4b`，BTF 对应同一份 vmlinux。

4K、其他采样、progressive JPEG、长期运行和与 KVM 同时使用尚未验收。
