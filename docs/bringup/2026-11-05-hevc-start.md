# 2026-11-05：HEVC 首次启动序列离线对照与待测清单

本轮仅离线分析、修改和验证；没有访问板子。HEVC 首帧正确画面仍待实板证明。
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

上表将 ACTION、CPU reset 读回作为一个固件启动契约修复；没有同时调整 WAIT_FLAG、
FIFO、buffer end 或 bit21。diagnostic 开启时的额外 MMIO 读取可能改变启动时序，
本次成功后仍需在同窗关闭该文件 debug 复跑，才能排除诊断时序依赖。
不从 PC=0xa1d/0xa1e 反推未知微码指令的语义。

用户指定可参考的 hwdecode-parity 草稿原记录 SHA-256 为 `3c82a4ea…`。
本轮只读该路径时实际为
`ee6d0074ab4824516aa50dfde8eefef21b575aa5986cdf80cd2289d96adcff7b`，
故没有把它作为该历史草稿复用，也未改动其文件。实现依据为上述厂商公开主机调用顺序，
没有复制私有草稿。原始检索及摘录保存在 `build/vdec-hevc/`。

## 给 t48/t3k 的同次启动测试清单

1. t3k 将审核后的 topic 合入 integration 候选；记录 integration SHA、完整配置、
   Image/DTB/模块 SHA-256、build ID 和固件包身份，传输后比对双端哈希。
   本任务仅提供源码，不提供可混装到别的 Image 的模块。DT/clock/pwrc 依赖已包含在 c99c3ed。
2. 依既有板窗门禁确认 uptime 已满 300 秒、连续 UART 无复位；保留本窗 UART/dmesg。
   开启动态调试：`echo 'file hevc.c +p' > /sys/kernel/debug/dynamic_debug/control`。
   候选须启用 CONFIG_DYNAMIC_DEBUG；QEMU 配置不能作为 integration 生产配置。
3. 保存 `/proc/interrupts` 的 HEVC IRQ 起点，跑 HEVC 节点 compliance，再用已有
   256×256 八位全 I、含 VPS/SPS/PPS 的同一 Annex-B 样本跑带流 SOURCE_CHANGE/解码。
   沿用现有 vdec-window/捕获入口与超时，不在失败后换流重试。
4. 期待日志顺序 before-reset → after-reset → after-start：前两阶段 status=ff，
   after-reset 的 reset=0；after-start MPSR 启动，status 允许固件立即更新。
   IRQ 计数递增，出现 NAL/RPM 或 slice-data 状态；收到 SOURCE_CHANGE 后准备 CAPTURE，
   继续该 AU，收到第一帧并保存可见 I420（用 vdec-capture，排除 stride/padding）。
   与同一输入的软件参考逐帧比较，记录数量、尺寸、每平面哈希和误差；仅收到帧不算正确画面。
5. 首帧和全 I 样本像素正确后，关闭 `file hevc.c -p`，重复全 I，再跑已有 P/B 样本，
   检查显示顺序和 EOS/LAST；之后才推进既定 HEVC 标准码流和同窗 H.264/MPEG-2/JPEG 回归。
   不把本任务的启动修正视为 Main10、多切片、长参考或全套 HEVC 通过。
6. 任一加载失败、WARN/Oops、意外复位、SOURCE_CHANGE/解码超时、错误帧或停机失败即停止
   HEVC 序列，不开第二条流。保存 timeout 的 status/PC/shift、三组分阶段快照、
   命令读回、IRQ 差值及 AXI 停机日志。停机失败沿用资源隔离/恢复流程，不释放仍可能 DMA 的内存。
   正式恢复和本窗其余 topic 是否继续由 t3k 按 integration 清单统一决定。

失败分流：before-reset 已非 ff → 检查主机发布；after-reset 变 0 → 检查 reset 对 scratch 的影响；
MPSR/PC 不动 → 检查 CPU/IMEM/时钟；PC 运行但 shift 不动且无 IRQ → 对照 WAIT_FLAG/FIFO/指针；
status 已是事件而 IRQ 不增 → 对照 mailbox/mask/IRQ 路由；IRQ/RPM 已进但无图 → 转入参数/重建路径。
这些都是下一轮定位分支，不是本轮已证明的故障原因。

## 验证边界

本轮没有新增纯逻辑：改动只有寄存器发布、CPU 启动时序和诊断，未增加寄存器 mock
或复述写值的 KUnit。既有 HEVC 参数/POC/tile/参考/SAO 测试及其他 codec KUnit
在 arm64 QEMU 中共 25/25 通过（HEVC 5 项）。W=1 只针对分支尖模块，
逐提交 strict checkpatch、fixture、binding/DT、完整生产 Image/模块检查留到合入评审。
没有 push、合并、发消息或申请板票；首帧、带流合规和 DMA 停机均留给统一板窗。

内核提交为 `5f7ed4f720237cfaf2a0de674e56a14e9257bebc`，仅修改 `hevc.c`：
`h265_dump_start`、`h265_command`、`h265_irq_thread` 和 `aml_hevc_dec_run`。
相对基线一事一提交，未改 DT/clock/pwrc 或其他 codec。

实际验证经 `tools/board-queue run --heavy --who vdec-hevc` 执行：

- QEMU：`kunit.py run 'amlogic-*' --arch arm64 --jobs 8 --timeout 120`，使用仓库
  vdec `.kunitconfig` 和本任务 `kunit` O=，25/25 通过，JSON、完整 QEMU 输出均保存。
- 模块：从上述配置派生，MODULES=y，驱动和测试均为 m；在本任务 `module` O= 生成
  内核/模块符号后清理本目录对象，再执行 `make O=… W=1 -j8 M=drivers/media/platform/amlogic/vdec modules`。
  编译及链接成功，五个既有 KUnit 模块有 missing MODULE_DESCRIPTION 警告，
  修改文件无编译诊断。不声称整个内核 W=1 或生产配置整包已通过。
- 首次模块链接失败保留在 `module.log`：当时只有 vmlinux.symvers，尚未生成顶层
  Module.symvers；补跑顶层 modules 后重新编译成功，没有屏蔽 unresolved symbols。
- 主仓库：`python3 -m unittest discover -s tests -p 'test_*.py'`，588 项，跳过 14 项。

Mac 原始输出在 `logs/vdec-hevc/`、`build/vdec-hevc/`；VM 同名构建根目录保留配置、
产物和日志。评审后重新跑分支尖门禁，`kunit-review.log`/`kunit-review-qemu.log`/
`result-review.json` 为最终 QEMU 证据（25/25），`module-review.log` 为清理后
重新编译的最终 W=1 输出；仍只有上述五个既有 KUnit 模块警告。
`source-review.sha256` 固定被测源文件，`module-review.sha256` 固定模块。
源码 SHA-256 为
`912fc17386d72d4b4aca941cb983dfa3a46359b77dae756550c81d6cd030b9cf`；模块 SHA-256 为
`42eb65723c3cb3c5b34a427d19d53de6563107e865c7e96e8ce77d327cc000b6`。
评审仅补充 amhevc_start() 三次读回的写入排空/延时说明，并将提交正文按列宽换行，
明确 ACTION_DONE 在每次 dec_run 发布；正文列明 amvdec.c/vh265.c 的参考函数。
模块哈希在本验证配置中与前版相同；注释变更未改变其二进制。源码在最终验证后未再修改。
