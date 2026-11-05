# 2026-11-05：调试启动 splat 离线修复与 PWM 锁拓扑

本轮只做离线工作。brcmfmac 移植上游修复，ADLA 按设备上限构造 SG；
PWM 按协调者审阅后授权修正不同 chip 的 lockdep 建模；同 chip 的真实 ABBA
明确保留为未解决项。三项全部消失的实板验收仍未完成，当前分支尚未证明零 splat。

源码工作树为 VM `vim4-build` 的 `/home/deepdream/src/linux-7.3-debug-splat-fixes`，
分支 `debug-splat-fixes`，起点 `2662456a1a636f668454ab04a1c63f567206a592`。
没有改动三个目录原有 Python 测试，没有访问板子、申请板锁、推送或合并。
启动原始证据见[解码记录](2026-11-05-vdec-debug-boot.md#高地址启动复验)。

## 上游核对与 brcmfmac

核对主线、linux-next、wireless 维护者树的 `firmware.c`，均已有有界注释搜索。
直接 cherry-pick `3ffb0de666c6dc3831a16ad33f9c9fd8a9310dcb`，本地提交
`17d29954473b6`；保留 Pengpeng Hou 作者、全部签名、Ack 和 Link。
[上游提交](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=3ffb0de666c6dc3831a16ad33f9c9fd8a9310dcb)、
[v2 邮件](https://lore.kernel.org/r/20260920034414.16948-1-hppiscas@163.com)、
[维护者回复镜像](https://lore-kernel.gnuweeb.org/linux-wireless/20261004094545.1324258-1-arend.vanspriel%40broadcom.com/T/)。
lore 原站访问失败时用公开邮件镜像交叉核对，未发送任何邮件。

根因在 `drivers/net/wireless/broadcom/brcm80211/brcmfmac/firmware.c`：
`brcmf_nvram_handle_comment():175` 原来把有长度的固件 blob 交给 `strchr()`；
末尾注释既无换行也无 NUL 时会越界。修复保存完整输入长度，并在剩余范围内用
`strnchr()` 搜索换行、`memchr()` 搜索 NUL。找不到终止符时结束注释解析是输入
确已耗尽，不截短有效输入；输出容量上限不能用作输入长度，否则长注释后面的
有效配置会被丢掉。`strnchr()` 保留 NUL 先于换行时的原有字符串语义。

新增 KUnit 条件可见的真实 `brcmf_fw_nvram_strip()`，通过
`VISIBLE_IF_KUNIT` / `EXPORT_SYMBOL_IF_KUNIT` 测试，不复制解析器。
三例覆盖精确长度且无终止符的末尾注释、嵌入 NUL 后的有效键值、超过输出容量的
长注释后仍保留有效键值。测试用标准 KUnit device，不模拟总线或固件请求。
测试与条件可见接口独立提交 `496597ebdf19`，使上游修复提交本身保持原样。

## ADLA DMA 路径

主线、linux-next 和 char-misc 维护者树未提供这个下游 `drivers/misc/adla` 驱动，
lore 检索未找到对应修复，因此这一项自写。没有推断或放大硬件的最大段长。

`drivers/misc/adla/drv/port/os/linux/mm/adlak_mm_os_common.c:172`
的 `adlak_dma_map_of_discontiguous()` 原先用 `sg_alloc_table_from_pages()`，
后者在 `include/linux/scatterlist.h:495` 直接传 `UINT_MAX` 合并相邻物理页，
导致 18 个相邻 4 KiB 页形成 73,728 字节段。紧接着的 `dma_map_sg():182`
把它送入 DMA API，`kernel/dma/debug.c:check_sg_segment()` 检查原始 SG 长度，
发现超过设备 `dma_get_max_seg_size()` 返回的 65,536 字节。

修复换用 `sg_alloc_table_from_pages_segment()`，直接传
`dma_get_max_seg_size(mm->dev)`。这会在 SG 生成阶段拆开相邻页，而不是依赖
`dma_map_sg()` 替驱动修正不合规输入。当前告警对应的相邻区间会形成
65,536 + 8,192 字节两段；总映射范围与缓存维护范围不减少。
`kernel/dma/direct.c:575` 的 direct SG 路径逐项映射并返回输入项数，
该路径的 map、sync、unmap 继续使用相同项数，不改变原有句柄生命周期。

修复提交为 `4c4126df2f8a`。这次只改变标准 SG 构造 API 的参数，没有可独立提取的驱动纯逻辑；不增加复述
内核 SG 实现的测试。真实 DMA API 路径与启动分配仍必须在下一调试窗口验证。

## PWM 锁依赖分析与修复边界

修复提交 `0a35577b8de2`，为每个 pwm_chip 的 mutex 注册独立 key，最终 device
release 时注销；未导出 CCF 锁、未改变调频或锁顺序。分配、add 失败、remove 后
延迟释放均沿用同一 key 生命周期。

实际部署 DTS 的 regulator 使用 AO PWM，Wi-Fi 使用 `pwm_ab` 通道 0，确为不同
chip；但 debugfs / 初次 request 仍可对 Wi-Fi chip 建立同实例反向依赖。协调者
明确授权先修正不同实例建模，并保留同 chip 真实 ABBA 为未解决项，不声称所有
PWM/CCF 锁链已经解决。完整的拓扑、r32 日志证据限度、上游讨论结论及局部选项
见 [PWM 锁分析](../pwm-clock-locking.md)。

新增 `drivers/pwm/core_kunit.c` 通过实际 PWM/CCF API 与受控线程竞争，确定建立
chip → CCF 依赖后，从 CCF 回调进入另一个 chip，验证回调执行且 lockdep 仍开启。
无寄存器模拟，没有复制框架代码。结果见下表。

## 验证与证据

构建只持 Mac `tools/board-queue run --heavy` 票。私有输出保存在 VM
`/home/deepdream/build/debug-splat-fixes/`，本仓库 `build/debug-splat-fixes/`
保存检索快照与交付日志。

| 项目 | 结果与原始日志 |
|---|---|
| arm64 QEMU + generic KASAN | `brcmfmac-final.log`：最终代码真实解析器 3/3 通过，`kunit/result.json` 与 `kunit/test.log` |
| strict checkpatch | 上游移植及两个本地完整提交均 0 error/warning/check，`upstream-style.log`、`brcmfmac-commit-style.log`、`adla-commit-style.log`；新增文件仅忽略 FILE_PATH_CHANGES，Broadcom/PWM 既有 MAINTAINERS 范围无需改变 |
| brcmfmac 静态检查 | W=1、C=2，sparse 固定 `v0.6.5-rc1-21-g84ec0658`（源码 `84ec0658c81db4ccc4aabc420d3dc118c2c6a310`），日志有实际 CHECK，内建/模块均无 brcmfmac 诊断；`validate.log`、`module-verification.log` |
| 模块 | `module-verification.log` 核对 MODULES=y，BRCMFMAC、测试、ADLA、PWM_MESON、COMMON_CLK_PWM 均为 m；实际生成 brcmfmac.ko、firmware_kunit.ko、adla_core.ko 等；未在 QEMU 另做模块加载测试 |
| 内建 | `builtin/.config` 上述驱动均为 y，W=1+C=2 目标对象和 built-in.a 编译完成；初次名为 module 的输出因未启用 MODULES 实际为 y，未把该次当作模块结果，后续由上述真模块构建补齐 |
| ADLA 静态检查 | W=1+C=2 确实执行且编译成功，新增 SG 调用无诊断；整个下游驱动并非零诊断。修改文件原有 6 处 gfp_t 传给 unsigned int、整数充当 NULL、未使用 vm_page_prot，以及其他 vendor 文件的原型/格式/kernel-doc 警告仍保留，不声称完成全驱动警告清理 |
| 头文件文档 | `kernel-doc.log`：更正既有 fw/fw_base 描述后，firmware.h 的 kernel-doc 无诊断 |
| PWM QEMU | `pwm-kunit-final2.log`、`pwm-kunit/result.json`、`pwm-kunit/test.log`：PROVE_LOCKING 开启，受控竞争用例 1/1 通过，无 lockdep splat |
| PWM 静态/构建 | `pwm-builds.log`、`pwm-final-verification.log`：core（始终内建）、Meson/clk-pwm 模块及内建的 W=1+C=2 编译完成，PWM 范围无诊断；实际 lockdep 配置也编译完成；测试内建及 core_kunit.ko 编译完成；`pwm-kernel-doc.log` 无诊断 |
| 测试模块元数据 | `test-module-metadata.log`：补齐两个测试模块的 MODULE_DESCRIPTION 后，重新 W=1+C=2 并链接，无新增测试模块 modpost 警告；未修改 arm64 vgetrandom 的既有 sparse 声明警告保留，不声称全树零诊断 |
| 生产配置 | `production/.config` 从本仓库 packaging/kernel/kernel.config 生成，完整 Image/modules/dtbs 成功，生成 2,338 个 .ko；最终退出码 0，见 production-resume.log |
| 主仓库 | `python3 -m unittest discover -s tests -p 'test_*.py'`：536 项，跳过 14 项；完整结果在 build/debug-splat-fixes/main-tests-final2.log |

`validate.sh` 和 `module-verification.log` 保存实际命令。首次 KUnit 配置因缺少
NETDEVICES 被 Kconfig 拒绝，已在测试配置补齐依赖。修复前对照在协调者要求停止
前已自行结束，之后未再运行；`kunit-before.log` 保留其结果。紧接的一次修复后
运行因复制源文件保留旧 mtime 而复用了旧对象（`kunit-final.log`），强制更新
源时间戳后重新编译并以 `kunit-final2.log` 的 3/3 作为最终有效结果，不隐藏失败日志。
smatch 未安装，未运行。未改 binding/DTS，无新增 schema 验证。为避免混用
`struct pwm_chip` 新旧布局，修改头文件前停止本任务当时的生产构建，确认编译进程
退出后再修改并恢复；首次 `validate.log` 中的生产阶段因此中断，不能当作通过，
最终通过证据为 `production-resume.log`。完整生产配置 SHA-256：
`7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`；Image：
`4e52c3f963eaa817887359b417a863c3728b395e4ca54dcbef8b566d34623cf6`。

编译器为 GCC 13.3.0，QEMU 8.2.2，VM 没有 KVM 加速、实际使用 TCG。
验证后只整理本分支测试元数据的 fixup 历史，保持上游移植提交 `17d29954473b6`
不变；最终树与验证代码的 Git tree 均为
`498d698513dea3eafa0a2e799a6fe3deb796f292`，没有因整理历史改变代码。

## 下一调试窗口的判定条件

由 hwdecode-parity 在 t3k 的下一次调试窗口合入经审阅的本分支，再构建同次
Image、DTB 和完整模块。本轮不发起窗口。独立 key 只修正跨实例建模，不等于所有
PWM/CCF 锁链都已解决；运行门禁仍必须拒绝包括保留的同 chip ABBA 在内的任何 splat。

启动后、首次解码前及窗口结束时均要求零 lockdep/KASAN/DMA-API 告警，且
lockdep 没有因首错关闭。正常 `DMA-API: debugging enabled` 不算告警。
三个旧特征必须同时消失：

- `possible circular locking dependency`，堆栈涉及 `prepare_lock`、
  `nonatomic_lock`、`clk_pwm_get_duty_cycle`、`meson_pwm_enable`。
- `adla ... mapping sg segment longer than device claims to support`
  （旧值 `[len=73728] [max=65536]`），且 ADLA probe 仍成功。
- `KASAN: vmalloc-out-of-bounds` / `brcmf_nvram_handle_comment` / `strchr`，
  且 Wi-Fi NVRAM 与固件加载正常。

不能因其中一项没再出现就通过：还须确认对应设备确实 probe、调试配置仍开启，
启动 gate 及后续解码 gate 都通过。实板结果由下一窗口追加，不用离线结果代替。
