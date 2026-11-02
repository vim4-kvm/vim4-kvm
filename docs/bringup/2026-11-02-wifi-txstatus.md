# 2026-11-02：Wi-Fi TX status、固件 AXI trap 复现与厂商对照

摘要：已部署只增加 TX status 数值和现成标识的日志模块；首次连接时固件在 iperf
启动前崩溃，未采到未知状态值，按规则没有再次激活 7.3 Wi-Fi。
新转储再次确认 main_thread 的片内 AXI 写异常，与历史 A 的地址/故障类型一致。
5.15 同 AP 完成上传 296.81、下载 418.87Mbit/s，各 600 秒。
旧 7.3 上传 254.31Mbit/s 仅为此次厂商上传的 85.68%，低于 95%；
跨轮结果不能充当本轮成功配对或精确归因。最终恢复默认 FullKvm，Wi-Fi 关闭。

## 版本、构建与部署

先 `tools/vm status`（含 fetch），再以用户指定命令创建 `wifi-txstatus` 工作树。
第一轮仅离线分析，主仓提交 `a2473003776d131326a37ed6342ea7cf29708a93`；
第二轮按协调者明确授权增加诊断日志、单模块持久部署及厂商对照。

- VM `/home/deepdream/src/linux-7.3-wifi-txstatus`，分支 `wifi-txstatus`。
  新提交 `0d0bdced8193be4169955ef21509a75d80bfd246`，直接父提交
  `f2e8424261af18690ee1fbf2c032365da9185568`，包含 COR 修复。未 push。
- 唯一源码变化：`fwsignal.c:brcmf_fws_txs_process()` 原错误日志改为
  `unexpected txstatus %u: hslot %u genbit %u seq %u count %u`，
  参数为 flags/hslot/genbit/seq/compcnt。无新计数器、机制或状态处理变化。
- 在 heavy 票下使用正式输出树
  `~/build/p0-1-uhd6-formal-f951e2d24d32/out`，构建 in-tree brcmfmac.ko。
  Image 源码仍为 `f951e2d24d32d5df0e701e7c355b3db4c91eaf74`，
  GNU build ID 仍为 `48106f6f9fb09b12d1eaf6a5fe91953dba53d9cb`。
  模块 `intree=Y`，vermagic=`7.3.0-vim4kvm-uhd6+ SMP preempt mod_unload aarch64`。
  保留 `.BTF`；vmlinux BTF SHA-256 仍为
  `34216585f80cfc7b55077bc0e27e51b2c153d0425cf04a5ccc99aba96224b8d0`。
- 初次modpost缺cfg80211/brcmutil符号：输出树Module.symvers不完整；后续遇到make
  依赖及重复导出检查，均保留失败日志。
  最终核对正式归档 Module.symvers 的锁定 SHA
  `d2fb843dbd5edd6f9d160e1f6876469b7b4bd1897381811cd1562764ce61f8b3`，
  过滤本次已经作为对象输入的 vmlinux/brcmfmac，仅将其他模块符号通过 modpost `-i`
  输入，再执行in-tree `.ko`目标；未忽略符号检查、未改配置/BTF，vmlinux哈希不变。

安装采用[COR overlay](2026-11-02-hdmirx-cor-lock-deploy.md)相同登记方式：
备份 `/var/backups/vim4-wifi-txstatus-0d0bdced8193`，仅替换 brcmfmac.ko.xz，depmod；
更新 `/boot/edge/manifest.json`、两个 r14e manifest、kernels.json、runtime-build.json
的模块/文件哈希和 loaded ID。所有 `module_overlays` 保留 t7_hdmirx 并增加 brcmfmac。
FullKvm 没有 INITRD，不生成 initramfs。正式归档、历史完整包清单保持原样。
主仓 `sources.toml` 的 kernel pin/tree 更新到新提交，COR 条目不变。
已有 `test_uhd5_lock.py` 要求 pin 属于 overlay revisions，且逐项验证收据，已支持两个
overlay，无需改测试或虚构离线祖先验证。

部署收据与模块 SHA、build ID、最终登记文件哈希见
[uhd6-brcmfmac-txstatus-deployment.json](../../packaging/kernel-edge/uhd6-brcmfmac-txstatus-deployment.json)。
模块 build ID=`da667c427b389418706c4de5107745a46531ac42`；xz SHA-256=
`a13c7461bddba2b18014d714f0d0790504c7468617d723a1346cae5b151d5d74`。
重启及最终恢复均从 `/sys/module/*/notes/.note.gnu.build-id` 核对 brcmfmac 和 COR；
后者仍为 `9b08acc2f8ce6ec746a59a4af4bf37565c8ed25d`。

## TX status 与 SDIO 的离线结论

7.3 `brcmf_fws_txstatus_indicate()` 读取 TXSTATUS/COMP_TXSTATUS TLV；
`FLAGS_MASK=0x78000000`、shift=27。处理器只识别 0–6：DISCARD、CORE_SUPPRESS、
FW_PS_SUPPRESS、FW_TOSSED、FW_DISCARD_NOACK、FW_SUPPRESS_ACKED、HOST_TOSSED。
因此错误日志确定表示 7–15 的未覆盖值，不是正常 no-ACK（4）或 hanger 缺包日志。
打印后仍按 compcnt 完成 hanger/credit 处理；仅 1/2 进入 suppression 重排队，
未知状态不直接 reset。一次压缩状态可能覆盖多个包，不能由日志条数推算丢包数。

厂商 5.15 基线 `80a07ad5406d57855c996285ae75a50a1b9147ae` 的 bcmdhd
`include/wlfc_proto.h` 定义 EXPIRED=6、DROPPED=7、MKTFREE=8、MAX_SUP_RETR=9、
FORCED_EXPIRED=10；`dhd_wlfc.c:_dhd_wlfc_compressed_txstatus_update()` 对 6/7
累计到期/丢弃计数，非 suppression 状态继续完成，没有对应的默认错误打印。
brcmfmac 的合成 HOST_TOSSED=6 与厂商 EXPIRED 数值重叠，盲目追加枚举会涉及 credit
语义。协议覆盖差异已确认，但缺实际 flags 不能选定具体语义或宣称 BCM43752 良性。

上游 `d843246ee7614828ac5ff1d58b21b1fce853044e`（状态同步及credit修复）已包含，
见[原邮件](https://lore.kernel.org/r/20200610152106.175257-5-chi-hsien.lin@cypress.com)。
未找到对应本板事件的后续最小修复；lore直接访问失败，不证明上游不存在。

SDIO 原告警 `unaligned sg len 112 blksize 256` 是 `meson_mmc_get_transfer_mode()`
对当前 request 不设置 descriptor chain 标记，下一 request 重新判断，不是永久关闭 DMA。
`meson_mmc_start_cmd()` 使用连续 bounce DMA，写前 `sg_copy_to_buffer()`、读后
`sg_copy_from_buffer()`，增加相应方向一次 CPU 复制。`dev_warn_once()` 不能给出回退次数。
无回退字节/次数及 CPU 对照，不能量化其吞吐损失。
上游 `e085b51c74cc99334c290f7c67d039c95f788239` 已加入长度对齐保护，
见[原邮件](https://lore.kernel.org/r/20201218075312.67338-1-lebed.dmitry@gmail.com)，不能删除检查消除日志。

厂商 common_drivers `563cff9dab2c8cd44590bf57c8ffaa7e2dae35e1` 的实际主机实现
`meson-gx-mmc.c`只检查8-byte SG offset，没有相同length检查。
两边DT均4-bit、SDR50/104、200MHz上限，供电/主机实现不完全相同；7.3已含T7
intf3 tuning，厂商也有`use_intf3_tuning`，静态上限不证明运行时实际时钟相同。

## 新固件崩溃：停止 7.3 重试

首次部署重启后 boot ID=`1fb7959f-15b6-4c18-ac74-a9983fcfa3bb`。
连接流程仍为 radio on → 已有 helper wifi-activate UUID
`974bbec1-7e28-4f64-91b4-674c72bc37e9`，未改 AP/密码。
uptime 41.109942 出现 SG 回退，41.755302 固件 halted/crashed，42.393684 card removed。
连接 helper 失败，wlan0 消失，**iperf 未启动，未知 txstatus 日志为 0，分布为空**。
这不是零异常通过；没有状态值可对照 bcmdhd。按“崩溃不重复触发”停止 7.3 激活。

保存器留下 `wifi-1793593473273177429-devcd1.bin/.json`，本地与最终板上 SHA 一致：

```text
bin  e5e846bf41601e25010c865af24afb66630271a8df00fbb8335d4a5dd860e367
json 92c4e584544f4326b9a6faef7bb4af81e21c3194978a5956ccfcb2f66ae3e419
```

重新解析：RAM 长 1,310,720，shared=0x1f1714、flags=0x100401，assert 三字段为零；
console ring=8192，固件时刻 37.167 秒，main_thread run cnt=415，TRAP 4。
PC=0x193200、LR=0x5aabf、SP=0x2afc30；DFSR=0x1c06、DFAR=0；
AXI errlog address=0x180013fc、flags=0x01111200、status=1。
这与[历史 A](2026-10-22-wifi-coredump-analysis.md)的地址及异步外部写异常一致，
支持同类固件/疑似 PHY 间接访问路径故障仍会发生；PC 不同，不宣称相同精确调用链。
DFAR=0 不能判为空指针，也不能仅凭相邻 SG 回退确定因果。
固件 SHA 仍为 `af7310c6c44da2690ea9f666eea8477a48e906810a1246a5fa207d3788fdf309`。

旧 A/B 从上轮 tgz 保全，四个 bin/json 哈希均匹配 10-22 记录；新崩溃使板上 RETAIN=2
轮换掉 A，本地旧 A/B 未丢失。03:12/03:34 原两份仍缺失。
原审计 `d5fff4595899b` 到父提交 f2e8424 的 brcmfmac diff 为零，新提交也只改日志；
不能再写成“可能已被后续代码覆盖”。兼容性修复未阻止本次故障，精确主机命令仍未知。

## 5.15 同负载结果与 95% 判定

通过 manager helper `kernel-select vendor true` 正常重启 Default，运行
`5.15.137-vim4kvm-hdrdual6`，固件仍为18.35.387.23.88 / 01-16e134aa。Mac `192.168.50.239:5209`，板 wlan0
`192.168.50.156`，5GHz 保存连接，eth0 始终管理通道。与上轮相同单 TCP、600 秒：
`iperf3 -c ... -B 192.168.50.156 --bind-dev wlan0 -t 600 -i 10 -J`，下载加 `-R`。

| 内核/轮次 | 方向 | 接收 Mbit/s | TCP 重传 | 完成情况 |
|---|---|---:|---:|---|
| 7.3 原模块，上轮 | 上传 | 254.308 | 61 | 600秒；23条未知状态，无崩溃 |
| 7.3 日志 overlay，本轮 | 上传/下载 | 无结果 | 无结果 | 连接阶段崩溃，未重试 |
| 5.15，本轮 | 上传 | 296.810 | 207 | 接收600.078秒；60个监测点全部connected |
| 5.15，本轮 | 下载 | 418.868 | 2631 | 接收600.007秒；59个监测点全部connected |

厂商上传/下载 RX dropped 增量分别 60/51，TX errors/dropped 均无增长；
两段 IPv4/IPv6 路由均恢复原值。无新增固件 halted、txstatus 或内核 WARN；
每段启停区间各 19 条带 ERROR 标签日志，含 6GHz bw_cap -13、P2P discovery -16
及其清理错误，不能称零驱动告警。启动阶段另有厂商 DRM vblank WARN，未计为网络流量新增。

**vendor parity 未通过/未证明**：旧上传÷本轮厂商上传=85.68%，低于95%；
本轮7.3又没有成功样本，不能验收当前overlay的双向95%。无线环境不是受控射频实验，
不能把差额全部归为SDIO bounce、TX status或单个驱动改动。

## 窗口、恢复与验证

全部访问经 `tools/board-queue run --who wifi-txstatus`，构建只持 heavy。
共享 history 的实际板票如下（失败立即释放后离线修正脚本，没有占板编辑）：

| 票 | 秒 | 结果 |
|---|---:|---|
| 450 | 43.235 | 安装/重启身份通过；测试脚本在/tmp被重启清掉，未启动流量 |
| 451 | 4.954 | 首次激活即固件崩溃，保全dump；接口消失打断初版清理，随后452补关无线 |
| 452 | 0.833 | 无线关闭、journal/身份取证；未重试连接 |
| 453 | 57.360 | 启动5.15通过；厂商启动已自动开无线，前置断言停止，未跑流量 |
| 454 | 1.651 | 非root radio off权限拒绝，释放后改用既有sudo授权 |
| 455 | 1269.988 | 厂商双向600秒、关闭无线、正常重启恢复FullKvm |
| 456 | 5.664 | 最终登记、模块和boot artifact核验 |

合计1383.686秒（23.06分钟），最长单票21.17分钟，全部已释放。
失败450遗留的本机一次性iperf listener已终止，未将失败结果混入成功样本。
最终 boot ID=`0d3820b3-aa5a-4712-923b-02b856b2209e`，FullKvm 默认，
内核/两个模块身份通过，所有登记boot artifact严格哈希通过，四项服务active、UDC configured。
Wi-Fi disabled，IPv4管理路由仅eth0。7.3 taint=4096（O，外部GPU模块），不是零taint；
5.15为12800，包含厂商启动WARN及外部模块标记。未测音频、未发HID、未读debugfs/regmap。

原始证据留本工作树忽略目录 `logs/wifi-txstatus/`：`build-module*.log`、
`checkpatch-final.log`、`installed.json`、`mainline*-window.log`、`mainline-run-dumps.tgz`、
`new-crash-summary.json`、`vendor-traffic-window-r2.log`、`vendor-*-server.json`、
`vendor-upload-r2.tgz`、`vendor-download.tgz`、`final-proof.json`及串口日志。
旧证据来自主仓 `logs/board-batch/wifi-evidence.tgz`；RAM及原始厂商日志私有，不入库。

checkpatch零错误/警告；主仓全量unittest 490项、12项跳过，其余通过，diff检查通过。
日志格式改动不另加镜像实现的测试；多overlay合同由现有锁测试覆盖。
需要继续修复/取证的结论：固件崩溃仍存在，应继续定位精确触发命令/状态时序；
实际txstatus值仍缺，不能选定状态语义或行为补丁；吞吐尚未达到95%验收。
本轮到此停止，不实现额外修复、不重复触发崩溃、不推送。
