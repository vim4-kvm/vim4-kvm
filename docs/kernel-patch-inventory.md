# 7.3 补丁清单与主线跟进

本次只在开发机和 OrbStack VM 离线审计、编译，不访问板子、不安装产物。
审计固定用户指定的 `0a775305f0ad81475f65d33b15f79099c8445c75`；正式工作树当时在
`0196fe22ecf01`，它是固定版本的祖先。两个正式引用均未由本任务更新。
新增整理位于 `maintenance/upstream-20261023`，前移试验位于 `maintenance/next-20261023`。
硬件能力与退出条件继续以[厂商能力对照](vendor-parity.md)为准。

后续独立音频候选 `vim4-audio-routes` 基于正式远端 `cb3b9f1a69051`，
38 个提交至 `e3eb8eb1e400e`，不混入下方固定审计的 580/291 计数。
[基础记录](parity/audio-routes-offline.md)与[处理续篇](parity/audio-processing-offline.md)
给出逐提交、寄存器差异、DT/schema、实际C测试与完整Image/DTB/modules构建证据。
未合入正式分支、未部署；低功耗VAD、DSP与真实板级端点仍有交付缺口。

## 计数口径与全部提交

`v7.3` 的 annotated tag 对象为 `091b06388b117`，解引用后的提交为
`c03c1a14507dfaf8b856c2608f9ac216021fc222`。不能把 tag 对象当提交计数。

| 范围 | 全部提交 | 普通提交 | 合并提交 |
|---|---:|---:|---:|
| `v7.3-rc7..0a775305` | 580 | 522 | 58 |
| 其中已在 `v7.3` 历史中 | 289 | 232 | 57 |
| `v7.3..0a775305`，实际下游 | 291 | 290 | 1 |

[逐提交清单](kernel-audit/commits.tsv)覆盖全部 580 条，包含完整哈希、主题、分类、
strict checkpatch 计数和私有/临时标记；[机器清单](../packaging/kernel-edge/series/inventory.json)
另含路径、补丁名和 SHA256。[汇总](kernel-audit/summary.json)固定比较端点。
不能把 580 都称为待上游下游补丁，也不能把已在上游的 T7 pinctrl/pwrc 基础支持再次投递。

290 个普通补丁按主要文件归档如下。一个提交可能涉及多个主题，交叉主题计数另存汇总，
因此下表使用单一归档主题以保持总数可加。

| 归档主题 | 补丁数 | 上游整理方向 |
|---|---:|---|
| DT | 53 | 区分 SoC 资源、板级接线与实验 profile；绑定先于节点 |
| dt-bindings | 26 | YAML 存在不等于资源归属和 ABI 已被上游接受 |
| clk | 16 | 功能门控可独立评审；critical/read-only 绕过需消费者接管和退出证明 |
| pinctrl | 0 | 本范围没有新增补丁；基础支持已进入 v7.3 |
| pwrc | 3 | 区分固件必需常开域与 DMA 生命周期未完成的临时常开域 |
| hdmirx/vdin | 58 | media graph、subdev/pipeline、标准控制、共享 VCBUS 归属 |
| wave5 | 20 | 通用队列/尺寸修复优先；固件差异、隔离与恢复另拆平台系列 |
| DRM/meson/Panfrost/bridge | 72 | 去 FROMLIST/fixup 标题，吸收已合入项；handoff 属实验，不作通用 KMS |
| ASoC | 7 | 保留标准 PCM/control 通知；RX 中的 ASoC 改动另有交叉计数 |
| IIO | 1 | `d0c36b0fab52f` sample-delay mask 修复可独立形成投递候选 |
| USB | 6 | HID/UAC2 通用生命周期修复与 CRG 私有控制器分开 |
| 网络 | 7 | BCM43752/WCC 能力发现与 P2P 流控分开评审 |
| thermal/MCU | 9 | 通用硬件变体与安静风扇策略分开，避免重复主线已有实现 |
| 其他媒体（JPEG/vdec） | 3 | JPEG 改 V4L2 M2M；vdec 安全/能力审查仍未完成 |
| 其他平台 | 9 | RTC、cpufreq、固件等逐项收敛 |
| **合计** | **290** | |

## 可投递性与严格检查

对每个普通下游提交运行 `scripts/checkpatch.pl --strict --no-tree`，累计 **345 error、
514 warning、375 check**。118 个提交没有这些诊断；其中 36 个仍命中整理/临时标记。
逐行结果在 TSV，可按提交定位，不能用净 diff 的较低计数取代历史补丁质量。

自动初筛为：82 个 `upstream-candidate`、175 个 `needs-cleanup`、33 个
`private-temporary`，另有 1 个 `merge-review`。标记覆盖新增 sysfs/私有 ioctl、module parameter、
debugfs 和实验/常开策略；FROMLIST/fixup 与只新增 debugfs 的项归入待整理，
不计为私有实现。它是可复现的筛选，**不是上游接收承诺**。
特别是没有新增私有接口的后续修复，仍可能依赖实验驱动，必须按上表主题复核。

可直接形成小系列候选：IIO mask 修复、标准 HID 请求取消、UAC2 单方向生命周期、
Wave5 导入 buffer 边界/IDR/标准控制修复。投递前仍要核对最新主线、作者和签名、
对应维护者及行为证据；不把整组 82 条直接称为“已可上游”。
DRM 邮件系列、SoC binding/clock/DT 支持需重排和去重；RX/VDIN、固定显示 handoff、
JPEG misc ABI、CRG 调试、TEE 完成握手与风扇策略属于需架构整改的下游部分。

## binding、Kconfig 与维护范围

[compatible 扫描](kernel-audit/bindings.json)对所有改动 C 文件的 OF match 项查 YAML 文本匹配，
共 298 条；这是覆盖线索，不是 schema 语义校验。9 条无匹配中，6 条来自既有通用驱动
的旧兼容项（cpufreq 四条、MMC 两条），本次新增且缺失的只有 JPEG、CRG、TEE control。

| 驱动/主题 | schema 情况 | 本次行动或剩余问题 |
|---|---|---|
| T7 clock/CPU clock、pinctrl、pwrc | 已有对应 YAML | clk 的 firmware read-only/critical 策略需单独评审 |
| RX/VDIN | `amlogic,t7-hdmirx.yaml`、`amlogic,t7-vdin-test.yaml` | 增加专门 MAINTAINERS；实验节点与共享 aperture 尚需正式设计 |
| Wave5 | `cnm,wave521c.yaml` 含 T7 | clocks/reset/domain 所有权仍受安全固件约束 |
| DRM/TX/handoff | meson-vpu、meson-t7-hdmi-tx、t7-display-handoff | 固定固件时序不是通用输出 binding 的最终方案 |
| ASoC | axg-fifo、g12a-tohdmitx/toacodec，RX 音频在 RX schema | PCM 生命周期测试已整合 |
| IIO SARADC、thermal/MCU | 已有通用 schema | 风扇私有策略接口仍需迁移 |
| JPEG | **新增** `amlogic,t7-jpeg-encoder.yaml` | 描述现有寄存器、IRQ、3 clocks、power-domain，增加维护条目 |
| CRG | **新增** `amlogic,t7-crg-udc.yaml` | 同时修正 Meson USB parent 的子节点引用，增加维护条目 |
| TEE control | **仍缺** `amlogic,t7-tee-control` | 私有 `/sys/class/tee_info/sys_boot_complete` 和独立无资源节点应先重构；不为握手 hack 固化新上游 ABI |

新 schema、实例以及修改的 parent schema 已通过 `dt_binding_check`；统一验证还运行本范围
所有变更 YAML 的检查和 8 个直接变更 DTS 的 `CHECK_DTBS=y` 检查。未命中 schema 的节点
不会因此自动通过，TEE 缺口需单独保留。完整构建中的 `dtbs` 本身不等于 `dtbs_check`。

Kconfig 审查确认 RX 依赖 PM/DEBUG_FS/SND_SOC，VDIN 依赖 VIDEO_DEV/OF/HAS_DMA 并选择
vb2 DMA-contig；Wave5 使用既有 V4L2 M2M 入口；CRG 限 ARCH_MESON/OF/glue/EXPERT；
TEE 限 ARM64/OPTEE/ARCH_MESON。JPEG 仍是 DMA-buf misc 驱动，不能仅改帮助文字称其 V4L2。
RX/VDIN 的旧 1080p/copy-only 帮助已更新为当前实际行为。`COMPILE_TEST` 的跨架构覆盖、
去掉生产路径的 DEBUG_FS 依赖，以及 ARM64 固件调用的可移植性仍需专项验证。

## 私有接口整改清单

以下均保留现有消费者；更换接口要同时迁移用户态并单独验收。调试信息已位于 debugfs 的部分
不需要迁回 sysfs，也不应成为应用必需 ABI。

| 接口/绕过 | 目标接口与退出条件 | 本次状态 |
|---|---|---|
| VDIN `hdr_curve` sysfs | 固定诊断曲线放 debugfs；产品色彩/tone mapping 用可评审的 V4L2 控制和标准色彩元数据 | 已审计，未替换；用户态 hdr-curve 仍消费它 |
| Wave5 `isolated/recovering/isolation_reason/isolation_time_ns` | V4L2 queue error/标准事件负责失败通知，设备级诊断用 debugfs/trace；迁移 monitor 后再删 sysfs | 已审计；不能把 DMA 隔离保护删掉换取风格清洁 |
| Wave5 `timeout_command/recovery_fail_step` | KUnit/故障注入配置或 debugfs，生产配置不暴露写入式故障注入参数 | 已审计，硬件恢复验收欠账保留 |
| 风扇 `speed_percent/sensor_fault/temperature_millic/trigger_temperatures` | thermal cooling state/trip 和适用的 hwmon `pwm`/温度/fault；板级安静策略移出驱动 | 已审计，ABI 文档存在但不代表标准 ABI |
| CRG `udc_debug`、debug 参数 | dynamic_debug/debugfs；电气测试应使用 USB 标准测试机制 | 已审计，仍有厂商风格宏和全局单实例状态 |
| TEE `sys_boot_complete` | firmware/TEE 生命周期内完成握手并记录契约；闭源 supplicant 依赖需先确认 | 已审计，schema 与 ABI 均未冒充完成 |
| JPEG `/dev/jpegenc` 私有 ioctl | V4L2 M2M、JPEG 标准格式/quality 控制、vb2/dma-buf | binding 已补，驱动架构迁移待做 |
| RX `phy_test/core_test/uhd60/dynamic_modes/hdr_probe/hdr_capture/audio_test`；VDIN `nv12/direct_dma` | 能力、格式和 pipeline 由 media/V4L2 协商；纯诊断留 debugfs | 已审计，不能离线强开所有未验路径 |
| clock/pwrc 常开、固定 DRM handoff | genpd/clk 消费者完整 quiesce/resume；原生 KMS 资源拥有与 HPD/EDID/modeset | 已审计，退出沿用厂商能力对照 F1–F3 门禁 |

## 主题序列与一键离线验证

[series](../packaging/kernel-edge/series/series)按原始拓扑顺序列出 290 个保留作者的邮件补丁，
文件按主题分目录。**目录分组不改变应用顺序**，跨主题依赖仍按总 series 应用。
已在独立 Git index 从 v7.3 逐个应用并比较 tree，结果与 `0a775305` 完全相同
（`e35abde9a3661a84746427495ddc0f727bf33dda`）；不是只证明补丁能导出。
新增整改提交保存在整理分支，未混入这份固定基线审计。

工具在 Linux VM 运行，不自动 fetch。以下 `$RECIPE` 指主仓 `packaging/kernel-edge` 的副本，
输出目录须不存在；完整构建需预留磁盘。准备独立 Python venv，安装
[验证依赖](../packaging/kernel-edge/maintenance-requirements.txt)，并将其 bin 加到 PATH。

```sh
python3 "$RECIPE/maintain.py" inventory --source ~/src/linux-7.3 \
  --head 0a775305 --output ~/build/vim4-series-new

# 先明确 fetch 目标，forward 本身只操作本地对象；复用现有提交身份，不改 Git 配置。
git -C ~/src/linux-7.3 fetch --no-tags \
  https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git \
  refs/tags/next-20261023:refs/tags/maintenance-next-20261023
python3 "$RECIPE/maintain.py" forward --source ~/src/linux-7.3 \
  --head 0a775305 --target maintenance-next-20261023 \
  --branch maintenance/next-new --worktree ~/src/linux-next-vim4-new \
  --output ~/build/vim4-forward-new

python3 "$RECIPE/maintain.py" verify --source ~/src/linux-7.3-maintenance \
  --base v7.3 --config "$RECIPE/uhd1.config" \
  --output ~/build/vim4-verify-new --build
```

`forward`只在新分支 rebase，遇冲突保留现场和 JSON；第一次停止数不冒充总冲突数。
VM 无配置身份时，先通过环境传入与开发机 `git var GIT_COMMITTER_IDENT` 一致的
`GIT_COMMITTER_NAME`/`GIT_COMMITTER_EMAIL`；身份预检失败不会分配工作树。
解决后用 `git rebase --continue`，然后对完整结果运行 `verify`。
`verify`即使 host/checkpatch/schema 失败仍继续收集各阶段，最终非零退出；schema 的
Kbuild 零退出不覆盖已输出的 DT 验证诊断。产物仅用于离线检查，不是部署包。

内核整理分支的 `scripts/vim4/offline-tests.py` 一次运行 34 个 tracked fixture，包含实际 C
函数的寄存器、边界、DMA 所有权和停止/恢复故障注入；每项有独立日志、超时和结果 JSON。
[基线结果](kernel-audit/host-tests.json)为 34/34。初次统一验证的 schema venv 缺 Pillow，
JPEG 解码 fixture 失败；独立完整依赖环境补测 34/34，不能把初次失败抹掉。
可通过 `--kunit-config /path/to/.kunitconfig --kunit-arch arm64` 再调用内核原生 KUnit/QEMU；
本轮未运行 KUnit 虚拟机测试，JSON 中 null 明确表示未运行。host C fixture 不是 KUnit。

## linux-next 成本与长期分支

目标固定为 `next-20261023`，commit `20a33c6b6cbe7e4805dfb6cd68816937443aa148`；
本轮远端未提供 `v7.4-rc1`。远端可用性以实际 fetch 为准，不能用版本名推定发布。
实际重放 290 条，Git 自动去掉 7 条已被主线包含的补丁，保留 283 条。
共 **9 次冲突停止、7 个不同文件**，从 rebase start 到 finish（含人工阅读、处理与并行
审计）为 **1028 秒**；这不是可外推的人日估算。原始冲突与去重日志保存在
[重放记录](kernel-audit/rebase.log)，[成本数据](kernel-audit/cost.json)含逐次提交/文件。

| 冲突主题 | 停止次数 | 处理 |
|---|---:|---|
| Synopsys HDMI bridge | 1 | 删除已随 RXSENSE 重构废弃的初始化 |
| Meson HDMI encoder | 2 | 保留主线显式 encoder 清理及下游错误处理/HDR helper |
| Khadas MCU/风扇 | 3 | 合并主线新 VIM4 支持与下游平台数据/安静策略，保留 PM 失败回滚 |
| T7 clocks | 1 | 合并重复 AXI fabric 注释，不扩大常开策略 |
| brcmfmac | 1 | 同时保留主线漫游特性与 WCC capability setup |
| Wave5 close/recovery | 1 | 保留统一错误出口和 PM 引用平衡，错误路径解锁后延后挂起，成功路径同步 put |

首轮 `make -k` 编译受影响驱动目录：两个 T7 DRM 驱动出现 **6 error、1 warning**，
是 `.reset`/reset helper、simple encoder 和 devm OF bridge helper 的 API 变化。
新增 `e38d04466478e` 改用 `atomic_create_state`、显式 encoder funcs 和
`of_drm_get_bridge_by_endpoint`，并用 devres 平衡 bridge 引用。
实际 probe 片段的 C fixture 覆盖 defer、非法 endpoint、无下游桥、devres 注册失败和释放；
修复后同一目录构建退出 0，35/35 host fixture 通过。

| 离线结果 | 7.3 整理分支 | next 迁移分支 |
|---|---|---|
| 整理 HEAD | `ca0e6c12862c6` | `e38d04466478e` |
| 新增提交 strict checkpatch | 3 条均 0/0/0 | 同三条及 DRM API 适配均 0/0/0 |
| host fixture | 34/34 | 35/35 |
| 变更 YAML binding/实例 | 通过 | 通过 |
| 8 个直接变更 DTS 的 schema 检查 | 通过 | 通过 |
| 完整 Image、dtbs、modules | 通过 | 通过 |
| KUnit/QEMU、硬件/性能验收 | 未运行 | 未运行 |

新提交严格检查见[7.3 记录](kernel-audit/checkpatch-new.log)和
[DRM 适配记录](kernel-audit/checkpatch-next-fix.log)。统一验证详见
[7.3 结果](kernel-audit/baseline-verify.json)、[next 结果](kernel-audit/next-verify.json)和
[next host 结果](kernel-audit/next-host-tests.json)。整条历史补丁栈仍有风格欠账，
两个 `verify` 的非零状态来自该历史 strict 检查，不能被构建通过覆盖。

VM 原始日志与产物：`/home/deepdream/build/kernel-maintenance-20261023/`；
使用原 `uhd1.config`，保留 BTF，不安装模块。成本数据记录输入/实际配置哈希、编译器、
最终树、Image 哈希和模块数量；首次缺依赖、初次编译失败均保留，不把修复前结果改写成通过。
7.3 产出 2334 个模块，next 产出 2333 个；同一输入经 `olddefconfig` 后移除 4 个、
新增 3 个通用模块，具体路径和实际配置哈希列在成本数据中，不能只比较总数量。

两条内核新分支均已推送：
[7.3 整理分支](https://github.com/vim4-kvm/linux/tree/maintenance/upstream-20261023)、
[next 迁移分支](https://github.com/vim4-kvm/linux/tree/maintenance/next-20261023)。
主仓离线套件本轮共 226 项：220 项通过、6 项按已有条件跳过。未触碰正式内核分支或板端状态。

建议长期保留四层：正式 `vim4-kvm-7.3` 只接已通过门禁的提交；`topic/*` 保存各子系统可独立
评审的小系列；`integration/next-日期` 固定目标、系列清单和配置，定期记录冲突/构建/测试成本；
`experiment/*` 隔离 handoff、私有 ABI、故障注入和受控上电。topic 之间写明 DT/clock/pwrc
依赖，避免跨主题随意重排。保留原作者和提交签名，先吸收上游已有实现，再删除对应下游补丁。
离线门禁通过后，占板回归按[部署门禁](subsystems/deployment.md#内核开发流程与部署门禁)
批量安排；rebase/全局改动仍需九类回归和性能对照，当前工作不证明可部署。
