# 2026-11-05：H.264 场缓冲生命周期与隔行候选

按[隔行设计](2026-11-05-vdec-interlaced-design.md)完成四个独立准备提交，再单独
开放隔行入口。各提交均实际运行离线检查；正在准备生产配置 `.27`，尚未上板，
不能据此宣称隔行像素或缓冲释放已经验收。

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
开放入口的首次提交正文换行触发 checkpatch 警告，修正文后重跑通过；未推送前
仅修正提交正文，没有改写前四个提交。

原始输出在 `build/hwdecode-parity/interlaced/`：四个提交分别为
`series-{1..4}-kunit.log`、`*-qemu.log`、`*-result.json`、`*-module.log`、
`*-builtin.log`、`*-source.sha256` 和 `*-commit-style.log`；入口提交为
`enable-*`。完整未拆草稿先跑过 25/25，随后逐提交重新运行，未以最终组合的
结果冒充中间提交可构建。

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
完整 coded 帧导出、逐行/多 slice 对照、MBAFF/field/PAFF 子集。按本轮协调要求
首错即停；未跑项单列，结束恢复 `.3` 并验证原 KVM 视频。输入沿用宿主封存
归档，板端不下载；本轮上传归档核对后删除。

## CVFC1 的一次性证据工具

不修改 GStreamer 插件。锁定的 1.24.2 `gstv4l2codech264dec.c` 在下游支持
VideoMeta 时使用原 CAPTURE；`gstv4l2codecpool.c` 将驱动输出 vinfo 写入 meta。
`build/hwdecode-parity/interlaced/capture-full.c` 提供一次性 sink，要求完整 coded
尺寸和 NV12 元数据，将 352×288 全部编码像素重排为 I420，仅去掉行 padding。
它已用 `-Wall -Wextra -Werror` 编译，尚未证明实板能导出。

`vdec-window.py` 的可选 `capture_probe` 在 compliance 后运行该工具，沿用
manifest、逐文件 SHA、超时、内核告警检查与恢复；没有新增另一套占板流程。
导出必须有 50 帧和完整文件长度。宿主一次性脚本 `compare-cvfc1.py` 从 `(26,60)`
裁出 300×168，与参考 I420 逐字节比较，并保存每帧结果与首个差异位置。参考
文件 MD5 已与 Fluster 的期望值一致，但目前没有完整硬件帧，**尚不能把 CVFC1
登记为驱动通过**。工具和分析脚本仅放 build/，不作为仓库测试或私有插件维护。
