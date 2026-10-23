# 2026-10-23：Wave5 E01 动态参数、LTR 与多层 GOP（离线）

继续 [E01 参数审查](2026-10-23-wave5-encoder-controls.md)，本轮完全离线，未 SSH、
重启或安装板子。动态参数、单槽 LTR、多 B／分层 GOP 已有候选实现；**E01 尚未全部完成**。
ROI、任意 GOP 图、VUI/HDR 的接口与固件证据边界见
[元数据与 ABI 附表](2026-10-23-wave5-e01-metadata-abi.md)。

## 基线与实现范围

内核独立 worktree `~/src/linux-7.3-wave5-encoder-parity`，功能分支
`vim4-wave5-encoder-parity`。开工 fetch/rebase 后基于
`origin/vim4-kvm-7.3 = 1d80e6ccc364161425714c9f7e07f48769b52f41`；
该提交已包含此前正式分支的编码器修正。未修改内核主工作树、未合入正式分支，
未更新 sources.toml、workspace.toml 或已部署锁。

厂商参数合同仍为 encoder_libs_aml
`4c38af2b398d00a906c26aa166d630a9f73d3f9e` 下 `multiEnc/`。
5.15 `vpu_multi.c` 负责 MMIO、IRQ 和 DMA，实际编码命令在 SDK 的
`vpuapi/enc_driver.c`，不能从内核 ioctl 名称推断 V4L2 控件能力。

| 项目 | 本轮实现与边界 |
|---|---|
| 动态参数 | 下一次 M2M job 前发送 CHANGE_PARAM，独立等待／消费变更报告。支持码率、VBV/AVC CPB、QP 区间、I QP／质量、GOP/刷新周期、重复 headers、AVC PPS 控制、HEVC 受支持的 PPS/RDO 控制、slice MB 数／模式；AUD 和固定 P/B QP 直接用于后续图片命令。 |
| 动态帧率 | 保持 EBUSY。此前“运行中已有帧率调整”与实际源码不符：原先仅 FORCE_KEY_FRAME 可运行中设置；本轮没有冒用 COMMON 重初始化充当动态帧率。 |
| 多 B | B_FRAMES 扩展至 0..7；0/1 保留原 preset，2..7 生成最多 8 项 CUSTOM_GOP，P 锚点先编码，随后 B 帧引用前后锚点。Baseline AVC／HEVC still-picture 不允许 B。 |
| 分层 B/P | 标准 H264/HEVC hierarchy 控件，最多 4 层，内部生成引用图；B 层数要求 B_FRAMES+1 为相应二次幂，P hierarchy 要求 B_FRAMES=0。支持逐层 QP，序列建立后这些结构控制 EBUSY。 |
| 任意自定义 GOP | 未公开任意 POC/ref 图的私有控制；现有标准 hierarchy 控件表达上述受限结构。任意图需要新的标准 compound ABI，见附表。 |
| LTR | 标准 LTR_COUNT=0..1、FRAME_LTR_INDEX=0、USE_LTR_FRAMES mask=0..1。mark/use 绑定下一张真实源图片，排空不消费，命令拒绝则保留；不开放多槽或与重排／分层 P 的组合。 |
| ROI、VUI/HDR SEI | 本轮没有接通生产路径；已补 HDR SEI 解析验证，不能据解析器通过声称固件已经输出 HDR。 |

## 动态命令合同与生命周期

`vpuapi/include/vpuapi.h:3412–3427` 定义 CHANGE_PARAM 组位；
`vpuapi/enc_driver.c:2188–2400` 的 `Vp5VpuEncParaChange()` 给出打包。
候选只使用已确认且有标准控制的组：PPS bit0、INTRA bit1、bitrate bit8、RC bit9、
I QP bit10、P/B QP bit12、independent slice bit16、RDO bit18。
RC change 只更新 HVS 和 VBV，不能借它切换 frame/CU/MB RC 模式。
BACKGROUND_DETECTION 的 enable bit 不在动态 BG 写入中，仍静态；
intra refresh、profile、level、tier、布局、RC 模式、SAO/SPS 组合也保持静态。
层级 bitrate、NR、RC weight、custom lambda 等没有在本轮额外暴露，不能称所有
厂商动态字段均已映射。

`vpuapi/vpuapi.c:1227–1231` 对 ENC_SET_FRAME_RATE 返回
RETCODE_INVALID_COMMAND，EncChangeParam 的 enable mask 也没有 frame-rate 组。
同一 switch 对旧 ENC_SET_BITRATE 也拒绝，但码率有另一个明确的 CHANGE_PARAM
bit8 合同；这正是两者不能一概而论的原因。S_PARM 仍只在实例建立前协商。

`AML_MultiEncoder.c:2385–2415` 将 reconFrameIndex=-4 作为独立参数变更报告，
不当作视频图片。候选在无图片报告尚待读取的 job 边界提交变更，等待有超时的
SET_PARAM 完成，再 GET_RESULT 并验证 -4；错误报告触发现有隔离，超时继续走
现有设备恢复框架。正常命令拒绝／其他变更失败给两条 VB2 队列设 error，并停止
该实例，submitted source 仍保留至 STREAMOFF 成功销毁固件实例。

S_CTRL 只在 control-handler 锁下修改每实例请求值／dirty mask；device_run 在相同
锁下生成快照。setter 不取 irq_lock，避免与 IRQ/device_run 的锁顺序反转。
成功才更新 active open_param；失败不提交影子配置。当前 job 使用旧配置，后续 job
使用最新合并配置；不是 Media Request API 的逐 QBUF 参数绑定。

运行中 CPB/VBV 提交前检查 KiB→毫秒的范围，避免返回成功后才因非法时长停流。
GOP/刷新周期须与当前 GOP 长度整除，结构变化需 STREAMOFF。

## GOP 与 LTR 合同

CUSTOM_GOP 的寄存器字段／8 项上限来自 `enc_driver.c:1118–1159`；
COMMON 必须是初始化最后一条 SET_PARAM。候选先发送有界 CUSTOM_GOP ACK，
失败立即返回，不发送 COMMON；其后沿用主线 sequence-init 完成处理。
SDK `enc_driver.c:2723` 起的校验要求引用已编码、参考 temporal_id 不高于依赖帧。
分层 B 按层从锚点向中点生成；分层 P 按显示顺序生成，参考同组先前低层锚点，
SDK `AML_MultiEncoder.c:157` 起的 svc 表提供相应上游之外的厂商行为证据。

[TI Wave5 参考实现](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/tree/drivers/media/platform/chips-media/wave5/wave5-hw.c?id=c1c8d6fad88e20ce43320f4914bf8891963af478)
也使用 CUSTOM_GOP→COMMON，但 pic word bit13 是 use_multi_ref_p；
T7 SDK 同一位置附近是 numRefPicL0<<12。候选对 legacy 固件明确写单引用 bit12，
当前 ABI 保持 single-reference-P 默认，不复制错误的 multiref 位。

标准层数语义来自内核 `Documentation/userspace-api/media/v4l/ext-ctrls-codec.rst`：
AVC LAYER 为层数 1..4，HEVC LAYER 为最高层索引 0..3（0 为普通编码）。
AVC LAYER_QP 使用高 16 位层号／低 16 位 QP；HEVC 使用 HIER_QP 与 L0..L3_QP。
层级 QP 启用时不再发覆盖它的逐图片统一强制 QP。QP 受帧型最小／最大范围检查。
运行中固定 P/B QP、CQ 覆盖项返回 EBUSY；QP cluster 在提交前拒绝排除现有层级 QP
的范围，保留旧值，不等到下一帧才让流报错。

LTR 的 SPS bit21 与 PIC_LONGTERM bit0/1 来自
`enc_driver.c:1237–1254,1931`、`vpuapi.h:4286–4287`。
此前附表“缺通用 stateful LTR ABI”的结论有误：
`include/uapi/linux/v4l2-controls.h` 已有三个标准控制，
`drivers/media/platform/qcom/venus/venc_ctrls.c:289–318,650–662` 与 Iris 是现有实现。
FRAME_LTR_INDEX / USE_LTR_FRAMES 有 EXECUTE_ON_WRITE 语义，重复写同一索引仍可请求。
USE_LTR_FRAMES 为 bitmask，注册 step 必须为 0。
use=0 清除仍在 pending 的 use；device_run 已取走的请求属于当前源帧，队列暂拒后
仍保留供同一帧重试。需要严格逐 QBUF 绑定时还需独立设计 Media Request 支持。

## 离线验证与提交

| 提交 | 内容 |
|---|---|
| `31c2e06e603c8` | 帧间 CHANGE_PARAM、独立完成报告及错误处理 |
| `2f15138981fcb` | 标准单槽 LTR、一次性 mark/use、重试／drain 所有权 |
| `401ab4479d19b` | 多 B、分层 B、CUSTOM_GOP 与 legacy ABI |
| `847ba16824ba7` | 低延迟分层 P 和 active GOP 周期检查 |
| `8836de38efd10` | AVC/HEVC HDR SEI 离线解析与异常输入测试 |
| `858bcc0a596db` | LTR／GOP／QP 组合在固件命令前验证，延后变更失败测试 |

六个提交逐一 git archive，在独立 O= 配置下、各自独立 MO= 目录，以
`ARCH=arm64 -j4 W=1 modules` 构建，并各运行全部 10 个 test_*.py：全部通过。
最终 ELF Machine 为 AArch64。只编译 Wave5 模块，未生成 Image／可启动部署包。
strict checkpatch 六次均为 `0 errors, 0 warnings, 0 checks`，没有忽略检查。
主仓全套测试在 db5479c：232 tests、10 skipped、OK。更新到 fc2300b 后复跑出现
1 个无关失败：其他任务的 vdec-vendor-live.md 超过 12 KB；本轮两篇记录均低于上限，
未修改他人文件。命令为 `python3 -m unittest discover -s tests -p 'test_*.py'`。

```text
Wave5 28 multi-B/hierarchical GOP graphs, boundaries and LTR combinations passed
Wave5 deferred changes: coalescing, queue wakeup, DMA retention and instance isolation passed
Independent x265 HDR SEI parsing agrees with ffprobe (BT.2020/PQ, MDCV and CLL)
```

最终模块 SHA256 `ad93098eef7fe7134854c915b190816924c30bb0d3266665ad13862e61ea8a97`。
原始日志、配置与 x265/ffprobe JSON 保存在忽略目录 `logs/wave5-e01/`。
快照验证脚本首次漏带公共测试头，补入 videobuf2-core.h／iopoll.h 后重新完成六轮。
已推送 fork，HEAD `858bcc0a596db61740ba05c9f69b5d9b15a097bc`。

按要求删除旧 Wave5 构建包、snapshot、临时工作树：Mac 原 build/ 目录约 1.54 GiB，
另有已结束的应用 worktree；VM 旧输出约 1.08 GiB，最终 O= 约 0.52 GiB 也已删除。
Mac build/wave5-e01 已删除；保留源码与日志。

测试是执行提取的真实 C 函数的受控 harness，不等同于板上 v4l2-compliance。
覆盖注册类型／范围、codec 控件隔离、QP cluster、状态门禁、动态参数失败回滚、
变更报告独立消费、LTR 标记重试／drain、GOP 引用先后与 temporal 层级、两版寄存器
打包、未使用 slot 清零、命令超时边界，以及既有 DMA 回收／隔离／恢复测试。
`test_geometry.py` 的 SPS、HDR SEI 是历史样本／独立语法向量，不是本候选实测输出。

## 下一次批量上板计划（约 55–70 分钟，不在本轮执行）

按 [部署门禁](../subsystems/deployment.md#内核开发流程与部署门禁) 执行。
构建在上板前完成并记录 Image/DTB/modules 同批身份；若基线已推进先 rebase、重跑
离线测试。性能采样全过程用 Mac lockf 先 heavy 后 board，两锁覆盖对应测试组。
若需要再次 rebase，依门禁另外安排九类全量回归；本表 55–70 分钟仅含 Wave5
针对性测试与冒烟，不包含全量回归或完整 Image/modules 构建。

1. 5 分钟：读取入场 build ID／默认启动文件哈希、服务、UDC/HID、isolated/taint，
   确认 PID 1 看门狗；display-once.py prepare/stage/preflight，一次性启动候选。
2. 10 分钟：720×400 AVC/HEVC 无 B，运行中交替码率 2/4 Mbps、QP 区间、固定 QP、
   GOP 30/60、slice、AUD、重复 header、FORCE_KEY_FRAME；记录 S_CTRL、DQBUF、
   IDR 间隔／QP／NAL。验证非法 CPB/GOP 被拒后继续编码，静态控制 EBUSY。
3. 15–20 分钟：B=2/3/7，分层 B=2/3/4 层、分层 P=2/3/4 层，独立 QP；
   用解码器检查引用无错、POC/DTS/PTS 与帧数；HEVC 另查 SPS 子层数和 NAL temporal_id。
   对 GOP 中间强制 IDR、不满 GOP 的 drain、重复 STREAMOFF/ON、两实例交错各做
   不少于 10 次。
4. 8–10 分钟：LTR_COUNT=1，先编码并 mark，再 use；重复写 index=0，use mask=0
   取消未提交请求。必须有丢帧／参考依赖观测或可控内容实验，不能只凭 ioctl 成功
   声称使用了长期参考。确认 B+LTR、分层 P+LTR、不支持的索引均被拒绝。
5. 8–10 分钟：一实例做动态变更，另一实例稳定编码；在 SET_PARAM 注入超时，
   验证现有恢复／失败隔离和旧缓冲生命周期，新实例恢复正常。记录恢复耗时与日志。
6. 5 分钟：One-KVM 4K60、画面／一路编码／HID/UDC，无新增 oops/taint。
   重启回默认基线，再核对入场身份、服务与 USB；清理一次性候选并释放两锁。

ROI/VUI/HDR 的生产支持尚未接通，不计入上述正向验收；附表列出下一候选需要先补的
合同与对应独立窗口。通过前不合并、不正式部署。
