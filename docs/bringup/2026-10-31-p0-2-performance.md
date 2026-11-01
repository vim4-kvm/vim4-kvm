# 2026-10-31：P0-2分窗性能准备与接收预检

结论：离线协议和工具改动已准备，**没有完成关键组A/B/A，不能判断7.3是否替代5.15**。
完整矩阵超过3小时，本轮没有启动56窗长测。执行前仍需M6上的物理HDMI运动源及
同钟receiver入口；当前仅有开发M4环境，不能跨机直接相减墙钟或用虚拟屏冒充物理源。

## 已完成与验证

- 独立worktree/分支p0-2，基于c7c2342；不改主工作区、不改内核来源锁。
- [旧整夜计划](../overnight-performance-plan.md)改为56窗/21小时19分15秒矩阵，
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
