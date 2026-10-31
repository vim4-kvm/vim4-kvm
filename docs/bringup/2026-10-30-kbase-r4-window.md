# 2026-10-30：kbase GBM分配器缺口与Vulkan执行故障

结论：明确定位r3静默退出发生在gbm_create_device：blob需要的两个DMA heap在7.3缺失。
Vulkan/OpenCL均能独立查询到Mali-G52目标版本，但Vulkan DMA负载三次DEVICE_LOST并触发GPU/MMU fault；
没有性能追平结论。零WARN加载保持，真实执行故障后停止额外负载并回5.15。
前一轮见[r3窗口](2026-10-30-kbase-r3-window.md)，移植方案见[维护入口](../gpu-kbase-7x.md)。

## 离线准备与本轮边界

先读探针所有exit/return分支，旧的DRM open、GBM创建、入口查询及部分EGL/GL配置分支无诊断。
改进packaging/gpu/gpu-probe.c：参数范围检查；打印uid/euid、LD_LIBRARY_PATH及三入口dladdr来源；
失败打印阶段、errno、EGL/GL错误和dlerror，shader/link失败附编译日志。
不改变shader、尺寸、迭代数与计时逻辑。ARM64已有builder、network none、Werror编译通过；
无设备路径与非法参数各退出2并有诊断。无需GPU的负向用例能复现旧探针的静默缺陷。

取得board→heavy双锁后，确认5.15 hdrdual6、四服务active、UDC configured；
复用r3固定Image/完整模块/DT和静态PID1，仅换诊断工具。模块SHA仍为
4ff4bbf3490d34a3f5f59e3b8b92f33c6199f6ae0d7dcf533ec1f1f26163359d，
build ID仍为a3572361d542e5505bd159ad8a327cf364fe25f3。
五个助手先完整备份，再按封存SHA临时同步；RAM sysboot选择已有kbase-r3-once私有目录。
不改默认Panfrost DT、5.15默认、U-Boot环境、系统Mesa或blob。
板端UTC 2026-10-31约04:17–04:24（Mac日期10月30日），总窗口远小于30分钟。

## EGL根因：实测排除与直接阻塞

| 边界 | 5.15 | 7.3 kbase |
|---|---|---|
| 探针用户 | root | root |
| /dev/mali0 | 0666，root:root | 0666，root:root |
| card0驱动 | /sys/bus/platform/drivers/meson | /sys/bus/platform/drivers/simple-framebuffer |
| DRM节点 | card0、renderD128 | 仅card0（3fdeec00.framebuffer） |
| card0 open与GET_CAP | 成功 | 成功 |
| 三入口提供者 | 同一私有libMali | 同一私有libMali |
| libdrm/Wayland等闭包 | 无not found | 无not found，解析路径逐项相同 |
| GBM创建 | 成功 | NULL，errno=ENOENT，EGL_SUCCESS，dlerror=none |

诊断输出直接证明临时前缀生效：eglInitialize、glGetString、gbm_create_device均来自
/tmp/vim4-kbase-*/lib/libEGL.so.1（符号链接到锁定blob），不是系统Mesa。
普通khadas账户也在video/render组，但本轮探针实际以root运行，权限不是该失败的解释。
两侧ldd完整递归解析依赖一致，含libdrm、Wayland client/server、stdc++、ffi及glibc等，
临时前缀查找普通依赖失败后由系统路径正常满足，不能把那些中间ENOENT当缺库。

仅对诊断探针及其启动器使用strace openat/ioctl/access/readlink；没有ptrace视频进程。
5.15 trace：card0 open成功，GET_CAP成功，然后system-uncached和heap-gfx都成功打开，
可选heap-secure缺失也不影响后续EGL1.5/GLES3.2上下文及渲染。
7.3 trace在同样的card0/GET_CAP成功后，两次打开均ENOENT：

```text
openat(..., "/dev/dma_heap/system-uncached", O_RDWR) = -1 ENOENT
openat(..., "/dev/dma_heap/heap-gfx", O_RDWR) = -1 ENOENT
gbm_create_device failed: errno=2 (No such file or directory), EGL=0x3000 GL=0x0 dlerror=none
```

因此当前直接阻塞是blob GBM的DMA分配器合同未满足，失败尚未到eglInitialize。
7.3实际只有system、reserved、default_cma_region；不能把cached system或CMA heap重命名/软链接
成system-uncached来宣称兼容。显示DRM由meson变simpledrm、缺render节点是额外差异；
尚未证明补齐真实heap合同后GBM/显示格式互操作就能通过。本轮未现场新增任何heap或库替换。

## 独立API查询与负载

EGL失败后按本轮新授权继续独立VK/CL路径，不沿用r3的首错全停策略。
加载及各负载后全量dmesg均没有WARNING/BUG/oops；但真实GPU fault同样阻止推广。

| 项目 | 5.15 libmali，本轮 | 7.3 kbase＋libmali，本轮 | 7.3 Panfrost，历史私有Mesa26.2.6 |
|---|---|---|---|
| EGL / GLES | ARM 1.5 / 3.2 | GBM创建失败，无上下文 | 1.5 / 3.1 |
| Vulkan设备API | Mali-G52 1.3.231 | Mali-G52 1.3.231 | 1.0.354，实验 |
| OpenCL设备 / C | 3.0 / 3.0 | 3.0 / 3.0 | 3.0 / 1.2 |
| GLES FPS | 619.040 / 617.597 / 618.961，均值618.533 | 不可运行 | 旧均值233.730，非本轮配对 |
| DMA compute，submit_wait ms | 1.892 / 1.933 / 1.900，逐字校验PASS | 三次VK_ERROR_DEVICE_LOST，无有效耗时/像素结果 | 旧中位数8.038，非本轮配对 |
| CL kernel latency | 回退后修正测试器测80.33µs | 子集未实际启动，见下 | 无同子集样本 |
| CL SP float | 回退后101.73 GFLOPS | 未取得负载数据 | 无同子集样本 |

API输出完整扩展已存vendor.json/candidate.json，均是真实Mali-G52，没有llvmpipe/lavapipe。
Panfrost只引用[旧三栈验收](2026-10-30-gpu-acceptance.md)，未新启动Panfrost。
新诊断探针含已有2秒预热、5秒steady循环与计时外回读；旧613.31 FPS来自旧探针口径，
仅作参照，不能把本轮618.53解读为性能改进。没有有效候选GLES性能配对。
DMA仍使用同一SPIR-V、24,883,200字节、6,220,800 uint；5.15 heap-codecmm，7.3 default_cma_region。
候选在vkWaitForFences报-4（DEVICE_LOST），约5.36/10.47/4.91秒是失败程序历时，不能充当GPU性能值。

失败期间内核出现t6xx GPU fault 0x4002、AS_ACTIVE stuck、CLEAN_CACHES_COMPLETED等待卡住，
以及AS0 Unhandled Page fault（raw status 0x6c002c1）。日志提到可能clk/pwr不稳仅是驱动提示，
不能由此诊断为电压不足，更不能据此调PWM。本轮没有修改时钟/电压策略或故障后修驱动。
三次原定DMA试次均失败后停止额外GPU负载；后续应把首个DEVICE_LOST/MMU fault也设为立即停止条件。

CL子集本轮最初未启动：测试器在干净环境下sys.executable为空，timeout尝试执行空字符串。
这与CL运行时故障不同。已修正为使用/usr/bin/python3后备，并在回退的健康5.15内以干净环境
重跑两项（--kernel-latency/--compute-sp）均退出0；SP float2/4/8/16为101.68/101.31/101.08/95.40。
候选已处于GPU执行故障状态，没有为补数据再次运行CL或重启候选。
最初strace调用也因空PATH找不到python3，纠正测试器PATH后才取得有效trace；未将该调用失败归因EGL。

## 其余项目与回退

故障后仅取只读状态：devfreq公布800/666.666/500/400/250MHz，cur_freq=250MHz，
governor=simple_ondemand；cooling设备devfreq-fe400000.gpu已注册。
没有执行五档写入/负载往返、真实thermal限频或确认zone绑定；HDMI＋Wave5并行未执行。
四服务active仅是服务状态，不证明视频帧/并行性能正常。

SSH正常reboot回5.15.137-vim4kvm-hdrdual6，五个助手按内容/模式/属主恢复并校验原SHA；
原不存在文件移除。六个受保护启动文件SHA与入场相同，四服务active、UDC configured，
最终再次确认后释放双锁。未发HID、未进行声音测试、未ptrace视频进程、未写PWM、未推blob。
HDR工作树与原主仓main均未修改。

原始证据为忽略目录logs/kbase-r4-window/：vendor/candidate JSON、*-egl.strace、
*-libraries.txt、candidate-dmesg.txt、candidate-final.txt、vendor-cl-fixed/、final.txt、final-services.txt。
脚本及新探针在build/kbase-r4-window，模块仍为r3封存产物。本轮不包含GPU故障或heap合同修复。

新诊断探针SHA256为77748220e39bdb1fe59052b8150e58e2cfa31988f2e0affad6834ef6c8ce76dc。
主仓离线unittest：317项、13项环境跳过、无失败；git diff --check通过。
内核分支本轮仅新增证据，提交30df5824c4bb2；无驱动/DT现场修改。
