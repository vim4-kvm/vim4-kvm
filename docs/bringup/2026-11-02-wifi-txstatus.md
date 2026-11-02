# 2026-11-02：brcmfmac TX status、SDIO 回退与历史固件崩溃

摘要：`unexpected txstatus` 的直接条件是固件返回驱动未识别的四位状态值
（7–15）；旧日志没有值，不能确定具体原因或宣布 BCM43752 的良性行为。
厂商 bcmdhd 支持更多状态，存在协议覆盖差异，但尚无对应本次事件的最小修复证据。
SDIO 告警是**单次传输**回退 bounce buffer，仍使用 DMA，不是永久关闭 DMA。
历史 A/B 转储再次确认固件片内 AXI slave data abort；没有证据证明已经修复。
本轮纯离线，不改内核、不构建或部署模块，不占板（0 分钟）。

## 版本与原始证据

先运行 `tools/vm status`（含 fetch），再执行用户指定的
`tools/vm worktree new wifi-txstatus --from origin/vim4-kvm-7.3`：

- VM 分支 `wifi-txstatus`，路径 `/home/deepdream/src/linux-7.3-wifi-txstatus`，
  HEAD/start 均为 `f2e8424261af18690ee1fbf2c032365da9185568`，干净、无新增提交。
- 厂商 5.15 `/home/deepdream/src/linux`：
  `80a07ad5406d57855c996285ae75a50a1b9147ae`；其 common_drivers：
  `563cff9dab2c8cd44590bf57c8ffaa7e2dae35e1`。
  `.config` 为 `CONFIG_BCMDHD=m`、`CONFIG_BCMDHD_SDIO=y`、
  `CONFIG_BCMDHD_OOB=y`、`CONFIG_AMLOGIC_MMC_MESON_GX=m`。
- 使用主仓 `/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/logs/board-batch/`
  的 `wifi-evidence.tgz`（原始 dmesg、计数、iperf JSON、两份历史转储），
  未向板子读取任何状态。解包及复核结果留在本工作树忽略目录
  `logs/wifi-txstatus/`：`source-audit.txt`、`sdio-source.txt`、
  `upstream-audit.txt`、`dump-review.json`。RAM 不入库、不公开。

[上轮流量记录](2026-11-02-hdmirx-cor-lock-deploy.md#wi-fi)为当前硬件证据：
5GHz STA TCP 上传 600 秒，接收 254.308Mbit/s，61 次 TCP 重传；
60 个连接监测点全部 connected，RX dropped=57，TX errors/dropped=0。
重新数原始 before/after dmesg：txstatus 0→23，unaligned sg 0→1，
`no packet in hanger slot` 为 0；没有新增固件崩溃。
吞吐成功只证明该窗口有进展，不证明状态无害或每帧均成功。

## TX status 的确定触发条件

7.3 `drivers/net/wireless/broadcom/brcm80211/brcmfmac/fwsignal.c`：

1. `brcmf_fws_txstatus_indicate()` 从 TXSTATUS 或 COMP_TXSTATUS TLV 读取
   小端 status；`FLAGS_MASK=0x78000000`、shift=27，结果是四位值。
2. `brcmf_fws_txs_process()` 识别 0 DISCARD、1 CORE_SUPPRESS、
   2 FW_PS_SUPPRESS、3 FW_TOSSED、4 FW_DISCARD_NOACK、5 FW_SUPPRESS_ACKED、
   6 HOST_TOSSED；其余值才打印本次信息。因此这些日志不是普通 no-ACK（4），
   也不是缺少 hanger skb 的日志。内部 HOST_TOSSED 调用本身不会触发它。
3. 打印之后继续处理 compcnt 个 hanger 包；默认 remove=true，只有 1/2 才进入
   suppression 重排队。会递减 transit、按流控模式归还 credit，最后调用
   `brcmf_txfinalize(..., true)`。未知状态没有直接触发 reset、coredump 或停止队列。
   一条日志也不等于一个数据包，COMP_TXSTATUS 可以涵盖多个包。

旧日志既无 flags，也无原始 status/compcnt/hslot。可确定出现了未覆盖状态，
不能区分固件合法新增枚举、异常值或信令解析问题；不能从 23 条推算丢包率，
也不能直接归为主机内存破坏或固件 crash 前兆。

### 厂商驱动对照与上游

5.15 的 `drivers/net/wireless/bcmdhd/include/wlfc_proto.h` 使用同类四位状态，
定义 EXPIRED=6、DROPPED=7、MKTFREE=8、MAX_SUP_RETR=9、FORCED_EXPIRED=10。
`dhd_wlfc.c:_dhd_wlfc_compressed_txstatus_update()` 对 6/7 分别累计
`pkt_exptime/pkt_dropped`，其余非 suppression 状态继续完成包，
没有等价的 `unexpected txstatus` 默认打印。
因此即使相同固件返回 7，厂商日志也可能安静；无日志不能证明没有相同事件。
brcmfmac 的 6 是主机合成 HOST_TOSSED，与厂商 EXPIRED 数值重叠，
盲目追加枚举或把 6 当成固件 EXPIRED 会涉及 credit 行为，不能仅靠消除日志修补。

**没有找到 5.15 在同一 AP、相同 600 秒负载下的原始对照日志或 CPU 数据**；
本轮没有切内核补测。这里完成的是源码行为对照，不声称实测厂商吞吐更高或零异常。

本地完整 git 历史确认上游
`d843246ee7614828ac5ff1d58b21b1fce853044e`
（2020，`brcmfmac: update tx status flags to sync with firmware`）已经包含：
当时加入 4/5 并后移 HOST_TOSSED，解决状态错配和 credit 返回。
原邮件链接为 [linux-wireless 补丁](https://lore.kernel.org/r/20200610152106.175257-5-chi-hsien.lin@cypress.com)。
不能把已存在的修复再次作为本轮答案。本地后续 fwsignal 历史没有补齐 7–10；
网页搜索也没有找到能对应本板事件的、可核对内容的后续 linux-wireless 修复，
lore 页面直接访问失败。此为检索边界，不是证明整个上游不存在相关补丁。

另查阅 [Infineon v2025_0602 发布说明](https://community.infineon.com/gfawx74859/attachments/gfawx74859/WiFiBluetoothLinux/3493/4/Infineon_Linux_FMAC_Wi-Fi_Driver_release_notes_v2025_0602.pdf)：
第 9 页确有扫描期间 txstatus 错误修复，但属于 CYW55571/2/3 **固件**章节，
不含 BCM43752，不能据此宣称本板适用或已有主机补丁。

结论：直接机制已确认，最接近的源码证据是协议状态覆盖差异；
尚不能确定哪一个状态触发，更不能把 BCM43752 18.35.387.23.88 的行为定为已知良性。
没有达到用户要求的“确切驱动缺陷＋上游质量最小修复”门槛，保持代码与日志原样。

## SDIO：传输回退，不是永久降级

原始信息发生在 uptime 1106.950396：`unaligned sg len 112 blksize 256,
disabling descriptor DMA for transfer`。7.3 `drivers/mmc/host/meson-gx-mmc.c`
的 `meson_mmc_get_transfer_mode()` 对多块或 CMD53 检查每段 length 是否为
blksz 的整数倍；112 不能整除 256，因此当前 request 不设置
`SD_EMMC_DESC_CHAIN_MODE`。下一 request 会重新选择，不修改全局能力。

`meson_mmc_start_cmd()` 回退到连续 bounce buffer；写入先 `sg_copy_to_buffer()`，
再把 `bounce_dma_addr` 交给控制器；读取完成由 threaded IRQ
`sg_copy_from_buffer()` 拷回。代价是相应方向增加一次 CPU 内存复制及相关缓存流量，
可能影响吞吐/CPU；不是 PIO，也不是整个 Wi-Fi 会话从此关闭 DMA。
`dev_warn_once()` 只打印一次，不能据此断言只有一个 request 回退。
现有记录无回退次数、字节数或 CPU 对照，不能量化损失；254Mbit/s 是含此路径的
实际结果，不是“关闭 DMA 前后”对照。

上游 `e085b51c74cc99334c290f7c67d039c95f788239`（2021，
`mmc: meson-gx: check for scatterlist size alignment in block mode`）明确解释
descriptor 长度以块为单位及 brcmfmac 的 SG 对齐约束；当前已包含。
[原邮件](https://lore.kernel.org/r/20201218075312.67338-1-lebed.dmitry@gmail.com)
与本地 commit/diff 相互对应。这是避免无效 CMD53 descriptor 的既有保护，
不能删除检查来消除告警。

5.15 `common_drivers/.../meson-gx-mmc.c` 是本板实际 DT compatible
`amlogic,meson-axg-mmc` 对应实现；其选择函数检查 8-byte offset，
没有相同的 SG length/block 对齐检查，CMD53 整体回退代码也被注释。
所以两边传输模式选择并不完全一致。
板级 DT 均为 4-bit、SDR50/104、200MHz 上限、non-removable、
cap-sdio-irq、keep-power-in-suspend；7.3 明确 supply/pwrseq，厂商供应配置有差异。
7.3 已含 `3ff620c8a862b50e9d1d869484e361b8161914bd` 的 T7 intf3 tuning，
厂商 DTS 也有 `use_intf3_tuning`。上限/采样策略相近不代表主机驱动配置逐项相同，
也不证明运行时实际时钟相同。当前证据不支持 SDIO 回退导致固件片内 AXI trap。

## 历史崩溃是否已经覆盖

从上轮 tgz 取出的 A/B bin/json 四个 SHA-256 逐项匹配
[10-22 分析](2026-10-22-wifi-coredump-analysis.md#样本缺口与取证范围)。
本轮用小端 u32 重新读取 RAM 尾指针、shared、trap、console ring：
两份长度均 1,310,720，shared=0x1f1714、flags=0x100401、assert 三字段全零，
ring=8192 bytes。binary 与 console 的 main_thread、TRAP 4、PC/LR/SP 相符：

| 样本 | PC / LR | DFSR / DFAR | AXI errlog address |
|---|---|---|---|
| A，05:03 保存 | 0x6e55c / 0x6e551 | 0x1c06 / 0 | 0x180013fc |
| B，06:13 保存 | 0x6e344 / 0x6e33b | 0x1008 / 0x180013fe | 0x180013fe |

支持固件片内 AXI slave data abort、疑似共同 PHY 间接访问路径；A 为异步写异常，
不能将 DFAR=0 解释为空指针。更细的反汇编与置信度沿用原记录，本轮未重新展开 ROM。
03:12/03:34 原两份仍不在该归档中，不把 A/B 冒充它们。

10-22 已审计版本 `d5fff4595899b` 到本轮 HEAD 的 brcmfmac 目录
`git diff --exit-code` 为零；最后一次该目录修改仍为
`8c79256b563167a116ec00a8f3f4684bbc54979a`。
discovery/scan、主接口 ARP/ND、TX credit、版本化 NDO 地址修复已经在当时审计范围，
它们处理已知兼容问题，不能作为 A/B 后来被覆盖的证明。
也没有证据将本轮 23 次未知 TX status 与固件启动后约 4 秒的历史 trap 关联。
结论仍是**无法离线确认首因或排除复现**，不能称已修复，也不能证明必然复现。

## 本轮交付与未解决项

仅增加分析记录、索引和 N03 边界说明；无内核改动，因此 checkpatch、
brcmfmac.ko 构建、vermagic/BTF 核对与部署收据不适用。
没有申请板票、没有下载方向或厂商 5.15 同负载测试；上板总时长 0 分钟。
重复现有吞吐窗口不能补回缺失状态值，本轮不占用 boot-space 的排队时间。

后续需要的最小证据是一次有界 STA 窗口内同时保存未知 flags、原始 status、
compcnt/hslot 和时间；优先沿用已有调试点，避免全量包日志或修改状态处理来掩盖事件。
需另测才可量化 bounce 回退比例与 CPU 代价、比较 5.15 同负载。
历史 crash 的精确 iovar/状态时序、匹配 ROM/符号、缺失转储及真实 P2P 仍未解决。
若再次崩溃，应先保全现有保存器的私有 dump 与身份/操作序列，不反复触发。

验证：`python3 -m unittest discover -s tests -p 'test_*.py'` 共 490 项，
通过（12 项跳过）；`git diff --check` 通过。日志见
`logs/wifi-txstatus/unittest.log`。跳过项不计为实测通过。
