# 2026-10-24：HDMI OUT 颜色自环校准与厂商基准

本窗口接续 [M3 4K 显示器颜色阻塞](2026-10-23-display-m3-window4.md)。
候选分支 `vim4-display-color` 基于 `vim4-kvm-7.3@302f6e0fffa6d`，
未合入正式分支、未正式部署。默认内核始终为 `eeddb005df059a850853876d52ef603aa1af192b`。
所有适用组合均取得合格的短窗口颜色样本；完整矩阵复测有采集错误，
**持续自环稳定性未通过**，不能据此部署或开始透传实现。

## 离线实现与证据

颜色链路来源见 [厂商源码基准](../display-color-vendor.md)，固定
`common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49`。
7.3 仍使用标准 DRM connector/bridge HDMI state、output format、Broadcast RGB 与
AVI helper；没有移植 amhdmitx 私有框架。SDR 8bpc 的 OSD HDR2 matrix-I 写入厂商
RGB→709 limited 系数，关 HDR core/LUT，matrix-I 单独开启。VPP0 只配置 OSD1 HDR2；
T7 不存在 OSD2 HDR core，OSD3 HDR 属 VPP1，不能按 OSD plane 名字猜寄存器。

RGB 输出在 POST2 进行 709 limited→RGB full/limited，TX CSC bypass；YUV 输出
POST2 bypass。TX 输入分量映射随实际数据域变化，AVI Q/YQ 来自标准状态；
4K60 的420仅在 EDID 声明时使用。RGB full 使用厂商 POST2 系数原表，limited 系数
按相同比例缩放并添加 10bit 域64偏置。物理精度由下面的原始帧校准判定。

| 内核提交 | 单一改动 |
|---|---|
| `f60afc76c6e85` / `47d593a452f16` | POST2 资源 binding / M3 DT |
| `ed6cc10e07a73` | POST2、量化范围与 TX 数据域一致 |
| `61b28bb35d133` / `2c7fd089a4f65` | VPP0 OSD HDR2 binding / DT |
| `a663a2d80cd42` | 厂商 SDR matrix-I 与 core/LUT 关闭序列 |
| `f04aad594663e` | TX link_state 颜色控制回读 |
| `0e294065e24a9` | video DT 资源检查避免固定数量并验证无重叠 |
| `71fad6c59b650` | 向 HDMI connector 挂接标准 Broadcast RGB 属性 |
| `c24465df1dd70` | TX input bus 格式描述与 POST2 的 RGB/YUV 域一致；补离线测试 |

以上小提交逐项 strict checkpatch 为 0 errors / warnings / checks。
Image、DTBs、2339 模块构建完成，68 个离线 host fixtures 通过，定向 schema 无诊断，
M3 与 video DT 资源检查通过。构建 ID `1fe8e024a87c17af593d2a76d16dec6751a37c0d`，
Image SHA256 `7b5a76c043e63538dce4d77fd4259d7e56ede76341a1315155b35d22cef65c00`。
日志位于 `logs/display/color/validate-2.log`、`offline-4/results.json`。

[校准工具](../display-color-calibration.md) 创建 KMS dumb 图案、原生 V4L2 NV12
采样、每块3帧误差报告和同 sink 寄存器差分，已登记工具目录。第二阶段只有
[透传设计草案](../hdmi-passthrough-design.md)，未实现 VD1/音频透传。

## 厂商 5.15 同线对照

两种内核使用同一根 OUT→IN 线、同一份 VIM4 COLOR SDR EDID；最终比较须核对完整
EDID 字节。原用户 RTK EDID 的420 map 引用了缺失 SVD，工具拒绝后改用专用有效 EDID，
未修改用户持久化配置。厂商 frac_rate_policy 临时设0以固定整数60Hz。
5.15 使用既有版本化 Image/DTB/initrd，通过 RAM sysboot 一次性启动，默认项未改。

自环会触发厂商 repeater 的 TX 插入回调并刷新自己的 RX EDID，临时设置
`rpt_edid_selection 1` 后稳定。运行中的 RX FSM 与写 EDID 交错曾产生混合 RAM 内容，
单纯读用户态 EDID 缓存不能发现；暂停 FSM、runtime load、同步 `reset40`、finally
恢复 FSM 后，TX 读回与校准 EDID 逐字节一致。失败窗口与完整修正窗口分别保存。

`vendor-r4/matrix.json` 完成7档寄存器参考：1080p60 和4K30各 RGB/444，4K60 RGB/444/420。
1080p60、4K30的420未声明。所有适用档均成功启停 dumb buffer，退出0。
厂商 RGB AVI 实测 Q=limited，YUV YQ=limited；不能把 native 当作已实现 full。

| 项目 | 厂商实测 |
|---|---|
| OSD1 HDR CTRL / input enable / output enable | `0x1c040` / 1 / 0 |
| OSD input coefficient | `00ba0273 003f1f99 1ea701c0 01c01e69 00001fd7` |
| POST2 enable | 0 |
| RGB CSC0/CSC1，高字节 | `65/00`，`08/00` |
| YUV CSC0/CSC1，高字节 | `00/00`，`08/00` |
| HDMI_SETTING，普通 /420 | `0x3000e` / `0x13008e` |
| AVI | BT.709、16:9、8bpc；4K30使用 AVI VIC0 + HDMI1.4 VSIF |

厂商无 `/dev/mem`；控制字经已登记 debug 接口，RX COR 用字节读两次，TX AVI 用实际
packet getter。未读取 LUT 自增端口或 HDCP 密钥窗口。

1080p60另用 `vfmcapsrc` 取得原生 NV21，丢8帧保存3帧，1920 stride、UV offset2073600，
BT.709 limited；仅在离线分析时交换 VU 为 UV，保留原始文件和哈希。

| 厂商输出 | 全图案最大8bit误差 | 黑 / 白 Y | 结论 |
|---|---:|---:|---|
| RGB native limited | 23 | 16 /234 | 原色不通过，不能当 RGB 绝对正确基准 |
| YCbCr444 limited | 2 | 16 /234 | 本组原始采样通过 |

证据：`logs/display/color/vendor-r4/`、`vendor-rgb-raw/`、`vendor-yuv-raw/`。
完整厂商模式矩阵只有寄存器参考，不冒充完整数值矩阵通过。

## 候选上板矩阵

自环启动时 RX 在 U-Boot 中尚未形成有效 DDC sink，TX 强制回退720p。
7.3 的1080p固件接管合同因此拒绝 probe，未发布显示 DRM card；这是采样前失败，
不能计颜色失败或通过。RAM 中尝试厂商 RX init/HPD/AON 操作后 HPD 可见，但 TX EDID
仍无有效 header；未 saveenv、未修改 bootloader。UART 见 `candidate-1..6-uart.log`。
接显示器满足1080p接管合同后回到自环，候选8/10启动通过。中间两次复位回基线，
日志没有记录原因，不能断言为内核故障或人为复位。最后窗口保留连续UART与boot ID。

带 RGB 属性的实测 build ID `faf085bd85942692418dbd417ad241fde917dc42`，
Image SHA256 `c156154c0ceaac32fffe7dcfbacc57f6642f76f171bcd22f270652e3dcf3ab4a`。
打包时提交 `b06fb6c849a51` 随后仅修正提交说明/身份为 `71fad6c59b650`，两者 tree
完全相同，后者重建的 Image SHA/build ID 逐字节一致，见 `final-head-build.log`。
最后 `c24465df1dd70` 只修正 bus 协商描述，没有改变矩阵、TX写入或像素；已离线执行
8/10bpc × RGB/444/420协商测试，不声称该提交另有一次上板窗口。
该HEAD完整Image/DTBs/2339模块构建完成，68项host fixtures与10提交strict checkpatch通过；
build ID `35d54c1c03846949e84e0b88b097ea5086535704`，Image SHA256
`d47b42f0ecd4926fcd13f02bda7d0bb3595b27d0f01d68ba614281fbbad5cb5d`。

下表为有效样本的全部色块、三帧、8bit 最大绝对误差。每个有效帧都满足完整性、
前进序列、原生几何和709 limited NV12合同，TX/RX AVI一致、checksum正确、taint=0。
**这是跨窗口颜色见证表，不是任何一次完整矩阵全通过。**

| 模式 | RGB full | RGB limited | YCbCr444 limited | YCbCr420 limited |
|---|---:|---:|---:|---:|
| 1080p60 | 1 | 2 | 2 | EDID不适用 |
| 4K30 | 1 | 2 | 2 | EDID不适用 |
| 4K60 | 1 | 2 | 2 | 2 |

4K60 RGB full取自 `candidate-r8`（预热8帧），420取自 `candidate-r10`（预热8帧）；
其余取自 `candidate-r12`（预热0帧，连续2秒时序资格确认后取3帧）。
RGB full黑/白实测NV12为 `[16,128,128] / [235,128,128]`；limited/YUV为
`[16,128,128] / [234,128,128]`，白色距235差1。没有放宽≤2阈值或忽略错误帧。
Mac离线重跑10组analyze全部吻合；原始帧、哈希、色块值、每档前后寄存器保留在这些目录，
索引 `logs/display/color/numeric-witnesses.json`。

### 完整窗口失败与测量工具修正

`candidate-r8` 默认8帧预热仅4/10适用档完成；其余有ENOLINK/EAGAIN或错误buffer。
连续2秒判稳的 `r9` 未消除失败。修正布局后的默认预热 `r10` 仅3/10，
短窗口 `r12` 为8/10（4K60 RGB full错误buffer、420 S_FMT ENOLINK）。全部失败保留，
不挑一个成功样本替换原矩阵状态。失败buffer示例 `flags=0x2041`、sequence回0；
VDIN debug记录 `stream_stops`、`invalid_frames` 和 `dma-wait`，尚未证明初始根因。
这与既有 [RX切换失锁](2026-10-23-hdmirx-lowclock-closeout.md) 的范围有关，但不能仅凭
相似错误码归为同一原因；真实PC源恢复后另做KVM冒烟。

工具实际修正：RX COR改逐字节访问（Python slice的memcpy可能宽读）；
NV12 UV偏移为 `stride * height`，不是 `stride * ALIGN(height,16)`。
1080p有效payload3110400，分配3133440，额外空间在尾部；旧工具错误拒绝完整帧，
已增加紧密平面加尾部空间的回归测试。驱动错误buffer仍严格拒绝。
`r11` 的预热0参数解析错误未采样，修正后才有 `r12`；不算板子颜色失败。

### 逐项寄存器差分

同一校准EDID下每档输出 `vendor-diff.json`，包括相同项；差异全集及理由如下，
没有通过写无关bank追求表面一致。两端实际均8bpc，P2T/GCP、input mask、output map、
CSC1与高字节、scrambling/clock ratio以及AVI colorspace/colorimetry/VIC语义一致。

| 寄存器差异 | 理由 |
|---|---|
| `0x271b HDMI_SETTING` RGB pre=3→0 | 厂商TX接709 YUV，候选POST2已输出RGB；444/420映射相同 |
| `0x39a0..a3/a9..ad` POST2 | RGB使用厂商709→RGB原表/limited派生；YUV使能0时残留系数无效 |
| TX `0xd20` RGB `0x65→0` | 候选在POST2转换；厂商RGB原色误差23，不能照搬该preset冒充正确 |
| AVI Q，vendor limited→候选full | 仅RGB full见证有此预期差异；limited相同；hex字段仅候选提供，语义逐字段对比 |
| `0x38a0` `1c040→1c000` | 候选明确关闭gamut模式；双方core/LUT off、matrix-I on |
| `0x38c8`、`0x38d1..d5` | ADPS/gamut遗留值；core和gamut模式关闭，未参与SDR像素，input/output矩阵及使能相同 |
| `0x1d5f` `0→7800` | 固件遗留的旧VPP matrix控制，相关enable位均0；不在新POST2/OSD HDR2链中 |
| `0x5b50/52..56/5a..5b/5e..62/66..67/78/80..85/8c` | OSD3 HDR属于VPP1，厂商与固件遗留不同；候选不拥有/不写，不在当前VPP0链 |

## 恢复与交付

已按文件协议收到“HDMI IN 接 Mac mini，HDMI OUT 接真实显示器”的恢复确认；
回到默认eeddb005，保护文件哈希均一致，One-KVM/manager active、UDC configured、taint0。
真实HID的按键down/up、绝对/相对鼠标、点击、滚轮均通过。
H.265 4K60连续300秒，约59.9818fps，18000帧量级持续前进、丢帧/丢包0、PLI0；
浏览器记录1次freeze，presentation最大间隔200.1ms，不能称为零冻结。
退出后视频模式恢复原H.264；再次核对保护哈希、服务、UDC、taint和Wave5隔离均正常。
证据 `recovery-hid.log`、`recovery-h265.log`、`recovery-after-smoke.json`。
用户持久化EDID SHA仍为 `32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。
基线panic=20/panic_on_oops=0与窗口前相同；候选为oops=panic/panic_on_oops=1，
两种内核PID1均持有30秒硬件watchdog。本轮没有改持久化sysctl或默认启动配置。
原始证据归档 `logs/display/color/board-final-evidence.tar.gz`，两端SHA256一致：
`4ef3921a00bc0a6c30e9a18a7332d8355ff8f6d71a3ccd8c4ddafa452ebaf068`。
确认eeddb005、保护哈希、候选目录无挂载/符号链接后，删除本轮两份display-once目录、
临时厂商boot config及board端工作目录；未触碰既有5.15和正式模块。
内核 `vim4-display-color@c24465df1dd70525a73557d26889e5ce15c35feb` 已推送，
未合入 `vim4-kvm-7.3`。主仓最终离线242项测试通过（6跳过）。

第二阶段设计保留单一采集所有者、DMA-buf/退休引用、源模式跟随、失锁恢复、One-KVM
共享、音频单采集者与漂移处理、厂商A/B/A光学延迟对照；本轮没有实现透传。
