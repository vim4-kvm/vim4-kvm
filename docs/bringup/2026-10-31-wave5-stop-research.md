# 2026-10-31：P0-3 公开停机协议与合法等待研究

续[第一轮安全审查](2026-10-31-wave5-real-hang-safety.md)。本轮只联网查资料、读源码；
没有连接板子、申请板锁、注入或修改内核。**仍不建议进入真实挂死上板阶段。**
新证据支持现有排空顺序及0x3f判值，但不证明T7挂死时APB/FIO必定返回，
也没有揭示可直接补入生产代码的安全停机步骤。最有价值的后续方向是输出buffer-full等待。

## 来源、版本与许可

以下为固定快照及其行号。公开访问不等于移植授权；受限资料不复制入库，不反汇编。

| 代号 | 固定来源与定位 | 阅读/引用边界与T7适用性 |
|---|---|---|
| S | StarFive `soft_3rdpart@b60da16be1b36453aa46599889c28310fd148fb8`，[wave5.c](https://github.com/starfive-tech/soft_3rdpart/blob/b60da16be1b36453aa46599889c28310fd148fb8/wave511/code/vpuapi/wave/wave5.c#L1971) 1971–2100；同树 `vpuapi/vpuapi.c:1089`、`vdi/linux/vdi.c:1448` | 文件头为LGPL-2.1 OR BSD-3-Clause且附源码再分发条款，可读并按条款引用；目录`wave511/code/LICENSE.txt`却是binary-only且禁逆向，不把文件头外的资产推定开放。仓库目标JH7110 Wave511解码，通用VDI显式列521/521C使用0x3f；不证明T7集成 |
| T | TI `ti-linux-kernel@a7758da17c2807e5285d6546b6797aae1d34a7d6`，[wave5-hw.c](https://github.com/TexasInstruments/ti-linux-kernel/blob/a7758da17c2807e5285d6546b6797aae1d34a7d6/drivers/media/platform/chips-media/wave5/wave5-hw.c#L1206) 1206–1312 | GPL-2.0 OR BSD-3-Clause，可读/按条款引用；TI 6.6平台同IP家族，非T7。TI cgit固定文件请求403，改用TI官方GitHub同仓快照；未取得另一套TI用户态SDK |
| A | Amlogic SDK `encoder_libs_aml@4c38af2b398d00a906c26aa166d630a9f73d3f9e`，[enc_driver.c](https://github.com/numbqq/encoder_libs_aml/blob/4c38af2b398d00a906c26aa166d630a9f73d3f9e/multiEnc/vpuapi/enc_driver.c#L674) 674–797；`include/vpuapi.h:1285,4128,4641` | 文件头标confidential/SLA并限制复制修改；公开镜像不能代替SLA授权，未取得可移植授权，不将其源码复制入库。与已有T7 SDK参照相同；仍缺SoC硬件保证 |
| K | 我们正式内核 `dc220366a1222a03423d5b5987fab3f027ec1d7a`，[wave5-hw.c](https://github.com/vim4-kvm/linux/blob/dc220366a1222a03423d5b5987fab3f027ec1d7a/drivers/media/platform/chips-media/wave5/wave5-hw.c#L1439) reset 1439–1571；同目录`wave5-vpu.c:280–340`恢复 | Wave5文件GPL-2.0 OR BSD-3-Clause；确为T7正式代码，已有恢复状态机，但源代码顺序不能证明总线故障时的电气性质 |
| B | Khadas Linux 4.9 `bd9460728746cc080acbaa084e53460437f43211`，[h265/vpu.c](https://github.com/khadas/linux/blob/bd9460728746cc080acbaa084e53460437f43211/drivers/amlogic/media_modules/frame_sink/encoder/h265/vpu.c#L387) 387–410；5.4 `ef8cd851f48356675c3e987fead999fe28f6f69d`，[multi/vpu_multi.c](https://github.com/khadas/linux/blob/ef8cd851f48356675c3e987fead999fe28f6f69d/drivers/amlogic/media_modules/frame_sink/encoder/multi/vpu_multi.c#L466) 466–470、992–1020 | 两者文件头GPL v2或更高，可读/按条款引用。4.9该文件是Wave4 HEVC路径；5.4 multi有T7域分支，但reset ioctl仍空操作，hw_reset仍是已否决的0xfe000044 bit28 |

S的其他定位：[寄存器](https://github.com/starfive-tech/soft_3rdpart/blob/b60da16be1b36453aa46599889c28310fd148fb8/wave511/code/vpuapi/wave/wave5_regdefine.h#L450)450–471，
[API头](https://github.com/starfive-tech/soft_3rdpart/blob/b60da16be1b36453aa46599889c28310fd148fb8/wave511/code/vpuapi/vpuapi.h#L4185)4185–4199、4224、4716–4750。
Rockchip检索未取得适用521C的独立参考实现。

## 1. reset与安全停机逐步对照

`VPU_SWReset`本身是加锁/产品分发，真正顺序在`Wave5VpuReset`。S API文档把FORCE
描述为不等事务，但同版本实际函数仍先drain；不能仅按枚举名或注释选择“强制”路径。

| 阶段 | S / A参考实现 | T / mainline家族与正式K | 是否缺步骤 |
|---|---|---|---|
| 宿主停止提交/旧IRQ | 用户态调用需外层串行；API入口不证明Linux队列与DMA生命周期 | K隔离入口屏蔽IRQ，worker同步、旧队列EIO、锁住提交与恢复 | K已有；不改回只调用SDK复位 |
| BUSY=0 | 宿主清标志；不等于固件停机或DMA完成 | K相同，随后真实排空 | 不能当停机ACK |
| stop→idle | backbone单核VCORE0=7、combined=7，GDI=0x100；双核另停VCORE1。S VDI显式521C判0x3f | T另按能力停VCPU=0xff、等0；K支持此分支，T7 VCORE/GDI判0x3f，双核拒绝 | 单核未发现遗漏；不套另一拓扑 |
| SLEEP | S/A在drain之后仅SAFETY执行，要求命令成功 | T在SAFETY开始先SLEEP；K legacy在drain后SLEEP，但恢复选ON_BOOT，跳过SLEEP | 添加SLEEP会重新依赖活固件，不补挂死保证 |
| 内部reset | REQ→STATUS=0→清REQ，S/A mask=0x0fffffff | T通用mask；K T7保留0x07ffffff | bit27无T7定义依据，不扩大mask |
| 解除stop/启动 | 成功后解除stop，FORCE/SAFETY再WAKEUP；ON_BOOT不唤醒 | K排空/内部reset后genpd OFF/ON确认、PC=0、复制固件冷INIT，旧上下文不复用 | 冷INIT不同于WAKEUP；K失败保留stop/DMA比参考失败时解除stop更保守 |

寄存器交叉核对（全部是IP内偏移，FIO空间不作物理MMIO地址直接写）：

| 功能 | S与A头文件 | K `wave5-regdefine.h` |
|---|---|---|
| RESET REQ/STATUS | 0x50/0x54 | 72/81行，同偏移 |
| GDI CTRL/STATUS | 0x88f0/0x88f4 | 490–491行，相同 |
| VCORE0 CTRL/STATUS | 0x8e10/0x8e14 | 502–503行，相同 |
| VCORE1 CTRL/STATUS | 0x9e10/0x9e14 | 506–507行，相同；不证明本芯片双核 |
| combined CTRL/STATUS | 0xfe10/0xfe14 | 510–511行，相同 |
| 独立VCPU CTRL/STATUS | 这两份头未给独立同名定义；combined占相同地址 | K 494–495行；按CONFIG能力选用，不能同时解释成两个总线 |

B的4.9代码确实写DOS_SW_RESET4和RESET0_REGISTER，但属于旧Wave4/SoC路径，
没有T7 Wave521C映射；5.4没有提供新的可信reset实现。未因此新增寄存器操作。

## 2. 合法等待：有候选，尚非安全真实挂死方法

S API头4185–4199描述`lineBufIntEn`：输出line buffer满产生中断后等宿主处理；
4224的`lowLatencyMode`控制早期中断/打包，**不是源行ready握手**。
所读公开文件未找到可用于T7编码的源行/源buffer-ready宿主门铃协议。

T7关联比单纯Wave511名称更强：K `wave5-vpu-enc.c:1739`已使能`line_buf_int_en`，
`wave5-hw.c:1690`打包bit6，`setup_wave5_interrupts():369`使能BSBUF_FULL。
但这仍不证明T7固件214414在满状态停哪些DMA。命令ACK可先让BUSY清零，帧完成却等待；
因此不能预设BUSY必须为1，也不能把只少一个ENC_PIC完成解释成固件死循环。

可继续离线细化的设计（**未实现/未执行，尚不称安全**）：只用合法映射、完整保留的输入/
重建/输出缓冲，在文档允许的输出容量内让复杂帧触发真实BSBUF_FULL；一次token仅在
该原因出现时阻止常规清中断，先记录硬件原因/实例/指针边界，再由现有帧watchdog恢复。
K `wave5-vpu.c:89–90`现在先清全部原因，不能只在finish_encode回调中“少归还缓冲”模拟。
新hook还须处理同次混合IRQ、一次完成、锁与延迟清理，不能全局屏蔽IRQ假装固件停滞。

风险门槛：先取得T7输出容量最小值、满中断精确触发/清除条件、满后禁止越界写及
所有DMA是否静止的合同；不能靠故意过小映射触发。即使契约成立，等待期间可能还有
重建/参考帧DMA，须保留全部所有权并照常drain。先做“清满中断后同帧继续”的对照，
再测“保持等待→reset→重载”，区分合法可续等待与死锁；前者不需要reset也能恢复，
故最多证明真实硬件未完成任务时的终止/重建，**不能单独关闭E03真实固件挂死缺口**。

## 3. 公开hang案例能证明什么

以下均可公开阅读；邮件正文未见统一开放再分发许可，只链接并简述，不整篇转载。
内核补丁按目标文件GPL/BSD许可阅读使用。TI网页访问失败不当作已核实正文。

| 来源 | 结果与适用边界 |
|---|---|
| [2024-02-28 abort讨论](https://patchew.org/linux/20240228-wave5-fix-abort-v1-1-7482b9316867@baylibre.com/)（AM62Px；正文175–198行） | 反对在固件状态未知时直接job_finish，讨论watchdog后复位/重建与迟到完成竞争；提到开发期stall由固件更新解决，但未给T7输入或独立复位合同 |
| [035371c9e5098](https://github.com/torvalds/linux/commit/035371c9e5098018b8512efc6a8812912469480c) | 已知521C Main10解码会超时，修复是恢复不支持格式的拒绝；非编码器用例，未证明VCPU死循环，不作为T7编码注入 |
| [a2c75e964e51b](https://github.com/torvalds/linux/commit/a2c75e964e51b096e9fe6adfa3eaed53594a668b)、[e3a80073d99c3](https://github.com/torvalds/linux/commit/e3a80073d99c376176d81013335cd355af576be2) | seeking/FLUSH与队列重调度修复；说明视频stall可能只是宿主协议/调度问题，并非硬件死锁 |
| [2026-10-07厂商FLUSH补丁](https://lists.openwall.net/linux-kernel/2026/10/07/110) | 芯片仍拒绝忙时FLUSH；加等待并检查返回结果。可复现解码停流，但仍有活固件响应，不补E03证据 |
| [TI 10.1 AM62Px release notes](https://software-dl.ti.com/processor-sdk-linux/esd/AM62PX/10_01_10_04/exports/docs/devices/AM62PX/linux/Release_Specific_Release_Notes.html) | EXT_EP-12109登记多实例hang修复；仅标题不足以判固件死锁或推导安全注入 |

检索到的TI E2E 1624256编码器paging异常正文请求403，未据摘要推断固件行为。
StarFive检索未找到附安全复现输入和停机证明的案例。以上搜索有范围限制，不能断言不存在。

## 4. 测试固件与三个前置条件

linux-firmware固定到`bda6eccc3a8f52e00696cf733b6e4f042d56655c`：
[WHENCE](https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware/+/bda6eccc3a8f52e00696cf733b6e4f042d56655c/WHENCE)
7833–7838只有`cnm/wave521c_k3_codec_fw.bin`的Wave5项，未标测试钩子。
[LICENSES/LICENCE.cnm](https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware/+/bda6eccc3a8f52e00696cf733b6e4f042d56655c/LICENSES/LICENCE.cnm)
限定该文件用于TI芯片并禁止逆向；可读许可/元数据，不在T7执行。
该文件999104字节，SHA256=`e77e73a5379b93ba5ae208ff91480f832a89d47eaf1ec42c88f6bcf86cff1fd8`。
S树仅发现`wave511/firmware/chagall.bin`及限制性许可，非T7 Wave521测试镜像。
未发现可授权在T7使用且带文档化停滞钩子的镜像，不猜ISA或开启未知DEBUG位。

| 前置条件 | 新证据 | 仍缺 |
|---|---|---|
| 停滞时APB/FIO可访问 | S/T通过宿主寄存器执行stop/reset，K保持时钟 | T7时钟/总线依赖与不返回访问的隔离保证；轮询timeout不能打断挂死的单次MMIO |
| stop排空已接受AXI | 多份参考顺序和S VDI的521C=0x3f相互印证 | T7状态位语义、stop覆盖范围与故障状态完成保证；只能在实际idle已确认后前进 |
| reset/OFF/ON不依赖VCPU | ON_BOOT代码不发SLEEP；K在独立genpd做状态回读 | T7内部reset硬件及BL31电源控制实现/合同；SMC调用可返回性不是GET轮询所能保证 |

无内核改动，strict checkpatch、KUnit/夹具和完整构建未重跑。资料与哈希在本机
`logs/p0-3-wave5/research/`；主仓离线测试提交前执行。下一步取得T7 buffer-full/AXI合同，
审核等待/恢复设计及离线状态机，再由用户决定上板；验收与保护退出沿用第一轮门禁。

主仓全套365项通过、14 skipped；首次文档超限已修正，失败日志保留。
