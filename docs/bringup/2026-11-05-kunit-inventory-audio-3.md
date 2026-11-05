# 2026-11-05：内核测试清单 audio（3）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `sound/soc/meson/test_t7_tdmout.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Compile real formatter code; check window isolation and reset recovery.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 83 | `C main` | V/B：扩展 MMIO window、四 lane mute/masks、reset/regcache sync 失败、clock 归还、重复 enable 和通道分布；标准 ALSA 与注入 |

## `sound/soc/meson/test_t7_toddr.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：T7 register ABI: source selection, PCM alignment and channel synchronization.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 76 | `C main` | V/B/F：source selector 隔离、S16 裁剪、各 PCM 物理/逻辑宽度组合、channel sync 启停和读写失败不改半状态；ALSA capture 样本与注入 |

## `sound/soc/meson/test_t7_vad.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute detector setup and verify cleanup at every register failure.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 43 | `C main` | V/B：FIR/LUT、PDM feed、reset 次序、每个 regmap 失败 cleanup；标准 ALSA detector 控制、实际 PDM 与注入 |
