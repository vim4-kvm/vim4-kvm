# 2026-10-22：U-Boot 复位分析与 microSD A/B 候选

本轮未连接板子、串口或操作磁盘。现场失败和 OOWOW 恢复见
[合并候选补记](2026-10-22-p2-uboot-combined.md#现场失败与恢复补记)。根据用户补充的
USB-C 单线供电条件，**PD 合同后的协议空窗导致源端复位/VBUS 下跌是首要假设**，
但尚无 CC 抓包或电源波形证明。先验证 A；B 仅供有时间时二分，可能循环复位。
本轮不刷 eMMC、不更新部署锁；两个镜像都未经硬件验证。

## 支持证据与边界

| 核对对象 | 源码或已有记录所能证明的事实 |
|---|---|
| Linux `tools/usb-pd-init.c:main/serve` | Request 后运行 `serve(20)`；PS_RDY 只置完成标记，不退出。Get_Sink_Cap 回复 USB-capable Sink PDO；Soft_Reset 清 TX ID/完成标记并 Accept；新 Source_Capabilities 重新 Request；DR_Swap 等未支持控制消息 Reject；结构化 VDM 请求 NAK。检测到 Hard Reset 报错退出 |
| `board/vim4pd.py:decision/bootstrap` | 仅合法 v1、PS_RDY 完成、无超时/Type-C 回退/I/O 错误、有效 PDO 位置、RDO 缺 bit25 时修复一次。已有 USB comm 位、热启动无合同等情况跳过；失败不在同次开机重试 |
| U-Boot `drivers/power/mfd/fusb302.c` | transition_sink 收 PS_RDY 后 ready；init 立刻报告并 return。state_machine_typec 的 ready 和 Soft_Reset 状态仅打印，无 Sink_Capabilities/Accept。PHY 自动 GoodCRC 不等于完整响应 |
| 厂商对照 | `~/src/u-boot` 同样立即退出、ready/softreset 仅打印。厂商 5.15 `drivers/usb/typec/tcpm/fusb302.c:fusb302_pd_read_message` 按实际消息类型处理并交给 TCPM，注明 TX_SUCCESS/GCRCSENT 会乱序；不能把 U-Boot 简单轮询视为等价接管 |
| 现场时序 | d54877c9f5 同时包含此前未实板验证的 pd-request 与种子。PD 完成后最后输出 DTB size，随后重入 BL2，没有 seed 日志。恢复 pd-handoff 后相同 DTB 路径继续到 Linux |

源码缺口及 Linux/U-Boot 差异为**高置信**；实际 Hard Reset/VBUS 下跌为**中等置信、
优先验证**。没有证据证明该 Mac 必然在此时发送 DR_Swap/VDM/Get_Sink_Cap，也没有
测量“合同后数百毫秒”。原始日志同时有 3A/1.5A PDO；`3f019096` 电流字段为 1500mA，
符合用户降额解释，但不能排除源策略/连接状态等因素。旧 `1401912c` → 新 `1304b12c`
还改变 No USB Suspend、Capability Mismatch、工作电流；B 定位 pd-request 整组变更，
不能单独归因 bit25。Linux 仅服务 20 秒，7.3 没有持续 TCPM 接管，不能保证后续热插拔。
A 有效旧合同会触发 Linux 修复，热启动 flags=d0 应跳过；B 若到 Linux，已有 USB comm
也会跳过。不要手工反复启动 PD 工具掩盖失败。历史主机审查见
[协议空窗与乱序复现](2026-10-22-pd-warmboot-audit.md)。

新 RNG 在此次早期 DTB 窗口尚未执行，最后一行不等于故障指令。A 移植文件系统 DTB
直载/禁止 raw 回退，以及厂商 T7 READY/CFG/OUT0/ACK 握手修正；没有因此宣称复位已修复。
路径、其他假设和前轮负向测试见[补记](2026-10-22-p2-uboot-combined.md#离线修正边界)。
上一 `e92aba63ca` / 镜像 `1bb67c73…` 仍含 pd-request，本轮不拿它上板。

## A/B 分支、构建和测试

均基于 pd-handoff `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`，独立工作树/O=，
已推送 [U-Boot fork](https://github.com/vim4-kvm/u-boot)，原工作树未改。

| 项目 | A：首选 | B：可选二分 |
|---|---|---|
| 分支 | `vim4-kvm-2019.01-edge-sd-kaslr` | `vim4-kvm-2019.01-edge-sd-pd-request` |
| HEAD | `85e7ecad761549b21627001b1c1a2d87bf511655` | `c714efb2e37c2fcfdae0ca626374728792a33f8b` |
| 基线以上提交 | `5549b61ce7`、`5c1609f901`、`85e7ecad76`，移植 d1c2033/d54877c/e92aba6 | 原 `84ac4ecf33`、`c714efb2e3`，无额外改动 |
| 新种子/RNG/DTB 修正 | 有 | 无；仍有原厂 KASLR hook，不是新增种子实现 |
| PD | 驱动与 pd-handoff 逐字节一致；5V/3A 单 PDO 为 `1401912c` | 固定 5V，最多 3A；3A=`1304b12c`，1.5A=`13025896` |
| Mac 镜像 | `build/uboot-sd-ab/A/u-boot.bin.sd.bin.signed` | `build/uboot-sd-ab/B/u-boot.bin.sd.bin.signed` |
| 完整 SHA256 | `269ba56b7b8d638676f79ad9b106538b621e150096362e7d1bec74057b399274` | `c2594fa420157542bd736344b584cff71c7aefd8be935bc5b17ae4d50e8639a5` |

VM 工作树 `/home/deepdream/src/u-boot-sd-{kaslr,pd-request}`；独立输出在同名
`/home/deepdream/build/`，BL33Z/签名分别加 `-stub`/`-image`。
`build/uboot-sd-ab/build.sh` 持 heavy 锁，以 kvim4_defconfig、GCC12/aarch64、独立 BL33Z
及 vim4-repack.py --update-bl31 构建，有厂商告警。兼容参数沿用上一候选，见脚本。
完整镜像均 3248640 字节；stock round-trip、早期前缀、BL30/40/31/32 及非 BL33 区域
一致性审计通过，构建/审计日志在 `logs/uboot-sd-ab/`。

主机测试通过（同目录 host-tests.log、pd-risk-audit.log、linux-*-tests.log）：

- A：unchanged Request/PS_RDY/FDT；RNG 握手、三个超时、重试与分配失败清理；
  文件系统 DTB 成败及禁止 raw fallback。
- B：Fixed 5V/3A 上限/1.5A/无 PDO/旧选择清理，1023 个非零电流与 Linux 一致；PS_RDY/FDT。
- 重跑旧实际驱动 mock，复现无 Soft_Reset Accept、无 Get_Sink_Cap 回复和乱序吞包。
  A/B 的 init、state_machine_typec、transition_sink、IRQ 函数相同（protocol-audit.json）。
  Linux 请求边界及 bootstrap 10 项测试通过，含旧 RDO 修复一次、已有 USB comm/超时跳过。

## 共用现场准备（以下均未执行）

用户在板边、串口可用；按 A → 可选 B，整组持 Mac 双锁：

```sh
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock /bin/zsh
```

保存正常 eMMC pd-handoff/HID 基线与已有 FIP/前缀备份，不更换当前内核/应用。
A 保留旧 12V/6A 选压策略，现场仅用这台 **只提供 Fixed 5V PDO 的 Mac**，不要换多档
PD 充电器。B 保留 raw DTB 探测，SD 启动也不能保证固件不访问 eMMC：已知恢复日志
两副本无效时只读失败，其他布局可能触发副本修复写回；B 不用于日常运行。

diskN 必须经拔插核对、手工替换为专用 SD 整盘。以下清空 SD，不能选内盘或其他数据盘：

```sh
diskutil list external physical
diskutil info /dev/diskN
diskutil partitionDisk /dev/diskN MBRFormat "Free Space" gap 32768S "MS-DOS FAT32" VIM4BOOT R
diskutil list /dev/diskN
diskutil info /dev/diskNs1
```

确认 FAT 实际分区号为 1，Partition Offset ≥16777216 字节；不符合就停止调整。
未来锁内 `rsync -rL vim4:/boot/ /Volumes/VIM4BOOT/`，复制实际文件（FAT 不支持符号链接）。
核对正常板哈希，须有 `dtb/amlogic/kvim4.dtb`、kvim4n.dtb、edge/Image、edge/vim4.dtb
及 extlinux。FullKvm 保留显式 eMMC 根分区 PARTUUID，不依赖 mmcblk 编号；内核/模块匹配。
Linux 根目录仍在 eMMC，会正常写 journal/应用数据；本流程不刷 eMMC 固件。若任何数据
也不能写，需独立 SD rootfs，不能使用这里的 Linux 验证流程。

### A：写卡与验收

在仓库根目录、上述锁内执行；核对 SHA 后写 SD，保留 bytes 442–511 磁盘身份/MBR：

```sh
export CANDIDATE="$PWD/build/uboot-sd-ab/A/u-boot.bin.sd.bin.signed"
export READBACK="$PWD/build/uboot-sd-ab/A"
shasum -a 256 "$CANDIDATE" # 必须等于 A 完整 SHA256
diskutil unmountDisk /dev/diskN
sudo dd if=/dev/rdiskN of="$READBACK/sd-mbr-before.bin" bs=512 count=1
sudo dd if="$CANDIDATE" of=/dev/rdiskN bs=1 count=442 conv=notrunc
sudo dd if="$CANDIDATE" of=/dev/rdiskN bs=512 skip=1 seek=1 count=6344 conv=notrunc
sync
sudo dd if=/dev/rdiskN of="$READBACK/sd-prefix-readback.bin" bs=512 count=6345
```

立即运行共用读回校验再 eject。镜像已含 sector 0，不额外整体 seek=1。
SD/eMMC 偏移一致：BL2=0x200，FIP=0xa4200（sector 1313），镜像末端 0x319200
（sector 6345，不含）。空卡须写完整早期阶段，不能只写 FIP。

1. 断电插 SD、冷上电，串口持续按空格中断 autoboot。确认 `85e7ecad76` banner、
   `boot_source: sd`、文件系统 DTB 成功。缺 extlinux 不会阻止默认回退扫描 eMMC。
2. 先在 RAM 检查种子，再进入 FullKvm；不执行 saveenv、mmc write、store/write 或烧录脚本：

   ```text
   load mmc 0:1 ${fdt_addr_r} edge/vim4.dtb
   fdt addr ${fdt_addr_r}
   fdt resize 0x1000
   fdt boardsetup
   run bootcmd_mmc0
   ```

   应见 `entering T7 RNG handoff` 和 `kaslr-seed=8 rng-seed=32 bytes` 成功日志。
   不打印 /chosen 种子；停在 entering 才进入 RNG 故障窗口，失败即停止。
3. 固件有效 3A 合同应为旧 `1401912c`；Linux `journalctl -b -u vim4-kvm-pd` 应见
   `PD bootstrap repair`、Request `1304b12c`（1.5A 为 `13025896`）、bootstrap complete。
   管理器区分 Linux 合同和固件快照；缺失/超时只会 skip，不算冷启动修复通过。
4. 检查 one-kvm、vim4-manager、gadget/PD 服务、UDC configured；实际发送并在 Mac
   观察键盘、绝对/相对鼠标、点击/滚轮。只枚举不算 HID 通过；失效立即拔卡回退。
5. 保存冷启动及两次 `sudo systemctl reboot` 的 boot_id、root 读取的 `/proc/kallsyms`
   `_text/_stext` 和 dmesg；基址应变化，无 nokaslr/缺种子警告。rng-seed 用固件写入
   成功＋内核消费/清除路径＋运行后属性清除共同判断，不单凭属性缺失、不输出随机值。
   热启动 PD timeout/skip 不算新合同失败，但须确认 HID。
6. 通过后正常关机、断电拔 SD，确认恢复 eMMC pd-handoff/HID。A 若仍复位，先停止、保存
   串口，不强行继续 B；后续可用 CC/VBUS 仪器、独立供电区分协议与断电。

### B：可选写卡与二分

A 成功且用户有时间才做。关机拔卡接 Mac，重新确认设备号，沿用同一 FAT 内容：

```sh
export CANDIDATE="$PWD/build/uboot-sd-ab/B/u-boot.bin.sd.bin.signed"
export READBACK="$PWD/build/uboot-sd-ab/B"
shasum -a 256 "$CANDIDATE" # 必须等于 B 完整 SHA256
diskutil unmountDisk /dev/diskN
sudo dd if=/dev/rdiskN of="$READBACK/sd-mbr-before.bin" bs=512 count=1
sudo dd if="$CANDIDATE" of=/dev/rdiskN bs=1 count=442 conv=notrunc
sudo dd if="$CANDIDATE" of=/dev/rdiskN bs=512 skip=1 seek=1 count=6344 conv=notrunc
sync
sudo dd if=/dev/rdiskN of="$READBACK/sd-prefix-readback.bin" bs=512 count=6345
```

运行共用校验并 eject，冷启动捕获 `c714efb2e3` banner、SD 来源、PDO/RDO、PD 完成及
复位位置。首要假设下预期复现循环；出现一至两次就断电拔卡，不任其长时间循环。
未复现也不排除 PD：SD 时序、Mac 合同历史/能力、供电条件可能不同。能到命令行则记录
后停止即可，不必进入 Linux/验证 KASLR。B 没有新的种子实现。
A 成功/B 失败支持 pd-request 相关性；A 还改变 DTB 路径，不是只变一个 USB comm 位的
实验。任何 B 结果都先拔卡回退，不留作正式固件。

### 共用读回校验与回退

紧接各自 dd 执行；校验失败停止、不能上电：

```sh
python3 - <<'PY'
import os
from pathlib import Path
image = Path(os.environ['CANDIDATE']).read_bytes()
root = Path(os.environ['READBACK'])
mbr = (root / 'sd-mbr-before.bin').read_bytes()
actual = (root / 'sd-prefix-readback.bin').read_bytes()
assert len(image) == 3248640 and len(mbr) == 512
assert actual == image[:442] + mbr[442:512] + image[512:]
print('SD prefix verified; MBR preserved')
PY
diskutil eject /dev/diskN
```

回退：**断电 → 拔 SD → 冷上电**，确认 eMMC `0d5a3d7848` 和实际 HID，不需刷回。
OOWOW：拔 SD、断开全部供电/回供、按住 FUNCTION 再冷上电。FUNCTION+RESET 依赖
U-Boot 到达按键检测，此故障下无效。本轮不刷 eMMC，正式采用 A 待现场结果另行决定。
