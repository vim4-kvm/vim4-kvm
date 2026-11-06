# 2026-11-06：MR3 存储归属修复实板计划

**待批准，未排票、未启动新候选。** 目标是验证
`d444ab83f7fab8044eea48902b17310763bb7a04` 的存储归属判断，并用新dynamic debug日志
确认r63缺失的失败路径证据。不能把上一轮板窗授权扩展成新启动额度。

候选从该已提交HEAD构建完整生产配置RAM包，配置与正式kernel.config一致，无HEVC
私有草稿。使用构建当天UTC日期的新release，记录Image/config/模块/固件/包SHA和build ID；
不在`.29`上单独混入新模块。封包及离线manifest/protected_files检查完成后才申请板票。

请求一张FIFO sampling票，目标15分钟、上限30分钟，**只启动一次候选**。
预算沿用r63：连续入场观察5分钟，上传/启动3分钟，compliance/解码5分钟，归档/恢复
proof/视频8分钟，余量9分钟。候选或恢复发生冷复位直接进入恢复流程，不追加启动。

顺序与样本保持r63相同：stateless带流compliance及media检查 → MR3/MR4/MR5 →
AUD_MW_E、BA1_Sony_D、BA1_FT_C、CAMASL3_Sony_B、CVFI1_Sony_D、
cabac_mot_picaff0_full、cama1_vtc_c。不增加HEVC、JPEG或全集。
使用相同官方h264parse私有前缀及v4l2codecs，记录实际Filename/SHA；三条MR全部keep，
其余用Fluster原始JSON判定。MR3须300帧逐字节等于JM/FFmpeg且两队列ERROR为0；
MR4/5与7条对照不得回退。

在模块加载后显式开启 `format "decode spec" +p` 与 `format "gap placeholder" +p`，
保存control实际启用行；仅这两类日志，不打开全驱动调试。逐流保存ioctl、队列trace、
内核日志和输出，分别统计：

- buffer命中但canvas不存在的回退（重点MR3 decode9/10及ts0），以及无buffer回退；
- gaps=0或其他不能归为已知占位的存储损失，不能忽略为“正常缺口”；
- 当前图分配、参考槽、最终buffer查找各失败出口的返回码与timestamp；
- 占位列表数量和占位colocated选择次数，后者预期0，不将列表计数当宏块引用数。

合法缺口日志不作为窗口级异常；普通像素Fail收集后继续。Timeout、内核BUG/WARN/Oops、
挂死、设备不可用、compliance异常立即收尾，离线分析，不现场改驱动。

入场前在宿主离线运行私有 `build/hwdecode-parity/browser/smoke.mjs`，显式设置
PLAYWRIGHT_MODULE及PLAYWRIGHT_BROWSERS_PATH；receiver保持r61/r63的Chrome通道，
核实际版本，不全局安装、不临场修依赖。入场重新观察连续5分钟无复位、uptime/boot_id
一致，核当前正式baseline proof、完整保护文件清单及视频；任何门禁失败不启动候选。

恢复、清理沿用r63：连续主机时间戳UART，正常恢复正式默认后核proof，检查/重传cleanup
helper，待候选挂载解除再清理；owned固件按SHA删除，正式模块不动。输出归档Mac并核
哈希和300×176×144×1.5大小后删任务目录，再验视频推进；只一次正常恢复reboot。
若冷复位，最多观察两次自然恢复启动，仍不能SSH则停止交协调者，不主动reboot循环、
不saveenv、不改默认启动项。记录每次启动及未运行项，不自动部署。
