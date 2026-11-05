# 2026-11-05：解码调试候选尚未进入 Linux

首轮调试窗口未运行 compliance 或 Fluster。U-Boot 读取调试 Image 时发生
Synchronous Abort，自动回到正式内核；随后预写流程正常重启并验证基线与实际视频。
HEVC 启动握手修正仍未提交、未实板验证，不能把这次失败归为解码器运行失败。

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
