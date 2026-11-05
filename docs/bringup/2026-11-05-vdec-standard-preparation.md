# 2026-11-05：解码标准验收离线准备

本记录记录离线构建与工具验证。后续首轮候选在 U-Boot 读 Image 时异常，未进入
候选 Linux，已恢复正式基线，见[启动记录](2026-11-05-vdec-debug-boot.md)。
标准码流硬件结果、带流 compliance、5.15 对照及性能全部未运行。
[验收合同](../vdec-validation.md)描述入口，[KUnit 结果](2026-11-05-vdec-kunit-results.md)
记录前置迁移，不把这些证据合并成硬件验收通过。

## 调试候选

源码 `e6f9f06b06d3765148ae6a271c64d8482a175531`，树
`c2642863a77ac3d8b1cdf5b1f6b99ad847629159`。正式配置叠加
[调试片段](../../packaging/kernel/vdec-debug.config)，olddefconfig 后确认要求的
KASAN generic、kmemleak、PROVE_LOCKING、DEBUG_ATOMIC_SLEEP、DMA_API_DEBUG 均开启。
完整配置 SHA256 `16e40afca3bc9019d1c7379268ea23ea36dfbc781444abf45f9cab16b4be47bc`。

独立构建 `Image dtbs modules` 通过，使用 GCC 13.3.0；配套 kbase 外部模块也从同次
配置与 BTF 构建。候选 release `7.3.1-vim4-20261105.22`，build ID
`9244e6c734b7cac00d9b38c7d09bb494295d055b`。没有修改正式来源锁或已验收配置。

| 产物 | SHA256 |
|---|---|
| Image | `3939de3e65e55466c641867b7f30c69cf346ef331ea94643aa855e602bfce2d1` |
| 整包 manifest | `f223bc7dc015a44b6b15c69badb9a2a17e86dfb92753e744016dd9ff80e71e53` |
| 整包归档 | `96f8da994e0a46a4ce7c14f4e0bc73c24860449c05b6f64533050bd98ffc8195` |
| RAM candidate.tar | `6d1755a59626e072066e5e467cb7f3b55f50e6a48260ca73bad338376d8c6b85` |

VM 产物为 `/home/deepdream/build/hwdecode-parity-bundle-debug/`；原始构建、打包输出
在主仓库 `build/hwdecode-parity/debug-config.log`、`debug-build.log`、
`debug-package.log`。尚不能宣称零 splat/零泄漏，必须实板运行之后判断。

为构建释放空间时只清理本任务旧包中已逐文件与归档校验一致的模块展开目录和重复
modules.tar.gz；保留整包、调试符号、RAM 归档与身份清单。校验证据为
`bundle-cleanup.jsonl` 和 `bundle-cleanup.log`，没有删除其他任务产物。

## 标准工具与输入

[Fluster 锁](../../packaging/kernel/vdec-fluster.toml)固定
`45d6dca42398305ac3a3ad9a0712028a2d08d97a`。在 ARM64 宿主实际运行 `list -c`，
记录 `fluster-host-list.log`；无板端视频节点时硬件解码器显示 KO，仅证明实际名称。
HEVC 在两版内核都选 V4L2 stateful，H.264/MPEG-2 在 7.3 选 V4L2SL。

计划测试集为 JVT-AVC_V1 135、JVT-FR-EXT High 45、JCT-VC-HEVC_V1 147、
MPEG2_VIDEO-MAIN 43、MPEG2_VIDEO-422 9，共 379 条。原文件的 SHA256、选择条件
及期望数量均在锁中；没有 JPEG 套件，继续使用已有 MJPEG 样本并注明边界。
H.264 的 180 条全部通过源校验；HEVC 只有 54/147 条通过，其余 93 个请求实际
收到 ITU `Request Rejected` HTML，不能作为 ZIP 使用。保留下载输出与响应头；
没有改发布者摘要或绕过校验。`--seal-cached` 从校验正确的缓存重新提取可用输入，
把所有缺失项及收到的文件摘要保留在清单中，但不把它们打进可执行输入。
H.264/HEVC bundle manifest SHA256 为
`027edb11a650cfcedee87a6df2c4418d5f44d081d0266f3c1652fecc0dc049ca`，归档 SHA256
`5110980ef12c4c999ad11c309f08e4274a8a1436b15db8d1ecac643c3a75da1b`。
原始输出为 `fluster-avc-hevc-prepare.log`、`fluster-avc-hevc-seal.log`，完整下载日志
在 VM bundle 的 `download.log`。单独重试仍得到 HTML，记录 `itu-retry.log`；
响应头保留在 VM tools 的 `itu-response-headers.txt`。以上是首次封存状态，补齐结果如下。

用户随后提供慢速逐个下载的 93 个 ZIP。当前板窗结束、基线及视频恢复后，重新逐个
核对发布者 MD5，再导入新的缓存；没有覆盖先前封存包。`--seal-cached` 已确认
HEVC **147/147**、JVT-AVC_V1 **135/135**、High **45/45** 全部可用；连同 MPEG-2
52 条，计划输入 **379/379** 已就绪。此计数仅指输入，不是硬解通过数。

最新目录为 VM `/home/deepdream/build/hwdecode-parity-fluster-avc-hevc-complete-v2`，
manifest SHA256 `eebc3e7202bfe35ce0d0a65506145a9d65bbae75b785b8334ad76bb054177772`，
归档 SHA256 `6b00986ed4ddba213f413c83c01a7bd6d4e392d01ee028416cd657eda9cabed4`。
封存后独立复核 504 个列出文件和归档内相同文件的 SHA256，均通过；两版对照应改用
此完整输入包。原始输出为 `hevc-local-import-v2.log`、
`fluster-avc-hevc-complete-v2-seal.log`、`fluster-complete-verify.log`；逐 ZIP 来源与
摘要保留在新目录的 `local-import.json`。

导入时 VM 直接读 Mac Downloads 阻塞，封存被提前启动，曾产生可用输入为零的
`complete` 清单；它未上板且不作为验收输入。终止阻塞进程后先复制至工作区，等待
93 条导入成功再顺序封存为 `complete-v2`。失败输出保留在
`fluster-avc-hevc-complete-seal.log`，不覆盖或隐去该次失败。

MPEG-2 的 52 条已由宿主校验后封存，最新 bundle manifest SHA256
`f4fbdfb634e776da8a48162a49954111faad289bcbec42b1b75c749453c39378`，记录
`fluster-mpeg2-reseal2.log`。首次下载期间增加参考软件锁，导致旧清单中的锁摘要与
快照不一致，因此未交板；重新使用校验后的缓存提取并封存。重试还发现一个真实
路径冲突：套件根的候选文件名恰好等于逐码流目录名。准备器已只删除存在的文件，
实际重试通过；没有增加映射或样本生成测试。

用户授权接受 ISO 协议，仅本地验证。参考软件归档 SHA256
`ba372c4069e9c96d0675e1442dbcb5a9c7f46d8ca760866bd51f185641ba759e`，由锁定
Fluster 的视频 Meson 配方编译，二进制 SHA256
`a7378621dcea43939087c846d1d7f486085429fef6c53526469e8d2ec582e776`。
实际 `list -c -d MPEG2_VIDEO` 显示 ISO-MPEG2-VIDEO OK；日志
`mpeg2-reference-download.log`、`mpeg2-reference-build.log`、
`fluster-mpeg2-list-reference.log`。源码与二进制不入库或发布。

独立工具链实际运行一次 FFmpeg 软件解码 `MPEG2_VIDEO-MAIN/att`，上游 ISO 像素
比较报告 Fail、986 个违规像素；保留 `fluster-reference-run.log` 和
`fluster-reference-result.json`。新结果解析器实际读回 Fail，见
`fluster-actual-result-parse.log`。这是工具与参考比较的负结果，不是 T7 结果，
也不是把 FFmpeg 当作新 oracle。

v4l-utils 固定检查源码 `d2e89246cefcb6371425361b12c4ca2a36a662d2`，私有编译
v4l2-compliance/v4l2-ctl，版本输出为 `1.33.0-1`。前者 SHA256
`80245c17cc93906fa4a505cbe684ac861f5213555ffd11cb7de9d0d4d6ba7289`，后者
`7671e7ea2bcc46644a060d9dd16134d728348e4885dd504e7b69722d82050c3f`。
构建及版本日志为 `v4l-utils-source.log`、`v4l-utils-build.log`、`v4l-utils-identity.log`。
上游 `utils/v4l2-compliance/v4l2-test-buffers.cpp:2767` 的 stateless 分支收到
ENOENT 后停止 Request 带流测试，因此不能声称 `-m -s` 覆盖了实际 stateless 出帧；
带流输出与跳过项仍须实录，再由 Fluster 检验完整解码。

## 工具验证及待验边界

`vdec-window.py` 增加基于验证计划的 compliance、fluster、performance 动作，
保留默认离线、显式执行、manifest、watchdog 与队列，并复用 board-window 基线恢复。
逐码流保存原始 JSON/日志及未运行状态，超时杀整个子进程组，首错停止。
主仓库只新增三个工具失败路径检查：缺失结果不算通过、超时后不运行下一条、
真实子进程收到终止信号；22 项窗口检查通过，未新增驱动 Python/mock 测试。

`vdec-benchmark.c` 使用真实 GStreamer fakesink 统计帧、丢帧、CPU 和时间，
`-Wall -Wextra -Werror` 编译通过；ARM64 宿主实际跑了三秒非同步管线、三秒同步
管线及提前 EOS 负例，前两项成功、最后一项按预期失败。保存
`vdec-benchmark-host-validation.log`。这些是测量程序集成检查，不是硬件性能或
十分钟播放验收。板上时钟、KVM 接收重叠、两版内核同策略对照均未运行。

主仓库离线全量检查实际 534 项、跳过 11 项，通过；原始输出
`repo-tests-vdec-standard-tools.log`。本轮无 DT binding/DTS 改动。
HEVC 原有超时仍未关闭：另已发现 frame-based 启动时 ACTION_DONE/WAIT_FLAG 与
5.15 协议不符，候选模块修正正在等待实板，未提交，不能记为已修复。
