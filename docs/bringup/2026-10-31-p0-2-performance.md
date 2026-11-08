# 2026-10-31：P0-2分窗性能准备与接收预检

结论：第二轮快速实验完成5.15→uhd5→5.15往返，**B未通过运行时就绪门禁，无有效B性能样本，不能判断性能是否追平**。
第二轮结果见下节；第一轮离线准备与阻塞记录保留。原完整矩阵已由用户取消。

## 第二轮：快速初判，非正式门禁

使用sources.toml仍登记的uhd5（不是未正式登记的uhd6）。候选Image、DTB、模块沿用r12；
仅将恢复证明的normal→watchdog_reboot差异经共享verify_baseline审阅后重新封入trial.json，
内核build ID及八项保护文件哈希均未变。归档SHA256为
`0c09cff9cd5ff1639dc529862ad34f3651644407fdbb014aad461fdc64b1e04e`。
本轮21分47秒占板，共29张短票据（含只读诊断、失败及收尾），最长3分20秒，均经FIFO；
采样票据保存sampling=true，编译在heavy下先完成。FIFO等待不计占板。
与其他线交替排队，不能把本轮当作冻结环境的正式验收。不测声音，不向M4发送HID。

### 配对结果

原生配置为3840×2160 SDR HDMI输入→1920×1080p60采集，H.264/H.265均12Mbps、GOP60，
120帧预热+1800帧测量；5.15使用原生HDR双路径中的VDIN1/vim4vdin1src NV21，
uhd5预定使用VDIN0 NV12/Wave5，必要后端差异不能省略。
最终A为 `logs/p0-2-quick/A-before` / `A-after`，B为 `B-final`。
可公开复核的[完整原生JSON与失败状态](p0-2-quick-evidence.json)随提交保存。

| 指标 | 5.15前A | 7.3 uhd5 B | 5.15后A | B相对A均值差值 / 快速结论 |
|---|---:|---|---:|---|
| 采集FPS | 59.997682 | 未采样 | 59.998047 | — / 不确定 |
| H.264 FPS | 59.997973 | 未采样 | 59.998090 | — / 不确定 |
| H.265 FPS | 59.997778 | 未采样 | 59.998068 | — / 不确定 |
| H.264进程CPU，单核100% | 1.179845% | 未采样 | 1.161980% | — / 不确定 |
| H.265进程CPU，单核100% | 1.169491% | 未采样 | 1.157153% | — / 不确定 |
| H.264编码sink→src p50/p95，ms | 3.269 / 3.477 | 未采样 | 3.266 / 3.428 | — / 不确定 |
| H.265编码sink→src p50/p95，ms | 3.528 / 3.739 | 未采样 | 3.517 / 3.682 | — / 不确定 |
| 缓冲交付计数 | 各1920/1920 | 未采样 | 各1920/1920 | 无交付缺口；源端绝对丢帧未测 |
| 软件端到端p50/p95 | 无有效标记 | 未采样 | 无有效标记 | — / 不确定 |
| 媒体运行时就绪 | 通过 | 失败 | 返回校验通过 | 不达标，属于运行时匹配失败 |

所有“未采样”都不是0。A两侧FPS波动低于0.001fps；每项只有两个约30秒窗口，
不能由此推出尾部、画质、丢帧或三组门禁通过。失败均保留，工具修正后另建运行目录。

### 失败与归因

1. 原4K基准直接协商NV21失败：当前主采集实际为AMLY；secondary资格环境和标准V4L2插件
   路径也需与生产启动器一致。补齐后4K缓冲池激活失败，未证明是全局CMA耗尽；
   原失败JSON保留在A0、A0-secondary、A0-enabled、A0-final。缩到1080p才建立有效原生样本。
2. B已RAM启动uhd5，但journal明确报 `No validated VIM4 platform for this kernel`，
   HDMI unit失败，One-KVM为dependency失败，未越过启动就绪门禁。证据为
   `B-final/boot.log`、串口 `uart-1793503273603123000.log` 与
   `candidate-service-journal.log`。这是平台启动器的版本匹配问题，不能归因编码器吞吐。
   自动return-baseline仅一次，`returned-baseline-identity.json`证明5.15身份、保护文件、
   服务与UDC恢复通过。没有刷引导区、改默认项或手工补串口。
3. 仅视频receiver每窗30秒约1800回调、300次像素采样，却0有效标记。顶部及中间带均失败，
   不计算p50/p95；实际接收视频为3840×2160，与独立原生1080p测量分开。
   M6运动页经MCP仅启动一次；收尾时截图确认其他窗口覆盖了物理运动页，
   不能由持续tick证明采样时物理HDMI可见。这些轮次判受干扰，更换标记行未修复此问题。
   本来拟测的dispatch→呈现代理值还包含HTTP送源及绘制调度，本身也不是标准源绘制延迟。
4. MCP直连本机报No route to host，改用板端SSH回环；无viewer时截图超时，先建立仅视频
   receiver后成功。M6未开SSH、未输入终端命令或单独Shift，确认US后只输入浏览器URL。

原始证据在本worktree `logs/p0-2-quick/`，不公开含个人桌面的截图和凭据。
新基准二进制SHA256为 `a3c8f51c604567306787f3ebd563c3e018c6a5bdaa49cef32c3c0a6f883d8487`。
编译用-Werror，VM原生夹具通过；完整离线370项通过、14项环境跳过。
运行中的运动页最终经MCP关闭，未再启动；保留其他未启动的同址标签，不继续删除未知归属页面。
未更改M6输入法或显示设置；本线源服务器、浏览器接收进程及SSH转发均已停止，票据全部释放。

下一步先由统一候选线修正/验证平台启动器支持实际release并登记tested_build，
再在没有其他M6窗口操作的批次校验物理标记可见性。正式结论需补三组独立A/B/A、
每延迟窗≥1000有效标记、标准同钟源绘制端点、无像素回读呈现轮与画质核验。
本轮不会重开已取消的56窗矩阵；GPU仍仅复用r11，CPU/内存带宽及JPEG本轮未跑。

## 第一轮离线准备（历史）

离线协议和工具改动已准备，**当时没有完成关键组A/B/A，不能判断7.3是否替代5.15**。
完整矩阵超过3小时，本轮没有启动56窗长测。执行前仍需M6上的物理HDMI运动源及
同钟receiver入口；当前仅有开发M4环境，不能跨机直接相减墙钟或用虚拟屏冒充物理源。

## 已完成与验证

- 独立worktree/分支p0-2，基于c7c2342；不改主工作区、不改内核来源锁。
- 旧整夜计划改为56窗/21小时19分15秒矩阵，
  每窗≤30分钟；首组4K60 H.264 60Mbps预留3窗/64分30秒。每日缓存、跨窗epoch、
  构建/升级失效及失败保留规则明确。稳定性最多10分钟，不测声音。
- ARM64原生基准在vim4-build用 `-O2 -Wall -Wextra -Werror` 编译，原生计时/PTS/
  DMA lease夹具通过；无板端编译。Swift运动源预构建，macOS 27音频API弃用警告保留，
  未开启音频。板端已有sysbench/GStreamer/Python，无需临时安装。
- 增加独立One-KVM视频延迟接收入口，复用board-window的offer/close；离线模拟验证
  仅video recvonly、正确关闭session。1Hz记录器补meminfo；compare schema=2拒绝
  跨日/源变化/构建epoch变化和复用B，summary逐指标失败返回非零。
- board-window缓存可纳入公开settings JSON，避免codec/源/浏览器变化仍命中；
  receiver/baseline开启sampling后保存票据快照。队列宿主测试验证sampling等待heavy退出、
  阻止新heavy，未通过实际启动编译干扰采样来验证。
- 工作分支全套离线369项通过、14项跳过；原生GStreamer夹具另在VM通过。
  主工作区只运行规定离线检查：365项通过、9项跳过。跳过不是硬件通过；
  本任务无内核/DT改动，checkpatch/dt-binding/KUnit不适用。

预构建产物在本worktree `build/p0-2/`，SHA256：

| 二进制 | SHA256 |
|---|---|
| vim4-driver-bench（Linux ARM64） | cc38f551d70516572d04c5751904538f8d6f173471525523c2bddff8a2bdae69 |
| vim4-latency-source（macOS ARM64） | 73aaa1e2cd1555ef3689d382c3eaedf27726aa07a3878aa4e4ea24c0fdc1b4a6 |

## 上板结果与失败

所有板访问经board-queue，未切内核、未改默认启动项、未发HID、未录音。
5.15.137-vim4kvm-hdrdual6，boot ID b8c4daff-003f-4430-9f58-6b0944d9b262。
已有taint=12800，不能把此启动当干净内核告警对照。

| 项目 | 结果 | 边界 |
|---|---|---|
| 只读collect | one-kvm/gadget/HDMI服务active，UDC configured；audio能力available | 未证明音频内容或延迟；未采样声音 |
| 首次receiver | 失败：未设置MANAGER_PASSWORD | 未进入视频测量；保留失败日志 |
| 使用开发凭据直连8080 | 失败：Playwright EHOSTUNREACH | 不改系统网络；改SSH回环入口 |
| SSH转发18082→8081视频receiver | 3840×2160 H.264，10.0028秒，599解码帧，59.8834fps；丢帧/丢包/freeze增量均0 | 仅工具冒烟，无源ID，无B，无同条件配对；待测 |
| 原生capture/编码与软件端到端A/B/A | 未运行 | M6物理运动源/同钟接收入口未就绪 |

原始证据保留在本worktree `logs/p0-2-preflight/`、`logs/p0-2-loopback-receiver/`；
包含失败stderr、collect/dmesg、接收全部50ms样本、依赖检查、离线检查日志。
只读证据包 `evidence-1793497343071278000.tar.gz` SHA256：
`89b79093173a44eba35d43c36e1203f46b8f4383b36999df73cdd3308ad227d0`。
旧命名vim4-hdmi的依赖探测返回inactive，正确服务名vim4-kvm-hdmi在collect为active，
不把前者误报成音频/采集服务退化。所有票据已释放，SSH临时转发已关闭。
新增sampling快照保存后的补充验收票据在P0-1窗口后排队，尚未取得板子即主动取消，
没有接触其候选；该快照持久化尚未实板验证，既有sampling互斥由离线测试覆盖。

## 下一步与结论边界

先在M6准备预构建源程序和同钟receiver，核验物理运动标记、浏览器依赖与≤2ms时钟误差，
冻结公共用户态/信源/settings/epoch；再读取P0-1最新tested_build及可信RAM候选SHA。
当前uhd5只允许预演，统一候选出来后需重测，不能将本轮5.15短收帧拼入新候选A/B/A。
随后执行首组3窗（64分30秒上限），保留所有失败。此组也只有一组，三组门禁仍待测。
完整矩阵仍计划56窗；日期/epoch一致才可抵扣有效样本，跨日/构建需新增A。
本轮停止继续排队；剩余长测时间由用户决定。

GPU只复用[uhd5 r11七轮](2026-10-31-kbase-r11-policy.md)，不声称已测统一候选。
其余吞吐、CPU/带宽、分段延迟、画质和软件端到端尾部保持待测，不捏造不达标归因。
