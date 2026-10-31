# 2026-10-31：原生 HDR 最小主路径验收与合入

按用户最终收敛范围，只完成原生 HDR 必要主路径及主线合入；不启动其他应用扩展、
新截图功能、透传、解码或额外 GPU 调优。GPU uhd5 的独立验收与锁见
[正式集成记录](2026-10-31-uhd5-main-integration.md)，本次保留其全部产物身份。

## 已验结果

Panfrost / 私有 PanVK 26.2.6，M6 同源 HDMI 3840×2160 PQ 60 Hz，
One-KVM Wave5，Chrome 156.0.8078.74 视频专用 WebRTC 接收；无测试 HID 或音频轨。
r13 使用最新 main 工具，只 RAM 启动，sampling on 后采样约 30 秒。

| 门禁 | 结果与证据 |
|---|---|
| 真实十位 DMA | 复用 [r6](2026-10-31-hdr10-remote-r6.md) 的 AMLY / GPU P010 高精度数据证明，未重复读帧 |
| 实际接收与 SDP | 3840×2160、1798 新解码帧 / 30.002 秒 = 59.929 fps；profile-id=2，零丢帧、零冻结 |
| SPS / VUI | 独立 FFmpeg trace_headers：profile_idc=2、Y/UV bit_depth_minus8=2、9/16/9、limited |
| prefix SEI | IRAP 前 type 137 / 144，各 24 / 4 字节；与本次 V4L2 HDMI metadata 逐字节一致，源全零即保留零 |
| 模式恢复 | 原生 HEVC → HDR2 映射 H.264 短接收成功；之后关闭源 HDR 并正常恢复 SDR |
| CMA / 内核 | 停服务前后 CmaFree 均 497108 KiB，taint=0，无新增内核 WARNING / fault |
| 收尾 | 正常一次回 5.15、四服务和 UDC configured、18 项保护哈希不变，M6 HDR关、Chrome原前台恢复，票据/隧道释放 |

浏览器显示回调间隔 p99=33.4 ms、p50≈16.7 ms，是该接收端回调端点；
不当作端到端延迟，也不以 r6 受 heavy 干扰的 19.38 ms 数据替代。
本窗约 14 分钟，包含回退后截图冷启动超时的一次只读重试；未重放 HDR 点击。

原始证据在主工作区 `logs/hdr10r13/`：`hdr-candidate-encoded.json`、
`web-prefix-0.h265`、`web-headers.log`、`hdmi-metadata.json`、`bitstream-proof.json`、
`cma-restored.json`、`returned-baseline-identity.json`、`restored.json` 及逐步截图。
码流/截图含源桌面，不提交原始图像或码流；仓库保存摘要与哈希。

## 同源基线与最小修复

复用同日、保护哈希匹配的 5.15 `logs/hdr10r7/` 基线：真实 Main10 / 十位 / 9/16/9 limited，
约 59.98 fps。已取 8192 字节随机访问前缀未见 HDR SEI，只能说明该前缀；
不能宣称整个 5.15 产品流没有 SEI，也不能声称两者静态元数据相同。

[失败记录](2026-10-31-hdr10-remote-r7.md)保留 r7b–r11 的真实失败，不覆盖为通过。
最终必要修复包括 P010 裸 caps、完整 PQ TRY_FMT、Wave5 CAPTURE 颜色约束延后，
以及以运行库 ISO transfer API 解决厂商 libgstvideo 枚举 ABI 差异。
后者已分别链接标准库和板上同哈希厂商库执行实际 C 函数回归。
服务路径补 reserved heap 的 video 组权限，允许原生 videorate 从测得的分数帧率输出整数 60 Hz；
保留正式 HDR2 DMA lease 预算。r12 已收到 Main10，但 SDP 仍声明 profile 1；
r13 去掉该处旧 Vendor 限定，离线两后端回归与实际 profile 2 接收均通过。

## 来源、封存与边界

- 内核 `vim4-kvm-7.3`：`dc220366a1222a03423d5b5987fab3f027ec1d7a`。
- capture `main`：`b43e564595407b0b637a23f49a3cb390d4a6cbfa`。
- One-KVM `vim4`：`2cf9ef4da71f5572173cabe3c60c58730a1d539f`。
- 完整组件包 `vim4-hdr10r13-uhd4-pq.tar.gz`：
  `7ee9314379de21cf8ed900cb2a72369d73b1af795ac06dc0657e233f75e2e9f3`。
- RAM 包 `hdr10r13-uhd4-pq-ram.tar.gz`：
  `988c65275305f01ef893bbdd056fe67b44177c6be4c4c5407ffaacb7dffa85f8`。

两份归档已复制到构建 VM `/home/deepdream/build/hdr10-final/` 并逐个复核 SHA256；
本地工作区 `build/` 同时保留，未发布 Release。

沿用同一 Image / DT / 2338 个匹配模块，release 为 `7.3.0-vim4kvm-hdr10r3+`，
build ID 为 `e1028db19a35ed0ba3edf23a0edf57f32466b2e5`，新 payload ID 为 `hdr10/r13-pq`。
[独立运行时锁](../../packaging/hdr10/native-runtime.json)保存源码、封包和完整模块清单摘要；
封包时的 hardware_validated=false 保持原字节，验收证明另存，不重写已封存归档。
uhd5 的 Image / DT / 外部模块 / BTF 锁不变，未把本候选模块混入 uhd5。

本轮未验：UU 实际客户端、kbase 原生 HDR 对照、其他三款应用、原生期间 SDR 截图、
非零或动态静态元数据、HLG、运动画面精度、长稳和端到端性能。
相关用户选项默认关闭，能力仍按格式/controls/插件探测；不按内核名自动开放。
本次不代表四应用全部 P0 完成。上述范围不再排队，合入 push 后停止。
5.15 默认启动不变，未发布 GitHub Release，未刷 U-Boot 或推送 vendor blob。
