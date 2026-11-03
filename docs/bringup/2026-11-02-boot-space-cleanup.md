# 2026-11-02：/boot 无引用旧产物清理

经用户授权，只删除四个无引用旧文件；`/boot` 普通用户可用空间由
4,288,512 B（4.09 MiB）增至 **19,869,696 B（18.95 MiB）**。
释放分配块 15,581,184 B（14.86 MiB）。未重启，未改 extlinux.conf，未额外备份或写回退脚本。
前轮空间不足背景见 [COR 锁部署](2026-11-02-hdmirx-cor-lock-deploy.md)。

## 盘点与引用

`/boot` 为 `/dev/mmcblk0p1`，ext4，挂载参数
`rw,noatime,nodiratime,errors=remount-ro`。分区原始大小 251,658,240 B（240 MiB）；
statvfs 文件系统容量 219,004,928 B（208.86 MiB），块大小 4096 B。
清理前 `du -ax -B1` 合计 204,652,544 B，完整逐文件/目录大小、分配块、链接目标、
普通文件 SHA256 与引用关系离线保存在本 worktree 的 `logs/boot-space/`，不入库。

| 空间口径 | 清理前 B | 清理后 B |
|---|---:|---:|
| f_bavail，普通用户可用 | 4,288,512 | 19,869,696 |
| f_bfree，含 root 可使用的保留块 | 14,348,288 | 29,929,472 |

所有 extlinux LABEL 均已核对。表中路径相对 `/boot`，目录引用包括其子项：

| LABEL | LINUX | INITRD | FDT / FDTDIR |
|---|---|---|---|
| Default | vmlinuz-5.15.137-vim4kvm-hdrdual6 | initrd.img-5.15.137-vim4kvm-hdrdual6 | dtb-5.15.137-vim4kvm-hdrdual6/ |
| Stock | vmlinuz-5.15.137 | initrd.img-5.15.137 | dtb-5.15.137/ |
| HdmirxTest | edge/Image | 无 | edge/vim4.dtb |
| OneKvmTest | edge/Image | 无 | edge/vim4.dtb |
| FullKvm（保存的默认项） | edge/Image | 无 | edge/vim4.dtb |
| VendorVapb1 | vmlinuz-5.15.137-vim4kvm-vapb1 | initrd.img-5.15.137-vim4kvm-vapb1 | dtb-5.15.137-vim4kvm-vapb1/ |

- `/etc/vim4-kvm/kernels.json`：vendor/Default 1535 项，mainline/FullKvm 2356 项，
  包括启动文件和模块；完整 artifacts 原件保存在 inventory.json 的 texts 中。
  [vim4boot](../../board/vim4boot.py) 校验对应 LABEL 的全部 boot 字段及 artifacts 文件内容。
  vendor 的 boot artifacts 是 hdrdual6 Image、initrd、两个 DTB 与两个 overlay.env；
  mainline 的 boot artifacts 是 edge/Image、edge/vim4.dtb。全部保留。
- `/boot/edge/manifest.json` 的 files 使用包内相对名，不能当作板上绝对路径；
  [安装器](../../packaging/kernel/register-runtime.py) 映射七个文件到 edge/。
  `/opt/vim4-kvm/hdr10-r14e/manifest.json` 与 `/etc/vim4-kvm/hdr10-r14e.json`
  的 boot_files 均列出这七个绝对路径，全部保留，COR 模块 overlay 登记不变。
- 一次性 RAM 候选：盘点了 `/var/lib/vim4-kvm/ram-candidates/` 下 kbase、hdr10
  的 extlinux.conf、manifest/trial.json，包括 completed 目录中的记录。
  LINUX/FDT、APPEND 中 init 等候选文件位于根分区私有目录，
  [display-once](../../packaging/kernel/display-once.py) 使用
  `sysboot mmc 1:2 any ${pxefile_addr_r} <私有目录>/extlinux.conf; reset`，不消费被删四文件。
  baseline_files 中 `/boot` 保护路径也纳入引用表。未删除根分区候选或历史证明。
- 5.15 厂商链：保留 Image→hdrdual6、initrd.img→hdrdual6、dtb→hdrdual6、
  dtb.img→dtb/amlogic/kvim4n.dtb，及各 DTB 目录中通往共享 overlays 的链接和全部 overlay 文件。
  uEnv.txt 的 rootdev、console、fan 等变量不改。当前 /boot 中没有 uInitrd 或 boot.ini；
  没有据历史名称推断它们存在。menu background 的 splash.bmp 当前也不存在，此为既有状态。

## 删除与保守保留

分类规则：a 为任一启动项/登记/链接引用，保留；b 为已证明无引用的旧候选或配置备份，删除；
c 为未证明外部消费者的配套文件，保留。`classification.json`、`inventory.tsv` 逐路径给出分类和原因。
四个删除项均为普通文件，无启动项、登记、候选证明或符号链接引用：

| 删除路径 | 字节 | SHA256 |
|---|---:|---|
| /boot/config-5.15.137-vim4kvm-hdrdual5 | 225598 | 90871708fd4e063014aa1939ebc8b51d481d69f64df45a0faccd9a2e5f3ce7a4 |
| /boot/vmlinuz-5.15.137-vim4kvm-hdrdual5 | 15340944 | 3b2196e060175b670a3a849421aa2a0d8629a168e38749759b5c9062fbbbbe1c |
| /boot/extlinux/extlinux.conf.before-full-runtime | 2346 | 5ad66a9f5c30669ca9c34f98347928d7c89e56ae1068205b999835b4fdf5ee90 |
| /boot/extlinux/extlinux.conf.before-kernel-switch | 2822 | 0f34f14cbaaca91c802c59476ccb06bdba0d782e738f006be412df0e4bf22b73 |

逻辑大小合计 15,571,710 B；没有把符号链接目标当作重复文件删除。
vim4boot 的 before-kernel-switch 路径是选择器写入备份的位置，不是启动读取依赖。

保守保留的不确定项：`.dtb.tmp`（13 B，来源未证实）、
`hdmi-passthrough-vendor-20261024.conf`（可能用于人工厂商对照），
config-5.15.137、config-5.15.137-vim4kvm、config-5.15.137-vim4kvm-hdrdual6、
config-5.15.137-vim4kvm-vapb1（厂商/实验配套配置），以及所有 System.map 链接
（指向根分区备份或候选，删除链接几乎不释放空间，外部诊断消费者未证明）。
hdrdual5 DTB 目录及其两个 DTB/overlay 链接也保留：目录可被人工 U-Boot 指定，
本轮只确认登记链，不裁剪通用 DTB/overlay 资源。所有目录均保留。
Stock、hdrdual6、VendorVapb1 的 initrd 都有明确 LABEL 引用，不能称作无用旧 initrd。

## 校验与占板时间

两张票均经 `tools/board-queue run --who boot-space --purpose ... --max-min N -- SCRIPT`，
脚本在取票前写好，无人值守，使用免密 `sudo -n`，没有密码/heredoc 混用。
共享 queue history 的实际持票时间如下（不含排队）：

| 票号 | purpose | 上限 | 实际持票 |
|---|---|---|---:|
| 443 | readonly-inventory | 5 分钟 | 5.666 秒 |
| 444 | delete-unreferenced-and-validate | 15 分钟 | 4.990 秒 |

合计 10.655 秒。删除脚本先核对盘点时的全部 boot 文件与引用原件哈希，再执行：

```text
PRE vendor Default 1535 VALID
PRE mainline FullKvm 2356 VALID
PRE ALL_REGISTERED_BOOT_ARTIFACTS_VALID
POST vendor Default 1535 VALID
POST mainline FullKvm 2356 VALID
POST ALL_REGISTERED_BOOT_ARTIFACTS_VALID
ALL_RETAINED_BOOT_FILES_AND_REFERENCES_UNCHANGED; BOOT_ID_UNCHANGED
```

前后均实际调用板上 `vim4boot.validate_entry(entry, text, hashes=True)`，覆盖全部登记项。
删除后 sync，复验后再 sync；全部保留普通文件内容与链接目标、活动登记及 RAM 候选引用原件未变。
extlinux.conf SHA256 始终为 `3851bbbc149c7d218b5458d2c81769d1aeb4f5decad80abe434bcab6c86c9ef5`。
运行内核保持 `7.3.0-vim4kvm-uhd6+`，boot ID 保持
`e2c35bc3-8b5b-4b50-9239-2fb93153dfaa`。没有 Wi-Fi、音频、HID、debugfs/regmap 操作。
本轮未改变启动链所用文件，因此无需为此次删除重启验证，也未声称进行启动实测。

## 下一次整包空间预算

安装器 install() 写入 `/boot/edge` 的七个文件，按本轮实测体积估算：

| 文件 | 字节 |
|---|---:|
| Image | 48,347,648 |
| vim4.dtb | 49,637 |
| panfrost.dtb | 49,247 |
| config | 251,047 |
| Module.symvers | 1,334,218 |
| vmlinux.btf | 7,475,440 |
| manifest.json（含当前 overlay） | 507,647 |
| 合计 | 58,014,884（55.33 MiB） |

原正式 manifest 为 507,240 B，本轮用较大的已安装版本估算。
模块、runtime、整包解压临时目录均在根分区；安装器不生成 initramfs。
它用 shutil.copyfile 依次原地截断覆盖上述文件，没有在 boot 暂存第二套整包；
空间门禁为各文件 `max(0, 新大小−旧大小)+4096` 之和。
同体积重装门禁只需 28,672 B，现有 19,869,696 B 普通可用空间已经足够；
shutil.disk_usage 的 free 采用 f_bavail，不将 root 保留块算进安装器门禁。
后续构建须按新包真实大小重算正增长预算。

若要求完整并存第二套 boot 文件，按4096对齐并额外留每文件一块，预算约
58,060,800 B（55.37 MiB）；目前普通可用空间尚缺 38,191,104 B（36.42 MiB），
连同 root 保留块也不够。最小可行方式是沿用现有安装器原地覆盖 edge 的方式，
无需新 initrd 或并存副本；本轮未安装任何包。
另一个独立前置条件是 install() 要求保存默认项为 5.15，而当前是 FullKvm，
所以不能直接执行；下一次实际安装前需另行处理该前置条件，本轮遵守授权不改默认项。

原始证据：`inventory.json`、`inventory.tsv`、`references.json`、`classification.json`、
`delete-plan.json`、`cleanup.log`、两个 duration.json、`queue-history.json`，
以及 inventory/classify/cleanup 与 window 脚本均在 `logs/boot-space/`。

提交前主仓离线验证：`python3 -m unittest discover -s tests -p 'test_*.py'`
运行 490 项，478 通过、12 项环境跳过；`git diff --check` 通过。
