# T7 音频处理、TDMD 与完整构建（仅离线）

本轮未访问板子、未安装产物。续接[基础系列](audio-routes-offline.md)，在独立 VM
工作树 `~/src/linux-7.3-audio-routes` 的 `vim4-audio-routes` 上增加 26 个提交，
从 `e934ed1e3b87f` 到 `e3eb8eb1e400e`。正式 `vim4-kvm-7.3` 未改动。
厂商固定版本仍为 Linux `80a07ad5406d`、common_drivers `4cfb128d36f8`。

新增的是可审查的主线框架候选，不是厂商功能、稳定性与性能已追平的证明。
正式硬件统计保持 **16 项：0 完全、5 部分、11 缺失**，另有 eARC 选装；
其中 A07/A11/A12/A13 新增组件、路由或实例候选，A14 新增正常录音时的硬件检测组件。
VAD 的低功耗采集交接和 DSP 远端固件仍有交付缺口，不能统称“只待上板”。

## 逐项结果与边界

| 项目 | 本轮交付 | 仍未交付或未验证 |
|---|---|---|
| TDMOUT A/B/C/D | T7 compatible、独立 gain bank、每声道 gain、ramp、reset 后缓存恢复；四 lane 静音先于停机；AED 输入 mux；T7 FE 先触发后端再触发 FRDDR | 真实引脚/OE、电气接口、时钟精度、停流爆音和长期并发未测；HDMI 专用路由仍归显示任务 |
| TDMD / A07 | D 输入/输出时钟、共享 gate、reset 42、独立 MMIO、TODDR source 18、D interface；SoC 节点 disabled；合成全双工 DT 夹具 | 未建立真实板级 pinmux/codec；不能直接部署夹具 |
| TDMIN_LB | 专用 compatible，slot 字段为 [11:8]，普通输入为 [12:8]；越界先拒绝；参考选择 TDMOUT B=13 | 未验证参考时钟与实际播放并行；普通 T7 输入保留厂商 enable bit26，LB 不套用此位 |
| Loopback A/B / A11 | 独立 component＋capture DAI；PDM/数字输入与 TDMIN_LB/ASRC B 两路 DAPM；各 1–16 通道、总计 2–32；双 channel-sync；失败清理 | 厂商当前启用 A、禁用 B；PDM4＋参考2 的真实顺序、FIFO 相位及长时同步未测 |
| ASRC A/B / A12 | 独立 component＋capture DAI；标准输入/输入采样率控件；SINC/AA SRAM、相位、auto-adjust、硬件 watchdog、超时与时钟排他回收；B 固定 source6、输出16k | A 输入变率须停流后更新 Input Sample Rate；未接管专用 RX 的变率策略。漂移补偿、SRAM 上电及功耗需硬件证明 |
| AED / A13 | component＋playback DAI；FRDDR 独立 tap[3]→AED→TDMOUT AED mux[31]；双 RAM、20段/通道 EQ、DC、全频/三段 DRC、音量与系数 TLV controls；默认旁路 | 当前后端明确限制 48k 双声道、TDMOUT B 首 lane；未交付其他 AED 目的端、任意多声道处理、噪声检测算法、实时系数切换或声学验收 |
| VAD / A14 | 独立辅助 component；16k PDM 已运行路径的 DAPM 检测、FIR/LUT、voice IRQ、只读累计事件、标准 wake IRQ hook；默认不启用唤醒 | **未实现**厂商 SRAM/DDR 录音交接、PDM 低功耗保留、整机 suspend 恢复与关键词识别；不得解除当前挂起限制 |
| DSP0/1 / A15 | 固定源码依赖审计及不可交付原因，见下文 | 当前输入缺少远端固件、可用 loader/SDK 与版本化消息/共享内存协议；未写私有 ioctl 兼容层冒充交付 |

ASRC SRAM 由 AUDIO genpd 的平台供电合同管理；厂商 `resample_hw.c:119` 的
`HHI_AUDIO_MEM_PD_REG0 = 0` 是整寄存器全清，无法据此证明各 SRAM 位的独占归属。
本实现没有复制该全局写法。上板先验证冷启动和 AUDIO 域重启后的系数 RAM；若固件域
合同不包含该 SRAM，必须先补有明确位定义的供电资源，不能用全清寄存器掩盖问题。

更正前轮的 lane 判断：`tdm_match_table.h:463` 等 T7 实例取 `LANE_MAX1`，
`tdm_hw.h:17` 将其定义为 **4**。通用 `regs.h` 中存在 MUTE4–7 等符号，不能证明 T7
有八条 lane。前轮文档中的“八 lane 缺口”已更正；GAIN_VER3/OE_V2 扩展 bank 差异属实。
没有为缺少调用证据的 OE force 模式添加猜测性电气配置。

## 框架、路由与控件合同

扩展现有 `axg-*`、Meson CCF/reset 与 YAML；ASRC/loopback/AED/VAD 分别新写标准
ASoC component、DAPM、ALSA controls，没有新增私有 ioctl、sysfs 或固件 ABI。
系数数据保留原版权及 GPL/MIT 声明，没有整体搬入厂商驱动。

AXG card 增加标准 `convert-rate` / `convert-channels` 后端约束。存在转换级的 card
不再用全部后端能力求 FE 采样率/通道交集，由各后端 fixup 和 DAI hw_params 校验。
无这些属性的 card 保留原协商。转换属性必须对应真实硬件级，不能用来把不支持的
采样率变成“软件已转换”。格式交集不放宽，TDM 参考后端继承原接口 fixup。

新增 `sound/soc/meson/test-data/t7-audio-processing.dts` **仅为编译夹具**，沿用数字
夹具并添加 TDMD、ASRC、loopback、AED、VAD。它没有 pinmux 或真实模拟端点，未进入
板级 DTB Makefile。保留 `/sound`、RX 节点、TODDR_A 合同和 FRDDR_A/TDM_A 显示分配。
图测试读取实际 C route 数组，检查可能路径、无反馈自环、DAI 独占与 MMIO 不重叠；
不证明 ALSA probe、动态 DPCM 次序或物理连通。真实声卡确认前不发布假端点 UCM。

合成参考路径：PDM 16k/4ch＋TDM_B 48k/2ch→TDMIN_LB→ASRC B 16k/2ch→
Loopback A/B→TODDR_B 16k/6ch。ASRC A 夹具选 SPDIF 输入以避免跨卡抢占专用 RX；
驱动保留 source8 能力，但接入该源需要独立的共享资源与变率设计。

AED 三个标准 bytes TLV 控件使用大端 u32 数组：EQ 为 200 个 Q3.23/26bit 系数，
每组 `[b0,b1,b2,a1,a2]`，两声道各20组；验证二阶分母的严格稳定条件。
全频 DRC 为18字，顺序为两组 release/attack 系数对、阈值与斜率，然后 RMS 对、
delay、输出阈值、恒定单位斜率、offset；输出阈值必须等于第二 knee，delay≤255。
三段 DRC 为每段10字，顺序见驱动中的固定默认表；时间系数为 Q23 且互补，斜率/
增益为 Q18。更新只允许引擎停止时；不声明实时原子调参能力。LR 音量为 0.5dB 步进，
master 的0.125dB 步进使用原始标准整数 volume，避免伪造整数百分之一 dB 的 TLV 单位。

## DSP 与关键词识别的不可交付证据

以下均来自固定厂商树，不把“没找到”推导为特定闭源许可证：

- `sound/soc/amlogic/auge/dsp/hifi4dsp_api.h:9–30` 需要 fw_name/fw1_name/fw2_name、
  物理加载地址，并定义 HIFI4DSP_LOAD/START/STOP 等私有 ioctl；这些 host 声明不是固件。
- `dsp/rpc_client_shm.c:57` 包含 `../../../../drivers/amlogic/hifi4dsp/hifi4dsp_firmware.h`。
  对应 include 无法在本快照解析；两棵固定树 `git ls-tree -r HEAD -- drivers/amlogic/hifi4dsp`
  均为空，缺少可审查的加载依赖。检查 C 全部 tracked 文件未发现 hifi/dsp/awe `.bin/.elf/.fw`。
- `vad.c:272–274,933–942` 仅在 `CONFIG_VAD_WAKEUP_ASR` 下调用
  `aml_asr_feed/enable/disable`；C 全树 git grep 只命中这三个调用，没有实现。
  本轮硬件 VAD 不依赖这些符号，也不声称能识别唤醒词。
- `mesont7c.dtsi:433–475` 的两个 DSP 节点及每核8MiB保留区，只证明资源预留，
  不证明远端程序、mailbox 消息合同和共享内存生命周期已交付。

继续 DSP 交付需要：可分发且与 T7 DSP 核匹配的固件及版本、入口/内存布局、加载与
停止流程、mailbox/RPC/共享内存协议，以及算法 SDK 或等效可构建源码与工具链。
取得这些输入后再接 remoteproc/rpmsg/ASoC；本轮不猜远端 ABI，也不假定 Android 私有
loader 可以直接移植为主线实现。

## 提交与验证

分支：[vim4-audio-routes](https://github.com/vim4-kvm/linux/tree/vim4-audio-routes)。
完整哈希、命令、退出码、配置与产物 SHA256 见[机器结果](audio-processing-results.json)，
附[检查输出](audio-processing-validation.log)。

| 提交 | 范围 |
|---|---|
| `41be1f202bdb1` / `62483506ca46c` | TDMOUT 绑定、GAIN_VER3、reset/cache |
| `f0c268a2e20a9` / `42c0a01e92c83` / `40b055d33e902` | CCF绑定、T7 clocks/pads、43 reset |
| `737aca498b9a3` / `cc507c62eec75` | TDMD 绑定、输入、TODDR18 |
| `cc67271633cd8` / `ce8bb28370676` | ASRC parents、CCF访问窗口 |
| `270c4efe5addb` / `5496b7c3eac6b` | ASRC绑定及组件 |
| `2b8cbdf5b2c63` / `ea4c6aa76d875` | loopback绑定及组件 |
| `7f778393d8b97` / `596188c3be116` | AED绑定及组件/路由 |
| `3c08ee991e715` / `f4d46cd3333c8` | VAD绑定及组件 |
| `8c775c9478446` / `a056f94380b62` | TDMIN_LB字段 |
| `65b631b619e32` / `a44dae7d097d3` | card转换属性与协商/触发 |
| `4e51f238962e7` / `52cd26e05be2f` | TDM失败回收、静音次序 |
| `5d6b68ef18bf5` / `df6b5e8266988` | SoC资源与处理路由夹具 |
| `e3eb8eb1e400e` | DAPM失败后幂等关断、窗口/时钟生命周期测试 |

离线检查包括逐提交 strict checkpatch，14 个实际 C fixture 脚本（ASan/UBSan）、
原 RX audio 测试、两个编译 DT 路由图、变更绑定及音频 DT 实例 schema。
机器结果共46项通过；主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`
运行231项，成功、跳过10项（跳过项不算通过）。
完整 `Image dtbs modules` 构建使用原 uhd1 配置经 olddefconfig，新增四组件均为模块；
保留 BTF，DWARF 仅改用 zlib 压缩以控制输出体积。最终构建与模块来自同一 HEAD；
完整原始构建输出保留 VM `~/build/kernel-audio-routes/final-full-build.log`。
2338个匹配模块齐全，12项产物哈希已登记；未执行启动、PCM、声学、功耗或性能测试。

后续按[批量上板清单](audio-board-checklist.md)统一窗口。除已列代码缺口外，板级
接线/端点配置、真实参数协商、ASRC漂移、音效响应、低功耗、RX/TX并发都需要各自证据。
