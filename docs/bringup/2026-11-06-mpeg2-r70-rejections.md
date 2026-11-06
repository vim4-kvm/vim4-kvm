# 2026-11-06：r70 sony 起始 B 请求拒绝追踪

r70 没有证实“缺失前向参考被换算成旧时间戳”的假设。复用原 arm64 QEMU visl
环境和与板上 SHA 相同的私有库，sony-ct1 的 77 个、sony-ct2 的 30 个 picture
控制均与板上 ioctl 逐字段相同，包括两个失败图像的 `forward_ref_ts=U64_MAX`、
`backward_ref_ts=0`、`picture_coding_type=B`。现有 r70 日志没有返回码或微码
完成状态，**尚不能确定本次失败点，未写新的参考策略修复**。

保留已进入 r70 的 aaec509，在它之上增加独立的请求失败诊断和 KUnit 回归。
这不是像素修复，也不把 sony 的 Fail 改成通过；下一窗须启用动态调试来补证据。

## 证据、控制和来源

只读主工作区 `build/hwdecode-parity/run70/` 的 candidate.tar、身份清单及
`archive/results/mpeg2/sony-ct{1,2}-fixed/`。本工作树 `build/mpeg2-r70/` 保存
`controls.py`、`controls.json`、`controls.log`、模块反汇编、库哈希和门禁原始输出；
新 visl trace 在 `build/mpeg2-visl/r70/`。没有修改 r70 或其他 worker 的环境。

r70 release 为 `.32`，候选源码 `6dd53c32b88975e6f962c65b785581d34e5c223e`。
其 mpeg12.c 与 topic aaec509 完全相同，SHA256 为
`5f5c1766e430a8ae5d1992dcd8f6f2dd0508f50777639c2c07a3e92cc9eccecb`。
还从 candidate.tar 单独解压实际 aml-vdec-drv.ko：`aml_mpeg12_dec_run()`
反汇编 ebd0/ebe0 等分支确认，缺失前向方向会跳过查找，成功解析后向方向后进入
MREG_REF0/1 写入路径；不是只凭源码清单假定补丁已经编入。

visl 使用复用镜像、自己的 rootfs 和脚本，以 heavy 队列运行。parser、
v4l2codecs、codecs SHA256 分别以 `2da88e7a`、`2e21a4ae`、`5668e8fa` 开头，
完整值保存在 `visl-libraries.sha256`，与 r70 tools-manifest 的 mpeg2-fixed 组一致。
两条退出码均为 0，trace 的 overrun、commit overrun、dropped events 均为 0。
比对范围为全部 picture 控制的时间戳、type、structure、DC precision、f_code 和
所有 flags；本次没有重新声称验证了所有 sequence/quantisation 字段。

下表两条流相同；时间戳列使用 ns，tv_usec=1/2 对应 1000/2000 ns，不能混用单位。

| 请求序号，从 0 起 | OUTPUT timestamp | type / structure | forward_ref_ts | backward_ref_ts | r70 完成 |
|---|---:|---|---:|---:|---|
| 0 | 0 | I / bottom | U64_MAX | U64_MAX | 暂存首场，OUTPUT 成功 |
| 1 | 0 | P / top | U64_MAX | U64_MAX | I/P 合并解码，CAPTURE index 0 成功 |
| 2 | 1000 | B / top | U64_MAX | 0 | 暂存首场，OUTPUT 成功 |
| 3 | 1000 | B / bottom | U64_MAX | 0 | OUTPUT 和 CAPTURE ERROR |
| 4 | 2000 | B / frame | U64_MAX | 0 | OUTPUT 和 CAPTURE ERROR |

GStreamer 1.24.2 私有源码的来源链如下，未修改用户态：

- `gst-libs/gst/codecs/gstmpeg2picture.c:272` 的
  `gst_mpeg2_dpb_get_neighbours()` 按 picture order count 选前/后邻居。
- `gstmpeg2decoder.c:856` 调用它，把邻居原样交给子类 `start_picture()`。
  第一个已解码 I/P anchor 的 system_frame_number 为 0；两个更早显示的 B
  没有较早 anchor，只有这个较晚 anchor。
- `sys/v4l2codecs/gstv4l2codecmpeg2dec.c:623` 在 prev 为 NULL 时直接写
  `GST_CLOCK_TIME_NONE`，即 U64_MAX；没有经过时间单位换算。next 非空时使用
  `gstv4l2decoder.h:37` 的 `GST_CODEC_PICTURE_TS_NS()`，frame number 乘 1000，
  得到这里的后向参考 0。picture type 来自当前 picture 的解析结果。
- 首场通过 HOLD_CAPTURE，次场作为 subrequest 使用相同 frame number/timestamp；
  因此 ts=1000 的两个 B 场不是两个独立显示图像。

## 拒绝路径核对及其证明边界

| 路径 | r70 已有证据及边界 |
|---|---|
| request/control validate | S_EXT_CTRLS、MEDIA_REQUEST_IOC_QUEUE 均成功。type=3、structure=1/2/3、DC precision=0/1/2 均在核心校验范围内；不是 ioctl 入队时被拒。 |
| 首场暂存/场配对 | 请求 2 OUTPUT 成功，HOLD 与下一请求的 timestamp/相反 structure 正确；同样失败的请求 4 是完整 frame，因此场配对不能单独解释两次失败。内存分配和执行态仍没有现场返回值。 |
| timestamp 0 查找 | CAPTURE index 0 先完成，在两次错误完成前未重新 QBUF。`v4l2_m2m_buf_copy_metadata()` 设置 timestamp 及 copied_timestamp；`vb2_find_buffer()` 对所有分配的缓冲查找，不限制 queued/done 状态。新增 KUnit 验证零时间戳和未解码零缓冲的区分。不能把此离线测试当作板上 canvas 写入已成功的证明。 |
| 参考寄存器选择 | 实际 B 控制在 aaec509 下选择一个参考：MREG_REF0 保持 0xffffffff，后向 ts=0 查到的 canvas 进入 MREG_REF1。两个方向都缺失或已声明方向查找失败仍为 -EINVAL；没有发现触发放宽该校验的新控制值。 |
| prepare / payload / canvas | prepare 只安装 IRQ 回调，无错误返回。run 内仍可能因输入准备分配、尺寸/有效载荷检查或 canvas 配置失败而返回错误；原日志没有记录是哪一支。 |
| 公共 worker | 控制安装、buffer pins、core reset、firmware load 都可能先于 codec run 失败。后续帧继续成功且无 timeout/隔离日志，不支持持续 fault，但无法由此排除一次性错误。 |
| 微码完成 | PIC_DONE/SEQ_END 带 PICINFO_ERROR 或 DATA_EMPTY/DATA_REQUEST 均返回 -EIO；这和主机 -EINVAL 在现有 V4L2 ERROR trace 中不可区分。没有 MPEG-2 timeout 日志，两次错误也未耗尽 500ms，但不能据此推定中断状态。 |

厂商 `vmpeg12_multi.c:3543` 对缺 anchor 写 0xffffffff，aaec509 保持此协议；
厂商还有上下文恢复及早期 B 的输出丢弃逻辑。因此它不证明新启动的微码一定能
解码相同的单向 B，也不支持在没有现场失败点的情况下复制后向 anchor 到两寄存器。

[r69 分析](2026-11-06-mpeg2-r69-analysis.md) 依据旧代码定位的“双参考强制查找”
缺陷仍成立；它不能解释 aaec509 已编入后 r70 的持续 ERROR。之前没有微码状态，
不能把“缺前向参考”继续当作这次请求失败的确定性归因。

## 诊断提交和离线验证

内核 topic `/home/deepdream/src/linux-7.3-vdec-mpeg2` 的 `vdec-mpeg2` 仍从
c99c3ed 派生，保留 aaec509；新增独立提交
`1c711971d464cff398183e5873686f46b9161a09`，不 amend 已进入 integration 的旧提交。

- `mpeg12.c` 的拒绝路径记录原因、返回码、请求 timestamp、type/structure、
  forward/backward timestamp；区分参考不存在与 canvas 配置失败，微码错误记录
  BUFFEROUT、PIC_INFO 和 ERROR_COUNT。成功路径和错误策略不变。
- 公共 worker 仅在 MPEG-2 失败时记录 control setup / buffer pins / core reset /
  firmware load / codec run 的阶段及请求 timestamp；日志为 dev_dbg。
- 新增 KUnit 使用实际观察的 B 场对及 B frame 参考值，通过真正的
  v4l2_m2m_buf_copy_metadata()/vb2_find_buffer() 检查 timestamp 0 可解析，以及
  anchor 重用后旧时间戳必须失效。它不模拟硬件中断或证明微码已通过。

分支尖 strict checkpatch 为 0 errors/warnings/checks；arm64 QEMU KUnit 27/27。
W=1 模块经 heavy 队列在独立 MO 输出目录编译；原有 5 条 KUnit 模块缺少
MODULE_DESCRIPTION 的 modpost 警告保留。原始输出和产物哈希在 `build/mpeg2-r70/`。
初次切换 MO 因源目录留有此前构建的对象而拒绝；已保存失败日志、清理自身对象，
随后在 VM 原生文件系统保留最终构建日志并复制回来。

## 下一窗：两条 sony 加两条对照

交给协调者/t3k 的 integration 清单仅 sony-ct1、sony-ct2、sony-ct3、mcp10ccett。
固定 r70 mpeg2-fixed 用户态库，仅合入诊断提交；本 worker 不排板、不操作板子。

1. 启用 mpeg12.c 和 `m2mops_vdec_device_run` 的 dynamic debug，确认规则启用后再跑。
   例如向 dynamic_debug/control 写入以下两行，测试后撤销相同规则（改为 -p）：

   ```text
   file mpeg12.c +p
   func m2mops_vdec_device_run +p
   ```

2. 保存完整内核日志、ioctl 控制、QBUF/DQBUF、完整 I420 和 ISO 输出。sony 分别应
   有 60/24 个显示帧；对齐 ns=1000/2000 的 run/rejected/completion 日志，不仅看
   tv_usec=1/2 的 ERROR。若是 reference rejection，须保留具体 forward/backward
   lookup/canvas 原因；若是 microcode completion，须保留 out/info/errors。
3. 两个对照须继续通过原 ISO 容差。sony 全流保持原判据，单独列出显示帧 0/1
   的零帧、首错和最大差；显示帧 2 以后逐字节对照 r70。诊断提交预期不改像素，
   ERROR 和零帧消失反而需要解释，不预先承诺 sony 通过。
4. 两条 sony 若仍 ERROR 但没有任何对应诊断，先保存证据并停止本子任务；核实
   模块身份和动态调试开启状态，不继续用静默 ERROR 拟合参考策略。像素 Fail
   保存后继续其余清单；timeout/WARN/Oops、DMA/隔离异常立即按统一窗口判停。

尚未完成的是 r70 的确定性运行时失败点及相应功能修复：visl 无 Amlogic 微码，
现有板上 trace 不含该信息。本次没有访问板子、push 或继续 IDCT 拟合。
