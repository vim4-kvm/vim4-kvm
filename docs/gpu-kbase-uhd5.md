# uhd5 kbase构建与历史门禁

当前已批准正式来源锁，见[主线集成记录](bringup/2026-10-31-uhd5-main-integration.md)。
以下保留初次构建与r10历史过程；后续r11/r12结果及用户批准范围以上述记录为准。

基线为正式uhd4内核8bca939d6bbd3e4d91e9f23b812e920172c99b3d，主仓470da38。
外部r44p0/UK11.39补丁、WC heaps及五档governor保持独立，不把DDK并入内核树。
候选GPU节点仅匹配kbase专用compatible，Panfrost不能绑定；默认Panfrost DT与5.15启动项不改。

## 构建合同

uhd5相对[uhd4配置](../packaging/kernel-edge/uhd4.config)只改
[配置差分](../packaging/kbase/uhd5.config.patch)：release标识与CONFIG_THERMAL_EMULATION=y。
因此需要一次新的Image与完整匹配模块集；不能复用uhd4模块的BTF或vermagic。
其他只改外部模块的迭代仍只重编外部模块，不重编Image。
编译必须持board-queue heavy票据，不持板票据。模块使用同次vmlinux/Module.symvers。

thermal emulation用于验证GPU zone跨95°C trip后cooling状态与实际频率上限；
5.15原配置也启用了此功能。只允许在测试窗口写具名GPU zone的emul_temp，finally写0并核对，
不改trip、PWM、电压。产品运行不设置模拟温度；是否保留该诊断接口由集成审阅决定。

## 工具与证据

独立工具分支board-window-payload-id@d82d429已由用户审阅合入main（be81255）。
它以namespace/payload_id区分不同模块/DT，真实kernel build_id仍负责PID1运行内核校验。
初次候选从该工具worktree运行board-window；后续使用main版本，必要回退修复随本次合入。
旧build-ID目录包与HDR/hdr10包保持原恢复/cleanup路径。
工具最终回归：Mac/Linux各352项（14/18环境跳过）；
覆盖同Image两payload、已有目录/符号链接拒绝、真实build ID不匹配和旧格式清理。
额外证明同Image各payload的恢复记录分别保留，避免漏清首次创建的模块挂载点；
完整inventory留在本机，cleanup仅传精简身份，避免超过Linux单参exec上限。

首次uhd5冷启动暴露异步probe请求未加载governor的WARN：
`__request_module → try_then_request_governor → devfreq_add_device → kbase_devfreq_init`。
这会与模块初始化的async同步互相等待，HDMI/gadget的modprobe也被拖住。
未跑GPU负载即回5.15，四服务/UDC/保护文件与临时助手均恢复核验。
0008主题补丁补`MODULE_SOFTDEP("pre: governor_vim4")`；构建器校验实际模块softdep，
完整stage的`modprobe --show-depends`证明governor先于mali插入。
这属于新默认策略的加载依赖，不改变Image或DVFS参数；修后只重编外部模块。

5.15复用[r9共享缓存](bringup/2026-10-31-kbase-r9-queue.md)，不得重测。
上板前核对缓存的5.15身份、启动/程序/plugin文件哈希；不匹配则停止配对并记录，不伪称缓存命中。
有效基线中位数/P95：DMA1.692/3.618ms、GLES616.361/617.773FPS、
CL latency78.32/79.14µs、SP101.69/101.71GFLOPS。

## 短窗口门禁

窗口一：5.15证明→一次性RAM候选→零WARN/fault加载→三API/像素和六类VK/CL（含default CMA）→
同协议七轮（含5分钟空闲）→mpgpu连续/半占空/空闲→GPU热模拟及恢复→4K60+GPU并行→回5.15。
预留最后4分钟恢复，最多30分钟；只在剩余预算足够时启动下一项。
窗口二如有需要：同Image、另一个payload/DT恢复dma-coherent，做最小及导入负载二分，首fault停项，
采日志后回5.15；不在板上现场改驱动。

每窗结束核对四服务、UDC、原始保护哈希、临时助手及emul_temp恢复，释放票据。
默认策略性能、温控、mpgpu和并行均通过后，才形成供审阅的产品合入清单；不自行合入正式。
[r10已执行结果](bringup/2026-10-31-kbase-r10-uhd5.md)：API/内存、mpgpu和温控通过；
DMA中位数与CL SP未达5.15，服务级并行与dma-coherent二分未完成，不能推广产品。
第二窗工具cleanup因大参数失败，修正已入独立工具分支，尚待板测；基线状态已独立核验。
