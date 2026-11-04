# 2026-11-04：T7 MPEG-2 请求接口

接续 [H.264 七组像素验收](2026-11-04-h264-boundaries.md)。本阶段增加标准
`V4L2_PIX_FMT_MPEG2_SLICE` 请求接口，仍是显式启用的实验驱动。MPEG-1 与其他
格式不能因共用固件或文件名而视为已经支持；正式启动维持原内核。

## 接入与生命周期

[MPEG-2 草案](https://lore.kernel.org/all/20261025192507.210058-6-christian.koever-draxl@student.uibk.ac.at/) 的两个 codec 文件保留作者
与提交历史，随后审查并适配已有停机约束。实现提交
`8552e35285df8ab68337975a98876ca2595525db` 通过 T7 安全固件加载与内部 canvas
配置接入。IRQ 只通知结果，由公共工作线程确认 DMA 停止后归还缓冲；停机失败
保留所有私有 DMA 和队列引用直到重启。各任务在加载固件前选择自身中断回调，
避免另一文件上下文初始化时覆盖当前 codec 的处理器。

输出格式探测原本沿用当前 H.264 格式，导致新格式无法正确协商；现在按请求
的格式及队列方向查表。CAPTURE 保存实际平面数量，并覆盖 OUTPUT 所确定的
尺寸，避免 NV12M 色度写到 Y 平面尾部或接受小于解码图像的输出缓冲。

## 参数头与离线证据

参数头由标准 sequence、picture、quantisation 控制重建。按照
[内核控制接口](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/ext-ctrls-codec-stateless.html)
保留 VBV 单位与 zigzag 矩阵顺序，picture 层传入四组矩阵，第二场不丢失矩阵
更新。交错帧的 chroma_420_type 随 progressive_frame 设置。

主机检查包含真实 C 函数的参数头解析、格式探测、多平面存储、任务回调归属、
中断通知与失败停机隔离，共 34 项通过，strict checkpatch 通过。一个含 I/P/B
帧与非默认矩阵的码流，将参数头替换为驱动输出后，软件解码的全部 16 帧保持
逐字节一致。这不证明 T7 硬件输出正确。

[样本生成器](../../packaging/kernel/vdec-fixtures.py) 增加纯 I 帧、I/P/B、
自定义矩阵、隔行帧和 1080p 运动样本。每个文件经 ffprobe 核 profile、尺寸、
帧数及场序，再生成实际压缩文件的软件参考。隔行帧不等于场编码，第一场暂存
与第二场组合路径仍需独立场编码样本；同样不能由短样本推定长时间共存通过。

## 首轮实测：完成中断但输出全零

窗口 `build/hwdecode-parity/run11/` 使用候选 `.13`，GNU build ID 为
`0c924fcc248d058211d64ae420cbde0a9e646e26`。先复验 H.264 的 JVT 矩阵、
Baseline 与 Main，112 帧全部逐字节一致。随后 MPEG-2 纯 I 帧样本正常结束，
16 帧却全部为零。固件逐帧报告完成、尺寸正确且错误计数为零，故完成中断
不足以证明有效输出。其余 MPEG-2 样本未运行。

首错后已恢复正式 `.3`，完整身份及持久文件证明一致，原 KVM 接收
59.76219 fps，无新增丢帧、冻结或丢包，UDC configured、CPU performance。
逐帧哈希、完整 I420 与内核日志已拷回离线分析。对照厂商初始化发现缺少
四处图片/IQ 状态复位，正在验证；尚不能将其认定为全零输出的根因。

第二轮 `run12` 使用 `972a720a030692b350c64af9cbde081bcfef2e9a` 的 `.14`，
build ID `b83261fdc9ee70135364eb9dc7e97e31dd0188df`。新增状态复位后，H.264
112 帧仍一致，但 MPEG-2 纯 I 帧仍全部为零，故该修改没有解决输出故障。
新增日志确认 Y/UV DMA 地址非零、canvas 尺寸和单平面偏移符合分配结果。
恢复 `.3` 后接收 60.56522 fps，无新增丢帧、冻结或丢包，身份与持久文件
校验通过。继续核查厂商每次运行前的完整核心复位，尚未通过硬件验收。

MPEG-2 的 IDCT 可能与软件参考存在舍入差异，但不能仅凭草案作者的描述放宽
验收；遇到差异先定位、量化，不把“有输出”当作正确解码。

## 完整复位与用户态参数对照

`run13` 使用 `6402bd45e222bc7e36adc020f76aa15d82ed689f` 的 `.15`，build ID
`83c131f4698f22a4a5362c55b5dda015ef276004`。MPEG-2 在总线隔离期间完整复位，
保留 POWER_CTL_VLD，再加载固件。36 项主机检查通过，包括逐个 MMIO 失败后
不解除隔离。H.264 112 帧仍一致，MPEG-2 仍全零；恢复接收 60.55829 fps。
完整复位未解决本次全零输出，不能将它记作故障根因。

转查实际用户态后发现 [GStreamer 的控制转换](https://github.com/GStreamer/gstreamer/blob/1.24.2/subprojects/gst-plugins-bad/sys/v4l2codecs/gstv4l2codecmpeg2dec.c)
把 VBV 值乘以 16384、错误拼接 profile/level 位，并未初始化默认色度矩阵。
[parser](https://github.com/GStreamer/gstreamer/blob/1.24.2/subprojects/gst-plugins-bad/gst-libs/gst/codecparsers/gstmpegvideoparser.c)
实际拆出的是 1 位 escape、3 位 profile、4 位 level；这些值需原样还原。
私有 [构建入口](../../packaging/kernel/build-vdec-gstreamer.py) 固定官方源码与
校验值，修正标准控制转换，保留完整 18 位 VBV 值及序列矩阵继承。真实 C
转换回放在原源码上失败、修改后通过；不修改系统插件或 KVM 捕获插件。

`run14` 重用 `.15` 的同一 Image/模块，仅测试进程通过 GST_PLUGIN_PATH 加载
私有插件，SHA256 `ca9b5d41cd5cb4e1971778e3db99171c66bc78a24a6b9bcd906cfe7de2e8f601`。
H.264 112 帧仍逐字节一致，MPEG-2 纯 I 帧的 16 帧不再为零。每个像素相对
FFmpeg 参考均在 ±1 内，合并全部帧后的 Y/U/V PSNR 分别为
70.38689/69.03053/67.75598 dB。逐字节检查仍正确地报告差异，未自动放宽门禁。
恢复 `.3` 后接收 59.77082 fps。各窗口完整身份、持久文件、UDC、performance
与零新增丢帧/冻结/丢包检查均通过。尚需分析其他 MPEG-2 样本的逐帧误差。

## 五组像素测量

`run15` 沿用 `.15` 与同一私有插件，五组 MPEG-2 共 96 帧全部解码完成，
无超时、缺帧或全零帧。随后切回 H.264，Baseline 32 帧逐字节一致。
MPEG-2 捕获阶段仅记录完成，全部 I420 拷回后再与固定软件参考逐帧比较。
下表最差 PSNR 取每帧的每个 Y/U/V 平面中的最小值，不能与整段合并值混用。

| 样本 | 帧数 | 最大绝对像素差 | 最差单帧平面 PSNR/dB |
|---|---:|---:|---:|
| 纯 I 帧 | 16 | 1 | 67.44829 |
| I/P/B | 32 | 3 | 64.23481 |
| 自定义矩阵 | 16 | 3 | 64.65114 |
| 隔行帧 | 16 | 3 | 64.27105 |
| 1080p | 16 | 4 | 67.38588 |

各帧、各平面平均有符号误差的绝对值均小于 0.012。这些结果显示小幅
IDCT/预测舍入差异，不能称为逐字节一致或完整 5.15 对齐；尚未取得同码流的
厂商硬解输出，独立场编码、长期运行及 KVM 共存仍待验证。工具的
`compare --measure-error` 提供完整逐帧统计，非精确输出仍返回非零。

本轮恢复 `.3` 后接收 60.76798 fps，无新增丢帧、冻结或丢包；完整身份、
持久文件、UDC 与 performance 检查通过。MDEC 关闭后 runtime suspended，
未观察到新增内核异常。原先的 `.13`/`.14` 私有板端载荷已清理，本地归档保留。
