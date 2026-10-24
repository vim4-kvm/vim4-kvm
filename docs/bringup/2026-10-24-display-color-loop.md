# 2026-10-24：HDMI OUT 颜色自环校准与厂商基准

本窗口接续 [M3 4K 显示器颜色阻塞](2026-10-23-display-m3-window4.md)。
候选分支 `vim4-display-color` 基于 `vim4-kvm-7.3@302f6e0fffa6d`，
未合入正式分支、未正式部署。默认内核始终为 `eeddb005df059a850853876d52ef603aa1af192b`。
本记录尚在测量中，未完成的项目不得作为颜色通过证据。

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

8 个小提交逐项 strict checkpatch 为 0 errors / warnings / checks。
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
| RGB CSC0/CSC1，高字节 | `65/00`，`08/08` |
| YUV CSC0/CSC1，高字节 | `00/00`，`08/08` |
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

## 候选上板矩阵与待办

自环启动时 RX 在 U-Boot 中尚未形成有效 DDC sink，TX 强制回退720p。
7.3 的1080p固件接管合同因此拒绝 probe，未发布显示 DRM card；这是采样前失败，
不能计颜色失败或通过。RAM 中尝试厂商 RX init/HPD/AON 操作后 HPD 可见，但 TX EDID
仍无有效 header；未 saveenv、未修改 bootloader。UART 见 `candidate-1..6-uart.log`。
已请求临时接显示器以满足既有接管合同，启动后再回自环。

数值矩阵、逐项寄存器差异解释、恢复与冒烟结果待本窗口完成后补齐。
