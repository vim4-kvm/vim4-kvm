# 2026-10-22：BCM43752 固件转储离线分析

摘要：指定的 03:12、03:34 转储已缺失，无法对比或确认根因。现存 **05:03、06:13 是
不同事故**，均确认 main_thread 片内 AXI slave data abort，有共同 RAM 调用路径。
最可能是 PHY 访问与芯片状态切换不协调；具体主机命令、时钟／电源条件未证实，不能归为
已修复的 P2P NDO 问题，也不能仅凭 -52 判为 SDIO 故障。

## 样本缺口与取证范围

背景：[首次 Wi-Fi](2026-10-20-edge-wifi.md)、[诊断能力](2026-10-21-edge-wifi-fps.md)、
[P2P 适配](2026-10-21-edge-wifi-p2p.md)。文件名换算的 UTC 是**保存时间**；console 从固件启动计时。

| 文件名前缀（均有 `.bin/.json`） | 保存时间 | 本轮状态 |
|---|---|---|
| wifi-1792638752659498349-devcd2 | 03:12:32 | 缺失，只有历史目录清单 |
| wifi-1792640062242079322-devcd1 | 03:34:22 | 缺失，只有历史目录清单 |
| wifi-1792645433994688264-devcd1 | 05:03:53 | 已拷贝，下称 A |
| wifi-1792649614125034247-devcd1 | 06:13:34 | 已拷贝，下称 B |

`logs/wifi-p2p/ndo-final-audit.log:48–51` 仍列出原文件。
保存器 `save-wifi-coredump.py` 的 `RETAIN=2` 会删除旧 bin/json；现状与轮换一致，缺少删除审计。
板上 `/var/backups`（深度 4）、`/tmp`（深度 3）、`/home`、`/root`（深度 5）
及 VM `/home/deepdream` 均未找到原样本；不是全盘无备份证明。询问备份位置后尚未收到补充。

只读命令（主仓库执行，循环仅针对 A/B）：

```sh
ssh vim4 'sudo cat /var/lib/vim4-edge-wifi-dumps/wifi-1792638752659498349-devcd2.bin'
# cat: ...wifi-1792638752659498349-devcd2.bin: No such file or directory
mkdir -p build/wifi-dumps
chmod 700 build/wifi-dumps
for name in wifi-1792645433994688264-devcd1 wifi-1792649614125034247-devcd1; do
  for ext in bin json; do
    ssh vim4 "sudo cat /var/lib/vim4-edge-wifi-dumps/$name.$ext" > "build/wifi-dumps/$name.$ext"
    chmod 600 "build/wifi-dumps/$name.$ext"
    ssh vim4 "sudo sha256sum /var/lib/vim4-edge-wifi-dumps/$name.$ext"
    shasum -a 256 "build/wifi-dumps/$name.$ext"
  done
done
```

失败拷贝的本地空文件已删除。板端／本地 SHA-256 相同，bin 同时匹配 JSON；长度均 1,310,720：

```text
A.bin  184c2686ed98c8aa6de1f1b47ad06a90a44dc04016fc9b9beae99f60fe81dc0d
A.json 20b601a1e2ba0c48bd11dc023026f63f08a1ad647378accd2cf4ee5776a98030
B.bin  c69a1223bfbe974b88d34f291e91d48dc2084eb4fdf2a06a57ae9e755a869126
B.json 863283b90089dd963c082f816743bfe63f898966e164326b1acc7624e9fd281d
kernel = 7.3.0-rc7-vim4kvm-uhd1+
```

只读拷贝 `/lib/firmware/brcm/brcmfmac43752-sdio.bin`，SHA-256 为
`af7310c6c44da2690ea9f666eea8477a48e906810a1246a5fa207d3788fdf309`，与历史记录一致。
原始 RAM 可能含凭据，不入库、不公开。解析器、`analysis.json`、完整 console、
`board-sha256.txt`、`ram-call-sites.txt` 均留在忽略的 `build/wifi-dumps/`。

## 格式与解析方法

只读核对 VM `linux-7.3` 的 `d5fff4595899b`；其 brcmfmac 目录与部署基线
`51307a1cf3a60` 的 diff 为零。结构来源是该目录的 `chip.c`、`debug.c`、`sdio.c`：

- BCM43752 RAM 基址 `0x170000`，本样本长 `0x140000`，映射 `[0x170000,0x2b0000)`。
  `brcmf_dev_coredump()` 以 NULL/0 调用保存器，SDIO memdump 顺序读 RAM；这里不是 ELF，
  没有独立寄存器区。PSM watchdog 另一入口可以前置事件数据，不能通用地忽略该差别。
- 末尾 `u32`（文件偏移 `0x13fffc`）给出 shared 地址 `0x1f1714`。
  `sdpcm_shared_le` 前七个小端 u32 是 flags、trap、assert expression/file/line、console、msgtrace。
  两份 flags=`0x100401`：版本 1、TRAP 位有效，ASSERT_BUILT/ASSERT 位均未置位；
  三个 assert 字段全零。**没有可提取的 assert 文件／表达式**，不能编造断言根因。
- trap 按 `brcmf_trap_info` 解 type、epc、cpsr、spsr、r0–r14、pc 共 20 个小端 u32，
  与厂商 `bcmdhd/include/hnd_armtrap.h` 对应。
- console 地址 `0x239204`，其 +8/+12/+16 为 buffer/size/index；两份 buffer 均
  `0x2392bc`、size=`0x2000`。按 `ring[index:] + ring[:index]` 还原，去除空字节后各 56 行；
  二进制 trap 与 console 的 type/address/PC/LR/SP 逐项吻合。
- `python3 build/wifi-dumps/analyze.py` 验证长度、哈希、RAM 指针及 ring index。
  IDA MCP 返回 `Transport closed`，改用本地 Capstone Thumb 解码核对返回点。

`brcmf_sdio_dump_console()` 的 `CONSOLE_BUFFER_MAX=2024` 小于实际 8192，会返回
`-ENOMEM`；仅影响 forensics console，**不影响原始 RAM 转储**，不是固件 crash 原因。

## A/B 的直接证据

| 字段 | A（05:03） | B（06:13） |
|---|---|---|
| 固件版本 / FWID | 18.35.387.23.88 / 01-16e134aa | 相同 |
| console 异常时刻 | 000004.005 | 000003.897 |
| 线程 | main_thread，run cnt 409 | main_thread，run cnt 416 |
| trap 地址 / type | 0x2afba0 / 4 | 0x2afd78 / 4 |
| EPC=PC / LR | 0x6e55c / 0x6e551 | 0x6e344 / 0x6e33b |
| SP | 0x2afbf8 | 0x2afdd0 |
| r0 / r3 | 0x2434b4 / 0x18001000 | 相同 |
| DFSR / DFAR | 0x1c06 / 0 | 0x1008 / 0x180013fe |
| AXI errlog address | 0x180013fc | 0x180013fe |
| errlog flags / status | 0x01111200 / 1 | 0x00111100 / 1 |

两份 trap 前均打印 `AXI slave error`、`CoreID: 135`、errlog id=`0x00030003`。
不猜测 `135` 的 core 类型。SP 在栈内不排除栈破坏；`RO overwritten` 在 trap **之后**，不证明致错覆盖。

厂商 5.15 源码基线 `80a07ad5406d57855c996285ae75a50a1b9147ae` 中：

- `drivers/net/wireless/bcmdhd/include/aidmp.h` 定义 status 低两位 1 为 slave error，
  `AXI_ERRLOG_FLAGS_WRITE_REQ=(1<<24)`；A 为写，B 为读，和 DFSR 相互印证。
- 同内核 `drivers/net/wireless/broadcom/brcm80211/brcmsmac/d11.h:208–209` 定义
  `phyregaddr=0x3fc`、`phyregdata=0x3fe`。以 r3=`0x18001000` 为基址，地址恰好匹配。
  这是 PHY 间接访问端口的强线索；该旧 D11 头文件不等于完整的 BCM43752 专有寄存器手册。

按 [Arm Cortex-R4 TRM，表 4-27/4-28](https://documentation-service.arm.com/static/5f0358e8dbdee951c1cd6f3b)
解码 `FS=(DFSR&15)|((DFSR>>6)&16)`：A 为 `0x16`，异步外部写异常、AXI slave；
B 为 `0x08`，同步外部读异常、AXI slave。A 的 DFAR 不可用于定位，**DFAR=0 不证明空指针**；
异步异常 PC 也未必就是触发写的指令。B 的有效 DFAR 与 errlog 相同。

console 的共同尾部返回地址包括 `0x194ee1,0x194f47,0x198891,0x1ac203,0x1ade8d`。
不能把所有栈扫描值直接当成可靠展开栈，故额外检查相应 Thumb 调用点：

```text
0x194edc: bl 0x194d20  -> 返回 0x194ee0（栈中 Thumb 地址 0x194ee1）
0x194f42: bl 0x194ec4  -> 返回 0x194f46
0x1ac1fe: bl 0x198860  -> 返回 0x1ac202
B: 0x194d3c mov.w r1,#0x19e; 0x194d44 bl 0x6e32c
   栈中返回 0x194d49，与 trap r1=0x19e 相符
A: 栈中返回 0x194e39，对应 0x194e34 bl 0x64b1c
```

7 个 RAM 代码窗口在 A、B、原固件间逐字节一致，支持共同上层路径、不同访问点。
PC/LR 及部分目标低于 RAM 基址，属于未捕获的低地址代码（ROM 路径），**不能当作 bin
偏移反汇编**。缺匹配 ROM／符号，不能确认函数名、PHY 索引含义或触发 iovar。

## 与早期 P2P 故障的关系

JSON 缺少 boot ID、模块哈希、操作序列；相同 release 不能确定候选版本，原两份不能与 A/B 关联。
只读 `journalctl -k --since '2026-10-22 03:00:00' --until '2026-10-22 06:20:00'`
返回 `-- No entries --`，没有补齐时间关联。

历史证据支持以下判断：

1. `logs/wifi-p2p/go-command-trace-full.txt:39–50`：同一 multicast worker 依次发
   SET_VAR 长度 21、13，SET_PROMISC，再 SET_VAR 长度 11、10、9；最后一项从
   1765.740093 到 1768.440314 返回 -110，随后出现 -5。
   按 `_brcmf_set_multicast_list()` 路径，长度 11/10/9 分别匹配 `arp_ol/arpoe/ndoe`。
   **追踪未记录名称／ifidx**，NDO 归因需结合函数顺序及 P2P 记录，不能凭长度唯一认定，
   更不能自动绑定到缺失 dump。
2. 厂商 `bcmdhd/dhd_common.c` 的 `dhd_arp_offload_set/enable`、`dhd_ndo_enable`
   都用 ifidx=0；旧 GO worker 向组接口发全局开关，确有差异。现修复已转主接口，应保留。
3. P2P 修复在旧历史为 `bffaeb2948228`、`b784909fb1d7e`、`ffdadae5b3f85`，
   正式版对应 `5e9fca57a4e28`、`d8c75238124b2`、`8c79256b56316`。
   分别覆盖 discovery/scan v2/NDO、ARP/ND 与 TX credit、ND 地址协议。
   最终八轮无 trap 是有限测试窗口，不能据此消除后续故障。
4. `go-first.log:18–28` 中 `bus is down` 已先于 `wsec_key error (-5)`。
   `fwil.c` 在 bus down 直接返回 -EIO，而固件负返回统一映射 -EBADE（-52）。
   约 248s key/abort/接口失败和持续 escan -52 可为级联症状；约 732s 再加载只证明恢复，
   不足以定位首条致错命令。
   -16 可来自主机 vif event 占用保护，不证明固件索引非法。

## 结论置信度与后续方案

| 判断 | 置信度与边界 |
|---|---|
| A/B 固件发生片内 AXI slave data abort | 高：binary trap、console、DFSR、errlog 交叉一致 |
| A/B 属于同一类 PHY 寄存器访问路径异常 | 较高：端口偏移、共同返回点及相同代码；精确专有符号缺失 |
| PHY／MAC 时钟、电源或状态切换时序导致访问不合法 | 中等，最可能假设；没有崩溃前寄存器时序或主机命令证据 |
| 原两份由错误接口上的 NDO／并发组顺序触发 | 历史 NDO 事故有较强证据，但对指定两份的逐一归因未完成 |
| SDIO 电气／传输是首因 | 当前支持弱：RAM 完整可读、内部 AXI 有明确故障；仍不能排除共同供电等因素 |

可复现建议，**本轮未执行**：

1. 找回原两份；今后在恢复前保全 dump、boot ID、Image build ID、模块／固件哈希、原始
   fwerr、操作时间。提供有界私有研究归档，避免第三次事故覆盖第一份。
2. 后续独占窗口使用已有 `check-wifi-p2p.py --exclusive --cycles 4`，按已保存 SAE STA →
   discovery → 社会信道扫描 → 2 秒监听 → 5200/2412MHz GO 交替 → STA ping → 删除的步骤。
   记录各步时间和接口事件；真实 peer 协商另测。
3. 对 A/B 另设“启动／固件恢复后前 10 秒”的观察组，与 STA-only、仅 discovery、GO 启停
   分组比较。记录命令名称、ifidx/bsscfgidx、长度、fwerr 及 UP/DOWN/IF 事件，不记密钥或
   扫描 payload。缺少操作历史，不能给出 A/B 的确定复现配方。
4. 驱动候选：在出错／拆接口后抑制过期 multicast、ND、扫描工作；对生命周期转换做完整
   状态约束和失败回滚。`proto_block` 已串行化单条 dcmd，不解决跨命令时序；追踪确认后
   补延迟 IF 事件与恢复竞态的确定性离线回归。
5. 诊断候选：修正 forensics console 上限、验证指针和 index，覆盖 8192 字节 ring 及非法
   index；保存有界原始 fwerr 历史。它们只改善取证。固件替换、PHY 电源／时钟调整需厂商依据。

## 交付与未完成项

本轮仅新增本文及 README 索引，不提交、不推送。内核／应用只读，无代码分支、worktree、
提交或构建。原始样本和本地工具不入库。
未拿板锁、未重载固件／模块、未修改 Wi-Fi/P2P、未停启服务或重启；因此没有本任务的
“恢复后 build ID／manager active”证据，也不执行回退，以免干扰其他会话的音频窗口。

已验证 A/B 三方哈希、结构边界、console/trap 一致性及 7 个 RAM 代码窗口。
主仓库离线测试 159 项，154 通过、5 跳过。未完成原两份对比、ROM 符号化、首条命令与状态
转移因果验证、驱动修复和上板复现；不能宣布根因已全部定位。
