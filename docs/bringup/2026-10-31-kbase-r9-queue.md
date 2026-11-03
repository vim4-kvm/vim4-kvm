# 2026-10-31：kbase r9队列首用与候选目录冲突

当前结论：外部模块、ABI、339项宿主测试通过；5.15默认策略七轮及温度已完整写共享缓存。
7.3候选因工具固定目录已占用而未启动，硬件门禁仍未过；最后保持5.15，四服务/UDC/哈希通过，票据已释放。
当前[候选入口](../gpu-kbase-7x.md)，前次见[r7离线记录](2026-10-31-kbase-r7-offline.md)。

## 代码与离线验证

0002平台层纳入mpgpu草案的只读缓存ABI：class为mpgpu，utilization输出十进制百分比加换行，
初值0，DVFS回调WRITE_ONCE，读取READ_ONCE；不在show里更新metrics。
class创建失败走reset/bus/PM回收，term先移除class。只支持单GPU，不覆盖已有class。
草案来自manager会话的docs/kbase-mpgpu.patch，仅只读审阅，未修改其工作树。

补齐metrics定时器销毁条件：初始化覆盖DEVFREQ或MIDGARD_DVFS，原term却仅覆盖后者。
0005现保证两种配置均停止状态并同步hrtimer_cancel，新增实际term函数宿主模型验证取消顺序。
0008仍是厂商式五档策略，0009通过schedule_work使用7.3的system_percpu_wq。

三外部模块W=1/KCFLAGS=-Werror、modpost/BTF、UK11.39的UAPI字节及34 payload/40 ioctl对照通过。
nm只引用system_percpu_wq，不再引用system_wq。新增/修改补丁无新增未允许的strict风格提示。
完整unittest：339项通过，10项跳过。Image仍为uhd3封存的9daea7a17e228cb5ef93b6b9cc926ccce43ec3b8eafb1b22aee447fdcfcb7000，
没有重编基础内核。首次打包因我选用了已转换kbase的DT而被Panfrost输入门禁拒绝；
改用原始保留DT后复用已编译模块完成打包。另修正class回调参数的缩进并仅增量重编该对象。

## 队列与首个短窗口

仅在vim4-kvm-kbase-r2工作；取入origin/main的已合入队列工具，当前合并尚未提交。
构建使用heavy票据，不持板票据；旧HDR heavy释放前没有编译。构建失败/完成后均由run释放。
最后核对正式sources.toml仍为f71b5c6289cb / 7.3.0-vim4kvm-uhd3+。

板票据f6a6e6bc5f394e5fab0f3ae9c13f1356、order14、purpose r9：
通过board-window collect与identity确认5.15.137-vim4kvm-hdrdual6、受保护文件哈希、
服务active、UDC configured；候选目录存在检查阻止后续步骤。
finally再次核对同一身份/文件并collect，未重启、未停服务、未安装临时助手。
未发HID、未测声音、未ptrace视频进程，未写PWM/电压或刷写启动文件。
退出后HDR的uhd4-smoke票据取得板子；没有继续访问板子。

## 工具问题与最小修复建议（未改工具）

board-window validate_bundle将trial.json的启动命令固定到
/var/lib/vim4-kvm/display-m1/<kernel build ID>，display-once.stage对已存在目录直接FileExistsError。
本次该目录已经存在，不属于本轮新产物，因此在stage前停止，没有挪动或覆盖它。
同一基础内核下仅修改外部模块或DT，真实GNU build ID不变，不能用这个ID作为唯一候选身份。
也不能为了规避目录冲突伪造内核build ID或重编基础Image。

建议：保留真实kernel build_id用于模块/BTF/运行内核验证，另用完整payload哈希或独立payload_id
命名私有候选目录；manifest显式携带受限命名空间，static init与sysboot验证使用同一目录合同。
这样同kernel的多套模块/DT可并存，候选链不必删除旧试验。此处只提建议，未改board-queue工作树或工具实现。
应补回归：同一Image/build_id配两套不同模块/DT均可独立stage、旧目录保留，真实build ID不匹配仍拒绝；
已有不属于当前payload的目录与符号链接仍应拒绝，不能通过放宽覆盖检查消除冲突。

另一个范围限制：board-window baseline CLI当前缓存的是浏览器接收指标，既有记录不含统一空闲历史的
七次DMA/GLES/CL中位数/P95与温度。共享baseline-cache.json当时不存在，不能将r6三次成绩视为命中。
私有窗口脚本使用同一BaselineCache、5.15身份/文件、probe/shader/脚本SHA及独立测量scope保存GPU结果，
无匹配记录才补测；后续修正私有脚本后已完成一次有效补测。

## 5.15有效补测与缓存

有效票据88f34a5ad328482c98c25130ff47ee6c（order42），UTC约12:21–12:31，sampling开启，
共享缓存scope=kbase-default-parity-v3；保存身份、内核/程序/plugin/libmali及探针/脚本SHA。
初次缓存reused=false，source_time记录测量开始；后续只有相同协议与身份才可复用。
没有匹配旧GPU缓存，r6的三次成绩未代替七轮。

| 默认策略、同heap-gfx | 中位数 | P95（nearest rank，七样本即最大值） |
|---|---|---|
| Vulkan DMA submit+wait ms | 1.692 | 3.618 |
| GBM/FBO GLES FPS | 616.361 | 617.773 |
| CL kernel latency µs | 78.32 | 79.14 |
| CL SP float GFLOPS | 101.69 | 101.71 |

同300秒空闲、每项前2秒间隔、相同内部预热与七次顺序。首个DMA冷档与后续暖历史不同，
保留逐提交频率原文，不能将中位数当作250MHz固定耗时。
idle-end GPU/SoC/A53为49.3/51.5/49.8°C，load-end为53.5/57.2/53.7°C；
这是本轮5.15数据，不是功耗测量，也不是与7.3完成温度配对。

只读运行态：CONFIG_MALI_MIDGARD_DVFS=y、CONFIG_MALI_DEVFREQ关闭，scale_mode=1，
dvfs_period=100，pm_poweroff="400000 2 0"，power_policy="coarse_demand [always_on]"，
空闲cur_freq=250MHz、utilization=0，min/max为档位0/4。
相同r44的all_policy_list[1]也使当前7.3源码默认always_on，无需新增门控改动。
视频进程实际环境VIM4_VIDEO_BACKEND=vendor、单物理分配偏好=1、私有V4L2路径，
结合源码支持现有5.15产品使用厂商GE2D/编码器路径，GBM BO→Wave5属于新增能力，
不能把该能力未测说成现有产品路径失败；可选显示passthrough仍需单独验收。

期间发现并修正私有暂存目录root归属导致SCP失败；一次交接时SSH不可达，仅连接失败即退出，未串口干预。
原遥测遍历非GPU devfreq触发EINVAL，现仅读GPU频率及GPU/SoC/CPU温度，缺测保留errno，不填0。
一轮已产出七次原始结果但收尾被总超时终止，未写成功缓存；增加逐步保存和SIGTERM诊断后重新完整测量。
新增宿主回归验证可选属性EINVAL及超时保存。单探针仍30/45秒限时，批次590秒、外层599秒。
失败轮次独立保留，不与有效缓存混算。

有效窗口未进入boot-candidate：补测完成后目录占用门禁停止。没有安装临时运行时助手、manager或切换内核。
final-baseline.json核对四服务active、UDC configured和六启动文件；父脚本另核八项保护文件身份一致。
没有为恢复而重启已经运行的5.15。最终队列无本会话票据，两个旧锁free。
最后fetch的origin/main为07ed1e5，正式清单仍uhd3；该提交放宽release tag，未解决payload目录碰撞。

## 尚未通过的门禁

7.3新默认策略七轮配对、mpgpu实际忙闲/占空比、default CMA CL、coherency二分、
候选零WARN/fault和并行60fps均未运行，不能把宿主通过当作硬件通过。
uhd3没有CONFIG_THERMAL_EMULATION，温控实际触发仍未验证。
因此尚不满足本轮提交/推送和产品路径方案的前提；不直接合并，不推blob。

证据：logs/kbase-r9-window中的module-build/incremental/finalize/style/unittest/prepare日志、
baseline-proof.json、vendor-contract.json、vendor-cache.json、collect JSON及各window日志；
共享队列history.jsonl记录票据释放/后继取得。raw目录中旧失败文件可能因SCP覆盖留存，
有效结果以vendor-cache.json及其完整28项samples、62项thermal为准，不使用旧失败result.json。
