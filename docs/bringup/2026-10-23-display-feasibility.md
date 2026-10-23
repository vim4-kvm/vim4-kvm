# 2026-10-23：7.3 T7 HDMI 显示输出可行性调查

结论：推荐扩展现有 meson-drm，并沿用已导入的独立 `meson_hdmitx21` bridge。
T7 TX 不是 G12A/SM1 的 dw-hdmi，不能只增加 compatible。
当前 7.3 已有 T7 OSD/VENC、TMDS、EDID/HPD 和双声道 I²S 实现；这些是待验收候选，
不是本项目已验证的显示能力。首个里程碑应为固定 1080p60 RGB8 的标准 DRM 扫描输出。
最大前置障碍是显示与当前 VDIN 独占相同 MMIO，以及共享仲裁、时钟、电源的归属。
simpledrm 仅保留条件路线：当前启动没有已点亮 HDMI framebuffer 的证据。

本任务只审源码、检索、SSH 只读查询，没有写驱动、构建、加载模块、停服务或重启。
日期按板端 UTC；寄存器、厂商文件/行号及差异见
[硬件与源码明细](2026-10-23-display-hardware-audit.md)。

## 基线与证据范围

| 对象 | 本轮实际核对 |
|---|---|
| 5.15 内核 / common_drivers | VM `~/src/linux`：80a07ad54；common_drivers：4cfb128d36f8，干净；完整身份见明细 |
| 7.3 | `0196fe22ecf0104d96b7ef0fa497ca2317bd20bb`；独立只读 worktree `~/src/linux-7.3-display-feasibility`，分支 `investigate/display-feasibility` |
| 原生上游标签 | `v7.3`：091b06388b117fefdcb63336ac09956a4914b961 |
| Armbian | `~/src/armbian-build-7.3`：ecc676bf89af37788f972db9a7ff3f92844a43eb，164 个 meson-s4t7-7.3 补丁 |
| 板上内核 | `7.3.0-vim4kvm-uhd1+`，build ID `3a61b75bccf8c46e9411dee92928999884bbfc7f` |
| 已部署 U-Boot | `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`，源码 `~/src/u-boot-pd-handoff` |

部署来源及既有 HID 回归见 [Wave5 正式部署](2026-10-22-edge-wave5-deploy.md)。
原始只读日志在主工作区 `logs/display-feasibility/`，不入库；关键输出抄录如下。

## 已有实现与社区现状

检索截至 2026-10-23 UTC；基础支持、ISP 和编码器不等于显示支持。

| 来源 / 时间 | 结果及可复用范围 |
|---|---|
| [Linux v7.3 meson-drm](https://github.com/torvalds/linux/tree/v7.3/drivers/gpu/drm/meson)；本轮本地标签核对 | `meson_drv.c:542–550` 只有 GXBB/GXL/GXM/G12A VPU 匹配，SM1 沿 G12A 路线；没有 T7/S4/C3/A5 显示匹配或 hdmitx21 文件。T7 已有 HDMI PLL 节点，不等于有显示管线 |
| [Ao Xu / Amlogic S4 11 补丁系列](https://patchew.org/linux/20250110-drm-s4-v1-0-cbc2d5edaae8@amlogic.com/)，2025-01-10 | 重用 VIU/VPP，拆开的 HIU、VD 寄存器与安全 TX 访问需适配；评审指出 CCF/PHY/syscon 边界问题。该系列未成为上述 v7.3 的 S4 匹配。Armbian 已收入改编实现，不能当作上游合入 |
| [Amlogic SoC ID 系列](https://lists.openwall.net/linux-kernel/2024/07/19/211)，2024-07-19 | 含 S4/C3/T7/A5 基础识别；不是 VPU/HDMI 驱动。本轮检索没有定位到可直接用于 T7 的厂商上游 TX 完整系列，不宣称全网不存在 |
| [C3 ISP v7](https://lists.openwall.net/linux-kernel/2025/03/11/433)，2025-03-11；[A5 clocks v6](https://patchew.org/linux/20260123-a5-clk-v6-0-6d3bbf0ec1ea@amlogic.com/)，2026-01-23 | 找到的是摄像头 ISP 和 PLL/外设时钟工作；没有找到 C3/A5 可移植的 DRM HDMI 系列。基础模块可以参考，不能据此推导 T7 TX 兼容 |
| [Armbian 固定补丁目录](https://github.com/armbian/build/tree/ecc676bf89af37788f972db9a7ff3f92844a43eb/patch/kernel/archive/meson-s4t7-7.3)，2026-10-13 补丁、10-19 快照 | `0102–0107`、`0111` 为 Igor Pecovnik 的 T7 显示/声音候选；本轮直接读 VM 文件。网页取固定快照返回 cache miss，不以网页下载成功作证 |
| [Khadas 7.0 测试镜像公告](https://forum.khadas.com/t/vim1s-vim4-ubuntu-24-04-linux-mainline-7-0-testing-images-are-available-now/26490)，2026-04-14，07-12 指向 numbqq/linux | VIM1S 列 HDMI Display；VIM4 只列 Server 和基础外设，未列 HDMI Display。不能把 VIM1S 桌面支持归给 VIM4 |
| [LibreELEC Amlogic 发布页](https://libreelec.tv/downloads/amlogic/)，页面列 2025.11 / 12.2 | 标准内核路线可参考 DRM/Kodi 集成，但设备表到 G12/SM1，未列 T7/VIM4；不是可直接搬用的 T7 显示支持 |
| [CoreELEC Amlogic-ne 公告](https://discourse.coreelec.org/t/amlogic-ne-new-era/19354/1)，2022-10-08 | 明确列 VIM4/T7，基于厂商 5.4.125。可参考 TX/播放策略与厂商寄存器序列，不能视为 7.3 标准 DRM/KMS 移植完成 |

Armbian 的关键覆盖：`0102` 防 HDMI PLL 被 unused-clock 清理；`0103` 常开 VPU_HDMI、
VI_CLK1、VI_CLK2；`0104` bindings；`0105` T7 VPU；`0106` 新 bridge；`0107` DTS；
`0111` TOHDMITX 的 I²S MCLK/2；S4 基础在 `0040-amlogic-0174/0175`、`0046/0048`。
`0105` 为 13 文件 +288/-91 行，`0106` 新 TX C 文件 1014 行。范围为 TMDS ≤600MHz、
RGB8、双声道 I²S、无 HDCP；不含 HDMI 2.1 FRL/DSC/VRR 的完整能力。

## 与现有 KVM 的冲突

**不能在当前 DT 上简单把 `&vpu` 改为 okay。** 显示与 VDIN 都以资源申请 API 独占
`0xff000000–0xff03ffff`，前者 `meson_drv.c:245`，后者 `t7-vdin-test.c:1510`。
当前 `hdmirx-test.dts:64–79` 显式禁用 VPU，正好避免此冲突。
硬件 RX 在 fe398000，TX 在 fe300000/fe380000，两者控制器并非同一实例；采集端 VDIN0
写内存、显示 OSD/VD 读内存可以规划并行，但现有软件尚未具备安全共用条件。

- **共享寄存器**：DRM `meson_vpu_init()` 全写 `VPU_WRARB_MODE_L2C1(0x27a2)`；
  VDIN 在同一寄存器改 bit16，另写 `0x27a3`。必须先逐项核对读/写仲裁与掩码，
  不可去掉 request_mem_region 后让双方自由写。推荐一个 VCBUS 资源所有者，给两消费者
  提供共享 regmap 和受控仲裁更新；先列明寄存器清单，再决定最小父设备拆分。
- **电源/时钟**：两者依赖 VPU_HDMI、VI_CLK1/2、VPU_INTR、VPU/VAPB；
  VDIN 还使用 CLKB，按输入宽度设置 VPU 400/666.7MHz、VAPB 250/500MHz。
  显示不可因 blank/退出而复位整个 VPU、关闭这些域或降低采集要求的频率。
  HDMI pixel PLL 与 Wave5 的编码时钟不同，但仍共用内存总线/VAPB，不能承诺互不影响。
- **内存**：DRM GEM DMA scanout 增加连续内存压力。1080p XRGB8888 每帧约 7.91MiB，
  三缓冲约 23.73MiB；4K 三缓冲约 94.92MiB，尚未计 compositor、VDIN、编码引用帧。
  1080p60/4K60 扫描读取理论有效载荷约 0.50/1.99GB/s，均为算术估计，未测带宽。
  当前 CMA 512MiB，不能仅凭空闲总量认定长期分配无碎片风险。
- **音频**：当前 `audio-test.dts:34–45` 删除原 VIM4 声卡，只保留 VIM4HDMIRX/TODDR_A。
  输出需恢复独立 FRDDR→TDM→TOHDMITX→TX codec 的播放链，保留原采集声卡名与速率行为；
  不要整体替换成旧 sound 节点。先验双声道 PCM，另验 RX 与 TX 同时工作、时钟源和路由不互改。

## 只读板端结果与 simpledrm 判断

2026-10-23 03:51 UTC，命令组合为 `ssh vim4` 中执行 `uname -r`、读取 kernel notes、
`systemctl is-active one-kvm vim4-manager`、UDC state、`/proc/fb`、`/sys/class/drm`、
DT status、`/proc/asound/cards`、`/proc/meminfo`、过滤后的 dmesg 与 debugfs clk/genpd summary。
没有读取 debugfs 的寄存器转储或用 devmem 试探硬件。

```text
boot_id=fcca52f8-0d54-4fd9-9d0d-8296934b341d
kernel build_id=3a61b75bccf8c46e9411dee92928999884bbfc7f
one-kvm=active  vim4-manager=active  UDC=configured
/dev/hidg0..3 存在；/proc/fb 为空
/sys/class/drm: card0 和 renderD128 均属于 fe400000.gpu；没有 HDMI connector
/vpu@ff000000/status=disabled；hdmi-tx@300000/status=okay
fe300000.hdmi-tx/driver -> meson-hdmitx21
ALSA: 仅 VIM4HDMIRX
CmaTotal=524288 kB；CmaFree=505192 kB（瞬时值）
T7_VPU_HDMI / T7_VI_CLK1 / T7_VI_CLK2 / T7_HDMIRX 均 on
vpu≈666666656Hz；vapb≈499999992Hz；vpu_clkb≈666666656Hz
t7_sys_vpu_intr / t7_sys_hdmitx_apb≈166666664Hz
hdmi_pll_dco=0Hz，enable_count=0，硬件 enabled=N
```

`readelf -n /sys/kernel/notes` 因文件非 ELF 失败，改为解析原始 GNU type 3 note 得到 build ID。
clk_summary 零值不能单独证明模拟硬件状态；bridge probe 成功不证明 DDC、全部 COR 或像素有效。

已有同一基线部署串口 `logs/wave5-deploy/window-r2/uart.log:418–449` 实际包含：

```text
hdmimode=none
HDMI HPD low, no need parse EDID
outputmode none
[OSD]fb_addr for logo: 0x3f800000
outputmode[none] is invalid
```

本轮未重启。厂商 U-Boot 有 `hdmitx`、`osd dual_logo`、`vout`/BMP 代码，但 logo 地址不证明亮屏。
运行 DT 没有 simple-framebuffer 节点，也没有 framebuffer 保留区；只有 secmon、PCIe pool、ramoops。
uhd1.config 启用 meson/hdmitx21，关闭 `DRM_SIMPLEDRM`；`SYSFB_SIMPLEFB=y` 本身不能接管。
若以后走 M0，需证明 U-Boot 已设定有效模式、实际地址/stride/格式，按真实帧大小保留内存、
传递 `/chosen/framebuffer` 并维持时钟/电源。`0x3f800000` 落在当前 CMA 命令行允许的地址范围内，
不能照抄为可安全写入的 fb 地址。simpledrm 不提供 HDMI 音频和真实模式重配。

## 推荐里程碑与第一步

以下为熟悉 DRM/本仓库的单人有效工作日估计，按新增工作计；依赖现场硬件，
不含上游评审等待。固件或未公开寄存器问题可能扩大估算。

| 阶段 | 工作量 / 风险 | 验收与硬件 |
|---|---|---|
| M0 条件性 simpledrm | 已有亮屏且参数齐全时 2–4 日；本机需补启动交接则 1–2 周，风险中高，优先级低 | 真实 fb 图案经 Linux 更新、无重分配覆盖；需 HDMI-OUT 显示器和可见画面证据。不刷 U-Boot；任何启动脚本/DT 改动另立任务 |
| M1 固定 1080p60 DRM（推荐首项） | 7–15 日；MMIO/仲裁归属与 SMC 核对占主要风险 | 先离线完成资源方案、寄存器/时钟表、候选构建；再独立窗口用 modetest dumb buffer/page flip 验 RGB8 1920×1080@60、vblank 推进和真实运动图案。需标准 HDMI 线与 HDMI-OUT 显示器/独立采集器 |
| M1b KVM 共存门槛 | 另 5–10 日；风险高，必须先于宣称桌面可与 KVM 并用 | 输出启停、页面翻转时 RX 1080p/4K 采集、H.264/H.265、CMA 回收均回归；性能采样持双锁，禁止同时编译。未过时最多交付单用途显示实验 |
| M2 EDID/切模式/HPD | 4–8 日；已有代码可复用，DDC/固件访问风险中高 | 多显示器 EDID 校验、拔插事件、1080p/720p 切换和无屏启动；再独立扩展 4K/SCDC。需用户在场拔插、至少两类 sink；不能由 ≤600MHz 宣称任意模式均支持 |
| M3 HDMI 音频 | 5–10 日；已有 bridge/TOHDMITX，声卡集成与 MCLK/ACR 风险中高 | 先 48kHz 双声道 PCM，随后 44.1kHz、静音/恢复、模式切换与并行 RX 连续性；需带 HDMI 音频的电视/显示器或可测输出的音频提取器 |
| M4 桌面/kiosk/播放器 | 3–7 日起，取决于用户态及解码进度 | 再验 GBM/Panfrost/compositor、浏览器或播放器的实际画面。HDMI 亮屏不代表硬件视频解码或受保护流播放完成 |

**下一任务的具体交付建议**：先做 M1 的离线设计和候选，不直接改当前 DT 启用显示；
先解决 VCBUS 所有权、共享 0x27a2 更新、时钟最低需求和 TOP/COR 安全访问策略，
保留无 AFBC、无 HDCP、无 FRL 的最小 OSD1→RGB VPP→ENC0→TMDS 路线。
SMC/直接 MMIO 差异不能凭 bridge 已绑定跳过。

待用户确认：HDMI-OUT 是否接显示器、型号/1080p60/声音能力；能否提供真实画面和后续拔插窗口；
最终是否要求 KVM 与桌面同时运行。未收到硬件答复时按“显示器及音频 sink 尚未确认”安排后续。

本轮无部署和恢复；结束复核及测试见[明细](2026-10-23-display-hardware-audit.md)。HID 仅查节点与 UDC，
没有写 HID 报告，不能声称本轮重新通过端到端键鼠验证。
