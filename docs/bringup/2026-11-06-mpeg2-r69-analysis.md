# 2026-11-06：r69 MPEG-2 像素与单向 B 参考根因

r69 的四条旧/新输出相同不能证明量化控制未生效：差异只在独立色度矩阵，而全部
码流都是 4:2:0，按 UAPI 和 ISO 参考解码器应忽略这些矩阵。已定位的驱动缺陷是
sony-ct1/ct2 开头两张 B 图像只有后向参考，驱动却强制查找两个 anchor，启动固件前
返回错误，产生两帧全零。topic 修复允许未声明的方向保持无效 canvas，并继续拒绝
声明后丢失的参考；尚未上板，不能声称整个 sony 流已通过。

全部 19 条旧 Fail 已逐帧比较 ISO 和 FFmpeg，首错宏块位置见
[逐流 CSV](data/2026-11-06-mpeg2-r69-pixels.csv)。另外 4 条通过对照也完整复核。
15 条是最大差 3–6 的小幅漂移；att/teracom 是随 P 链增长的误差，仍未证明具体
舍入、预测或微码根因。原容差不变，不把这种分类改写成 Success。

## 证据和身份

本轮只读协调者提供的主工作区：
`build/hwdecode-parity/run69/archive/results/mpeg2/`，内含 29 次的 `.out`、
`*_ref.yuv`、ioctl、队列 trace 和 kernel.log。r69 候选源码为
`6346fd353fdc0405841ab0804b9239e604f9128f`，release `.31`；其 mpeg12.c 与
本 topic 基线 `c99c3eddea02823a6b958d16e35ec7d7fd0ccc0d` 没有差异。
没有修改 r69 归档、访问板子、申请板票或 push。

本工作树 `build/mpeg2-r69/` 保存一次性分析脚本和原始输出：

- `analyze.py`、`*-old.json`、`*-fixed.json`：真实 ioctl 控制及逐帧/平面统计。
  控制重演包含全局 S_EXT_CTRLS 更新，不能仅看带 picture 的 request；后者会漏掉
  sony 重复 sequence 的亮度矩阵恢复。
- `pixels-summary.json`、`analysis.log`：输出 SHA、完整长度和 ISO 超容差位置。
- `ffmpeg.py`、`ffmpeg-summary.json`、`*.mbtype.log`、`*.frames.json`：VM FFmpeg
  6.1.1 单线程解码，passthrough I420，以及软件宏块图和显示顺序类型。
  软件 I420 留在 `/home/deepdream/build/vdec-mpeg2/r69/`，未写入参考归档。
- `mb-summary.py`、`macroblocks-summary.json`：首个超容差像素的平面/坐标、16×16
  显示网格位置和 FFmpeg 宏块类型。场编码的全零首图像按完整显示帧定位；未据此
  将两场的压缩宏块地址当成同一个 raster 地址。

比较所有完整显示帧，不截短文件、不寻找任意偏移来凑相等；23 条 fixed 输出的
长度、尺寸和 ISO/FFmpeg 显示帧数均一致。沿用 Fluster `compare_yuv_files()` 的
`abs(pixel-reference) > 2`，没有新增容差。FFmpeg 是辅助定位，ISO 仍是验收判据。

## 四条矩阵对照：4:2:0 的独立色度矩阵不参与反量化

真实 ioctl 逐请求的 quantisation 四组数组按 intra/non-intra/chroma-intra/
chroma-non-intra 顺序比较，以下是不同数组元素累计数；旧/新输入及输出帧数相同。

| 流 | 请求数（各组） | 亮度两矩阵差异 | 色度 intra/non-intra 差异 | 旧/新输出 |
|---|---:|---:|---:|---|
| att | 132 | 0/0 | 8316/8448 | 逐字节相同 |
| sony-ct4 | 78 | 0/0 | 2520/2520 | 逐字节相同 |
| Tek-5-long_conf4 | 150 | 0/0 | 0/9450 | 逐字节相同 |
| ibm-bw | 30 | 0/0 | 1386/1408 | 逐字节相同 |

本内核 `Documentation/userspace-api/media/v4l/ext-ctrls-codec-stateless.rst`
的 MPEG-2 quantisation 定义明确写独立 chroma 数组仅用于非 4:2:0。
本地锁定 ISO 参考源码 `video/decoder/getblk.c` 的 intra/non-intra 两处 qmat
选择也在 `chroma_format==CHROMA420` 时对所有块使用亮度矩阵。
因此四条的结果符合控制语义，不能用它们证明硬件忽略有效矩阵。

两条 sony 的差别不同：重复 sequence 恢复使 sony-ct1 的亮度 intra/non-intra
各 126 个元素、sony-ct2 各 252 个元素发生变化，输出也变化；证实有效亮度矩阵
路径会影响像素。先前 visl 的六条“控制有差异”不等于六条像素失败都由矩阵导致。

`mpeg12_write_headers()` 将控制写成 sequence 的两组亮度矩阵和 picture 的四组
quant_matrix_extension，`mpeg12_prepare_input()` 把它们放在纯 slice 数据前进入
VLD FIFO；场对第一场的头/矩阵保存在 fld_buf，第二场附上自己的 picture 扩展。
GStreamer `decode_slice()` 只复制 slice start code 和 slice，原始头不会再次覆盖它们。
当前驱动不直接逐项写 IQ 表，固件解析这些 MPEG 头；厂商 vmpeg12_multi.c 同样以原始
码流/FIFO 为输入，没有主机 IQ 表加载循环。厂商保存 IQ/解析上下文，当前逐请求
重建完整状态；`CTX_QUANT_MATRIX_OFFSET` 只是上下文布局定义，不能据此新增主机 IQ 写入。

## 首错归类和引用证据

CSV 的首错索引从 0 起。软件宏块图的 `<` 是仅后向预测，`>` 是仅前向预测，
`X` 是双向，第二字符 `-` 是 16×8，第三字符 `=` 是隔行；定义见
[FFmpeg n6.1 mpegutils.c](https://github.com/FFmpeg/FFmpeg/blob/n6.1/libavcodec/mpegutils.c)。
这些是软件解码的编码模式证据，不是假设读到了硬件内部宏块状态。

| 类别 | 代表首错 | 结论 |
|---|---|---|
| 初始单向 B 被拒绝 | sony-ct1/ct2 显示帧 0，MB(0,0)，仅后向预测 | 两条的显示帧 0/1 均为全零，capture timestamp 1/2 带 ERROR；驱动参考查找拒绝是确定性根因 |
| 小幅预测链漂移，15 条 | CSV 中 small-drift | 首错均在 P/B 预测块，12 条最大差 3；nokia6_dual_60/ntr_skipped_v3 为 4，tcela-9 为 6；尚未证明可改的寄存器/固件差异 |
| 较长 P 链累计漂移 | att 帧 5、Y(24,0)、MB(1,0)，前向预测；teracom 帧 3、Y(455,80)、MB(28,5)，前向预测 | att 最大 29；teracom 最大 64，最大误差几乎逐帧增长；不是起始矩阵切换失效的证据 |

sony-ct1/ct2 的 request 0/1 是 I/P 场对，timestamp 0 的 anchor 正常解码；随后
request 2/3 为 B 场对，forward_ref_ts=`U64_MAX`、backward_ref_ts=0。当前
`mpeg12_reference_canvases()` 把不存在的前向参考送入 vb2 查找并返回 -EINVAL，
其位置在启动固件之前。两条恰好只有 timestamp 1/2 的 CAPTURE 带 ERROR，且显示
帧 0/1 全零；其后的最大差都降到 3，仅剩 sony-ct1 7 个、sony-ct2 2 个超容差位置。
因此本次修复旨在消除两帧拒绝，不承诺其余小幅像素差也消失。

厂商 MREG_REF0/1 在 anchor 不存在时写 `0xffffffff`，与微码协议兼容；其有状态
输出端还会丢弃未就绪的早期 B，不能把这条代码当作相同码流已在厂商通过的证据。
stateless 路径应按已声明的预测方向提交，让只需要后向 anchor 的合法 B 正常启动。

FFmpeg 与 ISO 的比较也有边界：部分小差流的软件结果自身存在少数 >2 位置；
teracom 软件/ISO 最大差达 255，且软件解码报告 0 decode errors。因此不以 FFmpeg
替换 ISO，也不凭当前数字把硬件误差自动归为“允许的 IDCT 舍入”。

## topic 修复和验证

内核 topic 为 `/home/deepdream/src/linux-7.3-vdec-mpeg2` 的 `vdec-mpeg2`，
基于 c99c3ed。`mpeg12_reference_registers()` 从真实参考选择路径提取纯寄存器选择：
B 的未声明方向保留无效 canvas；声明但查找失败、B 两方向全缺和 P 没有前向参考仍报错。
不改变场对首场选择、P 两寄存器复制及 DMA/停机生命周期。
新增 KUnit 直接调用实际参考时间戳和寄存器选择函数，覆盖 sony 的后向单向 B、
前向单向 B 以及丢失参考。独立内核提交
`aaec5091f3dc411daba42eb3cb24d3fc254d1937` 的分支尖经 heavy FIFO 1404 验证：
arm64 QEMU KUnit 26/26，清理自身 vdec 对象后 W=1 模块实际重编成功，strict
checkpatch 0 errors/warnings/checks。modpost 仍有 5 条原有 KUnit 模块缺少
MODULE_DESCRIPTION() 的警告，未改动这些测试元数据；本次代码无编译诊断。
主仓库完整回归运行 588 项，OK（14 项跳过）。原始门禁输出均在 `build/mpeg2-r69/`。

## 下一窗清单：仅 6 条

由协调者交给 t3k 合入 integration，同窗一次启动，不由本 worker 排板票。

1. 私有 parser/v4l2codecs/codecs 均固定 r69 的 fixed 组身份，只更换内核 topic；
   跑 sony-ct1、sony-ct2，以及四条 r69 对照 mcp10ccett、sony-ct3、bits_conf_lep_11、
   Tek-5.2_conf4。未受本修复影响的漂移流不重复塞进本窗。
2. 保留完整 I420、ISO 输出、ioctl、QBUF/DQBUF 和内核日志。两条 sony 分别仍需
   60/24 个显示帧；timestamp 1/2 不再有 CAPTURE ERROR，显示 0/1 不再为全零，
   单独量化这两帧的 ISO 误差。其余帧应与 r69 fixed 保持相同像素或先解释差异。
3. 全流继续运行原 ISO 容差判据；若仅剩原先的 7/2 个小差位置，也照实保留 Fail，
   不把“消除了零帧”写成整流 Success。四条对照必须保留通过。
4. 像素 Fail 保存后继续；内核 timeout/WARN/Oops、DMA/停机异常或恢复预算不足
   立即停，由统一窗口恢复正式基线。不因单流失败重启另一候选。
