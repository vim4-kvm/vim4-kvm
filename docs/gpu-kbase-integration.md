# kbase r2：EGL选择、电源边界与补丁重放

推荐产品使用Vulkan/OpenCL ICD；需要GLES的独立进程使用私有EGL/GLES/GBM前缀。
不选择GLVND shim，本轮不编写shim原型，也不改正式服务。以下均为离线证据，
不是当前板子的运行快照；HDR会话继续独占板子。

## 5.15产品到底用了什么

本轮读代码与已有日志，没有新SSH、串口或板端查询：

- `board/vim4-kvm-run:20–21`在5.15仅设私有Vulkan ICD，没有LD_PRELOAD、EGL前缀或EGL vendor注册。
- `tools/mali-runtime.py:60–75`仅安装libMali.so、mali.json、manifest.json；没有libEGL/GLES符号链接。
- 本地主仓的gst-plugin-vfmcap@a493740，`meson.build:28`依赖Vulkan，
  `src/amly-gpu.c:183,305`创建Vulkan device/instance，用于AMLY转换/缩放；这条产品路径不使用EGL。
  此处只读该现有checkout，不修改或推进其分支。
- `tools/gpu-compare.py:35–40`的vendor测试模式才显式预加载libMali。
  [三栈验收](bringup/2026-10-30-gpu-acceptance.md)里的厂商GLES3.2/622fps属于该探针，
  不是KVM产品应用的EGL调用证据。
- 既有`logs/gpu-parity-20261030/board-stack.txt`记录私有目录只有上述三个文件，
  manifest激活方式为VK_ICD_FILENAMES；[审查记录](bringup/2026-10-30-gpu-parity.md)
  已记系统EGL仍走Mesa。不能由“5.15有libmali”推断产品系统EGL已硬件加速。

因此，(a)是新增的隔离GLES运行方式，(c)最接近现有产品路径。未检查当前板上进程maps，
也不宣称所有第三方应用从未自行dlopen EGL。

## 三个方案比较

| 方案 | 适用性与代价 | 决定 |
|---|---|---|
| (a)专用前缀/直接链接 | EGL、GLES与GBM必须来自同一blob；逐进程LD_LIBRARY_PATH选择SONAME，或专用构建直接链接libMali。不能与同进程Mesa对象混用；RUNPATH/RPATH、dlopen绝对路径、插件及符号版本仍需验证。开发维护通常数小时，完整应用验证约1–2天 | GLES验收与明确需要GLES的独立进程使用 |
| (b)GLVND shim | 入口__egl_Main只是握手。还要提供平台识别、API支持查询、真实GL函数解析、扩展dispatch stub/index、display/device映射、错误归属及线程/context切换；不能把getDispatchAddress直接转发成blob函数地址。多vendor和跨线程行为容易出错，blob内部符号抢占/递归与GBM对象来源也需处理 | 不选；原型约2–4天、可维护集成与回归约1–2周以上，估计不含CTS |
| (c)仅VK/CL ICD | Vulkan与CL已有独立loader接口，不需要EGL适配。GLES能力仍须通过(a)验收；CL是否无预加载即可正确分派仍需设备测试，不能拿符号存在当已通过 | 产品默认策略；不降低GLES目标 |

(b)的依据为部署版本对应的[libglvnd v1.7.0 vendor ABI](https://raw.githubusercontent.com/NVIDIA/libglvnd/v1.7.0/include/glvnd/libeglabi.h)：
结构体同时定义EGL静态/动态与GL分派接口，并要求vendor为其支持的display扩展提供vendor-neutral分派函数。
据此判断“薄转发”不足以满足ABI，属于本轮工程推论。维护成本主要在生命周期和扩展合同，
不只是匹配ABI版本号。未来若需要同进程多vendor或不可控第三方应用，优先取得有授权且UK匹配的GLVND库。

`packaging/kbase/run.py`默认`--graphics icd`，不再预加载blob劫持EGL；
`--graphics direct`仅在临时目录建立libEGL.so.1、libGLESv2.so.2、libgbm.so.1和libMali.so链接，
用LD_LIBRARY_PATH选中它们，子进程退出清理。两种模式都校验已加载UK和blob哈希、隔离VK/CL ICD。
两者均未接入正式board启动器。不要用direct模式启动同时依赖Mesa/GLX的桌面进程。

离线解析探针`packaging/kbase/resolve-egl.c`只dlopen/dlsym/dladdr，不调用任何EGL/GL/GBM函数：

```sh
cc -Wall -Wextra -Werror packaging/kbase/resolve-egl.c -o resolve-egl -ldl
LD_LIBRARY_PATH=/PRIVATE/PREFIX ./resolve-egl /PRIVATE/libMali.so
```

现有ARM64 builder镜像、`--network none`、blob只读挂载下，五个入口
eglInitialize/eglGetProcAddress/eglMakeCurrent/glGetString/gbm_create_device均解析到同一blob，退出0。
移除私有前缀后解析到系统EGL/GLES/GBM，探针按预期退出1。
VM本体缺Wayland server运行库，首次RTLD_NOW失败，未伪造依赖；最终在已有完整builder中测试。
这只证明SONAME/符号解析，不证明eglInitialize、线程切换或真实GBM分配成功。

## 电源 parity 的精确范围

固定厂商V:K/platform/devicetree/mali_kbase_runtime_pm.c：

- :193–217，首次power_on启用runtime PM并get引用，执行mali_hw_init。
- :219–228，注释明确put_autosuspend会触发reset并影响T7工作；power_off仅记录日志。
- :231–259，runtime init另持引用，runtime_on/off为空实现。
- :269–301，系统resume恢复时钟树、取PM引用，并以PWR_OVERRIDE1决定是否重新初始化。
- :304–323，系统suspend显式put_sync、disable PM、disable clock。

7.3候选持域引用、core/bus保持开启，与**任务间空闲不释放外部域**的5.15策略方向一致，
可以作为该范围的parity候选；引用计数、固件SMC、实际空闲功耗仍未测，不能称硬件行为完全相同。
其POWER_MANAGEMENT_CALLBACKS=NULL，未复现厂商系统suspend/resume的板级寄存器/时钟恢复合同，
所以**系统睡眠不是已达成parity的项目**。保持VDD_GPU固定也不证明功耗等同。
本轮无PM门控代码变更；没有证据支持安全地减少域引用或在每次作业间复位。
未来优化须先证明空闲/唤醒无MMU/reset故障和像素错误，再测仪器功耗、并发视频、thermal上限及系统恢复。

## 按主题重放

删除聚合linux-7.3.patch和重复的DTS副本，唯一入口为packaging/kbase/series：

1. 0001-kernel-api.patch：Kbuild/内核API/兼容头，不改UK或T7电源策略。
2. 0002-t7-platform.patch：T7独立平台、core/bus职责、专用compatible及native manager依赖。
3. 0003-devfreq-thermal.patch：频率cooling，去掉未校准IPA模型。
4. 0004-dt-candidate.patch：单独应用于7.3内核树；不在模块series中。其内容与内核提交6cdf7ffd90387一致。

前三块按series应用到固定vendor archive后才能构建完整候选，不承诺中间每块单独可用。
第四块仅作审阅/重放，build.py继续从完整保留DTB复制后修改两个属性，避免改动默认内核树。
构建manifest分别记录各补丁SHA，DT patch另记SHA；升级时先处理API，再检查平台与调频，最后重放DT。

清理了新增对齐、回调参数名、长宏行、未使用宏参数及版本比较风格；保留明确的旧API别名。
`check-style.py KERNEL/scripts/checkpatch.pl`对所有四块执行strict原始检查，只接受：
API块的10条LINUX_VERSION_CODE、两个明确旧PageMovable名字的CAMELCASE，以及平台/DT各一条FILE_PATH_CHANGES。
其他诊断均失败；不设置全仓checkpatch忽略。版本判断是外部多版本兼容需要，
MAINTAINERS提示不要求向正式内核加入DDK。未经筛选合计0 error、12 warning、2 check；筛选门禁通过。
