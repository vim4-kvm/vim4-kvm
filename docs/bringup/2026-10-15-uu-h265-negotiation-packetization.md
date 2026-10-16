# 2026-10-15：UU H.265 协商与封包修正

One-KVM `10247267` 增加自动/H.264/H.265 选择、配置持久化及当前会话编码显示。
默认自动：按活动视频 SDP 的 payload 列表、Main profile 与其他共享服务限制选择
H.265 或回退 H.264；固定编码不兼容会拒绝连接。活动 UU 会话固定共享编码器，
关闭时释放，其他服务的配置验证考虑协商结果。真实 WebRTC SDP 单元回归验证
同时提供 H.264/H.265 时答案只选 H.265；浏览器验证选择保存及应用重启恢复。

首包 `.8` 通过 603 项 Rust 测试、前端与发布构建、完整包验证，但官方客户端
上板黑屏：协商 H.265、板端约 60fps，观看端不断 PLI 请求关键帧，没有解码统计。
检查 rtp 0.17.2 默认 HevcPayloader：只识别类型 19 的 IDR，忽略类型 21 CRA；
存在四字节起始码时不再识别同一输入内的三字节起始码，且整倍数分片末尾标记有误。
历史硬件 H.265 20Mbps 码流包含 1 个类型 19、14 个类型 21，不能仅验证 IDR19。

`1a7fd9e5` 改为复用网页已用的 H265Payloader，经 TrackLocalStaticRTP 发送并保留
UU RTP 帧扩展；H.264 路径保持 sample track。新增 CRA、混合起始码、整倍数
分片末尾、序号、时间戳与 marker 回归，604 项 Rust 测试及 ARM64 release 通过。
修正版 `.9` 完整包验证通过并已上板，服务 active、HTTP 200、dpkg -V 无差异、
UU host online。官方客户端复测仍显示“正在传输画面”但黑屏；板端约 60fps，
客户端解码统计为空并持续请求关键帧。封包修正尚不足以恢复出画面。
未进行长期运行、其他平台客户端或 H.264/H.265 端到端延迟对比。

制品：`build/packages/2.5.1+vim4.20261015.9/`，deb SHA256：
`98d8b3dc01fef224de428be62113a8d3dba3659ca3a4c7ea2819c15e9a731bf2`。
证据：`logs/uu-remote/hevc-{tests,frontend,browser,package-verify,session}.log`、
`logs/uu-remote/hevc-packet-{tests,release,package-verify,deploy,after-deploy}.log`。

继续排查发现 webrtc-rs 保留 codec preference 中非零的 payload type。原代码在
set_remote_description 前筛选 H.265，将服务端默认 126 固定进偏好；客户端使用
其他编号时，答案仍错误地给出 126。回归将客户端 H.265 编号改为 104，旧实现
确定失败；`894aa390` 将筛选移至应用 offer 之后，答案及 sender 参数均为 104，
604 项 Rust 测试通过。仅记录协商编号，不记录原始 SDP、凭证或用户输入。
本机官方 UU 4.39.1 libstreamer 离线检查接受历史硬件码流的 SPS 和 VideoToolbox
格式描述；这只排除该样本的参数解析失败，不能替代实际客户端播放验证。
证据：`logs/uu-remote/hevc-payload-{regression,tests,release}.log`。

`.10` 完成 ARM64 发布构建、完整安装包验证（含真实升级、配置保留和认证更新
API），03:47 UTC 通过单应用更新助手上板并重启。服务 active、HTTP 200、
dpkg -V 无差异、UU host online。官方客户端再次反馈仍停在“正在传输画面”，
因此 `.10` 仍未通过 H.265 上板验收。
制品：`build/packages/2.5.1+vim4.20261015.10/`，deb SHA256：
`c0303970657d7390f49d712cd070bbd75f690a4bc7ddf0c7e64f364b048c2838`。
证据：`logs/uu-remote/hevc-payload-{package-verify,deploy,after-deploy}.log`。

现场只提取 SDP 编码/方向/轨道属性，未保存原始 SDP 或凭证：官方 offer 的 H.265
编号为 96，无 fmtp，五个接收视频 m-line；答案和线上媒体均为 96，媒体 SSRC
对应首个视频 m-line。只统计线上包头的 3 秒观察有 180 个视频 marker，仍无
客户端解码统计。官方 libstreamer 的离线 H.265 解包器接受参数集 AP、IDR/CRA
首分片；其 Annex-B 转 CMSampleBuffer 函数加 macOS VideoToolbox 能解出历史
硬件样本的 IDR19 和 CRA21 首帧。这些排查没有定位现场黑屏的剩余原因。

03:58 UTC 将板端 UU 偏好临时设为 H.264，保留其他配置、凭证和 `.10` 安装包。
新会话确认 H.264，03:58:49 官方客户端回报 decode/render 59fps、decode 2ms、
current/target delay 13ms、jitter buffer 3ms；板端稳定窗口约 60fps。
H.265 代码与选择项仍在开发分支，自动模式仍优先 H.265，不能作为已验收默认
发布或认为全新镜像验证通过。现场记录：`logs/uu-remote/hevc-payload-session.log`。
