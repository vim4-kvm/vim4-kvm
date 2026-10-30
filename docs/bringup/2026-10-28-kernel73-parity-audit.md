# 2026-10-28：7.3 对当前 5.15 功能的差距复核

7.3 已有可工作的 SDR KVM 链路，但不能替换当前 5.15 后保留全部功能。
优先缺口为原生远程 HDR、本地音画透传、HEVC 尺寸与画质控制、高刷/VRR，以及 NPU。
本轮只读源码、历史证据和运行版本；没有切内核、停服务或执行硬件实验。

## 比较对象与口径

| 对象 | 本轮核对的版本 |
|---|---|
| 正在运行 | SSH 实读 `5.15.137-vim4kvm-hdrdual6`，`one-kvm.service` active |
| 5.15 源码 | Linux `80a07ad5406d`，common_drivers `6558c1eee6d5` |
| 7.3 保留运行时锁 | `sources.toml` 的 `b1300eb808f43`，M0 DTB，build ID `eeddb005df059a850853876d52ef603aa1af192b` |
| 7.3 正式源码 | `vim4-kvm-7.3@213f271505411845eecb3c6ef10df7565b895ebc`，工作树干净 |
| 共享应用 | One-KVM `c1200faa0898`；其他应用与插件沿用当前工作区源码 |

正式源码工作树在 VM `~/src/linux-7.3-hdmi-integration`。
`~/src/linux-7.3` 当前实际是颜色分支 `c24465df1dd7`，不能把该目录的 HEAD 当正式分支。
本轮以 `git show`/正式工作树读取，不检出或覆盖任何分支。

以下“缺实现”指源码/应用合同确有缺口；“待交付”指实现已有但未形成匹配部署；
“待验证”不能当作已知故障。旧[厂商全能力表](../parity/README.md)的97项分母包含
大量扩展硬件、解码和音频处理，不等于当前KVM产品的功能数，也不能用旧百分比判断是否可切换。

## 当前使用会遇到的差距

| 优先级 / 功能 | 核对结果与影响 | 下一步完成条件 |
|---|---|---|
| P0 原生远程 HDR | **缺实现**。7.3 VDIN 暴露 NV12/RGB24；Wave5 输入格式表没有 P010。内核虽有 Main10 profile 枚举，不构成十位输入链路。One-KVM 的 `hdr_remote_available()` 仅允许 Vendor，Wave5 管线明确 NV12/BT.709/Main。不能保留5.15网页和UU的PQ/BT.2020十位输出 | 接通原生高位深DMA、编码输入和色彩/元数据能力，再接四应用及UU；HDR↔SDR、缩放、截图并行验收 |
| P0 本地 HDMI 音画透传 | **缺产品接入＋待验证**。保留运行时是M0/simpledrm；显示、视频平面和reader退休实现已随`de26c7df1ce47`、`274d7c33a45fe`进入正式源码（透传、M3分支无未合入提交），但只在实验M3/M3-video DTB启用。当前manager透传provider只接受5.15；缺的是把采集帧交给显示、能力查询和RX→TX音频桥组成的产品链路，不是内核没有显示或TX声音输出 | 单一采集队列向编码/显示共享帧租约；真实stride/UV offset、显示退休后归还、60fps、拔插/变模式、独立RX→TX声音验证 |
| P1 HEVC 非8对齐可见尺寸 | **待交付**。正式源码有padding/conformance window且候选码流已验；保留的b1300eb内核不含该能力。当前One-KVM仍用`wave5_requires_h264()`在宽高非8倍数时回退AVC，不能仅更新内核就算功能恢复。未合入分支`vim4-wave5-visible-hevc@20d8010d`删除了回退，但未探测内核能力，旧内核上会停滞 | 匹配新内核部署；应用探测旧/新内核能力后选择HEVC，覆盖1366×768、1440×900等实际内容与连续切换 |
| P1 1080p/1440p高刷、VRR | **应用限制＋待适配/验证**。One-KVM `h26x_frame_rate()`把Wave5输出限制在60fps；公共`vim4v4l2src`caps固定60/1。RX允许20–120Hz固定时序只是准入范围，未见VTEM/VRR解析及基准帧率处理，不能沿用5.15已验VRR结论 | 先分别完成固定120Hz输入、编码吞吐与实际呈现；再补VRR时序租约/基准策略，避免变周期误判失锁。硬件120能力尚未据此否定 |
| P1 HEVC 固定QP／无损 | **缺应用接入**。当前API只对Vendor报告可用；Wave5遇到保存的画质偏好明确退回码率控制。正式内核已有HEVC MIN/MAX/I/P/B QP、CQ码率模式及`V4L2_CID_MPEG_VIDEO_HEVC_LOSSLESS_CU`（`wave5-vpu-enc.c:1256`→`wave5-hw.c:1922`，b1300eb亦有；要求关闭RC并开transform skip）。缺口在应用接入与T7固件实际无损验证，不能把QP=0称无损 | 将真实支持的标准控制接到应用；固定QP解析实际slice，无损逐样本比较，复核共享网页/UU/SRT输出 |
| P1 输入格式与原始采集 | **缺实现＋待验证**。7.3明确拒绝HLG、隔行、像素重复及部分HDR色域；未暴露原生YUV444采集格式。RGB24不等于原生444 planes。动态RX解析8/10/12bit，但真实12bit源未验、最终输出仍8bit | PQ与HLG分别处理；真实深色源和单像素色度验证。传统隔行需场序/去隔行；不是删除拒绝条件即可支持 |
| P1 新板 NPU | **缺实现**。7.3所有现存分支均无ADLA驱动与DT节点；5.15已在本板用`/dev/adla0`完成分类和文字识别，不再只是芯片宣传能力。该证据来自独立probe，四套KVM应用本身没有NPU功能，属BSP能力欠账而非KVM产品退步 | 匹配板型的ADLA驱动、SDK、DMA/PM与模型结果；不能拿旧板Vivante/Galcore代替新板ADLA |
| P2 管理器 GPU 利用率 | **缺接入**。当前历史采样读取厂商`/sys/class/mpgpu/utilization`；Panfrost没有该接口时显示暂无数据。Panfrost已有devfreq忙闲统计和fdinfo `drm-engine-*`（需开profiling、按客户端近似），缺的是管理器接入而非数据来源 | 增加Panfrost后端并核对空闲、负载、采样窗口及缺失恢复 |

源码锚点：One-KVM `src/platform/vim4.rs:33,353`、
`src/platform/vim4/video_backend.rs:65`、
`src/video/pipeline/shared/vim4.rs:57`、同目录 `vim4/wave5.rs:49`；
gst-plugin-venc `wave5/gstvim4v4l2src.c:50`；
manager `deploy/vim4-passthrough:151`、`internal/board/history.go:71`。
Linux行号固定上述213f2715：`t7-vdin-test.c:1578`、
`wave5-vpu-enc.c:56`、`t7-hdmirx.c:839,1161`，均相对各驱动目录。

5.15对照证据：[远程HDR](2026-10-26-remote-hdr-modes.md)、
[四应用HDR缩放](2026-10-27-all-kvm-hdr-scale.md)、
[本地双路径](2026-10-25-native-hdr-dual-path.md)、
[HEVC画质](2026-10-27-hevc-quality.md)、[高刷](2026-10-26-1080p120.md)、
[真实VRR](2026-10-26-vrr-live.md)、[NPU](2026-10-27-npu-inference.md)、
[GPU趋势](2026-10-27-manager-gpu-trends.md)。各条只沿用其明确验收范围，
不将5.15未验的Safari HDR、HDR120或任意12bit也列成7.3已知退步。

## 已可用但仍欠匹配部署或完整验收

- **SDR四应用和基础USB不是缺失项**：10月25日同一7.3运行时上四应用两轮共8次切换均解码4K约60fps；
  HID/只读可写虚拟介质、NCM/ECM已有实测。不能把它写成“只有One-KVM能用”。
  [同板记录](2026-10-25-kernel-video-latency.md)、[USB](2026-10-22-p2-usb-audio.md)。
- **采集测量误拒绝的修复已合入，保留运行时尚未包含后续版本**：213f2715包含FDET与TOP四窗口修复，
  旧b1300eb在后续采集中仍观察过ERROR；四档各约610秒、0 ERROR属于候选证据。
  不能据浏览器解码60fps推断所有原始帧有效，也不能把旧误拒绝继续列为正式源码完全未修。
  lowclock分支仍未合入，38场景矩阵不是全过。[合入](2026-10-24-hdmi-integration.md)。
- **输入恢复、音频与故障恢复需扩大验证**：7.3已有source-change、PCM XRUN/重开、Wave5受控复位与失败隔离，
  并非没有恢复实现；真实固件硬锁、长期多源、全采样率、并行读写仍欠验。
  5.15最近48次四应用尺寸/PQ往返不自动覆盖7.3；近期UU官方客户端、SRT/RTMP并发和音频低频诊断也没有7.3专项硬件复测。
  [恢复记录](2026-10-27-signal-recovery.md)、[共享输出](2026-10-27-shared-broadcast.md)。
- **USB扩展功能**：One-KVM USB ACM虚拟串口在Wave5后端被应用拒绝（`src/platform/vim4.rs:228`），匹配`uhd1.config`未启用`CONFIG_USB_CONFIGFS_ACM`，5.15有实现；UAC2有枚举、缺主机实际录音；Windows RNDIS描述符/传输、运行中host/device角色切换、
  remote wake、完整TCPM仍未对齐。现有5个IN端点预算同样限制5.15，不是升级额外引入的缺陷。
- **性能没有整体优势结论**：10月25日同SDR软件端到端约68ms，两个内核接近；没有同画质、三组A/B/A和长期数据，
  不能承诺换7.3更快。该历史表与当前5.15后续优化也不是同一源码基线。
- **发布锁与正式源码不同步是待交付项**：`sources.toml`仍固定b1300eb，`build.sh`严格检查该revision；
  直接对213f2715运行该锁定构建入口会拒绝。应在新完整Image/DTB/modules、应用和九类回归通过后再更新锁，
  不删除保护或把实验DTB默认启用来掩盖差距。

## 更广的厂商能力仍有欠账

这些属于追平整个BSP的任务，不都阻塞当前KVM使用：硬件视频解码尚无可交付正确首帧；
ARC/eARC（CEC已有正式驱动并在实验M3 DTB启用，收发未验）、VDIN1 writeback、GE2D通用blit、完整显示planes/AFBC/色彩输出；
TDM/SPDIF/PDM、loopback/ASRC/AED/VAD、DSP的板级端点与实际声音；
GPU逐频调压、整机suspend/resume和唤醒（Wave5已有runtime PM但T7保持上电，RX/Wave5主动拒绝系统睡眠）；Wi-Fi历史固件崩溃根因、P2P真实传输、
Bluetooth、PCIe/NVMe、存储模式/吞吐及MIPI/ISP等扩展外设。
分项继续看[总表](../parity/README.md)，不将未接线外设或缺授权的Dolby/HDCP当作当前可用功能。

音频routes、平台PM、VDEC、显示颜色/透传、Wave5尺寸等引用，经`git rev-list --left-right --count`
确认已全部进入213f2715历史；**源码合入不等于启用或上板通过**。
VDEC/高级音频保持disabled DT，CPU idle/GPU cooling仅实验profile，显示接管仍需显式M3。

## 本轮纠正与验证

旧`docs/kernel.md`把7.3 M0旧版本写成“板上当前”，与本轮SSH实读不符，已改为历史记录。
7.3风扇阈值也不是缺实现：b1300eb和213f2715的`khadas_mcu_fan.c`均有
`trigger_temperatures`读写，manager helper及硬件状态页已有7.x后端。
`docs/kernel.md`旧“阈值接口未迁移”描述已修正；不能只凭早期文档把这项列入开发待办。

在正式213f2715干净工作树重跑6项现有host回归，全部退出0：source events、timings、audio、
HDR curve事务、Wave5 geometry/SPS、quiet fan。测试编译/执行实际宿主函数夹具，
不加载模块、不打开设备；不是新增功能或硬件验收。
VM证据在`~/build/kernel73-parity-audit-20261028/`，本机副本在
`logs/kernel73-parity-audit-20261028/`。本轮没有重建内核或运行KUnit/完整69项内核夹具。
主仓文档变更按提交前全量离线unittest检查，结果见同目录日志。

建议顺序：先形成包含已合入RX/Wave5修复的匹配7.3候选并回归基础KVM；
随后补原生HDR和本地音画透传，再处理HEVC尺寸/画质、高刷/VRR及NPU。
每项分别完成源码、应用能力探测和真实内容验收后，才算可以替换当前5.15。

10月30日只读复核修正：补无损控制、未合入的One-KVM尺寸分支与USB ACM缺口，细分透传、GPU、CEC、PM与NPU表述；
主要缺口判断不变。核对版本为213f2715、b1300eb及One-KVM `8a39b619`，未上板。
