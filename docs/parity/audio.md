# ASoC 与全部厂商音频路由

厂商声卡 V1:595–778 的九个 dai-link 依次为 TDMB/i2s4hdmirx、SPDIFA、TDMA/PCM、
TDMC/i2s4parser、PDM、SPDIFB、EXTN/TV、loopback A、TDMD；控制器还启用 ASRC A/B、
effect、VAD。驱动/codec 模块加载不证明板上焊有对应功放或麦克风。
固定 [V/E 来源](sources.md)；本页 17 项，状态统计见 [主表](../vendor-parity.md)。
H/M 为风险；估计单位人日，音频共享时钟工作只计一次。

新增 [T7 离线基础系列](audio-routes-offline.md)及[处理组件续篇](audio-processing-offline.md)：
累计38个提交，含 TDMOUT/TDMD、loopback、ASRC、AED、VAD检测组件和标准 DPCM 参数配置。
本页正式统计仍为16项：0完全、5部分、11缺失；新增 A07/A11/A12/A13 四类组件/实例候选，
A14 仅有正常录音时的检测候选。没有上板，状态不因离线候选升级；
[批量上板清单](audio-board-checklist.md)逐项标出所需外设及无法验证的范围。

| ID / 厂商能力及来源 | 7.3 状态 | 差异与证据 | 路线、依赖 / 人日 / 风险 / 验证硬件 |
|---|---|---|---|
| A01 HDMI RX LPCM、采样率变化与失锁恢复；V1:604,1003 | 部分对齐 | E3:1260 AIF/ACR、独立ASoC RX/TODDR与Opus；七档采样率离线、48/44.1/32k现场证据。ENOLINK/EAGAIN 是必要保护；应用 ready→hw_params 有竞态。[动态音频](../bringup/2026-10-22-edge-hdmi-audio.md)、[ENOLINK对照](../bringup/2026-10-23-hdmirx-audio-enolink.md) | 主线ASoC，承接正在进行的音频/采集稳定性任务：generation资格确认、可取消重开、错误分类；保留无效时零硬件启动。R01、2–5 / H / 可切七档LPCM源、真实失锁和浏览器连续性探针 |
| A02 多声道/压缩音频、HBR、通道分配；V1:TDMB/extn，V2:HDMIRX/ARC | 缺失 | 当前产品只验双声道LPCM/Opus，不能把SPDIF或解析AIF当作IEC61937/HBR透传已通；E3未交付全部路由 | 主线ASoC/IEC958 controls、按厂商T7路径确定DMA/通道布局；A01/A03，8–15 / H / 多声道发生器、AVR/音频分析仪，授权codec由用户态合法解码 |
| A03 HDMI-TX 播放；V1:1848、audio TDM路由，V2:amhdmitx | 部分对齐 | E0:481/E1:1903有FRDDR→TDM→TOHDMITX，E7 bridge双声道；E2 audio-test:34删除通用sound，当前仅RX声卡。M0/M1亮屏不等于HDMI声音 | 主线ASoC＋DRM HDMI codec/ELD；承接显示M3，D02、共享时钟与RX并存；5–10 / H / 带声音sink或HDMI音频提取器、48/44.1k实测 |
| A04 TDMA PCM 全双工；V1:643,978 | 缺失 | E0普通DT描述不代表专用运行DT已接播放/录音；未验外部PCM引脚/BT音频 | 主线ASoC dai-link/DAI格式，复用AXG FIFO/TDM；先核对板图/BT路由、A03时钟层；3–6 / M / PCM loopback夹具、逻辑分析仪、BT音频对端 |
| A05 TDMB 外部I²S双向及HDMI输入选择；V1:604,1003 | 部分对齐 | E3接HDMI输入，但未实现厂商TDMB所有外部pin/源切换和全双工；不重建厂商私有mixer ABI | 主线ASoC DAPM/mux、显式pin与RX源选择；A01/A03，4–8 / H / 外部I²S codec/loopback、逻辑分析仪 |
| A06 TDMC parser/I²S路由；V1:677,1051 | 缺失 | E2运行时无该DAI完整接入，厂商dummy codec不证明物理模拟输出存在 | 主线ASoC；先证明parser实际消费者与输出布线，A03基础层；3–6 / M / I²S codec/内存回环、板图 |
| A07 TDMD（新板额外一路）；V1:747,1070 | 缺失 | 新增离线 CCF/reset42、D输入/输出及gain bank、TODDR18、disabled DT与全双工图夹具；未接真实板级引脚/codec | 主线AXG框架候选已交付；待板型/后端与物理参数验证，2–4 / M / kvim4n与外部TDM/I²S夹具 |
| A08 SPDIF A 收发、B 输出；V1:632,719,1124,1149 | 部分对齐 | 厂商没有独立B输入；新离线系列修正T7输出mask、500MHz输入/filter、FIFO与schema，数字路由夹具已验证，实际声卡/pinmux与失锁策略仍欠账 | 主线ASoC SPDIF DAI＋DAPM/IEC958 controls；A03、pinmux/源选择；5–10 / M / SPDIF发生器/接收器、光/电接口板和逻辑分析仪 |
| A09 PDM 麦克风；V1:708,1095 | 缺失 | 新增T7→AXG绑定/DT和数字路由编译夹具；无确认接线的录音端点。主线正常采集复用不含厂商全部低功耗模式；builtinmic不证明实物 | 主线ASoC标准PCM捕获；时钟/采样率、DMA、引脚；5–10 / M / PDM麦克风扩展板、声学源 |
| A10 EXTN/TV 输入路由；V1:732,1163 | 缺失 | E2无相应extn route；厂商TV路径不等价于当前HDMI RX TODDR专用链 | 主线ASoC DAPM/DAI；先列TV实际源、时钟与A01共享资源，4–8 / M / 对应数字源、音频回环 |
| A11 Loopback A/B；V1:735,1274,1330 | 缺失 | 新写 component/DAI/DAPM、输入与参考mux、双channel-sync和通道控件；PDM4＋参考2的编译图及故障清理通过。厂商A启用/B禁用；未有硬件证据 | 主线ASoC候选；待实际通道/相位/FIFO同步，2–4 / M / PDM及数字回环图案。B仅作选装候选 |
| A12 硬件ASRC A/B；V1:1199,1225 | 缺失 | 新写组件、系数SRAM/AA/auto-adjust/watchdog、标准控件及排他时钟回收；B固定source6→16k。输入变率须停流更新；SRAM供电、漂移与专用RX共享尚未验证 | 主线ASoC候选；A01/A03、双时钟与长期水位测试，4–8 / H / 两个独立采样时钟源、长时录音比较 |
| A13 AED/EQ/DRC等音效；V1:1174 | 缺失 | 新写48k双声道TDMOUT B首lane组件，FRDDR tap/DAPM、双RAM EQ/DC/全频及三段DRC、标准音量/TLV系数控件；离线校验通过。其他目的端、实时调参/噪声检测未交付 | 主线ASoC候选；响应/动态范围及扩展路由仍待实现或验证，4–8 / M / 音频分析仪、已知测试音 |
| A14 VAD 与低功耗录音唤醒；V1:1238 | 缺失 | 新写16k PDM正常录音检测组件、FIR/LUT、IRQ累计事件/wake hook。低功耗PDM保留、SRAM/DDR交接及系统PM未实现；关键词ASR符号只见调用无实现 | 主线ASoC＋PM/wakeup仍有代码欠账；A09、P06/P08，8–15 / H / PDM麦克风、在场RESET、电流/唤醒测试；当前禁挂起 |
| A15 HiFi DSP0/1、mailbox/音频固件；V2:433,456（旧板V2o:502,529） | 缺失 | [固定源码证据](audio-processing-offline.md#dsp-与关键词识别的不可交付证据)：host私有LOAD/START接口依赖缺失loader头文件，无匹配固件/算法实现和远端协议；当前无法交付DSP功能 | 取得可分发固件、SDK/工具链及内存/mailbox合同后接remoteproc/rpmsg/ASoC；15–30起 / H / 匹配固件与回环硬件 |
| A16 eARC TX/RX | 缺失 | V1:1386和V0:1346均disabled，非当前板厂商启用能力；E无本板可用链。ARC寄存器节点不是eARC验收 | 选装路线：主线ASoC/CEC/HDMI接口，先核对板上连线与厂商支持；D05/A03，10–20 / H / eARC电视/AVR、协议分析仪；不列当前必须追平的前置任务 |
| A17 板载ACODEC/外接功放codec | 部分对齐 | V2 acodec节点与多个codec模块存在，但V1九路多连dummy，不能声称所有codec实际装板。E无厂商等效模拟播放验收 | 主线ASoC标准codec驱动/DT；先确认实际焊接和接口，再A03/TDMB；5–10 / M / 板图、对应codec扩展板/耳机或功放、模拟音频分析 |

音频完成门槛是已知波形/通道/采样率、开关源、失锁重开、RX/TX并行与长期连续性。
ALSA声卡列出、启动服务active、浏览器拿到全零音频均不足以通过。
ENOLINK 不属于应删除的绕过：临时不足在消费者恢复；正式实现必须保留无链路拒绝语义。
