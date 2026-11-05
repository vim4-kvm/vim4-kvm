# 2026-11-04：T7 MJPEG 解码接口

接续 [MPEG-2 场对修复](2026-11-04-mpeg2-request.md)。MJPEG 接入标准
`V4L2_PIX_FMT_MJPEG`，每个 OUTPUT 缓冲是一张完整 JPEG，无私有控制。
当前仅接受 8-bit sequential 4:2:0，CAPTURE 为单缓冲 I420。离线实现及编译
已通过，尚未完成像素验收，也不代表全部厂商格式已经对齐；正式启动不变。

## 实现与消费者

[MJPEG 草案](https://lore.kernel.org/all/20261025192507.210058-7-christian.koever-draxl@student.uibk.ac.at/)
的 codec 文件保留原作者与历史；实现提交为
`a02a63ad145db894ff6783b20e30d4da4db321fa`。T7 通过安全固件加载和内部 canvas
配置三平面，沿用公共工作线程的 DMA 停机确认；IRQ 只通知结果，不归还缓冲。
数据不足、超时、异常状态或输出索引报告错误；停机无法确认时保留 DMA 直到重启。

JPEG SOF 在启动 DMA 前检查精度、采样和图像尺寸，拒绝超过协商缓冲的图片。
输入长度检查先于标记读取，暂存区增长检查溢出。固件会跳过 SOI 后第一个段，
因此缺少 APP/COM 的 JPEG 先插入 COM，避免把量化表跳过。

GStreamer 的标准 `v4l2jpegdec` 在选定 codec 前枚举全部原始格式，选定后再次
协商。初次 CAPTURE 枚举提供格式并集，OUTPUT S_FMT 后只列出该 codec 的格式；
H.264/MPEG-2 不接受 JPEG 的 I420，JPEG 也不接受 NV12M。
采用标准 STOP/START 排空，保留真实末帧的有效载荷，空排空只返回零长度末尾标记。

可见尺寸提交 `adeffe6717d3f260ec33460117525aec4a22ab7e` 在按 canvas 对齐之前
保留图像宽高，通过 CAPTURE COMPOSE 报告。GStreamer 可以区分 1080 行图像与
1088 行存储，避免把对齐填充带入输出。此接口目前仅对 MJPEG 提供。

## 离线验证与待验边界

实际 C 函数回归共 41 项通过，包括截断头、非法采样、尺寸越界、中断状态、失败
停机隔离、初次格式发现与 codec 切换、排空和可见尺寸。驱动编译通过；strict
checkpatch 无代码诊断。新增测试文件的路径提示已核对 MAINTAINERS 目录覆盖。

[样本工具](../../packaging/kernel/vdec-fixtures.py) 生成普通 JPEG、移除前导 APP/COM
的 JPEG 和 1080p 运动序列。参考保留 JPEG 全范围像素，避免软件比较时偷偷做
范围转换。移除元数据前后 16 帧软件输出逐字节一致，首个有效段确认为 DQT。
主仓库 530 项检查通过、10 项跳过。

尚待上板验证三组像素、标准播放器 EOS，以及切回 MPEG-2/H.264。4K、其他采样、
progressive JPEG、长期运行和与 KVM 同时使用尚未验收。
