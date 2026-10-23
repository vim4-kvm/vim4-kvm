# T7 音频全路由离线审计与基础驱动系列

本页固定前轮 `e934ed1e3b87f` 的历史交付范围；后续 TDMD/处理组件、完整构建与当前
剩余项见[第二轮离线记录](audio-processing-offline.md)。下文“未实现/未运行”均指该前轮。

本轮仅操作开发机和 `vim4-build`，没有访问、占用或部署板子。
**交付的是基础驱动候选，不是全路由追平完成**：ASRC、VAD、AED、DSP、TDMD 等仍有
代码实现欠账，不能将它们统称为“只待上板”。[能力表](audio.md)的 16 项统计仍为
0 完全、5 部分、11 缺失；eARC 是另外一项选装范围。
批量硬件验收及外设见[上板清单](audio-board-checklist.md)。

## 固定版本与交付

厂商依据沿用[来源表](sources.md)：Linux `80a07ad5406d`、common_drivers
`4cfb128d36f8`。本次重新核对该版本 `kvim4n.dts` 595–778、977–1386，
以及 `sound/soc/amlogic/auge/{tdm_hw,ddr_mngr,spdif_hw,resample_hw,pdm_hw}.c`、
`audio_top.h`、`regs.h`、`clks/`。没有修改厂商树。

候选分支：[vim4-audio-routes](https://github.com/vim4-kvm/linux/tree/vim4-audio-routes)，
起点为已 fetch 的正式远端 `cb3b9f1a69051`，末端 `e934ed1e3b87f`。
独立工作树在 VM `~/src/linux-7.3-audio-routes`；原 `~/src/linux-7.3` 不切分支。
系列没有合入正式分支。显示任务继续拥有 `VIM4HDMITX`、hdmi-codec/ELD、TX bridge；
本系列不另建 HDMI TX 声卡。RX 接收器驱动、声卡名称、路由与 source 8 打包路径保留。

| 顺序 / 提交 | 可独立审查的变化 |
|---|---|
| 1 `b464012fda59b` | SPDIFOUT T7 独立 compatible，要求 reset，不伪装 AXG 寄存器兼容 |
| 2 `d13d95df45e88` | SPDIFOUT 按 match data 使用 T7 未移位通道掩码；实际 C 函数测试 |
| 3 `c63ebb8f7bfeb` | TDMIN T7 compatible/reset 绑定 |
| 4 `128b177556793` | TDMIN 显式时隙数量；保留 AXG 行为，测试格式、通道分布和 mux 位 |
| 5 `b17148b5bbd1c` | 非 RX TODDR 的 T7 PCM/IEC958 打包，AXG card 识别 T7 capture FE |
| 6 `edae286b17e4f` | PDM 的 T7→AXG fallback 和 SPDIFIN T7/reset 绑定 |
| 7 `8ee06152c54ca` | SPDIFIN 500 MHz 参考时钟与 sample-mode filter；时钟失败回收测试 |
| 8 `3534175e80afa` | FRDDR T7 compatible/reset 绑定 |
| 9 `8e2b521ac99ed` | FRDDR 通道数与 urgent 位，保留 sink 路由；识别 T7 playback FE |
| 10 `93e4fe510cf2a` | SoC DTSI 选择对应变体，为四个 TODDR 各自描述 channel-sync 资源 |
| 11 `99142051a2ad7` | 编译专用 SPDIF/PDM DT 夹具，验证 DAPM、资源与原 RX 配置 |
| 12 `e934ed1e3b87f` | T7 捕获不再广告不支持的 S20_LE；逐一验证声明的格式与实际 hw_params 一致，拒绝时不改寄存器 |

## 九个厂商 DAI 与主线组件的对应

这些是逻辑 dai-link，不是九个物理插座；厂商多数 codec 是 dummy。
`suffix-name` 是 Android HAL 命名，也不能代替实际 mux 配置。

| 厂商 link / CPU | 厂商配置 | 主线组合与缺口 |
|---|---|---|
| 0 TDMB | I²S，2×32，TX/RX 各两槽，`i2s-i2s4hdmirx` | `axg-tdm-interface` B + TDMOUT/TDMIN B + FIFO；节点实际 `tdmin-src-name=tdmin_b`，名称不证明默认取 RX。现有独立 RX 不经此 TDM link |
| 1 SPDIFA | MCLK×128，6.144 MHz 示例 | `axg-spdifout` A + `axg-spdifin` + FRDDR/TODDR；输入输出分别接后端 |
| 2 TDMA | DSP_A，2×16，单槽，MCLK×64 | `axg-tdm-interface` A + 双向 formatter；板级 TX lane 1、RX lane 0，不能照搬声卡掩码而丢掉 lane 选择；与 TX 的 TDM_A 分配需协调 |
| 3 TDMC | I²S，2×32，`i2s4parser` | C 接口 + formatter；厂商 `tdmin-src-name=hdmirx`、`i2s2hdmi=1`，不是独立 parser codec |
| 4 PDM | `pdm-builtinmic` | `axg-pdm` → TODDR source 4；标准 `dmic-codec` 只用于真实接入的数字麦克风 |
| 5 SPDIFB | MCLK×128 | SPDIFOUT B；厂商没有独立 SPDIFIN B，不能列成另一条双向输入 |
| 6 EXTN | `tv` | 应按 FRHDMIRX/其他真实源拆分 ASoC 组件；现有 RX 只覆盖其一个子集 |
| 7 loopback A | MCLK×256，continuous-clock | 厂商 A 混合 PDM 四声道与 TDMOUT B 两声道；需要专用硬件 loopback 组件，TDMIN_LB 或软件 snd-aloop 不等价 |
| 8 TDMD | I²S，2×32，`tdm-d` | 新板额外实例；需先扩展时钟/reset、formatter 资源和 TODDR source 18，当前未实现 |

## 可复用范围与寄存器差异

以下是本系列实现边界，不是所有 T7 寄存器均与主线相同的声明。

| 组件 | 本轮处理 | 后续仍需实现/证明 |
|---|---|---|
| FRDDR | 复用 SM1 的 CTRL2 sink 路由；T7 在 CTRL2[31:24] 写 channels−1，在 CTRL0[0] 写 urgent，错误逐层返回 | DMA drain/burst-finished、reset 生命周期和真实多 sink 并发；当前测试不覆盖这些硬件性质 |
| TODDR | T7 source 位于 CTRL1[30:26]，原驱动已有正确五位 mux；增加非 RX 的 type 0 PCM/type 4 S24；SPDIF raw 为 type 3、MSB27/LSB4；排除不支持的 S20_LE 能力位 | 当前只暴露前 16 个源；TDMD=18、PDM_B、ASRC_C 等不因字段五位就自动可用 |
| TODDR channel-sync | A/B/C/D 分别使用音频基址相对偏移 `0xc3c/0xc7c/0xcbc/0xcfc`，独立 4 字节资源 | 与真实 FIFO 启停、通道同步的联合验收 |
| RX source 8 | 保持 S16、MSB27/LSB12/type 0 和现有 CHSYNC 行为；不改动态链路资格检查 | A01 的失锁/变率恢复仍由已有稳定性任务验收 |
| TDMIN | CTRL[12:8] 写 slots−1，保留原来的 source/复位位和四 lane 的 AXG 组织 | 当时尚缺 TDMIN_D、额外时钟选择；更正：T7 match table 为 LANE_MAX1=4，通用寄存器头不能证明八 lane |
| TDMOUT | 尚保留原 SM1 节点，不新增假兼容 | T7 是 GAIN_VER3：gain enable 在独立扩展 bank，不能把 SM1 CTRL1[7] 当 T7 全通道 gain；需处理增益与 MMIO 所有权，T7 为四 lane |
| SPDIFOUT | T7 通道掩码是 CTRL0[15:0]，AXG 是 [11:4]；按变体分别清旧通道位 | IEC958 通道状态、独立引脚与 TX 同时输出、真实采样率测量 |
| SPDIFIN | T7 refclk=500 MHz；配置 CTRL6[12] filter，复用七档检测窗口 | 主线驱动原有检测抖动/无信号→32k 通知限制仍存在；本系列没有完成 loss-of-lock/XRUN 协议 |
| PDM | 正常采集寄存器与主线 AXG filter 路径可复用，添加 T7 compatible + AXG fallback | 主线范围 S24/S32、最高 48k、最多八声道；未支持厂商所有低功耗/training/VAD 模式 |
| 音频 CCF | 原 T7→S4 fallback 不变 | 第二个 MCLK pad aperture、TDMD 时钟、reset 与所有父时钟精度仍需专项实现 |

TDMD 不能只加一个节点：其 TDMIN_D/TDMOUT_D 时钟寄存器在 `0xe8/0xec`，
当前 audio-clkc 主 aperture 到 `0xd8`；SM1 reset provider 只有 39 项，
TDMD 对应 reset1 bit10（逻辑 42）尚不可用。需先补 CCF/绑定/reset，再加 DAI、
扩展 bank 资源与 source 18，最后接真实板级 codec；不能借用相邻实例 MMIO。

## 每项能力状态与实施顺序

“候选”表示本轮有离线代码交付；其余明确区分实现欠账与硬件验收。

| ID | 当前交付及剩余工作 |
|---|---|
| A01 部分 | 保留现有 RX；DT 合同对比、原 RX audio fixture 和 TODDR RX 回归通过；本轮没有新增现场或动态恢复证据 |
| A02 缺失 | 多声道/HBR/IEC61937、通道分配与 RX PAO 打包仍待实现；SPDIF raw 容器支持不代表它们完成 |
| A03 部分 | 由显示任务交付 VIM4HDMITX/hdmi-codec/ELD；本系列只提供共享基础驱动修正与明确资源分配 |
| A04 缺失 | TDMIN/FIFO 候选可复用；完整双向 link、TDMOUT T7、PCM 引脚/BT 接线仍欠实现与验收 |
| A05 部分 | 外部 I²S 同样缺板级后端；现有 RX 只覆盖厂商源的一部分 |
| A06 缺失 | TDM_C 基础捕获修正可用作后续依赖；parser/HDMI 选择、实际消费者与完整 card 仍欠实现 |
| A07 缺失 | TDMD 的 CCF/reset/formatter/source 18 依赖如上，未实现 |
| A08 部分 | 新 SPDIF A 收发/B 输出变体、DT 与数字路由夹具；实际声卡/pinmux、锁定协议和端到端验收仍欠账 |
| A09 缺失 | 已有主线 AXG PDM 的 T7 绑定/DT 与数字路由夹具；尚无确认接线的可交付录音端点，低功耗模式也未实现 |
| A10 缺失 | 先按实际 EXTN 源建模，避免把厂商 TV 私有 DAI 原样搬入；除 RX 子集外仍欠组件与路由 |
| A11 缺失 | 硬件 loopback A 的源/通道混合与 FIFO 同步尚未实现；B 在厂商配置禁用，不作为当前必须启用的第二实例 |
| A12 缺失 | ASRC A 取 source 8；B 在驱动中固定取 TDMIN_LB=6，板级输出 16k 供 loopback A。需新组件处理双采样时钟、系数、供电/错误回收、DPCM 协商，未写裸寄存器开关冒充 ASRC |
| A13 缺失 | AED effect v4 接 TDMOUT B，module=1、lane mask=1、channel mask=ff；系数格式、范围与原子更新、reset/旁路仍欠主线风格组件 |
| A14 缺失 | VAD source 4/PDM、level=1 内核算法、IRQ39/44。需先 A09、SRAM/低功耗时钟和 wake 生命周期；本轮不新增或解除整机挂起保护 |
| A15 缺失 | DSP0/1 保留内存不等于可运行远端核；需确认合法固件、启动/停机、mailbox 消息、内存所有权协议，再实现 remoteproc/rpmsg/ASoC 接口 |
| A16 选装缺失 | 厂商禁用 eARC；本轮不启用，独立作为选装路线 |
| A17 部分 | 未找到可确认装配的板图/codec 接线；不把 dummy 或模块名写成耳机、喇叭实物。确认后再接标准 codec/DAPM widgets、供电和 UCM |

依赖顺序：本系列的 FIFO/formatter/SPDIF/PDM → T7 TDMOUT、CCF/reset/TDMD、
真实板级后端 → loopback/EXTN → ASRC/AED → VAD/PM 与 DSP 固件协议。
ASRC/AED 等还有离线编码工作；外设清单不是这些代码欠账的替代。

## 路由、声卡和 UCM 边界

`sound/soc/meson/test-data/t7-audio-routes.dts` 仅为编译夹具，没有列入板级 DTB Makefile，
没有 pinmux/电气接口，**不得当作可部署 DTS**。它保留原 `VIM4HDMIRX`，另用 AXG card
定义四个 FE、四个 BE：FRDDR B/C→SPDIFOUT A/B、PDM→TODDR B、SPDIFIN→TODDR C。
后端使用标准 spdif-dit/spdif-dir/dmic-codec，表达外部数字端点，不声称板载器件存在。
它保留 TODDR_A 给 RX、FRDDR_A/TDM_A 给显示任务；双卡不能共享 CPU DAI。

图测试读取**实际 C 驱动的 DAPM route 数组**与编译 DTB：端点必须存在，两个播放 FE
各能到两个 SPDIF 后端，两条捕获各到对应 FIFO，不能交叉误接；同时检查 CPU DAI
独占、音频 MMIO 不重叠、原 RX 子树在解析 phandle 后不变。
这不验证实际 mux 选择、电气连通、DPCM 并行参数或声卡 probe 成功。

本轮不添加将假设器件暴露成用户端点的 UCM。真实 card/端口确认后，UCM 按
`hw:CARD=<稳定ID>,DEV=<已验PCM>` 选设备；不要固定数字 card index，也不要在 UCM
中隐式改 RX mux 或抢占显示 DAI。DPCM 的控制选择、双向启停与并发必须上板验收。

## 离线验证与复现

[机器结果](audio-routes-results.json)固定 HEAD、配置 SHA256、每项退出码与日志哈希，
附[验证输出](audio-routes-validation.log)。原始日志在 VM `~/build/kernel-audio-routes/`，
不作为部署包。环境 GCC 13.3.0、
dtc 1.7.0、dtschema 2026.9；配置取主仓 `packaging/kernel-edge/uhd1.config` 后 olddefconfig。

通过：12 个提交逐个 strict checkpatch，合计 0 error/0 warning/0 check；五个寄存器 C
fixture（ASan/UBSan）及原 RX audio fixture；编译 DT 路由/资源/RX 对比；
整个 `sound/soc/meson/` 对象构建；VIM4 基础/audio-test/display-m0/display-m2 四个 DTB；
五份变更 YAML 的 `dt_binding_check`；夹具及 audio-test 的选定音频 schema 实例验证无输出。

**未运行完整 Image/modules 链接、启动、运行时 PCM、性能和硬件回归**。
本次是相关目录对象构建与 DT 校验，不是完整内核包构建成功声明。
仍需预留完整输出空间、完成 Image/dtbs/modules 和匹配模块打包后才可进入一次性上板门禁；
检查时 VM 可用约 6.9 GiB、宿主约 7.6 GiB，没有删除其他任务产物腾空间。

```sh
cd ~/src/linux-7.3-audio-routes
OUT=$HOME/build/kernel-audio-routes
git format-patch -1 HEAD --stdout | scripts/checkpatch.pl --strict --no-tree -
# 对系列中每个提交分别执行上面的检查。
python3 sound/soc/meson/test_t7_spdifout.py
python3 sound/soc/meson/test_t7_tdmin.py
python3 sound/soc/meson/test_t7_toddr.py
python3 sound/soc/meson/test_t7_spdifin.py
python3 sound/soc/meson/test_t7_frddr.py
python3 drivers/media/platform/amlogic/t7-hdmirx/test_audio.py

# 在独立目录解出基线 DTS；不切回原工作树。
mkdir -p "$OUT/baseline"
git archive cb3b9f1a69051 arch/arm64/boot/dts/amlogic |
  tar -x -C "$OUT/baseline"
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
  -I scripts/dtc/include-prefixes \
  "$OUT/baseline/arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-audio-test.dts" |
  dtc -q -I dts -O dtb -o "$OUT/baseline.dtb"
python3 sound/soc/meson/test_t7_audio_routes.py \
  --baseline "$OUT/baseline.dtb" --output "$OUT/routes-fixture.dtb"

flock /tmp/vim4-heavy.lock make O="$OUT" ARCH=arm64 -j4 sound/soc/meson/
PATH=$HOME/build/dt-schema-venv/bin:$PATH flock /tmp/vim4-heavy.lock \
  make O="$OUT" ARCH=arm64 \
  DT_SCHEMA_FILES=sound/amlogic,axg-fifo.yaml:sound/amlogic,axg-pdm.yaml:sound/amlogic,axg-spdifin.yaml:sound/amlogic,axg-spdifout.yaml:sound/amlogic,axg-tdm-formatters.yaml \
  dt_binding_check
"$HOME/build/dt-schema-venv/bin/dt-validate" \
  -s "$OUT/Documentation/devicetree/bindings/processed-schema.json" \
  -l sound/amlogic,axg:sound/dmic:sound/linux,spdif "$OUT/routes-fixture.dtb"
```

dt-validate 即使有诊断也可能返回 0，必须同时检查输出；本轮选定实例验证输出为空。
该过滤器只覆盖所列音频 schema，不代表整个板级 DT 的所有既有问题已经清零。

主仓提交前离线全套 `python3 -m unittest discover -s tests -p 'test_*.py'`：
运行 226 项，220 通过、6 跳过、0 失败。跳过项不计通过。
