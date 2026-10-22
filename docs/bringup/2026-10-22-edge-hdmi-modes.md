# 2026-10-22：7.3 HDMI RX 输入模式泛化

首轮实现与故障记录；后续结果见[最终产物复核](2026-10-22-edge-hdmi-modes-final.md)。

独立内核和 One-KVM 工作树实现实测时序分档、几何和颜色配置。下文区分原始内容、
浏览器编码和源端实际格式；离线接纳不能替代实测。本轮不扩展 HDMI 音频。

## 源码与实现

内核工作树 `/home/deepdream/src/linux-7.3-hdmi`，分支 `vim4-hdmirx-modes`，基于
`51307a1cf3a60ea1a9cfc1cd35f159c5373d8f1d`，没有修改原工作树或推送。

- `5d9bc75716c9243cf251f7e48f6c7f65d46f3afd`：通用 PHY、真实 porch、颜色解析和 CSC、DMA 几何。
- `bebff17efd799`：检查各时钟档和边界上的 PLL 恢复频率。
- `552afb0238cda`：无效 FDET 的恢复重试，以及原生 YUV 映射与旧通道重排的区分。
- `209996a0efc5a`：原生 YUV 归一化之后应用 PQ 映射，接纳 422/444/420 的 HDR10。
- `30a7b739ee39c`：NV12 行对齐到 32 字节，满足 Wave5 的 DMA 导入几何。
- `6afb1c030c09d`：连续不稳定时序快照不再无限跳过恢复；瞬时 EAGAIN 仍重试。
- `a552088ffe47f`：PCS 恢复后执行厂商 T7 的深色 FIFO 复位。
- `5cad9a26b112d`：更新驱动行为文档。
- `4b8d2b1fad0bd`：Wave5 压缩格式接纳偶数可见宽高，RAW DMA 的 32×16 对齐保持独立。
- `ee408a794beb2`：单次撕裂测量只丢当帧，不终止整条 V4L2 采集流。
- `87d0423e74a21`：H.265 保持原有 8 像素步长，偶数可见尺寸仅扩展 H.264。

One-KVM 独立工作树为 `build/kernel-edge/hdmi-modes/One-KVM`，同名分支，基于
`2021f634`；提交 `af30338f`、`13bbaed0`。输入状态读取通用时序，采集 caps 不再固定 60Hz；
NV12 两平面视图使用 GstVideoMeta 的实际 stride，保留父缓冲引用和可见宽度。
1366 宽的 UV 偏移按 `1376 × height`，编码器所需的高度补齐也乘实际 stride。
原应用工作树未修改，候选 ELF 仅临时替换。采集 allocation query 在 snapshot tee
分支前主动请求 VideoMeta，保留真实 stride。

厂商依据为 VM `~/src/linux/common_drivers/drivers/media/vin/tvin/`：

- `hdmirx/hdmi_rx_hw_t7.c` 的 DCHA/DCHD/APLL 表及 `aml_pll_bw_cfg_t7`，
  `hdmi_rx_hw.c` 的 cable/PLL 分档、`hdmirx_set_vp_mapping`，以及 wrapper 的 T7 默认
  `os_rate=3`。PHY 六档边界 45/77/155/340/525MHz，PLL 五档边界 35/75/155/340MHz；
  低档使用厂商自动 4 倍过采样，1:40 时 cable clock 乘四后选档。
  wrapper 的 `FSM_SIG_UNSTABLE` 在 TMDS 恢复后调用 `rx_cor_reset`；
  T7 实现 `rx_sw_reset_t7` 对 `RX_PWD_SRST_PWD_IVCRX(0x1005)` bit4
  拉高一微秒后清除。恢复路径补齐此深色 FIFO 步骤，保留其余位。
- `hdmi_rx_hw.h` 的 FDET polarity/porch 寄存器。双快照拒绝撕裂读数，校验 active、
  front、sync、back 与 total 的关系；不从 mode table 或空白比例猜 porch。
- `vdin/vdin_ctl.c` 的 RGB full/limited、601/709 full/limited 到 limited BT.709 矩阵，
  以及 VDIN 分量选择。动态 RX 使用厂商 TOP 原生 YUV 映射，不重复旧固定路径的 444 重排。

动态接纳范围为逐行、偶数 320–3840 × 180–2160、20–120Hz、24–600MHz 像素时钟；
TMDS character clock 小于 600MHz。该范围是校验边界，不能视为每个组合均已上板。
按实际输入决定 RGB/444/422/420、8/10/12bit、量化范围和 601/709；NV12 输出统一
limited BT.709。已验证的 PQ/2020 HDR10 路径保留。HLG、未映射的扩展色域、隔行、
像素重复和 16bit 拒绝捕获，不将它们当普通 SDR 输出。DVI 检测忽略旧 HDMI AVI 缓存。

采集 lease 保存真实几何和颜色；格式变化先使旧 lease 失效，等待 DMA 回收后再配置 PHY。
SOURCE_CHANGE 也比较帧周期，区分同尺寸不同帧率。1366 可见宽度不取整，行步长取
NV12 的 32 字节对齐；缓冲长度、UV 地址和编码导入均使用该步长。
VDIN 自身只要求 16 字节，但 Wave5 RAW 协商将 720 宽补至 736、1680 补至 1696；
保持旧步长会在编码 QBUF 时返回 EINVAL。实际可见宽高保持源端尺寸。

## 构建与离线验证

独立输出 `/home/deepdream/build/kernel-hdmi-modes`，沿用已部署配置，SHA256
`b67c0feeb849506467984d27fa75c9484d5dbe46073bb33b22bbfd6418d0c298`。
重型构建在 Mac 取得 `/tmp/vim4-heavy.lock` 后执行：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build sh -c '
  make -C /home/deepdream/src/linux-7.3-hdmi \
    O=/home/deepdream/build/kernel-hdmi-modes ARCH=arm64 -j8 Image dtbs modules'
```

完整及最终增量构建成功；2335 个 `.ko.xz` 经 modules_install、depmod、逐文件清单
校验并保留 BTF。DTB 取同次 audio-test 构建、保留原以太网 MAC。后续仅模块变化。

| 候选产物 | SHA256 / build ID |
|---|---|
| Image SHA256 | `c58430e4d2949f337c245cdf9da41c2ced9249a6f8b99fd452a9539c0873210b` |
| Image build ID | `4086bbfe5035e5c3f318fb26107e4ad668fc70fe` |
| DTB SHA256 | `e0ebe345dba968f811136de69412cc58846814775ce4d4f3ac440ee5d32961c5` |
| 最终完整模块包（87d0423） | `a0ab3644c1774468b7c1436d45eea14fed4d33d58c6a2b403269eeaf25b17d1c` |
| One-KVM ELF SHA256 | `c8bfb00e3a5a60ae4f9a6dbc723eaf2a59f8aedcdb6b862965004bf4e6348f8e` |

12 组实际 C 函数离线测试通过：core、DDC、PHY、link、audio 既有回归、VDIN、stream、
timings、ioctl locks、source events、HDR curve、runtime EDID。包含 19 组目标时序、
96 组颜色解析、1366 步长/分配边界、时序撕裂/非法值、同尺寸帧率变更、DMA lease 保护，
以及无效 FDET 不能被 HDR 探测保护永远保留的回归。
DMA 测试在交接前后注入 EAGAIN，要求仅丢当帧、下一帧正常、不重启队列，最终引用
全部回收；连续错误有界恢复、活跃 lease 不得重配 PHY。各目标时序及 PHY 分档两侧
均检查实际 APLL 恢复时钟。
Wave5 的 5 组离线测试通过，包含 DMA 导入、清理、profile、行刷新和新增可见几何。
现有 `wave5_set_enc_crop_info` 按 AVC 块大小计算右/底裁剪，
`wave5_vpu_enc_check_open_param` 检查尺寸范围和偶数裁剪单位；
H.264 压缩格式接口此前的 8 像素步长会使 1366 宽、900/1050 高协商失真，改为 2。
H.265 的相同放宽在实机不安全，已回到原有 8 像素步长。

One-KVM `cargo test --locked --features vim4 --lib` 为 731 passed、2 ignored；
板级 helper 30 项通过，ARM64 release 构建通过。没有改前端产物。
原始日志位于本机 `logs/kernel-edge/hdmi-modes/`，构建日志在 VM
`/home/deepdream/build/hdmi-modes-build*.log`。

## 受锁上板与失败轮次

备份 `/var/backups/vim4-hdmi-modes-20261021` 包含基线 Image/DTB、完整模块包及逐文件
清单、原 One-KVM、配置、启动清单和 runtime inventory。候选安装后全量注册校验，
重启比对运行内核和已加载模块 build ID。整个安装、测试、恢复和再次重启持双锁：

```sh
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/kernel-edge/hdmi-modes/board-window.py --reuse
```

首次窗口不带 `--reuse`；重复窗口先校验基线恢复，再复用同一份原始备份。
测试 EDID 仅写临时 RAM，HPD 拉低后等待 capture_users=0，不覆盖固件或应用 EDID 设置。
恢复使用接收器缓存的基线 RTK EDID，SHA256
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。
Mac 图源按测试 EDID 名称 VIM4 或基线 RTK 匹配，退出时关闭自己的窗口。

失败日志逐轮保留。图源名称、归档重名、444 重复重排均修正复测。25/50Hz 无效 FDET
现在有界恢复；精简 EDID 去掉音频块后，50Hz 仍有零高度，最终矩阵保留原音频块。

## 内容与链路覆盖

`ee408a794beb2` 的真实 Mac 源、单 DTD EDID 矩阵：以下 19 组 RGB8 原始 NV12 全部通过。
每组两帧检查实际 stride、三条帧号带一致/校验和、连续帧号递增和三原色；
1366/720/1680 的 stride 分别为 1376/736/1696。每次采集后 DMA-buf 为 0，
CMA 始终 `505192 KiB`，VDIN faulted=0。事件订阅记录 40 条 SOURCE_CHANGE，
日志 `raw-modes-final.jsonl`、`source-events.jsonl`。

| 真实源几何 | 帧率 Hz（部分取近似值） |
|---|---|
| 640×480 / 720×400 | 59.94 / 70.087 |
| 800×600 / 1024×768 | 60.317 / 60.004 |
| 1280×720 | 60、50 |
| 1280×1024 / 1366×768 | 60.02 / 59.79 |
| 1440×900 / 1600×900 / 1680×1050 | 59.90 / 60 / 59.88 |
| 1920×1080 | 24、25、30、50 |
| 1920×1200 / 2560×1440 | 59.95 / 59.95 |
| 3840×2160 | 30、60 |

非块对齐几何先做独立检查：专用 V4L2 插件下，640×480、1366×768、
1440×900、1680×1050 的 H.264 各编码 180 帧；ffprobe 报告原尺寸、180 帧，
ffmpeg 完整解码无错误。再以真实 HDMI 图源往返切换后三者，6 次浏览器内容检查通过，
约 59.6–60fps；旧候选只在单次时序 EAGAIN 后持续停流，不能用其短暂解码计数算通过。
原始日志 `encode-h264-verify.jsonl`、`browser-geometry-final.jsonl`。

`ee408a794beb2` 候选上，H.264 的全部 19 模式按升序再降序切换，38 次均通过实际
WebRTC 解码尺寸、三条帧号带、三原色、JPEG snapshot 和持续帧率检查；
保持同一连接/SSRC，24/25/30/50Hz 分别达到对应帧率，70Hz 输入输出约 60fps。
另将 HPD 拉低 5 秒，确认 link_ready=0、capture_users=0，640×480 恢复后仍为
同一 SSRC、约 60fps。日志 `browser-modes.jsonl`；历史低帧率候选未算通过。

H.265 在专用插件下 640×480 编码 180 帧成功，但 1366×768 45 秒超时，
gst-launch 留在内核等待，拖延重启。遗漏专用插件的更早诊断也失败，不能把失败仅
归因插件。最终回退 HEVC 的 8 像素约束，非对齐模式使用 H.264；不宣称 HEVC 全覆盖。

颜色测试按实际 AVI 和 GCP 记录，不能按 EDID 请求命名判定通过。已取得原始内容证据：
444/8 SDR、422 PQ（HDMI 422 的固定容器，GCP depth=0，不能据此证明源精度 12bit）、
420/10 PQ 和 444/10 SDR。请求 RGB deep 时 Mac 实际发送 444/10；请求 422 SDR 时
Mac 回到 444/8，这两次不能分别算作 RGB 深色和 422 SDR 覆盖。

420/10 SDR 在 HDR 关闭后原色读数约为 R=(208,75,35)、G=(155,245,83)、
B=(59,28,244)，未通过理想三原色阈值。相同 Mac/EDID/图源流程在原基线内核复测，
得到相同读数；PQ/10 的原色也与基线一致。保留此源端 ColorSync/显示偏好关联现象，
只报告与基线一致，不把它写成绝对色准通过。原始对照为
`baseline-colors.jsonl` 和 `colors-final.jsonl`。

## 首轮结束时的恢复状态

第一次挂起后已重启核验基线 build ID `52d5e46fb006230785110a1fa5ba0dd1383b732f`、
原始全部模块/启动链接及 manager active（`restore-after-hang.log`）。这不是本轮最后状态。
第二次 H.265 挂起后，恢复器实际输出 `Restored original Image, DTB and complete
module directory; reboot required`，并恢复原应用、RTK EDID；`sudo reboot` 后 SSH
长期不响应，串口无继续输出。当时请求现场 RESET，保留板锁；之后用户已复位并核验
基线 build ID、manager active、tainted=0，续测另记。

最终 `87d0423e74a21` 已构建/打包、5 组 Wave5 测试通过，尚未上板。还需复位核验基线、
验证最终产物及 H.265 对齐模式、补齐浏览器颜色链路，最后再恢复重启核验。
已有浏览器 422 PQ 通过；随后 420 PQ 图源因 macOS 尚无 VIM4 屏幕退出，该轮无效。
420 SDR8、444 12bit 请求尚未执行；实际 BIOS 固件画面、RGB 深色、422 SDR、HLG
未实测，HLG 当前明确拒绝。主仓离线测试 147 项、5 skipped，结果 OK。
