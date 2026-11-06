# 2026-11-06：HEVC 输出过程与单 AU 隔离（批 B）

基于批 A `e0507657c4432d38c8d7dceed341cf30d3e2bc62` 实现最小头解析、
stateful discard、C.5.2 和单 AU 错误隔离。只做离线验证，未碰板或宣称新增流已通过。
仍使用自有 VM `linux-7.3-vdec-fixes` / `vdec-fixes` 和原 O=，不修改批 A 的 T1 补丁。

## 提交与责任边界

| 项 | SHA | 改动 |
|---|---|---|
| K5 | `d0584637cf8a6dea174d0eab46816bb1884a6f51` | hevc_headers.c：SPS/PPS 前缀、首 slice 输出位、EOS/EOB；直接读 feed 同一 CPU 视图。 |
| K6 | `d2d718f1d5ed3f22b478b0517085a00e1e641f5d` | 共享 stateful 消费 OUTPUT/DISCARD，discard 回 ready，不 DONE、不增加显示 sequence。 |
| K7 | `6c2101f02401a64819f5ce5c586c50e7f6ca3d18` | 纯 C.5.2 DPB 输出/丢弃 FIFO；codec/硬件层接入，格式暂停前判 prior output。 |
| K8 | `bc651815ee7d912f58a1c2e3d6348f93189f7077` | 头解析错误和实采零尺寸参数未就绪只影响当前 AU；安全 stop 后 OUTPUT ERROR，队列继续。 |

解析单元只读 Annex-B 起始码、去 EPB、带界 u(n)/ue(v)，按 ID 缓存 PPS/SPS 前缀。
首 slice 快照 no_output_of_prior_pics_flag、pic_output_flag 和最高 temporal sublayer 的
buffering/reorder/latency；同一 AU 尾部的参数更新不倒改快照。后续 slice 不重复处理输出过程。
没有解析 CTU、LT MSB 周期或整个参考语法；不新增映射、码流副本或用户态 ABI。
T7 原 feed 当前只支持 MMAP，解析和 memcpy 共用原 vb2_plane_vaddr 结果，未另做 DMABUF 同步路径。
这次解析是协调者明确批准的固件 RPM 缺字段例外，不扩展为通用软件解析框架。

reviewB 四项修订折回 K5/K7，仍是四提交。非零 nuh_layer_id 和保留的 VCL 类型
10–15、22–31 都跳过，只有0–9、16–21读取 slice 前缀；不因这些 NAL 丢掉主层 picture。
forbidden_zero_bit 和零 nuh_temporal_id_plus1 仍报错，包括非主层 NAL。
新增两例 KUnit，覆盖非主层的截断 PPS/EOS/slice，以及全部保留 VCL 类型放在主层 picture 前后。
K7 fixture 改名 hevc_kunit_traces.h 并加 include guard，轨迹数据不变。
相对初审尖 cb199a63 只有这四项，range-diff 在 build/vdec-fixes/reviewB/rewrite-diff.log。

K7 让每槽 referenced 与 needed_for_output 独立：隐藏图仍可供内部压缩图参考，
CAPTURE 则经 discard 返还 ready。输出/丢弃队列均有 H265_SLOTS 上限，取走 disposition 前不复用槽位。
原 epoch/逐图 reorder_limit 和惰性输出选择已替换，不保留算法切换门。
已决定的输出进入 FIFO 后不会被下一个 IRAP 撤回；prior-discard 只处理仍等待输出的图。

begin_picture 在 RPS 标记后、当前槽分配前处理 C.5.2.2；end_picture 仅在固件确认重建完成且
job 已停止后处理 C.5.2.3。BUFEMPTY 仍不是重建完成。fullness 在解码前参与 bump，
最高层 SPS limits 是输出依据，RPM 重合字段差异只 dev_dbg，不拒绝。
SPS/RPM buffering 不同也不会用 RPM 提前拒绝输出，槽位数采用解析出的 SPS 限制加原两槽余量。

同一 OUTPUT 因初始格式或 DRC 保留重送时，AU 元数据与 picture_started 保持，
不重复推进 POC/RPS/latency/CVS。DRC 的 prior-output 决策先于共享 stateful 的 SOURCE_CHANGE
和旧 CAPTURE 冲刷；内部图片池重建的 DPB 失效归 codec adapter，不再暗藏在 DMA 分配函数中。
EOS/EOB 从整 AU 检测，包括 suffix SEI 后的位置，只标记下一图开新 CVS；
不会立刻冲刷旧图或生成 V4L2 EOS/LAST。V4L2 STOP/drain/DRC 的事件和缓冲顺序仍归 stateful。

K8 的可恢复硬件范围仅为实采 VPSSPSPPS 零 width/height/chroma、参数集未就绪特征。
确认 stop/IRQ 同步成功后，只把当前 OUTPUT 标 ERROR，保留正常待输出图和队列可用性。
尚未被本图占有/写入的 CAPTURE 留 ready；parser 的未知 PPS/截断也只影响该 AU。
RPS 歧义、其它硬件错误、timeout、stop/PM 失败或 fault 仍走原 fatal/quarantine，未放宽。
厂商帧模式依据 `decoder_v4l/h265/vh265.c:11963-11976、12093-12126`，
本轮采用停下当前 job 的既有路径，不新增固件命令，不重注入参数集。

## 规范与离线测试

已取得 ITU 官方 H.265 v3（04/2015），PDF 第279–280页、印刷页257–258的 C.5.2.2/.3/.4。
原始文件 `build/vdec-fixes/batchB/h265-complete.pdf`，SHA256
`31d36b02c4bab2a84bcbd88124db3eb1ae0669a26b34c3e4643e07b712b267b3`，
摘录用于核对，未把 PDF 入库。[官方入口](https://www.itu.int/rec/T-REC-H.265-201504-S/en)。
第一次下载被截断，保留失败文件和日志，不把有 PDF 头当成完整文件。

规范核对纠正了提供模型的一点：PicLatencyCount 只增加在当前图之后输出的待输出图。
生产实现及非零 latency KUnit 按正文；六条目标流 latency 都为零，其既有模型期望不变。

KUnit 直接链接生产函数，测试包括真实 OPFLAG/BUMPING SPS/PPS/slice 前缀、EPB、
最高层限制、参数替换、未知参数、截断、EOS/EOB 的 AU 内位置；纯 DPB 的 FIFO、
IRAP flush/discard、隐藏参考、fullness、latency、连续 CRA/RASL 与新 CVS；
实际 vb2/V4L2 的 discard、全 discard DRC、空 LAST drain、坏 AU 后好 AU 和坏尾 AU 的 EOS。

六条目标流的完整 picture 前缀轨迹在 hevc_kunit_traces.h，由封存输入和提供的 sim.py 生成，
在 QEMU 中调用生产 begin/end/pop，按索引检查模型输出序列，期望帧数同时核对封存 frames.json。
输入及参考 JSON 摘要见 `build/vdec-fixes/batchB/trace-inputs.json`，生成器在同目录。
这些只证明元数据输出过程，不能代替硬件逐帧 MD5；没有向内核复制整个码流或厂商实现。

早期 QEMU 发现一份 BUMPING 测试 SPS 漏抄00，修正后通过；strict 的排版提醒均折回对应提交。
初审尖 cb199a63 的旧四提交经 heavy FIFO1604，53/55/59/62 项通过；保留原始证据。
reviewB 固定上述四 SHA：前两提交经 heavy **FIFO1607**，
后两及尖端配置检查经 **FIFO1609**（票 `7067fa7eab1b40d0950c87a7b94d36a3`），均已 released。
逐提交 W=1 模块、arm64 QEMU KUnit **55/55、57/57、61/61、64/64** 全通过。
完整 format-patch strict 均零 errors/checks；K5/K7 各一条新增文件 MAINTAINERS 通用提醒，
既有目录规则已覆盖，原始退出码保留。正文75列、diff --check通过，作者及签名未改。
尖端测试模块 SHA256 `08a296058cd10aae4d095586269302e46cc8c814d6a0c358bc0806790ae75f05`。

尖端 CONFIG_KUNIT=n、DEBUG_FS=n/y 两配置完整内核链接和 W=1 模块均通过，
模块日志零 warning/error，模块 SHA256 同为
`be0d74c2ad25ec7a1d91570231506292823694f8d79bcc8e55976130cbfa68ea`。
模块/内建均以新版 sparse v0.6.5-rc1-21-g84ec0658 实际 CHECK，驱动范围零诊断；
准备阶段保留既存 VDSO __kernel_getrandom 提醒，不宣称全树零诊断。
测试模块配置四条既存 KUnit 模块缺 MODULE_DESCRIPTION 提醒、kernel-doc 原 node/diag_started
缺注释提醒保留；smatch 未安装。源码目录每提交和最终含 ignored 状态为空，未生成树内产物。
主仓库全套 reviewB 复跑 **608项OK、14跳过**，`logs/vdec-fixes/reviewB/repo-tests.log`。
实际驱动格式枚举配合官方 GStreamer1.24.2 初始事件/EOS/DRC fixture 复跑通过，
`logs/vdec-fixes/reviewB/gst-fixture.log`。首次传错接口层源码的失败日志另存，未改 fixture。

复现脚本 `build/vdec-fixes/validate.sh` 转入 `reviewB/validate.sh`（VM 同构建根路径），
固定上述尖端与批 A 起点，默认逐提交全跑。完整 patches/配置/哈希/序列在 `reviewB/final/`，
汇总 `reviewB/gates.json`，每 SHA 证据仍在 `reports/<SHA>/`。
reviewB 首次 K7 strict 指出头文件 SPDX 须改块注释，已折回；失败日志保留。
所有失败/跳过原始输出保留在 `logs/vdec-fixes/batchB/`、`logs/vdec-fixes/reviewB/`，早期 keeper 拒绝取票也单列，
不以旧尖结果证明新尖通过。以上是离线配置门禁，不是正式整包或实板验收。

## 板验口径与未做项

交协调者/t3k，仍只跑封存输入，不现场改参数：

| 目标流 | 期望显示帧数 |
|---|---:|
| BUMPING_A_ericsson_1 | 49 |
| NoOutPrior_A_Qualcomm_1 | 40 |
| NoOutPrior_B_Qualcomm_1 | 47 |
| OPFLAG_B_Qualcomm_1 | 98 |
| OPFLAG_C_Qualcomm_1 | 96 |
| RAP_B_Bossen_2 | 80 |

每条要求逐帧/整流 MD5、帧数/顺序、Captured status0、LAST 和零 ERROR 全满足。
RAP_B 必须覆盖416×240→448×256及旧图丢弃，不能只看80帧。
VPSSPSPPS 不承诺6/6：只验坏 AU 不终止队列、后续 AU 继续消费，无新增 hang；
逐 AU ERROR、帧数和退出状态如实记录，含错误就不能判整流 Success。

批 A 两条 SLIST、RPS_D改善和原120条 Success不回退；保留全I、三短流5/8/17帧、
RPS_B/E、HEVC56/56、stateless60/60、media8/8及JPEG原窗口判据，事件/STREAMON次数不退步。
原Success退步、新WARN/fault/泄漏、超时或异常状态即停，按既定恢复，不改参考或放宽超时。

LTRPSPS_A、WPP_D、LT MSB周期、参数集重注入仍未做；不以恢复队列掩盖错误输出。
未碰板、未排板票、未push/合并。批 A 的 T1 配套保持原补丁，批 B 另交记录，等待协调者审查。
