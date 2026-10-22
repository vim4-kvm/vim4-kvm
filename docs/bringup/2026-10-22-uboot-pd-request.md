# 2026-10-22：U-Boot 固定 5V USB PD Request（离线候选）

摘要：修正 Fixed RDO 电流与 USB 标志，并把 PDO 策略收敛为固定 5V、最多 3A。
主机协议/FDT 测试、Linux 函数交叉比较、独立构建及镜像重打包通过。
本轮没有 SSH、串口、板锁、刷写、重启或服务操作；没有本轮上板/恢复基线证据。
正式部署由另一会话进行，本候选留待用户另行安排，不能据离线通过宣称 Mac HID 已修复。

## 分支与实现

VM `vim4-build` 工作树 `/home/deepdream/src/u-boot-pd-request`，分支
`vim4-kvm-2019.01-edge-pd-request`，基于
`0d5a3d7848377c0093ecdfb15de80cf2bf83e928`，未修改原工作树、未推送。

- `84ac4ecf33b9c9b8123d87a76d1a8bc6c30cb54c`：严格 5V 策略、RDO 修正与测试/文档。
- `c714efb2e37c2fcfdae0ca626374728792a33f8b`：交接回归使用 Mac 单 PDO 样本；最终镜像版本。

`drivers/power/mfd/fusb302.c` 从前往后选择第一个电流非零的 Fixed 5V PDO；
工作/最大电流均为 min(源能力, 3A)，bit25 USB Communications Capable、
bit24 No USB Suspend 置位，bit26 Capability Mismatch 清零。3A 是上限，
不是最低功率需求，1.5A 来源仍请求 1.5A；本实现没有另外定义未满足的最低需求。
无可用 PDO 时清空选择与策略电压/电流，回到现有 wait-caps/最终超时回退路径，不发 Request。

Mac `0x3e01912c` 的正确请求为 **`0x1304b12c`**：
`(1<<28)|(1<<25)|(1<<24)|(300<<10)|300`。电流单位是 10mA；
`0x1301912c` 的工作电流仍为 1A，不能作为 3A/3A 的期望值。
5V/1.5A 则为 `0x13025896`。

删除原 charge IC 12V/6A 上限策略，影响该分支所有使用此驱动的板型：
不再支持高压充电选择或 Battery/Variable 请求。Linux `request_5v()` 要求 PDO1
为 5V；本固件也允许后续位置的 5V Fixed PDO，并在 RDO 中保留对应位置。
对通常 PDO1 为 5V 的来源，两者请求字节一致。

`/chosen/khadas,usb-pd-boot` 仍为 v1、16 个大端 u32，RDO 原样保存。
没有改等待时序、寄存器操作、快照编码，没有增加 Get_Source_Cap 或 Hard_Reset。
[热重启审查](2026-10-22-pd-warmboot-audit.md) 中接收中断乱序、
Soft_Reset 和合同后无人服务等问题仍未修复。

## 离线验证

在 VM 工作树运行：

```sh
python3 tools/test-vim4-pd-handoff.py --linux-pd-source \
  /Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/tools/usb-pd-init.c
cc -Wall -Wextra -Werror \
  /Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/tests/pd-request.c \
  -o /tmp/vim4-pd-request-linux-test
/tmp/vim4-pd-request-linux-test
```

沿用 handoff 框架，提取实际驱动函数，I²C/FIFO 为 mock，FDT 使用本仓库 libfdt。
覆盖 Mac 单 PDO、5/9/15/20V 多 PDO、1.5A、超过 3A、非首位 5V、
无 5V、零电流/非 Fixed/空列表、旧选择不复用及 FIFO 请求字节；
保留 PS_RDY 门控、原始 PDO、硬复位清标志、两种 DT 形状与无 fixup I/O 回归。
交叉比较直接编译 Linux `request_5v()`，遍历 1023 个非零电流字段值。
实际输出（`logs/pd-request/host-tests.log`）：

```text
PASS: fixed 5V only, 3A ceiling, 1.5A, no usable PDO, stale selection
PASS: Linux request_5v matches all 1023 nonzero source currents
PD boot: flags=c2 source=1061 request=1042 rdo=1304b12c rp=3 policy=5000mV/3000mA
PASS: USB Request, PS_RDY gate, raw PDO retention, hard reset, vendor/mainline FDT, no fixup I/O
PD request boundary tests passed
```

最后一行来自单独运行 Linux 测试；其三个拒绝用例会打印预期失败消息。
`flags=c2` 来自测试最后注入的接收硬复位和回退，不是板上测量或成功合同。
主仓库离线测试：163 项、5 skipped、OK，日志 `logs/pd-request/repo-tests.log`。

## 独立构建与镜像

按 U-Boot VIM4.md 的 GCC 12 参数构建，输出：
`/home/deepdream/build/u-boot-pd-request`；
BL33Z `BUILD_BASE=/home/deepdream/build/u-boot-pd-request-stub`。
仅本工作树的 `build`、`bl33z/build` 为指向私有输出的未跟踪符号链接。
实际 Mac 命令（脚本在忽略目录内，仅构建/打包）：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build bash \
  /Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/build/pd-request/build.sh
python3 build/pd-request/verify.py
```

脚本执行 `make O=/home/deepdream/build/u-boot-pd-request kvim4_defconfig`，
再以 `CONFIG_SUPPORT_BL33Z=1`、`-j10 CROSS_COMPILE=aarch64-linux-gnu- CC=gcc-12`、
`KCFLAGS='-Wno-error=array-bounds -Wno-error=misleading-indentation'`、
`LDFLAGS=--no-warn-rwx-segments` 构建；BL33Z 另加 `--gc-sections`。
重打包命令：

```sh
python3 tools/vim4-repack.py \
  /Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/build/kernel-edge/boot-input/u-boot.bin.sd.bin.signed \
  /home/deepdream/build/u-boot-pd-request-final --update-bl31
```

stock 输入 SHA256 `95547c4cd3624fab11ff118668bd15d1497aef8c8339049c714566bb63adadee`。
最终输出（`logs/pd-request/build-final.log`）：

```text
Verified stock round-trip, preserved early stages/BL30/BL40/BL32 and expected BL31/BL33
image bytes: 3248640
image SHA256: 0766bf9125f45f9a51e74acb49d5d6c0d964f46037a7f0f47437bb0981258874
FIP SHA256: a79382036a97ddf5e9e77f2a47cbeda991c8513befdad1f23731e5d6a14489d3
```

VM 镜像：`/home/deepdream/build/u-boot-pd-request-final/u-boot.bin.sd.bin.signed`；
Mac 副本：`build/pd-request/u-boot.bin.sd.bin.signed`。
清单 `build/pd-request/image-verification.json` 对比已部署 handoff 的本地镜像
（SHA256 `3ddfc405d283e5cc645382c5c00b4e8ddc261361825e721f5e7e87492dd30bab`）：
长度/FIP 载荷布局一致，FIP 前字节、BL30/40/31/32 逐字节一致，BL33 替换。
这里未读取当前 eMMC；历史镜像对比不能替代下次部署前的板上核对。

## 后续刷写与回退步骤（本轮未执行）

沿用[已执行部署流程](2026-10-22-pd-firmware-deploy.md#锁备份与刷写)，
仅替换 FIP，不能把整张 SD 镜像或整个 16MiB 备份写回。

1. 由用户另行安排窗口，Mac 外层 `/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock <窗口命令>`
   覆盖前置核验、备份、写入、读回、重启、测试与恢复全程。先确认用户届时指定的内核/manager 基线；
   不能把本任务开始时的 52d5e46… 强行覆盖到另一会话新部署的系统。
2. 核对根分区为 mmcblk0p2、第一分区 sector 32768、eMMC 可写且无挂载虚拟介质；
   核验候选完整哈希。读取现有 FIP，若仍为 handoff，其 SHA256 应为
   `751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0`；不符则停止并重新审核。
3. 新建专用备份目录（例如 `/var/backups/vim4-pd-request-20261022/`），保存前 16MiB、
   单独 FIP、extlinux 和内核/manager 身份清单，fsync 后复制到 Mac 并逐哈希核验。
   本次回退目标是现有 handoff，不能直接用上一轮的 `device-fip-before.bin`（它是更老固件）。
4. 写前再次确认整个前缀与新备份一致；从候选取偏移 672256、长度 2576384 的 FIP，
   只写到 eMMC 同一范围（512 字节 sector 1313，共 5032 sectors）。
   fsync 后读取完整前 16MiB，要求其等于“新备份仅替换 FIP”的期望值；
   FIP 哈希必须是上列 a7938203…，区间外逐字节未变。任何差异都不得重启。
5. 保持串口记录重启，确认 U-Boot 版本 c714efb2e3，核验 64 字节 chosen 快照。
   真实收到 Mac 单 PDO 时应见原始 PDO 3e01912c、RDO 1304b12c，并单独验证 PS_RDY、
   UDC configured 和实际 HID 输入；无 caps 的热启动不得算成功合同。
   冷插拔只能在另行安排的现场条件下执行。
6. 临时验证结束，在同一锁窗口核验当前 FIP 是本候选，再从**本次新备份**恢复 handoff
   FIP 到上述区间，fsync 并完整前缀读回核对。恢复后重启确认原 U-Boot、
   窗口开始时约定的内核 build ID、manager active；保留串口和哈希证据。
   不改内核、模块或应用的实验不应借回退覆盖另一任务产物。

历史部署中的 `build/pd-handoff/board.py` 固定了旧 FIP、备份目录和 manager 基线，
不能原样用于本轮候选；执行者须按以上新目标更新并离线审核后再使用。
Linux 不能启动时 SSH 回退不可用，仍需现场 FUNCTION+RESET 进入 OOWOW；
该失败恢复路径和本候选的冷启动、HID、双内核启动均未实测。
本轮没有需要恢复的板上改动，也没有执行“恢复后重启”，不引用历史结果冒充本轮证据。
