# 2026-11-05：HEVC stateful 接口与首次码流

接续 [核心电源与时钟](2026-11-05-hevc-core.md)。独立 HEVC 节点的
v4l2-compliance 已通过，但首次码流在固件握手阶段超时，没有输出帧。
本记录不表示 HEVC 解码或 EOS 端到端行为已通过，更不表示完成 5.15 格式对齐。
后续主要验收证据改用 fluster 标准一致性码流；自制样本只作补充。

## 实现与离线检查

保留原作者导入 HEVC codec，再接入有界停机、IRQ 同步和共享调度器。完整
Annex-B 由固件解析，因此使用标准 stateful HEVC 接口；原有 H.264/MPEG-2
仍使用 stateless requests，JPEG 保持独立节点。没有引入私有 RPS 控制。

首遍只解析参数并通知 SOURCE_CHANGE，停机后分配参考帧，应用准备 CAPTURE
后继续该输入。NV12M 两平面各自满足 SAO 写入容量；显示帧按 POC 排序，已非
参考但尚未输出的帧继续持有缓冲。IRQ 只唤醒工作线程，确认 DMA 停止后才
交还缓冲。停机不确定仍保留既有隔离行为。当前只接入八位 4:2:0 输出；Main10
明确拒绝，不能把截断低两位当作支持十位。多切片、长参考、动态分辨率和
多实例尚未通过实板码流验证。

独立修正参数移位边界、均匀 tile 边界、缺失参考帧误用 POC 0，以及负 POC
回绕与 prevTid0Pic 更新条件；后一项核对了
[FFmpeg HEVC 实现](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/hevc/hevcdec.c)。
EOF 修复后实际 C 函数回归共 49 项通过，模块构建与 strict checkpatch 通过。
这些主机测试不能证明固件重建图像正确。新增第二路中断的 binding example、
dt_binding_check 和编译后测试板 DTB schema 检查通过，日志为
`build/hwdecode-parity/hevc-irq-checks.log`、`hevc-irq-dt-final.log`；工具曾有
非致命 jobserver 警告，不称整段日志无警告。

关键源码提交：

- `5b5764a94ddc05bfcd343d6db2ad3009f904f534`：codec 停机与参数边界。
- `4ea5b9b8c8d39c8524d24090f678946122626f10`：stateful 队列及显示顺序。
- `8c94ee343220cebc8f208097daf2308fd5a04c76`：EOS 订阅和最后缓冲后的事件。

## 第二十九、三十轮

两轮均使用完整私有 build 21，Image build ID
`f48d32fab3e617545c28afde8e458565039e6a56`，源码为上述 stateful 提交；原始
vmlinux SHA-256 为 `45c6ab2b621a11fc7b1ab39f99921751b5dc22e2fe81a64e58c04de1cede9820`。
保持正式默认启动与版本锁，沿 RAM 候选入口测试，未向正式模块目录安装。

第二十九轮先通过 HEVC 电源与固件检查。HEVC compliance 为 **46/47**，零警告；
唯一失败是未支持 EOS 事件订阅，按首错退出，没有运行解码样本。

第三十轮使用同 Image/BTF 的 EOS 修正模块，build ID
`7f7356dd16c1144ab23a8cfe1da07489c72de042`，SHA-256
`0032a285a835a6c4881a8c006a56bc46ed151d5d2ea54ecaffd8e515cc3d43da`。
HEVC、H.264/MPEG-2、JPEG 三个节点均 **47/47**，各零警告。GStreamer 实际
发现 `v4l2h265dec`，但首个 256×256 全 I 帧样本在首帧等待超时，输出 **0/16 帧**。
内核记录 status `00`、PC `00000a1d`、已移入字节 `00000064`；采证时 HEVC
IRQ 计数仍为零。故障点尚未定位，不能凭这些值断言固件或中断哪一侧有错。

随后 P 帧、B 帧及本轮既有格式像素回归均未运行。没有继续试第二条码流，未把
接口通过当作解码通过。EOS 完成顺序目前只有离线测试证据；实板仅证明订阅
接口符合检查要求。5.15 同板对照、fluster 标准码流和长期 KVM 共存尚未运行。

两轮均正常重启恢复正式 build 3、完整文件证明和原应用。恢复后的五秒 4K
H.265 接收分别为 59.96、59.57 fps，无新增丢帧、冻结或丢包；两簇 performance、
UDC configured、管理器与 One-KVM active，taint 保持 4096，无新增 Oops/WARN。
未发生新的意外冷复位，但不据此关闭此前冷复位问题；没有改变节能策略。
五秒接收只证明恢复，不是延迟或长期性能验收。

原始证据在 `build/hwdecode-parity/run29/`、`run30/` 及
`logs/hwdecode-parity-r29/`、`hwdecode-parity-r30/`；保留 compliance、首条码流
失败、IRQ、内核日志、模块身份与恢复视频计数。主仓库离线检查 531 项通过，
11 项按环境跳过。

## 启动握手与输入 FIFO 离线候选

当前 hwdecode-parity 基准为 `e6f9f06b06d3765148ae6a271c64d8482a175531`。
hevc.c 保留未提交改动，等待用户通知独立启动 splat 修复分支就绪后联合构建和实板
验证，详见[调试启动交接](2026-11-05-vdec-debug-boot.md#启动-splat-修复交接)。
第 31、32 轮均未运行标准流，不能证明这些候选解决了原来的首帧超时。

本次读取厂商 common_drivers `563cff9dab2c8cd44590bf57c8ffaa7e2dae35e1`：

| 候选变化 | 厂商证据与原因 |
|---|---|
| 新 AU 的 WAIT_FLAG 为零；启动微码前写 ACTION_DONE | vh265.c:14152、14268；fresh frame-based 输入无无效前缀，启动需要释放命令握手 |
| 输入结束地址为 exclusive end，写指针按 8 字节对齐 | utils/vdec.c:1985、1993，utils/vdec.h:76；旧代码减一且写指针不对齐 |
| 分配量多保留一个 FIFO 字，避免填充恰好占满整圈 | 厂商对环尾写指针做回绕；本驱动每 AU 使用独立缓冲，保留空位使读写指针不会重合为“空”。16 KiB 填充与厂商一致，不解析输入 |
| 设置 endian 后先使能 FIFO，再启用取流 | utils/vdec.c:2312–2333；旧代码先启用取流，顺序与厂商不同 |
| 超时同时记录缓存 IRQ 状态和实际 DEC_STATUS | 原 status 00 只是缓存 IRQ 值；没有 IRQ 时不能据此推断固件实际命令状态。仅增加既有具名寄存器读数 |

原始逐行源码摘录在 `build/hwdecode-parity/hevc-input-vendor-evidence.log`。
这些是源码协议差异及待验修正，不是已证明的超时根因；后续需标准流实际出帧、
原始 Fluster 结果、带流 compliance 及干净的调试日志，才能提交行为修复。

离线实际验证：strict checkpatch 零 error/warning/check；模块和内建均完成 W=1、
有效 sparse，日志包含 hevc.c 的 CHECK；arm64 QEMU 现有五套 KUnit **17/17**。
本轮 KUnit 只证明已有纯逻辑回归未坏，不覆盖 FIFO、微码握手或像素正确性。
无头文件、DT binding/DTS 改动，未运行 smatch（未安装）。原始输出为
`hevc-input-checkpatch.log`、`hevc-input-module.log`、`hevc-input-kunit.log`；
当前补丁、模块身份与 KUnit JSON 保存在 `build/hwdecode-parity/debug-input/`。
该模块只对应原 `.22` Image/BTF；合入独立修复后的新候选必须重新构建，不能沿用。
