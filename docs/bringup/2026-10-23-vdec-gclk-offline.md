# 2026-10-23：T7 GCLK_EN 访问条件与分步候选（离线）

确认 `0xfe32260c` 是 DOS 内部的 GCLK_EN；厂商用普通 MMIO 写入，没有找到 T7
通过 TEE 代写的路径。发现并修正一个确定的顺序差异：厂商在 secure VDEC 上电前
设置 DOS_GCLK_EN0，而旧候选在上电后设置。新候选显式持有 NIC3 父域，把 EN0
移到 VDEC 上电前，并拆开单寄存器探针。**尚未证明该差异就是 SError 根因**；
厂商也没有读取 GCLK_EN 的用例，不能预先保证它可读。

本轮未 SSH、未连接串口、未获取 board 锁、未加载模块或部署；等用户安排批量窗口。
已有异常与恢复见 [MDEC 远程窗口](2026-10-23-vdec-mdec-window.md)，
前次厂商审计见 [MDEC 离线记录](2026-10-22-vdec-mdec-offline.md)。

## 异常范围与地址

完整 pstore 已离线复读：
`logs/vdec-mdec-window/pstore-after/var/lib/systemd/pstore/dmesg-ramoops-0:542–622`，
SHA256 `931852b5d830fd06376e2f865b7a385c4417e38c7de77030675ed7e3d9700c6c`。

```text
23.369024 VDEC[4]=0 NIC3[39]=0 rate=799999987
23.369055 CONFIG_DEVICE_SECURE(13,0) a0=0x0
23.369065 reset=0x0 mem_pd=0x0
23.369071 DOS_GCLK_EN0=0x3ff
23.369077 writing GCLK_EN offset=0x260c
23.369108 SError 0xbf000002
pc _regmap_read+0xd4/0x270; lr _regmap_read+0x68/0x270
x20=x4=x3=0x260c; x24=0x3ff
regmap_read -> t7_prepare_mdec+0x1ac/0x200
 -> aml_vdec_t7_mdec_test -> mdec_test_store -> sysfs_kf_write
```

这是异步 SError：PC/参数对应 GCLK_EN 回读，但不能排除先前 posted write 引发。
没有成功回读 GCLK_EN，也没有执行本次 PIC_DC 单读、微码或解码 DMA。

下面出处固定为 `~/src/linux/common_drivers` 提交
`4cfb128d36f8511b2db1bd13c08d5704347ded49`；路径都相对这个仓库，避免与
5.15 主内核树混淆。缩写 `M=drivers/media_modules/`，`U=M/frame_provider/decoder/utils/`，
`C=M/common/media_clock/clk/`，`R=M/include/regs/dos_registers.h`。

| 块/寄存器 | 地址与依据 | 访问边界 |
|---|---|---|
| DOS aperture | `arch/arm64/boot/dts/amlogic/mesont7.dtsi:2688–2691`，基址fe320000/10000；APB4描述1323–1328 | 映射不等于内部电源可用 |
| GCLK_EN | `R:223` word0983 ×4=260c，物理fe32260c | DOS内部全局门控；不是CLKCTRL或AO |
| PIC_DC | `R:111` word098e ×4=2638，物理fe322638 | MDEC内部寄存器 |
| DOS-top EN0/reset/memPD | `R:390–391,436`，fe32fc04/fe32fc00/fe32fcc0 | 厂商先访问EN0，后请求VDEC域；不能因此认为整块DOS可在断电时访问 |
| CLKCTRL | `drivers/clk/meson/t7.h:25,76–79`，fe000044、fe000140/148 | 独立于DOS aperture的系统门控及VDEC功能时钟 |
| T7 PWRCTRL | U-Boot `arch/arm/include/asm/arch-t7/register.h:1091–1094` 的ISO/FOCRST位于fe00c020/24/30/34 | 只有地址，没有足以核实VDEC位号的secure内部表；没有猜位写入 |

T7 `M/common/chips/decoder_cpu_ver_info.c:237–239` 的 `reg_compat=NULL`，
`M/common/register/register.c:108–159,174–188` 两套访问分支最终均为word×4的
readl/writel；旧分支 `drivers/media/common/arch/registers/register_map.c:318–348,796–815`
也相同。没有证据支持把GCLK_EN换bank或地址。

## 首次内部访问前的条件与顺序

| 条件/顺序 | 厂商证据 | e8ebc2e旧候选 → 新候选 |
|---|---|---|
| SYS_DOS总线时钟 | `drivers/clk/meson/t7.c:7129`，SYS_CLK_EN0_REG0 bit1；主线名字CLKID_SYS_DOS | 两者都持有；不拿它替代功能时钟 |
| VDEC功能时钟先使能 | `U/vdec_power_ctrl.c:151–157,268–282` 的clk_vdec_mux及hi_enable；`C/clk.c:105–107` | 都通过CCF开启，未绕过provider直写共享CLKCTRL |
| EN0先于VDEC域 | `C/clkg12.c:479–486,521,732–768`：EN0[9:0]=3ff → clk_set_rate(max) → 返回power helper后domain get | **旧顺序相反；新路径先持NIC3、读EN0、保留高位写低10位、读回，再设800MHz和domain get** |
| 功能时钟源/频率 | `drivers/clk/meson/t7.c:3733–3855`：140/148低半字source[11:9]、div[6:0]、gate8、148最终mux15；T7能力表237–252为800MHz | 地址/位/父源表一致。主线保留当前mux父路径；未证实它有错。日志的clk_get_rate不是物理波形证明 |
| VDEC=4、父NIC3=39 | `include/dt-bindings/power/t7-pd.h:10,46`；`drivers/power/sec_power_domain.c:254–258,307`；`U/vdec_power_ctrl.c:84–96,275–282` | 主线PWRC_T7_DOS_VDEC_ID同为4。新DT另列NIC3引用，避免EN0早期访问时父域被自动关掉；GET需39=0、4先=1后=0 |
| RAM、隔离、上电复位 | `U/vdec_power_ctrl.c:195–202` 对T7直接返回，无Linux本地序列 | 保留secure genpd；域on后逐笔读EN0、reset、memPD。reset或memPD非0即拒绝内部访问 |
| 普通内存策略 | `U/vdec.c:4510–4537,4863` → `drivers/tee/tee.c:825–834` | 仍调用b200000e(13,0)，检查a0；该调用是DMC策略，不能当APB权限证明 |
| 内部GCLK及首个PIC_DC | `U/amvdec.c:72–87`：GCLK写3ff → PIC_DC清bit31；`U/amvdec.h:91–96` 的AMVDEC_CLK_GATE宏为空 | 新探针先读GCLK，另一步写，另一步回读，最后只读PIC_DC；正常open仍须整套测试及下电通过 |

没有在T7选中的decoder路径找到额外的DOS专用APB/AXI clock申请。VAPB是VPU时钟，
不能凭名字加到VDEC。AM2AXI0/1/2为系统共享桥：厂商 `t7.c:7141–7143` 保留门控，
7.3 `drivers/clk/meson/t7-peripherals.c:1238–1240` 已全部标critical；未找到哪个桥
单独对应本次内部APB事务的硬件说明。HCODEC使用140/148高半字，候选不修改它们。

没有发现必须先写DOS_GCLK_EN3的证据；它用于HEVC/HEVCB（`C/clkg12.c:499–506`）。
本候选canvas H.264不申请HEVC。任务级VLD/PSCALE/reset顺序及legacy AO路径在
前次记录中列明：`U/vdec_power_ctrl.c:410–461` 的AO sleep/iso、memPD和reset写
不是T7 PM分支，不能搬来“补齐”。

## Secure-only核对与剩余边界

厂商调用链为 `WRITE_VREG → write_dos_reg_comp → write_dos_reg/aml_write_dosbus
→ writel`，不经过OPTEE代理。整个media_modules树对GCLK_EN只有定义和
`amvdec.c:85` 这一处写；**没有找到合法读用例，也没有找到它是write-only的说明**。
因此下次先读可以区分“写之前已不可读”，不能保证这笔读本身安全。

电源SET为SMC `82000093(domain, on)`，GET为`82000095(domain)`，0表示on、1表示off
（`drivers/power/sec_pwr_ctrl.c:9–26`）；与7.3 `drivers/firmware/meson/meson_sm.c:49–50`
一致。设备策略`b200000e(13,0)`与微码加载`b200000f(15,0,0)`含义不同。
通用TEE寄存器API `b200e052/e053` 见 `tee.c:104–110,856–878`，但没有VDEC
调用证据或对应固件允许的寄存器表，**没有改用该SMC试探代写**。

现有U-Boot包含T7 PWRCTRL地址定义和BL31/BL32打包脚本，没有这版BL31内部的
VDEC power switch、ISO、MEM_PD位表及执行顺序。不能从GET=0或memPD=0推导隔离
一定解除，不能把domain ID当ISO bit号。若新探针仍失败，下一缺口就是这版secure
firmware的实现/寄存器访问属性；本轮没有将猜测写成新的复位、隔离或SMC操作。

## 单步接口与失败回收

`aml_vdec_hw.c:678–862` 共用初始化实现，sysfs `register_step` 写数字顺序推进。
读取属性只返回缓存，不允许跳步。需allow_t7_power、power_test通过，无context，
runtime suspended；跨调用保持时钟、域引用及module pin。runtime状态不代表资源已释放。

| step | 操作 |
|---|---|
| 1 | 开两时钟、持NIC3；SMC确认VDEC off/NIC3 on；不碰DOS |
| 2 / 3 / 4 | 分别读EN0、保留HCODEC高位写EN0低10位、读EN0核验 |
| 5 | 设800MHz、取VDEC域、GET确认4/39 on、设置普通内存策略；不碰DOS |
| 6 / 7 / 8 | 分别读EN0核验SMC后仍开启、读reset=0、读memPD=0 |
| 9 / 10 / 11 | 分别首次读GCLK_EN、写3ff、读回核验 |
| 12 | 只读PIC_DC一次 |
| 13 | 关时钟→放VDEC→放NIC3引用；GET4=off后才设置mdec_test通过 |

每个寄存器步骤只有一笔DOS read或write，没有隐藏RMW。日志含begin/complete、
step、offset、value；mb约束完成标记的顺序，但不保证异步SError精确归因。
CCF/SMC步骤内部当然可能操作多个硬件寄存器，不宣称一笔系统级总线事务。

返回错误时不再访问DOS，尝试仅经clock/genpd正常下电；本probe拒绝再次诊断。
下电状态不确定则保留fault/模块引用/DOS poison，不panic、不归还解码DMA。
正常响应且人为中止可写step=0，不碰DOS，不授予open权限。
若sysfs命令超时、SError或SSH失联，不再写abort、不卸载、不恢复编码器争用DOS，
只等看门狗回基线。不能用用户态timeout证明MMIO或DMA已经停止。

`vdec-window.py mdec` 现在以13条独立、各8秒超时的sysfs命令推进，逐条核对缓存收据；
首错即停，后续compliance/H.264/Wave的boot收据门禁不变。为每次重新加载后的
compliance/H.264准备时也重做完整分步流程；不沿用前一模块的硬件状态。

## 离线构建与验证

分支 `vim4-vdec`，未改变其0afc7546基底或正式内核分支。新增提交：
`acc92fa83f4e5`（NIC3 binding），`c6fc96a347d09`（顺序/探针/DT/生命周期测试）。
独立worktree `~/src/linux-7.3-vdec`，独立O目录 `~/build/kernel-vim4-vdec-field`。
完整候选仅持Mac heavy锁构建：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build sh \
  /mnt/mac/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/build/vdec-gclk-offline/build-vm.sh
```

完整构建通过，无warning/error；release `7.3.0-vim4kvm-uhd1+`，2335模块，
四个选定模块vermagic/split BTF核验通过。build ID
`4aaef5382254d02368d0f49efc680a2059c04289`。
VM包 `~/build/vim4-vdec-gclk-offline-bundle`，Mac副本
`build/vdec-gclk-offline/bundle`；五个artifact哈希逐项复核通过。

| 产物 | SHA256 |
|---|---|
| Image | `fe5be0a0416c7b2e74b7f27e4a67b95bcfc1024383ca0fdc1b1d8fe5219eaf9a` |
| vim4.dtb | `c70ec9521dfe37e4903aeda89f673a0c603fe06fa6714108c754886cbc5246b2` |
| modules.tar.gz | `d3e41ca64d78e2ae20edbc1744928d83922f1c2629e8ade6414b9de1056ad669` |

两个新提交分别strict checkpatch为0/0/0；实际C函数故障注入Mac/VM各10项通过；
runner 18项通过；主仓232项（226通过、6跳过）。日志在 `logs/vdec-gclk-offline/`。
FDT复读候选okay、VDEC4/NIC339两引用；normal layout仍disabled。
为释放VM空间，仅删除本O目录四个可重建链接中间文件，保留vmlinux/BTF/模块和构建stamp。

## 下次批量窗口清单（未执行）

1. 重取届时基线ID、五文件和看门狗PID1持有/30/60秒证明；921600串口先留档。
2. heavy→board双锁，RAM一次性候选/私有模块；默认DT disabled、参数关闭，不正式部署。
3. 依次probe（自动open=EPERM）→power（reset单读及下电）→mdec。
   mdec的step2是新的断VDEC/持NIC3条件下DOS-top首读，仍有总线异常风险。
   step4成功才SMC上电，step6核验门控未丢失，step9成功才允许step10写入。
4. 以最后begin/complete定位，失败结束窗口，不跳读试写；13步成功才compliance、短H.264、1080p。
5. 超时/失联等待看门狗回默认基线，最长180秒；仍失联才在终端单独输出约定的
   NEED_RESET提示并停止。恢复后取/sys/fs/pstore和/var/lib/systemd/pstore，不重试硬件。
6. 回基线确认原Wave模块、服务active、UDC configured、真实HID、编码/采集约5分钟，
   清理本轮私有临时文件，释放两锁。UDC not attached时锁内usb-pd-init后重新核验。

本轮没有新的上下电、寄存器可访问、正确帧或恢复实测。风险仍是首读/写入可触发
SError或总线挂死；看门狗上次已真实恢复，不保证所有secure/fabric故障都能恢复。
