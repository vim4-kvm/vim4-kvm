# 2026-11-04：T7 硬件解码格式对齐

通过标准 V4L2 接口对齐厂商 T7 实际能力，格式枚举和完成中断不能代替像素验收。
第五轮 H.264 Baseline、Main、High、1080p High 运动样本全部逐帧通过；
已恢复原内核并验证视频，正式启动未变。完整格式与边界仍未对齐。

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

## 第三轮：PPS 修复后定位 T7 revision C 字节序

候选源码 `0fa7572fa352c3392d616aef638063bd8dcc7e4d`，build ID
`9359e674b0e0ce320e2d19b69f06c66d33c58701`。同样本返回完整 32 帧、正常 EOS，
仍未通过原始像素比较，立即停止后续格式。原 KVM 身份与文件证明恢复一致，
五秒 H.265 接收约 59.75 fps，无新增丢帧、冻结或丢包。

离线逐字节分析发现 Y 每八字节反序，UV 合并平面也每八字节反序；对已采集数据
仅作这项还原后，全部 32 帧与软件参考完全一致。该处理仅用于定位，不能把
变换后的文件算作原始硬件输出通过。原始失败文件及分析在
`build/hwdecode-parity/run3/`，串口在 `logs/hwdecode-parity-r3/`。

串口 SoC 信息为 T7 revision C。厂商
[config_cav_lut_ex](https://github.com/vim4-kvm/common_drivers/blob/31619c527655514b4c89516ef609b6db1dd47db6/drivers/media_modules/frame_provider/decoder/utils/vdec_canvas_utils.c)
在该修订且 endian=7 时还写 `MDEC_CAV_CFG0` 的 byte-switch remap；第一版内部
LUT 修复遗漏这一条件。提交 `4befe13e1f628bebe41d2d43d7dbe4a8ad0526af` 通过
标准 SoC revision 匹配启用该设置，其他修订沿用原配置，待下一候选验证。

## 第四轮：Baseline 正确，Main 参考列表长度错误

候选源码 `4befe13e1f628bebe41d2d43d7dbe4a8ad0526af`，build ID
`f3f23e980549560d6d69d664e67ecab384f4c968`。Baseline 原始输出的 32 帧全部逐字节
等于参考，未作事后字节变换。Main 完整输出 64 帧，16 帧正确、48 帧不一致；
第一个不一致的编码帧是第二个 P 帧，其错误随后传入依赖它的 B/P 帧。
停止 High 和 1080p。原 KVM 完整恢复，五秒 H.265 约 59.75 fps，零新增丢帧、
冻结或丢包，performance 未变。

该 P slice 显式覆盖为四个参考项，并让同一图像以两个不同权重出现。
驱动却因额外读取固件的 override 标志而退回 PPS 默认三项，串口参考列表日志
与码流解析相符。厂商 `h264_dpb.c` 直接使用固件已解析的当前 slice 数量。
提交 `0c23450690ed6381a13c7a545f720d8eb8cee554` 复用已解析并校验过的两份数量，
不再另从 PPS 猜测。实际重排函数回归复现重复参考与四项列表，旧实现失败；
也覆盖 list 1 和单参考覆盖，24 项测试与 strict checkpatch 通过，待板端复验。
证据在 `build/hwdecode-parity/run4/`、`logs/hwdecode-parity-r4/`。

## 第五轮：四组 H.264 样本全部匹配

候选源码 `0c23450690ed6381a13c7a545f720d8eb8cee554`，build ID
`5c11f2e75a28dab691ad951c54361db97bd81609`。同次 Image、DT、完整 2341 模块
构建及封包通过，配置与正式基线一致。probe、13 步上电/MDEC 检查和 47 项
V4L2 compliance 通过；24 项驱动主机回归与 strict checkpatch 通过。

| 运动样本 | 帧数 | 原始 I420 与软件参考 |
|---|---:|---|
| 640×368 Baseline | 32 | 全部逐字节一致 |
| 640×368 Main，B 帧、多参考和 weighted P | 64 | 全部逐字节一致 |
| 640×368 High，B 帧、多参考、8×8 transform | 64 | 全部逐字节一致 |
| 1920×1080 High，B 帧 | 16 | 全部逐字节一致 |

各进程正常 EOS，测试间重开成功，硬件回到 runtime suspended。没有新增
timeout、Oops 或 panic；这些短样本证明正确性，不据耗时宣称最大解码帧率。
High 在当前 T7 固件上可以通过现有参数表协议解码，本轮不引入只在另一块
S4 固件上报告需要的 in-band SPS/PPS 补丁。

正常重启回原 build 3，完整身份及受保护文件证明一致。原 H.265 KVM 接收约
59.77 fps，无新增丢帧、冻结或丢包，UDC configured、两簇 performance，
taint 仍为 4096。证据在 `build/hwdecode-parity/run5/` 和
`logs/hwdecode-parity-r5/`。完整厂商格式、分辨率和码流边界尚未对齐，不部署
实验分支为默认内核。

后续 UHD、最大尺寸与量化矩阵进展见 [H.264 边界记录](2026-11-04-h264-boundaries.md)。
