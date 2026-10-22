# 2026-10-22：T7 stateless 解码第二轮离线准备

本轮只做离线取证、时钟 provider、默认关闭的 DT 和驱动平台分支。
**没有启用或上板运行 DOS VDEC；没有正确帧、compliance 或性能验收。**
T7 probe 会在资源获取、V4L2 注册和 MMIO 之前返回 `-EOPNOTSUPP`，原因是
secure H.264 固件路径及 DMA 超时后的缓冲区生命周期仍未闭合。
因此本轮产物是可审查的平台准备，不是已可用的解码驱动。
前一轮的格式和硬件概览见 [硬件调查](2026-10-22-vdec-hardware-audit.md)。

## 源码和修改范围

内核 worktree：VM `vim4-build:/home/deepdream/src/linux-7.3-vdec`，分支
`vim4-vdec`，从 `e0346697f25035c7eaa77fa44641a54d6e31e327` 建立。
本节证据以厂商内核 `80a07ad5406d57855c996285ae75a50a1b9147ae` 和
common_drivers `4cfb128d36f8511b2db1bd13c08d5704347ded49` 为准。
下列厂商路径除注明外均相对 `~/src/linux/common_drivers/`；行号是该提交的原始行号。

| 修改 | 本轮实现 | 有意保留的限制 |
|---|---|---|
| `drivers/clk/meson/t7-peripherals.c`、clock binding header | 补 VDEC、HEVC front/back 的双路 mux/div/gate，共 21 个追加 ID | 不改已有 ID、HCODEC 高半字或 Wave 寄存器；新 gate 使用 `CLK_IGNORE_UNUSED`，消费者未接入前不改变固件遗留门控 |
| `arch/arm64/boot/dts/amlogic/amlogic-t7.dtsi` | `video-codec@320000`、DOS 64 KiB、IRQ 92、SYS_DOS/VDEC、DOS_VDEC、canvas | `status = "disabled"`；无 DMC、HEVC 或 HCODEC IRQ；DOS 映射仍与现有 JPEG 驱动重叠，不能同时启用 |
| 新 T7 binding、`MAINTAINERS` | 描述 T7 单 VDEC 引擎资源与共享 DOS 限制 | 不借用 S4 compatible，不声称 HEVC codec 支持 |
| `drivers/media/platform/amlogic/vdec/aml_vdec_platform.*`、`aml_vdec_drv.c` | T7 专用 platform data、最早 probe 拒绝 | 不继承 S4 codec_ops、支持格式和 raw 固件名；移除拒绝条件本身不足以启用 |
| `aml_vdec_hw.*`、`reg_defines.h`、`aml_vdec.c` | T7 无 DMC 分支；DBUS ack 有界轮询；上电错误返回；T7 跳过本地 PD/reset 写入，并保留厂商 clock/domain 顺序 | 没有实现所有 DMA 队列的隔离或超时后内存持有；关闭路径仍不具备 T7 运行资格 |

没有改原主工作树、部署锁或厂商接口；没有重分发固件字节。

## 功能时钟对照

厂商 CCF 文件为 `drivers/clk/meson/t7.c`，寄存器声明在同目录 `t7.h`。
下表寄存器为 byte offset，相对 T7 peripherals clock controller；不能把它们当 DOS word index。

| 厂商 CCF 名称 / 新 provider 名称 | 寄存器、字段 | 父时钟 / 频率依据 | 出处 |
|---|---|---|---|
| `vdec_p0/p1`、`vdec_mux` / `t7_vdec_0/1`、`vdec` | P0 `0x140`，P1 `0x148`；mux `[11:9]`、div `[6:0]`、gate 8；最终 mux `0x148` bit 15 | fdiv2p5、fdiv3、fdiv4、fdiv5、fdiv7、hifi、gp0、xtal | `t7.c:3740–3858` |
| `hevcf_p0/p1`、`hevcf_mux` / `t7_hevcf_0/1`、`hevcf` | P0 `0x144`，P1 `0x14c`；低半部字段同上；最终 mux `0x14c` bit 15 | 同 VDEC 的八个 parent | `t7.c:4099–4210` |
| `hevcb_p0/p1`、`hevcb_mux` / `t7_hevcb_0/1`、`hevcb` | P0 `0x144`，P1 `0x14c`；mux `[27:25]`、div `[22:16]`、gate 24；最终 mux `0x14c` bit 31 | 仅 fdiv2p5、fdiv3、fdiv4、fdiv5、fdiv7 | `t7.c:3972–4096` |
| HCODEC（已有，不改） | `0x140/0x148` 高半部，最终 mux `0x148` bit 31 | 与 VDEC 同八个 parent | `t7.c:3860–3970` |
| DOS 总线门控 | `SYS_CLK_EN0_REG0=0x44` bit1，厂商 `dos` / 当前 `t7_sys_dos`、`CLKID_SYS_DOS` | 与 Wave/HCODEC 共享引用；不能整块复位或绕开 CCF | 厂商 `t7.c:7129`；当前 `t7-peripherals.c:sys_dos` |

T7 三项功能时钟最大值均为 800 MHz，`hevc_clk_combine_flag=false`、
`is_support_dual_core=false`，出处 `drivers/media_modules/common/chips/decoder_cpu_ver_info.c:237–253`。
800 MHz 是厂商表上限，不等于每个格式均要求该频率。
动态选择见 `drivers/media_modules/common/media_clock/clk/clkg12.c:732–866`；
其 VDEC 路径调用 `vdec_max_clk_get()`，不可用旧代手写 source/div 表代替 T7 CCF。
本轮仅保留旧驱动初始约 500 MHz 请求，没有在板上设频。

## 电源、隔离、复位和停机顺序

以下 `utils/` 缩写为 `drivers/media_modules/frame_provider/decoder/utils/`。
电源调用失败必须终止后续 DOS 访问；轮询有 timeout 也无法打断一次挂起的 MMIO 总线事务。

| 阶段 / 引擎 | 厂商实际顺序和检查 | 出处 / 本轮处理 |
|---|---|---|
| T7 上电 | 功能 clock on / hi enable → `pm_runtime_get_sync(domain)`；T7 不执行 `dos_local_config()` 的旧式 RAM PD/reset | `utils/vdec_power_ctrl.c:151–176,195–203,268–282`；本轮 clock 和 PM 错误向上传递，使用 `pm_runtime_resume_and_get()` |
| T7 下电 | 本地配置（T7 no-op）→ 功能 clock off → domain put | 同文件 `285–299`；不能沿用旧 S4 driver 先 domain off 再 clock off 的顺序 |
| secure genpd 层级 | VDEC、HEVC、HCODEC、Wave 都由 NIC3 父域提供桥接层级 | 当前 `drivers/pmdomain/amlogic/meson-secure-pwrc.c:335–338`；不单独复位共享 NIC3 |
| VDEC 关闭总线请求 | 先停止 ARM RISC：MPSR/CPSR 清零并等待 IMEM/LMEM DMA；然后 `VDEC_ASSIST_DBUS_DISABLE=0xffff`，等回读相等，再 200 次 settling loop | `utils/vdec.c:773–817,1072–1093`；厂商 DBUS 等待无界，离线 reset 分支改成 100 ms 有界轮询，保留 200 次 `cpu_relax()` 循环，不臆造微秒长度 |
| VDEC reset | 关闭 DBUS → DOS_SW_RESET0 bits 3/4/5/7/8/9 置位再清零 → 清 MMC_CTRL1 bit 3、PIC_DC_MUX bit 31、EXTIF_CFG1 → DBUS 写零恢复 | `utils/vdec.c:5130–5168`；T7 无独立 DMC req，不能写 S4 DMC bit 21 |
| VDEC 正常停机观察 | MPSR/CPSR=0 → IMEM_DMA_CTRL bit15=0（约100ms）→ LMEM_DMA_CTRL bit15=0（约100ms）→ WRRSP_LMEM low12=0（约12.5ms）→ 双 CPU reset bits11/12，前后各三次 reset readback | `utils/amvdec.c:1079–1138` |
| HEVC 隔离 | AXI_CTRL bit6 禁 front，查 AXI_STATUS 中 bits15/11；再 bit14 禁 back，查 AXI_STATUS2_LO；T7 不查 S5 DBE1；每段约100ms后仍继续 | `utils/vdec.c:876–949`；厂商条件为 `status & (BIT(15) | BIT(11))`，不是两个位都为1，本轮不擅自强化/解释其硬件语义 |
| HEVC reset | 隔离AXI → frame mode STREAM_CONTROL=0 → SAO_MMU_RESET bit0置位 → DOS_SW_RESET3 的 parser/dblk/CPU/DDR/MPRED/SAO/MMU 等掩码置位再清零 → 等 WRRSP_LMEM low12=0 → 清SAO MMU reset → 恢复AXI | `utils/vdec.c:5244–5349`；T7 在后续各代外部 RESET 分支中走 default，没有可照搬的 T7 RESET5 写入 |
| HEVC 正常停机观察 | MPSR/CPSR=0 → IMEM/LMEM DMA bit15清零 → WRRSP_LMEM low12=0，之后读reset及可能关闭VCPU门控 | `utils/amvdec.c:1172–1219`；并非 VDEC reset 的替换名称 |

寄存器 word index 在 `drivers/media_modules/include/regs/dos_registers.h`：
DBUS_DISABLE `0x46`（1974）；VDEC IMEM/LMEM/WRRSP `0x340/0x350/0x353`（34–41）；
HEVC AXI_CTRL/STATUS/STATUS2_LO `0x307c/0x307d/0x307f`（545–548）。
当前驱动 regmap 使用 byte offset，需要乘4。

**可靠停机仍有缺口。** 厂商 IMEM/LMEM/WRRSP timeout 只是 break，HEVC AXI timeout
只是日志，VDEC DBUS 只有 disable 寄存器回读，没有另一个已证实的 outstanding-DMA 计数。
这些源码给出了正常路径的检查点，不能证明 timeout 后仍可释放 vb2、DPB 或 firmware DMA。
旧 S4 `aml_stop_vdec_hw()` 也丢弃前两项 timeout，`load_firmware()` 甚至在 DMA timeout 后
仍释放 microcode buffer。本轮不把这些行为复制成 T7 可用的关闭保证；probe 拒绝保持生效。
下一步须在驱动生命周期中贯通错误返回、永久故障状态、DMA 映射持有/隔离与重载策略，
并先确认可证明停机的硬件状态，再允许 V4L2 排队。

## 固件：不能靠剥头转换，secure load 可避免重分发

首轮只读保存的现有 `/lib/firmware/video/video_ucode.bin` 为 389696 字节，
SHA256 `59e242bd63d6372d6462d2a2d6815e7bdea1a2cd12cd29fac093f38e73294e4b`。
NEWP 的包头256字节；每目录项由256字节 package_info 与其 length 数据组成；
CODE header 固定512字节，出处
`drivers/media_modules/common/firmware/firmware_priv.h:60–118`。
该文件15个目录项 length 均512，h264_multi header 虽声明28672字节，目录项没有这些 raw 字节。
元数据后还有377920字节，本轮没有将它解释成可直接执行的明文固件。
厂商 parser 对 NEWP 不做旧 raw checksum 校验，见
`common/firmware/firmware_drv.c:698–759,852–858`（此处前缀为 `drivers/media_modules/`）。

旧 S4 loader 是单CODE文件：跳过512头，将后续字节送 IMEM DMA，并从固定偏移复制
H.264 swap 段，见当前 `aml_vdec_hw.c:load_firmware()` 和
`h264.c:copy_mc_cpu_fw()/aml_h264_load_fw_ext()`。
因此不能把 NEWP 目录项重命名为 `s4_h264_multi.bin`，也没有已证实的普通世界纯格式转换方法。

可避免重新分发字节的路线是复用板上启动固件已经支持的 secure loader：

- 厂商 `utils/amvdec.c:631–638,670–675` 对 `mh264` 选
  `VIDEO_DEC_H264_MULTI=15`、`OPTEE_VDEC_LEGENCY=0`；定义见
  `common/firmware/firmware_type.h:45,92`。
- `drivers/tee/tee.c:59–62,626–644` 调用 SMCCC `0xb200000f(index, core, swap)`。
  当前 T7 JPEG 驱动已用同一入口，但参数为 index21/core3；JPEG 的已有实测不证明 index15 可解码。
- H.264 TEE 模式不分配或复制普通 swap 区：
  `h264_multi/vmh264.c:9366–9411`；也不覆盖安全 loader 设置的 AV_SCRATCH_G：
  `9135–9136,11424–11437`（前缀为 `drivers/media_modules/frame_provider/decoder/`）。

所以后续不能只加一个 SMC 再继续执行旧 raw loader。必须新增 T7 secure 路径、保留安全世界
设置的 scratch/swap 状态并核对 stateless H.264 消息协议。当前准备未执行 SMC index15，
未声称能解包、解密或转换已有包；相关字节没有进入 Git。

## 离线验证和下次现场窗口

已运行 `git diff --check`；驱动/DT、clock ID 和 binding/MAINTAINERS 按提交边界分别检查，
`scripts/checkpatch.pl --no-tree --strict` 均为0 errors、0 warnings、0 checks。
新增 binding 使用 VM `~/build/dt-schema-venv/bin/dt-doc-validate` 通过。
主任务持 heavy 锁，在独立 `O=~/build/kernel-vim4-vdec` 构建
`drivers/clk/meson/t7-peripherals.o`、VIM4 hdmirx-test DTB，以及独立
`MO=~/build/kernel-vim4-vdec/amlogic-vdec` 的 `aml-vdec-drv.ko`，全部通过，含BTF，无warning。
日志 `logs/kernel-edge/vdec-round2/t7-offline-build.log`。主仓离线169项测试通过，5项跳过。
未构建完整Image或全模块，也未运行完整dtbs_check。

现场按风险从低到高：

1. 离线核对候选的 build ID、BTF/模块、disabled 节点和 probe 拒绝仍存在。
2. 独占 board 锁，停所有 DOS 消费者；只有完善并审核 secure loader、总线隔离和资源释放后，
   才安排仅 power/probe/unload 窗口。此时仍需现场 RESET 条件，不用软件 timeout 代替。
3. 先用已知640×480逐行8-bit H.264 I/P码流单实例取正确帧，再1080p含B帧；每项明确timeout，
   一次硬件无响应即停，先取证，不反复重载。
4. STREAMOFF/close/错误码流/超时注入，证明DMA停止与内存所有权后，才进入4K或并发。
   性能采样同时持board/heavy锁；最终恢复基线并验证编码、HDMI、UDC及实际HID。

当前不能改为 okay 来验证 probe 拒绝：`drivers/base/platform.c:1497–1511` 会在驱动probe前
自动附着并上电单个genpd。还须处理这一行为与厂商clock-before-domain时序的关系；
驱动内早拒绝不阻止platform core附着。firmware、停机和DOS/JPEG隔离仍是实现门槛。
