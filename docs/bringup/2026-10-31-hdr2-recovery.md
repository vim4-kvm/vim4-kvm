# 2026-10-31：HDR2双向恢复分解与uhd4r3复验

承接[r17](2026-10-31-hdr2-mcp-ice-pq.md)。用户已于2026-10-30确认VDIN HDR2主路径；
HLG保持“已实现、无真实源未验”。本轮只修恢复链路，不改HDR矩阵、LUT或One-KVM产品判断。

## 定位与修复

One-KVM `src/video/pipeline/shared/vim4.rs:444–483`每100ms观察信号、拉取样本；
`src/platform/vim4.rs:506–528`要求变化连续两次一致。
Wave5后端的`native_hdr(config)`始终为false（`shared/vim4.rs:120–125`），
因此本次不能归因于native HDR判断与source_changes各触发一次。
未见`vim4.rs:285–328`的错误重试1秒退避；应用判定保持不变。

GStreamer 1.24.2 `sys/v4l2/gstv4l2src.c:1133–1145,1164–1191`收到source-change时停止并重协商。
短generation不一定代表完整One-KVM管线重建：没有对应第二条应用capture-start日志。
VDIN的source monitor在STREAMON完成资格检查后仍可能保留失锁缓存，再把恢复上报成第二次变化。
内核`21e3174a3323f`在video_lock下同步已准入源的基线；宿主执行真实C函数，覆盖
失锁→新lease准入→monitor不重复通知，以及后续真实变化仍通知。没有吞掉未准入事件。

仅修重复事件仍约1.78秒。所有六次切换均有真实`5v-or-align`失锁，不能绕过PHY恢复。
`t7-hdmirx.c:t7_hdmirx_link_work`原来以250ms采样三个匹配clock，且DMA owner存在时禁止PHY编程。
`c171faa2aa2bb`只在有线缆、无owner、非撕裂快照重试的恢复阶段用50ms采样；
保留三次匹配、PLL/PCS及视频资格检查，正常/无源/撕裂快照仍250ms。
厂商T7默认`sig_stable_max=10`（`hdmi_rx_wrapper.c:471–483`），
`TIMER_STATE_CHECK=HZ/100`（同目录`hdmi_rx_wrapper.h:30`），默认视频稳定窗口100ms。
新clock资格窗口150ms；两者检查算法不同，不能称完全等价，也未读回厂商运行时覆盖值。

`8bca939d6bbd3`在最后一个旧DMA lease真正释放后立即唤醒恢复，重新从零完成三次clock资格检查，
消除额外0–250ms调度相位。保持streamoff、帧边界等待、旧buffer退休和全部PHY检查。
停止标志与重排工作在同一link锁内串行，晚到close不能在取消后重新排队；宿主覆盖该生命周期。
这三个补丁各有回归、独立提交，strict checkpatch均0 error/warning/check。

## 分段证据与测量边界

专用ftrace实例只跟踪VDIN START/STOP、RX lease准入、query_timings及原有buffer事件，未ptrace。
r1一次切换：source-change 187.491065，stop进入187.491106，stop完成188.177968，
下次start189.237474，新generation189.258708：停止0.687秒、再等1.060秒、lease资格约21ms。
r2对应一例：181.851293→181.851395→182.337614→182.895222→182.916488：
停止0.486秒、再等0.558秒、lease约21ms。旧owner退休耗时没有被省略。

源端重协商、内核资格、事件/管线停止、buffer退休、重新准入、首个编码完成及浏览器解码是不同端点。
本轮5.15没有同样的内核内部trace，不能精确分配每个阶段的跨内核差值；
浏览器统计的最后推进至下一次推进间隔包含源端失锁、编码/网络/解码，并非纯HDMI或纯重建耗时。
接收器记录keyFramesDecoded、lastPacketReceivedTimestamp、totalDecodeTime，
不把keyframe计数当精确首个IDR到达时间。

## 候选、构建与窗口

最终候选`vim4-hdr2-recovery@8bca939d6bbd3`，基于正式f71b5c6289cb及六主题HDR2系列ce6bc0cc5218a。
release为`7.3.0-vim4kvm-uhd4r3+`，build ID `725c2b4b39b6b075da97e7481efe03d4e5600f65`。
完整Image/DTB/2338模块包SHA256：`b9e8a286d6b57d1f51e76fe8d8945508a4040c04d00949d376e860179147a35d`。
私有GStreamer与One-KVM程序沿用r17已验的ffee02fb…、926535c6…，应用源码未改。
三版分别完整构建Image/dtbs/modules，运行所有驱动宿主测试、W=1及实际sparse CHECK；本轮未重跑dtbs_check。
所有编译先于采样，在持有板锁与heavy锁后进行，未动kbase工作树。

每个测量窗口都先确认M6空闲，结束回5.15、HDR关闭并恢复原Chrome页/微信输入法；
只开自有固定图标签和显示器设置，不测声音、不读无关寄存器、不发非MCP输入。
接收器只申请video，无音频或data channel，LAN candidate选择沿用r17显式诊断参数。
第一次r1启动因缺空模块挂载目录被PID1 guard拒绝，自动回5.15；补齐目录后重试，保留失败证据。

250ms粗采样：5.15 PQ→SDR约1.26–1.27秒；r1仍1.78秒，r2为1.27–1.53秒，
r3为1.299/1.525/1.271秒，SDR→PQ为1.271/1.267/1.269秒。
粗采样不能决定严格速度门禁。一次50ms尝试在服务尚未就绪时offer失败，完全作废；
接收器新增采样间隔参数，最后短窗口先确认已解码3840宽视频，再切换HDR。

## 最终配对与门禁

50ms统计的帧推进间隔如下，单位秒；每个方向三次、同一浏览器及LAN参数，均H.264/4K60。
先检查实际framesDecoded推进，再切HDR。样本并非点击至首帧，而是切换造成的解码推进中断。

| 方向 | 5.15 | uhd4r3 | 中位数差 |
|---|---|---|---|
| PQ→SDR | 1.173 / 1.225 / 1.284 | 1.224 / 1.236 / 1.809 | +0.011 |
| SDR→PQ | 1.229 / 1.173 / 1.867 | 1.240 / 1.259 / 1.162 | +0.011 |

中位数差小于一个采样周期；两栈都出现约1.8秒长尾，但出现在不同方向。
不能据此宣布7.3的PQ→SDR尾部“不差于5.15”：本轮该方向均值仍1.423对1.227秒，
最大1.809对1.284秒。**速度门禁未全过，只推特性分支，不合main或正式内核，不改正式锁。**

第三次PQ→SDR的额外延迟已落到内核/重协商阶段，而非接收解码：
stop 213.042568→完成213.647376（0.605秒），下一次start214.607996（再等0.961秒），
lease完成214.629124；随后出现不足一帧的短代，stop214.629440→214.647334，
再次start214.695264→214.716633。相比前两次约0.458秒的停止后等待，这里多约0.5秒。
六次物理失锁均为`5v-or-align`，无第二次应用capture-start；
该短代仍可能属于GStreamer内部重协商，不能只凭generation数量认定应用重复重建。
下一步需要跟踪ready/clock资格、最后lease释放、GStreamer negotiate/allocation原因，
区分撕裂快照250ms重试、信号重新稳定和内部重新分配；本轮没有证据允许删减检查或退休等待。

最终配对前的一次5.15细采样在03:32:31 PDT遭外部UU连接：实际codec从H.264改H.265，
close_all_sessions关闭本次接收会话；其后样本全部无效。保留该日志，不归咎网络或候选。
UU退出后重建接收器，最终5.15有效样本在03:41–03:43，7.3在03:45–03:47。
7.3下一次外部UU接入为03:51:10，晚于有效采样；不能把后续停流算入切换时长。
一次补测准备的窗口操作过快，截图尚为原Chrome页，已中止该轮；最终改成逐屏核对显示器设置，
未将未发生HDR切换的标记当样本。

| 其它门禁，同一uhd4r3完整包 | 结果 |
|---|---|
| 干净启动/CMA | taint=0，无WARNING/BUG/Oops/CMA失败；独立编码及冒烟后CmaFree 503120KiB |
| PQ色准 | 同源固定图三对完整帧Y/U/V p99全部0；max 146/23/18，局部内容噪声边界沿用r17，不把max当转换误差 |
| 输出/码流 | NV12 709/709/709/limited；实际HEVC SPS VUI 1/1/1/0 |
| 持续Wave5 | DMA-buf，3600/3600帧，59.998031fps；最大采集间隔16.693376ms，pad→AU p50/p99 12.583/26.220ms |
| 产品DMA | PQ/SDR双向direct_dma=1、stream_copy_bytes=0，无严格DMA类型报错 |
| 退休 | 前一完整回归10代/10743 ticket/10733提交；最终细采样9代/12240 ticket/12231提交，两次均6个source change、未退休0、过时代提交0、trace丢失0 |
| ADLA/Panfrost | 三模型各3次的15个输出SHA与5.15一致；Mali-G52 MC4正确像素/gl_error=0，无GPU fault/timeout增量 |
| MCP | 两内核实际截图、切HDR均成功；服务重启未就绪的502不算MCP故障修复失败 |

原始证据留在本地仓库`logs/hdr2-r18/`、`logs/hdr2-r18-r2/`、`logs/hdr2-r18-r3/`、
`logs/hdr2-r18-final/`；没有把用户屏幕、表单或原始图像推送远端。
主仓unittest 325项通过、13项环境相关跳过。首次文档体积检查失败，
把接收器生命周期教训放到应用子系统入口后全量重跑通过，没有放宽体积限制。

5.15最终交还时三项服务active、UDC configured、16项保护文件SHA256全部一致；默认启动不变。
03:53截图发现用户正在M6使用新页面，停止测试输入，没有触碰其表单。
等页面再次保持不变后，仅恢复HDR关闭（03:59:31截图）、关闭设置并恢复微信输入法（04:00:54截图）。
用户已自行切回原站点，保留其当前页面/滚动位置，没有关闭用户标签。
最后一段测量约03:30–03:48；回退到5.15后因用户操作而等待，安全恢复收尾至04:00:54，
整体收尾超过原30分钟预算，未借延时继续测试。

本会话板上三个`/var/tmp/hdr2-r18*`目录已归档并完整读取85个成员、核对关键文件后删除；
归档SHA256 `736f44efe702467eece5be1bfa4f6cc46d9817451657014f543544e161ff7102`，146445070字节。
未动其它会话目录或USB持久数据。锁在任务收尾释放，不留持锁进程。
内核推`vim4-hdr2-recovery`、主仓推`hdr2-uhd4-integration`与`gpu-hdr-prototype`特性分支；
One-KVM保持db848a52，不推正式vim4。main、正式内核和sources.toml不变。
将来全部速度门禁通过后，仍需新正式锁及kbase基于新release重新rebase/回归，不能把uhd3构建混入。
