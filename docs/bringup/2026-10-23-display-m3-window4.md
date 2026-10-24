# 2026-10-23：M3 4K 显示器窗口：链路与出声，颜色和 GPU 阻塞

接续 [M3 HDMI 实现](2026-10-23-display-m3-hdmi-color.md) 和
[批量清单](2026-10-23-display-m3-hdmi-validation.md)。本窗口没有正式部署，
没有将失败的 M3 atomic-color / video 路径合入正式源码。

## 版本、锁与一次性启动

用户把 HDMI-OUT 接到支持 4K60/HDR 的显示器，未提供具体型号；EDID 名称为
`RTK UHD HDR`、序列号 `demoset-1`。物理判断通过 need-user 文件协议取得，
不再用 Mac USB 采集卡抓帧。中断的 HDR 工作已保存在 WIP refs / stash，未丢弃。

实际取得 board + heavy 双锁：UTC 2026-10-24 03:45:32，04:30:22 释放，约 44分50秒。
窗口内没有并行重型构建。此前正式部署任务已回退，锁内读取的恢复目标为：

- 实际基线源码 `b1300eb808f43e7161d4971d47c689af28e67e83`；
  build ID `eeddb005df059a850853876d52ef603aa1af192b`。
- M3 合入当时最新正式源码 `8b2553f7b3c6235c57fbca8b22eec1e12abecc8c`，
  merge 为 `6ed602246f6bf`；加只读 TX/SCDC/packet 诊断的候选为 `4e7f9da265482`。
- 候选 build ID `a8bbfc54a13f91a5fff0f987af2d8b38917bd2be`，同次完整构建
  Image、M3/M3-video DTB、2334 个模块。使用重新编译的静态一次性 init，
  不复用过期的工具二进制。

候选只在本次 U-Boot RAM 中 `sysboot`，默认 extlinux 项、Image/DTB、运行时登记
均未改写。初次 prepare 使用过期 init，preflight 拒绝后自动回默认项；之后改用
与当前生产源码一致的新 init。init 离线测试 Mac 共6项、跳过1项，VM 6项全部通过。

4K sink 会让固件选择 4K 并留下额外 OSD。根据厂商 U-Boot `cmd_osd.c`，仅在候选
RAM 命令中先 `display_layer=viu2_osd0; osd close`，再选择 `osd0`，设置
`outputmode/hdmimode=1080p60hz`、`colorattribute=444,8bit`，通过
`vout prepare`、`osd open/close/open/clear/enable`、`vout output` 建立已知接管状态。
核对 OSD2/3 fetch-off 和 ENC2 2200×1125 后才启动候选。**没有 saveenv 或刷 U-Boot。**

## EDID 与模式证据

EDID 原文经 edid-decode 解码：最高 TMDS 600MHz、SCDC present、支持低速 scrambling，
30/36-bit deep-color；PQ / SDR EOTF、静态 metadata type 1，估计峰值约 486cd/m²。
音频 LPCM 2ch，32..192kHz，16/20/24bit，FL/FR。首选 3840×2160 59.982Hz / 533.12MHz，
另有 CEA 4K60/59.94/50/30/25/24、1440p59.95、1080p60/59.94、720p60/59.94。

420 capability map 引用了越界 SVD 19/20；有 420 10-bit 标志并不等于某个有效
4K60 mode 可用 420。最终以 DRM 解析和 atomic 校验为准，没有强行扩大 EDID 能力。

M3-video 的首次 OSD-only atomic commit 返回成功，但 OSD fetch 保持关闭，用户见
整屏紫色。为隔离视频层问题，先回默认基线，再用**同次构建**的 M3 OSD-only DT
重新一次性启动；后续 OSD fetch 正常开启，取得以下读回：

| 请求 | 实际状态 / 读回 | 验收结论 |
|---|---|---|
| 1080p60 RGB 8bpc | active=0x04380780，TMDS 148.5MHz，SCDC=0 | 原 video profile 只有紫色背景；OSD profile 用户反馈超时 |
| 1440p60 RGB 8bpc | 2560×1440，241.5MHz，2720×1481，59.95Hz；active=0x05a00a00 | 用户明确看见本模式文字和色条，无闪烁/黑屏，但整体偏紫/品红，失败 |
| 4K30 RGB 8bpc | 3840×2160，active=0x08700f00，PHY0=0x33eb42a2，SCDC=0 | 完成切换/读回；收到的是迟到的 1440p 反馈，不能归为本模式物理通过 |
| 4K60 RGB 8bpc | CEA VIC97，PHY0=0x37eb65c4，SCRCTL=0x21，SCDC config=0x03/status=0x0f | 链路配置读回通过；物理颜色/闪烁未取得本模式确认 |
| 4K60 YUV420 | atomic commit 拒绝，EDID map 异常 | 未上屏，不称支持 |
| 1080p60 RGB 10bpc | DRM actual output_bpc=10，TMDS185.625MHz，P2T=0x81、GCP=0x01 | 打包/位深读回；没有独立物理颜色确认 |

第一次 1440p 测试工具未带 `-a` 枚举模式，index 与 atomic modeset 的列表不同，
实际切到了 4K29.97；该次结果作废。修正为同样的 `-a` 枚举，并在展示模式文字前
校验实际 DRM geometry / output_bpc，才取得表中有效 1440p 读回。

短超时轮换模式使用户反馈滞后，回复里明确说屏幕文字为 1440p，不能按当时正在
等待的 4K30 标签记成通过。后续物理窗口应保持同一画面等到回复，要求反馈屏幕
模式文字；没有回复就停止该轮物理验收并回基线，避免连续发过期问题。

## 颜色、HDR 与 GPU 的阻塞

TX AVI packet bank 0 为 RGB/full，而 CSC0/1 控制读回仍为 `0x00/0x00`；
OSD HDR2 继承了 YUV 转换路径。用户反馈黑/深色块呈品红，符合传输与 AVI 不一致，
但尚不能据此断定 CSC 写入不保持的硬件根因。不能把设寄存器的离线 mock 当成
有效物理转换。下一步需核对 CMS 实际时钟/路由、SMC 读写结果及厂商有效路径。

读回 OSD1/3 HDR2 CTRL=`0xe05f`，输入/输出矩阵 enable=1，gamut control=0x0b；
通用 0x3910..0x391d 仍全零。新增只读采样刻意避开自动递增 LUT 数据端口。
当前继续保留 HDR2 所有权门禁，不下发未经转换的 HDR 内容。本窗口对 PQ metadata
做 TEST_ONLY，因未同时选择 BT2020 而返回 EINVAL；这只证明该组合被拒绝，
不是实际 HDR 输出或正确 BT2020/HDR 组合的硬件测试。DRM bank 6 enable=0，
其中残留的固件 payload 不能计为 HDR packet 正在发送。

GPU 确认 renderer=`Mali-G52 r1 (Panfrost)`、OpenGL ES3.1 / Mesa25.2.8，
不是 llvmpipe。但可见 3840×2160 surface 的 Mesa render-only dumb allocation
实际请求 `width=3840 height=2178 bpp=32`，被驱动的 2160 行分配限制拒绝。
没有有效 4K GPU scanout，也没有可报告的分数。PRIME ioctl trace 保留用于后续核对。

窗口后离线修复：

- `c916015a6dbb4`：affected-plane expansion 不包含未挂接的禁用 VD1/2，
  `video_collect()` 应产生空退休槽，而非返回 EINVAL 提前跳过整个 OSD 提交。
  测试执行真实 C 路径，覆盖双缺席、单层参与、blank，保留退休/fence 合同。
- `9137809a908cc`：dumb allocation 允许最多 4096 行 tailroom；可见 framebuffer /
  mode 上限及完整行 DMA 边界不变，固定 M1 尺寸合同不变。实际 callback 测试覆盖
  3840×2178 和上界、零尺寸、M1 拒绝路径。**两项尚未复验上板。**

## TX 实际出声、采集共存与拔插

`speaker-test -D hw:VIM4HDMITX,0 -c2 -r48000 -F S16_LE -t sine -f1000`：
用户确认显示器“有声音”。随后按用户要求立即停止，后续不得再播放测试音。
TX/RX 声卡同时 RUNNING，TX 为 48kHz/S16_LE/2ch，ELD 对应 RTK UHD HDR；
Audio InfoFrame bank2 enable=0xe0、2ch。用户出声反馈是物理证据，不能仅以 PCM write 代替。

模式操作期间已有 680秒 4K H.264 浏览器会话完整结束，同 SSRC，像素 hash 变化；
样本间 670秒 frames1504→41532，dropped 保持13、lost/freezes=0。
这是连续性证据，不证明每个十秒片段恒定60fps。VDIN invalid_frames 有增长，
不是零错误；源码中 `-EAGAIN` 的 RX 测量撕裂会增加此计数，需与 RX 的硬失锁/
tmds-invalid 日志分开，并在正式基线上另做对照，不能归零或替采集任务作结论。

协议等待期间未收到拔插回复，45秒 HPD 样本90条均为 connected。释放锁后才收到
迟到反馈：用户确认拔下约10秒再插回，画面恢复、颜色仍偏紫，并要求结束在场操作。
这补充了用户观察；因未捕获边沿且反馈缺少发生时间，无法配对候选 boot ID，
**仍不计为带时间戳的候选 HPD 自动验收**。不再追加用户操作请求。

## 恢复、冒烟、清理

重启默认项后实际 build ID 回到 `eeddb005df059a850853876d52ef603aa1af192b`。
`/boot/edge/Image`、DTB、extlinux、kernels.json、runtime-build.json 五个哈希全为原值；
模块挂载回根文件系统，one-kvm / vim4-manager / vim4-wave5-monitor 均 active，
UDC configured、isolated=0、taint=0，dmesg 无新增 Oops/BUG/Call trace/WARNING。

H.265 4K 冒烟20秒：60.028fps，frames1385，dropped/lost/freezes/PLI 增量全0。
首次 HID 相对鼠标断言失败；复测记录了原始坐标，键盘 down/up、绝对和相对鼠标、
click、wheel 全过。第一次失败原因未证实，不掩盖失败记录。
基线控制台的用户确认超时，所以只记录自动化恢复通过，**本轮末尾肉眼画面未确认**。

确认模块不再 bind candidate 后删除本窗口 `/var/tmp/display-m3-window-4` 和
`/var/lib/vim4-kvm/display-m1/a8bbfc54a13f91a5fff0f987af2d8b38917bd2be`；
没有改他人的 /var/backups 回退点。只 fsync 本地目录，不做可能等待 CIFS 的全局 sync。
根盘余18G，/boot余13M。锁已释放；之后不再改变板子状态。

## 离线归档与下一窗口

原始日志 `logs/display/m3/window-4/`：build.log、candidate-manifest.json、各模式
drm/link/vpu/kernel、monitor.edid/monitor-edid.txt、remaining.log、用户原文、
gpu-debug.log/gpu.trace、audio-pcm/link、coexist.jsonl、final-default-serial.log、
final-baseline-health.json、final-hid[-retry].log、final-encoding.log 和 cleanup-board.log。
它们是本地原始证据，不随文档推送，不应假设远端仓库包含这些大文件。

下一次仍用一次性启动：先验两项离线修复，再以 YUV444/M2 已知颜色为参考，查清 RGB
CSC 读回和 HDR2 每层路由；每种模式保持画面等用户确认，不轮换过期指令。
随后复验 4K GPU PRIME/零拷贝、60Hz OSD flip、NV12、HPD/ELD、10-bit/420。
HDR/BT2020、P010、AFBC 仍按各自证据门禁推进，不把“属性存在”计为能力完成。
