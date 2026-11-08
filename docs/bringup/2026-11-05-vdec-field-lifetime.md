# 2026-11-05：H.264 场缓冲生命周期与隔行候选

按隔行设计完成四个独立准备提交，再单独
开放隔行入口。各提交均实际运行离线检查；生产配置 `.27` 在 r48 完成 stateless
compliance，HEVC streaming 超时后停止并恢复 `.3`。r49 解耦 HEVC 后，六条隔行中
四条通过、两条仍像素失败，三条对照全部通过；CVFC1 完整帧按正确偏移裁剪后
50 帧逐字节相等。尚未重跑 H.264 全集，不能宣称完整隔行或逐行回归验收完成。

## 提交与验证

| 内核提交 | 改动与原因 | arm64 QEMU KUnit |
|---|---|---|
| `4995c03778a02` | CAPTURE 首次使用时编号，held 第二场复用编号；ERROR 清 HOLD；解码前复制 metadata，保证 IRQ 中能用当前 timestamp | 22/22 |
| `7b8761bea26f6` | canvas/MV 按 timestamp 识别图片；held IDR 第二场保留首场槽位，零 timestamp 有效 | 23/23 |
| `7b9eb755691ee` | 每条参考项独立填充地址；合成场视图结合原始布局与 fields，保留各项 POC | 24/24 |
| `d61578110f3a4` | 场 PicNum/LongTermPicNum 按奇偶和 frame_num wrap 计算；限制列表扫描范围 | 25/25 |
| `02a3b188757e5` | 去掉逐行 SPS 限制；每个参考列表独立按 32 项检查，仍保留 16-picture DPB 和 8-bit 4:2:0 限制 | 25/25 |

每个提交分别通过 W=1 模块/内建构建、有效 sparse、format-patch strict
checkpatch；修改头文件也运行 kernel-doc。vdec 无诊断，内建前置仍有既有的
arm64 `__kernel_getrandom` sparse 声明告警。没有 DT binding 修改，smatch 未安装。

原始输出在 `build/hwdecode-parity/interlaced/`：四个提交分别为
`series-{1..4}-kunit.log`、`*-qemu.log`、`*-result.json`、`*-module.log`、
`*-builtin.log`、`*-source.sha256` 和 `*-commit-style.log`；入口提交为
`enable-*`。完整未拆草稿先跑过 25/25，随后逐提交重新运行，未以最终组合的
结果冒充中间提交可构建。

## 候选身份

复用注册的 `vdec-sequence` 工作树和 O=，快进到已提交的入口 HEAD 后构建。
`interlaced/candidate-build-resume.log` 保存完整构建、封包及私有模块核验输出；
`run48/artifact-identity.json` 保存 VM 来源与 Mac 副本的哈希/长度核对。

| 产物 | 实际身份 |
|---|---|
| release | `7.3.1-vim4-20261105.27` |
| Image build ID | `4cb47d45df4f5852d76502231f533958837a71db` |
| 配置 SHA-256（与正式配置一致） | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA-256 | `bf67e6a1fe8708f93a961c2fe59c01e6866c466809ce5d04aca5edab784cb302` |
| 整包 manifest SHA-256 | `017b26d81b42646c6cd199127dcb89e52c20b412df6074f8999812a4fb63e5e7` |
| RAM archive SHA-256 | `a1701fa1cd87989427dfa9feb1586d4e4e7fa62e6f9c5db41e7230db5dc820cd` |
| 私有模块 build ID | `5334b469c8b6ad7f2a26f6d7217ee2435efa748d` |
| 私有模块 SHA-256 | `f3bd823b44c2928c6ea5ab8d6842164331b49d402c57c513a6b4e713741c1a72` |

私有模块的 vermagic、基础 revision、Image build ID 与上述包匹配；差异严格
限定为下文所述 HEVC 草稿，封包后的候选源码已恢复干净。输入归档、JPEG 流和
一次性导出工具均核来源 SHA 后写入窗口计划，板上再次逐文件核对。

新增 KUnit 调用真实槽位分配/清理、参考视图选择、场编号和重排函数，覆盖
held IDR、timestamp 零值与大值、槽耗尽、inactive DPB、原始布局保持和负数 wrap。
没有新增 Python/mock 驱动测试；HOLD/FLUSH、DMA 生命周期和 V4L2 队列语义留给
实板 streaming compliance 与标准码流。

## HOLD 与参考视图边界

沿用 7.3 实际存在的 `v4l2_m2m_buf_done_and_job_finish()`、核心 timestamp 不一致
释放，以及 `v4l2_m2m_ioctl_stateless_decoder_cmd()` 的 FLUSH。当前树没有
`v4l2_m2m_release_capture_buf()`，未另建场队列。预先编号使核心直接释放 held
缓冲时已有 sequence；错误时清 HOLD，避免失败场滞留。

固件继续解析码流。内核只使用 stateless 控制和固件返回的 slice 信息。
同一 timestamp 的两个场共享 canvas/MV；DPB 的 top/bottom 两个参考项分别
填充，不能再只找第一项或整项复制 L0 到 L1。

厂商 `h264_dpb.c:dpb_combine_field()` 合成 frame view 时仍置 `coded_frame=0`。
因此合成帧仍使用 field MV 布局；相反，原生 frame/MBAFF 的场视图保持原始
MV 布局。`h264_reference_structure()` 将原始结构与所选 fields 合并后编程。

## `.27` 的范围与窗口计划

H.264 结论只引用已提交的源码 HEAD
`02a3b188757e5ece5a0670681bab43d662d9d271`。候选配置保持正式 `kernel.config`，
不含调试片段或 debug-splat 修复；只能证明功能/像素，不能替代零告警调试内核验收。

为复用已运行的三节点 compliance 路径，另外构建与 `.27` Image 匹配的私有
解码模块，仅 HEVC 文件有差异：**未提交草稿，仅用于 compliance 节点**。
草稿 diff SHA-256 为
`158cde0d2ef95e16117f4b1e889ae0405af390e4b63ae8fe2b13e4131b3d3f12`。
不加入新的 ACTION/reset 实验；原生整包和私有模块分开记录，不能把草稿算作
H.264 的已提交实现。构建、传输和运行身份由 `run48` manifest/哈希记录核对。

按 FIFO 使用一个目标 15 分钟的窗口：三节点 streaming compliance、CVFC1
完整 coded 帧导出、逐行/多 slice 对照、MBAFF/field/PAFF 子集。普通 Fluster
像素 Fail 继续收集；Timeout、内核异常、设备不可用或 compliance 进程异常时
停止收尾，未跑项单列。结束恢复 `.3` 并验证原 KVM 视频。输入沿用宿主封存
归档，板端不下载；本轮上传归档核对后删除。

## r48 实板结果

原始结果在 `logs/hwdecode-parity-r48/validation-fluster-1793892700936879000/`，
完整板端目录在 `build/hwdecode-parity/run48/board-upload.tar`。其中
`results/compliance/results.json` 与各节点原始日志保留实际退出码。

| 项目 | 结果 | 边界 |
|---|---|---|
| stateless media | 8/8，退出 0 | media 接口 |
| stateless streaming compliance | 60/60，0 warnings，退出 0 | MMAP/no-poll/select/epoll 有 CAPTURE；不证明隔行像素 |
| JPEG streaming compliance | 汇总 60/60，0 warnings，退出 0 | 日志另有 `Unknown header ID`、`plane size is too large (18144 > 6144)`；输入存在限制，不能按汇总声称有效 JPEG 像素验证 |
| HEVC streaming compliance | 退出 1，没有总计 | `v4l2-test-buffers.cpp(1738): ret == 0` |
| CVFC1 完整 CAPTURE | 未运行 | 前面的 HEVC 触发窗口停止 |
| Fluster JVT-AVC_V1 子集 | 运行 0/10，未运行 10 | 没有像素 Pass/Fail 或逐码流 Timeout 结论 |

HEVC 原始内核日志为 `timeout, irq_status 00 status 00 pc 00000a1d shift 00000072`，
随后 `VDEC power state uncertain; retain lease until system reset`。这是私有草稿
的固件超时，按窗口级错误立即收尾，不算 H.264 失败，也不在本轮重试。
结束诊断另存 `end-diagnostic-error.txt`；没有将诊断不完整写成检查通过。

未运行清单：`AUD_MW_E`、`BA1_Sony_D`、`BA1_FT_C` 三条对照；
`CAMASL3_Sony_B`、`CVFI1_Sony_D`、`cabac_mot_picaff0_full`、`cama1_vtc_c`、
`Sharp_MP_Field_1_B`、`Sharp_MP_PAFF_1r2` 六条隔行；`CVFC1_Sony_C`。
其中 BA1_FT_C 在 `.26` r47 已转为通过，本轮不能用更早 `.25` 的 Fail 作为对照状态。

恢复后 release、build ID 和正式文件哈希均与 `.3` 基线匹配。Mac 实际接收
3840×2160 H.265，5.004 秒解码 299 帧，59.75 fps；新增丢帧、冻结、丢包均为零。
原始记录为 `returned-baseline-identity.json`、`returned-video.log`。
本轮上传共 533 个文件，Mac 归档逐文件 SHA 核对，再复核板端未变后删除
`/var/tmp/hwdecode-standard-r48`，见 `run48/board-upload-files.json` 和
`upload-cleanup.log`。未修改正式启动配置。

后续 r49 复用 `.27`，先运行 capture_probe，再运行上述十条 Fluster；不重试
HEVC，不重建内核。普通像素 Fail 继续收集，窗口级错误仍停止并恢复。

## r49 隔行子集与对照

原始结果在 `logs/hwdecode-parity-r49/validation-fluster-1793893158785852000/`。
`results/vector-*.json` 与 `results/fluster-followup-*/vector-*.json` 保存 Fluster
原始 JSON；`window-status.json` 为流程成功、conformance 未全通过，不能混为一谈。
同一已提交 H.264 HEAD、Image、私有模块和配置均沿用上表。

| 码流 | 以前结果 | `.27` r49 | 说明 |
|---|---|---|---|
| AUD_MW_E | Success | Success | 逐行对照 |
| BA1_Sony_D | Success | Success | 逐行对照 |
| BA1_FT_C | `.26` Success | Success | 多 slice 对照 |
| CAMASL3_Sony_B | Fail | Success | MBAFF、多 slice |
| CVFI1_Sony_D | Fail | Success | field、多 slice |
| cabac_mot_picaff0_full | Fail | Success | PAFF |
| cama1_vtc_c | Fail | Success | PAFF/MBAFF，含负 bottom POC 偏移 |
| Sharp_MP_Field_1_B | Fail | Fail | 待离线定位，不能归因固件 |
| Sharp_MP_PAFF_1r2 | Fail | Fail | 待离线定位，不能归因固件 |
| CVFC1_Sony_C | Fail | Fail | 套件仍 Fail；独立完整帧证据证明驱动输出正确，见下节 |

选定 10 条全部运行：**7 Success、3 Fail、0 Error、0 Timeout、0 未运行**。
普通 Fail 后继续执行到最后一条，内核日志未发现 BUG/WARNING/Oops 或解码超时。
这仍是生产配置功能结果，不替代调试内核锁与内存检查。全集其余 125 条本窗未运行；
不能将本次增量与旧版本结果拼成 `.27` 全集通过数。HEVC/JPEG 本窗未运行。

恢复 `.3` 的完整身份核对通过，Mac 5 秒实际解码 302 帧、60.36 fps，
3840×2160 H.265，新增 dropped/freeze/lost 均为 0。612 个上传文件逐项归档核对后
删除，见 `run49/board-upload-files.json`、`upload-cleanup.log`。本任务复用的 O=
和驱动目录共清理 11,712 个 `.o`，保留 Image、模块和包，详见 `object-cleanup.json`。

## CVFC1 的一次性证据工具

不修改 GStreamer 插件。锁定的 1.24.2 `gstv4l2codech264dec.c` 在下游支持
VideoMeta 时使用原 CAPTURE；`gstv4l2codecpool.c` 将驱动输出 vinfo 写入 meta。
`build/hwdecode-parity/interlaced/capture-full.c` 提供一次性 sink，要求完整 coded
尺寸和 NV12 元数据，将 352×288 全部编码像素重排为 I420，仅去掉行 padding。
它已用 `-Wall -Wextra -Werror` 编译，并在 r49 实际导出完整 50 帧。

`vdec-window.py` 的可选 `capture_probe` 在 compliance 后运行该工具，沿用
manifest、逐文件 SHA、超时、内核告警检查与恢复；没有新增另一套占板流程。
导出必须有 50 帧和完整文件长度。宿主一次性脚本 `compare-cvfc1.py` 从 `(26,60)`
裁出 300×168，与参考 I420 逐字节比较，并保存每帧结果与首个差异位置。参考
文件 MD5 与 Fluster 的期望值一致。工具和分析脚本仅放 build/，不作为仓库测试
或私有插件维护。

r49 的 `capture-probe.json` 记录退出 0、50 帧、7,603,200 字节。完整硬件输出
`run49/full-capture.i420` SHA-256 为
`b5d8caf13f7b4cebc3736a23ebf79584c216c05fd415d71ad1fe853e70d657fe`。
宿主 `run49/cvfc1-compare.json` 记录 **50/50 帧逐字节相等**，裁剪后 MD5
`9fdb17e17d332b5d9752362c9c7ff9b0` 与参考相同，没有差异字节。
同一完整帧改从 `(0,0)` 裁剪得到 `d2aeaea0b9da3509442377a849cc2ff1`，
恰好复现套件错误值。因此登记为**驱动通过、套件 Fail**。

用户态版本由 [GStreamer 源码锁](../../packaging/kernel/vdec-gstreamer.toml) 固定。
1.24.2 的 `sys/v4l2codecs/gstv4l2codech264dec.c`：`new_sequence()` 第 897–899 行
只取 crop 宽高；`copy_output_buffer()` 第 1036 行起从原点复制，不处理 crop 偏移。
一次性 sink 通过 VideoMeta 保留原 CAPTURE；没有修改该插件，也没有改变标准套件结果。
