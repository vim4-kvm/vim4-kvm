# 2026-10-30：npu2 上板，双模型通过、YOLO输出与视频门禁失败

**整体未通过。** ADLA初始化和HDMI首次加载参数修复有效；VGG16/DenseNet通过
完整输出与5%均值门槛。YOLO第三输出错误；Wave5的NPU关闭对照已失败，不能报告并行追平。
默认5.15及启动文件保持，最终服务/UDC正常。没有在板上修改驱动。

## 窗口与身份

GPU窗口结束后检查默认`5.15.137-vim4kvm-hdrdual6`、四服务active、UDC configured，
取得本地board/heavy/日志锁及远端媒体锁；没有抢占编码器、删除编码器互斥文件。
串口`/dev/cu.usbserial-1100`，921600。候选仅由U-Boot RAM sysboot选择，不刷U-Boot。
窗口约08:30–08:43 PDT，少于30分钟；子项均有timeout且小于10分钟。
不发任何键鼠/HID，不测声音，不ptrace视频进程，不写PWM、不猜电压；测量无并行编译。

| 项目 | 身份 |
|---|---|
| 原/最终5.15 build ID | `4a9b69d62ba7b3a5adeb41b213f7f3e573006165` |
| 候选release | `7.3.0-vim4kvm-npu2+` |
| 候选build ID | `d59175ac6cd704edf7a5b79f7b2d6c810026505f` |
| 内核提交 | `vim4-npu-adla@8f8fa2c449ecf` |
| bundle SHA256 | `d80b802ecdf6f7c811dc093d40d5de20b5465d2a6d2cf9862adc7adaddca0bf0` |
| probe SHA256 | `509eee645a022f923c58aa614b14b98009a714edd85df55ca89dd1b08a839aed` |

SDK、模型、输入与[5.15基线](2026-10-30-npu-adla-acceptance.md)哈希一致，未重跑5.15。
现场启动器尚无npu2；备份后临时安装五个匹配助手，确认vim4-kvm-run含npu2，
再取当前release/build ID/cmdline/root_partuuid及文件哈希证明，prepare并stage。
最终按窗口前备份恢复助手（包括启动器），不保留半安装状态。

## 三模型

每模型101轮，去首轮统计100个样本；端点为input_set＋output_get，落盘在计时区间外。
本次复用旧窗口基线，不能声称同时段交替配对。每轮所有输出保存，505份文件已下载并复核SHA。

| 模型 | 5.15均值ms | npu2均值ms | npu2 P50/P99/max ms | 均值退化 | 字节门槛 |
|---|---:|---:|---|---:|---|
| VGG16 | 0.560168 | 0.562563 | 0.556883 / 0.703886 / 0.750053 | +0.428% | 101/101相同，通过 |
| DenseNet CTC | 1.951742 | 1.924883 | 1.919154 / 2.054739 / 2.151366 | -1.376% | 101/101相同，通过 |
| YOLOv8n | 30.133937 | 30.751435 | 30.197619 / 32.484237 / 39.559427 | +2.049% | 101份第三张量不同，失败 |

YOLO前两个张量共202份与基线字节相同。第三张量每轮稳定输出常量-17.00094223，
57600个float32中56664个不同，max abs=29.17729187、mean abs=9.50198487、
RMSE=12.44140157。基线该张量范围[-39.51570129,12.17634964]。
候选均值即使低于5%退化门槛，也不能抵消输出失败。
同一窗口dmesg有101次`adlak_invoke_add_queue(): adlak task create fail!`。
初判为任务创建/切分或提交边界兼容性问题，导致部分输出未被正确执行；
尚未证明是缓存或DMA映射原因，需离线审查adlak_invoke_create的失败分支。
SDK仍给出有限输出并返回成功，不能以退出码0代替输出完整性验收；没有重跑挑选样本。

## 接口、PM与恢复

| 项目 | 实测与边界 |
|---|---|
| probe | /dev/adla0出现，KMD 1.4.0.3，四服务active；无上一轮IRQ错误 |
| HDMI参数 | phy_test/core_test/uhd60/dynamic_modes/hdr_probe/hdr_capture均Y，上一轮参数不匹配消除 |
| ATTACH buf_type=0 | 先建MMU上下文，分配页再物理导入，4096字节别名验证、detach/free，退出0 |
| 负向PROFILE_CFG | 两次无network错误路径测试退出0，无死锁 |
| 正向SDK profiling | VGG16三轮，383 µs、3298400 bytes，destroy rc/status=0 |
| runtime PM | 核心时钟0→799999987 Hz→0；active→suspended；最终clock gating and suspended |
| 受控wait超时 | 独立探针LD_PRELOAD把WAIT的timeout_ms置0，SDK报ioctl ret=-1/status=-1，随后出现Failed to free buffer；探针最终退出0，不能判全通过 |
| cancel | INVOKE后执行CANCEL，内核接口返回0；SDK卡到外层12秒timeout，退出124，不能判全通过 |
| 进程被杀 | INVOKE后仅杀独立探针，退出137，未杀视频进程 |
| 后续请求 | 三种故障之后各跑3轮普通DenseNet，全部正常退出且9份输出与5.15字节一致 |

PM独立1000轮DenseNet、外层12秒，退出0；采样排除在性能表之外。
故障注入只进入独立NPU探针，没有注入真实硬件挂死，没有盲写MMIO。
这些证明后续正常请求可恢复，不证明真实软复位失败分支、精确用户errno或所有DMA/IOVA页回收。
故障后无残留probe进程；CmaFree在独立观察前后均243032 kB，也不能替代逐资源计数。
候选电压未获得有效框架读回，不把驱动请求890000 µV冒充本次实测。
保页例外仍是**代理暂定，待用户确认**，本次未触发该故障锁定分支。

## HDMI＋Wave5

只创建独立video recvonly WebRTC会话：不加载产品UI，不创建HID数据通道或音频transceiver。
通过SSH loopback访问现有One-KVM编码器，没有启动第二个编码器；20秒等首帧超时后关闭会话。
在NPU关闭的对照中，日志显示raw received=3/pushed=2、encoded=0，GStreamer Failed to process frame，
dmesg记录17次`wave5_vpu_enc_register_frame_buffer, fail: -12`。
CmaTotal=262144 kB；全机MemAvailable约7.4 GB。初判需检查连续内存容量、分配/回收与运行时配置，
不能仅凭总空闲内存排除CMA问题，也不能据此归因为NPU并发干扰。
浏览器未收到可解码帧，丢帧与NPU开启后的延迟/影响没有有效数据；未继续做无基准的并行测试。
没有操作Mac mini M6产生运动，也没有把no_signal标签解释成物理源故障。

## 回退、证据与后续

普通reboot回默认5.15，恢复五个助手；12个文件的SHA和uid/gid/mode全等于现场备份，
包括Image、DTB、extlinux、uEnv、登记文件。四服务active，UDC configured，无残留探针。
没有改默认内核、启动文件或正式部署锁；锁已释放，未push。
证据在本机`build/npu-board-20261030-r6/`和板上`/var/tmp/vim4-npu-accept-20261030-r6/`，
含原始/最终证明、UART、全部候选张量、逐模型result、差异量化、故障日志、视频日志及PM采样。
旧5.15基线仍在r4工作目录；独立故障shim的源码随本机证据保留，不对视频进程使用。

下一轮先离线修YOLO任务创建/错误输出传播、审查wait/cancel释放路径，
核对候选CMA规划及Wave5帧缓冲分配；不在本轮板上试改驱动。

验证：共享主仓unittest运行305项、7跳过，唯一失败为并行GPU新增gpu-diagnose.py未登记工具目录。
保留GPU改动；以已提交HEAD加本次三份文档在隔离工作树重跑，305项、12跳过，其余通过。
隔离树未初始化子仓，因此多出5项子仓相关跳过；不能把隔离结果写成共享工作树全绿。
