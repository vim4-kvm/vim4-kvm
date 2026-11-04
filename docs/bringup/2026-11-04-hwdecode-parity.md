# 2026-11-04：T7 硬件解码格式对齐

本任务以厂商 T7 的实际能力表为范围，通过标准 V4L2 接口实现；格式枚举、
完成中断和返回缓冲均不能代替正确图像验收。当前仍处于驱动修复阶段，
未完成格式对齐；第二轮已得到完整非零图像，但像素比较失败，已恢复原内核并验证视频。
没有改变正式启动内核，也没有任何格式通过本轮硬解码验收。

## 范围与验收

厂商来源为 common_drivers 的
[T7 平台表](https://github.com/vim4-kvm/common_drivers/blob/31619c527655514b4c89516ef609b6db1dd47db6/drivers/media_modules/common/chips/decoder_cpu_ver_info.c)，
须同时看 `FMT_VDEC_ALL`、`FMT_HEVC_VP9_AVS2_AV1` 和各 codec 的功能约束。
适用格式是 MPEG-1/2、MPEG-4、H.264、MJPEG、VC-1、MVC、AVS、HEVC、VP9、AVS2、AV1。
通用前端出现 VP8、RealVideo 或 AVS3 的名字不代表 T7 支持。

按格式分别验证 profile、位深、色度采样、隔行和分辨率；平台的面积上限不能
直接解释为每种格式都支持同样的 8K 帧率。先用小尺寸运动样本对软件参考逐帧
比较，再扩展到对应边界，检查重开、参考帧、错误退出和与 KVM 的资源共存。
不以软件解码回退充当硬件解码。保持现有 performance 策略。

样本生成与逐帧比较入口为 [vdec-fixtures.py](../../packaging/kernel/vdec-fixtures.py)，
均离线运行，`generate` 创建新目录，`compare` 对指定格式的板端 I420 输出
验证字节数和每帧哈希；失败返回非零，不把帧数正确当作像素通过。

[多格式补丁](https://lkml.iu.edu/2610.3/01558.html)只报告 S4 验证，尚不能作为
T7 的验收证据，也不覆盖 VC-1、AVS、AVS2、MVC。需逐项审查固件协议、电源、
地址表和缓冲生命周期后使用；不整套替换本项目已有的停机与 DMA 持有处理。
逐项阅读邮件正文还发现：HEVC、VP9、AV1 的 10-bit 输入均降成 8-bit 输出；
VP9 排除了需要反向概率更新的流；HEVC 长期参考和 MPEG-4 使用作者明确标作
RFC 的私有控制。这些均不能当作标准接口、完整位深和厂商格式覆盖已经实现。

## 内部地址表与外部 canvas 的区别

[前次记录](2026-10-23-vdec-timeout.md)报告全零输出后超时。本轮追到
`is_support_vdec_canvas()` 的调用者，纠正了此前把这个能力位解释为外部
`meson_canvas` 的判断：它实际表示 **VDEC 内部 LUT**。

- [能力查询](https://github.com/vim4-kvm/common_drivers/blob/31619c527655514b4c89516ef609b6db1dd47db6/drivers/media_modules/common/chips/decoder_cpu_ver_info.c)：T7 为真，S4 为假。
- [config_cav_lut_ex](https://github.com/vim4-kvm/common_drivers/blob/31619c527655514b4c89516ef609b6db1dd47db6/drivers/media_modules/frame_provider/decoder/utils/vdec_canvas_utils.c)：为真时写 `MDEC_CAV_CFG0`、`MDEC_CAV_LUT_DATAL/DATAH/ADDR`；为假才调用外部 `canvas_config_ex`。
- [H.264 消费者](https://github.com/vim4-kvm/common_drivers/blob/31619c527655514b4c89516ef609b6db1dd47db6/drivers/media_modules/frame_provider/decoder/h264_multi/vmh264.c)：`config_decode_canvas` 经上述函数配置 Y/UV，再写 ANC 表和当前帧索引。

现有 7.3 H.264 只调用外部 `meson_canvas_config`。因此，即使 ANC 索引和完成
中断正常，也没有把目标 DMA 地址写到 T7 实际消费的表中。这是确定的实现缺口；
是否足以解释全部零帧与后续超时，仍须实板验证，不能把推断写成已定位全部根因。

修复按 DPB 槽位为 Y/UV 分配内部表项，每次硬件任务重写。内部索引不进入外部
canvas 分配器，DMA 停止前仍保留所有输出和参考缓冲。标准外部 canvas 路径继续
服务 S4；不能因 T7 的差异全局改写 canvas 控制器。

## 已完成的离线修复

H.264 的 SPS/PPS 临时表只赋值部分字段，却整表交换字节序后交给固件；清零目标
内存随后被未初始化栈内容覆盖。现改为初始化完整临时表。另修正 B 帧第二参考
列表误从第一列表复制的问题。实际 C 函数测试使用编译器栈填充和不同列表，
两项都能稳定拒绝旧实现；已有生命周期回归也通过。硬件正确帧尚未验证。

内部 LUT 测试反解每个 DPB 槽位的硬件表项，核对 Y/UV DMA 地址、步长、高度、
线性布局和字节序；另覆盖换实例后重写、非法槽位、表写入失败与外部 canvas
分配器隔离。实际 C 函数回归共 23 项通过，strict checkpatch 无诊断。

## 首轮 RAM 窗口

候选源码为任务分支 `hwdecode-parity` 的 `0ad3f43b8254a10ec8c5aa58a380b8a445da988f`，
包含参数表/参考列表修复 `da9e9c50bafce` 和内部 LUT 修复 `0ad3f43b8254a`。
同次 Image、DT 和完整模块构建、封包检查通过；ADLA 编译告警位于未改代码，
不能描述成整个内核零告警。候选 build ID 为
`56431fab756d52b5e00a4482ae550f98d9b5ea26`，原始产物、测试样本和结果在
本机 `build/hwdecode-parity/`，串口在 `logs/hwdecode-parity/`。

一次性 U-Boot RAM 选择成功，串口记录了候选的 kernel release 和 PID1 启动。
随后在 gadget 服务启动附近直接回到 BL2，下一次启动原因为 `cold_boot`；
没有记录到 panic，也没有进入窗口脚本的解码器上电、compliance 或码流测试。
用户确认供电线、主机和 RESET 均未动。没有内核 panic 证据，也没有 PD 协议
记录足以认定这次冷启动的原因；不能把它归为外部人为操作。

默认启动一直指向原 build 3，重启后完整身份、受保护文件、模块和应用核验一致。
五分钟 3840×2160 H.265 接收平均 60.01295 fps，丢帧、冻结、丢包增量均零；
UDC configured，两簇 performance，taint 仍为 4096。候选空模块挂载点和本次
创建的 release 专用 Wi-Fi 固件副本已回收，板锁释放。小样本、Main/High/B 帧、
1080p 以及其他所有格式均未运行，不把恢复视频算作硬件解码通过。

## 第二轮：内部 LUT 已输出图像，量化仍错误

使用同一候选 Image 和完整模块，仅为 RAM 启动器增加有界的 FUSB302/TCPM
软件日志采集；不读未上电 MMIO、不改 PD 策略。候选成功启动，串口记录到
Request、Accept、PS_RDY；这不能解释或排除上一轮的异常冷启动。

probe、上电、13 步 MDEC 检查通过，V4L2 compliance 47 项通过、零错误和警告。
640×368 Baseline、QP22 运动样本返回 32 个完整非零 I420 帧并正常 EOS，
没有超时、SError 或 panic。但逐帧 SHA 与软件参考不一致，首帧 PSNR 仅约
9.26 dB，画面能辨认测试图案，亮度与颜色严重失真。单纯交换 UV 不能修正。
首次像素失败后停止，Main、High、1080p 和其他格式没有运行。

码流 PPS 的初始 QP 偏移为 −4、chroma 偏移为 −2；驱动此前把负数补码写入
固件参数表。[已审查的协议修复](https://lkml.iu.edu/2610.3/01563.html)指出固件
从表中读取的是有符号 Exp-Golomb 的码号。实验提交
`0fa7572fa352c3392d616aef638063bd8dcc7e4d` 改为相应编码；实际 C 函数测试
对写入并交换 lane 的表作固件语义反解，覆盖合法 QP 和 chroma 范围，旧实现
无法通过。23 项回归和 strict checkpatch 通过，硬件修复效果仍待下一候选验证。

证据位于 `build/hwdecode-parity/run2/` 和 `logs/hwdecode-parity-r2/`。
采集时 scp 无法读取 root 私有的 GStreamer registry cache；像素、结果、内核
和串口日志均已取得，后续采集显式排除该缓存。正常重启恢复原身份与完整文件
证明，五秒 H.265 接收约 59.79 fps、丢帧/冻结/丢包增量零，服务、UDC 与
performance 正常；原身份未变，复用首轮五分钟基线，不把短测称作稳定性验收。
