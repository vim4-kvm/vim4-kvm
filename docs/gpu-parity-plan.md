# VIM4 GPU 离线候选与验收方案

本轮差距、固定源码及逐项 file:line 见
[2026-10-30 GPU 审查](bringup/2026-10-30-gpu-parity.md)。目标仍是7.x功能与性能不低于
厂商5.15；下列候选尚未达到这一验收条件，不能据离线构建改正式部署锁。

2026-10-30[三栈上板验收](bringup/2026-10-30-gpu-acceptance.md)：默认GPU cooling绑定、
五档调频、runtime恢复和4K60 Wave5并发窗口已取得限定通过证据；未人为触发过温降频。
同一GBM/FBO shader三轮平均：厂商622.659fps、系统Mesa231.714fps、私有Mesa233.730fps。
私有GLES仍3.1、Vulkan设备仅1.0.354；CL设备3.0但OpenCL C1.2，完整clpeak三轮map阶段超时。
严格功能/性能目标未达成。优先定位G52编译器性能、API能力及CL map边界；固定电压与厂商一致，非缺口。
方针“上游实现、kbase/libmali必要时临时后备”**用户已于 2026-10-30 确认**。
当前优先[产品HDR转换/缩放](gpu-hdr-pipeline.md)，编译器暂停：GCM默认、完整系列显式选项；可上游补丁仅本地整理，不对外发送。
后续[离线性能复核](gpu-performance-diagnosis.md)修正测量边界：GLES旧值含末次回读且无预热，
Vulkan4.25倍为冷提交主机等待口径，clpeak120秒是全程序预算；尚不能直接归因GPU执行效率或map死锁。

[诊断实测](bringup/2026-10-30-gpu-diagnosis-window.md)已将该GLES场景的约93% GPU区间差归于循环编译；
[离线候选](gpu-performance-candidates.md)实现通用成本约束展开和10ms devfreq采样，尚待下一独占窗口确认。
私有Mesa候选另用`/opt/vim4-mesa-26.2.6-unroll1`，默认部署与原版保持并存。

[候选配对窗口](bringup/2026-10-30-gpu-candidate-window.md)已验证约2.50倍GLES绕过收益与10ms暖提交收益，
冷首发仍未改善。下一优先级是[循环代码生成本身](gpu-loop-codegen.md)，不将展开作为已完成的后端修复；
大语料局部代码增长最高9.5倍，暂不默认推广。10ms默认化仍需更长功耗/后台负载回归。

最新[保留循环离线候选](gpu-loop-candidates.md)：GCM及分阶段控制流清理保持178个语料loop，
完整系列总代码体积约-0.533%、spill/fill不变；冷恢复内核候选e99220d902834。
新builder默认关闭实验展开，默认部署锁不变，等待≤20分钟独占窗口。

[保留循环候选实测](bringup/2026-10-30-gpu-loop-window.md)：完整系列错误像素并触发GPU timeout，不可推广；
仅GCM约273.2fps，对照厂商612.7fps，未追平。QoS恢复boost冷首发约8.12→4.90ms，
thermal/用户频率上限仍有效；后续重点为控制流故障隔离与power_on之前的频率时序。

最新[离线修复与下窗门禁](gpu-loop-repair.md)：已定位同块分支偏移错误导致计数器反复初始化，
0006修复有旧代码失败的Mesa单元回归；默认仍只GCM，完整修复系列尚未硬件验收。
内核4ccae3570a97e试验每阶段最多10µs快轮询再回退睡眠；不改上电顺序/OPP/电压，
power_on内部2.42ms仍未分段实测。下一窗口先全帧相等与GPU错误零增量，再计FPS与冷暖提交。

## 内核候选

VM `~/src/linux-7.3-gpu`，分支 `vim4-gpu-panfrost`，基于`213f271505411`。
只把95°C GPU被动降频map从pm-test移到默认VIM4 DTS，pm-test保留CPU idle试验。
公共SoC和其他板型不变；所有继承VIM4的profile获得GPU thermal绑定。
不更改已存在的五档频点、供电、50ms autosuspend或PWM电压模型。
`amlogic_data`没有GPU_PM_RT标志，当前不能把runtime suspended等同外部时钟已关。
T7时钟/复位门控正常化仍需独立候选和恢复证据；本轮不改所有Amlogic型号共享的PM策略。
厂商T7 runtime回调明确因reset影响GPU工作而省略put_autosuspend，不能仅凭上游标志存在就打开。

主仓`packaging/kernel-edge/`配置文件**无需GPU改动**：现有uhd1.config已有
`CONFIG_DRM_PANFROST=m`、`CONFIG_PM_DEVFREQ=y`、
`CONFIG_DEVFREQ_GOV_SIMPLE_ONDEMAND=y`、`CONFIG_DEVFREQ_THERMAL=y`、
`CONFIG_THERMAL_OF=y`、`CONFIG_THERMAL_GOV_STEP_WISE=y`、
`CONFIG_PM_OPP=y`、`CONFIG_PM_GENERIC_DOMAINS=y`。
profiling是运行时选择，不因有fdinfo便默认常开；无需增加虚构的GPU perf PMU配置。
电压策略与厂商一致：固定电压，非缺口；不再追求逐频电压表。
闭源固件是否另行调压未证，不从Linux只切频的证据推断固件行为。

构建复制uhd1.config到私有O=目录；不经要求正式锁匹配的build.sh冒充发布构建：

```sh
cd ~/src/linux-7.3-gpu
out=$HOME/build/gpu-panfrost-20261030
# .config已由主仓uhd1.config复制；首次复现须另选新的空out目录。
make O="$out" ARCH=arm64 olddefconfig
make O="$out" ARCH=arm64 -j4 Image dtbs modules
git diff 213f271505411 | scripts/checkpatch.pl --strict --no-tree -
```

schema独立目录`~/build/gpu-schema-20261030`，使用ARM64 defconfig，
`PATH=$HOME/build/dt-schema-venv/bin:$PATH make ... dtbs_check`
并指定`DT_SCHEMA_FILES='gpu/arm,mali-bifrost.yaml:thermal/thermal-zones.yaml:opp/opp-v2.yaml:regulator/pwm-regulator.yaml'`。
这是GPU/thermal/OPP/regulator定向schema遍历，不称为所有binding全板零诊断。
W=1/sparse另用`~/build/gpu-sparse-20261030`，复制同一配置，先modules_prepare，
再执行`make ... W=1 C=2 CHECK=$HOME/build/gpu-check-env/sparse-src/sparse -j2 drivers/gpu/drm/panfrost/`。
Ubuntu sparse0.6.4被内核checker-valid拒绝，不能把退出0当已检查；最终使用
`v0.6.5-rc1@37156835e3d725b6d750f000be33ba3814bb2310`，独立源码构建。

最终检查状态、提交及产物哈希在本文件末尾登记。日志均留在VM的`~/build/gpu-*.log`。
本次olddefconfig输出SHA256为`4f8f254d60a37b7cdd7842a1ea7e40f0b036491185efa056179de15628e8dfa6`。
与并行NPU任务更新后的主仓配置相比，删除本基线不认识的AMLOGIC_ADLA_COMPAT，
补入原源码默认值VIDEO_MESON_T7_DOS=m、四个T7音频选项=n及U_SERIAL_CONSOLE=n；
这些是版本/默认项差异，不是本轮要求修改主仓的GPU配置。

## 首轮用户态方案（由第二轮实现替代）

以下保留首轮25.2.8探测的历史结果；当前私有运行时实现见
[第二轮构建记录](bringup/2026-10-30-gpu-runtime.md)。系统25.2.8保留作对照。

优先保持安装版本25.2.8进行依赖/行为对照，不凭“升级最新版”许诺GLES3.2。
本轮已下载并校验官方25.2.8 tarball、检查PanVK v7实验门控和AFRC版本判断；
VM Meson1.7.2配置探测在缺少rustc处失败，**没有生成Mesa库或通过用户态完整构建**。
日志`~/build/gpu-userspace/configure.log`。这不改变内核候选的构建结论。

按现有`packaging/ubuntu/Dockerfile`的固定Ubuntu24.04 digest、
`20261012T000000Z`快照和`downloads.lock.json`/`fetch.py`方式扩展独立GPU builder，
不修改本轮禁止触碰的kernel-edge配置。输入锁应包含：

| 输入 | 固定要求 |
|---|---|
| Mesa | `https://archive.mesa3d.org/mesa-25.2.8.tar.xz`；SHA256 `097842f3e49d996868b38688db87b006f7d4541e93ce86d2f341d8b3e7be7c93` |
| OS/原生工具链 | 复用现有Dockerfile的Ubuntu digest/快照；构建ARM64，导出dpkg-query -W完整清单 |
| Meson/Ninja/Python | Meson1.7.2，下载wheel及其SHA入锁；Ninja/Python来自同一Ubuntu快照；Python需mako、yaml、packaging |
| Rust/bindgen | 复用现有锁定Rust工具链（须>=1.78）；bindgen-cli0.71.1，cargo --locked，预取crate及Cargo.lock，离线阶段cargo --offline |
| LLVM/OpenCL | 同快照llvm-19-dev、libclang-19-dev、libclc-19-dev、libllvmspirvlib-19-dev、spirv-tools、spirv-headers，避免LLVM与translator跨major混用 |
| native headers | 同快照libdrm-dev、libglvnd-dev、libexpat1-dev、libelf-dev、libzstd-dev、zlib1g-dev、libwayland-dev、wayland-protocols、libudev-dev、libxcb-randr0-dev、libxrandr-dev、bison、flex、pkg-config |

准备依赖镜像是联网阶段，封存镜像ID、包清单、wheel/crate哈希后才进行`--network none`
构建。当前主仓builder尚无LLVM/translator/bindgen且Meson为1.3.2，不能直接声称可用。
上述是待补齐的依赖配方，未验证整套snapshot依赖解析；严格二进制可复现还需双次独立构建比较。

在具备锁定依赖的ARM64容器中执行（已核对25.2.8的选项）：

```sh
export LLVM_CONFIG=llvm-config-19 SOURCE_DATE_EPOCH=1764806400
meson setup build mesa-25.2.8 --prefix=/opt/vim4-mesa-25.2.8 --libdir=lib \
  --buildtype=release -Dgallium-drivers=panfrost -Dvulkan-drivers=panfrost \
  -Dgallium-rusticl=true -Dllvm=enabled -Dplatforms=wayland \
  -Degl=enabled -Dgbm=enabled -Dgles2=enabled -Dglx=disabled -Dglvnd=enabled
meson compile -C build -j4
meson test -C build --print-errorlogs
DESTDIR="$PWD/stage" meson install -C build
dpkg-query -W > stage/build-packages.txt
```

若构建器的libclc目标文件安装于版本目录，须将该目录随私有运行时封存并记录，
不能只拷libRusticlOpenCL.so而漏LLVM/translator/libclc。对stage中的每个ELF执行
readelf/ldd依赖检查，校验ICD library_path指向私有前缀，归档源码哈希、
Meson introspect配置、编译器/包清单和每文件SHA256；压缩包不得包含系统/usr库替换项。
离线Meson测试不等于GPU CTS或API设备探测通过。

运行选择也保留进程隔离：EGL用`__EGL_VENDOR_LIBRARY_FILENAMES`指私有Mesa vendor JSON、
`LIBGL_DRIVERS_PATH`指私有DRI目录，必要时仅该进程设置私有库搜索路径；
Vulkan用`VK_DRIVER_FILES`指私有PanVK JSON，G52实验窗口另显式设
`PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1`；OpenCL用`OCL_ICD_VENDORS`指私有ICD目录，
`RUSTICL_ENABLE=panfrost`。不得全局开启实验开关或改EGL/GLES链接。
正式启动器须在验证完成后扩展7.3分支；现有`unset VK_ICD_FILENAMES`不能自动激活私有PanVK。
G52 PanVK实验成熟度和GLES3.2缺口都不能由这个打包方案消除。

## 上板验证清单（本轮未执行）

先预约独占窗口，记录5.15/7.3 Image、DTB、完整模块build ID和用户态哈希。
当前默认5.15保持不变；7.3只通过一次性RAM sysboot候选选择，正常重启回5.15。
候选需基于当前保留DTB的完整profile，不能用通用VIM4 DTB覆盖现行采集/USB/MAC配置。
每项由脚本设置timeout（TERM后最多5秒KILL），总上限不超过600秒；单项结束恢复governor、
频率限制和profiling，保存原始计数器。全程不发HID、不开声音；Mac mini M6仅作既定HDMI源。

| 单项上限 | 5.15基线与7.3候选要记录 | 判定与限制 |
|---|---|---|
| 2分钟 | GPU ID、shader/L2 masks、features/issues；EGL/GLES设备版本/extensions、Vulkan device properties、CL platform/device版本/extensions | 真实GPU探测，拒绝llvmpipe/lavapipe；CL符号版本不代替clGetDeviceInfo。先确认两侧共同API与负载 |
| 5分钟 | 复用logs/gpu-devfreq/gles-load.c离屏回读或固定glmark2，双方相同pbuffer实际尺寸、shader、迭代数、CPU亲和、温度、频率/电压状态 | 各三轮：吞吐、帧时间p50/p95/p99、进程/整机CPU、错误和像素；实际surface不同则作废。保留原始值，不以异后端旧分数相除 |
| 5分钟 | vkmark或仓库mali-dma-probe同一shader/尺寸，CL用clpeak相同数据量并保存能力扩展 | 先证明PanVK import/external memory能力，缺扩展记失败；实验开关记录入结果。CL版本可选能力逐项比较，不能以3.0数字替代2.x功能 |
| 5分钟 | userspace governor五档升降各20秒，读取clk_summary与OPP/devfreq驻留；已审核的regulator_summary/PWM具名状态 | 与厂商一致采用固定电压，非缺口；不写PWM/猜电压。model µV不是实测，闭源固件是否另行调压未证 |
| 5分钟 | 正常负载温区、cooling type/max_state/cur_state、GPU最大频率；有THERMAL_EMULATION临时配置的专用候选可做95°C/回落软件注入 | 不堵风扇、不人为烤到临界温度；温度未达trip则降频未验。软件注入仅证明绑定/恢复，不证明真实传感器闭环；生产config无需开emulation |
| 3分钟 | 渲染→空闲→渲染，runtime_status/active_time/suspended_time、genpd和时钟状态、实际功耗仪读数（若有） | 空闲应autosuspend且恢复像素正确，无timeout/MMU fault；cur_freq在挂起时是缓存，不证明关钟功耗。无功耗仪不宣称功耗追平 |
| 8分钟 | 固定HDMI采集/Wave5并行GPU导入/处理，脚本记录帧序、回读、DMA/CMA驻留、编码吞吐/丢帧、GPU fence与kernel errors | 与无GPU并发基线同场景比较；逐帧输入退休再复用，结果应无新增损坏/停流/池泄漏；不用截图、高频ptrace或HID触发场景 |

每个5.15/7.3配对项应相邻测量并记录热状态和后台服务，构建在测量前结束。
若不能在相同API/格式/分辨率运行，报告能力阻塞，不降格为“性能已追平”。
允许测量噪声的数值界限须在窗口前固定；目标吞吐不低于5.15，尾延迟/CPU/功耗无回退。

## 风险与需要决策的事项

- 固定电压与厂商Linux一致，非缺口，不再追求电压表；闭源固件是否另行调压未证。功耗对照无需以新增调压功能为前提。
- 上游G52 GLES3.1低于厂商3.2，PanVK仍实验。需决定是否投入G52上游API/CTS补齐；实验PanVK只能进入隔离验证候选，不能作为现有严格产品目标的完成证明。
- OpenCL厂商实际device版本/扩展、双方CTS、GPU/视频DMA格式及同步、真实热降频和功耗均未离线证明。后续是否安排一次性启动独占窗口由用户确定，本轮不部署。

## 本轮验证结果

- 内核提交：`vim4-gpu-panfrost@d2cd4c6c981e9f1722adca53c36e77e2b3c91266`，两份DTS改动；未推送。
- `checkpatch --strict --no-tree`：0 error、0 warning、0 check，19行patch；`git diff --check`通过。
- `dtbs_check`：ARM64 defconfig遍历、上述四组schema，退出0。12个T7 DTB无诊断；其他12个板型14条thermal cooling-map命名诊断，不能称全树零诊断。
- 生成的11个VIM4 DTB用fdtget核对，GPU cooling-device均指向本DT的GPU phandle，两个边界均为THERMAL_NO_LIMIT。
- `W=1 C=2`：Panfrost的13个C文件均有CHECK记录，GPU目录无诊断；准备阶段既有`arch/arm64/kernel/vdso/vgetrandom.c:5`有`__kernel_getrandom`未预先声明的sparse警告。
- Mesa25.2.8源码SHA256通过；Meson配置因VM缺rustc退出1，用户态包未构建/安装。
- 主仓全套离线测试（含已暂存新增文档）296项、7项跳过、无失败。
- 完整`Image dtbs modules`退出0，2337个模块，编译日志无warning/error；未执行上板验证。

产物在VM `~/build/gpu-panfrost-20261030`，`gpu-manifest.json`记录源码tree、
build ID、全部11个VIM4 DTB哈希；`modules.sha256`记录完整模块集，
`gpu-cooling.patch`可供离线审阅。release仍为`7.3.0-vim4kvm-uhd1+`，不能仅凭release匹配部署。

| 产物 | SHA256 / build ID |
|---|---|
| vmlinux build ID | `f1fceb5f1387724fc11a40fa9ce28ef69c4d8ae4` |
| Image | `17889f0bbc2260ac68cee95e1a0406a0db62a28c9589ceb464c946cf4d377d58` |
| display-m0 DTB | `e31c0a2a58e11942cc6941dc7bc87a8a54c9c0641fb61a35c07f3fcc48dd3bef` |
| panfrost.ko | `9b0b715de426d08a6093a1f9c52acedc7d6046780800f1f1be7fd42100006665` |
| modules.sha256 | `a1a15d08293bc83b284a486bce8b72c8af217a23d13dd814bbfdeb98f112465f` |

主仓只提交审查、方案和两个文档入口；保留并行NPU任务提交。正式内核分支、部署锁、
`packaging/kernel-edge/`配置和板上启动项均未由本轮修改。
