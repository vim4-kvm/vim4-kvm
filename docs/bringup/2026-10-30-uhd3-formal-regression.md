# 2026-10-30：NPU与nodebug正式合入、uhd3回归

用户于2026-10-30批准NPU六段合入、纯调试关闭、验证后pin/push，以及软复位失败时
拒绝后续请求并保留可能仍被DMA使用的页至重启。真实复位失败注入仍未验证。
GPU HDR会话仅离线工作；本轮不修改GPU源文件、Mesa或GPU配置。

## 源码、配置与离线门禁

正式VM工作树`~/src/linux-7.3-hdmi-integration`的`vim4-kvm-7.3`从213f271505411
快进至f71b5c6289cb3254690e57292327e73514f0715f，树f3f8877c70e547bc53f2ca0469c25fcffb7f15a6。
六段保持原作者/许可证，未重写历史：

| 提交 | 边界 |
|---|---|
| 3b3b70be472f0 | 厂商执行核心与兼容ABI |
| 7fecc129445ad | T7C binding |
| 3d7e1fd06c49f | T7/VIM4 DT |
| af3bf7eed020d | 标准平台接口适配 |
| e8e61f526eee8 | 缓存fixup、取消与恢复 |
| f71b5c6289cb3 | ABI/边界/PM/生命周期测试 |

uhd1/uhd2/edge采用已审阅nodebug集合，ADLA_COMPAT=m；新`uhd3.config`使用
独立release **7.3.0-vim4kvm-uhd3+**。有效配置与已验nodebug仅LOCALVERSION不同。
关闭DEBUG_MISC、SLUB_DEBUG、DEBUG_RT_MUTEXES、DEBUG_SPINLOCK、DEBUG_MUTEXES、
DEBUG_WW_MUTEX_SLOWPATH、DEBUG_RWSEMS、DEBUG_LOCK_ALLOC、LOCKDEP、FUNCTION_TRACER、
FUNCTION_GRAPH_TRACER、FTRACE_SYSCALLS及其自动退出的依赖。保留BTF、KVM/SCHED_INFO、
事件tracepoint、栈清零、PAN/MTE/PAC、栈保护等安全基线。失去的诊断能力及临时调试构建方法
见[nodebug审计](../uhd2-nodebug.md)和[草案说明](../nodebug-performance-gate.md)。

完整Image/dtbs/modules成功，**2338模块**，名称集合与nodebug相同；网口、Wi-Fi、
Panfrost、HDMI/VDIN/Wave5/JPEG、CRG/ACM、IR、ADLA均齐全。
build ID **a3572361d542e5505bd159ad8a327cf364fe25f3**。
ADLA dt_binding_check和目标DTB schema校验通过。第2–6段checkpatch严格检查为
0 errors/0 warnings/0 checks；仅过滤已由MAINTAINERS覆盖的FILE_PATH_CHANGES提醒。
原样厂商导入段单列5207 errors/11236 warnings/678 checks，不作机械格式化。
主仓unittest **315项（8跳过），其余通过**；驱动IOVA/取消/生命周期/PM宿主C回归与bounds测试通过。

## RAM上板：17:23–17:31 PDT

入场5.15.137-vim4kvm-hdrdual6、四服务active、UDC configured，板/重负载/日志锁已取得。
串口仅操作U-Boot RAM环境；默认5.15、/boot/edge、extlinux与U-Boot未改。
CMA保持512M@0x10000000-0xf0000000；载荷完整模块经私有PID1绑定。
临时部署五个精确release路由帮助程序，退出后逐一恢复原内容与权限。

| 回归 | 实测与判定 |
|---|---|
| KVM页面 | manager认证、status/kernel API、页面/JS及One-KVM页面/JS均200 |
| One-KVM＋HDMI＋Wave5 | 专用仅视频recvonly客户端，59.182秒推进3552解码帧，**60.018fps**；丢帧/丢包/冻结计数均0，无编码失败 |
| gadget/HID枚举 | CRG configured，现有三HID配置保留；仅读取描述符/配置，无HID报告写入 |
| ACM | 使用现有helper暂启ACM、关闭未测试音频功能以符合端点预算；acm.usb0及ttyGS0存在、只读打开成功，随后原配置精确恢复；不证明M6主机侧串口数据传输 |
| GPU | 既有私有Mesa26.2.6，Panfrost/Mali-G52，512×512显式展开shader，124帧/0.201秒，像素179,128,128,255，gl_error=0；GPU错误零增量 |
| 运行身份 | /proc/config.gz哈希匹配；11具名加载模块build ID逐项匹配清单，taint=0 |
| 回退 | 5.15默认，12文件SHA/uid/gid/mode全部与入场相同，四服务active、UDC configured |

视频只有接收通道，不加载产品输入脚本/数据通道，不发键鼠，不测声音；不ptrace、不写PWM、
不盲读寄存器。各进程有超时，媒体/编码器锁与板锁生效；结束全部释放。
PCIe原有可恢复`IRQ index 1 not found`及wireless-extensions弃用提示保留，未新增oops/taint。

## NPU与内存快检

probe固定CPU2、worker CPU1、IRQ CPU0，CPU两簇2208/2016MHz；每模型3个独立context。
VGG16/DenseNet各1000轮去50，YOLO101轮去10。三模型**6909个完整输出文件均与5.15基线字节一致**，
task create失败0。下表合并同启动context，只作回归快检，不冒充多启动统计门禁：

| 模型 | 暖样本 | 平均ms | P50ms | P99ms | 最大ms |
|---|---:|---:|---:|---:|---:|
| VGG16 | 2850 | 0.5060 | 0.4978 | 0.6180 | 2.1671 |
| DenseNet CTC | 2850 | 1.9514 | 1.9403 | 2.2835 | 10.5969 |
| YOLOv8n | 273 | 29.7524 | 29.5631 | 34.2432 | 36.0822 |

YOLO fwrite均值2.6685ms、端到端34.8079ms；此前调试构建约7ms写入未复现。
CPU2微基准5重复：4,838,400B tmpfs fresh write中位1718.4MiB/s、fwrite+close
1692.2MiB/s、read/copy_to_user 2132.8MiB/s；64MiB memcpy为6887.9MiB/s。
A73温度49.6–58.0°C。DDR安全接口不可用，记null，未以猜测频率填值。
此前多启动性能置信区间“不确定”结论保留；本轮未重算配对CI或证明所有模型长期≤5%。
此次正式采用依据用户明确批准和本轮限定回归通过，不宣称长期稳定性、声音或HID输入资格。

## pin字段与板上保留版本

`sources.toml`的kernel/tested_build更新为本轮uhd3；所有SHA从实际载荷读取，
完整值随该文件提交。Image为原始未压缩格式，image与uncompressed_image SHA相同；
manifest与source_manifest也相同。runtime-proof只证明候选完整载荷清单，不是eMMC安装证明。
live-proof为板上uhd3配置、notes、taint及运行版本实采，11模块ID与构建清单相同。
新增retained_runtime明确保留uhd1的实际ID、Image/DTB与登记proof，不能将pin解释成已覆盖/boot/edge。
板上FullKvm仍为旧uhd1，默认Default仍5.15；本轮没有正式内核持久部署或外部Release。

本地证据：`build/uhd3/`的构建/配置/schema/checkpatch/manager测试日志，
`build/uhd3-window/evidence/`的原始/候选/最终proof、每轮SDK与分段、6909文件哈希、
微基准、ACM/GPU/HTTP证据及dmesg，`video.log`与两个UART日志。
板端`/var/tmp/vim4-uhd3-window/`；载荷VM`~/build/uhd3-candidate`。

## manager EDID与交付

manager提交0c89b292eac4fd07c85fdf142dfa18591c04a329：仅修复7.3缺失/空EDID状态处理，
非空损坏EDID仍报错。通过既有Ubuntu manager单组件package/verify与board.py deploy；
包2.5.1+vim4.20261029.102.dev.3.g0c89b29.dirty，`.dirty`来自主仓部署准备改动，
manager源本身干净。隔离Go测试/vet通过；helper220项（12跳过），其余通过。
部署只重启manager，One-KVM启动时间不变；板级check通过。启动等待中的未认证401不作API故障。
5.15认证GET /api/edid返回200，activeKnown=true，RTK-CONTROL正常；无EDID写入。
部署后再次核对12保护文件一致、四服务active、UDC configured、dpkg audit无输出。
内核正式分支已推送213f271505411→f71b5c6289cb3；manager main已推送81c6cc5→0c89b29。
主仓交付范围为5a05138之后全部已提交的NPU/GPU/内存工作，加配置提交2e4e98d和本记录/pin提交；
push前确认GPU没有未提交文件混入，采用显式文件列表提交，未修改GPU源码。
原始push日志在`build/uhd3/{kernel,manager,main}-push.log`，远端核对另存remote-final.log。
主仓最终unittest为315项、8跳过；pin构建入口validate-only通过，生成配置SHA与上板完全相同。
不发布GitHub Release。
