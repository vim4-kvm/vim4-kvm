# 2026-10-22：U-Boot 复位分析与 microSD 验证候选

本轮离线，未连接板子或操作物理磁盘。现场恢复见
[合并候选补记](2026-10-22-p2-uboot-combined.md#现场失败与恢复补记)。
可以确认故障早于种子 fixup；**不能仅凭最后一行串口确定复位的电气/EL3 原因**。
新镜像移除不适用的 Android DTB 探测，并修复独立的 RNG 握手缺陷；只准先做 SD 验证，
不能宣称现场复位已修复，eMMC pd-handoff 保留。

## 调用路径与排除证据

IDA ARM64 反编译与厂商源码相符；旧构建和 pd-handoff 配置相同，未改 DTB/MMC 初始化。

```text
board/khadas/kvim4/kvim4.c: board_late_init
  board/khadas/common/board.c: aml_board_late_init_front
    run common_dtb_load
      cmd/amlogic/imgread.c: do_image_read_dtb → do_image_read_dtb_from_rsv
        store_rsv_size → mmc_get_rsv_size（最后一条 size 日志）
        store_rsv_read → mmc_read_rsv → storage_rsv_range_check → dtb_read
          _dtb_init → dtb_read_shortcut → update_dtb_info
            _dtb_read → blk_dread（MMC/DMA）→ _verify_dtb_checksum
```

恢复日志出现 `_verify_dtb_checksum`、两个无效副本、`total valid 0`，随后 `imgread`
返回失败，加载文件系统 `dtb/amlogic/kvim4.dtb` 168682 字节。失败日志没有这些后续输出。
因此窗口位于 size 返回之后、首次校验输出之前，**最后一行不等于精确出错指令**。
正常日志也有 GPT/Android MPT 不存在的诊断，不能将其单独当成本次刷坏分区证据。

| 假设 | 证据及置信度 |
|---|---|
| 新 RNG MMIO、种子 FDT 写越界造成此次复位 | 高置信不在已观察窗口：新函数仅由 ft_board_setup 调用；后者在 `booti/bootm` 准备或显式 `fdt boardsetup` 执行，早期 `common_dtb_load` 不调用。d1c2033 的另一配置修改只影响 boot_jump_linux |
| 新 SMC/BL31 版本导致复位 | 高置信没有新增早期 SMC，也没有更换 BL31。正常、失败、新候选的 BL30/40/31/32 和 FIP 前代码逐字节相同。`secure_image_check` 在 raw read 成功返回后才可能调用；不能把尚未看到 DTB 校验的失败归到该 SMC |
| RNG 时钟/电源未开启 | 本次未到 RNG，不能解释此窗口。厂商 T7 U-Boot rand() 不做时钟操作；厂商 5.15 T7 RNG DTS 没有 core clock 项。没有据此猜寄存器或开关电源域 |
| 栈、对齐、MMC/DMA/内存破坏 | 仍可能，缺 FAR/ESR/ELR 和 DMA 状态；代码及重定位地址变化本身不证明越界 |
| 看门狗/EL3 异常复位 | 未定。日志已打印 `watchdog disable`，这是 board_init 的非安全 WDT；不能证明安全侧 WDT 状态。T7 reset_system 本身可用 WDT 复位，但没有调用证据。正常/失败 BL33Z 均有 reason=0x00，不能据此区分断电、看门狗或其他复位 |
| PD 完成后的 Hard Reset/VBUS 下跌 | 仍需排除。驱动 PS_RDY 后立即退出轮询，ready 状态没有完整控制消息处理；新 Request 可能改变源端后续交互。flags=41 不代表此后 VBUS 稳定；缺 CC/电源波形 |

BL31 为仓库提供的签名封装 blob，未提供匹配的可分析 ELF、源码或 EL3 异常记录；
不能虚构其异常处理/复位策略。相同 blob 的 SHA 为
`f5fc4e1eb3311c7bf315ce2a16005d1051fedc595bb2672c09da8bbf06b1c3e7`。
证据保存在 `logs/uboot-recovery/image-audit.json`、ida-dtb-path.json，原串口日志不改写。

## 修正与主机验证

VM worktree `/home/deepdream/src/u-boot-pd-kaslr-fix`，分支
`vim4-kvm-2019.01-edge-pd-kaslr-fix`，提交 `e92aba63ca12a6d1511a5392717aff5a8b102184`，
基于 d54877c9f5，原工作树不改，部署锁不变。

1. Linux VIM4 的 CONFIG_DTB_LOAD 直接从启动介质文件系统加载 DTB；通用 late-init
   失败回退及显式 `imgread dtb _aml_dtb` 均拒绝 raw reserved-DTB。
   厂商 `dtb_read()` 不只是读取：一个副本有效或时间戳不同时会调用 `_dtb_write()` 修复。
   Ubuntu MBR 布局没有 Android reserved 区，此探测没有必要，也不能允许将文件系统块
   当作待修复副本。改动去除现场最后到达的路径，是隔离/规避措施，非物理根因证明。
2. 按厂商 `arch/arm/mach-meson/t7/hw_rng.c` 补齐顺序：READY bit0 清零 → CFG bit0
   清零 → CFG bit31 启动/等待 → OUT0 → READY 写 1 ACK。各等待最多 10ms；原先
   d1c2033 直接照搬 Linux 握手，遗漏 READY 和 ACK。新增进入日志不打印随机值。
   软件超时不能挽救不返回的 MMIO 事务；真实硬件仍待 SD 验证。

三组测试均通过，`logs/uboot-recovery/host-tests.log`：

```text
PASS: Linux filesystem DTB selection, failed loads, no raw reserved-DTB access
PASS: T7 READY/CFG/OUT0/ACK order, all three timeouts, fresh seeds, retry and FDT rollback
PASS: Linux request_5v matches all 1023 nonzero source currents
PASS: USB Request, PS_RDY gate, raw PDO retention, hard reset, vendor/mainline FDT, no fixup I/O
```

将两个新测试中的实际被测函数替换为 d54877c9f5 旧函数，两者都按预期 SIGABRT：
旧 RNG 在 READY 前访问 CFG；旧 DTB fallback 进入注入的不可返回存储接口。
见 negative-tests.log。这证明测试能发现对应源码行为，不是主机复现了板子的复位机制。

## 签名镜像

heavy 锁覆盖独立 O= / BL33Z 构建及签名；GCC12 兼容参数不变，仍有厂商旧告警。
脚本 `build/uboot-recovery/build.sh`，日志 `logs/uboot-recovery/build.log`。

| 项目 | 值 |
|---|---|
| Mac 镜像 | `build/uboot-recovery/u-boot.bin.sd.bin.signed` |
| 完整大小 | 3248640 字节 |
| 完整 SHA256 | `1bb67c7345091f5e74cc280989c5b20e9ab5ec362cf00711ee75efb943ed870d` |
| FIP SHA256 | `57ca9a75b32870b481726224eb0c4c495b9d4a4bb774245b30f750e539a1ac5a` |
| 源码 tree | `d4a1c91abfa31ba890fa117ea94fec09d572f14f` |

stock round-trip 和三镜像对比确认仅 BL33/FIP 元数据变化。
源码分支推送至 `https://github.com/vim4-kvm/u-boot.git`；镜像留本机，不作为已验收发布。

## 下次现场：先 SD，后决定 eMMC

以下为**未执行的现场步骤**。准备可清空的专用 microSD、串口和冷上电恢复条件。
全窗口持 board/heavy 双锁，先保存当前 pd-handoff 前 16MiB/FIP、内核/应用及 HID 基线。

### Mac 写 SD（只写确认过的外置 SD 整盘）

1. `diskutil list external physical`，拔插核对容量/设备号。下列 `diskN` 必须手工替换为
   **专用 SD 整盘**，不能是 Mac 内置盘或任何 eMMC。分区步骤会清空该 SD。
   `diskutil` 的 Free Space 为引导前缀留洞；不要用通常从 1MiB 开始的 FAT 分区覆盖 FIP。

   ```sh
   diskutil info /dev/diskN
   diskutil partitionDisk /dev/diskN MBRFormat "Free Space" gap 32768S "MS-DOS FAT32" VIM4BOOT R
   diskutil list /dev/diskN
   diskutil info /dev/diskNs1
   ```

   确认实际 FAT 分区号为 1（否则停止调整方案）且 Partition Offset **至少 16777216 字节**。
   Free Space 会受平台对齐影响，以实际输出为准；不能跳过检查。使用 MBR，避免 GPT 头被引导镜像覆盖。
2. 在写引导前，复制当前正常 `/boot` 的实际文件到 SD，包括 `dtb/amlogic/kvim4.dtb`、
   `kvim4n.dtb`、edge/Image、edge/vim4.dtb 和 extlinux。可在未来锁内执行：
   `rsync -rL vim4:/boot/ /Volumes/VIM4BOOT/`，`-L` 解引用 FAT 不支持的符号链接。
   核对这些文件 SHA 与正常板一致。extlinux.conf 保留显式指向 **eMMC 根分区 PARTUUID**
   的 FullKvm 项；不要使用依赖 mmcblk 编号的 root 参数。实际当前内核和模块必须匹配。
3. 卸载 SD 并写镜像。镜像已包含 sector 0，不额外整体 seek=1。保留 SD 新建的
   bytes 442–511（磁盘身份/MBR 表），其余使用候选内容：

   ```sh
   CANDIDATE="$PWD/build/uboot-recovery/u-boot.bin.sd.bin.signed"
   shasum -a 256 "$CANDIDATE"  # 必须与上表一致
   diskutil unmountDisk /dev/diskN
   sudo dd if=/dev/rdiskN of=build/uboot-recovery/sd-mbr-before.bin bs=512 count=1
   sudo dd if="$CANDIDATE" of=/dev/rdiskN bs=1 count=442 conv=notrunc
   sudo dd if="$CANDIDATE" of=/dev/rdiskN bs=512 skip=1 seek=1 count=6344 conv=notrunc
   sync
   sudo dd if=/dev/rdiskN of=build/uboot-recovery/sd-prefix-readback.bin bs=512 count=6345
   python3 - <<'PY'
   from pathlib import Path
   root = Path('build/uboot-recovery')
   image = (root / 'u-boot.bin.sd.bin.signed').read_bytes()
   mbr = (root / 'sd-mbr-before.bin').read_bytes()
   actual = (root / 'sd-prefix-readback.bin').read_bytes()
   assert len(image) == 3248640 and len(mbr) == 512
   assert actual == image[:442] + mbr[442:512] + image[512:]
   print('SD prefix verified; MBR preserved')
   PY
   diskutil eject /dev/diskN
   ```

   校验失败停止。SD/eMMC 镜像偏移一致：BL2 从 `0x200`
   开始，FIP 从 `0xa4200`（sector 1313）到 `0x319200`（sector 6345，末端不含）。
   SD 需要完整早期阶段；**不能只把 FIP 写到空卡**。这些命令不涉及 eMMC。

### 验证与退出条件

1. 断电插 SD 冷启动，持续按串口空格中断 autoboot；核对 e92aba63ca 和 `boot_source: sd`。
   旧 banner/emmc 来源不计通过。观察直接加载 SD DTB并到提示符；缺 SD extlinux 不能
   阻止启动，默认扫描仍会回退到 eMMC。先只在 RAM 验证种子：

   ```text
   load mmc 0:1 ${fdt_addr_r} edge/vim4.dtb
   fdt addr ${fdt_addr_r}
   fdt resize 0x1000
   fdt boardsetup
   ```

   确认成功长度日志，不执行 `fdt print /chosen`（会泄露种子）。再用 `run bootcmd_mmc0`
   进入 SD extlinux 的 FullKvm 项做 Linux 回归。
   不执行 saveenv、store/write、mmc write、更新/烧录脚本或 OOWOW 整盘安装。
2. 若仍复位，停止重试，断电拔卡恢复 eMMC。保存末行和启动时间，后续需分开验证供电/PD
   和存储路径：同候选、相同线缆，比较可靠独立供电与 USB 单线；有仪器时记录 VBUS/CC。
   无波形不能据最后一行断定存储故障或排除 PD。
3. SD 启动 Linux 时，内核/DTB 来自 SD，根文件系统仍是 eMMC；这不是刷 eMMC 固件，
   但 Linux 持久 journal/应用会正常写数据。若要求 eMMC **任何数据都不能写**，本流程
   只能停在 U-Boot 命令行；完整 Linux/HID 验收需另外准备独立 SD rootfs。
4. 冷启动检查 PD Accept/PS_RDY 对应快照：5V/3A RDO=1304b12c，5V/1.5A=13025896，
   不要求 PDO 必须带某一固定能力位。检查服务、UDC，并运行现有 actual HID 夹具观察键盘、
   绝对/相对鼠标、点击/滚轮；只枚举成功不算 HID 通过。出现任何 HID 失效立即断电拔卡。
5. 保存冷启动及两次正常重启的 boot_id、`/proc/kallsyms` 的 `_text/_stext`、dmesg。
   串口应先有 `entering T7 RNG handoff`，再有成功长度日志；若停在进入日志，才进入
   RNG/MMIO 故障窗口。三次基址应变化，无缺种子 KASLR 警告；rng-seed 的证据必须是
   固件成功写入＋Linux 消费/清除路径＋运行后已清除，不能只看属性缺失。不打印种子。
6. 全部通过后正常关机、断电拔 SD，再确认正常 eMMC pd-handoff/HID。
   **只有 SD 验证通过才考虑写 eMMC**：重新备份、核验哈希，只替换 FIP 的 5032 sectors，
   按[历史范围写入及回退步骤](2026-10-22-p2-uboot-combined.md#历史-emmc-刷写流程仅-sd-验证通过后参考)
   完整读回核对；不得重新使用失败的 6a25037a… 镜像。

SD 阶段的回退就是断电拔卡，不需要刷任何内容。若 eMMC 已更新后不能启动，拔 SD、
断开全部供电/回供、按住 FUNCTION 冷上电进入 OOWOW，仅恢复新备份的 FIP 范围并逐字节核对。
本轮不提供已验证修复结论，也不修改已部署 U-Boot 锁。
