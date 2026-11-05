# 2026-11-05：H.264 parser A/B 像素采证计划

协调者已批准并在 [r61](2026-11-05-vdec-r61-parser-ab.md) 执行；额外入场门禁为
连续UART/uptime确认至少5分钟无新冷复位。以下保留原计划，执行偏差见r61。
依据 [visl 离线结果](2026-11-05-vdec-visl-controls.md)，
用同一个已验 `.28` RAM 候选、同一私有 v4l2codecs、同一输入，单变量切换 Khadas 与
官方 Ubuntu 1.24.2 h264parse。不改驱动，不部署，不将 visl 请求成功当像素通过。

## 样本、产物与预算

14 条 parser 受影响流全部各跑两遍；MR3/MR4/MR5 也各跑两遍作为不缺尾请求的对照。
清单采用 visl CSV 的 17 条，先 CAMA1/CAPA1/CAWP5，再其余隔行，最后 MR3/4/5。
每流相邻执行 Khadas/官方两组，保存独立目录；只换 parser，其他库哈希固定。
官方 parser 放任务私有前缀，使用隔离 GST_PLUGIN_PATH/GST_REGISTRY；不覆盖系统库、
不安装 deb、不替换系统插件注册表。开跑前 gst-inspect 核对实际 Filename 和 SHA，
两组都记录 codecparsers/codecs 实际加载路径与哈希。

单张 FIFO sampling 票目标 15 分钟、上限 30 分钟，预算：入场/上传/身份3分钟，
候选启动2分钟，34次解码及数据回收15分钟，恢复/保护文件/视频7分钟，余量3分钟。
单流30秒超时；剩余时间不足恢复预算即不启动下一条。运行前离线计算全部 YUV 大小和
包大小，空间不足则缩小为 CAMA1/CAPA1/CAWP5/MR3/MR4 五条，不临场删除他人数据。
本计划只请求 **1 次候选启动**，任何冷复位直接进入恢复，不追加候选启动/样本。

沿用 vdec-window 的 manifest、watchdog、--execute/--at-board 和 baseline 门禁。
基线由当前 sources.toml 的 tested_build/retained_runtime 与正式 proof 生成，
validation-plan.protected_files 必须逐项相等。候选使用既有 `.28` 封包和哈希核验，
不重建候选以免混入额外变量。HEVC 不参与；stateless 带流 compliance 先验队列可用。

两种 parser 都 keep 原始完整 CAPTURE，记录格式、coded/visible 尺寸、stride、bytesused、
帧数及顺序；保存 QBUF/DQBUF、STREAMOFF/DECODER_CMD 和内核日志。输出归档到 Mac 后
核对哈希及 YUV 大小，再删除板端本任务上传与输出。普通 Fluster MD5 Fail 不停止，
Timeout、BUG/WARN/Oops、挂死、节点不可用或 compliance 异常立即停止并恢复。

## 离线判定

宿主对同一输入用 FFmpeg/JM 参考解码，保存版本、命令、输入哈希与原始输出。
逐帧 MD5 使用相同像素格式和有效尺寸；若存在 padding/crop，先按 CAPTURE 元数据去除，
不能把 coded 填充区与参考 visible 帧直接比较。每个连续原始文件另保留总 SHA。

- Khadas 输出若恰少末帧，比较其全部 N-1 帧与参考前 N-1 帧；不要再丢弃它的最后一帧。
- 场流同时记录缺的是第一场还是第二场、HOLD/STREAMOFF 是否释放未配对缓冲，
  不预设少一个 slice 必然只少一个完整输出帧；逐场对照定位首个像素差异。
- 官方组须帧数完整且每帧一致，才能认定该流的旧 Fail 只有 parser 原因。
- 任一已输出帧不一致，记录首个差异帧/场、slice、POC、DPB/LTR/MMCO；回到驱动离线定位。
- 两组结果都保留；原 Khadas 环境的 Fluster Fail 不改写成套件 Success。

## 冷复位与恢复

正式默认也曾连续复位，不能假定回到 eMMC 即已安全恢复。连续主机时间戳 UART 覆盖
入场至收尾；每个候选/恢复启动单独计数，保存 Linux 起点、复位时间、末条日志。
候选复位后只读观察正式默认，最多观察两次自然启动；不 saveenv、不主动 reboot 循环。
仍无法 SSH 就停止并交协调者决定，不能用重启刷样本。

SSH 恢复后先核正式 proof 和全部保护文件，再按 owned manifest 的哈希清理任务副本；
正式模块目录不动。执行清理前检查 `/tmp/board-window-<id>/display-once.py`，
若被 systemd-tmpfiles 清掉，重新上传仓库 helper 并核验，沿用 r60 经验。
清理完成后仅一次正常 reboot，重新核 proof、保护文件和视频实际推进；若再次冷复位，
只被动观察并记录，不再主动重启。失败保留完整 UART，恢复优先于解码样本数。
