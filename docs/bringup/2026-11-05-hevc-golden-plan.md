# 2026-11-05：HEVC 厂商金标准轨迹离线方案

仅离线准备，未访问板子、未排票、未push。目标为同板、同固件包、同hevc-intra的
CPU可见寄存器轨迹及正确首帧；当前没有金标准或已定位分歧。
[补丁、格式和工具](../../packaging/kernel/hevc-golden/README.md)含完整使用说明。

## 资产、源码与模块替换

| 项目 | 离线证据/边界 |
|---|---|
| 厂商入口和release | [r44](2026-11-05-vdec-full-conformance.md#515-一次性启动与中止)当时核对 `5.15.137-vim4kvm-hdrdual6` Image/initrd/DT/1535项清单；相邻主仓库build/hwdecode-parity/vendor-comparison仍有本机归档，不能证明今天板上仍在 |
| 身份 | kernel-manifest内核build ID=`4a9b69d62ba7b3a5adeb41b213f7f3e573006165`，source字段明确未证实，不能把当前common_drivers当部署来源 |
| 启动风险 | r44解码前DRM vblank WARNING、约33.6秒hard LOCKUP/panic；未获得成功运行notes匹配，不可直接复用profile称已稳定 |
| 旧成功路径 | [厂商启动](2026-10-23-vendor-boot-gpu.md)、[H.264活体](2026-10-23-vdec-vendor-live.md)：较早5.15.137-vim4kvm曾一次性往返、已装libgstamlv4l2解600帧；不是hdrdual6/HEVC成功证明 |
| VM构建树 | /home/deepdream/src/linux=workspace固定80a07ad5406d57855c996285ae75a50a1b9147ae，有.config/Module.symvers；generated release=5.15.137-vim4kvm；内部common_drivers=563cff9dab2c8cd44590bf57c8ffaa7e2dae35e1，vdin有他人修改，未动 |
| 本轮参考 | workspace锁common_drivers=31619c527655514b4c89516ef609b6db1dd47db6，Mac只读参考及vendor patch均基于它；与VM树不同，不能用于冒充hdrdual6匹配构建 |
| 本机归档 | VM build/native-hdr6-5.15-stage/boot有hdrdual6 Image/config/System.map/DT；该stage未找到精确symvers/源码证明，没有修改已有树/O= |
| 模块可行性 | 归档config有MODVERSIONS=y、TRACING=y、V4L_DEC=m；源码Makefile：寄存器属于media_clock，电源/input/加载属于decoder_common，HEVC属于amvdec_h265。原则上可只重编模块，当前未证明能安全加载到hdrdual6 |

**vermagic相同不足以允许加载。** 还须同源码/配置/生成头、完整Module.symvers、导入CRC/
依赖、工具链和签名策略；不能force-vermagic/force-modversion。media_clock/decoder_common
可能已被其他消费者持有，不能只卸amvdec_h265，也不冒险卸载共享消费者。
优先找回hdrdual6构建收据，再在自己的副本和独立O=重建三模块，所有构建经heavy队列。
找不回则需用户决定暂停或另批完整可追溯5.15实验候选（独立release，一次性启动，
不重装/覆盖原厂商内核）；本轮未做此扩展。vendor patch仅apply-check，未冒充编译通过。

## 最短用户态与输入

首选已装厂商GStreamer V4L2插件，避免新写amports私有播放器。旧记录证明libgstamlv4l2.so
和H.264 factory存在，**没有记录证明HEVC factory名或今天可用性**。获批库存核对须保存
gst-inspect的插件/factory/设备/caps。amvdec_ports/aml_vcodec_dec_drv.c注册aml-vcodec-dec
（请求video26但实际号须枚举），有vdec_hevc_if；不套用7.3的video3或v4l2h265dec名称。

预期管线为 `filesrc ! h265parse ! FACTORY ! videoconvert ! video/x-raw,format=I420 ! appsink name=capture`，
FACTORY由inspect确认。复用vdec-capture.c保存16帧可见I420并到EOS，进程外限时15秒，
轨迹normalize截到首个DECPIC_DONE；仍须对软件参考验证第一帧，不以硬件事件替代像素。
若厂商HEVC factory不存在，先停，离线准备对应stateful客户端再审，不临窗试amports ioctl。

同一raw文件SHA=`ea0bdf6ae42f3d238dbe1d09cf385846526e46d239f4f71b4313875f6a823041`，
即integration31/r69/r70的hevc-intra.h265，256×256八位全I，16 AU、首AU5999字节。
Vhdr只供compliance，GStreamer用raw。两侧核验实际AU前缀/长度；若parser分包不同，
先记录每个QBUF边界，不把分包差异当硬件寄存器缺口。

## 补丁与可见性

厂商补丁/六个输入文件SHA见vendor-source.json，仅在自己的文件副本制作，原源码只读。
7.3实验提交 `562ec48e8fd719ebdbad92b647e7f0dbb2fc7b9c`，分支experiment/hevc-golden-trace，
基于自动NAL的f065c67，不带手动握手候选。开关默认关闭，记录power/reset/firmware/init/
input/start/IRQ/首帧及DOS 3000..3eff、3f33..3f35访问。
7.3另采原生regmap read/write覆盖直接调用，工具去重；两侧额外采可用irq/clock/power
事件并保存format，不能把CCF请求当内部每笔MMIO。所有CPU stats随冻结trace归档。

trace_clock=global、current_tracer=nop，每CPU缓冲建议16MiB；须在首次HEVC power前启用。
若thermal已持域，只记录decoder租约，不能称物理off冷启动。任何LOST/overrun/entries覆盖
均拒绝完整比较。TEE/BL31内部访问、微码自行写寄存器及CCF/genpd provider原始MMIO
不在模块补丁覆盖内；要追这些，须另有匹配源码与跟踪实现，不能补造“完整”序列。
trace_printk也改变时序，后续需禁跟踪复验。报告首个可见写值/顺序分歧，DMA仅按有证据
的同名region归一化、保留offset；合法框架、自检或内存布局差异不自动等于根因。
r69/r70快照已格式自测，工具拒绝拿它们冒充完整访问轨迹。

## 两个窗口方案：约22–26分钟，待审查和用户批准

前置离线门禁：匹配源码/模块兼容性、用户态路径、完整私有依赖加载方案、候选与输入
SHA/软件参考、trace容量及恢复流程。缺项不申请窗口。下面不是安装/运行授权。

1. **A：厂商金标准，约11–13分钟。** 入场proof/视频约1分钟；在基线核对厂商
   Image/initrd/DT/overlay/完整模块、root UUID及APPEND，不据旧文档断言今天仍在。
   对照r44与曾成功profile的DT/参数/服务，差异先审，不直接照搬有panic的旧命令。
   只新增临时extlinux文件，UART执行 `sysboot mmc 1:1 any ${pxefile_addr_r} /私有配置; reset`；
   mmc/地址按本次U-Boot环境确认，不改DEFAULT、不saveenv、不覆盖版本化文件。
   核对release/notes/模块，连续UART和uptime满300秒；WARN/复位即停。
   在HEVC消费者前启用已匹配的私有跟踪模块，解同一流一次（≤15秒），冻结保存trace/stats/
   IRQ/固件/像素，普通重启回未改的Mainline。
2. **B：7.3实验轨迹，约11–13分钟。** 同样入场proof；t3k同次构建整包、一次性启动，
   满300秒且UART无复位后同输入采一次，首帧或超时均冻结归档，不在板上改寄存器重试。
   回基线后离线normalize/compare，报告首个分歧的双方原始行、相位、地址映射和覆盖缺口。

每窗预留至少3分钟恢复；A不稳定或无正确首帧，先离线分析，不占B做无golden对比。
禁止关闭watchdog、忽略WARN、force加载模块或连续重启碰运气。失联、boot异常、
trace丢失、像素错误或停机失败即停，由协调者按既有board-window流程恢复。

**每次恢复到正式7.3.1-vim4-20261105**，build ID
`bdbfa439f298e92b5bad092528d11119a974f262`，以sources.toml和installed-proof为准，
不回旧`.3`。用board-window return-baseline及runtime descriptor核对Image/DTB/完整
模块/外部模块、默认Mainline和启动哈希；确认服务/UDC/CPU策略、无实验模块/私有挂载，
跑同一baseline video_check，验证画面推进及丢帧/冻结/丢包增量。恢复不确认就交协调者，
不声称通过；只清理已核对哈希的本任务临时配置/上传，不碰用户数据和基线模块目录。

## 离线验证与待决定

7.3实际启用TRACING/FUNCTION_TRACER后，heavy队列W=1模块及arm64 QEMU 25/25通过，
五个既有KUnit MODULE_DESCRIPTION警告。首次直接选择隐藏TRACING依赖失败保留，
改用FUNCTION_TRACER选择后通过。厂商patch仅apply-check，缺匹配来源故未编译/加载。
脚本12项通过，已解析r69/r70 snapshot并验证compare拒绝。原始输出在
build/vdec-hevc/golden及logs/vdec-hevc的golden日志；没有真实板上轨迹。

需协调者审后再报用户决定：找回hdrdual6构建输入后继续模块方案，还是另批完整可追溯
5.15实验候选；满足前提后是否批准两窗。今天板上资产、HEVC factory和模块可替换性
仍须获批库存核对，离线文档不能替代这些事实。
