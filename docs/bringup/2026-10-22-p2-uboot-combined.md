# 2026-10-22：P2 PD Request＋KASLR 合并固件候选

最新结论：原合并候选 d54877c9f5 / 6a25037a… **现场冷启动循环复位，已撤回**。
用户经 OOWOW 恢复 pd-handoff FIP 并逐字节核对，板子已恢复正常。
本次分析和新候选构建完全离线；没有 SSH、串口连接或板端操作。
新候选、证据边界及必须先做的 microSD 验证见
[失败分析与 SD 验证](2026-10-22-uboot-sd-recovery.md)。以下原构建证据保留为历史，
旧 eMMC 流程不得跳过 SD 验证直接复用。

## 现场失败与恢复补记

用户最初观察 19 个循环；当前保存的 coldboot-uart.log 已有 32 次 DTB size 行、
31 个完整 d54877c9f5 banner，oowow-uart.log 另有 14 次 size 行，部分串口片段缺字。
每轮停在 `the dtb partition size is:40000   byte`，没有 seed handoff 日志，随后重入 BL2。
记录既有 5V/3A `PDO=3f01912c RDO=1304b12c`，也有用户报告的
5V/1.5A `PDO=3f019096 RDO=13025896`；`flags=41` 表示观测到合同完成和 Sink attached，
不能据此排除随后供电/PD Hard Reset。

恢复日志 recovered-boot-uart.log 的 0d5a3d7848 在同一位置继续 DTB 校验、文件系统
加载，最后到 Ubuntu login。fip-before.bin SHA 为
`751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0`；
fip-new.bin SHA 为 `efb0bef62ca74dbaff85d00817bf5e35574e2e06c4eba5e07e788dd64007eca9`。
现场恢复逐字节核对由用户完成；本轮只复核已有文件，不能把本地备份哈希称为新板端回读。

**FUNCTION+RESET 在此次早期崩溃下无效；拔 SD、断开全部供电/回供、按住 FUNCTION
再冷上电可以进入 OOWOW。** 热复位组合依赖 eMMC U-Boot 运行到按键检测，不能作为
任意引导故障下的恢复保证。不能把冷上电的成功进一步推断成未公开 MCU/BootROM 实现细节。

高置信结论是故障窗口早于 RNG/FDT seed fixup；直接诱因尚未确定。
新候选移除 Linux 启动的 Android 保留 DTB 探测，并修复独立的 T7 RNG READY 握手遗漏。
主机测试覆盖路径避让及握手故障，**不等于已复现或证实修复物理复位**。

## 分支、实现与离线证据

VM 工作树 `/home/deepdream/src/u-boot-pd-kaslr`，分支
`vim4-kvm-2019.01-edge-pd-kaslr`，基于 `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`。
先快进到 pd-request `c714efb2e3`（包含 `84ac4ecf33`），再合并 kaslr `d1c2033e4b`。
合并提交 `0d4af00f156a91c9b00a2b3aea3a6dbb08f1f825`；最终 `d54877c9f5e612db08969f3f0edc4ba37c86568b`
仅增加成功交接长度日志，不输出种子值。未更改原工作树、未推送。

实现细节分别见 [PD Request](2026-10-22-uboot-pd-request.md) 与
[KASLR](2026-10-22-p2-kaslr.md)。串口成功日志为：
`Boot random seed handoff: kaslr-seed=8 rng-seed=32 bytes`。
只有两个 FDT 属性成功写入才打印；硬件超时、卡死样本、FDT 空间不足仍走失败提示。

在合并工作树执行：

```sh
python3 tools/test-vim4-pd-handoff.py --linux-pd-source \
  /Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/tools/usb-pd-init.c
python3 tools/test-vim4-random-seed.py
git diff 0d5a3d78 --check
```

`logs/p2-round2/uboot-final-tests.log` 实际输出：

```text
PASS: fixed 5V only, 3A ceiling, 1.5A, no usable PDO, stale selection
PASS: Linux request_5v matches all 1023 nonzero source currents
PD boot: flags=c2 source=1061 request=1042 rdo=1304b12c rp=3 policy=5000mV/3000mA
PASS: USB Request, PS_RDY gate, raw PDO retention, hard reset, vendor/mainline FDT, no fixup I/O
PASS: fresh seeds, FDT encoding, retry, bounded RNG faults and allocation rollback
```

此处 flags=c2 为 mock 硬复位/回退用例，不能当作真实合同成立。
测试编译实际函数，覆盖协议边界、重试清旧种子、FDT 字节序及有界故障；不是 RNG 熵认证。

## 构建与镜像

Mac 以 `/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build ...` 串行重型构建。
私有 `O=/home/deepdream/build/u-boot-pd-kaslr`；kvim4_defconfig，GCC12，
`CONFIG_SUPPORT_BL33Z=1`、`CROSS_COMPILE=aarch64-linux-gnu-`，参数沿用原候选文档。
BL33Z 私有 `BUILD_BASE=/home/deepdream/build/u-boot-pd-kaslr-stub`。
构建脚本 `build/p2-round2/build-uboot.sh`；首次完整构建另见 `uboot-build.log`。
`tools/vim4-repack.py STOCK OUT --update-bl31` 的 stock SHA256 为
`95547c4cd3624fab11ff118668bd15d1497aef8c8339049c714566bb63adadee`。

最终镜像 VM `/home/deepdream/build/u-boot-pd-kaslr-final/u-boot.bin.sd.bin.signed`，
Mac 副本 `build/p2-round2/u-boot.bin.sd.bin.signed`：

```text
image SHA256 6a25037a5adc7fc422a64084e9d5b719169c70c2c360857373eead13b15a4566
FIP   SHA256 efb0bef62ca74dbaff85d00817bf5e35574e2e06c4eba5e07e788dd64007eca9
Verified stock round-trip, preserved early stages/BL30/BL40/BL32 and expected BL31/BL33
```

最终构建日志 `logs/p2-round2/uboot-final-build.log`；逐段验证清单
`logs/p2-round2/uboot-image-verification.json`。较早的 ab63ac… 镜像不含成功长度日志，
已经由上述最终镜像替代，不作为现场刷写目标。

只读获取板上前缀，当前 FIP SHA256 仍为
`751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0`。
候选对比 handoff：FIP 前早期阶段及 BL30/40/31/32 均逐字节不变，只替换 BL33。
镜像 3248640 字节，FIP 位于 `0xa4200`（672256），长度 2576384。
sector 0 的磁盘身份/分区表不由候选覆盖。

## 历史 eMMC 刷写流程（仅 SD 验证通过后参考）

1. 用户在板边、USB-C 接线/供电可冷插拔且 OOWOW 恢复可用时开始。
   Mac 外层持 `/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock <窗口脚本>`，
   覆盖备份、写入、读回、冷启动、两次重启、HID 与必要回退；暂停另一任务板上操作。
   开启 `tools/uart-log.py`。记录窗口开始时内核 build ID、应用哈希、PD 快照、空 LUN、
   实际 HID。若仍采用本轮基线，内核应为 `3ed254bfa838ab50732fdce1c5134400a1663fd5`。
2. 核对候选完整 SHA256、根设备 mmcblk0p2、首分区起始 sector 32768。
   新建 `/var/backups/vim4-pd-kaslr-onsite-日期/`，不能复用旧回退固件：

   ```sh
   sudo dd if=/dev/mmcblk0 of=BACKUP/emmc-prefix-16MiB.bin bs=1M count=16 status=none
   sudo dd if=/dev/mmcblk0 of=BACKUP/fip-before.bin bs=512 skip=1313 count=5032 status=none
   sudo cp /boot/extlinux/extlinux.conf BACKUP/
   sudo sha256sum BACKUP/*.bin
   sudo sync
   ```

   `BACKUP` 替换为本次真实目录；将备份复制到 Mac，逐哈希比较。当前 FIP 必须匹配上列
   handoff 哈希，否则停止、重新审查回退目标。确认 16MiB 备份内 FIP 与单独备份相同。
3. 从候选提取 FIP：`dd if=CANDIDATE of=fip-new.bin bs=512 skip=1313 count=5032`，
   校验长度/哈希。写前再读前 16MiB，要求与新备份一致。
   只执行 `sudo dd if=fip-new.bin of=/dev/mmcblk0 bs=512 seek=1313 count=5032 conv=notrunc,fsync`。
   随即读回完整前 16MiB，逐字节验证等于“新备份仅替换 `[672256:3248640]`”的期望值；
   FIP 哈希匹配候选，区间外完全不变。**核对失败不能重启**，立即按第 7 步恢复。
   不写整张 SD 镜像、不写整个 16MiB 备份、不改分区或 eMMC boot0/boot1。
4. 串口监视正常关机后，现场断开所有供电和 USB 回供，再按约定供电顺序接入 Mac USB-C。
   如需拔插 USB-C 重新协商，由现场人员操作，不能仅用远程热重启代替。
   验证固件版本、原始 Mac PDO `3e01912c`、RDO **`1304b12c`**、真实 Accept/PS_RDY，
   `/chosen/khadas,usb-pd-boot` 64 字节快照与内核/manager 展示一致。
   无 Source_Capabilities 的热启动不算合同验证；1.5A 电源应为 `13025896`，不可强求 3A。
5. 确认 UDC configured、one-kvm/manager active，运行
   `node tools/one-kvm-usb-check.mjs --exclusive --hid-only`（按现有工具方式注入登录环境）。
   必须观察实际 Mac 键盘、绝对/相对鼠标、点击和滚轮；任一失败立即回退，不继续带故障试验。
6. 冷启动后、再正常重启两次，各保存 boot ID、串口长度日志及以下只读输出：

   ```sh
   cat /proc/sys/kernel/random/boot_id
   sudo awk '$3 == "_text" || $3 == "_stext" { print }' /proc/kallsyms
   sudo dmesg | grep -E 'KASLR|random:|crng'
   sudo test ! -e /sys/firmware/devicetree/base/chosen/rng-seed
   ```

   要求内核随机化基址跨启动变化、无缺种子 KASLR 警告、每次均有成功交接日志、HID 正常。
   极低概率地址碰撞需追加重启核对，不能仅凭一次相同基址判定禁用。
   `rng-seed` 的证据是“固件写入成功＋7.3 drivers/of/fdt.c 调用
   add_bootloader_randomness 并 fdt_nop_property＋运行后已清除”；仅属性缺失不证明消费。
   CRNG ready 不能单独证明来源，更不能认证硬件熵质量。不打印、保存种子字节。
7. 任一关键验证失败，从**本次新备份**取 fip-before.bin，先核验当前 FIP 为本候选或已知
   写入失败状态，再用相同 seek/count/conv 参数写回。完整前缀读回必须与本次备份逐字节相同。
   重启并确认 pd-handoff、原内核 build ID、服务和实际 HID；持久 journal 配置保留。
   若 Linux 无法启动，拔 SD、断开全部供电，按住 FUNCTION 冷上电进入 OOWOW，
   从 Mac 的备份恢复同一 FIP 范围，
   不调用整盘重装或格式化。恢复通道须在写前准备好；本次现场已验证上述冷上电方式。

通过现场验收可保留合并固件，由用户记录最终部署决定。旧 `build/pd-handoff/board.py`
硬编码旧固件/旧应用基线，不能原样执行。本轮没有现场冷插拔、实际种子或固件 HID 结论。
