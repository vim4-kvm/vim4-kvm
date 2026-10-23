# 2026-10-23：Wave5 E02 可见尺寸与 E01 标准控件离线候选

本轮完全离线：未 SSH 板子，未拿 board 锁，未安装/重启/合入已部署分支，
未改 sources.toml/workspace.toml。E02 已实现 selection + 内部 padding + 固件
conformance window 路径，但固件真实 SPS/像素仍待上板；E01 补了标准接口与
参数语义，**尚未完成厂商全能力对齐**。详见
[131 项序列参数映射](2026-10-23-wave5-encoder-controls.md)和
[公共/动态/逐帧协议附表](2026-10-23-wave5-encoder-protocol.md)。

## 分支与实现范围

内核独立 worktree `/home/deepdream/src/linux-7.3-wave5-encoder-parity`，
分支 `vim4-wave5-encoder-parity`，开工 fetch 后以 `0a775305f0ad8` 开始，
交付前再 rebase 到采集修复后的 `b1300eb808f43`。
独立输出 `/home/deepdream/build/kernel-wave5-encoder-parity`；主工作树未修改/切分支。

| 提交 | 内容 |
|---|---|
| aba2a290f9a65 | E02 可见矩形与 HEVC 8 对齐编码尺寸、完整 OUTPUT 高度计算 UV 偏移、已分配缓冲时拒绝改 crop |
| 477434f12c18a | AVC/HEVC 参数独立，flip 可取消，序列建立后改参 EBUSY |
| 7a6ae881d6cb4 | I/P/B QP/上下界、tier、PU split、CQ、CPB、header；修正单位/遗漏字段 |
| 5abf3c372dca1 | 单 B、lookahead 所有权/时间戳/调度；STREAMOFF 先销毁、失败隔离、后续 STREAMON 可重建 |
| 3d691ea1e223f | 帧间隔真实协商值、忙时拒绝重配、OUTPUT 重配清除旧 crop 偏移 |
| f5a0dc6856b1a | CONSTANT_QUALITY 标准 1..100 质量等级、真实控件注册与 cluster 边界测试 |
| 7bebd6b4ae796 | SPS conformance 解析/独立参考 NAL、208 组固定 QP + IDR 命令测试 |
| bc1de9cc74ee9 | 限制 OUTPUT 源索引、校验固件结果索引，避免 32 项时间戳表越界 |
| ded994eb9dd68 | drain 命令拒绝时进入 STOP、归还错误 CAPTURE，避免无源缓冲导致反复调度 |

没有新增私有控件或 uAPI；固件入口的 HEVC 8 对齐检查仍存在。
序列配置失败不会以未校验的物理尺寸进入固件。现有应用端尺寸回退策略未更改，
需要批量上板通过后再让应用使用新 selection 路径，不能把本轮候选当作已上线。

## E02 固件合同与主线规范

以分支内 `Documentation/userspace-api/media/v4l/dev-encoder.rst:147–178,326–370`
为准：CAPTURE 尺寸由驱动返回；OUTPUT S_FMT 描述完整存储布局，CROP 表示
可见矩形。客户端顺序是 CAPTURE 选 HEVC → OUTPUT 设置 RAW 存储 →
S_SELECTION(OUTPUT,CROP) 设置可见区域 → 查询两队列布局并分配缓冲。

1. SDK `encoder_libs_aml 4c38af2b398d` 的
   `multiEnc/vpuapi/enc_driver.c:1222–1228` 只把 HEVC 高度向 8 补齐，宽度直接发送。
   `multiEnc/amvenc_lib/AML_MultiEncoder.c:530–559` 为非 8 对齐高度设置底部 crop。
   这解释旧 1366 宽度路径仍会把非对齐宽直接送入 SRC_SIZE，不能据此断言固件
   不支持非 8 对齐的**可见**尺寸。
2. `enc_driver.c:1380–1381` 的 CONF_WIN_TOP_BOT/LEFT_RIGHT 将四个**像素**偏移
   分别写入两个 16bit 半字；主线 `wave5-hw.c` 使用相同命令字段。
   `vpuapifunc.c:254–339` 为旋转/镜像添加块 padding 并变换 crop，HEVC 无变换时
   保留原偏移。候选复用主线这一计算，不软件改写 SPS。
3. 例如 OUTPUT NV12 为 1376×768、stride=1376，CROP=(0,0,1366,768)，
   SRC_SIZE 发 1368×768，右 crop=2；单平面 UV 从 stride×完整 OUTPUT 高度开始，
   不能从可见/编码高度推算。1440×900 → 1440×904，底 crop=4；
   1680×1050 → 1680×1056，底 crop=6。
4. selection 检查矩形范围、最小尺寸、偶数色度单元、flags 与状态；错误不修改 crop。
   两队列任一已经分配缓冲时，改 crop 返回 EBUSY，避免 CAPTURE 容量与新编码尺寸不符。
   所有补边都位于已协商 OUTPUT 容量内，驱动不另分配/读越界像素，也不保证补边
   像素颜色；客户端必须提供整个协商缓冲，码流可见区用 conformance window 排除补边。

**结论**：有固件参数支持可见裁剪的正面源码证据，本轮没有“固件不支持”的证据。
源码与模型不证明 Wave521C 实际接受本候选宽度/SPS；这一点留给恢复门禁之后的实测。

## E01 与多实例审查

新增标准固定 P/B QP、逐帧型 QP 上下界 cluster、HEVC tier/PU split、5.2 level、
CQ、AVC CPB_SIZE、joined HEADER_MODE、B_FRAMES=0..1。修正 QP 0..51、
merge-minus-one → 固件 1..2、MAX_MB → HEVC CTU、SAO 参数复制。
AVC/HEVC 的 profile/level/filter/QP 不再由另一套控件默认值覆盖。
全局和帧型 QP 范围取交集，非法组合原子失败；CPB/VBV 从 KiB 换成目标码率下
的毫秒，超出固件 10..3000ms 返回 ERANGE，不再直接把 KiB 当毫秒。
CBR/VBR 采用不同默认 VBV 时长，不保证硬 CBR；CQ 的 CONSTANT_QUALITY=1..100
按反向归一化 QP 51..0 选择三个帧型的固定 QP，未使用固件独立 CQ 模式。
其他模式关闭 FRAME_RC_ENABLE 时保留显式 I/P/B QP，不用质量等级覆盖。

多实例仍用共享 V4L2 m2m 调度器，每份参数、force-key 和已提交标记属于实例。
固件 ENC_DELAY 不归还尚未完成的源/目标，不重复提交 held source，并完成本次
m2m job 让其他实例继续；按 enc_src_idx 关联重排后的时间戳。命令拒绝只移除本次
未接受的源，不错误移除队头仍由固件持有的源。job_ready 区分已提交与未提交，
避免没有新输入时空转；drain 仍允许 SRC_END。复位/隔离所有权路径未放宽。
STREAMOFF 即使命令队列为空，也不能直接归还已提交的 lookahead：先 DESTROY
实例；失败转现有隔离保留 DMA。成功后释放旧辅助缓冲、回到 NONE、重置源提交
标记，后续 STREAMON 可重建；OUTPUT 仍在流送时，CAPTURE STREAMON 也会创建实例。
后续 release 不重复 DESTROY。完整 STREAMOFF 和重复 close 有实际 C 路径测试，
实际固件重建和流重启仍须 v4l2-compliance 与生命周期压力测试，不能称完整合规。
边界审查另发现旧时间戳表固定 32 项却无索引检查：现在 OUTPUT 最多 32 个缓冲，
API 再验证输入索引，coded report 的负数/越界源索引返回 EIO，由完成路径隔离，
不读取越界内存；SRC_END 不再覆盖表项。实际 API 的边界用 ASan/UBSan 验证。
drain 命令被拒绝时，即使没有源缓冲也进入 STOP、清空并归还错误 CAPTURE，
不把“无源”当成跳过收尾的条件；之前已接受的 lookahead 仍留待安全销毁。

未完成：运行中改码率/QP/GOP、任意/层级 GOP、多 B、ROI/LTR、custom map、
VUI/HRD/SEI 子集与厂商 NR/代价表。部分已有标准控制可继续实现，部分确实缺
通用 stateful payload ABI；附表逐项区分，不能把全部缺口归咎固件或标准。

## 离线验证

重型编译全程由 Mac `/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build ...`
串行化；未持 board 锁。每个提交归档独立 Wave5 源码快照，调用：

```sh
make O=/home/deepdream/build/kernel-wave5-encoder-parity ARCH=arm64 olddefconfig modules_prepare
make O=... ARCH=arm64 -j4 M=<该提交的Wave5快照> MO=<独立模块输出> W=1 modules
git show --format=email <commit> | scripts/checkpatch.pl --strict --no-tree -
for test in drivers/media/platform/chips-media/wave5/test_*.py; do python3 "$test"; done
```

构建范围是驱动模块，非完整可部署 Image；配置/Module.symvers/vmlinux 来自已有
runtime-recovery 构建，headers 与本基线重新 modules_prepare。没有用它做板级启动。
本机证据保留在 `logs/wave5-parity/`，不会把日志误当源码交付。
既有 isolation/recovery/FIO/IRQ/close/DMA 测试继续运行；新测试执行实际 C 函数，
用 mock V4L2 队列/控件模拟边界，不冒充真实内核锁竞争或 v4l2-compliance 设备实测。
控制测试还编译实际注册代码，检查菜单空洞、范围拒绝、默认设置、cluster 失败回滚、
质量等级单调性与两个实例互不影响。三个负向突变（HEVC 不补齐宽度、恢复共享
codec 参数、重新选择已提交源）均被实际断言拒绝，退出码均为 1。
SPS 测试使用 x265（min-cu-size=8）生成单帧参考流，经 hevc_metadata 设置裁剪，
ffprobe 分别得到 1366×768、1440×900、1680×1050、偏移的 1366×768、旋转的
768×1366；完整 SPS NAL 固定在测试中，再与实际 C 计算比较 coded/crop/visible。
解析器另验证历史 Wave521C 头与截断输入；这不是候选固件输出，不证明实际像素。
未来可离线运行 `test_geometry.py stream.hevc` 读取真实 Annex-B SPS。

最终结果：以上 **9 个提交各自模块编译、全套 Wave5 测试、strict checkpatch 全通过**，
均为 `0 errors, 0 warnings, 0 checks`，W=1 没有编译警告。逐提交构建与测试日志为
`logs/wave5-parity/final-series-build.log` 和 `09-drain-build.log`，三项突变记录为
`mutations.log`，参考流/ffprobe 为 `sps-reference.log`。
功能分支推送 `origin/vim4-wave5-encoder-parity`，HEAD `ded994eb9dd68`；未合入
`vim4-kvm-7.3`。主仓完整 unittest 在原工作区为 223 项、6 skipped、OK；
独立文档 worktree 为 223 项、10 skipped、OK（可选子仓/依赖检查缺少对应工作区而跳过）。

## 后续批量上板窗口（约 50–65 分钟）

统一排队后全程持 board + heavy 双锁，使用
`packaging/kernel-edge/display-once.py` 一次性启动；开始时记录默认基线 commit、
build ID、Image/DTB/module 哈希，备份并核对自动回退，不更新已部署锁。

1. 5–8 分钟：基线 SSH/服务/UDC/HID、候选身份、v4l2-compliance 编码节点与控件/selection
   查询；实际 QUERYCTRL 范围、菜单、busy/错误值返回须与离线预期一致。
2. 8–10 分钟：先跑一轮已有 timeout_command 恢复＋失败隔离兜底，确认持有 DMA、
   超时后多实例 EIO、成功复位后新实例能开。失败即停止尺寸扩展，正常重启回默认。
   真实固件挂死恢复仍未证明，不能把软件超时成功当作无限风险输入的授权。
3. 10–15 分钟：NV12/NV12M、共享 DMABUF offset、单/多平面分别测
   1366×768、1440×900、1680×1050、1920×1080、4K；输入完整缓冲初始化，
   逐像素边缘/动态帧标记核对可见区，不只看 ffprobe 宽高。每个流保存 Annex-B，
   `ffprobe` 和本候选 `test_geometry.py <stream.hevc>` 核对 coded/crop/visible；
   非零 left/top 和 90/270 度各一例。遇到 watchdog/IRQ 异常立即终止本组并回退。
4. 8–10 分钟：RC 开/关/CQ、I/P/B QP 范围、profile/level/tier、header/AUD、slice、
   周期与强制 IDR；单 B 的 I/P/B→I/P/B 重排、时间戳、短流/drain/STREAMOFF。
   多 B/ROI/SEI/运行中改参属于后续实现，不纳入本候选通过项。
5. 10 分钟：两个实例（AVC+HEVC）交错启动/编码/退出，含一路 B、另一路低延迟；
   One-KVM 4K60 动态画面连续编码、HID/UDC、CMA/fd、oops/taint/journal。
   采样不能与其他构建重叠。离线测试不提供 fps/延迟结论。
6. 5 分钟：重启回窗口开始记录的默认基线，核对 build ID、One-KVM/manager active、
   UDC configured、HID 实际可用，释放双锁。未正式部署、未自动合入主分支。

上述是待执行清单，不是完成证据；若非对齐尺寸仍挂起或 conformance 不符，保留
固件入口物理对齐保护与应用现有回退，收集命令/码流后再修复，不能删保护继续试。
