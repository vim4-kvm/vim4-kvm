# 2026-11-06：.39 解码分层重构行为对照计划

已获协调者批准。目标是验证重构与 .38 的行为等价，不部署、不推进主线。
部署任务仍暂停；本轮不向工作机发送 HID，不切 EDID、画面或编码设置。

## 身份与离线门禁

- 源码 `0ae8beaa56d3a798e8078c5f727c34ed3acafd9c`，tree
  `50d9610fcec8630bf46064a8c8995a1a5b26c929`；基准为 .38
  `d177f0dc1ca40a33dadee38f95c08fa332236f69`。不引入后续修复。
- 生产 release `7.3.1-vim4-20261106.39`，独立源码
  `/home/deepdream/src/linux-7.3-vdec-integration39`，独立
  `O=/home/deepdream/build/vdec-integration39/kernel`；KUnit 使用同根独立 kunit 目录。
- 生产配置 SHA256
  `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`。
  实际执行 `make … W=1 Image dtbs modules`，另跑 arm64 QEMU KUnit。
  逐提交门禁引用已审系列记录，不声称本轮重跑。
- 最终 manifest、RAM 描述及 validation-plan 声明
  `hevc_diagnostic_api=debugfs-v1`。诊断路径只使用
  `/sys/kernel/debug/aml-vdec/<device>/{hevc_test,hevc_core_test}`，缺失即拒绝。
  显式调用当前 `hevc_cycle(plan)`，不用旧 sysfs 缓存或自动回退。
- 无线屏蔽 RAM 变体只增加 brcmfmac/hci_uart/btbcm module blacklist、
  `mmc_pwrseq_simple_driver_init` initcall blacklist 和 bluetooth.service mask。
  逐文件比较只允许 extlinux.conf/trial.json 变化，不改正式默认或 saveenv。
- 封包后核源码、配置、build ID、完整模块、输入、工具及插件 SHA；
  上传清单与计划引用的每个文件逐项核对，缺文件在宿主拒绝。
  protected_files 必须与当前 baseline.json 的 2372 项逐项相等。

## .38 补基准

原 .38 r92–r95 仅跑 HEVC，不能借 r73/r75 冒称已有其他格式的 .38 实测。
已批准使用原 .38 无线屏蔽包，不重编，补 H.264 三流、MPEG-2 四流、JPEG 三样本，
JPEG 编号和带流 compliance。旧包使用从 r92 归档校验提取的旧诊断适配器，
不与 .39 的 debugfs 工具混用。结果另记为
[补测于 .38 同一包](2026-11-06-vdec-integration39-baseline.md)。

## 比较规则

HEVC 基准为 [.38 独立全集](2026-11-06-hevc-integration38-results.md)，
逐流 CSV SHA256 为
`2628f40a606969525aea2d8cd16c87903198914574a4bfa8839ce91ea43966d2`。
冻结原实际 comparison.json，12 条失败的 I420 与归档清单逐项校验。

- 120 条 Success：逐帧 MD5、顺序、帧数、布局、字节数、status 0、LAST、
  ERROR 缓冲和事件/队列结构均与 .38 相同。
- 10 条 Error：实际输出前缀的逐帧 MD5/字节、帧数、首错或首缺位置和失败类别相同。
  旧失败转成功同样是行为差异。
- 2 条 Timeout：原输出均为空，只允许相同内核解码超时类别和空输出。
  超时立即结束该窗恢复；归档后确认等价，才可在下一票续未运行项。
- 其余格式与补采的 .38 硬件输出逐字节及逐帧摘要比较；MPEG-2 对实际 `.out`，
  不用 `_ref.yuv` 代替硬件输出。JPEG 同时核既有 IDCT 误差边界。
- 节点编号、HEVC 56/56、stateless 60/60、media 8/8、JPEG 60/60、
  DOS step=0、全 I 98304 字节、SOURCE_CHANGE/CAPTURE/EOS/LAST 顺序均对照 .38。
- 唯一预先允许的语义变化是 stateless 的 G_SELECTION/G_CROP/CROPCAP
  从 EINVAL 改 ENOTTY；若计数改变，逐子项说明，其他差异不能借此豁免。
  原始 trace 行号、PID、地址和耗时不要求逐字符一致。

r98后协调者追加[合法drain尾部裁决](2026-11-06-vdec-integration39-r98-drain.md)：
数据LAST/空LAST只按原始STOP顺序及平面payload证明后归一化；r100补充允许两条路径
仅少DQ最后一个OUTPUT，须证明其QBUF早于STOP、客户端收到LAST后才停止。
其他计数仍严格。旧失败不改口径。已过项不重跑，续未跑项。
R102补充：旧Error首个错误交付之后，有原始顺序证明的客户端收尾控制次数不作比较；
首错前和数据、CAPTURE、失败类别/status、LAST/ERROR及内核错误签名仍严格。

首次 .39 窗：入场 → 节点/debugfs/固件/DOS/compliance → HEVC 全 I 和三条短流
（cip_B_NEC_3、MERGE_E_TI_3、TMVP_A_MS_3，5/8/17 帧）→ 一轮 select/epoll
compliance → 其他格式短回归 → 有完整预算才开始 HEVC 全集。
续窗仍核接口、固件、节点及 DOS；不把先前短回归重复计入 132 条。

全集沿用 .38 八个逻辑批：18/18/17/16/18/17/11/17 条，
逐批 slot 总计 630/630/625/620/630/595/445/595 秒。
每流原 30 秒，原长流 60 秒；开始批前保留整批 slot 加恢复预算。
时间足够可以连续多批，不截流、不重跑求通过。保存逐流 GST/ioctl/kernel.log、
摘要和失败 I420；成功 I420 比对完成后可删除，摘要保留。

## 板窗与停止

每窗一张 FIFO sampling 票，目标 20 分钟、上限 30 分钟；每窗最多一次候选启动。
420 秒恢复绝对保留，另留退出余量。入场 uptime≥300 秒、boot_id 不变且 uptime 单调；
先排空 UART 并记录字节数/SHA，再连续主机时间戳采证。每窗前 Data 可用空间≥8GiB。

任何未约定的行为差异立即停止整个系列，包括旧失败改善；不现场改驱动或参数。
超时、挂死、splat、DMA/IOMMU 异常先恢复，保留第一次证据。
生产配置的运行记录不等同于 KASAN/kmemleak 完整验证。

冷复位累计覆盖本任务的候选和恢复启动：第 1 次若在 420 秒内自然恢复正式且
2372 proof/视频通过，可继续下一窗；**累计第 2 次立即停下报告**。
SSH/串口均不可达或恢复超时即停，不主动循环 reboot，不做物理恢复。

每窗恢复正式 `7.3.1-vim4-20261105` / fd41fb5 / build ID
`bdbfa439f298e92b5bad092528d11119a974f262`；核 2372 proof、无线恢复和被动视频。
画面静止不能判定时如实记“画面静止、未判定”，不得为测试操作工作机。
清理 helper 先检查并重传；只按已核 SHA 删除本任务固件副本、RAM 暂存与上传目录。
上传先归档核摘要后清板。密码只走 stdin。结果提交不 push、不合并。
