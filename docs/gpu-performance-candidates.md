# G52 编译与短负载调频：离线候选

2026-10-30，承接[06df4d3 上板结果](bringup/2026-10-30-gpu-diagnosis-window.md)。
本轮未访问板子；未读取或修改 NPU 工作树、分支和配置。未 push，未改部署锁。
方针仍为**代理建议，待用户确认**：优先上游 Panfrost/Mesa，必要时保留 kbase/libmali 临时后备。
结论：通用展开候选已将原循环编译到显式展开版的相同统计；实际 FPS、功耗和广泛正确性待上板。
10ms 轮询是可回退的调频实验，不能承诺解决首个约2ms提交。

后续[上板窗口](bringup/2026-10-30-gpu-candidate-window.md)：候选原循环587.8fps，
10ms暖Vulkan约2.03ms但冷首发仍8.1ms；active空闲CPU约+0.107个百分点。
[循环/语料审查](gpu-loop-codegen.md)发现局部代码最多膨胀9.5倍，展开保留为绕过实验，暂不默认推广。

## 循环上限和后端证据

M 为 Mesa26.2.6 原始 tarball，SHA256 `b9436b3e1a8be76fbd4823dc884f90596ab7c6ac5e1867a305e66ffccfb31a92`。
源文件行号以下均指未打补丁版本；VM 原件 `~/build/gpu-runtime-26/mesa-26.2.6` 未修改。

| 位置 | 事实与含义 |
|---|---|
| M:src/panfrost/compiler/bifrost/bifrost_compile.h:140 | `max_unroll_iterations=32` 是驱动策略，不是 G52 ISA 的循环次数限制；该宏也供 Valhall 使用 |
| M:src/compiler/nir/nir_opt_loop_unroll.c:29、36、899–933 | 26 是历史 GLSL IR→NIR 成本换算启发式；普通自动展开同时要求 trip_count≤max_iter 和 instr_cost×trip_count≤max_iter×26。原设置等价于32次、832成本双上限；不是只有迭代数判断 |
| M:src/compiler/nir/nir_loop_analyze.c:79–125 | intrinsic/texture计1；展开后可常量折叠的ALU计0、mov/vec计0、可融合的乘加减免。已有成本模型可复用，无需新增探针识别 |
| M:src/compiler/nir/nir_opt_loop_unroll.c:908–921 | aggressive选项只在能隐藏load延迟或消除全部控制流等条件启用；另有soft-fp64设置。显式unroll/dont-unroll及既有force-unroll路径优先，候选不改变它们 |
| M:src/panfrost/compiler/bifrost/bifrost_compile.c:3700、3741 | if发条件分支、then退出jump；loop建header/break/continue、回跳。原探针反汇编有计数器IADD、ICMP、BRANCHZ及回跳；fract依赖链跨循环边界，不能只数循环体的ALU |
| M:src/panfrost/compiler/bifrost/bi_pressure_schedule.c:49–54、227、285；bifrost/bi_schedule.c:1993、2190 | 压力调度和clause调度按基本块进行，branch留在块尾；未形成跨迭代的软件流水。展开扩大常量传播、调度与打包范围，是目前有干预证据的修复方向 |
| M:src/panfrost/compiler/bifrost/bifrost_compile.c:4578–4598、3939–3995；bi_ra.c:1292–1327 | 压力调度→RA→clause调度；分配失败会spill。v7工作寄存器≤32可维持高线程数。原探针7/9个寄存器且零spill，不能归因为寄存器溢出 |
| M:src/freedreno/ir3/ir3_compiler.c:168 | freedreno也设32，复用同一NIR双上限；没有证据表明直接照搬其值适合G52 |
| M:src/gallium/drivers/v3d/v3d_screen.c:623；src/broadcom/vulkan/v3dv_pipeline.c:215 | v3d/v3dv设16。不同后端的成本/代码体积取舍不同；本候选不改它们，也不改Valhall的32 |

近期历史核对：M:docs/relnotes/26.0.0.rst:737、907记录单块循环识别修复及“展开能消除全部控制流”的NIR分析，
[26.2.0官方变更](https://docs.mesa3d.org/relnotes/26.2.0.html)继续修复loop-header支配关系和partial-unroll越界判断。
这些是循环分析/正确性演进，不能只提高阈值而跳过它们。
[26.2.6官方变更](https://docs.mesa3d.org/relnotes/26.2.6.html)包括
pan/bi helper分析TLS-store修复及NIR continue/phi/SSA修复；它们不是本次展开预算调整。
tarball的`.pick_status.json`对应commit分别为`45ea3ed8ce649d6b72d1843307a29d9cc3b7704e`、
`e775390f214f870219e60485e9c5c8620695ade3`、`69e0bf9e517784abef00ce1fe684400fbe2ad996`。
[25.0发布记录](https://docs.mesa3d.org/relnotes/25.0.0.html)已有Panfrost循环反向值传播修复，说明后端循环优化仍需正确性回归。
GitLab git/history访问返回403，cgit及镜像history也未取得；**未完成首次引入32的commit归属和开放MR查重**。
目前能证明的是上述固定发布源码及发布历史，不能声称“上游没有相关MR”或已经完成上游审阅。

## Mesa候选与离线对照

[0001补丁](../packaging/gpu/patches/0001-nir-bounded-bifrost-unroll.patch)新增内部编译选项
`max_unroll_cost`：0保持现有行为，非零独立限制普通自动展开后的NIR估算成本。
仅Bifrost v6/v7设最大256次、成本1024，避免单纯把32升256而连带将预算放大8倍。
1024仍比旧832提高约23%，是待语料调优的候选值，非已证明的通用最优值。
无shader文本、程序名、128次或产品探针特判；未知次数循环仍沿用NIR分析和原安全条件。
Valhall及其余驱动选项保持原值。

[0002测试](../packaging/gpu/patches/0002-nir-test-unroll-cost.patch)在Mesa自身nir_tests构造96次、有运行期输入和输出store的循环：
足够成本预算允许展开；相同迭代上限但小预算拒绝展开；验证NIR结构。
初始空循环用例会被视作展开后全常量、成本为0，不能检验成本边界，已改为有运行期操作的用例。
原作者和许可证保留。

同一ARM64 sealed builder `vim4-gpu-builder:26.2.6`，所有编译/测试/打包容器均`--network none`。
基线卷`vim4-gpu-runtime26`不改；独立卷`vim4-gpu-candidate26`复制基线源码/build后重编受影响对象和链接目标。
Mesa `meson test --print-errorlogs`：**51组通过、0失败、6组跳过**（生成的Rust绑定无测试）；新增两例通过。
干净builder源副本也验证两补丁按顺序`git apply`成功。

[compiler-compare.sh](../packaging/gpu/compiler-compare.sh)对基线/候选各编译原循环和显式展开，
使用drm-shim、`PAN_GPU_ID=0x7402`、禁用shader cache；分别保存ISA/verbose和shaderdb统计。
下表为**首个用户片段变体**；另一blend变体也记录，不能把后续内部blit shader混入。

| 编译输入 | 指令 / tuple / clause | 静态cycles估计 | 工作寄存器 | spill/fill | code bytes / loop数 |
|---|---:|---:|---:|---:|---:|
| 原26.2.6，原循环 | 27 / 20 / 6 | 0.750 | 7 | 0/0 | 416 / 1 |
| 原26.2.6，显式展开 | 402 / 268 / 35 | 11.083 | 6 | 0/0 | 3328 / 0 |
| 候选，原循环 | 402 / 268 / 35 | 11.083 | 6 | 0/0 | 3328 / 0 |
| 候选，显式展开 | 402 / 268 / 35 | 11.083 | 6 | 0/0 | 3328 / 0 |

blend变体：原循环63指令/9寄存器/752字节/1循环；其他三项均437指令/9寄存器/3664字节/0循环，全部零spill。
cycles是`bi_gather_stats`静态管线吞吐启发式（arith tuple/24等），**没有把循环体乘128，也不模拟分支延迟**；
因此0.750不能解释为比11.083更快。noop黑像素、退出1为预期；不引用其FPS，不证明硬件正确性。
新原循环与旧显式展开的统计一致，为消除该合成场景大部分差距提供了明确候选，但还未达到厂商原循环614fps。
旧硬件展开版约567fps，相对厂商原循环仍差约7.6%；更大的shader语料、编译时间和i-cache代价仍未测。

产物私有前缀`/opt/vim4-mesa-26.2.6-unroll1`，系统Mesa及旧私有前缀并存。
`package.py`按实际前缀写EGL/Vulkan/OpenCL ICD，ELF依赖闭包、相对RPATH和无builder动态路径检查通过。
归档内`manifest.json`逐文件SHA、`share/build-proof/`含补丁、依赖锁、测试、编译转储与选项。
最终归档SHA见本页末尾“产物”。无板端安装。

全新构建复现（在仓库根；新卷，不复用NPU目录）：

```sh
docker volume create vim4-gpu-unroll-rebuild
docker run --rm --network none -e GPU_VARIANT=bounded-unroll \
  -v "$PWD:/repo:ro" -v vim4-gpu-unroll-rebuild:/output \
  vim4-gpu-builder:26.2.6 bash /repo/packaging/gpu/build.sh
```

输出`/output/mesa-26.2.6-unroll1-arm64.tar.xz`；默认不传GPU_VARIANT仍构建原版。
编译对照需要两个stage前缀可见、分别在`/opt/对应名称`建symlink，然后执行：

```sh
bash /repo/packaging/gpu/compiler-compare.sh \
  /opt/vim4-mesa-26.2.6 /opt/vim4-mesa-26.2.6-unroll1 \
  /output/build/src/panfrost/drm-shim/libpanfrost_noop_drm_shim.so \
  /repo/build/gpu-diag-window/gpu-probe /output/compiler-proof-final
```

上游化：独立NIR成本选项及回归测试可讨论；驱动数值必须补shader-db/Piglit/dEQP、
编译时间、code-size/spill分布及v6/v7硬件测试。未实现跨迭代后端调度或分支消除，后者需要更大正确性覆盖。

## Panfrost冷启动升频

K为VM `~/src/linux-7.3-gpu`，分支`vim4-gpu-panfrost`；旧基线d2cd4c6。

| K源码 | 已核实行为 |
|---|---|
| drivers/gpu/drm/panfrost/panfrost_devfreq.c:90、228–234、record_busy函数 | 原50ms轮询，阈值45%、回落差5%；busy只记账，无提交预测或boost |
| drivers/gpu/drm/panfrost/panfrost_job.c:211、提交前record_busy路径 | runtime get后准备MMU/提交；busy记账处在调度锁路径，不能直接加入可睡眠OPP/clk切换 |
| drivers/gpu/drm/panthor/panthor_devfreq.c:127、288；lima/lima_devfreq.c:85、178 | 同样50ms及忙闲记账，并非普遍已有提交升频算法 |
| drivers/gpu/drm/msm/msm_gpu_devfreq.c:124、161、270–290、330–336 | 也50ms，但空闲超过采样窗口后active路径发2倍当前频率的PM QoS min请求，并延时撤销；另有worker和生命周期处理 |
| drivers/devfreq/devfreq.c:1805–1843；governor_simpleondemand.c | 已有polling_interval sysfs可控制轮询；不需要为纯策略参数新增板级DT binding |

内核候选 **4e239aec051a4**：只将Panfrost默认轮询50→10ms，保留阈值、既有OPP、thermal clamp、PM及电压。
不在spinlock下切时钟，不加新异步工作；单次小于10ms的cold任务仍可能在首次采样前完成。
不采用“无条件恢复最高频率”的捷径，以免绕过现有governor/QoS约束。
若短周期仍不足，下一候选才按msm思路在可睡眠的active/submit入口申请有界PM QoS boost，
需要明确request初始化、失败展开、suspend/remove取消、热上限及并发提交合同。

完整`Image dtbs modules`成功；Panfrost `W=1 C=2` sparse成功，GPU目录无新增诊断，
仅架构vdso已有`__kernel_getrandom`未声明警告。strict checkpatch **0 error/warning/check**；
现有`tools/testing/panfrost/test_pm.py`恢复顺序/失败夹具通过；`git diff --check`通过。
无DT改动，未重跑dtbs_check；没有修改主仓packaging/kernel-edge配置。
10ms使活跃期定时检查最多增加到原来的5倍，功耗/CPU代价未测；当前不是可直接宣称上游接受的默认值。

## 下一独占窗口：测量预算20分钟

另计锁空闲确认、5.15基线确认、一次性RAM启动/回退；先完成全部编译，采样时禁止并行编译。
固定同一工具、512×512 GBM/FBO、2秒预热、10秒稳态、读回另计；调试转储不进性能采样。
仅测试子进程注入ICD、实验PanVK和shader-cache环境；不改系统全局选择。

| 项目（顺序） | 上限 | 对照与判定 |
|---|---:|---|
| GLES原版/候选×原循环/显式展开，交错三轮 | 4分钟 | 每项timeout25秒；同核同服务状态。候选原循环应接近展开版，并核对像素；独立GPU timer各5秒且disjoint=0才使用 |
| Vulkan自由调频50/10ms、固定800MHz | 5分钟 | 同一候选核用已有polling_interval做50/10配对三轮，每进程三次预热＋20提交；外层90秒。锁频仅现有OPP、结束恢复；保存cold及submit/wait，不能把冷提交当吞吐 |
| 空闲→短burst→空闲，采样功耗/温度代理 | 3分钟 | 两种interval同样间隔/任务；记录trans_stat差、温区温度、CPU/proc stat、runtime状态。已审阅电源计数器若存在才读；温度/驻留不是瓦特，不写PWM/电压、不人为加热 |
| HDMI采集＋Wave5并行回归 | 5分钟 | 无GPU/候选原循环各60秒，现有脚本和帧/丢帧/编码计数，确认内容推进及无GPU/Wave5错误；不ptrace、不HID、不音频，保持已知服务状态 |
| 预留及设置恢复核对 | 3分钟 | 在finally恢复polling_interval、min/max、PM、profiling和服务；任一超时取消余项，保留失败证据 |

`gpu-diagnose.py --mode private --runtime /opt/vim4-mesa-26.2.6-unroll1`可复用现有隔离、fdinfo和trans_stat。
其200ms频率样本不能解析2ms升频；短负载主要看分段计时、trans_stat和独立受控50/10/800对照，
若需要毫秒轨迹再开低开销具名clock/devfreq tracepoint，单独诊断不混FPS。
最终回5.15默认并核对服务、UDC及启动文件哈希。候选核只有模块源码差异，
本轮Image/DTB仍与先前构建一致；上板应使用该完整构建匹配模块，不能仅换Image而误测旧panfrost.ko。

## HDR转换/缩放4K60最小产品方案（未实施）

复用现有`gst-plugin-vfmcap/src/amly-gpu.c`、`amly-gpu-scale.c`及像素对照工具，避免另造GPU框架。
先区分两条验收链：HDR保真AMLY→P010及缩放；HDR→SDR还需PQ/BT.2020到SDR的tone-map与色彩矩阵，
不能用数据布局转换宣称完成tone mapping。
已有5.15 Main10链见[产品记录](bringup/2026-10-26-hdr-gpu-pipeline.md)，不能直接算7.3通过。

当前阻挡：`amly-gpu.c:100–102`要求Vulkan≥1.1，而G52 PanVK已测设备仅1.0；
必须逐项审查实际所需API/扩展，确认可用core1.0＋KHR扩展替代后才放宽门槛，不能只改版本字符串。
`gst-plugin-venc/wave5/gstvim4wave5enc.c:156`当前只公布NV12，不能把现有7.3 Wave5验收当作P010/Main10支持。
还要核实7.3能否从现有采集节点交付保留10bit/PQ的buffer及元数据；仅有NV12八位输入无法恢复HDR精度。

最小先做离线录制AMLY/P010样本→私有PanVK导入连续dma-buf→同尺寸转换/双线性缩放→buffer校验，
先不接浏览器；重用双缓冲与输入退休fence，保持stride/offset/capacity、DMA所有权和异常后生命周期。
7.3用已验证的default_cma_region而非厂商codecmm；按4K P010约24.9MB/帧预算双输出约49.8MB，
输入、临时纹理、采集池及Wave5另计，不能只看两个输出。随后接VDIN与Wave5 NV12 SDR链，
Main10/P010需单独驱动/插件能力项。4K60要求持续每帧≤16.67ms且队列不增长；
必须报告GPU转换p95/p99、捕获/编码并发帧推进和像素/色彩，不能用24.9MB写入探针代替。

工作量估计（工程日）：扩展/API和buffer合同审查1–2日；复用shader与离线像素/时间基准2–3日；
采集同步、池预算及NV12产品接入2–4日；HDR→SDR色彩/缩放验证2–3日；硬件窗口与回归1–2日。
离线转换及既有NV12接入约6–11日，HDR→SDR色彩验证另加2–3日；
若缺10bit采集或Wave5 Main10内核支持，保真HDR另估5–10日，且需固件能力证据。
以上是方案与估算，未改视频插件/驱动、未承诺4K60可达。

## 产物

内核：VM `~/build/gpu-panfrost-20261030`，分支`vim4-gpu-panfrost@4e239aec051a4`。
Image SHA256 `5b850638dfa74de0233431a14ddd547e39caec895d1451620ac9c8d389ee79f7`；
VIM4 DTB `9e78f8657bfd2f57029c09f3d43e6ec48ecb55cfcfa81e7e74927beb63fd4308`；
panfrost.ko `442898fdef30c53fcf180f751a2be3234f2f9aa0b780c5371d904f722c565687`。
构建及sparse日志VM `~/build/gpu-poll10-{build,sparse}.log`。
Mesa归档`mesa-26.2.6-unroll1-arm64.tar.xz`保留在Docker卷`vim4-gpu-candidate26:/output`，
本机副本`build/gpu-candidates/`；SHA256
`c75269107304cf21a87100c276d076cac2f48fc4ddadfe305775994f870f0e71`。
归档含51个ELF，私有ICD前缀和依赖闭包检查通过；ICD JSON的loader最高版本不等于G52设备API版本。
主仓unittest：309项、7项跳过、无失败；shell语法及任务文件diff检查通过。
