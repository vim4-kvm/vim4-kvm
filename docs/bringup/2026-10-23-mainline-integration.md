# 2026-10-23：统一合入主线，保留 eeddb005 正式部署

用户结束功能开发，要求将可交付源码合入生产分支并验证。本轮不启动候选、不安装
新 Image/DTB/modules 或应用、不改默认启动项，不移动已部署版本锁。
历史上板证据不冒充本轮新验收。
任务从 10 月 23 日持续到本地 10 月 24 日凌晨；收尾 HID/视频证据属于后者。

## 分支盘点与取舍

起点：内核远端 `vim4-kvm-7.3@8b2553f7b3c62`，本地主工作树原为
`0196fe22ecf01`，先快进；主仓 `main` 快进至 `3be5e0b`，所有记录分支的提交
均已在其历史中。One-KVM 生产分支先快进至 `672b8fd9`。

| 仓库 / 分支 | 处理与边界 |
|---|---|
| 内核 `maintenance/upstream-20261023@ca0e6c12862c6` | 合并 `94a122b698536`，入口修复 `c740ce633db55`；schema、MAINTAINERS、Kconfig 说明；无冲突 |
| 内核 `vim4-wave5-encoder-parity@9d33f6ad27898` | 已在远端起点历史中，无剩余提交；本轮后续完整构建覆盖该代码 |
| 内核 `vim4-display-m2@2cc04af44e3d4` | 已在起点历史中；M3 包含后续变化，独立 DT profile 不替换正式 M0 |
| 内核 `vim4-display-m3@c916015a6dbb4` | 合并 `274d7c33a45fe`，保留实验 profile 与 HDR/BT2020 拒绝；颜色失败不写作通过 |
| 内核 `vim4-vdec@2084efcdfe05c` | 经元数据审查副本合并 `f2921218bbf15`；disabled DT 与监督试验门禁保持关闭，正确首帧仍缺 |
| 内核 `vim4-audio-routes@e3eb8eb1e400e` | 合并 `089a3d1b3ea68`；新路由/处理组件未上板，不改变正式 RX 声卡选择 |
| 内核 `vim4-platform-pm@62724cd3d00ab` | 合并 `ed10f339668e1`；CPU idle/GPU cooling 默认不启用、待验证，详见下节 |
| 内核 `fix/hdmirx-lowclock@c3e6a61417868` | **暂不合入**。判稳、EDID 撤销 ready、DFE 后增益校准及诊断会改变现有 RX，34/38→36/38 仍不全过，最终诊断未上板。不为收尾扩展新参数，保留原分支 |
| 内核 `wip/display-m3-hdr2` 及全部 `wip/*` | **不合入**，保留 WIP；tailroom/颜色保护完整构建与现场验收欠账不隐去 |
| 内核 `maintenance/next-20261023` | **不合入 7.3**，保留下一版本 API 迁移 |
| 主仓 `fix/board-panic-on-oops@ec88e220` | 已被 `main` 包含；包源码有 `panic_on_oops=1`，未安装，不按源码推断板上实际值 |
| One-KVM `vim4-p1-audio@cb5e5fc5` | 合入生产 `vim4@3661c6f3`，统计默认关闭。唯一冲突 `capture_linux.rs` 同时保留 EAGAIN 计数与 ENOLINK/ERANGE 返回 AudioSourceChanged 的恢复语义 |
| One-KVM `vim4-wave5-visible-hevc@20d8010d` | **保持功能分支**。删除生产非8对齐 AVC 回退，未添加内核能力探测；eeddb005 不含 E02，不能安全直接合入生产 |

其余内核非 WIP 功能引用 capture-stability、TMDS qualification、SARADC、
M0/M1/M2-qualified、VDEC-clocks/validated、Wave5 hang/recovery/runtime-recovery、
P1/P2/pstore 与 release/kvm-audio-saradc 均已被起点包含。
One-KVM modes/audio/capture-stability 均已合入生产；只有上表 HEVC 分支留待后续。
主仓 HDR stash 为未完成保存点，未展开到 main，也未删除。

## 默认关闭与待验证项

- VDEC：SoC `video-codec@320000` 为 `disabled`；`enable_t7=false`、
  `allow_t7_power=false`、`t7_snapshot_only=true`。trial DTB 不由构建自动启用。
- M1/M2/M3/视频平面/CEC：仅显式实验 DTB 接管；正式启动继续 M0。
  HDR/BT2020 保留 EOPNOTSUPP，P010/AFBC 无完整实现或验收。
- 音频：新 ASRC/AED/VAD/loopback/TDMD 等节点保留 disabled，真实引脚、codec、
  采样率漂移及低功耗唤醒待验证；RX 专用声卡不因合入新增路由。
- 平台 PM：CPU power-down idle 与 GPU passive cooling 未上板，默认不启用。
  公共 DT idle 为 disabled，GPU map 仅放入显式 `pm-test.dtb`。
  保留已有 CPU/GPU critical 温控、启动 GPU 电压和风扇正常策略；RX/VDIN/Wave5 的
  系统挂起拒绝是安全保护，不当作已实现恢复。真正 s2idle/deep 本轮不执行。
- One-KVM：`ONEKVM_AUDIO_STATS` 缺省关闭；旧内核继续将非8对齐 HEVC 回退 AVC。
- 板级 panic-on-oops 包改动待部署；本轮不写 sysctl 或 reexec/reboot。

## 验证方法与本地证据

每一新增内核合并点依次执行同一离线入口、完整 `make Image dtbs modules`、
按修改范围的 DT schema/DTB 检查及逐普通提交 strict checkpatch；同一 O= 目录
增量重建，逐点保存 commit、配置及 Image/DTB 哈希；VDEC 起另存有效配置与完整模块清单。
增量构建仍覆盖完整目标，不把单模块编译称作完整构建。

统一入口原未向显示 fixture 传必需的 `--vendor`，schema venv 又缺 Pillow，
首次维护检查 host 阶段失败。补依赖后修正入口：显式 `VIM4_VENDOR`/`--vendor`，
记录厂商 revision，加入 VDEC lifetime 与 Panfrost resume fixture。失败日志保留，
以修正后的逐点结果为准。KUnit/QEMU 本轮未运行。

音频首轮发现 DT 路由 fixture 缺必需的 `--baseline`，完整构建/schema 已过但整轮
不算通过。统一入口增加 `--audio-baseline`/`VIM4_AUDIO_BASELINE`，同时跑普通路由
与 `--processing`；基线从合并前 `ed3f5c1164e37` 的 audio-test DTS 独立预处理并
编译，SHA256 `8ce2374decd372e132684fc4ec4dcb65e4c051d8ff45ba5460c3b3ef39955352`。
不是用当前 DTB 自比；复跑仍执行完整构建与所有离线 fixture。
PM 新节点改变 phandle 分配，暴露 fixture 将 `pinctrl-0` 原始编号误作引脚变化；
改为解析节点路径，普通与 processing 两种检查均通过，未放松 RX 合同。

VDEC 原历史有5项缺 Signed-off-by、缺少正文和说明行过长；整合副本
`integration/vdec-reviewed-20261023@0144ff83668fe` 仅补提交元数据，逐提交 tree
与原版一致，原作者与原分支保留。`vdec-review.json` 保存24对提交及 tree。
严格检查的原始日志保留自动“新增文件是否更新 MAINTAINERS”提示；这些文件均在
对应现有 MAINTAINERS 范围内，人工核对后与实质代码/提交规范诊断分别计数。

VDEC 合并冲突：保留共享 DOS 的 MAINTAINERS 条目，保留 DT 实验说明；时钟定义
去重已有 VDEC ID，仅追加 HEVCF/B 时钟。音频唯一冲突为 MAINTAINERS 标题，
保留现显示名称并插入音频组件和测试归属。新增音频四模块在验证 O= 配置中设为
`m` 编译，未改版本锁引用的 `uhd1.config`。

One-KVM 合并后重跑 VIM4 Rust、部署助手、网页 typecheck/build 和 release 构建。
额外尝试默认 Rockchip 目标，环境 FFmpeg 无 `AV_HWDEVICE_TYPE_RKMPP`，
该目标被依赖阻断；不记为通过、不为整合改动不相关平台。

本地证据：`logs/unified-mainline-20261023/`；VM 逐点结果位于
`~/build/unified-mainline/`，清理前归档 JSON、小日志和复现脚本。
产物从未安装；已部署 `sources.toml`/`workspace.toml` 原值保留。

合并说明补齐签名和换行，`integration-message-review.json` 与
`merge-signoff-review.json` 逐项证明改元数据前后 tree 相同；检查点旧 hash 可沿此映射
对应上表。最终系列总 diff 又发现两处多余大括号、一处参数缩进，修复为
`302f6e0fffa6d`，未改变控制流，并重新完整验证。

| 检查点 | 离线 fixture | 完整模块数 | Image/DTB/modules |
|---|---:|---:|---|
| maintenance-reviewed | 37/37 | 2334 | 通过 |
| display-m3-reviewed | 51/51 | 2334 | 通过 |
| vdec | 52/52 | 2335 | 通过 |
| audio-reviewed | 67/67 | 2339 | 通过 |
| pm-reviewed | 68/68 | 2339 | 通过 |
| 最终 302f6e0fffa6d | 68/68 | 2339 | 通过 |

最终相关 schema（另含 CPU idle/thermal）零诊断。逐普通提交 strict checkpatch 为
0 error、0 check，仅40条新增文件/MAINTAINERS 提示，逐项核对归属；不是声称原始
warning 数为零。最终总 diff 仅余 MAINTAINERS 提示及 binding 应分补丁的合并展示
提示；binding 在实际系列中已分提交。音频入口及最终样式修复单独 strict 全零。
One-KVM VIM4 Rust 739 通过、2 ignored，部署助手30通过，网页 typecheck/build 与
release 构建通过；上文额外 Rockchip 检查仍被环境依赖阻断。
主仓全量离线 unittest 共236项，0失败、6跳过（与本机环境基线一致）。

## 正式板、清理与推送

收尾未重启：build ID `eeddb005df059a850853876d52ef603aa1af192b`，三服务
`one-kvm`/`vim4-manager`/`vim4-wave5-monitor` active，UDC configured，taint=0，
failed unit 为0；前后 boot ID、启动文件、登记文件、正式应用哈希一致。
真实 HID 的键盘 down/up、绝对/相对鼠标、点击、滚轮均通过。
当前模式未修改：3840×2160 H.265，20秒稳态 60.04fps，丢帧/丢包/freeze 均0，
呈现间隔 max 37.6ms。仅当前短冒烟，不补算长期或其他模式验收。
实际 `panic=20`、`panic_on_oops=0`，说明新板级策略仍待部署。

已删11个合入的 VM worktree、16个 Mac worktree、Mac build/ 的205项旧内容及 VM
429项旧产物；构建清单、日志、有效配置、模块列表已归档至本地证据目录。
构建快照中的90个修改/新增源码文件及差异另存后清理，保留主仓 HDR stash、WIP、
lowclock、next、HEVC 分支；未合入的 U-Boot 产物与 schema 工具依赖留在 VM。
板上删除117项旧候选/测试文件和旧回退点，约963MB；保留
`/var/tmp/vim4-deploy-7.3-final`，Image/DTB/应用均匹配正式版；同包另有 Mac 校验归档。
Stock 5.15、现有启动入口、运行目录和用户虚拟盘保留。旧 TMDS 备份的 Image 与正式版
不同，因此没有将它错误标为当前回退点；PD/引导恢复证据清理前归档。

内核 `origin/vim4-kvm-7.3@302f6e0fffa6d`、One-KVM `origin/vim4@3661c6f3` 已推送；
主仓本记录与统计合入 main。版本锁保留已部署产物，没有安装本轮构建输出。

## 下一阶段（本轮不执行）

1. 显示颜色：定位 CSC 写入不保持及 OSD HDR2 路由；验证 WIP tailroom/静音保护，
   再验 4K GPU PRIME、OSD flip、NV12、10bit/420、带时间戳 HPD/ELD。
2. HDR：取得每层 HDR2 所有权后验证 HDR/BT2020/PQ/HLG，不解除现有拒绝。
3. VDEC：安全时钟/域/DBUS 生命周期后取得正确 H.264 首帧，再扩 codec/多实例。
4. RX：1024×768 候选独有失败缺稳定二分判据；lowclock 仍有36/38错误，保留恢复前
   诊断和标准 EDID ioctl，对照源端时钟与测量窗口，不直接放宽查询容差。
5. 待部署批次：Wave5 E02/E01 已验子集及匹配 One-KVM 探测/应用；panic-on-oops
   板级包；M2/M3 颜色修复后专项与九类回归；音频/PM 另行上板门禁。
   源码合入本身不授权改变部署锁或启用实验 DT。
