# 2026-10-25：厂商 5.15 原生 HDR 与 SDR KVM 双路径交付

## 范围与安全边界

前置 [HDR→SDR 修复](2026-10-25-vendor-passthrough-hdr.md) 已交付默认 hdr1，
manager main `3c6ade7`、common_drivers 正式分支 `28b3dfef6`、主仓 `828630d`。
本条记录后续原生 HDR 实验及交付：显示保留 HDR10，独立 VDIN1 为 KVM 映射 SDR，
两路4K60。用户目视确认“没问题”，批准全部合入、部署并改为默认；未单独确认 HDR 图标。

最初阶段用户允许 One-KVM 采集接入候选、审阅前不合入 `vim4`：
One-KVM 分支 `passthrough-native-hdr`（接入 `b6019dce`，DMA 分配修复 `9827383e`）；
common_drivers 分支 `vim4-5.15-native-hdr`，不改正式分支。
候选内核代码 `482dc9543`；One-KVM说明补充 `483f441e`。
板上全程持有 Mac 侧 board/heavy 双锁，实验阶段默认 extlinux/内核清单哈希保持不变。
候选仅通过串口 RAM sysboot；原生产 One-KVM 二进制未替换，实验 ExecStart、HDMI 启动器与
插件目录均在 `/run`；最终获批后改为正式部署，见下方交付章节。

## 厂商路径与实际可行性

不能由“VDIN1 在 DTS 默认只声明 VIU 回写/lite”推断它不能接 HDMI RX。
T7 实际有独立 VDIN0/1 输入 mux、HDR2 核和写入通道；当前代码的限制主要是共享 frontend
生命周期和 V4L2 接口。保留厂商 T7 small/MIF1 路由，没有靠修改 export_id 假装完整 core。

本轮路径：

- HDMI RX 同一路 0x4001 → VDIN0 422 10-bit、HDR2 bypass → amvideo/VPP bypass → TX。
- 同一 RX → VDIN1 独立 HDR2 映射 → NV21 SDR DMA-buf `/dev/video71` → One-KVM 编码。
- 不从 HDMI OUT 回写采集，因此采集来源不是显示器分辨率/OSD，也不强迫 KVM 缩放至1080p。
- 声音继续独立 EXTN capture6 → SPDIF playback1 桥，不占用 KVM capture0。

厂商原有 tvpath 保留高位深 vframe 的 signal_type/DRM，VPP 根据 sink 能力生成 TX HDR。
厂商 VDIN1 capture 默认主要走 VIU 回写，再从 VD1/TX 格式选择 HDR→SDR；本候选改为
直接共享 HDMI 数据、借用已经打开的主 RX，只管理自己的写入/缓冲，不再开关主 RX。
这不是纯用户态第二条 VFM map 就能完成的功能。

## 驱动与接入修复

- VDIN1 借用主 RX 时跳过 RX open/start/stop/close、共享 AFIFO reset 和 EDID 改写；
  缺少主路径或源端口不同则 ENOLINK，不伪造第二个独立 RX。
- V4L2 STREAMON 重新建立自己的工作模式/frontend，不强迫每次 open 后都必须 S_INPUT；
  失败如实向用户态返回。原接口只在 S_INPUT 设置 V4L 工作模式，GStreamer 重开后
  保留相同 input 而跳过 S_INPUT，会错误走普通 CMA 分配路径。
- NV21 单平面自动给出1 plane；NV21M chroma stride 改为完整 width；完成帧有真实单调
  timestamp 与递增 sequence。原厂 sequence 一直0，不能拿它证明零丢帧。
- 显式候选参数 `aml_media.vdin0_native_hdr=1` 只让 VDIN0 bypass；VDIN1 根据 RX 而非 TX
  的 HDR 类型选择 HDR10/HLG→SDR。默认参数关闭，不改变正式 HDR→SDR 基线。
- One-KVM 仅在 `VIM4_SECONDARY_HDMI_CAPTURE=1` 使用 V4L2 DMA 路径；快照/编码分支
  保留真实 VideoMeta 与缓冲预算。默认三缓冲及跨 tee 协商曾仅约30fps，不能归因硬件带宽。
- 系统 `video4linux2` 虽报告 Ubuntu1.24.2，实际链接厂商 `libamlv4l2src`，调用 hdmictrl
  后关闭主 RX。实验仅使用既有 mainline 目录内的标准插件私有引用，不替换系统库。

## 已完成数据

VDIN1 直采同路 HDMI、3840×2160 NV21：600帧、steady **59.998fps**，sequence从2到601，
599次推进、缺口0，首尾采样哈希不同。主 RX 没有被第二实例重新打开/关闭。
启动开销包含在总耗时10.060s，不把含启动的59.642fps与稳定帧率混淆。

原生显示候选：VDIN0 source_bitdepth=10、canvas stride=9600、full_pack=1；
VPP VD1 vframe bitdepth=0x2a02、signal_type=0x20091009（BT.2020/PQ）。
TX 2160p60、422 12bit、AVI BT.2020 limited、DRM EOTF ST2084。
格式控制0x2743=0x800009、dither0x27fc=0：10-bit没有在输出端量化成8-bit。
422 的 GCP 显示24bit不能单独反推有效精度，须结合 formatter 与源帧读数。
VDIN0 HDR CTRL=0x1c040 bypass，VDIN1=0xe05e 映射，核彼此独立。

DMA 分配修复后的独占20秒网页窗口：H.264 3840×2160 **60.031fps**，
drop/lost/freeze/PLI 增量0，呈现 p95 18.2ms、最大36.9ms、无>50ms。
音频当时尚未重启，音频峰值0不计作声音验收。早先30fps窗口保留为失败数据。

还发现元数据不能只检查 EOTF：Mac 此次 RX/vframe 的 mastering/CLL 值全0，厂商 VPP
先将其改为默认色度和1000/50，再发 TX。候选增加保留原始 HDMI metadata 的路径，
包括合法的零值和单独为0的 MaxCLL/MaxFALL；不能混用解码器SEI的10000倍亮度单位。
T7 实际调用 `amcsc_pip.c:hdmi_packet_process()`，仅修改旧 `hdr_tx_pkt_cb` 不生效。
最终逐值读回与并行 H.264/H.265 验证另记下方，不将此前默认值报为正确透传。

第四轮 TX 实际读回：PQ、BT.2020、色度六值/白点/MaxLum/MinLum/MaxCLL/MaxFALL
全部0，与 VDIN 源帧 mastering/CLL 的零值一致，不再合成默认1000/50。
原厂 RX `pktinfo dump 87` 在 T7 的旧 FIFO/提取接口仅返回空缓存，本轮以实际
进入 VPP 的 vframe 和 TX 硬件 infoframe 读回核对，不把旧接口的空包当成有效源证据。
只读取逐个审阅过的 formatter/HDR 控制寄存器，没有扫 regmap/LUT。

第四轮物理动态灰阶/短音、60秒 H.264：**59.9953fps**、4K，
drop/lost/freeze/PLI 增量0；呈现p95 17.9ms、最大23.1ms、无>50ms，
网页音频峰值0.10318。EXTN→TX PCM 独立推进，peak3277、播放队列1280帧/48k≈26.7ms。
KVM三帧灰阶0/17/34/50…236/252，RGB中性通道一致，与单路径SDR基线相同；
证明KVM实际得到SDR，不拿截图证明显示器HDR光度或色差。
VDIN0 在88.646→159.481秒，完成帧3773→8023，约60.000fps，drop_cnt保持0、
drop_num保持启动时的2；VDIN1在活动采集窗口独立约60fps，drop_cnt保持0。
视频延迟估计仍为一帧采集完成+显示调度约16.7–33.4ms，不是光子端实测；
原生音画同步尚无物理测量，不用浏览器呈现间隔替代。

同一第四轮动态源、独占60秒 H.265：浏览器实际 codec=video/H265、4K **59.9913fps**，
drop/lost/freeze/PLI 增量0，呈现p95 17.9ms、最大23.9ms；音频峰值0.10172。
测试器退出时自动恢复原编码模式。实验阶段原生产 One-KVM 二进制 SHA256 为
`eb0409556e76f9316eee69f39dfb9e438508f4bdc23d85844ea948024a393f2e`；候选单独放在根分区，
SHA256 `f3c0404b4d9454b0168fd884a6a369bc6450d6ddda836007c295bcbbbba30569`。
该轮 UU host 在线、未新连客户端；后来04:40–04:47用户连接期间已有新 RTCP 回报，
丢包0、发送约60fps；接收机并行编译期间出现58.45fps，不作独占性能验收。

## 正式交付与短黑屏调查

用户目视认可后进一步批准 One-KVM 合入 `vim4`、原生候选成为默认，不再新增备份或回退项，
也不再测声音。各仓已合入推送：common_drivers `cb894fcbf`、One-KVM `24d35af8`、
manager `55158a0`。正式 One-KVM 从合入后干净主线构建，替换生产二进制；
私有标准 V4L2 插件随构建/组件包安装，不使用会关闭主 RX 的系统厂商插件。

使用 `packaging/kernel/promote.py --no-backup --native-hdr` 登记默认及透传资格，
完整模块哈希与候选一致后，自动登记当前模块 note，并保留同 release 的其他已验记录。
空间不足时显式淘汰未登记且无其他入口共用的旧 VendorPrevious 产物；保留现存其他入口，
未新增备份/回退脚本。Default、Image/initrd/dtb 别名指向 hdrdual1。
随后正常重启，实际运行/default 均为 `5.15.137-vim4kvm-hdrdual1`，
启动参数 `aml_media.vdin0_native_hdr=1`；正式 HDMI 启动器保留422 10-bit，
One-KVM 启动器自动选择独立 SDR capture；实验 `/run` 覆盖已移除。

面板“当前内核不支持”的直接原因并非此次 module note 缺失，而是旧 provider
只接受 `vdin0 vfm_cap amvideo` 串联路由，未接受原生 `vdin0 amvideo`。
同时修正原生显示仍依赖旧采集 `fmt_valid/vfm_started` 的假设，改读主 RX 状态机；
输出精度按原生 HDR 选择422 12-bit，状态区分真正 HDR 输出与 HDR→SDR。
重新部署后实际页面开关可用、显示“透传中”，API supported=true、running、
input.hdr=HDR10、output.hdrToSdr=false。此次未改前端布局/文案；此前 HDR→SDR
正常事实及不支持格式/异常信号说明使用已定稿版本。

用户提到的一次闪黑：04:40:57 UTC，RX 记录 colorspace 1→0、vtotal2250→2249、
frame_rate5999→5998、tmds_invalid→unready、READY→WAIT_CLK_STABLE，
04:40:58重新锁定；04:41又发生颜色/HDR重新协商，最后04:41:44恢复PQ。
同期无 TX `hdmitx_set_dispmode`、无 OUT HPD，测试图案早在04:36:38退出，
因此证据指向源/RX时钟与颜色协商，不是观察到的 TX 重设循环或图案退出；
无法仅靠这些日志进一步断言源端动作/线缆是根因。

正式默认重启后的无声动态灰阶、60秒 H.264：3840×2160 **60.0101fps**，
drop/lost/freeze/PLI增量0，呈现p95 18.0ms、最大32.7ms、无>50ms。
不创建音频分析器、不播音；仅只读确认声音服务 active。
随后复核发现 modeset 后 AVI 色域退回709，原观察提前结束；修复及重新验收见
[正式部署收尾](2026-10-25-native-hdr-production.md)，不把该窗口记作30分钟成功。

## 版本、验证与限制

内核 release `5.15.137-vim4kvm-hdrdual1`，来自独立 `linux-native-hdr-5.15` 树，
完整匹配模块和 initrd。第三轮仅旧 packet callback 的元数据修复未生效；第四轮加到 T7 PIP。
第四轮 tgz SHA256 `655146033a5f416b97ab43ed03200cda4b2064687d2a413e85b55a317dfe2d85`，
运行 aml_media note SHA256 `27835042af4f2305ff581d320058266606f3b2de8f776f97e3c0027aa2ccab4d`。
第一次 initrd 尚未生成完就尝试启动，sysboot 未找到配置，自动回默认 hdr1；随后改为等待
stage 退出成功、校验 initrd，再一次性启动；未遗留坏默认项。

One-KVM Rust全量746通过、2忽略，助手35项通过，修改文件 rustfmt 通过；全库 fmt
还报告其他既有文件格式差异，未顺手改动。驱动真实 C 函数 fixture覆盖借用 frontend
开关隔离、独立 HDR 核、NV21 位深和原始 HDR 元数据；checkpatch0错误、2警告
（新 Python 测试未加许可头，遵循任务约束）。完整内核构建通过。

当前显示器 EDID 只声明 PQ、不声明 HLG；无真实 HLG 输入，HLG仅离线分支覆盖。
不把 HDR10 成功宣称为 HLG 现场验收。尚缺原生双路径跨模式/热插拔长测、
MJPEG 独立支路接入及声音/视频物理同步测量；本次现场输入为4K60。
其他 KVM 应用未接入 VDIN1，不能把 One-KVM 通过当作它们的原生 HDR 支持证明。
