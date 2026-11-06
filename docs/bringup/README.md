# 上板记录索引

每条记录一个文件，位于 `bringup/日期-主题.md`。先按日期或标签在本页找到条目，只打开需要的文件；
不要通读整个目录。标签：board、kernel、video、audio、usb、application、pikvm、uu、manager、deployment。

新记录：新建 `bringup/YYYY-MM-DD-英文短名.md`，首行 `# YYYY-MM-DD：标题`，并在本页对应日期下追加一行。

## 按任务查找

- 内核：[启动](2026-10-19-edge-firstboot.md) → [合入](2026-10-23-mainline-integration.md) → [差距](2026-10-28-kernel73-parity-audit.md)。
- 音视频：[双路径](2026-10-25-native-hdr-dual-path.md)、[HDR](2026-10-26-all-kvm-hdr.md)、[延迟](2026-10-27-current-video-latency.md)。
- USB：[PD](2026-10-12-pd-boot-init.md)、[组合](2026-10-21-edge-usb-functions.md)、[介质](2026-10-18-nas-storage-usb-disk.md)。
- 应用：[切换](2026-10-13-nanokvm-deploy-jetkvm-switch.md)、[登录](2026-10-18-unified-auth-gateway.md)、[UU](2026-10-25-uu-protocol-audit.md)。
- 部署：[组件](2026-10-13-component-deploy-loop.md)、[双内核](2026-10-21-dual-kernel-integration.md)、[回退](2026-10-22-edge-7-3-final-deploy.md)。

以下保留完整日期索引。这些里程碑记录的是历史证据；查找当前架构和约束时，仍应先读对应子系统入口。

## 2026-11-06

- [HEVC厂商序列移植](2026-11-06-hevc-vendor-port.md) — kernel video；T7分支依据、寄存器目录和七提交；尖端f21dfc47 W=1/KUnit 25/25通过（协调者代跑heavy），未上板。
- [r70 MPEG-2 请求追踪](2026-11-06-mpeg2-r70-rejections.md) — kernel video；visl 107 个 picture 控制与板上一致，缺前向参考时间戳假设排除；实际模块含 aaec509，持续 ERROR 返回点待诊断窗口，附四流清单。
- [r70 .32短回归](2026-11-06-vdec-r70-integration32.md) — kernel video；DOS step=0、H.264十条通过；Sony仍有ERROR缓冲，HEVC有效输入WAIT=0仍超时；无冷复位，正式恢复/清理通过。
- [MPEG-2 P 链算术定位](2026-11-06-mpeg2-rounding.md) — kernel video；21 条参考截取自校验精确，新图像差均≤2；teracom 64 次零运动残差舍入累积已量化，无有证据的内核算术修复。
- [.32集成与板窗计划](2026-11-06-vdec-integration32-plan.md) — kernel video；HEVC WAIT_FLAG、DOS降噪及MPEG-2单向B参考修复集成，离线封包与短回归计划；待批，不部署。
- [r69 MPEG-2 像素与单向 B 参考](2026-11-06-mpeg2-r69-analysis.md) — kernel video；四条色度矩阵无像素变化符合 4:2:0 语义；sony-ct1/ct2 两张起始 B 因缺前向 anchor 被拒绝，topic 修复及六流清单待上板。
- [r69联合验证与AVC收口](2026-11-06-vdec-r69-joint.md) — kernel video；合r65为129S/1F/5KU，旧110/58均无回退；MPEG-2完成29次4S/25F，HEVC streaming超时；正式恢复/清理通过。
- [r68候选冷复位与被动恢复](2026-11-06-vdec-r68-coldboot.md) — kernel video；.31启动8.219秒冷复位，正式自然恢复也复位一次，第二次恢复成功；零码流，proof/视频/清理通过。
- [r67启动识别修复](2026-11-06-vdec-r67-startup.md) — kernel video；候选版本行残缺导致旧UART门禁误停，码流未运行；改由SSH身份核验，保留UART复位检测，附真实捕获回放。
- [r66插件身份拦截与恢复](2026-11-06-vdec-r66-identity.md) — kernel video；路径转换缺陷被门禁拦截，码流未运行；正式恢复两次冷复位后自然恢复成功，附路径修复及r67条件。
- [r65集成部分全集](2026-11-06-vdec-r65-joint.md) — kernel video；119S/1F/5KU/10未运行，MR3/4/5与Sharp_Field逐字节正确；日志采证超时单列，正式恢复；[r66续跑计划](2026-11-06-vdec-r66-plan.md)待批。
- [AVC评审版与三格式集成计划](2026-11-06-vdec-integration31-plan.md) — kernel video；两提交逐项门禁完成，AVC/HEVC无冲突集成；H.264全集→MPEG-2 29次→HEVC，待批板窗。
- [MPEG-2 visl 矩阵根因](2026-11-06-mpeg2-visl.md) — kernel video；25 条三组离线对照，6 条用户态矩阵错误已修、6 条实为 MPEG-1、13 条像素根因待证；含统一窗口清单，未上板。
- [r64 MR3存储归属验证](2026-11-06-vdec-r64-storage.md) — kernel video；10/10通过，MR3/4/5各300帧逐字节正确、两队列零ERROR；104项buffer命中但无槽实证，正式恢复，未部署。
- [MR3 旧timestamp与存储归属](2026-11-06-vdec-mr3-storage.md) — kernel video；visl/ioctl定位ts0缓冲比槽位活得久，独立修复27项KUnit通过；[上板计划](2026-11-06-vdec-mr3-storage-plan.md)已执行。
- [r63 缺口修复实板验证](2026-11-06-vdec-r63-gap.md) — kernel video；9S/1F，MR4/5逐字节正确、7对照无回退；MR3仍53帧错误/12对ERROR，正式恢复通过，未部署。
- [r62 入场依赖失败](2026-11-06-vdec-r62-entry.md) — kernel video；正式proof通过，宿主Playwright缺失导致零候选启动；私有依赖与离线receiver冒烟完成，替代票已批准。

## 2026-11-05

- [HEVC 金标准轨迹离线方案](2026-11-05-hevc-golden-plan.md) — kernel video；两侧补丁与对齐工具，hdrdual6源码/模块兼容性未证实；两窗方案待审查及用户批准，未碰板。

- [HEVC 首次启动离线对照](2026-11-05-hevc-start.md) — kernel video；r69/r70有效AU无SOURCE_CHANGE，WAIT_FLAG修正无效；[首slice握手候选](2026-11-05-hevc-header-handshake.md)与compliance/首帧短清单待t3k统一上板。

- [MR3/4/5 缺口参考定位](2026-11-05-vdec-gap-references.md) — kernel video；JM与DQBUF定位缺口项导致ERROR，含S4索引修正的topic修复26项KUnit通过，像素未上板；[验证计划](2026-11-05-vdec-gap-validation-plan.md)已批准。
- [r61 parser A/B 像素采证](2026-11-05-vdec-r61-parser-ab.md) — kernel video；官方14S/3F、Khadas17F，14条仅缺显示帧且已有像素正确；LTR首错10/16/16，正式恢复通过。
- [H.264 visl 离线控制采证](2026-11-05-vdec-visl-controls.md) — kernel video；17条五组QEMU控制采证，14条Khadas漏末slice、官方parser恢复；像素未验，LTR继续定位。
- [H.264 parser A/B 像素计划](2026-11-05-vdec-parser-ab-plan.md) — kernel video；待批准，私有parser双组保存输出，单次候选启动与r60式恢复。
- [冷启动采集器空环境修复](2026-11-05-vdec-coldboot-collector-fix.md) — kernel；真实空环境子进程离线通过，固定 Python 路径与独立 ready 参数快照，未上板。
- [冷复位 A/B r60](2026-11-05-vdec-coldboot-ab-r60.md) — kernel；A 2次/1复位、B 1次/0复位，恢复再复位后停；最终正式恢复，17项未运行。
- [RESET/VBUS/PD 闭环方案](2026-11-05-vdec-reset-measurement-plan.md) — kernel、usb；仅方案，需实物接线与仪器确认，未排板。
- [冷复位 A/B r59 入场失败](2026-11-05-vdec-coldboot-ab-r59.md) — kernel；默认串口路径不存在，零 SSH/上传/启动，20 项未运行，票已释放。
- [冷复位 A/B 工具与封包](2026-11-05-vdec-coldboot-ab-tools.md) — kernel；UART 审查修正、固定批次、早期采集及两组封包离线核验；未上板。
- [冷复位同 RAM 封装 A/B 计划](2026-11-05-vdec-coldboot-ab-plan.md) — kernel；正式包/.28 交替各十次，累计50分钟已批准；工具复审前不排板。
- [解码 v2 内部评审系列](2026-11-05-vdec-review-v2.md) — kernel video；56→16 提交，逐树构建/sparse/QEMU/头文件与 DT 检查；三项原作者 SoB 缺口保留，不宣称 parity、不部署。
- [.27 / .28 启动前六秒离线差异](2026-11-05-vdec-boot-diff.md) — kernel；解码源码/公共 DTS 相同，核对 MMC/ADLA/fan 基线差异与 UART 时序，提出未执行的区分实验。
- [H.264 全集最终汇总与评审边界](2026-11-05-vdec-avc-final.md) — kernel video；110/135套件通过，旧58项零回退；20Fail、5已知不支持，保留原始Error/Timeout；r58恢复通过，可进入代码评审但未达完整5.15验收。

- [r57 Sharp STREAMOFF 与续跑](2026-11-05-vdec-r57-sharp-streamoff.md) — kernel video；累计103S/21F/1Error/2Timeout/8未运行；Sharp两队列STREAMOFF成功、无FLUSH调用，SP1超时后正式恢复通过。

- [r56 FMO 停止与 Khadas parser 来源](2026-11-05-vdec-r56-fmo-parser.md) — kernel video；累计79S/17F/1Timeout/38未运行；已知FMO超时立即恢复，系统parser匹配Khadas包，首条STREAMOFF实测通过。

- [r55 系统 parser 来源核对](2026-11-05-vdec-r55-parser-identity.md) — kernel video；候选正常启动，采证脚本提前退出，续跑未运行；系统 parser 与同版本官方 deb 哈希不同，来源待补证，正式恢复通过。

- [r54 Sharp 尾帧与队列跟踪](2026-11-05-vdec-r54-sharp-trace.md) — kernel video；stateless compliance 通过，AVC 53S/10F/72未运行；零丢事件的 trace 证明末 slice 未进 OUTPUT，定位用户态排空，正式恢复通过。

- [r53 冷复位与跨内核启动统计](2026-11-05-vdec-r53-coldboot.md) — kernel video；`.28` 第三次启动再次冷复位，解码未运行；新正式恢复与视频通过，附已覆盖启动数及缺失范围。

- [r52 基线计划保护门禁](2026-11-05-vdec-r52-baseline-guard.md) — kernel video；`.28` 启动成功，旧保护哈希在解码前被拒绝，全部测试未运行；新正式默认与视频恢复通过。

- [manager 首次续窗登录传输与回退](2026-11-05-integration-manager-continuation.md) — kernel deployment manager；历史首错恢复与SSH入口修正；后续正式验收通过见下一条。

- [7.3 集成内核与新 manager 正式部署](2026-11-05-integration-formal-deploy.md) — kernel deployment manager；八类同资产结果及manager续窗门禁通过，新默认保留；fan90trip持久化和面板保存/读回/恢复、实时PD5V3A通过；19档未重跑，音频仅状态，`.3`整包保留。

- [完整 AVC/MPEG-2 一致性与 bit21 实验](2026-11-05-vdec-full-conformance.md) — kernel video；H.264 58/135、MPEG-2 18/43；HEVC bit21 仍超时，5.15 启动 hard lockup，对照未运行；已恢复 `.3` 并归档清理。
- [标准码流失败特性聚类](2026-11-05-vdec-failure-groups.md) — kernel video；隔行 SPS 52 Fail、多 slice 18 Fail；主机驱动显式限制，修复待验证；附逐流结果与重叠分组。
- [H.264 隔行支持设计](2026-11-05-vdec-interlaced-design.md) — kernel video；尺寸、场参考、MV 与 HOLD 生命周期的设计及初期离线准备。
- [H.264 场缓冲生命周期](2026-11-05-vdec-field-lifetime.md) — kernel video；`.27` stateless compliance 60/60；r49 子集 7/10、四条隔行转通过，CVFC1 正确裁剪后 50 帧逐字节相等；恢复 `.3`。
- [H.264 Sharp 尾帧与 r50](2026-11-05-vdec-sharp-tail.md) — kernel video；预算内运行 65/135，54 Success、11 Fail；两条 Sharp 各缺一帧，其余帧逐字节正确，排空路径待定位。
- [解码分支集成基线重放](2026-11-05-vdec-integrated-rebase.md) — kernel video；56 个补丁 range-diff 不变、逐提交构建通过；17 次 QEMU KUnit 通过，`.28` 实板验收待运行。
- [r51 `.28` 启动冷复位](2026-11-05-vdec-r51-coldboot.md) — kernel usb video；启动约6秒回 ROM，解码验收未运行；正式 `.3` 身份与视频恢复，计入候选冷复位统计。
- [T7 H.264 多 slice 生命周期修复](2026-11-05-vdec-multislice.md) — kernel video；`.26` 复验 11 条 Fail 转通过，3 条单 slice 对照通过；7 Fail、1 内核 Timeout 保留；恢复 `.3` 和视频，上传已归档清理。
- [独立格式 Fluster 与 HEVC 启动顺序](2026-11-05-vdec-independent-fluster.md) — kernel video；H.264 子集 1/2，MPEG-2 0/2（1 未运行），像素失败即停止；清理已归档上传，恢复 `.3`；HEVC bit21 模式差异待验证。
- [解码缓冲序号修复与复验](2026-11-05-vdec-buffer-sequence.md) — kernel video；独立序号提交与静态检查；`.25` stateless/JPEG 各 60/60，HEVC SOURCE_CHANGE 超时，Fluster 未运行；已恢复 `.3` 与视频。
- [生产配置解码功能验收](2026-11-05-vdec-production-validation.md) — kernel video；`.24` 正常启动，stateless 带流 compliance 遇输出缓冲序号不递增；后续未运行，已恢复 `.3` 与 4K 视频。
- [生产 .90 首窗与单项接收补测](2026-11-05-integration-prod90-regression.md) — kernel；首窗采集/编码局部通过、API接收首错保留；随后获批仅补应用重启接收，4K H.265解码推进通过，两窗均恢复.3并核视频，其余未验不变。
- [集成候选构建与 KUnit 复验](2026-11-05-integration-build-results.md) — kernel；fd41fb5 生产.90/调试.91 RAM全量校验通过，现存迁移驱动/标准CCF arm64 QEMU 15套59/59；额外DMA-BUF两次超时登记，板测待安排。
- [集成候选回归与构建准备](2026-11-05-integration-regression-plan.md) — kernel；19 分钟生产回归清单、缺入口/待实板边界及同 O= 双候选 RAM 构建入口；仅离线准备，未排 heavy、未构建、未访问板子。
- [KUnit 提交说明与利用率审查返工](2026-11-05-kunit-review-rework.md) — kernel；25 提交补正文/Signed-off-by，消息阶段空 diff、原四 SHA 保留；最终 29 完整 patch 检查通过，撤销 fallthrough 并独立补 break；QEMU 44/44，利用率显示需实板回归。
- [全树 KUnit 最终组合复验](2026-11-05-kunit-final-replay.md) — kernel；82 个 Python 已迁出/删除，九配置 arm64 QEMU 11 套 44/44；WERROR=n 仅作运行复验，既有静态失败及实板边界保留。
- [PWM 既有 KUnit 复验](2026-11-05-pwm-kunit-results.md) — kernel power；复用原测试 QEMU 1/1，PWM/clk-pwm/regulator 内建/模块及静态检查完成；无 Python 可迁，同控制器 ABBA 保留，实板未验。
- [brcmfmac KUnit 迁移结果](2026-11-05-brcmfmac-kunit-results.md) — kernel network；删除 P2P Python，arm64 QEMU 新参数/决策 2 项与已有 NVRAM 3 项均通过，构建/范围静态检查完成；固件/P2P/offload 待实板。
- [ADLA KUnit 迁移结果](2026-11-05-adla-kunit-results.md) — kernel；四个 Python 删除，真实 allocator/取消/边界 arm64 QEMU 4/4，内建/模块编译完成；既有 W=1/sparse 门禁未通过，DMA/复位/生命周期待实板。
- [其余非暂缓驱动测试迁移结果](2026-11-05-remaining-drivers-kunit-results.md) — kernel usb thermal；9 个 Python 删除，风扇 arm64 QEMU 3/3，范围构建完成；CRG/TCPM 有效 sparse 未通过，V/B 待实板。
- [Meson ASoC KUnit 迁移结果](2026-11-05-asoc-kunit-results.md) — kernel audio；15 个 Python 删除，arm64 QEMU 3/3，构建及范围静态检查完成，音频/硬件待实板。
- [Meson DRM KUnit 迁移结果](2026-11-05-drm-kunit-results.md) — kernel video；18 个 Python 删除，QEMU 8/8，内建/可用模块与有效 sparse 等检查完成；显示/DMA 待实板。
- [T7 JPEG KUnit 迁移结果](2026-11-05-jpeg-kunit-results.md) — kernel video；两个 Python 删除，arm64 QEMU 2/2，范围构建与静态检查通过；真实 DMA 和像素待实板。
- [T7 HDMI RX KUnit 迁移结果](2026-11-05-hdmirx-kunit-results.md) — kernel video audio；20 个 Python 迁出/删除，arm64 QEMU 9/9，内建/模块与范围静态检查完成；硬件语义待实板。
- [Wave5 故障注入离线方案](2026-11-05-wave5-fault-injection-plan.md) — kernel video；标准 fail_function 注入点、隔离/DMA 预期与判定；仅准备，全部待实板，内部时序注入缺口单列。
- [Wave5 KUnit 迁移结果](2026-11-05-wave5-kunit-results.md) — kernel video；13 个 Python 文件迁出/删除，arm64 QEMU 9/9；W=1、有效 sparse、模块/内建及静态检查完成，硬件语义待实板。
- [内核树测试迁移清单](2026-11-05-kernel-test-migration.md) — kernel；87 个文件逐项盘点，82 个已迁出/删除，保留生成器/vdec；44 项组合重跑通过，实板及部分静态门禁未完成。
- [测试清单 drm-1](2026-11-05-kunit-inventory-drm-1.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 drm-2](2026-11-05-kunit-inventory-drm-2.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 drm-3](2026-11-05-kunit-inventory-drm-3.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 other-1](2026-11-05-kunit-inventory-other-1.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 other-2](2026-11-05-kunit-inventory-other-2.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 other-3](2026-11-05-kunit-inventory-other-3.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 other-4](2026-11-05-kunit-inventory-other-4.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 hdmirx-1](2026-11-05-kunit-inventory-hdmirx-1.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 hdmirx-2](2026-11-05-kunit-inventory-hdmirx-2.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 hdmirx-3](2026-11-05-kunit-inventory-hdmirx-3.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 hdmirx-4](2026-11-05-kunit-inventory-hdmirx-4.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 jpeg-1](2026-11-05-kunit-inventory-jpeg-1.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 wave5-1](2026-11-05-kunit-inventory-wave5-1.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 wave5-2](2026-11-05-kunit-inventory-wave5-2.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 wave5-3](2026-11-05-kunit-inventory-wave5-3.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 audio-1](2026-11-05-kunit-inventory-audio-1.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 audio-2](2026-11-05-kunit-inventory-audio-2.md) — kernel；逐文件入口、原检查及待确认处置。
- [测试清单 audio-3](2026-11-05-kunit-inventory-audio-3.md) — kernel；逐文件入口、原检查及待确认处置。
- [集成生产与正式基线同窗Wi-Fi对照](2026-11-05-integration-wifi-control.md) — kernel network；`.3/.90`各600秒342.08/328.88 Mbit/s，同窗-3.86%通过性能门槛，生产配置与恢复4K视频已核；五个旧splat首报均在`.92`已覆盖区间内，完整调试A仍未完成。
- [PD FIFO移植与A/B验证](2026-11-05-pd-fifo-validation.md) — kernel usb network；`.92`仍cold_boot；修复复用O=配置陈旧问题后，真正生产`.93`完成600秒均值326.97 Mbit/s（-11.52%），未回退硬IRQ；最终`.3`与4K视频恢复，PD分支未通过合入门槛。
- [TCPM冷复位专项与正式启动统计](2026-11-05-tcpm-coldboot-audit.md) — kernel usb；核对Get_Source_Cap再等待路径及FUSB302上游待审排空补丁；只读34 boot中确认20次正式启动、2次早期非请求复位，PD根因未定，提交移植方案待审。
- [冷复位的 Wi-Fi probe 排除实验](2026-11-05-debug-splat-reset-isolation.md) — kernel network usb；E1内核明确拒载brcmfmac仍cold_boot，eMMC门禁未运行；自动回 `.3` 后另有未请求复位，最终身份/4K视频恢复；E2供电前提无法确认，未做。
- [启动修复重放到 KUnit 迁移基线](2026-11-05-debug-splat-integration.md) — kernel；v2保留原分支，MMC/ADLA重放到7e35e3b，合并为一个ADLA KUnit suite，逐提交strict 0/0/0；编译与统一候选验收待集成窗口。
- [ADLA 锁类修复与 PD 启动时序比较](2026-11-05-adla-mutex-pd-timing.md) — kernel network usb；调用点宏及QEMU KUnit 1/1；`.83` Soft_Reset收到及时Accept后仍cold_boot，A未过，已恢复 `.3` 与4K视频；B改用集成候选。
- [启动修复实板复验与生产吞吐准备](2026-11-05-debug-splat-board-validation.md) — kernel network usb；`.81` 新暴露 ADLA mutex 类别报告后 cold_boot，PD 同步采证；已恢复 `.3` 与4K视频，生产 `.82` 待清理旧候选容量后测600秒吞吐。
- [MMC 硬中断锁修复与冷复位分析](2026-11-05-mmc-irq-reset-analysis.md) — kernel usb；DMA 完成恢复到 IRQ 线程、SDIO 短锁改 raw，离线构建完成；两次 cold_boot 原因未明，列出下一窗口同步采证要求，未上板。
- [解码与启动修复联合调试](2026-11-05-vdec-joint-debug.md) — kernel video；`.23` 启动遇 MMC IRQ 锁上下文错误和未解释冷复位，未运行解码；已恢复 `.3` 与 4K 视频。
- [风扇自适应温度对照](2026-11-05-fan-thermal-adaptive.md) — kernel manager；生产.90最高58.6°C，比.3高0.8°C、无新增降频；收尾清理冲突已修，原manager与视频核验通过。
- [风扇标准 thermal 迁移](2026-11-05-fan-thermal.md) — kernel manager；15级DT档位及用户态兼容，原分支离线检查与首次基线未稳定记录。
- [调试启动 splat 离线修复与 PWM 锁拓扑](2026-11-05-debug-splat-fixes.md) — kernel；brcmfmac 上游移植及真实解析 KUnit、ADLA SG 上限修复；PWM 独立 key 修正跨实例建模，同实例 ABBA 明确保留，未上板。
- [解码调试候选启动与门禁](2026-11-05-vdec-debug-boot.md) — kernel deployment；修正大 Image 加载地址后进入调试 Linux，暴露 PWM 锁、ADLA DMA、brcmfmac 越界及工具 media 查找问题；基线和视频已恢复，标准流未运行。
- [解码标准验收离线准备](2026-11-05-vdec-standard-preparation.md) — kernel video；调试整包、锁定 Fluster/ISO 输入、compliance 与性能工具；无本轮硬件结果，HEVC 超时仍待验证。
- [解码 KUnit 迁移结果](2026-11-05-vdec-kunit-results.md) — kernel video；移除七个 Python 测试文件，arm64 QEMU 五套 17/17，模块/内建与修改范围静态检查通过；硬件语义待实板。
- [解码测试迁移清单](2026-11-05-vdec-test-migration.md) — kernel video；逐项登记七个文件、49 项测试的风险与 KUnit/compliance/实板替代验证。
- [HEVC 接口与固件模式](2026-11-05-hevc-interface-review.md) — kernel video；保留 stateful，核对三种 codec 的固件参数方向；未发现 T7 主机完整参数注入模式，结论限于源码接口。
- [HEVC stateful 与 EOS](2026-11-05-hevc-stateful.md) — kernel video；三个节点 compliance 各 47/47，首条 HEVC 码流超时零帧；已恢复 KVM，标准码流及厂商对照待运行。
- [HEVC 核心资源](2026-11-05-hevc-core.md) — kernel video；补齐后端时钟后，空闲 AXI 停止、固件加载和 96 帧既有格式回归通过；HEVC 解码尚未验证，保留早期冷复位记录。

## 2026-11-04

- [MJPEG 解码接口](2026-11-04-mjpeg-decoder.md) — kernel video；双节点各 47 项 compliance 通过，T7C 字节重排后 48 帧最大误差 2，H.264/MPEG-2 回归通过。
- [MPEG-2 请求接口](2026-11-04-mpeg2-request.md) — kernel video；修正用户态控制与初始场对参考，六组 112 帧完成解码并量化像素误差，长期共存仍待验。
- [硬件解码格式对齐](2026-11-04-hwdecode-parity.md) — kernel video；H.264 Baseline/Main/High/1080p 运动样本逐帧像素通过，完整格式与边界尚未对齐。
- [H.264 分辨率与码流边界](2026-11-04-h264-boundaries.md) — kernel video；包含 JVT 矩阵、UHD 和 4096×2304 的七组 216 帧逐帧像素通过。
- [管理器实时 PD 状态](2026-11-04-manager-tcpm-status.md) — application usb；已部署，中英文实页显示内核5V/3A合同，KVM/USB服务未重启。
- [开机 PD 接入 Linux TCPM](2026-11-04-boot-pd-tcpm.md) — kernel usb；build 3已部署，5V/3A与十分钟4K冒烟通过；冷启动和全回归待验。
- [USB 总线挂起修复部署](2026-11-04-pm-typec-parity.md) — kernel usb；build 2 保留为默认，五分钟4K冒烟通过；节能方向取消，真实主机睡眠未测。

- [UU 自动码率与 Wave5 在线更新](2026-11-04-uu-adaptive-bitrate.md) — uu video application；在线切目标码率持续解码、无采集重建，Mac 接入与弱网验收待完成。
- [UU TWCC 发送端带宽估算](2026-11-04-uu-twcc.md) — uu video application；发送编号、反馈还原、被动带宽估算与在线码率闭环，含重传和拥塞回放测试。

- [安全媒体移植首段与运行时清点](2026-11-04-security-media-port.md) — kernel board；HDCP只读密钥状态候选、固定CA/TA输入，认证/DV/安全启动尚未完成，未部署候选。

- [日期内核构建、清理与最终验收](2026-11-04-kernel-731-vim4-20261104.md) — kernel deployment；20261104 build 1 通过最小冒烟并留作 Mainline，旧 uhd7 启动/模块/固件目录已删除；首次工具中止和恢复保留在同一记录。

## 2026-11-03

- [内核命名统一、旧产物清理与管理面板](2026-11-03-kernel-naming-cleanup.md) — kernel deployment manager；仅保留 Vendor/hdrdual6 和 Mainline/7.3.1，正常重启后四服务/UDC、4K H.265 59.78fps及面板卡片通过。

- [7.3.1整包部署与boot清理](2026-11-03-kernel-731-deploy.md) — kernel deployment video usb；中途回uhd7确认MCP文本问题也存在于基线，补齐九类验收后留在7.3.1并推广来源锁；音频只验状态，UU只证明官方RTP接收。

- [PiKVM 首帧拆段与冷启动口径](2026-11-03-pikvm-first-frame.md) — pikvm video application board；8.2秒含约6.3秒HTTP启动等待，暖接入0.64–0.70秒，按需关键帧有效。

- [uhd7 三模块安装与四应用会话验收](2026-11-03-mainline-modules.md) — kernel video application deployment；四应用4K60、JetKVM第二浏览器接管关键帧及UU官方客户端接收，修正临时测试就绪门禁。

- [5.15 amlvenc 按需 IDR 离线调研](2026-11-03-amlvenc-on-demand-research.md) — video；H.265 可只改参数，H.264 需 change_qp 转发；登记输出缓冲越界等 3 个 issue，暂不改 5.15。

- [Wave5 AVC 默认按需 IDR](2026-11-03-wave5-avc-default.md) — video board application deployment；共享插件、编码切换重试与生产验证。

- [Wave5 AVC 恢复帧 QP 与编码选择持久化](2026-11-03-wave5-avc-recovery-qp.md) — video board application deployment；逐帧 QP、网页恢复与重启验证。

- [Wave5 单帧 VBV 与 HEVC 帧级码控对照](2026-11-03-wave5-single-frame-vbv.md) — video board deployment；4K60 静态带宽、分带质量、接入、PLI 与延迟。

## 2026-11-02

- [Wave5 静态画面行刷新](2026-11-02-wave5-refresh.md) — video board；4K 细节图、逐行带质量、按需 IDR 与丢包恢复

- [uhd7 固定高刷与原生 YUV444 窗口](2026-11-02-hfr-yuv-window.md) — kernel video board；高刷吞吐、QHD AVC 限额、444 色度通过，接收无丢帧，图样跳号强推断来自信号源；QHD HEVC SPS 低报，重发 HDMI Forum 48–120 Hz EDID 后 M6 仍无 Variable

- [uhd7 正式构建与 BCM43752 SDIO 部署](2026-11-02-wifi-sdio-formal.md) — kernel network board deployment；同次完整模块、eMMC、独立中断、FullKvm 重启及安装后反向 TCP

- [BCM43752 SDIO 主机路径优化与 5.15 同窗对照](2026-11-02-wifi-sdio-host-path.md) — kernel network board；可缓存中转缓冲区、SDIO 中断使能过滤、硬中断完成、GPIOX_7 独立中断，同窗 120 秒 D2 401.6 对 5.15 363.3

- [BCM43752 下载上限与 SDIO 每聚合周期](2026-11-02-wifi-glom-cycle.md) — kernel network board；tracepoint 拆解每聚合周期，7.3 对 5.15 的中转复制与中断路径差额

- [BCM43752 下载余差与 SDIO 接收对齐](2026-11-02-wifi-rx-alignment.md) — kernel network board；同期双内核下载、接收中转复制探针与固件对齐对照

- [BCM43752 下载吞吐与接收处理 CPU](2026-11-02-wifi-rx-cpu.md) — kernel network board；同一连接交替切换 wlan0 RPS，比较 SDIO 与 TCP 接收路径

- [BCM43752 固件版本与 5.15 驱动协议对照](2026-11-02-wifi-fw217.md) — kernel network board；AP6275S 程序、SAE 管理密钥、SDIO 发送窗口和 discovery

- [BCM43752 厂商扫描请求与中断对照](2026-11-02-wifi-vendor-scan.md) — kernel network board；5.15 原厂 24 次激活、运行时地区和驻留、7.3 单变量验证

- [BCM43752 扫描信道与 MPC 交替对照](2026-11-02-wifi-scan-pairs.md) — kernel network board；首次扫描、固件年龄、请求与 BSS 信道

- [BCM43752 连接崩溃的扫描轨迹](2026-11-02-wifi-scan-trace.md) — kernel network board；主机命令时序、PHY 数据端口与扫描 MPC 实验

- [Wi-Fi 激活分组与聚合上限对照](2026-11-02-wifi-pm-glom.md) — kernel network board；11.90分钟、输入同哈希、PM/P2P因果未确立、状态7、32/36负结果、恢复FullKvm
- [BCM43752 第三轮离线差异与实验草案](2026-11-02-wifi-txstatus-offline.md) — kernel network offline；D11核心表、固件输入缺口、初始化矩阵、≤30分钟实验预算，未占板
- [P0-2 性能与常开功耗合并窗口](2026-11-02-p0-2-pm-window.md) — video kernel board；14分56秒后按指令停止，仅5.15 idle完成，signal取消，已回FullKvm
- [Wi-Fi TX status、固件崩溃与厂商对照](2026-11-02-wifi-txstatus.md) — kernel network deployment；日志overlay、AXI trap再现、厂商双向600秒、旧上传比85.68%，已恢复FullKvm
- [boot 空间清理](2026-11-02-boot-space-cleanup.md) — deployment kernel；四个无引用旧文件，4.09→18.95 MiB，全部登记哈希前后通过，无重启
- [HDMI-RX COR 锁部署与 Wi-Fi 有界流量](2026-11-02-hdmirx-cor-lock-deploy.md) — kernel deployment video network；三次 EDID、4K60 600秒、Wi-Fi 600秒与恢复

## 2026-11-01

- [HDMI-RX EDID 撤回 SError 审计与 COR 复位竞争修复](2026-11-01-hdmirx-edid-serror-audit.md) — kernel video offline；根因边界、候选分支未上板、登记 issue
- [vim4-manager HTTPS 部署验收](2026-11-01-manager-https.md) — manager application deployment；443/8443、本机 CA、Tailscale 证书、HTTP 开关
- [USB 端点合并部署验收](2026-11-01-usb-endpoint-merge.md) — usb application deployment；多媒体键并入绝对鼠标，4/5 端点含麦克风
- [HDR/r14e、MAC 与音频最终合入](2026-11-01-p0-hdr-final-merge.md) — application audio deployment；用户授权合入并停止，未验边界保留
- [One-KVM 音频源变化恢复与稳定设备名](2026-11-01-onekvm-audio-source-recovery.md) — audio application deployment；API/现有采集通过，待用户听测
- [跨内核原厂MAC传递修复与部署](2026-11-01-ethernet-mac-handoff.md) — network kernel deployment
- [r14e持久安装与用户手测](2026-11-01-hdr10-r14e-installed.md) — deployment kernel application hdr10 kbase
- [HDR r14e准备与恢复记录](2026-11-01-hdr10-phase2-preparation.md) — board video application source-recovery
- [HDR 第二阶段 uhd6 短窗](2026-11-01-hdr10-phase2-uhd6.md) — board video application uu

## 2026-10-31

- [原生HDR10 r3离线候选](2026-10-31-hdr10-remote-candidate.md) — kernel video application offline candidate
- [HDR窗口恢复预算D1修复](2026-10-31-hdr10-recovery-budget.md) — video application offline safety
- [原生HDR第二阶段窗口补审修复](2026-10-31-hdr10-phase2-window-fixes.md) — video application offline safety
- [原生HDR第二阶段四项审查修复](2026-10-31-hdr10-phase2-review-fixes.md) — video application offline safety
- [原生HDR第二阶段离线接入候选](2026-10-31-hdr10-phase2-offline.md) — video application uu gpu offline
- [uhd6正式完整构建与验收](2026-10-31-uhd6-formal.md) — kernel video gpu deployment；九类汇总/19模式/600秒运动通过，持久安装，5.15仍默认
- [uhd6统一来源与过程](2026-10-31-uhd6-unified.md) — kernel gpu video deployment；来源冲突、r3证据与失败历史
- [uhd6 EDID恢复取证与修复门禁](2026-10-31-uhd6-edid-review.md) — kernel video deployment；自动回5.15，review及撤回/恢复短窗通过
- [P0-2分窗性能准备与接收预检](2026-10-31-p0-2-performance.md) — board video performance offline
- [P0-3公开停机协议与合法等待研究](2026-10-31-wave5-stop-research.md) — kernel video offline safety
- [P0-3真实挂死注入安全审查](2026-10-31-wave5-real-hang-safety.md) — kernel video offline safety
- [原生HDR最小主路径验收与合入](2026-10-31-hdr10-native-final.md) — kernel board video application hdr
- [uhd5 GPU正式来源锁与最小烟测合入](2026-10-31-uhd5-main-integration.md) — kernel gpu deployment
- [uhd5完整封包、正常回退与正式推广阻塞](2026-10-31-kbase-r12-package.md) — kernel gpu board deployment
- [kbase r11厂商live DVFS策略与配对复测](2026-10-31-kbase-r11-policy.md) — kernel gpu board video
- [kbase uhd5、payload目录修复与默认性能门禁](2026-10-31-kbase-r10-uhd5.md) — kernel gpu board video
- [kbase r6 DMA追平、平台二分与thermal绑定](2026-10-31-kbase-r6-window.md) — kernel gpu board video
- [kbase r9外部模块验证与队列候选目录冲突](2026-10-31-kbase-r9-queue.md) — kernel gpu board audit
- [kbase r7默认调频离线候选与等锁超时](2026-10-31-kbase-r7-offline.md) — kernel gpu audit
- [原生HDR修复包复验与同源5.15码流](2026-10-31-hdr10-remote-r7.md) — kernel board video application
- [原生HDR r6十位DMA、Panfrost与编码caps阻塞](2026-10-31-hdr10-remote-r6.md) — kernel board video application gpu
- [7.3原生远程HDR离线调查与分阶段门禁](2026-10-31-hdr10-remote-offline.md) — kernel video application uu offline
- [uhd4正式完整构建、短烟测与队列工具修正](2026-10-31-uhd4-formal-smoke.md) — kernel board video hdr npu gpu deployment
- [uhd4正式准备与旧heavy锁阻塞，未上板](2026-10-31-uhd4-formal-preparation.md) — kernel deployment
- [HDR2双向恢复分解、uhd4r3细采样与长尾门禁](2026-10-31-hdr2-recovery.md) — kernel board video hdr application npu gpu
- [MCP与ICE定位、uhd4 PQ门禁及恢复速度余项](2026-10-31-hdr2-mcp-ice-pq.md) — kernel board video hdr application
- [uhd4主题整理与SDR回归，MCP/接收端门禁阻断](2026-10-31-hdr2-uhd4-gate.md) — kernel board video hdr npu gpu

## 2026-10-30

- [kbase r5零fault、WC heaps与三栈配对](2026-10-30-kbase-r5-window.md) — kernel gpu board video
- [kbase GBM缺少DMA heap与Vulkan DEVICE_LOST](2026-10-30-kbase-r4-window.md) — kernel gpu board video
- [kbase r3零WARN加载、EGL设备失败与助手恢复](2026-10-30-kbase-r3-window.md) — kernel gpu board video
- [kbase首窗WARN门禁失败与5.15回退](2026-10-30-kbase-window.md) — kernel gpu board video
- [7.3 kbase外部模块离线候选与ABI检查](2026-10-30-kbase-offline.md) — kernel gpu audit packaging
- [HDR2a5产品DMA恢复、逐代退休与4K60门禁](2026-10-30-hdr2a5-window.md) — kernel board video hdr application
- [HDR2a3的VUI、色差、4K60与退休/产品恢复余项](2026-10-30-hdr2a3-window.md) — kernel board video hdr
- [HDR2a2的MCP、4K60与VUI/色准余项](2026-10-30-hdr2a2-window.md) — kernel board video hdr
- [MCP开启PQ与HDR2编码协商阻断](2026-10-30-hdr2-unified-window.md) — kernel board video hdr
- [HDR2 PQ的SDR基线与受限shadow诊断](2026-10-30-hdr2-pq-window.md) — kernel board video hdr
- [uhd3 GPU候选与HDR离屏窗口A](2026-10-30-gpu-hdr-window-a.md) — kernel board video benchmark
- [NPU与nodebug正式uhd3合入、回归及manager EDID部署](2026-10-30-uhd3-formal-regression.md) — kernel board video manager deployment
- [nodebug两启动对门禁与绑核尺寸曲线](2026-10-30-nodebug-paired-gate.md) — kernel board benchmark video
- [nodebug消除tmpfs写入差距与60fps回归](2026-10-30-nodebug-memory-window.md) — kernel board benchmark video
- [YOLO端到端差距定位到文件写入](2026-10-30-npu-e2e-window.md) — kernel board benchmark
- [GPU同块回跳修复与快轮询窗口](2026-10-30-gpu-repair-window.md) — kernel board video benchmark
- [uhd2四启动对性能门禁仍不确定](2026-10-30-npu-boot-pairs.md) — kernel board benchmark
- [保留循环候选、正确性与冷恢复实测](2026-10-30-gpu-loop-window.md) — kernel gpu board benchmark
- [uhd2集成输出与并行通过，DenseNet性能阻断pin](2026-10-30-npu-uhd2-acceptance.md) — kernel board benchmark video
- [Mesa展开候选与10ms调频配对窗口](2026-10-30-gpu-candidate-window.md) — kernel gpu board benchmark
- [npu4三模型、取消与视频并行门禁通过](2026-10-30-npu4-acceptance.md) — kernel board benchmark video
- [GPU 性能差距分解窗口](2026-10-30-gpu-diagnosis-window.md) — kernel gpu board benchmark
- [npu3 视频恢复与 YOLO缓存合同、恢复后延迟失败](2026-10-30-npu3-acceptance.md) — kernel board benchmark video
- [npu2 双模型通过与 YOLO/视频门禁失败](2026-10-30-npu2-acceptance.md) — kernel board benchmark video
- [GPU 三栈上板验收](2026-10-30-gpu-acceptance.md) — kernel gpu board benchmark
- [ADLA 首次上板验收与 npu1 probe 失败](2026-10-30-npu-adla-acceptance.md) — kernel board benchmark
- [私有 Mesa 26.2.6 离线运行时](2026-10-30-gpu-runtime.md) — kernel gpu packaging
- [GPU 完整性审查与默认降频候选](2026-10-30-gpu-parity.md) — kernel gpu audit
- [7.3 保留运行时与发布锁同步](2026-10-30-kernel73-retained-pin.md) — kernel deployment application
- [第三轮尺寸与原生 GPU 定向复验](2026-10-30-kernel73-gap-r3.md) — kernel video manager deployment
- [7.3 差距补齐批量验证](2026-10-30-kernel73-gap-validation.md) — kernel video usb manager deployment

## 2026-10-29

- [管理面板中英文界面](2026-10-29-manager-i18n.md) — manager application deployment
- [One-KVM 新图标](2026-10-29-onekvm-icon.md) — application deployment
- [One-KVM 连接统计的采样精度](2026-10-29-onekvm-connection-stats.md) — application deployment board

## 2026-10-28

- [One-KVM 控制台面板、虚拟键盘与 WebRTC 套接字耗尽](2026-10-28-onekvm-console-panels.md) — application deployment board
- [One-KVM 终端浮层与断线提示](2026-10-28-onekvm-terminal-polish.md) — application deployment board
- [One-KVM 板子终端侧栏](2026-10-28-onekvm-board-terminal.md) — application deployment board
- [管理器界面体验整理](2026-10-28-manager-uiux.md) — manager application deployment board
- [7.3 对当前 5.15 功能的差距复核](2026-10-28-kernel73-parity-audit.md) — kernel video audio usb application audit
- [低频原生音频诊断](2026-10-28-audio-diagnostics.md) — audio application board
- [源端空闲时非静音音频与数字静音恢复](2026-10-28-source-idle-audio.md) — audio uu application board
- [UDP 同帧批量发送候选与延迟对照](2026-10-28-udp-batch-latency.md) — video application board benchmark

## 2026-10-27

- [当前 One-KVM 延迟与 SDR 缩放瓶颈](2026-10-27-current-video-latency.md) — video application board benchmark
- [HEVC 无损与固定 QP](2026-10-27-hevc-quality.md) — video application deployment board
- [共享编码的 SRT 与 RTMP 输出](2026-10-27-shared-broadcast.md) — video audio application deployment board
- [NPU 真实推理与分类、文字识别验证](2026-10-27-npu-inference.md) — kernel application board benchmark
- [UU 分辨率请求被 HDR 能力检查阻塞](2026-10-27-uu-resolution-hdr-preference.md) — uu video application deployment board
- [管理器资源趋势 GPU 使用率](2026-10-27-manager-gpu-trends.md) — manager application deployment board
- [信号变化自动恢复与切换停顿](2026-10-27-signal-recovery.md) — video application deployment board benchmark
- [UU 原生 HDR 能力与非对齐行宽修复](2026-10-27-uu-hdr.md) — video uu application deployment board
- [UU HDR 降分辨率的 GPU 缩放](2026-10-27-uu-hdr-scale.md) — video uu application deployment board benchmark
- [四套 KVM 共用 HDR GPU 缩放](2026-10-27-all-kvm-hdr-scale.md) — video application deployment board benchmark
- [超宽屏 SDR 硬件缩放与尺寸控制](2026-10-27-sdr-scale-controls.md) — video application pikvm deployment board benchmark

## 2026-10-26

- [四套 KVM 的远程 HDR 接入](2026-10-26-all-kvm-hdr.md) — video application manager deployment board
- [Chrome 与 Safari 的远程 HDR 兼容性复核](2026-10-26-hdr-browser-compatibility.md) — video application board
- [远程 HDR 全局默认与源端切换](2026-10-26-hdr-global.md) — video manager uu application deployment board
- [GPU 转换、DMA Main10 与网页真 HDR 60fps](2026-10-26-hdr-gpu-pipeline.md) — video application deployment board benchmark
- [HDR 分段测量与私有 Mali Vulkan 驱动](2026-10-26-hdr-gpu.md) — video kernel deployment board benchmark
- [远程 HDR 像素修复与 SDR 自动选择](2026-10-26-remote-hdr-pixels.md) — video application kernel deployment board
- [远程 Main10 HDR 与高刷超宽屏](2026-10-26-remote-hdr-modes.md) — video kernel uu application deployment board
- [统一 RTK UHD HDR 入口](2026-10-26-rtk-unified.md) — video application manager board deployment
- [VRR 范围声明纠正与 4K 输入验证](2026-10-26-vrr-range-4k.md) — video kernel application board
- [真实 VRR 输入与 One-KVM 连续画面](2026-10-26-vrr-live.md) — video kernel application board
- [VRR 输入候选部署与 KVM 回归](2026-10-26-vrr-input.md) — video kernel application manager board deployment
- [5.15 1080p120 候选部署](2026-10-26-1080p120.md) — video kernel application board deployment
- [厂商编码器码率峰值与 VBV 对照](2026-10-26-encoder-vbv.md) — video board benchmark

## 2026-10-25

- [VIM4 SRTP HMAC 后端正式接入](2026-10-25-srtp-openssl-hmac.md) — video application board benchmark
- [RTP 发送离线基准与板端 CPU 回放](2026-10-25-rtp-send-benchmark.md) — video application board benchmark
- [交帧之后的编码、发送与浏览器分段](2026-10-25-video-downstream-latency.md) — video application board
- [显示与采集交付边界核实](2026-10-25-video-front-boundaries.md) — video kernel application board
- [One-KVM 同帧分段延迟](2026-10-25-video-stage-latency.md) — video application board
- [VDIN1 逐缓冲交付与 RDMA 时序核实](2026-10-25-vdin1-frame-handoff.md) — video kernel board
- [5.15 / 7.3 视频延迟对照与 Wave5 启动修复](2026-10-25-kernel-video-latency.md) — video kernel application deployment board
- [原生 HDR 双路径的四应用采集修复](2026-10-25-native-hdr-all-kvm.md) — video application pikvm deployment board
- [管理面板前端重构验收与部署](2026-10-25-manager-ui.md) — manager application deployment
- [UU 协议审查与 P1 修复验收](2026-10-25-uu-protocol-audit.md) — uu application video audio usb audit
- [UU P1 修复部署与自动验证](2026-10-25-uu-p1-validation.md) — uu onekvm video board
- [UU 缩放 CMA 生命周期与工具连接](2026-10-25-uu-cma-tools.md) — uu onekvm video board
- [UU 限定板子文件传输](2026-10-25-uu-files.md) — uu onekvm usb application board
- [厂商 HDR 输入黑屏、采集位深与输出域](2026-10-25-vendor-passthrough-hdr.md) — kernel video audio manager board
- [厂商原生 HDR 与 SDR KVM 双路径交付](2026-10-25-native-hdr-dual-path.md) — kernel video audio onekvm board
- [原生 HDR 正式部署与 AVI 色域恢复](2026-10-25-native-hdr-production.md) — kernel video manager onekvm board
- [原生 HDR↔SDR 采集颜色跟随与独立曲线](2026-10-25-native-hdr-color.md) — kernel video uu onekvm board
- [HDMI 输出 HDR 偏好与独立显示映射](2026-10-25-passthrough-hdr-switch.md) — kernel video manager deployment board
- [透传音频 xrun 原地恢复与连续 TX](2026-10-25-passthrough-audio-recovery.md) — audio video manager deployment board
- [厂商 VAPB 最低需求修复、60fps 与默认内核部署](2026-10-25-vapb-clock.md) — kernel video audio uu deployment board
- [厂商 5.15 HDMI 音频桥与 KVM 共存](2026-10-25-vendor-passthrough-audio.md) — audio video manager deployment board
- [音频寄存器只读诊断触发重启](2026-10-25-audiobus-read-abort.md) — audio kernel deployment board uu
- [厂商 5.15 真实 1080p60 EDID 跟随](2026-10-25-vendor-passthrough-1080p.md) — video manager uu deployment board
- [UU 缩放生产合入与时钟失败降级](2026-10-25-uu-scaling-production.md) — video application uu deployment board

## 2026-10-24

- [UU 缩小输出的 GE2D 时钟与流水线修复](2026-10-24-uu-scaled-60fps.md) — video application uu deployment board
- [厂商 5.15 透传 OUT 热插拔恢复](2026-10-24-vendor-passthrough-hpd.md) — kernel video manager deployment board
- [厂商 5.15 透传 TEE 离线设计](2026-10-24-vendor-passthrough-design.md) — kernel video audio manager deployment
- [厂商 5.15 周期黑屏诊断与修复](2026-10-24-vendor-passthrough-blackout.md) — video manager deployment board
- [厂商 5.15 HDMI 透传交付与待验证项](2026-10-24-vendor-passthrough.md) — kernel video audio manager deployment board
- [颜色候选交付门禁失败与管理器预览](2026-10-24-display-color-user-handoff.md) — kernel video usb manager deployment board
- [HDMI 透传第二阶段暂停与恢复入口](2026-10-24-hdmi-passthrough.md) — kernel video deployment board
- [7.3颜色与透传源码合入及默认开关](2026-10-24-hdmi-integration.md) — kernel video deployment
- [HDMI 采集 ERROR、周期量化与厂商对照（进行中）](2026-10-24-hdmi-capture-quantization.md) — kernel video deployment board
- [HDMI RX 计量器与持续采集复测（进行中）](2026-10-24-hdmi-capture-stability.md) — kernel video deployment board
- [HDMI OUT 颜色自环校准与厂商基准](2026-10-24-display-color-loop.md) — kernel video deployment board

## 2026-10-23

- [统一合入主线，保留稳定 KVM 部署](2026-10-23-mainline-integration.md) — kernel application deployment board
- [RX 阶段收尾：矩阵残留问题与稳定 KVM](2026-10-23-hdmirx-lowclock-closeout.md) — kernel video usb deployment board
- [M3 4K 显示器窗口：链路与出声，颜色和 GPU 阻塞](2026-10-23-display-m3-window4.md) — kernel video audio usb deployment board
- [HDMI 模式切换失锁：基线对照与稳定判定](2026-10-23-hdmirx-lowclock.md) — kernel video deployment board
- [Wave5 正式批次：HDMI 模式门禁失败并回退](2026-10-23-wave5-formal-deploy.md) — kernel video audio usb application deployment board
- [M3 HDMI 离线验证与一次性启动清单](2026-10-23-display-m3-hdmi-validation.md) — kernel video audio deployment
- [M2 第三窗口：物理颜色对照、TX 录音与 HPD 修复](2026-10-23-display-m2-window3.md) — kernel video audio deployment board
- [M3 HDMI HDR、10-bit、420 与跳行缩放（候选，HDR 与颜色阻塞）](2026-10-23-display-m3-hdmi-color.md) — kernel video audio deployment
- [M3 VD1/VD2、PPS 与 NV12 atomic scanout（离线候选，未上板）](2026-10-23-display-m3-video-planes.md) — kernel video deployment
- [T7 H.264 FIFO 修正、43 次 IRQ 与全零帧现场结果](2026-10-23-vdec-timeout.md) — kernel video usb deployment board
- [T7 H.264 启动链与安全微码审计明细](2026-10-23-vdec-timeout-audit.md) — kernel video
- [T7 VDEC 多 fd 所有权与分级解码窗口](2026-10-23-vdec-multifd.md) — kernel video usb deployment board
- [M3 视频 MIF、PPS 相位与 VD2 SRAM（离线，尚无 video plane）](2026-10-23-display-m3-video-parameters.md) — kernel video deployment
- [T7 VDEC p0 访问通过、compliance 阻塞与 RX 停顿归类](2026-10-23-vdec-p0-window.md) — kernel video usb deployment board
- [M3 DMA 边界修复、启动接管与剩余视频路径合同（离线）](2026-10-23-display-m3-dma-contracts.md) — kernel video deployment
- [T7 VDEC 外部控制寄存器全量差分](2026-10-23-vdec-register-diff.md) — kernel video usb deployment board
- [M3 多层退休、SRAM 所有权与 OSD overlay/cursor（离线）](2026-10-23-display-m3-layers.md) — kernel video audio deployment
- [VDEC APB 候选第九步仍失败，看门狗恢复](2026-10-23-vdec-apb-window.md) — kernel video usb deployment board
- [Wave5 E01 动态控制、分层 GOP 与 LTR 上板窗口](2026-10-23-wave5-e01-window.md) — kernel video usb deployment board
- [厂商 H.264 活体对照与物理时钟检查候选](2026-10-23-vdec-vendor-live.md) — kernel video usb deployment board
- [Wave5 E01 动态参数、LTR 与多层 GOP（离线）](2026-10-23-wave5-e01-runtime-gop.md) — kernel video
- [Wave5 E01 ROI、任意 GOP 与 VUI/SEI 剩余合同](2026-10-23-wave5-e01-metadata-abi.md) — kernel video
- [T7 GCLK 十三步远程窗口：首次读失败、看门狗恢复](2026-10-23-vdec-gclk-window.md) — kernel video usb deployment board
- [M3 首批离线实现：OSD 原子属性与标准 CEC，其余显示层待开发](2026-10-23-display-m3.md) — kernel video audio deployment
- [T7 GCLK_EN 访问条件与分步候选（离线）](2026-10-23-vdec-gclk-offline.md) — kernel video deployment
- [T7 VDEC MDEC 远程分级窗口](2026-10-23-vdec-mdec-window.md) — kernel video usb deployment board
- [M2 颜色修正与第二个一次性窗口：共存通过，物理颜色和 TX 音频待验](2026-10-23-display-m2-window2.md) — kernel video audio deployment board
- [M2 首次一次性上板：60Hz 翻页、PRIME 上屏，颜色错误阻塞验收](2026-10-23-display-m2-window1.md) — kernel video audio deployment board
- [Wave5 编码器批量窗口与 T7 硬件看门狗](2026-10-23-wave5-parity-window.md) — kernel video deployment board
- [Wave5 E02 可见尺寸与 E01 标准控件离线候选](2026-10-23-wave5-encoder-parity.md) — kernel video
- [Wave5 E01 全量参数与标准控件映射](2026-10-23-wave5-encoder-controls.md) — kernel video
- [Wave5 E01 公共、动态与逐帧参数协议附表](2026-10-23-wave5-encoder-protocol.md) — kernel video
- [M2 原生 ENC2 模式切换：PLL/VENC/PHY、SCDC 与厂商参数对比（离线）](2026-10-23-display-m2-modeset.md) — kernel video audio deployment
- [HDMI RX 同链路 7.3 / 厂商 5.15 十分钟对照](2026-10-23-hdmirx-vendor-comparison.md) — kernel video audio deployment board
- [M2 RDMA 翻页与独立 TX 音频：离线实现，原生 modeset 仍缺失](2026-10-23-display-m2-rdma-audio.md) — kernel video audio deployment
- [厂商5.15一次性启动往返与GPU用户态识别](2026-10-23-vendor-boot-gpu.md) — kernel deployment board
- [M1 合入与 M2 离线开发：HPD、EDID、线性 PRIME 和音频接口](2026-10-23-display-m2.md) — kernel video audio deployment
- [Wave5 运行时恢复：五轮注入、失败隔离与一次性启动窗口](2026-10-23-wave5-runtime-window.md) — kernel video deployment board
- [M1 第七窗口：一次性启动、RMFB、翻页与 Panfrost](2026-10-23-display-m1-window7.md) — kernel video deployment board
- [HDMI 音频与采集稳定性：27轮自动恢复与EAGAIN残留](2026-10-23-kvm-audio-capture-stability.md) — kernel audio video application deployment board
- [HDMI 音频 PCM 生命周期修复与 SARADC 正式部署：九类通过](2026-10-23-kvm-audio-capture-stability-deploy.md) — kernel audio video application deployment board
- [T7 DRM M1 固定输出、RMFB 崩溃与离线修复](2026-10-23-display-m1.md) — kernel video audio usb deployment board
- [M1 一次性启动与恢复安全网](2026-10-23-display-m1-safety.md) — kernel deployment
- [T7 DRM M1 共存接管设计](2026-10-23-display-m1-design.md) — kernel video audio
- [Wave5 独立电源域复位与固件冷重载（离线候选）](2026-10-23-wave5-genpd-recovery.md) — kernel video power deployment
- [Wave5 运行时硬复位地址冲突与拓扑保护（仅离线，恢复受阻）](2026-10-23-wave5-runtime-recovery.md) — kernel video
- [Wave5 隔离正式窗口复验](2026-10-23-wave5-isolation-final.md) — kernel video audio usb manager deployment board
- [Wave5 超时隔离与十轮验收（第二轮）](2026-10-23-wave5-isolation.md) — kernel video application deployment board
- [Wave5 恢复前置修复与厂商复位审查（未上板）](2026-10-23-wave5-recovery.md) — kernel video
- [M0 第四轮音频归因与发布](2026-10-23-display-m0-r4.md) — kernel video audio usb manager deployment board
- [HDMI RX 音频 ENOLINK 基线对照](2026-10-23-hdmirx-audio-enolink.md) — kernel audio application board
- [M0 音频复核与正式部署回退](2026-10-23-display-m0-deploy.md) — kernel video audio usb manager deployment board
- [U-Boot framebuffer 的 simpledrm 接管实验](2026-10-23-display-m0.md) — kernel video audio usb manager deployment board
- [7.3 T7 HDMI 显示输出可行性调查](2026-10-23-display-feasibility.md) — kernel video audio board
- [T7 显示硬件与源码明细](2026-10-23-display-hardware-audit.md) — kernel video audio

## 2026-10-22

- [手动 PD 协商合同持久化并保留](2026-10-22-pd-manual-contract.md) — usb deployment board
- [SARADC channel 2 超时取证与离线候选](2026-10-22-saradc-timeout-audit.md) — kernel board
- [Wave5 首轮部署采集停止复核](2026-10-22-wave5-first-failure-audit.md) — kernel video board
- [Wave5 尺寸与关闭路径防护正式部署](2026-10-22-edge-wave5-deploy.md) — kernel video audio usb manager deployment board
- [Wave5 HEVC 防护候选现场验证并恢复原模块](2026-10-22-wave5-hevc-field.md) — kernel video usb deployment board
- [U-Boot 现场复位分析与 microSD 安全验证](2026-10-22-uboot-sd-recovery.md) — usb kernel deployment
- [7.3 ramoops/pstore 正式部署并保留](2026-10-22-edge-pstore-deploy.md) — kernel deployment board
- [P1 浏览器音频观察器复核](2026-10-22-p1-browser-audio.md) — audio application board
- [PD 热重启历史合同卡片](2026-10-22-pd-warm-carryover.md) — usb manager deployment board
- [7.3 T7 标准硬件解码可行性调查](2026-10-22-vdec-feasibility.md) — kernel video board
- [T7 解码硬件、固件与主线差异明细](2026-10-22-vdec-hardware-audit.md) — kernel video
- [Wave521C GET_VPU_INFO 实机取证](2026-10-22-vdec-wave5-capabilities.md) — kernel video board
- [T7 stateless 解码离线准备](2026-10-22-vdec-t7-offline.md) — kernel video
- [T7 H.264 完整离线候选与现场恢复脚本](2026-10-22-vdec-candidate.md) — kernel video deployment
- [T7 解码候选现场分级验证与恢复](2026-10-22-vdec-field.md) — kernel video usb deployment board
- [T7 VDEC SError 离线修正与分级上电门禁](2026-10-22-vdec-power-fix.md) — kernel video deployment
- [T7 VDEC 第二次现场：单读通过、compliance panic与恢复](2026-10-22-vdec-field2.md) — kernel video usb deployment board
- [T7 MDEC SError 离线排查与安全策略、单读门禁](2026-10-22-vdec-mdec-offline.md) — kernel video deployment
- [P2 PD Request＋KASLR 合并固件候选](2026-10-22-p2-uboot-combined.md) — usb kernel deployment
- [P2 有界持久 journal 部署并保留](2026-10-22-p2-journal-deploy.md) — deployment board
- [P2 ramoops 候选与正常重启验证](2026-10-22-p2-pstore.md) — kernel deployment board
- [P1 HDMI 音频分段定位](2026-10-22-p1-hdmi-audio.md) — kernel audio application board
- [P1 HDMI 帧率、恢复与 CMA 复核](2026-10-22-p1-hdmi-video.md) — kernel video board
- [P2 USB 音频、组合与 RNDIS 核对](2026-10-22-p2-usb-audio.md) — usb audio application board
- [P2 KASLR、随机数与 U-Boot 离线候选](2026-10-22-p2-kaslr.md) — kernel deployment board
- [P2 GPU 电压表复核](2026-10-22-p2-gpu-voltage.md) — kernel
- [P2 挂起与唤醒离线审查](2026-10-22-p2-suspend-audit.md) — kernel usb
- [P2 持久日志与 ramoops 方案](2026-10-22-p2-persistent-logs.md) — kernel deployment
- [v7.3 正式版第三轮部署并保留](2026-10-22-edge-7-3-final-retained.md) — kernel video audio usb manager deployment board
- [U-Boot 固定 5V USB PD Request（离线候选）](2026-10-22-uboot-pd-request.md) — usb deployment

- [Wave5 非对齐 HEVC 挂起离线分析与局部修复候选](2026-10-22-wave5-hevc-hang-analysis.md) — kernel video
- [v7.3 正式部署尝试与自动回退](2026-10-22-edge-7-3-final-deploy.md) — kernel video audio usb manager deployment board
- [BCM43752 固件转储离线分析（原样本缺失）](2026-10-22-wifi-coredump-analysis.md) — kernel
- [v7.3 正式版运行时、PD-USB 与部署离线准备](2026-10-22-deploy-7-3-final-prep.md) — usb manager deployment kernel
- [HDMI 动态 LPCM 与无链路恢复](2026-10-22-edge-hdmi-audio.md) — kernel audio application deployment board
- [7.3 日志分级与 T7 硬件随机数](2026-10-22-edge-diag.md) — kernel usb deployment board
- [7.3 正式版 rebase 与整包回归](2026-10-22-edge-7-3-final.md) — kernel deployment board video usb
- [7.3 正式版整包上板回归](2026-10-22-edge-7-3-final-board.md) — kernel deployment board video usb
- [PD 热重启原因与主动查询风险审查（未刷写）](2026-10-22-pd-warmboot-audit.md) — usb manager deployment board
- [U-Boot PD 交接刷写与双内核验证](2026-10-22-pd-firmware-deploy.md) — usb manager deployment board
- [U-Boot PD 交接与管理器候选（第一轮离线准备）](2026-10-22-pd-firmware-handoff.md) — usb manager deployment board
- [7.3 HDMI RX 输入模式泛化](2026-10-22-edge-hdmi-modes.md) — kernel video application deployment board
- [HDMI 模式最终产物复核](2026-10-22-edge-hdmi-modes-final.md) — kernel video application deployment board

## 2026-10-21

- [7.3 GPU/IR 合并内核正式部署](2026-10-21-edge-gpu-ir-deploy.md) — kernel deployment board video usb
- [7.3 IR 开机自动加载 Khadas 键表](2026-10-21-edge-ir-autoload.md) — kernel deployment board
- [7.3 IR、板载按键与 SPI NOR 节点](2026-10-21-edge-ir-keys-spinor.md) — kernel board
- [7.x Panfrost 调频与 GPU 供电](2026-10-21-edge-gpu-devfreq.md) — kernel deployment board
- [7.x Wi-Fi Direct 创建、扫描与并发建组](2026-10-21-edge-wifi-p2p.md) — kernel deployment board
- [7.x 管理器状态、界面与 WPA3 适配](2026-10-21-manager-mainline-status.md) — manager kernel usb application deployment board
- [双内核完整系统集成与往返验收](2026-10-21-dual-kernel-integration.md) — application kernel video usb deployment
- [7.x USB 功能接入与主机传输](2026-10-21-edge-usb-functions.md) — usb application kernel deployment board
- [Wi-Fi 固件排查与 MJPEG 帧率分段](2026-10-21-edge-wifi-fps.md) — kernel video application deployment board
- [7.x VDIN 缩放与硬件 MJPEG](2026-10-21-edge-scaling-jpeg.md) — kernel video application deployment board
- [7.x 音画测量校准与漂移复核](2026-10-21-edge-av-calibration.md) — video audio application board
- [7.x HDR 切换与稳定性](2026-10-21-edge-hdr-stability.md) — video audio application deployment board

## 2026-10-20

- [One-KVM 接入 7.3 V4L2/Wave5](2026-10-20-onekvm-wave5.md) — application kernel video board
- [One-KVM 7.3 CPU 性能定位](2026-10-20-onekvm-performance.md) — application kernel video board
- [本地基准与 VDIN 直接 DMA](2026-10-20-direct-dma-benchmark.md) — application kernel video board
- [驱动原生基准、AVC profile 与采集内存](2026-10-20-driver-profile-memory.md) — kernel video board
- [实验 One-KVM 局域网登录入口](2026-10-20-edge-lan-gateway.md) — application manager board
- [7.3 One-KVM HID 接入](2026-10-20-edge-hid-integration.md) — application usb audio board
- [7.x UHD 清晰度与 Mac 渲染分辨率](2026-10-20-edge-uhd-detail.md) — application video board
- [7.3 HDMI LPCM 与 One-KVM 音频](2026-10-20-edge-hdmi-audio.md) — kernel audio application board
- [7.x Wave5 逐行刷新与卡顿对照](2026-10-20-edge-cyclic-refresh.md) — kernel video application board
- [7.x 输入状态等待与端到端延迟](2026-10-20-edge-status-latency.md) — kernel video application board
- [7.x 安静风扇曲线](2026-10-20-edge-quiet-fan.md) — kernel video deployment board
- [7.x BCM43752 SDIO Wi-Fi](2026-10-20-edge-wifi.md) — kernel deployment board
- [7.x 启动风扇与 HDMI 恢复](2026-10-20-edge-recovery.md) — kernel video audio application deployment board
- [7.x HDMI 真实输入时序](2026-10-20-edge-input-timings.md) — kernel video audio application deployment board
- [7.x 失锁期间的状态查询与队列锁](2026-10-20-edge-queue-lock.md) — kernel video audio deployment board
- [7.x 1080p60/4K60 自动切换与缓冲回收](2026-10-20-edge-dynamic-modes.md) — kernel video audio application deployment board
- [7.x HDR10 链路与元数据观测](2026-10-20-edge-hdr-observation.md) — kernel video deployment board
- [7.x HDR10 采集与 HDR→SDR](2026-10-20-edge-hdr-capture.md) — kernel video audio application deployment board
- [7.x HDR 高光与连接优化](2026-10-20-edge-hdr-optimization.md) — video audio application deployment board

## 2026-10-19

- [7.3 edge 首次启动](2026-10-19-edge-firstboot.md) — kernel deployment board
- [7.3 CRG UDC 与最小 HID 实测](2026-10-19-crg-udc.md) — kernel usb board
- [7.3 CRG 真实 HID 与只读虚拟盘](2026-10-19-crg-composite.md) — kernel usb board
- [7.3 HDMI RX 资源与源端 5V 实测](2026-10-19-hdmirx-resources.md) — kernel video board
- [7.3 HDMI RX EDID 与源端 DDC 读回](2026-10-19-hdmirx-ddc.md) — kernel video usb board
- [7.3 HDMI RX 固定频率 PHY PLL 实测](2026-10-19-hdmirx-phy.md) — kernel video board
- [7.3 HDMI RX 1080p 完整视频帧](2026-10-19-hdmirx-frames.md) — kernel video board
- [7.3 HDMI V4L2 连续取帧](2026-10-19-hdmirx-v4l2.md) — kernel video board
- [7.3 HDMI 私有 DMA 环与 1080p60](2026-10-19-hdmirx-dma-ring.md) — kernel video board
- [7.3 HDMI DMA-buf 与软件 H.264](2026-10-19-hdmirx-dmabuf.md) — kernel video board
- [7.3 Wave521 硬编码与 4K60](2026-10-19-wave521-uhd.md) — kernel video board

## 2026-10-18

- [One-KVM 原生指针默认样式](2026-10-18-onekvm-native-cursor.md) — application deployment
- [One-KVM UU 远程终端与卡片重设计](2026-10-18-onekvm-uu-terminal.md) — application uu usb deployment

- [NAS 网络存储与 NAS 文件夹 U 盘](2026-10-18-nas-storage-usb-disk.md) — manager usb kernel
- [One-KVM H.264 每秒停顿](2026-10-18-onekvm-h264-periodic-stutter.md) — application video
- [One-KVM MCP Fit 截图提前“超时”](2026-10-18-onekvm-snapshot-fit.md) — application video deployment
- [管理器统一登录与 8080 KVM 网关](2026-10-18-unified-auth-gateway.md) — manager application deployment

## 2026-10-17

- [One-KVM 设备端带声音录屏](2026-10-17-onekvm-device-recording.md) — application video audio

- [One-KVM HID 队列修复部署](2026-10-17-hid-queue.md) — usb uu application deployment
- [UU 视频诊断统计部署](2026-10-17-uu-video-metrics.md) — uu video application deployment

- [供电信息只读验证](2026-10-17-power-telemetry.md) — usb manager board

- [Tailscale 管理修复部署](2026-10-17-tailscale-management-fixes.md) — manager application deployment
- [U-Boot 取消启动风扇测试](2026-10-17-uboot-quiet-fan.md) — kernel deployment
- [管理器 Wi-Fi 网络管理与热点模式](2026-10-17-wifi-client-hotspot.md) — manager deployment

## 2026-10-16

- [RTK UHD HDR 4K60 成为各应用内置 EDID](2026-10-16-rtk-uhd-hdr-builtin-edid.md) — video
- [CRG EP0 重复入队导致重启](2026-10-16-crg-ep0-double-queue-reboot.md) — kernel usb
- [共享虚拟介质状态与等待切换](2026-10-16-shared-media-state-wait-switch.md) — usb manager
- [管理器已有虚拟磁盘管理](2026-10-16-manager-virtual-disk.md) — usb manager
- [虚拟介质独立页面与跨应用介质状态](2026-10-16-virtual-media-page-cross-app.md) — usb manager
- [共享数据盘管理与四套 KVM 目录部署](2026-10-16-shared-data-disk-four-kvm.md) — usb manager
- [UU 信令与输入生命周期更新部署](2026-10-16-uu-signaling-input-lifecycle.md) — uu
- [4K60 8-bit YUV444 原始采集实测](2026-10-16-4k60-yuv444-raw-capture.md) — video
- [4:4:4 采集接口实现与生命周期修复](2026-10-16-yuv444-capture-interface-lifecycle.md) — video kernel
- [4:4:4 全帧处理优化至 4K60](2026-10-16-yuv444-full-frame-4k60.md) — video
- [4:4:4 编码能力核验与错误声明修复](2026-10-16-yuv444-encoder-capability.md) — video
- [PiKVM HDMI 音频周期性爆音](2026-10-16-pikvm-hdmi-audio-pops.md) — pikvm audio
- [数据盘交互修正与管理器动效](2026-10-16-data-disk-ui-motion.md) — manager
- [开发版本规则与管理器正式版部署](2026-10-16-development-release-versions.md) — manager deployment
- [四套 KVM 正式包部署](2026-10-16-kvm-release-deployment.md) — applications deployment

## 2026-10-15

- [PiKVM 隔夜降帧：采集线程与 CPU0 中断争用](2026-10-15-pikvm-overnight-fps-cpu0-irq.md) — pikvm video
- [部署 One-KVM UU 远程开发版本](2026-10-15-onekvm-uu-dev-deploy.md) — uu
- [UU 输出设置与缩放吞吐检查](2026-10-15-uu-output-scaling-throughput.md) — uu video
- [UU 网页输出控制、名称与系统身份](2026-10-15-uu-output-controls-identity.md) — uu
- [UU Mac 身份的键盘错码](2026-10-15-uu-mac-identity-keycodes.md) — uu usb
- [UU 滚轮方向默认值与手动覆盖](2026-10-15-uu-scroll-default-override.md) — uu usb
- [UU 连接初期体感延迟诊断](2026-10-15-uu-initial-latency.md) — uu
- [UU H.265 协商与封包修正](2026-10-15-uu-h265-negotiation-packetization.md) — uu video
- [UU H.265 出画面与周期性发送阻塞](2026-10-15-uu-h265-picture-send-stalls.md) — uu video

- [Screen Sharing 退出后物理桌面未恢复：同步取证](2026-10-15-screen-sharing-desktop-not-restored.md) — video
- [管理器 EDID 预设接口验证](2026-10-15-manager-edid-preset-api.md) — manager
- [部署 EDID 管理器，并保留 UU 虚拟屏故障现场](2026-10-15-edid-manager-deploy-uu-virtual-screen.md) — manager uu
- [UU 虚拟屏恢复故障定位](2026-10-15-uu-virtual-screen-recovery.md) — uu video
- [UU 与网页滚轮对照及采样干扰](2026-10-15-uu-web-scroll-sampling-interference.md) — uu usb
- [管理器侧边栏、风扇曲线调节与 EDID 界面](2026-10-15-manager-sidebar-fan-edid-ui.md) — manager
- [PiKVM H.265 菜单与 Direct 实板部署](2026-10-15-pikvm-h265-menu-direct.md) — pikvm
- [PiKVM Direct 周期停顿与绘制延迟](2026-10-15-pikvm-direct-stalls-paint-latency.md) — pikvm video
- [One-KVM UU 会话链路展示与鼠键反转核对](2026-10-15-onekvm-uu-session-path-input-swap.md) — uu
- [UU 会话卡片界面整理](2026-10-15-uu-session-card-ui.md) — uu
- [RTK EDID 音频与 One-KVM 运动后延迟](2026-10-15-rtk-edid-audio-onekvm-motion-latency.md) — audio application
- [跨 KVM 运动播放与积压恢复](2026-10-15-cross-kvm-motion-playout-backlog.md) — video
- [不同系统缓冲差异的原因调查](2026-10-15-buffering-difference-causes.md) — video
- [One-KVM 尽快播放策略对照](2026-10-15-onekvm-asap-playout-comparison.md) — video application
- [One-KVM 正式启用低延迟播放](2026-10-15-onekvm-low-latency-playout.md) — video application
- [PiKVM 尽快播放策略部署与对照](2026-10-15-pikvm-asap-playout.md) — pikvm video

## 2026-10-14

- [HDR 输入映射到 SDR](2026-10-14-hdr-to-sdr.md) — video
- [HDR 审查修复与部署](2026-10-14-hdr-review-fix-deploy.md) — video
- [JetKVM 默认 EDID 改为 4K60 并部署](2026-10-14-jetkvm-default-edid-4k60.md) — application video
- [One-KVM VIM4 与三套界面切换](2026-10-14-onekvm-integration-three-ui.md) — application
- [One-KVM 输入状态与流设置](2026-10-14-onekvm-input-stream-settings.md) — application
- [One-KVM 虚拟盘初始化修复](2026-10-14-onekvm-virtual-disk-init.md) — application usb
- [One-KVM 本地扩展、看门狗与包更新](2026-10-14-onekvm-extensions-watchdog-update.md) — application
- [One-KVM HID 功能配置与 USB 组合](2026-10-14-onekvm-hid-usb-profiles.md) — application usb
- [4K60 高码率编码实验](2026-10-14-4k60-high-bitrate-experiment.md) — video
- [三套 KVM 自定义 60 Mbps 部署](2026-10-14-custom-60mbps-deploy.md) — video application
- [One-KVM 高码率连接偶发退化到 10fps](2026-10-14-onekvm-high-bitrate-10fps.md) — application video
- [Wave521 时钟与编码耗时](2026-10-14-wave521-clock-encode-time.md) — video
- [4K60 编码链路抖动与丢帧检查](2026-10-14-4k60-encode-jitter-drops.md) — video
- [WebRTC 视频分段卸载发送（.23）](2026-10-14-webrtc-segmentation-offload.md) — video
- [NanoKVM Wi-Fi 扫描空列表](2026-10-14-nanokvm-wifi-empty-scan.md) — application
- [提交工作区积累改动并部署 .24](2026-10-14-workspace-commit-deploy-24.md) — deployment
- [PiKVM VIM4 构建、集成和上板验证](2026-10-14-pikvm-build-integrate.md) — pikvm
- [PiKVM 切入检查补漏](2026-10-14-pikvm-switch-check-gaps.md) — pikvm
- [PiKVM HEVC、卡顿定位与全新 Ubuntu 组装](2026-10-14-pikvm-hevc-stutter-fresh-ubuntu.md) — pikvm deployment
- [PiKVM 卡顿：ICE 选路与实际收包接口](2026-10-14-pikvm-ice-path-receive-interface.md) — pikvm video

- [MJPEG 单帧耗时与 NanoKVM 分辨率菜单](2026-10-14-mjpeg-frame-time-resolution-menu.md) — video application
- [MJPEG 硬件编码与 4K 运动画面吞吐](2026-10-14-mjpeg-hardware-4k-throughput.md) — video
- [JetKVM 码率控件部署](2026-10-14-jetkvm-bitrate-control.md) — application
- [NanoKVM 码率菜单样式修正](2026-10-14-nanokvm-bitrate-menu-style.md) — application
- [NanoKVM 码率滑块部署](2026-10-14-nanokvm-bitrate-slider.md) — application

## 2026-10-13

- [编码可靠性与关键帧实验](2026-10-13-encoder-controls.md) — video

- [组件包部署闭环验证](2026-10-13-component-deploy-loop.md) — deployment
- [无人值守部署](2026-10-13-unattended-deploy.md) — deployment
- [保持画质的低延迟验证](2026-10-13-low-latency-quality.md) — video
- [键鼠输入延迟与行为](2026-10-13-input-latency-behavior.md) — usb
- [HDMI 静音修复及重新打包验证](2026-10-13-hdmi-mute-fix-repack.md) — audio
- [补齐原 NanoKVM 功能缺项](2026-10-13-nanokvm-missing-features.md) — application
- [HID 生命周期与部署可靠性](2026-10-13-hid-lifecycle-deploy-reliability.md) — usb kernel
- [采集分辨率菜单部署](2026-10-13-capture-resolution-menu.md) — application video
- [H.265 默认开放](2026-10-13-h265-default.md) — video
- [KVM 界面管理面板](2026-10-13-kvm-manager-panel.md) — manager
- [JetKVM 完整功能接入](2026-10-13-jetkvm-full-integration.md) — application
- [NanoKVM 正式部署与 JetKVM 往返切换](2026-10-13-nanokvm-deploy-jetkvm-switch.md) — application
- [NanoKVM 终端、镜像上传与可写 U 盘](2026-10-13-nanokvm-terminal-upload-writable-disk.md) — application usb
- [虚拟显示器退出后 HDMI 桌面未恢复](2026-10-13-virtual-display-hdmi-not-restored.md) — video

## 2026-10-12

- [串口、OOWOW 与 Ubuntu 首次启动](2026-10-12-initial-serial-oowow-ubuntu.md) — board
- [自编内核与 `/lib` 事故](2026-10-12-custom-kernel-lib-symlink.md) — kernel
- [HDMI 输入采集](2026-10-12-hdmi-input-capture.md) — video
- [采集→编码链路与 USB gadget](2026-10-12-capture-encode-usb-gadget.md) — video usb
- [Mac USB HID 实测与描述符修复](2026-10-12-mac-hid-descriptor-fix.md) — usb
- [PD 开机初始化固化](2026-10-12-pd-boot-init.md) — usb
- [WebRTC 网页 KVM](2026-10-12-webrtc-web-kvm.md) — video
- [4K 视频输出](2026-10-12-4k-video-output.md) — video
- [自动风扇和 Wave521 提频](2026-10-12-auto-fan-wave521-clock.md) — kernel video
- [应用主线调整为 NanoKVM-Pro](2026-10-12-switch-to-nanokvm-pro.md) — application
- [NanoKVM-Pro 首阶段部署](2026-10-12-nanokvm-pro-first-deploy.md) — application
- [NanoKVM 原版视频控件、MJPEG 与 VDIN 缓冲区释放](2026-10-12-nanokvm-video-controls-mjpeg-vdin.md) — application video
- [NanoKVM 终端、脚本、网络唤醒与镜像管理](2026-10-12-nanokvm-terminal-scripts-wol-images.md) — application
- [NanoKVM HDMI 音频、Ubuntu 管理与应用更新](2026-10-12-nanokvm-hdmi-audio-ubuntu-update.md) — application audio
- [4K60 编码预算与局域网 RTP 分包](2026-10-12-4k60-encoder-budget-rtp.md) — video
