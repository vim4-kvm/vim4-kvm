# 2026-11-05：解码 `.27` / `.28` 启动前六秒离线差异

结论：两个候选的 vdec 源码、T7 公共 DTS、电源域与时钟运行时代码相同；
生产配置相同。可见的启动路径差异来自集成基线，尤其 MMC 完成中断、ADLA
分段和风扇控制。日志没有证明这些变化导致冷复位，也没有证明解码器已在复位前
取得硬件资源。本轮只读已有源码、包清单和 UART，没有排板、改公共驱动或部署。

## 身份与统计边界

| 项 | `.27` | `.28` |
|---|---|---|
| 源码 | `02a3b188757e5ece5a0670681bab43d662d9d271` | `960132382e00864f4944aee077cd621927a97bb0` |
| GNU build ID | `4cb47d45df4f5852d76502231f533958837a71db` | `81bb2f999ffffb38d549afbf8b15fb3048184c0f` |
| 已覆盖 Linux 启动 / 非请求冷复位 | 3 / 0 | 8 / 2 |
| 原始清单 | `build/hwdecode-parity/run48/package-manifest.json` | `build/hwdecode-parity/run54/package-manifest.json` |

配置 SHA-256 均为 `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`，
模块总数均为 2341（基础 2338、外部 3）。生产配置没有 KUnit、PROVE_LOCKING、
PREEMPT_RT；vdec 为模块。相同数量不能证明模块二进制或装载次序相同。

截至 [H.264 收口](2026-11-05-vdec-avc-final.md)，正式 `fd41fb5` 包覆盖至少 13 次
启动、零复位。样本少、不是随机对照，正式包分母还是下界，不能据此归因或宣布
统计显著。历史 `.3` 也有复位；跨内核口径见 [r53](2026-11-05-vdec-r53-coldboot.md)。
`.28` 两次失败为 r51/r53，末条内核时间分别 5.540308 / 5.331471 秒，随后直接
BL1/cold_boot，没有 panic。它们是时间下界，不是精确复位时刻。

## 源码、配置与启动路径

比较命令为 `git diff 02a3b18 9601323 -- <路径>`，原始输出保存于
`build/hwdecode-parity/v2/boot-source-diff.log`、`boot-adla-fan.diff`、
`boot-locking.diff`。旧解码系列 rebase 的 range-diff 另存于
`build/hwdecode-parity/rebase-integration/range-diff.log`。

| 路径或机制 | 已核实变化 | 对前六秒的意义与未证部分 |
|---|---|---|
| `drivers/media/platform/amlogic/vdec/` | 两个源码树完全相同 | 不能把重基后的提交 SHA 变化当成解码代码变化 |
| `t7-dos.c`、`drivers/clk/meson/`、`drivers/pmdomain/amlogic/` | 运行时代码相同；后者仅删除 Python 测试 | 没有新的 vdec 时钟/电源操作差异；仍缺逐次调用跟踪 |
| `amlogic-t7.dtsi` | 相同，含 HEVC clocks/domain/IRQ 描述 | 解码器资源描述不是两包之间的变量 |
| VIM4 板级 DTS | 风扇 cooling states、thermal trips/maps 扩充 | 风扇从私有轮询改为标准 thermal 管理；板级 DT 并非完全相同 |
| `meson-gx-mmc.c` | SDIO IRQ 锁改 raw；完成路径统一唤醒线程执行 DMA sync/unmap 与 request_done | 生产配置也改变完成时序，不能仅因修复源自 lockdep 就视为无运行时影响 |
| ADLA `adlak_mm_os_common.c` | SG 建表按设备最大 segment 大小拆分 | 初始化/分配的 DMA 路径有实际变化；不能从 probe 日志推断每次分配都执行了该函数 |
| ADLA mutex 初始化 | mutex_init 移到调用点，类 key 分离 | 无 lockdep 时主要是包装变化；并非新的加锁策略，未做二进制等价证明 |
| `khadas_mcu_fan.c` | 删除 quiet_work 私有轮询，采用 DT thermal cooling，并修 cooling-device devres 归属 | `.27` 约 0.37 秒首次缺传感器时请求 15%；`.28` 不再打印该私有路径日志，不能据日志缺失认定风扇未工作 |
| brcmfmac | 有界 NVRAM 注释解析修复，另有 KUnit 可见性重构 | Wi-Fi 在六秒内完成固件初始化，属于活跃路径；缺边界输入触发证据，不能因此归因 |
| PWM | 每控制器 lockdep key 与 KUnit 可见性重构 | 生产无 PROVE_LOCKING，锁类修复不能直接解释冷复位；未改此驱动 |

`aml_vdec_drv_probe()` 在 `enable_t7=false` 时直接返回 `-ENODEV`，先于
`meson_t7_dos_get()` 和 `req_hw_resource()`。参数默认 false。
`vdec-window.py:prepare_acceptance_decoder()` 才显式加载 `enable_t7=1`，随后
执行无电 probe 和 MDEC/HEVC 实验。r51/r53 没达到 candidate ready，因此没有
进入这条 acceptance 路径。`.27` 的 HEVC 私有模块也是在该阶段加载，不是 Image
内建代码；`.28` 没有私有草稿。

这证明的是**测试流程未提前启用解码器**，不等于证明启动时无人通过 modprobe
配置覆盖参数。UART 没有完整 module_load 或 probe trace；没有解码日志也不能
证明模块未装载。下次实验须同时保存实际参数、modules-load/modprobe 配置、
模块事件，才能闭合这一点。

## UART 中可观察的次序

一次性提取脚本和逐行来源在 `build/hwdecode-parity/v2/boot-evidence.py`、
`boot-events.json`、`boot-events-summary.log`，输入为各 r48–r58 的原始 UART。
下表是 Linux 单调时间，非主机时间；只列相同可观测里程碑，不把并行日志排序
当成完整的 probe 因果顺序。

| 窗口 | eMMC 发现 | SDIO 发现 | ADLA 版本 | Wi-Fi 固件完成 |
|---|---:|---:|---:|---:|
| r48 `.27` | 1.535 | 2.115 | 4.330 | 5.205 |
| r49 `.27` | 1.630 | 2.204 | 4.324 | 5.442 |
| r50 `.27` | 1.635 | 2.212 | 4.389 | 5.438 |
| r51 `.28`，复位 | 1.646 | 2.251 | 4.520 | 5.429 |
| r53 `.28`，复位 | 1.647 | 2.216 | 4.402 | 5.222 |
| r54 `.28`，正常 | 1.643 | 2.244 | 4.411 | 5.411 |
| r56 `.28`，正常 | 1.620 | 2.235 | 4.425 | 5.302 |
| r57 `.28`，正常 | 1.635 | 2.220 | 4.342 | 5.259 |
| r58 `.28`，正常 | 1.644 | 2.227 | 4.513 | 5.247 |

两次复位和成功启动的这些时序相互交叠；没有可见的异常 probe 重排。
NetworkManager/hostnamed、TEE、cpufreq 启动和复位相邻只提供定位区间，
不能证明服务导致复位。命令行的 blacklist、CMA、panic 等测试设置相同，
RAM init 路径按包身份不同。r51 使用旧恢复包、r53 使用新正式恢复包仍复位，
所以“仅恢复目标变更”无法单独解释两次失败。

## 提议的区分实验（未执行，需另行安排）

1. 先固定实验封装：为正式 `fd41fb5` 和 `.28` 生成相同 RAM 启动流程，使用
   同一正式 rootfs、Wi-Fi 固件、命令行和服务设置，只改变核对过的内核包。
   交替顺序而不是先跑完一种；每次 Linux 启动计数，自动恢复单列，保留连续
   主机时戳 UART。继续禁止隐式加载私有 HEVC 草稿。此步骤区分“测试封装/时序”
   与“内核包”的影响；零复位只能提供有限样本上界，不能宣布根治。
2. 采证先于干预：在可启动的配置收集实际模块参数与服务/modprobe 配置；若需
   早期 module/probe、clock/genpd trace，先确认现有配置事件是否可用，避免
   把新增调试配置与原生产包混成同一统计。当前记录没有这些事件，不能补写为已验。
3. 仅当证实 vdec 在六秒内被启用，才提议同一 `.28` 下单变量禁止自动装载
   vdec 的对照；不修改驱动电源逻辑。若默认门禁已经使 probe 提前退出，
   不重复用这个无效变量消耗板窗。
4. 若 RAM 封装相同而 `.28` 仍独有失败，比较 `.27` / `.28` 的基线行为。
   MMC/ADLA/fan 的单项回退或 DTS 组合必须由相应维护 worker 单独准备、验证，
   避免旧驱动与新 DT 不配套。先选有早期执行证据的变量，一次只换一个，
   不以关锁检查或关 DMA 检查作为修复。本任务不改这些目录。
5. 任一 BUG/WARN、挂死或恢复失败即收尾，按当时正式 baseline proof 恢复并
   验视频。若再次只有 BL1 cold_boot、无内核记录，则转向 RESET/VBUS/PD
   的闭环采样方案；现有 UART 不能区分掉电、外部 reset 与固件 reset。

本方案没有安排实际次数或预授权板窗；统计停止条件和窗口预算由协调者在实验
前明确。现阶段允许评审解码系列，不据此批准生产部署。
