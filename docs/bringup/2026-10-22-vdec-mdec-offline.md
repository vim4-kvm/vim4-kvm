# 2026-10-22：T7 MDEC SError 离线排查与单读门禁

本轮完全离线，未连接板子、加载模块或重启。发现明确的软件遗漏：厂商调度器在
首次 MDEC 操作前设置 VDEC 普通内存访问策略，候选没有对应 TEE 调用；同时将
500MHz 对齐厂商 T7 默认800MHz，增加内存PD、复位和门控核验，以及独立 MDEC
单读阶段。**这些是源码差异修正，尚不能证明 SError 已根治**；BL31/BL32 内部
实现不可见，仍须用户在板边验证。前次实测见 [第二次现场](2026-10-22-vdec-field2.md)。

## 已有异常证据

本地 `logs/kernel-edge/vdec-field2/pstore-after/var/lib/systemd/pstore/dmesg-ramoops-0` SHA256
`297cd35d9854b6004261ef1691bef95228f55924461058e7d7609a82de2c3e13`，
510–575行；同目录 `dos-enable-objdump.txt` 保留原模块反汇编。

```text
102.576202 pre-DOS power: VDEC[4]=0 NIC3[39]=0 rate=499999992
102.576292 power test DOS_SW_RESET0 offset=0xfc00 value=0x0
102.576318 power test complete: VDEC off; no firmware or DMA started
159.485128 pre-DOS power: VDEC[4]=0 NIC3[39]=0 rate=499999992
159.485176 SError Interrupt on CPU0, code 0xbf000002
PID 2040 Comm v4l2-compliance; pc _regmap_read+0xd0/0x270
x20=x4=x3=0x2638
_regmap_read -> _regmap_update_bits -> regmap_update_bits_base
 -> dos_enable+0x6c/0x88 -> vdec_enable+0x10c/0x158
 -> aml_vdec_runtime_resume -> fops_vcodec_open
```

DOS基址 `0xfe320000`；PIC_DC word `0x098e` ×4 = byte `0x2638`，物理
`0xfe322638`。反汇编 `dos_enable+0x68` 调用该RMW，异常栈为返回位置+0x6c。
此前依次访问 `DOS_GCLK_EN0=0xfe32fc04`、`GCLK_EN=0xfe32260c`。
SError异步，仍不能排除前一写引发；不能把PC当作精确失败总线事务。
原单读只证明DOS-top可读和域可下电，没有证明MDEC内部可访问；未运行固件或解码DMA。

## 厂商实际调用链与首次 MDEC 前置条件

出处固定为 VM `~/src/linux/common_drivers` 提交
`4cfb128d36f8511b2db1bd13c08d5704347ded49`。下文路径缩写：
`U=drivers/media_modules/frame_provider/decoder/utils/`，
`C=drivers/media_modules/common/media_clock/clk/`，
`R=drivers/media_modules/include/regs/dos_registers.h`。

T7 DT `arch/arm64/boot/dts/amlogic/mesont7.dtsi:2435–2459` 选择
`amlogic, vdec-pm-pd`；`U/vdec_power_ctrl.c:887–895,911–916` 绑定 PM_DOMAIN。
`U/vdec.c:4980–5000` 的 `vdec_poweron()` 在引用计数/状态检查后调用这个实现。
不能因为同文件有 legacy 上电实现，就认定T7执行了它。

| 顺序/条件 | 厂商实现、寄存器与出处 | 旧34ab候选 → 本轮 |
|---|---|---|
| 总线及功能时钟 | `drivers/clk/meson/t7.c:3733–3855,7129`：SYS_DOS为SYS_CLK_EN0_REG0 bit1；VDEC两路为CLKCTRL offset140/148低半字，source9:11、div0:6、gate8、最终mux148 bit15；与HCODEC高半字独立 | DT两时钟正确，未改共享provider/reset |
| 功能时钟开启、设频 | `U/vdec_power_ctrl.c:151–157,268–282`：开clk_vdec_mux，hi_enable，然后domain get；`C/clk.c:105–107` → `C/clkg12.c:732–768` 无条件取max；T7 `common/chips/decoder_cpu_ver_info.c:237–252` 为800MHz | 原500MHz → 请求800MHz；仅对齐厂商值，不断言500MHz必错 |
| DOS总部门控 | `C/clkg12.c:479–486,521` 设频前RMW `DOS_GCLK_EN0[9:0]=3ff`，不动HCODEC[26:12]；`R:390–391` | 原值相同，但原先不读回；现在写后核验。保留严格SMC确认后才允许DOS的边界，因此此笔仍在domain on之后，与厂商helper位置不同 |
| 电源/父域/隔离转换 | `drivers/power/sec_power_domain.c:63–69,254–258,307`：VDEC=4、父NIC3=39，secure power-on；`U/vdec_power_ctrl.c:84–96,275–282` domain get；T7 `dos_local_config:195–202`直接返回 | 已有GET确认4/39=0，保留；不能由GET推导内部RAM/隔离位已正确 |
| 本地RAM和复位状态 | T7没有Linux本地写序列；预期由secure转换完成。`DOS_MEM_PD_VDEC` word3f30，`DOS_SW_RESET0` word3f00（`R:390,436`） | 原未检查 → 读两者，非0拒绝后续MDEC。只读状态验证，不用其他SoC写法补救 |
| **普通内存访问策略** | `U/vdec.c:4863`先prepare_run，随后调用codec run；`vdec_prepare_run:4510–4537` 对VLD目标调用 `tee_config_device_state(DMC_DEV_ID_VDEC,0)`；`h264_multi/vmh264.c:11222–11238`随后amvdec_enable | **原完全缺失 → 在MDEC前调用SMC并检查a0=0**。这是DMC设备策略，不是已证明的APB访问权限修复 |
| MDEC/VLD等内部全局门控 | `U/amvdec.c:72–87`：AMVDEC_CLK_GATE_ON数项 → GCLK_EN=3ff → PIC_DC清bit31；但 `U/amvdec.h:91–96`将这些宏定义为空，VLD_CLK本身也被注释 | 原DOS_GCLK_EN0/GCLK_EN值已相同；现在GCLK_EN写/读回核验，才允许PIC_DC。未发现可补的独立MDEC门控位 |
| 首次PIC_DC | 同上87行RMW bit31；`R:111,223` PIC_DC=098e、GCLK_EN=0983 | 原直接RMW → 显式测试中只读一次，成功下电后才允许普通open的RMW |

关于用户列出的其他寄存器，逐项核对结果：

- **AO_RTI_GEN_PWR_ISO0、DOS_MEM_PD_VDEC=0、RESET0=fffffffc→0**：
  `U/vdec_power_ctrl.c:410–461`是 **legacy** 分支：sleep清位→10us→reset→
  clock→memPD清零→iso清位→MCRCC_STALL清零；PM匹配已证明T7不走这里。
  `dos_local_config:207–214`的memPD→reset→20us→0→10us→memPD也只对S5/T5M等生效。
  未把这些写入T7路径，未假造AO地址或reset DT。
- **DOS_GCLK_EN3**：`C/clkg12.c:499–506`属于HEVC/HEVCB，word3f35、bytefcd4；
  VDEC_1分支只改EN0。H.264若启MMU可另外申请HEVC，但本候选canvas输出没有该域，
  不能为MDEC试写EN3或开启共享HEVC域。
- **VLD/PSCALE**：`U/vdec.c:5130–5166`的任务级reset位注释列出VLD3/4/5、
  IQIDCT6、MC7、DBLK8、PIC_DC9、PSCALE10等，实际只写3/4/5/7/8/9→0，
  不等于全部位都应reset。`h264_multi/vmh264.c:9043–9055`在上下文恢复中设置
  POWER_CTL_VLD并关PSCALE共享路径；同文件11231首次amvdec_enable在reset_core之前，
  所以这些不是厂商首次PIC_DC前的前置写入，不能用来解释本次open失败。
- 地址映射：T7 `.reg_compat=NULL`（`common/chips/decoder_cpu_ver_info.c:237–239`）；
  旧接口 `drivers/media/common/arch/registers/register_map.c:796–815` 同样word×4，
  不是“新旧接口相差一个MDEC bank”。

## Secure接口及仍不可见的部分

| SMC | 参数/含义 | 证据与处理 |
|---|---|---|
| `82000093` | x1=domain，x2=1上电/0下电，其余0 | `drivers/power/sec_pwr_ctrl.c:9–16`；T7 VDEC4、NIC339由genpd父子管理，不额外手动SET |
| `82000095` | x1=domain，其余0；a0=0 on/1 off | 同文件19–26；已有严格核验，其他返回拒绝DOS |
| `b200000e` | x1=13(VDEC设备ID)，x2=0普通策略，其余0 | `drivers/tee/tee.c:48–58,825–834`；`include/linux/amlogic/tee.h:32`；新增调用，a0非0返回EACCES并下电 |
| `b200000f` | x1=15 H264_MULTI，x2=0 legacyVDEC，x3=0不swap | 既有固件加载路径；与以上策略不同，本次诊断不调用 |

没有在T7选中的厂商Linux路径找到独立“MDEC内存PD/时钟”SMC。通用TEE读写寄存器
API虽存在（`tee.c:104–110,856–878`），该VDEC上电链没有使用它们，不能猜参数调用。
`vpu_mempd_psci_smc`（`sec_pwr_ctrl.c:29–38`）用于VPU memPD编号空间，不能拿来替代DOS。
缺少BL31/BL32内部代码，不能逐条证明secure隔离、RAM上电、reset的微观顺序；
CONFIG_DEVICE_SECURE源码说明的是内存访问默认策略，尚不能证明它控制CPU到MDEC的MMIO。

## 驱动和脚本的可观察行为

`aml_vdec_hw.c`的 `t7_prepare_mdec()` 共用于显式测试和runtime resume：
策略SMC→DOS-top reset/memPD只读检查→EN0写/读回→GCLK_EN写/读回。
`mdec_test` sysfs写1要求allow_t7_power、无上下文、runtime suspended和本模块
power_test已通过；然后完整上电、以上前置步骤、**PIC_DC只读一次**、下电并GET核验。
读属性仅返回缓存。成功路径没有PIC_DC写、IRQ使能、微码、DMA或任务reset。

普通open/runtime resume都要求power_test和mdec_test通过；power_test重跑会撤销
mdec通过状态。模块重载也全部清零。前置检查或读失败仍尝试正常关时钟/domain，
下电无法确认则保留原fault/模块pin/DOS poison机制；解码超时DMA quarantine未改。
返回错误由脚本封锁该boot的后续阶段；SError/挂总线不能靠返回值或用户态timeout回收。

`vdec-window.py`阶段顺序变为 `probe → power → mdec → compliance → h264 → wave`。
mdec≤8s，确认passed=1、VDEC=1、runtime suspended，再关allow；每个模块生命周期
进入compliance/H264前均重做power与mdec。失败不强卸载、不重试、不恢复编码器争用DOS。
打包只收vdec5；vdec3/4仅允许恢复动作，已知panic提交继续拒绝。

## 离线产物与验证

内核分支 `vim4-vdec`，基于 `1262da082ba5`，本轮两个提交：
`a2bfd6a3e3c71`（MDEC门禁/读回/800MHz）、`eb3ba8f704405`（TEE策略）；
均保留在独立 `~/src/linux-7.3-vdec`，不修改主工作树。
持heavy锁完整构建Image、两个DTB和2336模块，独立
`O=~/build/kernel-vim4-vdec-field`；release `7.3.0-vim4kvm-vdec5+`，build ID
`3952d858af0b4d3a16a0050b9642ffc0d63fd742`。VM包 `~/build/vim4-vdec-mdec-bundle`，
Mac包 `build/vdec-mdec-offline/bundle`，manifest记录完整源码提交、模块清单及BTF/vermagic核验。

| 产物 | SHA256 |
|---|---|
| Image | `859b2d588a1c2845c348c8e96641e9fbcf70d8288a820ade013e1b0c9d895ba1` |
| vim4.dtb | `04cc3d480cdb8ee462f5263508114ddec449331f9216db93f286ca02407ed540` |
| modules.tar.gz | `69ec0ed7c9c2c1572763ccbc9c3aa68b012a9e86e82bd2263dd096ac93e945b9` |

构建日志无warning/error；故障注入9项通过；严格checkpatch为0/0/0。
主仓离线184项通过、跳过5项。日志均在 `logs/kernel-edge/vdec-mdec-offline/`。

## 下次现场清单（本轮未执行）

串口在线、用户在RESET旁，确认其他任务窗口结束。核对当时基线；脚本当前合同仍为
build ID `f283ab1f8a001a19bab5247afc4f9b0c00c1da99`，若基线改变，先重新离线准备合同，
不能跳过校验。各窗口持board/heavy双锁，结束释放；不正式部署vdec。

```sh
# 仅准备，未执行；ACTION按下面步骤逐次选取。
python3 packaging/kernel-edge/vdec-window.py ACTION --execute --at-board \
  --manifest build/vdec-mdec-offline/bundle/manifest.json
```

1. 上传本轮完整bundle、工具和固定6帧320×256样本；boot-install安装独立release，
   手动锁内重启候选。先arm-baseline把磁盘Image/DTB恢复并核验，保证下次重启回基线。
2. `probe`：allow默认N，udev settle，自动/手动open为EPERM；无DOS访问。
3. `power`：上电，GET4/39为0，DOS_SW_RESET0单读，下电GET4为1。频率已改800MHz，
   仍需重新验证，不能沿用vdec4通过收据。
4. **`mdec`：新增最高关注步骤**。串口应依次留下策略SMC a0、reset/memPD、EN0、
   GCLK_EN写前和读回、PIC_DC读前与值、下电完成；只读PIC_DC一次。非0前置状态或
   SMC拒绝即停，不能现场改memPD/reset“试一下”。GCLK_EN读回本身也可能SError。
5. 全部通过才compliance≤20s，然后小H264≤10s、正确帧比较；1080p性能仍需单独
   准备并审核命令，现脚本不自动做。Wave小尺寸尝试只在前面通过后，不能绕过失败。
6. 失败保存串口、dmesg/pstore；若失联先等60s给panic=20自动恢复。仍失联才按约定
   单行发 `NEED_RESET` 请求，15秒探测、最长10分钟。恢复后取两个pstore目录，不重试。
7. 无论结果，恢复现场开始时基线和原Wave模块；核验build ID、两服务active、UDC
   configured、真实HID和编码采集。not attached时双锁内usb-pd-init后再验。

本轮无恢复实测；候选仍有需要RESET的风险。
