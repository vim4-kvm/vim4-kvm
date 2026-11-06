# 2026-11-06：r71 单向 B 微码失败与参考 canvas 候选

r71 已确定 sony-ct1 的两次失败发生在微码完成路径，主机没有拒绝控制或参考查找。
两条 sony 的对应 B 图像均逐宏块确认没有前向预测；在 ISO 解码器中把未使用的
前向参考指向后向 anchor，两条完整输出仍逐字节等于归档 ISO。基于这些证据提交
一个窄范围候选：只给缺少前向参考的 B 填上有效 REF0，REF1 和解码参数不变。
**候选尚未上板，不能声称消除了微码错误或整流 Fail。**

## 现场失败点及错误计数的边界

只读证据为主工作区 `build/hwdecode-parity/run71/archive/results/mpeg2/`
`sony-ct1-fixed/kernel.log`、完整输出及 ioctl；release `.33` 含 1c711971 诊断。
必须查每条流目录内的 kernel.log，不能因 run 根 kernel.log 没有诊断就提前判停。
本窗 ct2、ct3、mcp10ccett 没有执行，以下不能作为它们的 r71 板上结果。

| OUTPUT timestamp，ns | 图像 | REF0 / REF1 | BUFFEROUT | PIC_INFO | ERROR_COUNT | 结果 |
|---:|---|---|---:|---:|---:|---|
| 0 | I/P 场对 | ffffffff / ffffffff | 1 | 00000000 | 0 | 成功 |
| 1000 | B top/bottom 场对 | ffffffff / 00050504 | 2 | 00000000 | 226 | -EIO |
| 2000 | B frame | ffffffff / 00050504 | 2 | 00000000 | 10 | -EIO |
| 3000 | P frame | 00050504 / 00050504 | 1 | 0001f000 | 0 | 成功 |

日志顺序为 canvas 0/4 配置成功、run、IRQ、`microcode completion ret=-5`，
公共 worker 的 stage 为 codec run。由此排除本次的 prepare、控制安装、输入准备、
场配对及 canvas 查找拒绝；实际失败点是 `mpeg12_threaded_isr()` 收到
`MPEG12_DATA_EMPTY`（2）后调用 `mpeg12_job_done(ctx, -EIO)`。
PIC_INFO=0 没有 PICINFO_ERROR 位也不改变这个分支，-EIO **不是由 226/10 的阈值产生**。

厂商 `vmpeg12_multi.c:81` 定义 `MREG_ERROR_COUNT=AV_SCRATCH_C`，`:3599–3607`
只把非零值打印为 err_cnt 并清零；本驱动每次 restore 同样清零，然后由微码更新。
可见主机源码没有它的单位、增量条件或位域定义，锁定的 video_ucode.bin 是二进制，
没有可核对的微码源。因此这里的确切含义只能定为“本次微码运行的错误计数/报告值”，
不能称为错误宏块、坏 slice、缺参考次数或错误像素数；226/10 也不能据此定位宏块。
DATA_EMPTY 只说明这次输入耗尽而没有完成图像，尚未证明微码内部哪一步不能接受无效 REF0。

厂商 `vmpeg12_multi.c:2562` 在 `refs[0]==-1` 时丢弃早期 B，`:3438` 把这种状态的
decode_timeout_count 设为 1。它的 `:3543` 无效 canvas 写法不是成功解码这种 B 的
证据；r69 对厂商写法的兼容性推断不能升级为微码支持证明。

## 按位流解码的完整宏块统计

从锁定 ISO 参考源码复制到自己的 VM `r71-reference`，仅在解码后记录 picture
及 macroblock_type，在 skipped_macroblock() 派生方向后统计，再进入运动补偿。
`MACROBLOCK_MOTION_FORWARD=8`、BACKWARD=4、INTRA=1；这是熵解码后的位流语义，
没有用画面相似性或单个首错宏块推断整个图像。逐地址检查无空洞/重复，数量与尺寸一致。
本轮没有修改 IDCT、量化、运动向量、场选择或参考像素。

| 流 | 请求 / 显示图像 | 宏块总数 | intra | 仅 backward | 仅 forward / 双向 | skipped（已含在前述总数） |
|---|---|---:|---:|---:|---|---:|
| sony-ct1 | ts1000 top / 显示 0 | 154 | 1 | 153 | 0 / 0 | 0 |
| sony-ct1 | ts1000 bottom / 显示 0 | 154 | 1 | 153 | 0 / 0 | 0 |
| sony-ct1 | ts2000 frame / 显示 1 | 308 | 1 | 307 | 0 / 0 | 30 |
| sony-ct2 | ts1000 top / 显示 0 | 660 | 5 | 655 | 0 / 0 | 3 |
| sony-ct2 | ts1000 bottom / 显示 0 | 660 | 7 | 653 | 0 / 0 | 4 |
| sony-ct2 | ts2000 frame / 显示 1 | 1320 | 9 | 1311 | 0 / 0 | 0 |

所有 skipped 宏块均继承后向方向。准确说，这些图像包含 intra 和仅后向预测宏块，
不是“每个宏块都做后向运动补偿”；没有宏块从缺失的前向 anchor 采样。
既有 trace_headers 还确认两条首 GOP 均为 closed_gop=1、broken_link=0，anchor 的
temporal_reference=2，随后 B 为 0/1；不能把这两帧当作开放 GOP 随机接入时应丢弃的图像。

## ISO 反事实实验和期望输出

先在原语义下重解码，再仅对 picture index 2/3/4 的运动补偿临时令
`forward_reference_frame[c]=backward_reference_frame[c]`，调用后恢复指针。
两种输出均与 r70 归档 ISO 全流逐字节相同：sony-ct1 60 帧、sony-ct2 24 帧；
r71 sony-ct1 的 ISO 全流哈希也相同。没有替换参考帧像素、改变容差或删掉起始图像。
这验证了统计及软件层面的无影响结论，不模拟 Amlogic 微码的控制流。

首两帧期望为下列完整 I420，尺寸分别为 352×224、704×480：

| 流 / 显示帧，从 0 起 | ISO 字节范围 | SHA256 |
|---|---|---|
| sony-ct1 / 0 | 0–232 | cca05e9cfa9f7b8b435029bd92131922c11b1cd2522a90d47b70b2d423be801c |
| sony-ct1 / 1 | 0–226 | 89e374c6337167091fcbce6093737045ec3bb482a9a3268d5d31b5167bd6699d |
| sony-ct2 / 0 | 2–230 | d065121c2701eb09fe0fd5bd25f016466255dfa5a691307fe90fb933f8bbb110 |
| sony-ct2 / 1 | 7–222 | 4bb697f3c11c1f3f9df27c5b363cca69bc9ad63b2d97f26dea8ff867147a1b70 |

哈希用于固定参考身份；硬件验收仍按原 ISO 容差逐像素比较，不要求硬件与 ISO 哈希相等。
ERROR 缓冲可能残留非零数据：r71 sony-ct1 首帧有 384 个非零字节，次帧全零。
因此以 ERROR 和逐帧参考差为准，不把“两帧必须全零”作为诊断条件。

## 候选的正确性范围和风险

规范预测对后向宏块只读取 backward anchor，intra 不读取任何外部 anchor；修改未使用
的 forward canvas 不改变预测样本、插值舍入、残差或场奇偶。这对上表全部宏块严格无影响，
也经完整 ISO 输出实验证实。内核仍解析真实 ts=0 的后向缓冲，只把已解析的 canvas 编号
同时写给 REF0，没有新增缓冲、复制图像或让目的缓冲充当参考。

未证实的是微码内部是否只检查 canvas 有效性，还是还依赖保存的解析上下文。
有效 REF0 是有依据的最小候选；它仍可能 DATA_EMPTY 或产生错误像素，须保留真实错误返回。
若实际位流需要不存在的前向 anchor，别名属于错误隐藏，不能证明一致性解码正确；
驱动不做完整宏块熵解析，仍依赖用户态正确声明参考，不能把本候选解释为恢复缺失的图像。
已声明但无法解析的参考继续 -EINVAL，不用另一个方向掩盖查找失败。

内核提交 `743d43ff09d195a6121ac2edfdeb8944893b0daa` 在 aaec509 和诊断提交之后独立
提交，保留既有评审/上板历史。仅改 `mpeg12_reference_registers()` 的缺前向 B 分支；
I/P 场对、P 参考复制、两个已声明 B anchor 的方向、仅前向 B 的行为均保持原样。
KUnit 更新实际 top/bottom 场对及 frame 控制的两个寄存器期望，并确认双向 anchor
仍独立、声明后丢失仍拒绝。分支尖经 heavy 队列：arm64 QEMU KUnit 27/27，独立
O=/MO= 目录 W=1 模块实际重编成功，strict checkpatch 0 errors/warnings/checks；
保留 5 条原有 KUnit MODULE_DESCRIPTION modpost 警告，改动代码无编译诊断。

原始统计、源码插桩副本、分析脚本、哈希和验证日志在本工作树 `build/mpeg2-r71/`；
VM 私有源码/输出在 `/home/deepdream/build/vdec-mpeg2/r71-reference/`，门禁原始日志
在 `/home/deepdream/build/vdec-mpeg2/r71-validation/`，已复制回本工作树。
厂商和 ISO 原源码、输入、r69/r70/r71 归档均只读；未碰板、排板票、push 或使用子代理。

## 下一窗：sony-ct1/ct2/ct3 + mcp10ccett

由 t48/t3k 合成一个 integration，固定 r70/r71 的 mpeg2-fixed 三库，只加本候选。

1. 启用 `file mpeg12.c +p` 和 `func m2mops_vdec_device_run +p`，保存**各流**完整
   kernel.log、完整 ioctl、QBUF/DQBUF、I420 和 ISO。核对模块身份及调试规则生效，
   不再只查 run 根 kernel.log。按此顺序跑四条，不增加其他漂移流。
2. 两条 sony 分别要有 60/24 个显示帧。ts=1000/2000 应出现 REF0=REF1（r71
   canvas 为 00050504，按本次实际编号核对），完成应为 PIC_DONE/SEQ_END，无
   PICINFO_ERROR，OUTPUT/CAPTURE 均不带 ERROR；原样记录 ERROR_COUNT（期望 0）。
   若仍 DATA_EMPTY/ERROR，候选未解决；不能把错误计数下降当作通过。
3. 显示帧 0/1 对 ISO 单列每平面首错、最大差和 >2 像素数，四条全流均跑原判据。
   不能以“错误帧消失”改写整流结果；sony 的其余历史小差仍可能保留 Fail。
   显示帧 2 以后逐字节对照 r70/r71；ct3、mcp10ccett 全流应保持原像素和 Success。
4. 若候选仍有相同 DATA_EMPTY，不继续现场试其他参考替换；保留完整证据后结束本子任务。
   timeout、WARN/Oops、DMA/隔离异常立即按统一窗口判停；普通像素 Fail 保存后继续。
   不忽略 -EIO、不把错误缓冲标成功，也不把厂商丢弃早期 B 当作一致性通过。

本轮交付的是有软件语义及现场失败依据的候选，不是硬件验收结论。
