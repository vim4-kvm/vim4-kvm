# 2026-11-01：HDR/r14e、MAC 与 One-KVM 音频最终合入

用户最新明确要求“把这两个task的都合到主线去吧然后关闭掉”，授权六组件正式分支及
主仓 main 收尾合入、push，覆盖此前等待听测确认的合入限制。
**这是合入授权，不是用户确认所有功能已经实测通过。保留未验边界并停止后续任务。**

## 正式源码与来源锁

全部使用原 `p0-5-native-hdr` 独立工作树，fetch 核对远端后按下表快进，无冲突，
不重写提交、不强推、不切换或修改主工作树及其他会话工作树。
gst-venc 工作区只有 Khadas upstream remote，正式 fork 用下表仓库 URL 直接核对、推送，未改 Git 配置。

| 仓库 | 正式分支 | 原远端 | 合入终点 |
|---|---|---|---|
| gst-plugin-venc | vim4 | b3b82a98cac16c4e845fad6357189b57cf8b2db4 | 3a74cc9c0f074ff8bf980440e426438bba65d1db |
| gst-plugin-vfmcap | main | b43e564595407b0b637a23f49a3cb390d4a6cbfa | 5de382e36350fc37b43d9ff11f693fa3f2bb0323 |
| NanoKVM | vim4 | 63fa80f6b03d26d7bf0c66abe8fbfb81793b7183 | 0525dea7d5d2417b3b5c5eee754f026d9ca4c671 |
| kvm (JetKVM) | vim4 | f2b8122505cacda2762948a91c99c1acdb107ef0 | 166719c5b8acdfb1ab995c440aabc8a0e39ae08d |
| One-KVM | vim4 | 2cf9ef4da71f5572173cabe3c60c58730a1d539f | dae5089fc59aa069399539fa304412c37f0c3f08 |
| ustreamer | vim4 | 8d8a4eec16e774422e67168b221142ec052b46ad | 97eb951d10a0ccebd312d6951acc91624f5f0876 |

以上仓库均为 `https://github.com/vim4-kvm/<仓库名>.git`。
主仓从 `origin/main=5d27a22a3cbb385b4ec3a2177bc279ff475dd276` 快进至包含本记录的提交，
纳入持久安装、217c9e4 MAC generator、音频部署记录及各次恢复工具审查修复。
`workspace.toml` 六组件开发来源锁更新为上表终点，不修改其他组件或内核来源。
`packaging/kernel-edge/sources.toml` 的 uhd6 tested_build/retained_runtime 和
`packaging/hdr10/phase2-sources.json` 的 r14e 原始组件/程序哈希保持原样，代表历史封包而非新构建。

## 当前已部署身份与封存包

合入收尾不进行任何板上操作。沿用既有安装证据：默认/运行 uhd6/kbase，
内核 `f951e2d24d32d5df0e701e7c355b3db4c91eaf74`，GNU ID
`48106f6f9fb09b12d1eaf6a5fe91953dba53d9cb`，2341 匹配模块，Panfrost 选择保留。
入口 `http://192.168.50.210`，MAC `c8:63:14:74:70:0d`；这不是本合入轮次重新测量的状态。

| 封存对象 | SHA256 |
|---|---|
| uhd6 正式内核归档 | 7e68dc27e46bb270d561f4307bba1cd947152ee3813a0a926f817f11f8e9dfc6 |
| r14e 原用户态归档 | 9069fc083a8afe1a139e6d3e5eb725c608afafb4245ec3b155f873fd3f4a5b90 |
| r14e 持久安装包 r1 | 034ace4fb6a041029ec17a353e02d83e1bf89c183c6751c52b0bf263b84c4897 |
| One-KVM 音频 overlay r1 归档 | 70e961e33abb57f0362b56e1b4f6f2455c7d37ceb3ab0143b4a27a21621ae12d |

r14e 的 `/opt/vim4-kvm/hdr10-r14e` 40 文件/收据未改，其中原 One-KVM 来源为
`50f0b4d433c0ebb8c83f806f49084622547afe99`，原程序 SHA256
`79678cbff6ab7885de3fb0aff6f3c9ec229ea63aa1f217e7ebafb12853d6162a`。
当前独立 `/opt/vim4-kvm/one-kvm-audio-dae5089/one-kvm` 来源为上表音频提交，实际运行 SHA256
`a7942537db1504a57969011cfc5df8ab0529eaa744c52328ba38d6d7176e1e8a`。
runtime-build 的 overlay、commit、哈希及 `/etc/vim4-kvm/one-kvm-audio.json` 已记录差异，
不能将新音频程序算进旧 r14e 包或改写其封包哈希。

## 验证与明确未验范围

本轮只有来源锁/状态文档改动，合入无冲突；组件未新增代码，不重复编译、板测或完整矩阵。
主仓最终完整 unittest 日志 `build/p0-5/p0-final-merge-unittest.log`，451 项、15 跳过，其余通过。
组件复用既有构建、定向回归与独立审查，完整证据见
[阶段二记录](2026-11-01-hdr10-phase2-uhd6.md)、[安装](2026-11-01-hdr10-r14e-installed.md)、
[MAC](2026-11-01-ethernet-mac-handoff.md)、[音频](2026-11-01-onekvm-audio-source-recovery.md)。
音频 VIM4 lib 830 通过/4 忽略、部署助手37通过；真实 API/旧数字配置及60秒现有采集推进/XRUN=0通过。
非 VIM4 check 的既有 RKMPP SDK 缺失阻断仍保留，不写为通过。

Panfrost One-KVM 180 秒样本、r8 短样本的实际时长与共同 payload 身份仍按阶段二原始记录，
不把不同归档 r14e 的短健全检查称为新的180秒验收；Nano/Jet 八份保留码流不重跑。
Pi 引用修复后的有限 VDIN 池持续映射/JPEG/往返、kbase 原生 HDR、UU 真实原生客户端
HDR 渲染/独立解码帧率和停止后 CMA 仍未证明。RR 或官方窗口呈现不替代客户端 HDR 证明。
非零静态元数据/HLG/动态 HDR 无真实源的未验边界保留，不能将5.15前缀未见SEI写成元数据相同。
音频重复物理源切换/听感仍未确认；数字静音与无订阅者的现有计数器不证明音质。
低分 AS-1（4分、部分 PATCH 数字名响应）及既有 SIGALRM 兼容边界（3分）只登记，不扩改。
180秒样本复用说明 E1（4分）按原审查约定保留。

未发 Release，未切默认启动，未新增板上操作、测试矩阵或功能。所有既有工作树与证据保留，
停止后续工作，由协调者关闭 workers，不自行关闭终端。
