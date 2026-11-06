# 2026-11-05：H.264 缺口参考修复实板计划

**待协调者批准，未排票。** 验证 [缺口修复](2026-11-05-vdec-gap-references.md)；
生产配置 RAM 候选只增加 topic 的已验证提交，不混 HEVC 草稿、不修改默认启动项。
封包时记录源码/config/Image/模块/固件 SHA 和 build ID，先离线核对 manifest。

单张 FIFO sampling 票目标15分钟、上限30分钟；只允许一次候选启动。
预算：入场连续UART与uptime稳定观察5分钟，上传/启动3分钟，compliance/码流5分钟，
归档与恢复proof/视频8分钟，余量9分钟。正式包也有连续冷复位风险；任何冷复位直接
进入恢复，不能为完成样本追加候选启动。剩余时间不足恢复预算就停止新增解码。

输入与顺序：stateless 带流 v4l2-compliance（含 media/Request API）→ MR3、MR4、MR5
→ AUD_MW_E、BA1_Sony_D、BA1_FT_C、CAMASL3_Sony_B、CVFI1_Sony_D、
cabac_mot_picaff0_full、cama1_vtc_c。后七条为既有通过的逐行/多slice/场对照。
使用 r61 已核验的官方 h264parse 私有前缀和相同 v4l2codecs，逐项核对实际库路径/SHA；
不覆盖系统库。此轮不重复 Khadas A/B，不测 HEVC，不扩大为全集。

MR3/4/5 keep 完整输出并逐帧与已归档 JM/FFmpeg 参考比较，要求各300帧、所有帧一致、
Fluster MD5 Success，OUTPUT/CAPTURE 不再返回 ERROR。保存全部 ioctl/队列trace、
内核日志；通过动态调试只开启新增两类占位日志，统计列表占位次数与 colocated 选择次数。
后者预期0；列表项数量可以非零，不能据此报告宏块非法引用。若仍Fail，保存首次ERROR、
首错显示/解码索引及DPB，不现场修改驱动。普通像素Fail继续收集，Timeout、内核
BUG/WARN/Oops、挂死、节点不可用或compliance异常立即收尾。

baseline.json 从入场时正式 sources.toml/proof 生成，protected_files 逐项相等。
全程连续主机时戳UART；每个候选/恢复启动分别记 Linux 起点、复位间隔、末条日志。
恢复沿用 r60：候选复位后只读观察正式默认，最多两次自然启动；仍无法SSH则停止并
交协调者处理，不saveenv、不主动reboot循环。SSH恢复先核proof/保护文件，再按owned
manifest核哈希清理本任务固件和候选；正式模块目录不动。

清理前检查 display-once.py helper，缺失则重传仓库版本并校验；必须等候选挂载解除后
再删目录。仅一次正常恢复reboot，复核正式proof和实际推进的视频；若再次冷复位只被动
观察。输出归档Mac并核哈希/完整帧大小后才删板端任务数据。记录实际顺序和未运行项，
任何结果均不自动部署修复，也不宣称5.15 parity。
