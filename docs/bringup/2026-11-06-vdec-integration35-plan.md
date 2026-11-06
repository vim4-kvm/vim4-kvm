# 2026-11-06：.35 MPEG-2整理系列与HEVC EOS验收计划

本轮只离线准备，**不排板票、不部署**；候选封包及计划完成后交协调者批准。
申请一张FIFO sampling票，目标15分钟、上限30分钟，只启动一次.35，不现场重试。
正式默认仍为7.3.1-vim4-20261105（fd41fb5），恢复保留7分钟，核2372项保护文件和视频。

## 集成来源与验证

独立工作树`/home/deepdream/src/linux-7.3-vdec-integration35`从
`5dd4f646bcd8af7b9749bf1396c2a9a2ebf04e5f`开始，依次no-ff合入：

1. quiet-power `efe8d3689a77ec36a3d02556bb6601cb9a22acef`，与.34相同。
2. HEVC vendor-port `d593d7a47916ce2c705aef821fbf2fe0a42353ea`，在.34的2a622cf6上只补HEVC OUTPUT的DYN_RESOLUTION能力声明。
3. MPEG-2 mainline `091d19b940f7f0a3ee5a2844c96c75c5f0935943`，基于5dd4f646的6cf9a04e/091d19b9两提交整理版，替代743d43ff；解码行为相同，诊断删减。

最终源码`67f95220173d8efc84866f4dc1d2c5c344ecbb1e`，tree
`05e9f81233599512bdab97a5c91cf19b5dff6c95`。三次合并无冲突，无未提交内核草稿。
相对.34仅aml_vdec.c/mpeg12.c变化，完整diff和合并日志保存在integration35/。
新工作树没有提交身份配置，首次merge在修改树之前被Git拒绝；随后命令环境沿用
.34已有localhost-copilot身份完成合并，未改Git配置或他人工作树。

生产O=复用`/home/deepdream/build/vdec-sequence/kernel`，独立QEMU复用
`/home/deepdream/build/hwdecode-parity-kunit`，不动共享visl。生产采用正式kernel.config，
含CONFIG_DYNAMIC_DEBUG，不加调试配置；生产W=1 Image/DTB/modules构建同时作为
分支尖模块门禁，不继承topic尖端结果。
未改binding/DTS，本轮不重复逐提交sparse/内建/strict；MPEG-2系列门禁由其整理记录负责。

本集成尖端实际arm64 QEMU KUnit **29/29通过、无跳过**，tip.kunit.json/log与
tip.qemu.log保存原始结果。主仓库全套实际607项OK（11项跳过），main-tests.log保留。
生产W=1全树日志含1168条其他目录warning，解码目录零warning/error；仅规范化工作树
路径后与.34初始完整构建比较，无新增独特warning文本，不能写成全树零警告。
warning计数/差集见warnings.json；配置构建前后cmp均与正式kernel.config一致。

## 最终产物与离线封包门禁

生产W=1 Image/DTB/modules、外部模块、统一整包和RAM封包全部完成，build35.log保存
原始输出。构建使用heavy票1461，无板票/sampling；最初误传60分钟被工具拒绝、未开
构建，随后按默认30分钟预算申请，拒绝日志也保留。未修改正式sources.toml。

| 产物 | 身份 |
|---|---|
| release | `7.3.1-vim4-20261106.35` |
| GNU build ID | `3ff51e33b43ff171e1b9e9712e913963f480a620` |
| RAM candidate.tar SHA256 | `d94265c143d4311f04eda033706c7a9f1e85778032fc368dba0d8c2e7cde12bc` |
| package manifest SHA256 | `e9644fce76a5a83bfc19386d1d468bdc08c21aedce568e43eba9d58105f31a35` |
| config SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA256 | `6cb93a0988bea94824d165c03297de73486569ec6a9ac0cfe2adfb400fdf468d` |
| 生产未压缩aml-vdec-drv.ko SHA256 | `85ff3d0791a32070691fd2c365132a32182a0e475ad9248019eaa1536ef9a440` |

VM包在`/home/deepdream/build/vdec-sequence/bundle35/`，Mac副本及本轮全部脚本/日志在
`build/hwdecode-parity/integration35/`。copy35.py实际逐文件校验VM/Mac副本；
artifact-identity.json锁来源和哈希，sources35.toml只用于本候选。
finalize.py实际校验包内容、源码锁、build ID、baseline及2372项protected_files逐项相等；
16项工具/插件和全部码流归档重新核哈希。计划暂用r73，运行路径不引用旧run目录，
video.py已存在并核验。baseline身份沿用r72恢复的正式fd41fb5，入场仍须实测。
默认离线window.py已通过，未带--execute、未接板；remote.py仍要求--execute/--at-board。
原始输出在offline-validation.log、window-offline.log、copy-artifacts.log。

四条MPEG-2的r72大小/SHA写入validation-plan.json，原YUV仍留宿主，归档后做实际
逐字节比较。HEVC期望哈希沿用r72已证实的同一参考，不改vdec-capture判成功逻辑。
offline-eos-evidence.log用r72原始ioctl确认旧失败特征：DQEVENT第186行晚于首次
CAPTURE分配第166行，STREAMON第183/242行共两次，缺DYN_RESOLUTION且status1；
只是负例证据检查，不伪造通过trace，不代替.35实测。窗口草稿已去掉旧MPEG-2诊断
字符串门禁，保持ERROR/Timeout停止和逐流日志，普通像素Fail仍继续收集。

## 窗口顺序与判据

入场 → stateless compliance/DOS=0 → H.264三流 → MPEG-2四流 → HEVC同一全I短流 → 恢复。
入场上传/启动180秒、compliance90秒、H.264 60秒、MPEG-2 180秒、HEVC180秒；
恢复/视频/归档420秒绝对保留，另有690秒余量，总计1800秒。HEVC仅剩余≥3+7分钟才开始。
单流Fluster与首帧捕获各30秒，沿用vdec-window watchdog和增量journal门禁。

入场uptime≥300秒且连续UART无复位、前后boot_id相同；正式proof、视频、空间和
私有浏览器依赖冒烟通过。候选SSH release/build ID/cmdline/新boot_id逐项核验。
板上不下载码流、不换系统插件，固件仅按归属暂存release专用副本。

- stateless media与带流compliance均须零失败/零警告；关闭动态调试时DOS step严格为0，否则停窗。
- H.264使用同一官方parser，MR3_TANDBERG_B、BA1_FT_C、cabac_mot_picaff0_full均须Success；三条保留ioctl，MR3保留像素/队列trace。不替代全集历史结论。
- MPEG-2按sony-ct1/ct2/ct3、mcp10ccett顺序；私有修正插件的路径、ldd和SHA门禁不符就整段未运行。所有输出保留、两队列零ERROR，要求与r72各自输出逐字节相同。板端先核预锁大小/SHA，归档后宿主实际逐字节比较；sony-ct1/ct2预期套件仍Fail，不能把与r72相同写成标准像素通过。整理版已删诊断，不再要求旧诊断字符串，逐流kernel.log和ioctl照旧留证。
- HEVC开启hevc.c动态调试，仍为相同5999字节首AU/全I输入。secure加载tag265S/core2/swap=1/a0=0、非零overlay及08/RPM→SOURCE_CHANGE→05→0a留证；不改固件/输入现场重试。compliance须至少56/56且零失败/零警告，通过才抓首帧。
- 首帧须98304字节、256×256 I420，整帧及三平面与既有参考逐字节一致；同时进程退出0且明确打印`Captured 1 frames; status 0`。只有文件正确、status1仍是失败。
- 保存HEVC ENUM_FMT和完整ioctl/GStreamer日志：必须见COMPRESSED|DYN_RESOLUTION，首次SOURCE_CHANGE在CAPTURE分配/启动前被消费，只有一次CAPTURE STREAMON，不因初始事件再建CAPTURE。DQEVENT指针本身不说明事件类型，须结合GStreamer SOURCE_CHANGE日志，不能仅以首帧哈希判EOS修复。

HEVC判据依据[EOS定位](2026-11-06-hevc-r72-eos.md)；本轮不覆盖途中DRC、早STOP的
全部规范边界、P/B/10bit、标准全集或5.15对照，不将单流通过推广为完整HEVC支持。

普通Fluster像素Fail留证继续；Timeout、ERROR缓冲/结果、WARN/Oops/BUG、AXI故障、
挂死、设备不可用、采证失败或恢复预算不足立即收尾。HEVC失败只记该段失败并恢复，
不抹去前面结果；不追加启动、不扩输入。MPEG-2偏离r72也按回归停窗。

## 恢复与证据

请求恢复正式fd41fb5，若冷复位则被动观察最多两次自然启动，不主动reboot循环；
持续失败停止并交协调者。UART完整留存，各次Linux起点/ROM分开计数，残缺ROM不跨
下一次Linux起点归属。正式包既有冷复位风险计入420秒恢复预算，不归因本候选。

清理前检查并重传display-once.py helper，按owned-firmware哈希只删本任务副本，
正式模块不动；核baseline build ID、2372项保护文件和视频推进。归档核哈希后删板端
本轮目录，释放sampling票。构建O=对象在封包且窗口结束后清理，日志/包/共享visl保留。
板窗获批后再执行，当前不以离线baseline相等声称板端此刻身份已验证。
