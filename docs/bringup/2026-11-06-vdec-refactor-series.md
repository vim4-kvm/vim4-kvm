# 2026-11-06：解码分层重构系列

离线审查候选，基于 .38 的 `d177f0dc1ca40a33dadee38f95c08fa332236f69`。
内核分支 `vdec-refactor`，工作树 `/home/deepdream/src/linux-7.3-vdec-refactor`，
尖端 `0ae8beaa56d3a798e8078c5f727c34ed3acafd9c`。原计划第 1 项按批准拆成两提交，
故重构共十个内核提交，另有一个按审查要求单列的 selection 语义提交和工具配套改动。尚未上板、push 或合并。

## 实现边界

`aml_vdec_stateless.c` 和 `aml_vdec_stateful.c` 分别持有 request 与 stateful 的
ioctl/vb2/m2m 表；控件数组归 H.264/MPEG-2，HEVC/JPEG 节点描述符归各自 codec 文件。
两个接口实现均不 include hevc.h、也没有 codec 名称；平台节点表绑定名称、描述符和所需 core，
按原顺序注册，core 缺失时跳过对应节点，失败按数组逆序回滚。
全部节点继续共用唯一 m2m 调度器，公共分发器不判断 codec 身份。
`aml_vdec.c` 保留共享格式、pin、job 所有权；共享核心不含 is_hevc/is_jpeg。

stateful 派生上下文在 open 分配，锁、wait_capture/min_capture、格式缓存和 sequence
不再占用公共 ctx；codec_priv 仍在原 OUTPUT STREAMON 初始化。
job 的完成等待、pin/clock 状态和初始诊断标记保持 open 生命周期，
不会在 STREAMOFF 后重建 codec 时意外多跑诊断快照。

HEVC 分成三个实现：`hevc_dpb.c` 只有 POC/RPS/ST/LT、槽位及现有输出选择元数据，
没有 MMIO、DMA 地址或 vb2；CAPTURE 指针与压缩图/MV 分配分别按槽号关联。
`hevc_hw.c` 持有 DMA、RPM、寄存器、IRQ 和固件握手；`hevc.c` 是 stateful codec adapter。
事件、LAST、drain 和实际缓冲完成只在 stateful 层。
JPEG 继续走 direct pair，HEVC 走 buffered CAPTURE，未引入第三种模式或 disposition。

VDEC1 与 HEVC 前后端各有资源子结构，固件/复位通过描述符与 post-load 回调绑定。
统一 job acquire/stop/release 保留停止 DMA 与归还缓冲之间的边界：
request 在原 request_complete 后 release，HEVC 在原输出处理后解锁/unpin。
停止失败沿原 quarantine 保留 owner/分配/映射；每 job stop 不变成每 job 断电。
HEVC swap 缓存仍跨 job 保留，runtime PM 的释放时点不变。

两个 HEVC 显式诊断入口移至
`/sys/kernel/debug/aml-vdec/<platform-device>/{hevc_test,hevc_core_test}`，
测试函数和缓存独立于正常解码。根目录只在模块初始化创建一次，各设备保留自己的子目录；
remove 只删该设备子目录，模块退出在所有设备注销后删根。复制失败保留 -EFAULT。
注册 debugfs 文件不会运行 MMIO 或上电实验。
保留 `enable_t7`、`allow_t7_power`、`t7_snapshot_only` 三个门；去门属于后续独立行为系列。

## 提交与审查映射

| 项 | SHA | 内容 |
|---|---|---|
| 1a | `8cc53e636ee143e962271572af7c97ce4e163263` | 机械移动 ioctl/vb2 接口，隔离原 job/pin 所有权。 |
| 1b | `6c6a938a899eb3893a81644a130084a3dc3488c6` | 节点描述符绑定两类接口，删除 codec 身份分支。 |
| 2 | `b0df4655237e5b4eab5645d8d68e27f0bb464704` | 私有 stateful 上下文，保留初始化及锁顺序。 |
| 3 | `43125b1e601def5c4b089ef1b27edd3afd4445ca` | 纯 HEVC DPB 与直接链接 KUnit，原算法不变。 |
| 4 | `04aaf96585d818773c7a20f21dc553577b5a9bd4` | HEVC DMA/MMIO/IRQ 移入硬件层。 |
| 5 | `cbf35e112b2efd38b63fa9f574b06e8dbc64294f` | HEVC/JPEG stateful 回调与共享协议完成路径，附真实事件/vb2 KUnit。 |
| 6 | `36637de41a4ee7b311775f7d9772c6b5fcf313fd` | VDEC1/HEVC core 资源和诊断状态归组。 |
| 7 | `035e74425fbc16a959880f204641a83f5ef5eddf` | 静态复位/固件描述，H.264 scratch G post-load。 |
| 8 | `ed45b254b1b9d15b5089909e740338b4fb802f54` | 统一 job 生命周期，附四个所有权边界 KUnit。 |
| 9 | `1f99a58efa926689b4a3a4a211934a50b8e8eba1` | HEVC 显式诊断迁至模块根目录下的设备 debugfs。 |
| 独立语义 | `0ae8beaa56d3a798e8078c5f727c34ed3acafd9c` | 去掉 request 节点恒拒绝的 selection，EINVAL → ENOTTY。 |

没有旧新入口兼容垫片、重复的硬件拥有路径或逐函数 HEVC KUnit 导出。
原 VDEC1/S4 固件与复位代码仍编译，原 HEVC 寄存器和握手交错顺序保留。
静态审查附 `build/vdec-refactor/static-audit.json`：十个纯 DPB 函数归一化后与基线相同，
十四个硬件函数的寄存器调用行相同；它不替代硬件轨迹或像素验证。

## 两轮审查修正

结构与行为意见分别来自 worker 状态目录的 `vdec-refactor.review2.md`、`vdec-refactor.review3.md`。
节点/控件归属和平台节点表已折入第 1b 项，测试私有入口改为包含 `.c` 并折入第 5 项，
exit 只走 job_stop、无直接重复 finish 已折入第 8 项，模块根目录修正折入第 9 项。
前十提交保留 stateless G_SELECTION/G_CROP/CROPCAP 的 -EINVAL；仅最后独立提交改为 -ENOTTY。
板验须保持原 stateless compliance 60/60，若计数变化按实际记录，不伪装纯移动。

静态证据 `build/vdec-refactor/review2/{ownership-audit,control-audit}.json`：
两个 codec 节点描述符原样搬迁，H.264 八个/MPEG-2 三个控件配置及顺序完全相同。
S4 仍单节点，T7 仍 request → JPEG → HEVC；HEVC core 缺失只跳过最后节点。
视频编号仍待实际板验，离线只证明注册调用顺序与节点表相同。

## 工具配套与门禁

`packaging/kernel/vdec-window.py` 的 HEVC 验收计划必须显式设置
`hevc_diagnostic_api: "debugfs-v1"`，缺声明/入口或版本不匹配就拒绝，
不回退旧 sysfs 的 passing 缓存。新测试验证拒绝发生在电源访问之前，
以及只使用 debugfs 结果。旧候选配套已归档旧工具，不通过自动探测混用接口。
GStreamer EOS fixture 改用节点绑定的格式 flags，仍消费真实驱动格式枚举函数。
协议 fixture 用官方 GStreamer 1.24.2 代码回放初始 SOURCE_CHANGE、EOS 和后续 DRC，已通过。

主仓库完整 unittest：**610 项 OK，14 跳过**，
`logs/vdec-refactor/review2/repo-tests.log`。首次运行发现既有 .38 结果记录缺索引，
补入口后复跑通过；原失败日志保留。工具配套尚未提交：沙箱禁止创建共享
`.git/worktrees/vim4-kvm-vdec-hevc-port/index.lock`。未修改权限；
`build/vdec-refactor/T1-tools.patch` 和 `T1-message.txt` 供协调者审查/提交。
本记录与索引也保持未提交。

本轮最终固定 SHA 系列经正式 heavy **FIFO1581**，票
`adbae82194c249d186cebc8d5627ad14` 已 released。十一提交逐个通过 W=1 模块与
arm64 QEMU KUnit：前五提交 39/39，第 5 项至第 7 项 42/42，第 8 项起 46/46。
逐提交 strict 均零 errors、零 checks；七个新增文件提交各一条 MAINTAINERS 通用提醒，
既有目录 F 已覆盖，保留原始退出码。测试配置有四条既存 KUnit 模块缺 MODULE_DESCRIPTION
的 modpost 提醒，无新增编译诊断。尖端测试模块 SHA256：
`1804b13299cd46d4af0c876f365e6769c840b7fe979ee7a44711d84eaa90b7d0`。

尖端另以 CONFIG_KUNIT=n、DEBUG_FS=n/y 两配置完整链接内核并 W=1 构建模块，均通过，
模块日志零 warning/error。两份模块 SHA256 分别为
`9c4f706eb678323fe503c46fbd145f6803c02819e62fef73ec32854cf864b367`、
`a93a92e5be8f760d21dccd4da27c4f6e692da82285d168647c757a92522f5305`。
它们是离线验证配置，不等于 .38 正式整包或板验。旧 FIFO1570 和旧模块哈希只证明上一版
d8504a9d，不作为本轮通过证据。

复现脚本 `build/vdec-refactor/validate-series.sh` 固定上述尖端，经正式 heavy 入口，
复用自有 O= `/home/deepdream/build/vdec-refactor/{kunit,module}`。
VM 入口 `/home/deepdream/build/vdec-refactor/validate.sh`，Mac 有同名副本。
`build/vdec-refactor/final/gates.json`、`series-titles.txt`、十一份 patches、配置/模块哈希、
source.sha256 与每提交 `reports/<SHA>/` 保存原始证据；日志在 `logs/vdec-refactor/`。
每次构建强制刷新本驱动源文件时间戳，防止复制快照保留旧时间使 Kbuild 复用旧对象。
早期由此造成的一次重复符号失败、其日志与旧门禁均保留，不作为最终通过证据。

私有协议测试为 `aml_vdec_stateful_kunit.c`，仍在实现末尾条件包含，未增加导出。
KUnit 原 39 项保留：第 5 项增加三项实际 V4L2/vb2 边界测试，
第 8 项增加四项 job 生命周期测试。测试覆盖初始 SOURCE_CHANGE 保留 OUTPUT、
DRC 事件先于 LAST 且不停止 OUTPUT、首格式前 STOP 的延迟 EOS 完成；
以及停止后仍持 owner、准备失败不触硬件、部分 acquire 清理、停止失败保留 owner。
新 fixture 首次漏初始化输入 vb2_queue 引发 QEMU NULL dereference，已补齐，
最终逐提交复核包含该修正；不把 fixture 故障描述为驱动实板问题。

## 验收清单与未做项

协调者审查后由 t3k 合成一个候选，整系列上板一次：

1. HEVC 132 条的逐帧 MD5、顺序、帧数和状态对照
   [.38 的 120S/10E/2T](2026-11-06-hevc-integration38-results.md)，
   包括失败流已完成的帧、首错/缺失位置与失败路径；不顺带修失败或新增 unsupported。
2. H.264/MPEG-2/JPEG 对照 .38 窗口既有结果与精度判据，像素/帧数/状态不变。
3. stateless streaming 60/60、media 8/8、HEVC 56/56；JPEG 用 .38 原命令，
   SOURCE_CHANGE/LAST/EOS 与 CAPTURE STREAMON 次数不回退。
4. 原全 I 首帧/三平面逐字节一致，三条 P/B 短流仍 5/8/17 帧逐帧一致、LAST、status 0、零 ERROR。
5. 旧 Success 退步、已知失败输出变化、新 WARN/fault/资源泄漏、compliance 或事件顺序变化，
   均停止并回到离线定位；不现场猜寄存器或改输入，超时沿既定恢复流程。

`ab07ae47` 已撤回：其死 IRQ EOS 路径与错误输出 KUnit 不在基线/本系列。
裁剪修复 `b54ff9b7`、C.5.2 输出重写、NAL/PPS 标志解析、RPS_D 单次解析、
LTRPSPS_A/WPP_D/VPSSPSPPS 及三个门的移除全部留到后续独立系列。
未接触板子、排板票、push、合并或对外发送；本轮完成后等待协调者审查。
