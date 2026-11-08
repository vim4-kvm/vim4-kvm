# 内存与拷贝测量合同

本页管内存微基准的可比性与定位边界；正式配置以[内核锁](../packaging/kernel/sources.toml)和配置为准。
纯调试关闭已集成；历史多启动区间仍不确定，不据短测宣称全面追平。
导航：[判读](#判读与安全边界)、[测量](#独立微基准)、[证据](#证据与未验范围)。

## 判读与安全边界

不为追分削弱安全加固或改变内存策略。配置项差异先证明真实路径和开销，不拿名字猜原因。
memcpy 热缓存、内核用户拷贝、tmpfs 写入及首次缺页是不同端点，不能用一个结果解释全部。
DDR 条件必须有可信的实际只读回读；时钟门控名、晶振和频点表不是实际内存频率。
无可靠读回时明确缺失，不盲扫 MMIO、不写电压或调试频率，也不 drop caches 掩盖差异。

两边复用同一二进制与 libc，按 CPU capacity 簇分别固定并记录实际核、频率、温度、THP、
swap、挂载和 cgroup 条件。固定频率诊断与生产默认策略分组；结束恢复亲和与策略。
线程继承亲和会影响子进程，不能只看主程序参数推断实际运行核。

## 独立微基准

入口为[C 微基准](../tools/memory-bench.c)与[运行器](../tools/memory-bench.py)，
构建、尺寸、计时、超时和内存预算以源码及帮助为准；先离线构建，再占板复制同一产物。
它不调用视频或 NPU，也不负责环境可比性；采样不得与编译或其他负载并行。
输出独占创建，失败保留结果；私有临时文件正常收尾，D 状态无法回收时停止窗口并报告。

memcpy 预触页并通过真实 libc 调用防止优化消除，小尺寸不能宣称 DRAM 带宽。
tmpfs fresh、rewrite、resident pread 与 fwrite 含 close 分开；pread 还含 VFS 和页查找，
不是裸 copy_to_user，stdio flush 也不是 fsync 或持久化。
首次与重复触页比较默认和 nohuge；映射覆盖字节不等于实际逐字节写带宽。
逻辑传输量不是 DDR 总线流量。保留每次重复、首组和 faults/切换计数，
同一启动内重复不能用作跨启动性能区间。

## 证据与未验范围

[nodebug 三方窗口](bringup/2026-10-30-nodebug-memory-window.md)恢复 tmpfs 与 YOLO 端到端，
memcpy/pread 未全面追平；[两对窗口](bringup/2026-10-30-nodebug-paired-gate.md)
未复现大核 memcpy 退化，但联合区间与 DDR 条件缺口仍令门禁不确定。
[正式回归](bringup/2026-10-30-uhd3-formal-regression.md)是所列功能范围的证明，
不能替代性能配对。
后续新窗口遵守[性能协议](performance-baseline.md)，不照抄旧候选 release、恢复目标或文件哈希。
