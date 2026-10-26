# 自定义 EDID

`rtk-uhd-hdr.bin` 是从用户连接的 RTK UHD HDR 物理显示器读取的完整
256 字节 EDID，未经字段修改。SHA256：
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。

2026-10-15，在 Mac M4、macOS 27.0.1 上，经 VIM4 输入两次验证 Apple
Screen Sharing 高性能会话退出后自动恢复；实际协商为 4K60 YUV444 8bit。
没有验证该表声明的全部模式、HDR 或所有主机。它是可复现的自定义配置，
不是已替换的系统默认预设。对照记录见 [上板记录](../../docs/bringup/2026-10-15-screen-sharing-desktop-not-restored.md)。

本文件保留原始物理表作离线回退。当前板级助手、管理面板、NanoKVM、One-KVM
与JetKVM的「RTK UHD HDR」（`RTK-CONTROL`）统一使用下文合并后的高刷/VRR表。
`apply RTK-CONTROL` 只接受与当前内置表一致的数据；回退原始文件需用自定义名称上传。

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

管理面板应用RTK预设时，同步JetKVM的 `hdmi_edid_string`，只改该字段并保留其他设置；
运行中的JetKVM先停止再保存。JetKVM内置RTK项使用同一张合并表，厂商默认项不变。
历史原表的应用切换与重启验收见 [双内核集成](../../docs/bringup/2026-10-21-dual-kernel-integration.md)。

## 1080p60 SDR 8-bit

`1080p60-sdr8.bin` derives from the existing Khadas Ubuntu
`/etc/tvconfig/hdmi/port1_14.bin`. Only the HDMI VSDB deep-colour flags at
offset `0xb2` are cleared (`0xb8` → `0x80`), then the CTA block checksum is
recomputed (`0x84` → `0xbc`). Timings, LPCM audio and other capabilities remain.

The vendor table makes the test Mac transmit 1080p60 YUV444 10-bit at
185.625 MHz, which the current mainline receiver does not support. This separate
named preset advertises the supported 8-bit path without rewriting the vendor
table or uploaded EDIDs. Both kernels can use it; the original preset remains.

## RTK UHD HDR：4K60、高刷、超宽屏与VRR

`rtk-uhd-hdr-1080p120.bin` 基于上面的 RTK 原表，是当前 `RTK-CONTROL` 使用的数据。
文件名沿用高刷实验的历史名称；菜单只有一个「RTK UHD HDR」，不再列实验项。
旧 `RTK-1080P120` 标识仅作兼容别名，选择后保存为 `RTK-CONTROL`。
原表没有 CTA VIC 63/64（1080p120/100），垂直扫描范围上限为 61Hz。
首版在原有两个保留 SVD 槽位 `0x8c/0x8d` 写入 63/64，将 `0x72` 的垂直范围
上限改为 120，再重算 `0x7f/0xff` 校验和；当时共改动 5 字节。原有 SVD 索引不移动，
避免改变 Y420 capability map 的对应关系。首选模式仍为 4K60，1080p60/1440p60 DTD、
音频、HDR和深色保留。同一表内加入HDMI Forum VRR 48–120Hz，移除原AMD
FreeSync 40–61Hz声明；不新增菜单项。按所选模式限定上限：当前Mac的1080p最高120，
4K最高60，声明VRRmax=120不增加4K120时序。首版错误写入保留值VRRmax=60，
经Mac单字段对照与edid-decode检查后修正；最大值1–99不可用于声明保守上限。
当前表由 [vim4edid.py](../vim4edid.py) 从原始256字节表生成，增加第二个CTA块，
用DTD声明2560×1440p120、3440×1440p60，用VIC90声明2560×1080p60。
水平扫描上限同步提高到180kHz，保留首选4K60和原有时序、音频、HDR块。
当前384字节表SHA256：`ec7f330a18d36bed31f4de4ce104fa4e8844f1ef9d6dbdd89a2ab8f955792f92`。
配套5.15 One-KVM的动态画面与HDR边界见[远程HDR与扩展尺寸验收](../../docs/bringup/2026-10-26-remote-hdr-modes.md)。
此前256字节合并表SHA256：`45ed44250763f39561961829ff5f9f5f18a8fba6847afd088f8aab2636ceaf45`。
首版VRR实验表SHA256：`085a5b2ffeadf88c17a4d0e8d6a48ef9d92e14ec71a02c43dc21e4fedbf74ea1`。
字段对照和4K变频结果见[范围声明纠正与4K输入验证](../../docs/bringup/2026-10-26-vrr-range-4k.md)。
历史固定高刷版本SHA256：`75c822f7e6c747dc9f8bbe235e9e9fd49a2a7a318810a7d4f9525eb6c1491d07`。

这只是输入能力声明，需要配套 RX 高刷格式映射与应用编码上限。首次实板验收从
SDR 8-bit 开始；增加声明不等于已经验证 HDR120、远程120帧或本地 HDMI OUT120。
原表内的其他保留 VIC/能力声明沿用，不能把校验和正确当作整表协议符合性证明。
加载后需在源端主动选择 1920×1080 120Hz；完整验收步骤见
[1080p120 审查](../../docs/1080p120-audit.md)。历史[1080p120实板验收](../../docs/bringup/2026-10-26-1080p120.md)测后曾恢复原表；当前合并部署见[统一RTK入口](../../docs/bringup/2026-10-26-rtk-unified.md)。

## VRR EDID 离线候选

`tools/vrr-edid.py` 可按显式范围生成单独候选，不覆盖原表、不写接收端。
远程模式不依赖OUT；本地模式要求显示器EDID，并取同协议的接收/请求/显示器范围交集。
原RTK只有AMD FreeSync 40–61Hz，不能当作HDMI Forum VRR显示器。
此工具没有建立硬件资格，使用方法与待验边界见
[VRR离线准备](../../docs/vrr-preparation.md)。

VRR能力合并到 `RTK-CONTROL`；不再要求用户选择另一张实验表，厂商默认选择不变。
需配套5.15 VRR输入驱动与应用，首次测试主动选择1080p60 SDR 8-bit。
1080p约49–120Hz已有[真实源验证](../../docs/bringup/2026-10-26-vrr-live.md)，不能视为硬件极限；不启用本地输出VRR，
不代表7.3支持VRR，也不声明原生1Hz输入。固定1080p120模式仍独立保留。
