# 2026-10-25：VIM4 SRTP HMAC 后端正式接入

在[独立回放实验](2026-10-25-rtp-send-benchmark.md)之后，将 OpenSSL SHA1 状态实现接入
One-KVM 的 VIM4 构建。当前改动只优化 AES-CM 的 HMAC 计算，未改变编码器、协商策略、
RTP 分包、ICE 选路或逐包 UDP 接口；32 包批量发送仍是后续独立候选。

## 实现与验证

One-KVM `b6b8057c` 将 crates.io `webrtc-srtp` 0.17.2 原样纳入 `libs/srtp`，保留作者、
MIT/Apache-2.0 许可证与上游测试。相对原始 crate，协议源码仅 AES-CM 公共 cipher 模块
有改动。新增默认关闭的 `openssl-hmac` feature，由应用 `vim4` feature 显式启用；
只启用 OpenSSL AES 或普通桌面构建时仍使用原 RustCrypto HMAC。功能树见
`logs/hmac-production-features.txt`、`logs/hmac-desktop-features.txt`。

RTP/RTCP 分别预计算带 key 的 inner/outer SHA1 状态，每包复制后完成 HMAC，避免
逐包创建 EVP 对象。原实现本来就复用 ipad/opad；此次收益来自 SHA1 后端，不是新加
密钥状态复用。密钥派生、标签长度、常量时间认证、ROC、重放检查和 profile 均不变。
低层 SHA_CTX API 在 OpenSSL 3 中有弃用约束；升级依赖时需复核，不能在
`OPENSSL_NO_DEPRECATED_3_0` 构建中开启此 feature。见
[维护说明](../../One-KVM/libs/srtp/VIM4.md)。Debian 包同时安装该库两份许可证。

完整应用 release 单测通过：774 passed、2 ignored。SRTP 依赖自身测试另外运行，
新后端40项、OpenSSL AES加原HMAC38项、纯Rust38项均通过；新测试覆盖 RFC2202、
长短 key、SHA1 块边界、RTP ROC、SRTCP E/index 及重复复用，与 Rust 参考完整标签相同。
Linux 部署助手35项通过。原始日志为 `logs/hmac-production-app-tests-host-only.log`、
`logs/hmac-srtp-*-tests.log` 和 `logs/hmac-linux-deploy-helper-tests-board-path.log`。

最初三项 UU 桌面集成测试失败发生在 ICE gathering，尚未进入 DTLS/SRTP：测试传入空
ICE 列表，生产默认回退到公共 STUN，五秒超时。本机串行也复现。`68518957` 给这些本地
双 peer 测试使用仅 test 可见的 host-only 配置，保留生产回退策略和原超时；未跳过测试。
Mac 上部署助手测试依赖 Linux/root 环境，随后在正确的 Linux 板级路径环境中通过。
失败记录保留，不计为通过。

## 正式依赖的板端回放

5.15.137-vim4kvm-hdrdual6，测试进程固定自身 CPU0/1；既有频率与 governor 不变。
每种编码使用相同四个真实 4K60/30Mbps AU、生产 release/LTO、AArch64 cfg 与 VIM4 track 行为，
比较 feature 关→开→关；每窗口三组、每 case100帧。全部 complete/valid、失败段数0。
四组 codec/profile 完整密文 transcript 在三个窗口逐个相同，每包解密内容校验通过。
原始数据 `logs/hmac-formal-replay-{a1,b,a2}.json`，不是早期独立补丁的旧结果。

以下 P50/P99 单位 ms；每格合并三组共300帧，短窗口尾分位仅作离线对照：

| SRTP Context | 原实现 A1 | 新后端 B | 恢复 A2 |
|---|---:|---:|---:|
| H.264 AES-CM，48包 | 0.281 / 0.542 | 0.120 / 0.375 | 0.280 / 0.543 |
| H.264 AES-CM，220包 | 1.330 / 1.677 | 0.572 / 0.908 | 1.331 / 1.665 |
| H.265 AES-CM，48包 | 0.294 / 0.552 | 0.122 / 0.439 | 0.294 / 0.642 |
| H.265 AES-CM，224包 | 1.385 / 1.733 | 0.570 / 0.896 | 1.382 / 1.737 |

AES-CM 的 P50 减少约57%–59%，恢复基线后耗时恢复。未修改的 GCM 控制路径 P50 基本
不变，其 P99 跨窗口抖动明显，不将变化归因给 HMAC。这一段不含采集、编码、网络、
浏览器或显示，不能直接声称画面延迟减少上述数值。

## 实际发送链路

两种编码各做一次 A→B→A，物理 RTK HDMI 运动源、3840×2160/60、30Mbps、
Chrome 156.0.8078.47，每窗口视频预热15秒、像素读回预热3秒、正式120秒。
六次均实际协商 `SRTP_AES128_CM_HMAC_SHA1_80`，各取7200个完整发送帧；
浏览器约60fps，零 packetsLost、framesDropped、freeze、无效/不一致像素标记及
时钟跳变。各窗口有1037–1184个三带有效像素样本。期间无构建、解码或其他板端基准。

发送段直接按实测视频 SSRC 和 RTP timestamp 分组，按发送入口排序，要求序号连续、
无重复、仅最后一包有 marker，首尾均落在浏览器测量窗内。被排除的641–1126组/窗口
全部位于测量窗外，无包序或 marker 拒绝。无需离线解码或按相邻帧猜测跨级对应。
这个端点是首包 send 入口→尾包 send 入口：含中间包的计算、调度及逐包探针记录，
不含首包之前的 HMAC 和最后一次系统调用，不能称为纯 HMAC 或完整网络传输。
同板时钟直接计算发送时长；跨机校准只用于选择窗口，half-RTT 最大1.29ms。

以下是**相同实际包数**的 P50，单位 ms，括号为帧数；220包样本少，不以其P99作验收：

| 实际发送跨度 | 基线 A1 | 新后端 B | 恢复 A2 |
|---|---:|---:|---:|
| H.264，48包 | 2.296（111） | 2.098（168） | 2.257（141） |
| H.264，220包 | 10.551（16） | 9.673（15） | 10.500（18） |
| H.265，48包 | 2.263（125） | 2.084（138） | 2.277（182） |

48包帧 P50 减少约7%–9%，220包 H.264 约8%。48包的系统调用观测总时长（除尾包）
P50 各窗口仍约0.81–0.84ms，包间工作/调度/探针间隔之和由约1.42–1.43ms降至
1.26ms；220包相应调用约3.84–3.95ms，间隔由约6.52–6.64ms降至5.71ms。
这些是各指标独立中位数，不能将中位数相加声称逐帧严格分解；原始逐帧闭合已校验。
与 Context 回放一致，改善落在包间处理，系统调用成本仍较大。

全帧混合分布 P99：H.264 为10.507→9.387→10.226ms，H.265 为8.456→7.830→8.436ms。
大于等于180包的分组也下降，但帧大小分布不完全相同，仅作描述，不能替代同包数对照。
H.265本轮没有220/224包的共同样本，不拼凑与H.264的大帧比较。

编码段独立用同PTS配对：H.264入口→输出 P50 为12.367→12.362→12.366ms，
H.265 为13.197→13.197→13.200ms，没有编码优化证据。此次仍开启压缩AU临时内存盘
dump，独立记录开销 P50 为0.109–0.125ms、P99为0.377–0.594ms；不能把它记作零，
也不能从发送跨度机械扣除。每包事件记录的开销仍包含在包间间隔中。

源端开始绘制→浏览器软件呈现 P50：H.264 为67.598→67.507→67.551ms，
H.265 为68.095→68.014→68.056ms，尚未检出明确的整链路中位数改善；不是光学测量。
浏览器候选窗口把远端报告为地址隐藏的 prflx，基线报告板端host地址，未做本轮逐包
网卡抓包，不能声称已证明全部窗口的物理网络路径一致或给出网络分段收益。
本轮每codec仅一组A/B/A，未完成三组重复、30分钟同连接和压力矩阵，不能称为正式
端到端性能验收。原始 `logs/hmac-live3-*`，独立汇总 `logs/hmac-live3-summary.json`、
`logs/hmac-live3-transport-summary.json` 和各窗口 `*-latency-summary.json`。

最初两个基线pilot被诊断探针中断，分别为 RTLD_NEXT 看不到 GStreamer 局部加载库，
以及回退查找误用了不导出函数的 libamvenc_api.so；均未进入候选测量。改用已经加载的
libamvenc.so 后六窗口通过，失败记录保留在 `logs/hmac-live{,2}-run.log`，未纳入对照。
每次退出均恢复原二进制，首轮后另做 H.265 冒烟通过；对照结束时无探针drop-in，原文件SHA256
恢复为 `3e0c82ac311557afaf0c1471d79cdcbcb00af599f006d529b80ea1131e3dbf72`，
HDMI服务PID1094未变，内核仍为5.15。

## 安装包交付

随后按标准流程从干净源码完整冷构建，不把诊断二进制直接留作生产文件：

```sh
python3 tools/ubuntu-build.py package --component onekvm --version 2.5.1+vim4.20261025.20
python3 tools/ubuntu-build.py verify --component onekvm --version 2.5.1+vim4.20261025.20
python3 tools/board.py deploy --exclusive --packages build/packages/2.5.1+vim4.20261025.20 --kernel 5.15.137-vim4kvm-hdrdual6
```

来源为 One-KVM `b6b8057c`、主仓库 `2d721d5`，实际镜像及完整树哈希见包内
`sources.json`。重新构建前端、私有GStreamer插件、DMA helper，debug应用单测再次
774 passed、2 ignored，部署助手35项通过。隔离包验证通过校验和、ARM64 ELF、动态库、
sudoers、配置保留、损坏文件拒绝、更新feed、真实dpkg锁争用、升级、同版本/降级拒绝、
认证更新API与安装重启。两份SRTP许可证均在deb中，包内来源元数据与外部一致。

最初省略版本生成的开发号基于较旧的已发布版本，低于板端；安装前已主动终止该构建，
未安装，日志为 `logs/hmac-official-package-outdated-base.log`。正式包实际部署时漏传
`--kernel`，安装已完成，随后默认7.3的板级检查在5.15上退出1；未重复安装，改为
`tools/board.py check --kernel 5.15.137-vim4kvm-hdrdual6` 后通过。上例列出完整正确参数。
部署等待循环访问管理器根路径得到401并多等15秒，公共auth/state端点正常；不是服务
未启动。实际安装与复核日志分别为 `logs/hmac-official-deploy.log`、
`logs/hmac-official-check-515.log`，不把首次命令退出1记成成功。

最终已安装 One-KVM `2.5.1+vim4.20261025.20`，二进制SHA256与包内相同：
`b0a48759cd6cd3d42755364fab0ea538f59b6c256ef294f6ae3d5c23b634e527`。
保留另一任务刚部署的 manager `2.5.1+vim4.20261026.1`。内核仍5.15，HDMI服务PID1094
未变，原视频/stream/audio配置逐项相等，恢复H.265，WebRTC session_count=0。
临时探针、板端私有备份/基准目录、采集tmpfs均清理，无探针映射或drop-in。

实际安装包另用物理HDMI运动源和指定RTK音频设备的440Hz脉冲验证：H.264/H.265均
3840×2160、约59.99fps，15秒窗口零丢包/掉帧/freeze，两者解码音频峰值分别0.1019、
0.1014。它证明非静音互通，不是音频长期连续性或光学延迟验收。补充MJPEG冒烟返回400，
原因为既有UU配置锁定H.264/H.265；该行为在原基线源码也存在，未关闭UU或修改配置，
该项未计通过。原始 `logs/hmac-final-{h264,h265}.jsonl`、`hmac-final-mjpeg.err`、
`hmac-final-settings-check.json` 和 `hmac-final-cleanup-check.json`。真实UU客户端本轮未复测。

主仓库259项测试通过（7项按环境跳过）。本轮源码已提交，尚未推送；未启用批量UDP、
编码fast packing或超频，也未把单段改善称为端到端性能验收。
