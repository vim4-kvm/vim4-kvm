# 2026-11-05：解码调试候选加载地址与启动门禁

首轮调试窗口未运行 compliance 或 Fluster。U-Boot 读取调试 Image 时发生
Synchronous Abort，自动回到正式内核；随后预写流程正常重启并验证基线与实际视频。
HEVC 启动握手修正仍未提交、未实板验证，不能把这次失败归为解码器运行失败。
后续高地址候选已进入调试 Linux，但暴露启动诊断问题及 media 查找失败，见末节。

## 身份与原始证据

候选来源、配置及归档见[离线准备](2026-11-05-vdec-standard-preparation.md)。
本次使用候选 `7.3.1-vim4-20261105.22`，Image build ID
`9244e6c734b7cac00d9b38c7d09bb494295d055b`；窗口 `hwdecode-parity-r31`。
动作入口为主仓库 `1aa279b` 的 vdec-window，编排脚本与输入计划保存在
`build/hwdecode-parity/run31/`。板窗前主仓库全量 534 项、11 项跳过，通过。

输入已离线校验，首轮选择标准 HEVC `AMP_A_Samsung_7`，源 SHA256
`09a9c0d78a502ece45f1df02c773b18bb3133fe21a8f1e9046db19bfa68f7c29`。
compliance 的 Vhdr 输入只包装 ffprobe 给出的 17 个访问单元，重新拼接与源字节一致。
没有生成或替换标准码流；该输入仍未送入硬件。

UART `logs/hwdecode-parity-r31/uart-1793856019831612000.log` 显示：
RAM sysboot 已选择候选，读取 Image 时在 `0x05100000` 发生异常，调用链为
`__asm_invalidate_dcache_range` → `mmc_read_blocks` → `ext4fs_read_file`。
随后重启，日志中出现的 Linux 为正式 `.3`，没有调试候选 Linux 启动记录。
候选就绪检查因此失败，180 秒外层时限结束后走恢复，不继续解码。

离线核对 u-boot-edge `4317387a6a58f4d42186cbadc24cd3cc52675bc3`：
`board/khadas/configs/kvim4.h:149` 默认 kernel_addr_r 为 `0x01080000`；
`board/khadas/kvim4/kvim4.c:316` 的第一段普通内存映射止于 `0x05100000`，
下一段从 `0x09000000` 起。调试 Image 为 90,765,824 字节，旧 Image 为
48,347,648 字节；前者按默认加载地址跨入该映射空洞。地址与异常吻合，后续需调整
一次性加载布局并验证，不能通过关闭要求的调试配置掩盖问题。未改写 U-Boot 环境。

## 恢复与未运行项

`returned-baseline-identity.json` 核实正式 `7.3.1-vim4-20261104.3`，build ID
`e595ad243d663f6c33b92678a4de6e0b78ec16d5`，完整基线身份与文件检查通过。
`returned-video.log` 为视频接收器原始输出：五秒 4K 接收新增 298 帧，
59.569 fps，新增丢帧、冻结均为零。窗口退出并释放板票；私有 release 的临时
SDIO 固件按哈希核对后删除。持久启动项与生产配置没有改动。

本轮标准流、带流 compliance、KASAN/锁/DMA/泄漏运行验收、厂商对照及性能均未运行。
窗口记录仅证明启动失败路径和此次正常恢复，不证明硬锁情况下总能恢复。

## 高地址启动复验

`display-once.py` 按 ARM64 Image 头的内存范围核对加载布局；大镜像仅在本次
U-Boot RAM 环境设置 kernel_addr_r，prepare、读包与 board-window 使用同一检查。
要求头部允许异地加载，范围留在审阅过的普通内存段；不写 saveenv、不关闭调试选项。
新增一项工具回归覆盖本次跨映射空洞与不允许重定位的失败，主仓库 535 项、11 跳过
通过，原始输出 `debug-load-layout-full-tests.log`。实际旧危险包被拒绝、新包完整
校验通过，见 `debug-load-layout-bundles.log`。

新 payload 为 `hwdecode/debug-high`，同一 Image/config/整套模块；RAM 归档 SHA256
`8413dd49d658ff62b64b67cd644626f3342dce5fc6ca33c6f0a5c19ce6e36cf9`。
窗口 `hwdecode-parity-r32` 实际进入 `.22`，证明高地址加载修正有效。旧失败私有包及
重复输入在逐文件/归档核对后清理，宿主原包和日志保留；详见 `run32/cleanup-old.log`。

但启动日志已经出现三项诊断，均早于解码操作：

- PWM regulator 调用 meson PWM 的 clk_set_rate 路径与 clk_pwm_get_duty_cycle
  的锁顺序形成循环依赖，涉及 prepare_lock 和 PWM nonatomic_lock。
- ADLA 映射长度 73,728 字节的 SG 段，超过设备报告的 65,536 字节上限，触发 DMA-API WARNING。
- brcmfmac 的 brcmf_nvram_handle_comment → strchr 在固件 NVRAM 末尾发生
  KASAN vmalloc-out-of-bounds 读。

原始启动日志 `logs/hwdecode-parity-r32/dmesg-1793857262099786000.log`，完整窗口日志
在该目录的 `validation-fluster-1793857262223514000/`。当时工具未在解码前检查这些
启动诊断，仍运行了电源/MDEC/HEVC 固件预检；随后因 media 设备查找失败停止。
compliance 命令与 Fluster 均未开始，不能把预检通过记为零 splat 或解码通过。

预写恢复完成，完整正式基线身份重新通过；`returned-video.log` 实测五秒新增
300 帧、59.954 fps，新增丢帧和冻结均为零，板锁释放。后续必须先处理启动诊断和
工具门禁，不能筛掉这些日志继续宣称调试验收通过。

离线工具修正：media core 在 `drivers/media/mc/mc-devnode.c` 注册的是 media bus，
不是 media class；改从 `/sys/bus/media/devices` 按真实父设备关联查找，待下一轮实板
验证。启动日志门禁提前到任何解码器操作之前，预检后和结束时再检查；正常的
DMA-API 启用信息不算错误，实际 WARNING/KASAN 等仍直接失败。新增一项真实诊断
失败路径回归，主仓库 536 项、11 跳过通过，输出 `vdec-startup-guard-tests.log`。

## 启动 splat 修复交接

按用户最新安排，三项启动问题由独立 worker 修复，解码任务不再修改这些目录。
已经通过 tools/vm 创建 VM 工作树 `/home/deepdream/src/linux-7.3-debug-splat-fixes`，
分支 `debug-splat-fixes`，起点为部署版本
`2662456a1a636f668454ab04a1c63f567206a592`；构建目录为
`/home/deepdream/build/debug-splat-fixes`。交接时未向该工作树复制代码、未产生修复提交。
hwdecode-parity 也未改动这三个子系统。

### brcmfmac 草稿

Mac 主仓库私有目录 `build/hwdecode-parity/edit/brcmfmac/` 有草稿：
firmware.c/h、Kconfig、Makefile、firmware_kunit.c 和 .kunitconfig。尚未编译、未跑
KUnit、未做静态检查，不是已验证补丁；仅供接手者审阅，勿直接视作完成。

草稿在 nvram_parser 保存输入长度，用有界 strnchr 查找注释换行，有界 memchr
处理 NUL，避免末尾无终止字符时越界；保留 NUL 先于换行时的原语义。
通过 KUnit visibility 暴露真实 brcmf_fw_nvram_strip；两个拟议用例覆盖无 NUL/
无换行的末尾注释，以及 NUL 先于后续键值换行。前者使用精确长度分配，建议开启
KASAN 实际复现旧实现失败，再验证修复。使用标准 KUnit device 辅助，不模拟 Wi-Fi
总线或固件请求；原始实板堆栈见上述 r32 日志。

### PWM 与 ADLA

这两项没有代码草稿。PWM 原始锁链在 r32 dmesg 的启动 4.2 秒附近；ADLA 的
DMA-API 警告在 16.7 秒附近。需要接手者从实际调用关系核对修复及各自验证方法。

首个 lockdep 故障会关闭后续锁检查，KASAN 默认只报告首个错误，因此 r32 中
后续未再报错不能证明解码器内存或锁安全。下一次调试窗口等待用户通知修复分支
就绪，再由 hwdecode-parity 合入独立修复构建候选，一次启动同时验证修复与解码。
在此之前解码任务只做离线工作，不再开调试板窗口。
