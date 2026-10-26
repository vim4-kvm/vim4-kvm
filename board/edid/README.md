# 自定义 EDID

`rtk-uhd-hdr.bin` 是从用户连接的 RTK UHD HDR 物理显示器读取的完整
256 字节 EDID，未经字段修改。SHA256：
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。

2026-10-15，在 Mac M4、macOS 27.0.1 上，经 VIM4 输入两次验证 Apple
Screen Sharing 高性能会话退出后自动恢复；实际协商为 4K60 YUV444 8bit。
没有验证该表声明的全部模式、HDR 或所有主机。它是可复现的自定义配置，
不是已替换的系统默认预设。对照记录见 [上板记录](../../docs/bringup/2026-10-15-screen-sharing-desktop-not-restored.md)。

板级助手 vim4-edid 内置同一张表作为 `RTK-CONTROL` 预设，NanoKVM、One-KVM
与 JetKVM 菜单中显示为 RTK UHD HDR 4K60；vim4-manager 仍用本文件的安装副本。
`apply RTK-CONTROL` 只接受与内置表一致的数据。

加载并保存到板级配置（会重新协商 HDMI）：

```sh
ssh vim4 'sudo -n /usr/libexec/vim4-edid preset RTK-CONTROL'
```

恢复厂商默认表：

```sh
ssh vim4 'sudo -n /usr/libexec/vim4-edid preset VIM4-4K60'
```

NanoKVM 使用板级共享 EDID 配置；One-KVM 通过同一助手修改它，PiKVM
沿用板级输入。JetKVM 有独立保存的 EDID，启动时会加载，不能仅写板级
配置就假设四套应用切换后都保持同一张表。

当前开发板的 JetKVM 独立配置也已同步此表：
`/var/lib/jetkvm/config.json` 的 `hdmi_edid_string` 为本文件的十六进制内容。
这属于该板保存的自定义配置；没有修改 JetKVM 内置默认预设。同步时 JetKVM
处于停止状态，先备份配置再原子替换，只改该字段；不要覆盖运行中应用的配置。
JetKVM 的 edid-apply 助手返回 loaded=false，确认与当前接收端加载的表一致。
应用切换与重启的后续验收见 [双内核集成](../../docs/bringup/2026-10-21-dual-kernel-integration.md)。

## 1080p60 SDR 8-bit

`1080p60-sdr8.bin` derives from the existing Khadas Ubuntu
`/etc/tvconfig/hdmi/port1_14.bin`. Only the HDMI VSDB deep-colour flags at
offset `0xb2` are cleared (`0xb8` → `0x80`), then the CTA block checksum is
recomputed (`0x84` → `0xbc`). Timings, LPCM audio and other capabilities remain.

The vendor table makes the test Mac transmit 1080p60 YUV444 10-bit at
185.625 MHz, which the current mainline receiver does not support. This separate
named preset advertises the supported 8-bit path without rewriting the vendor
table or uploaded EDIDs. Both kernels can use it; the original preset remains.

## RTK 4K60 + 1080p120（实验）

`rtk-uhd-hdr-1080p120.bin` 基于上面的 RTK 原表，预设标识为 `RTK-1080P120`。
原表没有 CTA VIC 63/64（1080p120/100），垂直扫描范围上限为 61Hz。
派生表在原有两个保留 SVD 槽位 `0x8c/0x8d` 写入 63/64，将 `0x72` 的垂直范围
上限改为 120，再重算 `0x7f/0xff` 校验和；总共改动 5 字节。原有 SVD 索引不移动，
避免改变 Y420 capability map 的对应关系。首选模式仍为 4K60，1080p60/1440p60 DTD、
音频、HDR、深色及厂商数据块保留；FreeSync 范围仍是 40–61Hz，不声明 120Hz VRR。
SHA256：`75c822f7e6c747dc9f8bbe235e9e9fd49a2a7a318810a7d4f9525eb6c1491d07`。

这只是输入能力声明，需要配套 RX 高刷格式映射与应用编码上限。首次实板验收从
SDR 8-bit 开始；增加声明不等于已经验证 HDR120、远程120帧或本地 HDMI OUT120。
原表内的其他保留 VIC/能力声明沿用，不能把校验和正确当作整表协议符合性证明。
加载后需在源端主动选择 1920×1080 120Hz；完整验收步骤见
[1080p120 审查](../../docs/1080p120-audit.md)。该表已用于[1080p120实板验收](../../docs/bringup/2026-10-26-1080p120.md)，测后恢复原RTK表。

## VRR EDID 离线候选

`tools/vrr-edid.py` 可按显式范围生成单独候选，不覆盖原表、不写接收端。
远程模式不依赖OUT；本地模式要求显示器EDID，并取同协议的接收/请求/显示器范围交集。
原RTK只有AMD FreeSync 40–61Hz，不能当作HDMI Forum VRR显示器。
此工具没有建立硬件资格或新增可用的VRR预设，使用方法与待验边界见
[VRR离线准备](../../docs/vrr-preparation.md)。
