# 2026-10-25：原生 HDR 正式部署与 AVI 色域恢复

## 结论与授权

[双路径实验及首次交付](2026-10-25-native-hdr-dual-path.md) 后，用户目视确认“没问题”，
批准 One-KVM 分支合入 vim4、原生 HDR 成为默认，不再新增备份/回退项，也不再测声音。
HDR 图标未单独获得目视确认；硬件 EOTF/AVI 及实际采集数据独立核验，不混为光学验收。

主仓首次正式接入 `6592215`；common_drivers 合入 `cb894fcbf`、One-KVM 合入 `24d35af8`、
manager `55158a0`。One-KVM 从合入后干净 vim4 构建，安装生产路径，使用正常服务入口，
不再依赖 `/run` 实验覆盖。私有标准 V4L2 插件纳入构建/组件包，避免系统厂商插件关闭主 RX。

## 补充发现及修复

首次正式默认重启后虽为 PQ、422 12-bit，持续复核发现 AVI 已退回 BT.709。
厂商 `construct_avi_packet()` 在 TX modeset 时重新初始化 AVI，只按分辨率设601/709；
HDR EOTF/元数据本身未变，VPP 未必重新发完整 HDR 包，所以仅验证 DRM EOTF 会漏检。
这与此前用户那次 RX 失锁导致的闪黑是两个不同问题，不能互相替代归因。

common_drivers `4b4346f8a` 在重建 AVI 时按有效 sink HDR 能力、当前 PQ/HLG/色域信息
保留 BT.2020，不把不支持 HDR 的 sink、BT.709 或 SDR 自动标成 HDR；显式 colorimetry
仍遵循厂商设置。真实 C 策略 fixture 覆盖 PQ、HLG、非标准色域、SDR 和无 HDR sink，
并加入 CI。manager `01a24cf` 要求 DRM EOTF 与 AVI BT.2020 同时正确才报告原生 running，
对应离线回归不再把“只有 PQ、没有 BT.2020”判为成功。无新增前端布局/文案改动。

重新构建完整 `5.15.137-vim4kvm-hdrdual2` Image、DTB、模块和 initrd；候选 tgz SHA256：
`8c682fd8ae76744f3b71b76747ae0fbaadc68fd3bf51744133f27eba58a280d7`。
运行模块 note SHA256：`04223ca9c63959ad7b4f11ad5c6eb370e21051c6df78afb7694a974e6e11144f`。
先一次性启动核对，再经标准 `promote.py --no-backup --native-hdr` 登记默认；
保留同 release 的旧资格记录，新模块 note 自动追加，避免后续部署误报“不支持”。

## 自动验证

hdrdual1 正式主线的无声动态源、60秒网页窗口：
H.264 3840×2160 60.0101fps，H.265 59.9926fps，两者 drop/lost/freeze/PLI 增量0；
呈现p95分别18.0/18.4ms、最大32.7/22.9ms。其后因发现 AVI 问题，不把这些数据
当作 HDR 色域正确的证明。KVM 实际 SDR 灰阶及10-bit显示源证据见双路径记录。

hdrdual2 一次性启动及正式默认重启均成功；实际运行/default 为
`5.15.137-vim4kvm-hdrdual2`，标准 boot alias 同步指向它。
为腾出空间仅删除已不被 extlinux/登记清单引用的 hdr1 旧 boot 产物，未新增备份。
重启后 TX 为2160p60、422 12-bit limited、DRM ST2084、AVI Extended/BT.2020，
静态元数据各值仍与源端合法零值匹配；不再出现“PQ但709”。
页面实际开关 enabled/checked、显示“透传中”，supported/running、hdrToSdr=false；
One-KVM、manager、视频透传、声音服务均 active、NRestarts=0，UDC configured。

hdrdual2 正式主线无声动态源、各60秒：H.264 4K **59.9950fps**，
H.265 4K **59.9937fps**，两者 drop/lost/freeze/PLI 增量0。
H.264浏览器呈现p95为31.9ms、195次回调未逐帧到达，但实际呈现/解码约60fps、
无>50ms间隔；H.265 p95为18.1ms、最大23.7ms，回调缺口0。
六张解码帧的16档灰阶均为0/17/34/50…236/252，RGB通道相等，与SDR基线一致。
不拿这些网页图像代替显示器 HDR 色差/光度测量。

默认重启后的05:33:55–06:03:55 UTC，完整1800秒、1799次采样：
TX modeset **0**、RX READY→WAIT_CLK_STABLE **0**、扫描停顿≥2秒 **0**、
ready持续丢失≥2秒 **0**。所有采样 signal/ready=true；1797次running、2次单次starting，
后两次前后扫描仍各推进60帧、下次恢复running，没有对应重设/失锁日志；状态瞬态原因未定。
结束时仍为PQ/BT.2020、422 12-bit、2160p60，四项服务active、无新增内核告警。
监测读取 TX modeset、RX 状态机、ready 及显示扫描帧推进，不是光学黑屏探测器。
声音仅检查服务 active，不播放测试音、不请用户听、不再做音频验收。

离线验证：主仓252项通过、7跳过；manager205项、12跳过及Go全量通过；
One-KVM746项通过、2忽略；原驱动fixture及新增 AVI fixture通过，完整内核构建通过。

## 已知边界

原闪黑对应04:40:57 UTC RX颜色/时钟失锁，约1秒恢复，后续重新协商HDR；同期无 TX
modeset/OUT HPD，测试图案数分钟前已退出。上游为何重新协商尚不能单凭日志确定。
HLG真实源/显示器、原生双路径跨模式与拔插长测、MJPEG独立采集支路、物理音画同步仍待验证。
当前选用 One-KVM；其他 KVM 应用不因本次合入而自动具备 VDIN1 采集能力。

本机证据在忽略目录 `logs/passthrough-hdr/`：native2-kernel-build-fixed、native2-stage、
native2-once-boot，以及后续 native2-default/monitor/page/video 记录；不写入认证数据。
