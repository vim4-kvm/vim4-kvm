# 2026-10-23：T7 VDEC 外部控制寄存器全量差分

两份清单全部读完：2,055 字相同、89 字不同，均正常回基线，无新 SError。
明确的 VDEC 差异是 p0/p1 路径；候选将对齐厂商 p0，但尚未证明这是内部访问故障的根因。
本轮比较厂商 5.15 的实际 H.264 解码状态与 7.3 的第八步状态，
不重新执行已失败的 `c7e7e28f…`，不访问内部 GCLK/PIC，不进入 compliance 或解码。
原始证据保留在本机 `logs/vdec-register-diff/`；下文区分已采集数据与未完成步骤。
后续 [p0 现场窗口](2026-10-23-vdec-p0-window.md) 已通过 GCLK/MDEC 访问，停在 compliance；
同时补录本文恢复采样的一次停顿的历史 journal 与 RX 归类。

## 相同地址清单与边界

固定清单共 2,144 个对齐 32 位地址，SHA-256：
`8028286aacd732f62afa32a16eca074c8bb82088c43ce62ae3235dcfd91f59e5`。
`addresses.txt`、含名字与出处的 `register-plan.json` 和每次读取前后的 JSON 行一起留档。

| 控制块 | 实际清单 | 地址证据 |
|---|---|---|
| CLKCTRL | `0xfe000000–0xfe001ffc`，整个 0x2000 窗口，包括保留字 | 厂商 `mesont7.dtsi` 的 CLKCTRL 资源；`drivers/clk/meson/t7.h` 命名偏移 |
| PWRCTRL | ACK、POWER_OFF、ISO、FORCE_RESET 各两字，MEM_PD0–25 | U-Boot `arch/arm/include/asm/arch-t7/register.h:1087–1120` |
| SYSCTRL | 头文件已定义的普通/安全 STATUS；NOC_CFG0、NOC_STS0/1 | 同头文件的 `SYSCTRL_*STATUS_REG*`；NOC 三字见 944–946 行 |
| DMC protection | `0xfe034380–39c` 与 `0xfe036380–39c` | 厂商 `dmc_t7.c:32–40,57–88` 普通 MMIO 的控制寄存器读清单；DT 2541–2542 行 |
| DOS top | 仅 `0xfe32fc00/fc04/fcc0` | 前轮厂商活体读取与候选第 2–8 步已读：RESET0、EN0、MEM_PD_VDEC |

厂商 common_drivers 固定为 `4cfb128d36f8511b2db1bd13c08d5704347ded49`。
T7 `mesont7.dtsi:2689–2702` 将旧 AOBUS 资源定义为地址和长度均零，
不能套用旧芯片 AO/RTI 地址。未知 NIC QoS 和 TZ/firewall 窗口没有凭名称扫描。
`dmc_t7.c` 的 secure exception/status 经 `dmc_rw` 代理，未当普通 MMIO 读取。
因此这里的“全量”是 CLKCTRL 整窗及其余有出处的清单，**没有宣称覆盖全部安全世界状态**。

## 读取与候选防护

厂商 5.15 的 `CONFIG_DEVMEM=n`；沿用其已验证 debugfs `aml_reg/paddr`：
写入一个十六进制地址只更新缓存，随后一个新打开的只读 fd 执行一次 `readl_relaxed`。
两参数才是写硬件，工具从不发送第二参数。实现依据
`drivers/memory_debug/reg_access/reg_access.c:34–51,84–149`。
7.3 用 `/dev/mem` 的 `O_RDONLY`、`PROT_READ` 映射，只执行一次 volatile 32 位 load。

新增 `vdec-register-dump.c` 在打开任一硬件接口前校验**完整**清单；
拒绝内部 `0xfe32260c`、PIC、未知 DOS 地址、未对齐地址与第二个写入值。
每次先输出 begin 地址，读完再输出 address/value，避免只在进程正常退出时才保存快照。

`vim4-vdec` 的 `b9a9164d77b82` 默认 `t7_snapshot_only=1`，只在加载时可选。
内核拒绝第九步及后续步骤、完整 MDEC 和 open/runtime-resume；
第零步仍允许直接撤销第八步的上电。`vdec-window.py snapshot` 在第八步保存
clk/genpd 与同一寄存器清单，随后第零步下电，不读取内部 GCLK。
实际 C store/open 边界测试 13 项通过，strict checkpatch 为 0 errors / 0 warnings / 0 checks；
主仓 VDEC 工具测试 20 项通过。
最终主仓全量测试：`python3 -m unittest discover -s tests -p 'test_*.py'`，
234 项，6 项按条件跳过，无失败。

## 现场与差分

新候选源码 `b9a9164d77b82acf86259145153d2768b4c6ddd2`，完整 Image/DTB/模块集构建通过，
build ID `ddaaa01a6d7c0c02e2d8981d59fd612908232648`，选定模块的 vermagic/BTF 校验通过。
Image SHA-256 `9e6d2fc9b56af9f6341cfb3f02ff83ad582907a1f9ab77d350176a6a525e7523`；
DTB `871e931bb4d901c563ffa292577664a8bdeb2d6c2dcc32f4e93ada36165b59c9`；
完整模块包 `6ecc54d8b32794866caf763175c2527a1e2357c9cc88931bcd433c196a6cf63b`。

厂商窗口于 23:42 UTC 取得双锁；入口基线为 `eeddb005df059a850853876d52ef603aa1af192b`，
PID 1 持有 watchdog，RuntimeWatchdog=30s、RebootWatchdog=60s，五文件及厂商模块清单核验通过。
RAM `sysboot mmc 1:1` 一次性选择 5.15，29.82 秒到登录，实际 build 为
`389f77352dc8ab21aa80d8cf36819bb9da31d7ee`。以 khadas 运行 `amlv4l2h264dec`，
使用前轮同一 SHA 的 640×368/30fps H.264 样本；首次解码缓冲出现后才读寄存器。
全部 2,144 字读取完成时解码仍在进行，随后 `Got EOS`，600 个输出缓冲；无 SError。
`vendor/vendor-dump.log` SHA-256：
`9a97f59f7ad6e7ed1a3c6401d298fbb71b368e57ab014c93c23572aa7d4a1e6e`。

| 地址 | 厂商解码中 | 7.3 第八步 | 含义 |
|---|---|---|---|
| `fe000040` | `ac02a000` | 相同 | SYS 时钟控制 |
| `fe000044` | `ffffffff` | `07f89ff2` | DOS bit1、AM2AXI bits21–23 均 on |
| `fe00004c` | `fffffffc` | `ff99ffd0` | CPU APB bits19/20 均 on |
| `fe00006c` | `b800a000` | 相同 | AXI 时钟控制 |
| `fe000140` | `00000100` | `02000000` | p0 gate on→off；高半字 HCODEC 不同 |
| `fe000148` | `80000000` | `00008100` | VDEC 最终 mux p0→p1、p1 gate off→on；bit31 另属 HCODEC |
| `fe00c000` | `e6b85600` | `e0b8d600` | PWR ACK0 |
| `fe00c010/020/030` | 均 `1941a9ff` | 均 `1f4129ff` | OFF0 / ISO0 / FORCE_RESET0；域 ID 不是原始位号 |
| `fe010500/520/524` | `0 / 3f3f3f3f / 3f` | 相同 | NOC CFG0 / STS0 / STS1 |
| `fe32fc00/fc04/fcc0` | `0 / 3ff / 0` | 相同 | DOS RESET0 / EN0 / MEM_PD |

厂商 clk_summary 中 p0/最终 VDEC 为 799,999,988 Hz，p1 gate off；DOS 与 CPU APB 为
166,666,664 Hz，相关 gate on。genpd 中 VDEC、NIC3、HEVC、NOC/NIC2 为 on，
Wave/HCODEC 为 off；HEVC 的消费者包含温度传感器，不能仅由其 on 状态推断解码依赖。
候选于 23:49 UTC 取得双锁，一次性 `sysboot mmc 1:2`；probe、power、snapshot
三阶段通过。快照收据只含这三项，第八步后读完全部 2,144 字，第零步撤销上电，
`VDEC[4]=1`、runtime suspended；没有执行第九步/完整 MDEC/compliance/H.264。
`candidate/snapshot.log` SHA-256：
`5c271a3100ee3cb0686ee6599de53d25b9ae500ab4adb59795177b9cc2f1ca3c`。

全部 89 条原值、XOR、字段与解释见[逐地址差分附表](2026-10-23-vdec-register-diff.tsv)。
62 条 CLKCTRL 差异对应低半区 31 字；两个快照各自的上下半区 1,024 对全部相等，
是本次观测到的镜像模式，不视为 62 项独立时钟缺失。其余为 PWRCTRL 18、SYSCTRL 3、DMC 6。

- **已匹配**：SYS/AXI 控制、DOS/AM2AXI/两条 CPU APB 门控；CPU APB/DOS 均报告
  166,666,664 Hz。CLKCTRL LOCK0–3、PROT0–3 均为零，NOC 三字与 DOS-top 三字相同。
  VDEC/NIC3/HEVC/NOC/NIC2 两边均 on，Wave/HCODEC 均 off，不存在本轮“HEVC 漏上电”的证据。
- **可定向对齐**：厂商 VDEC p0，候选 p1；父源索引均为 fclk_div2p5、除一、gate on，
  CCF 报告 799,999,988 / 799,999,987 Hz。报告差一 Hz 不是实测晶振差异；同频也不证明路径等价。
  高半字 HCODEC 是独立消费者，不照抄整字。VAPB 另为 666,666,656 / 499,999,992 Hz，
  属共享 VPU 时钟，保留采集驱动所有权；本轮不改它，亦未证明它与内部故障无关。
- **其他消费者与缺口**：ISP/MIPI_ISP、GE2D、DSI/EDP、VI_CLK 状态不同；ISP 源码声明
  MEM_PD13–17，不能把这些外设差异直接当 MDEC 内存掉电。MEM_PD11 高位及 18/22/23/25
  的准确 SRAM 位映射仍缺；PWRCTRL 域 ID→位号缺少 secure firmware 表，不硬编码回写。
- **安全属性**：SYSCTRL STATUS0/1 是 CEC mailbox；SEC_STATUS2 的变化在 bits8–15，
  只找到 SEC_AO_SEC_GP_CFG7 别名，未找到当前固件位定义。不能将名字含 SEC 当成 DOS 授权。
  DMC 差异是起始页 0、结束页 0x7f 的 DRAM 访问监视配置，不能当 APB firewall。
  未公开 TZ 窗口/secure DMC 状态仍未采集；没有据此新增 SMC 代写。

厂商 `h264_multi/vmh264.c:11231,11424` 先 `amvdec_enable()`，再加载微码；
`utils/amvdec.c:85` 在 enable 中直接写内部 GCLK。源代码未要求先用 TEE 为该寄存器代写。
本轮状态差分仍不是 BL31 全部内部状态或所有前置条件的证明。

## 定向候选与下次窗口

修正通过 DT 单独取得 `CLKID_VDEC_0`，在持有 DOS lease 的上电路径中用 CCF 选择 p0，
直接设置 p0 频率，避免 rate selection 又选回 p1；硬件预检拒绝 p1。
不在 probe 时用 assigned-clocks 隐式写时钟，不直接覆盖共享 HCODEC/PWRCTRL 字段。
已提交 `9c5687a94c9bc09999535ce15f4caab094976c01`（`vim4-vdec`），本轮未上板运行此修正。
实际 C 生命周期/时钟错误传播测试 14 项通过，strict checkpatch 为 0 errors / 0 warnings / 0 checks；
持 heavy 锁完成 Image、两份测试 DTB、完整模块集和 `package-vdec.py --once`。
Image 未改动，build ID 仍为 `ddaaa01a6d7c0c02e2d8981d59fd612908232648`；
这是新 DTB/模块组合，须按 manifest 的 source 与哈希辨认，不能只按 Image ID 区分。
新 DTB SHA-256 `67189483760a0eaf4a26a2641397eed29ac652c5ff74812b7e045e147d12c038`；
完整模块包 `4c0e04aef53824b9512fb5cd17f39624d34d77c2553a60a72135dfa6a4463424`；
vdec 模块加载 ID `a25a2242205f01d56d08adf6ad499e5b967c5b17`，vermagic/BTF 校验通过。
当前候选在 Mac `build/vdec-register-diff/fixed-bundle`、VM
`~/build/vim4-vdec-register-diff-fixed-bundle`；VM bundle 同时保留精确 vmlinux/配置/符号及原始模块。
逐文件核验新 bundle 和 debug 哈希后，已删除本任务旧快照 bundle、O= 构建目录、
Mac 旧 bundle/启动 tar；只保留当前候选与调查证据，未清理其他任务目录。

下次须另行安排：先 probe→power→snapshot，核对 p0 gate、mux、频率与 vendor 指纹；
确认下电后才进入十三步（第九步首次内部读仍可能 SError）。snapshot 默认保持内核八步限制；
显式 mdec/compliance/H.264 动作才以 `t7_snapshot_only=0` 加载，仍受 power/MDEC 收据和 open 门禁。
只有完整 MDEC 通过才进入 compliance，再做 H.264 正确帧。继续双锁、一次性启动、看门狗；
三分钟未回基线停止并报告人工复位需求，不盲目补写未解释的差异。

## 恢复与后续

两个窗口分别于 23:49:39 / 23:56:37 UTC 清理并释放锁，均回
`eeddb005df059a850853876d52ef603aa1af192b`；五文件、cmdline、Wave5 文件 SHA
`e88df353c730e5d82bbef8335788a28d5f71cfc7a4e1b8b5854ef00046d4b667`
及加载 ID `8e2dedd2579d126adb8ba710eec2082ec1753b05` 与各自入口相同。
One-KVM/manager/Wave5 monitor active、UDC configured、taint 0、无私有模块挂载或实验模块残留。
两次均正常重启，无需看门狗/RESET 回退，也无需 usb-pd-init；临时 boot config、payload、私有模块目录已删。

| 回基线后 300 秒运动画面 4K H.265 | 帧数 / fps | drop/lost/PLI | freeze | HID |
|---|---|---|---|---|
| 厂商窗口后 | 18,306 / 59.9989 | 全零 | 0 | 按下/释放、绝对/相对鼠标、点击、滚轮全通过 |
| 候选窗口后 | 18,213 / 59.6857 | 全零 | 1，最长呈现间隔 1.647 秒 | 同上全通过 |

第二次 baseline dmesg 在启动后 45.394 秒有 RX `5v-or-align` readiness revoked，
与一次停顿相符，随后恢复；不是连续无停顿通过。未修改采集驱动或服务配置，未新增 panic/oops/SError。
完整采样、UART、前后 pstore 包与基线 JSON 均留在对应 vendor/candidate 证据目录。
