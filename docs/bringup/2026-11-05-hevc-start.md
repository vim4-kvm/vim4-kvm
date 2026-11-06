# 2026-11-05：HEVC 首次启动序列离线对照与待测清单

本任务仅离线分析、修改和验证；没有访问板子。t48 提供的 r69 结果见下文，
HEVC 首帧正确画面仍待实板证明。
接续 [stateful 首次码流](2026-11-05-hevc-stateful.md) 和
[bit21 单变量实验](2026-11-05-vdec-full-conformance.md#hevc-bit21-单变量实验)。
协调者 t48 审查，t3k 合成 integration 候选并统一跑板窗，本任务不排板。

## 对照范围与证据

基线为 `c99c3eddea02823a6b958d16e35ec7d7fd0ccc0d`，VM 工作树
`/home/deepdream/src/linux-7.3-vdec-hevc`，topic 为 `vdec-hevc-start`。
独立构建根目录 `/home/deepdream/build/vdec-hevc`，只在其中使用 kunit/module 两个 O=。
厂商只读参考仓库 common_drivers 的 HEAD 为
`31619c527655514b4c89516ef609b6db1dd47db6`；下面厂商路径相对
`drivers/media_modules/`，内核路径相对 `drivers/media/platform/amlogic/vdec/`。
“相同”指可见主机代码顺序/字段相同，不代表固件内部行为或当前候选实板已验证。

| 步骤 | 厂商证据 | c99c3ed 基线证据 | 判定及本轮处理 |
|---|---|---|---|
| 电源/时钟 | `frame_provider/decoder/utils/vdec_power_ctrl.c:151,268`：HEVCF/B 均开，随后获取电源域 | `aml_vdec_hw.c:t7_hevc_power_on`：本地 gate、双路 p0/CCF、runtime PM、检查物理时钟 | 已证实关键顺序相同；框架/错误处理不同；历史 r28 双路回读成功，本轮不改 |
| T7 总线停机/全核 reset | `utils/vdec.c:5244`：AXI 隔离、stream=0、SAO MMU reset、RESET3 bits 3/4/8/10/11/12/13/14/15/17/18/19/24/26、清零、等待 WRRSP | `aml_vdec_hw.c:t7_hevc_stop,t7_hevc_reset`：同一 mask；停机有界且要求前后端读写均确认 | 已证实 reset mask 相同；等待更严格，历史 r28 空闲通过；真实解码后排空待证 |
| 固件类型与路由 | `utils/amvdec.c:497,577,670`：h265_mmu → HEVC_MMU=17，默认 legacy 路由，无 swap；`common/firmware/firmware_type.h:47` | `aml_vdec_hw.c:aml_hevc_prepare_hw`：secure DMC client 4，SMC load(17,0,0)，返回值检查 | 已证实主机选择相同；TEE/SM 内部目标地址、IMEM 内容和校验待证。安全加载没有向主机公开装载地址，不能把 a0=0 当内容校验 |
| 装载先后/缓存 | `vh265.c:run`：全核 reset、准备输入、按 mc_loaded 加载、恢复协议 | 基线先 prepare/reset/load，再 prot_init/feed；PM 引用释放清 loaded 缓存 | 不同：输入配置与加载相对次序；启动前均配置完成。是否影响 T7 待证，本轮不改 |
| workspace/parser | `vh265.c:5086,12309`：工作区、IQIT/parser 初始化、命令表、parser 接口；IQIT 仅写 bit14，startcode/emulatecode 写入位于禁用块 | `hevc.c:h265_config_workspace,h265_init_decoder`：IQIT 写 bit14 后额外清零，显式设置 startcode/emulatecode，省略厂商自检 | parser 中断字段/shift control/命令表对应；IQIT 清零、startcode 配置不同，workspace 尺寸和微码访问待实板；本轮不改 |
| mailbox/IRQ | `vh265.c:12309`：clear=1，mask=1；decode mode 高字节 0x80 指 MBX0 | `hevc.c:h265_prot_init,h265_config_decode_mode`；`aml_hevc_enable_irq` 先安装回调、开 Linux IRQ，再开硬件 mask | 已证实 clear/mask 和 MBX0 字段相同；历史 IRQ=0 的原因待证 |
| stream buffer | `utils/vdec.c:1980`：end=start+size，读指针 offset，写指针含 padding 后按 FIFO_ALIGN 向下对齐 | `hevc.c:h265_feed`：end=start+size-1，读指针从 coherent buffer 首地址开始，写指针 payload+16KiB，不另对齐 | 不同：end 语义、WP 对齐/填充策略；是否导致当前停滞待证，本轮保留以隔离启动实验 |
| WAIT_FLAG | `vh265.c:14152`：新帧写 0；prot_init 的写 1 已注释；续帧写 data_invalid | `hevc.c:h265_prot_init`：写 1 | 已证实不同；本轮不改，启动修正失败后优先单独实验此项 |
| FIFO/输入使能 | `utils/vdec.c:2314`：endian bits 6:4=7，FIFO bit29=1，然后 stream bit0=1 | `hevc.c:h265_feed`：先 stream bit0/endian，再 FIFO bit29 | 字段相同，先后不同；待证，本轮不改 |
| decode mode/bit21 | `vh265.c:12255`：framebase=1、flags、MBX0；bit21 由 performance_profile 决定 | `hevc.c:h265_config_decode_mode`：framebase=1、flags、MBX0；bit21 无条件置位 | 模式字段相同，bit21 条件不同；此前单改条件无效，本轮保留 c99c3ed 行为，不混入旧草稿 |
| 首次 ACTION/DECODE_SIZE | `vh265.c:14268`：ACTION_DONE，设置 shift/count/size，随后 amhevc_start | `hevc.c:aml_hevc_dec_run`：feed 设置 size；CPU reset 后将 ACTION 覆盖为 0，再 CPSR=0、MPSR=1 | 已证实不同；本轮改为 reset 前发布 ACTION_DONE，不再覆盖为 0、不再额外写 CPSR |
| CPU reset/启动读回 | `utils/amvdec.c:1056`：RESET3 三读，写 bits11/12 再清零，三读，MPSR=1 | 基线只有 reset 两写和 MPSR=1，没有 reset 读回 | 已证实不同；本轮恢复三读/两写/三读顺序，并加入分阶段寄存器诊断 |
| 后续 DECODE 命令 | `vh265.c` IRQ：NAL 搜索/参数解析后写状态，MCPU 请求唤醒继续 | `hevc.c:h265_command,h265_irq_thread`：clear mailbox、status、MCPU_INTR_REQ | 主机协议对应；真正第一次 IRQ、NAL/RPM、slice-data 和像素正确性全部待证；新增命令/请求读回 |

上表描述首轮 ACTION/reset 修正，未混改其他差异；不从 PC 反推微码指令语义。

草稿路径实际 SHA 为 `ee6d0074…`，与历史 `3c82a4ea…` 不符，未复用或修改。
实现依据上述厂商调用链；原始证据在 `build/vdec-hevc/`。

## r69 证据与下一处差异

t48 在 `.31` integration 中运行了 `5f7ed4f720237…`。本任务只读归档，未操作板子。
证据根为相邻主仓库 `build/hwdecode-parity/run69/archive/results/`，关键日志为
`kernel-journal-0041.jsonl` 及相邻编号、`hevc/hevc-compliance.log` 和前后 interrupts。

- 固件 load a0=0；before/after-reset 的 ACTION 均 ff、reset=0；启动后 MPSR=1、PC=3。
  超时 MPSR=5、PC=a1d、IRQ/status=0；SHIFT **0x08→0x28→0x63**，不是十进制计数。
  stream RD 从 `b72e0400` 到 `b72e0440`，只证明取数前进了 0x40，不能把 RD 当解析进度。
  尚不能证明上次修正是进展的唯一原因，但已排除本轮 CPU 完全没启动/输入完全不取数。
- 原日志 mode 从 `80000001` 变为 `21`、`14`。`hevc.h` 中 DECODE_MODE 和
  CUR_NAL_UNIT_TYPE 同为 scratch J：启动后这是 SPS(33)、IDR(20) 的 NAL 类型，
  不能记为模式遭破坏，也不证明 SPS/PPS 或 slice header 已解析正确。诊断改名 mode_or_nal。
- 带流命令明确使用 `--stream-from-hdr HEVC=…/hevc-intra.vhdr`，不是默认填充数据。
  同版本 v4l-utils `d2e89246cefcb6371425361b12c4ca2a36a662d2` 的
  `utils/v4l2-compliance/v4l2-test-buffers.cpp:119` 会剥离 Vhdr/长度头，设置 payload
  bytesused 和 data_offset=0；`:1738` 是等待 SOURCE_CHANGE 的 select 超时。
  归档 tools-manifest 的文件 SHA 与 integration31 fixture 一致，首 AU 长度 0x176f
  恰好匹配 DECODE_SIZE，前缀为 `0000000140010c01ffff040800000300`。
  离线解析 16 个 Vhdr AU 拼接恰好等于 h265 文件，软件解码得到 16 帧 256×256 I420。
  因此本轮不能用“compliance 送了无效数据”解释超时；未指定有效输入的其他测试则不能据此类推。

r69 后以 `f065c6712f7e…` 单改初始 WAIT_FLAG=0，并记录输入前缀；r70 实板证明
启动后固件又写成 1，仍停在同一 SHIFT/IDR，未解决超时。

## r70 结论与差异表补充

`run70/archive/results/kernel-journal-0019.jsonl`：有效 AU=5999 字节、前缀匹配、skip=0；
reset 前后 WAIT=0/status=ff，启动后 WAIT=1；SHIFT=0x28→0x63，NAL=0x20→0x14，
timeout PC=a1f、摘要 a1d，IRQ/status=0。两次 PC 读取不同不能证明等待的是哪个条件。
最初 WAIT=1 不是本轮停滞的充分解释。首个 slice 前协议详见
[握手对照表与候选](2026-11-05-hevc-header-handshake.md)。

| 新核对项 | 厂商/当前差异与下一候选 |
|---|---|
| 自动头解析 | 厂商 NAL_SEARCH_CTL bit0=0 时无需主机逐头应答；当前0x200008合法，没找到必须盲补的命令 |
| 手动头握手 | 厂商 bit0=1：09报告NAL，主机01/02/03/04应答；候选首次格式探测使用此路径，已知格式后仍自动 |
| slice应答 | 厂商08/RPM后才发05；当前已有同一路径，r70没到08，不预发05或伪造事件 |
| mailbox/调试 | mask=1、mode高位MBX0一致；缺少IRQ原值/FIQ路由/AMRISC mask及debug/RPM读回，候选补齐只读诊断 |

新提交 `857b5a2e2442f8d17cb024869b4e1aba035c84aa` 为定位候选，尚非已证实修复。
不改 bit21/FIFO/end/WP，不加 IRQ 注入、轮询应答或新模块参数。

## 给 t48/t3k 的下一窗短清单

1. 按 integration 既有身份/入场门禁，保存 UART、模块/固件身份与 IRQ 起点，启用
   CONFIG_DYNAMIC_DEBUG 和 `file hevc.c +p`；不混装本任务最小验证配置模块。
2. 只跑带同一有效 hevc-intra.vhdr 的 HEVC compliance；首次 search应为0x200001，
   期待09和NAL 32/33/34/20的逐头应答01/02/03/04，再到08/RPM与SOURCE_CHANGE。
   保存新mailbox/parser/debug读回；没有有效HEVC输入的其他测试另行标记。
3. compliance 通过后，仅跑同一 256×256 八位全 I 样本首帧捕获；保存可见 I420，
   对软件参考比较尺寸/平面哈希及误差。仅有缓冲或事件不等于正确画面；本窗不扩到 P/B/全套。
4. 失败即停 HEVC，不换流、不再捕获：保存 input/三阶段/timeout 快照、IRQ 差值和
   AXI 停机日志，按既有隔离/恢复流程由 t3k 统一处理。若成功，也只报告本次开启诊断的结果，
   关闭诊断复验和其他格式覆盖留到后续统一计划。

## 首轮离线验证（r69 前）

`5f7ed4f720237cfaf2a0de674e56a14e9257bebc` 的 ACTION/reset 修正、读回注释和诊断
经 heavy 队列 W=1 模块及 arm64 QEMU 25/25（HEVC 5 项）验证；主仓库 588 项、跳过 14 项。
旧输出在 `build/vdec-hevc/*review*`、`logs/vdec-hevc/repo-tests-review.log`。
首次 modpost 缺少顶层 Module.symvers 的失败保留在 `module.log`，补齐符号后通过；
模块产物哈希路径问题在下节更正。逐提交静态/DT/生产整包门禁仍留到合入评审。

## r69 后离线候选

新提交 `f065c6712f7e034918d5473fdd6778e4e636eef3` 基于 `5f7ed4f720237…`，
只改 `hevc.c:h265_prot_init,h265_feed,h265_dump_start`，分别为 WAIT_FLAG=0、
输入前缀诊断和共享 scratch 的日志命名；没有新增纯逻辑，无新增寄存器 mock 测试。
源码 SHA-256 为
`b4fabd8ae6d68205eb1465263ff36c972eda8114786f0576e273ed4665608d9f`。

分支尖 QEMU 25/25 通过，W=1 模块编译及链接通过，仍有五个既有 KUnit 模块
missing MODULE_DESCRIPTION 警告，修改文件无编译诊断。两个构建均通过 heavy 队列，
O= 仍复用本任务的 kunit/module 目录，没有碰板。主仓库全套测试结果见本任务日志。

更正产物身份：M=编译输出在源码目录，旧脚本却对O=中较早产物取哈希，不能用作
那次重编译的身份。另经heavy队列执行 `make O=…/module W=1 -j8 modules`，
对实际O=产物核验，r69后候选模块SHA为：
`0cb14906c4214ae9b8ef51e9d34572c081974b013d37ebad5fb7512af6168856`。
本任务仍只交源码，由 t3k 集成构建；不把此最小配置模块用于 integration 混装。

r69原始证据、工具源码、软件参考、KUnit及构建输出保存在 `build/vdec-hevc/*r69*`；
主仓库测试为 `logs/vdec-hevc/repo-tests-r69-delivery.log`，全部588项、跳过14项。
最新候选验证、产物SHA和判停见[握手记录](2026-11-05-hevc-header-handshake.md)。
