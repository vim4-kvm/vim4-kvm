# 2026-11-06：.37 HEVC 一致性首轮修复验收计划

按协调者授权离线封包后自行排 FIFO sampling。先完成定向验收，再以同包重跑
132 条 Main/Main Still 8bit；不部署。来源及修复假设见
[四提交分析](2026-11-06-hevc-conformance-fixes.md)，对照为
[.36 全集](2026-11-06-hevc-full-results.md)。修复收益只按实际像素、帧数和接口结果报告。

## 源码、封包和离线门禁

源码固定 `3cbab82167a1dc3de870165a5a01fd7c66d48a86`，基于主线
`957910f06161aeda0fcf67fb162972203a16310b`，四提交只修改 HEVC 三个文件。
与 .36 对照，957910f0 的解码目录内容相同。独立 worktree
`/home/deepdream/src/linux-7.3-vdec-integration37`；独立生产 O=
`/home/deepdream/build/vdec-integration37/kernel`，独立 KUnit O= 在同根 `kunit`。
保留 .36、正式包及历史证据。只从旧目录读取 build.json 模板，不覆盖它们。
生产配置逐字节等于正式 kernel.config，含 CONFIG_DYNAMIC_DEBUG；release 为
`7.3.1-vim4-20261106.37`。生产 W=1 Image/DTB/modules、外部模块与封包已实际完成；
arm64 QEMU KUnit **34/34、无跳过**。原始输出保存在
`build/hwdecode-parity/integration37/` 的 build37.log、tip.kunit.json/log、tip.qemu.log。
heavy 票 1507 已释放。解码目录零诊断；全树 1168 条 warning，与 .36 规范化源码路径后
无新增独特文本，不写全树零警告。配置前后 cmp 一致；未改 DTS/binding。

| 产物 | 身份 |
|---|---|
| 源码 | `3cbab82167a1dc3de870165a5a01fd7c66d48a86` |
| GNU build ID | `44eea7201d285aa51eca9c7eae5e259995b06a45` |
| 原 RAM 包 SHA256 | `529f1f0aa72509bd89bf0c308b61c31cc4eb8445925243df508d10371d558bd0` |
| 无线屏蔽 RAM 包 SHA256 | `9e21cf7d071dc08735828e1a5f0748411e069405b2f4d15c9c3b165cd7042dc0` |
| package manifest SHA256 | `31e301057e37b15aa50ac52065531202dc06019c8bfba298e4c56d92ceebaba5` |

沿用 [.36 无线屏蔽方式](2026-11-06-vdec-integration36-no-radio-plan.md)：
仅候选 APPEND 增加 module_blacklist、initcall_blacklist 和 bluetooth.service mask。
制作变体时逐文件比较，只允许 extlinux.conf 和 trial.json 中该文件摘要变化，Image、
模块和 DTB 等 2357 个文件不变。identity.json、no-radio.log 保存实际逐项比较；
RAM/manifest 的 VM→Mac 副本已核大小和 SHA。无线关闭只以模块、SDIO/HCI/provider、服务和 deferred-probe 采证，
不把它称为物理断电。正式 cmdline、默认项和 U-Boot 环境不变，不 saveenv。

首窗离线计划已生成到 `build/hwdecode-parity/run85/`，尚未排板票或操作板子。
offline-check.log 实际检查源码/包身份、2372 项清单逐项一致、清单不一致时拒绝、
工具摘要、定向顺序、默认离线入口，并复用真实捕获回放像素失败继续和超时停止路径。
同根 browser-import.log 记录私有 Playwright 1.56.1 导入通过。主仓库全套实际
607 项 OK（11 跳过），原始 main-tests.log 保留。

封包并清理本轮可重建对象后，Data 仅约 7.0 GiB，低于 8 GiB 入场阈值，
因此暂停在离线阶段，未上传、未启动 .37。disk-before-board.log 保留 df 原始输出；
历史证据未删，恢复空间后才按原授权继续。所有实板结果在此刻均未运行。

既有 147 条缓存输入、发布者参考和工具离线校验，不下载新流。132 项、4 条超尺寸
Known unsupported 与 11 条 Main10 的范围沿用原全集；不会将未跑项计作通过。
官方 1.24.2 h265parse 私有前缀，stateful v4l2h265dec 必须来自系统
video4linux2/libgstvideo4linux2.so；stateless 插件仍为私有 v4l2codecs。
入场冻结系统插件摘要、逐段核 gst-inspect 路径/版本/SHA，输入上板后再次核 SHA256。

## 顺序、窗口和预算

每窗一张 sampling 票，目标 20 分钟、上限 30 分钟。入场连续 UART 排空后观测，
boot_id 不变、uptime 单调且至少 300 秒；核 formal proof、以太网、SSH、HID、视频、
板端空间和 Mac Data 可用空间。Data 少于 8 GiB 就在窗间停报，不删历史证据。
本窗起 VBUS 仍经 Mac→用户 USB-C 功率计→VIM4，型号未补；此前插拔断电启动不计
非请求冷复位，不由显示功率推断瞬时供电上限。

每窗总时限 1800 秒，420 秒恢复绝对保留；执行器另留 20 秒退出余量。
入场、上传和启动按 180 秒；stateless compliance 按 90 秒；初始 HEVC 门禁按
180 秒，三轮重复 compliance 各最多 120 秒。单流外层 timeout 沿用锁定全集清单：
通常 30 秒，长流的放宽值仍逐条保存在 full-plan.json。每组的启动门槛为该组各条
timeout+5 秒之和；初始清单拆成最多六条一组，全集沿用原八批，余量不足就结束。
这些是启动整组的预算上界，不因实际解得快而缩短任何单流 timeout。

1. stateless 带流 compliance 60/60、media 8/8、DOS step=0，插件/节点/固件门禁均阻断。
2. 首个候选的全 I compliance 至少 56/56、零失败/警告；原首帧 98304 字节及三平面
   精确匹配、status 0、初始 SOURCE_CHANGE 先于 CAPTURE、只一次 CAPTURE STREAMON。
3. cip_B_NEC_3、MERGE_E_TI_3、TMVP_A_MS_3 按 5/8/17 帧和发布者逐帧 MD5
   验收；任一退步停止系列并报告。门禁通过后，同一输入的 select+epoll compliance
   连跑三次，全部保存；这是非阻断观测，不重复到通过。
4. 跑候选 CSV 的 30 条原失败，每条记录像素、帧数、LAST、status、ERROR 和拒绝日志。
   三条原内核 timeout 放末尾，出现内核 timeout 仍先恢复，下一票从下一条续跑。
5. 跑六条原 Success 代表：DBLK_B_SONY_3、MERGE_E_TI_3、TMVP_A_MS_3、
   ENTP_A_QUALCOMM_1、TILES_A_Cisco_2、SLIST_A_Sony_5；任一退步停止系列报告。
6. 以上门禁和代表全过后才开全集阶段：同包重跑独立 132 项，不以定向结果充全集。
   后续每窗仍记录一次非阻断 HEVC compliance，不重复全 I/短流门禁。

定向与全集是两个明确阶段；同一阶段不重跑已尝试流，失败不会换参考或改参数求过。
每流逐帧/整流 MD5、精确帧数/字节数、进程退出 0、Captured N frames; status 0、
LAST 和零 ERROR 全满足才 Success。像素 Fail、返回的 EOS/接口 Error 记录后继续。
外层超时、内核 timeout/splat/DMA/IOMMU/挂死则结束当前窗恢复，新票续下一条。
保存逐流 kernel/GST/ioctl 和比较摘要；失败 I420 全保留，成功流保存散列后清板端输出。

候选冷复位后恢复正式，用下一张替代票继续，不在同票重启候选；同一批连续三次
冷复位停止并报告。原始 UART、Linux 起点到复位间隔、实际启动身份逐次计数。
恢复失败或保护文件/视频不符立即停止系列，不将其视为普通单流失败。

## 收尾和交付

每窗恢复正式 `7.3.1-vim4-20261105`，源码 fd41fb5、build ID
`bdbfa439f298e92b5bad092528d11119a974f262`，2372 protected_files 逐项等于
当前 baseline.json，视频推进且无新增丢包/掉帧/冻结；无线恢复证据也保留。
清理前检查并重传 /tmp helper，只按 owned-firmware.json 摘要清本任务固件，正式模块
目录不动。上传目录先取回、逐文件核摘要后删除，再释放 sampling。独立 .37 的可重建
对象清理不涉及 .36 或历史原始日志。

最后交付定向 30 项和全集 132 项两张总表、旧 Success 回归集合、compliance 复现率、
冷复位和未运行原因，主仓库全套测试实际输出。提交不 push、不合并、不部署；
调试内核锁/内存检查、5.15 对照、性能、多实例、10bit 仍未由本轮证明。
