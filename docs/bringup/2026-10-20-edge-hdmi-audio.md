# 2026-10-20：7.3 HDMI LPCM 与 One-KVM 音频

独立实验启动项已打通 HDMI RX → FRHDMIRX → TODDR_A → ALSA → One-KVM Opus →
浏览器。固定 RGB8 3840×2160/60 输入、双声道 S16_LE/48kHz 已实测；
32/44.1kHz、动态采样率、休眠及失锁恢复尚未上板验收。
5.15 默认启动项、生产 Image、应用、USB 助手与配置未改变。

## EDID 复用边界

5.15 保存的活动 EDID 为 RTK-CONTROL，来自 [RTK EDID](../../board/edid/rtk-uhd-hdr.bin)，
SHA256 `32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。
它的首选 UHD60 DTD 是 533.12MHz，并公布 YUV444、HDR 和深色能力；当前实验
接收器只验证了 594MHz RGB8 UHD60，不能直接把这些未实现的能力一并公布。

[音频 EDID](../../packaging/kernel-edge/uhd60-audio-edid.hex) 保留此前验证的
UHD60 基础块、视频及 HDMI 数据块，复用 RTK 已验证 LPCM 能力的子集：
双声道、16bit、32/44.1/48kHz，FL/FR。每块校验和、音频能力子集和视频能力保持由
[离线检查](../../tests/test_edge_audio_edid.py) 验证。它不是完整 RTK EDID 的逐字节复制。
新固件为 `vim4-hdmirx-ddc-test/uhd60-audio-edid.bin`，不覆盖旧 EDID 或生产活动配置。

## 驱动与部署

- Linux `375bfd949dd5fbf6216d66a6b32e6f91d163b049`，包含首次音频接入 `6adca5b91a4b9`。
  使用独立 `amlogic-t7-a311d2-khadas-vim4-audio-test.dtb` 与 `audio_test=1`。
- 新声卡 `VIM4HDMIRX`，应用设备 `hw:VIM4HDMIRX,0`。TODDR 控件
  `TODDR_A SRC SEL` 选 `IN 8`。T7 选择位为 CTRL1[30:26]，S16 截取输入 [27:12]，
  单独管理通道同步寄存器，沿用上游 FIFO DMA 与周期中断。
- RX 验证 LPCM 双声道和 N/CTS 采样率后，启用 ACR 500MHz 参考、音频 PLL、
  FRHDMIRX 时钟和接收器输出/自动静音控制。PLL 超时会回收状态；停止后还原
  专属控制寄存器并停时钟。内部测试正弦始终关闭。
- One-KVM `a7743cb04b78618d7b6ed1a433c4a62e005cf674`：声卡存在时开放 ALSA 能力，
  新实验配置默认选择该卡；现有独立数据库通过音频 API 显式迁移。
- 安装前备份匹配 Image、DTB、整个模块目录、启动包装器、实际应用二进制和 SQLite。
  备份根目录 `/var/backups/vim4-onekvm-edge-20261020/audio-375bfd9/` 为 root 私有。
  新 DTB 复制上一实验 DTB 的板级 MAC 属性，避免丢失固定 DHCP 地址。

| 部件 | SHA256 |
|---|---|
| Image | `1e789cb30023745ec11af89389eef0177b55087a61c765b4ec364759e040772c` |
| 板级 DTB | `6ccb1ad1bcefba6cfb119b19e80f870a4c625f63c27b9dc34026735f94a16eb2` |
| 2333 模块归档 | `d5e8183f5bcc0365008aba6a8fd00dc70daf1f59d3e78fd993dd2b7f31a1d795` |
| One-KVM | `99b5152f4993a96dacf1802909a239a0a2d05713e2369ff64413d57b064b072e` |
| 音频 EDID | `2702ea6f67f82f414047f8f22b38f1eb5ae8a2c6207da5291f0aae40ce8be3d3` |

## 验证与剩余项

Mac 的 `hdmi-audio-tone.c` 仅向 VIM4-UHD-60 输出 440Hz、0.1 幅度测试音，
不改变系统默认输出。正式驱动录到 144000 帧、双声道 48kHz；峰值 3277/32768，
原型录音左右 RMS 均为 2317.05，440Hz 频率分析与输入吻合，其他邻近频率接近零。
`edge-audio-driver-final.wav` 与分析在忽略的 `logs/kernel-edge/` 中。

浏览器 `one-kvm-audio-check.mjs --exclusive` 连续解码 239040 帧，峰值 0.10285，
实际 Opus 波形非静音。音频 API 五轮停止/启动通过，HID 保持 online，内核 taint=0。
这不是主观听感或完整声画同步验收；长时间无爆音、丢信号/换格式恢复仍需补测。

ASan/UBSan 离线测试覆盖格式拒绝、时钟失败、占用 FIFO、PLL 超时与重复清理，
以及 T7 TODDR 源选择、S16 裁切、通道同步；内核 Image/DTB/模块构建、719 项 Rust
测试和 ARM64 release 通过。未安装 dt-schema，未声称完整绑定校验通过。
