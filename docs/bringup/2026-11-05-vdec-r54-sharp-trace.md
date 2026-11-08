# 2026-11-05：r54 `.28` 功能与 Sharp 尾部跟踪

`.28` 正常启动，stateless media compliance **8/0**、带流 video compliance
**60/0**（通过/失败）。全集 index 0–60 为 **53 Success / 8 Fail**，另两条 Sharp
均 Fail；合并 **53 Success / 10 Fail / 72 Not run**，无 Error/Timeout。
窗口按预算正常结束；JPEG、HEVC 本窗未运行，生产配置不证明调试锁/内存检查通过。

## Sharp：缺少提交发生在用户态

两条输出均 7,257,600 字节，即 14 个 720×480 I420 帧；预期 15 帧应为
7,776,000 字节。与 r50 导出逐字节相等，因此继续适用既有参考比较：
Field 已输出 0–13 全部正确，缺显示帧 14；PAFF 已输出 0–12 和 14 全部正确，缺最后解码的 B 帧（显示帧 13）。
本次原始输出 MD5：Field `bdbd94b5629b7d79da5155dbea8677f5`；
PAFF `3861dfb8bde8d9be0c53ac21694f2a34`。

| 码流 | 输入 slice | OUTPUT QBUF/DQBUF | CAPTURE QBUF/DQBUF |
|---|---:|---:|---:|
| Sharp_MP_Field_1_B | 30 | 29/28 | 15/14 |
| Sharp_MP_PAFF_1r2 | 23 | 22/21 | 14/13 |

两个隔离 trace 实例分别记录 86、70 个事件；各 CPU 的 overrun、commit overrun、
dropped events 都为零。实例在保存后正常删除，流程继续进入全集，没有跟踪收尾异常。
只有 QBUF/DQBUF 事件实际产生，不能把已启用但无记录的 vb2 事件当作额外完成证据。

Field 日志中，最后底场 3344 字节 slice 已被 h264parse 读到，随后读到 NAL10/11，
`current_off 3358, size 3358` 报 `Need more data`，接着 decoder 收到 EOS；
decoder 只完成到 frame_num=14/poc=28 的顶场，未解析底场并提交第 30 个 OUTPUT。
最后 CAPTURE DQBUF 的 sequence=13、timestamp=26000；timestamp=28000 对应
首场 OUTPUT 带 HOLD，第二场提交不存在。这不是已经提交完整图像后由驱动丢掉尾帧。
PAFF 同样少一个 OUTPUT；最后 B slice 没有送入解码器。

由此可定位用户态 parser 排空限制；不修改内核 PicNum/LTR、colocated、HOLD 或插件。
此跟踪未记录 decoder command ioctl，不能声称单独验证了 FLUSH 命令的执行；
缺失输入提交已足以解释尾部不完整，不能要求驱动用 FLUSH 补造缺失 slice。
若末 slice 是配对第二场，首场 CAPTURE 仍在 HOLD 等待，须由后续 FLUSH 或
STREAMOFF 路径释放；本次“已接收请求未见像素错误”不证明 HOLD+FLUSH 释放已经实测。
板端 parser 身份待 r55 采集；私有 v4l2codecs recipe 的版本不能代替系统 h264parse
身份。宿主原版 parser 的 `draining with no new data` 路径与板端日志不同，之前宿主
保留所有 slice 的结果仅适用于该宿主插件，不排除板端 parser 的问题。

## 身份、证据、恢复

源码、配置、RAM 包同 r52，没有 HEVC 草稿。
完整原始数据位于 `logs/hwdecode-parity-r54/validation-fluster-1793910163620005000/`：
`results/compliance/results.json`、三份 `results.json`、逐码流 JSON/日志、
`vector-0120-v4l2.trace` 和 followup-0 下的 `vector-0123-v4l2.trace`，以及各自 trace-stats。
普通像素 Fail 继续采集；未运行条目单列，不合并旧 `.27` 结果冒充新基线全集。

恢复 `7.3.1-vim4-20261105`，build ID 与 2372 个保护文件全部匹配；
`returned-video.log` 为 3840×2160 H.265，297 帧、59.37 fps，零新增 dropped/freeze/lost。
700 个上传文件逐项归档、复核后删除，见 `build/hwdecode-parity/run54/upload-cleanup.log`。
截至本窗，`.28` 已覆盖 **4 次启动/2 次冷复位**，新正式覆盖下界增为 **9 次/0 次**；
本次候选和恢复均未复位。r55 获准从 index 61 续跑，仍遇 Timeout 或内核错误即收尾。
