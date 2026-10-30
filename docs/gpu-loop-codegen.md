# Bifrost循环代码生成与展开语料代价

2026-10-30，配套[候选上板窗口](bringup/2026-10-30-gpu-candidate-window.md)。
结论：展开是有效绕过，**不是已经修复循环代码生成**。保留实验候选，不建议直接默认推广或以当前阈值提交上游。
后续优先改善不变量放置与受控循环的分支/clause布局。方针仍为**代理建议，待用户确认**。

后续[保留循环候选](gpu-loop-candidates.md)已分开实现NIR GCM、JUMP前向清理、受保护的一致控制流回边优化，
并在GPU分支实现冷恢复QoS boost。展开默认关闭；这些仍是离线候选，不覆盖本页已有硬件测量边界。

## 27条静态指令为何不能与402条直接比较

固定Mesa26.2.6源记为M；基线及候选、原始SHA、静态统计见[离线候选](gpu-performance-candidates.md)。
本轮未取得厂商ISA，不能证明厂商具体用了哪一种循环布局。
厂商原循环GPU timer1.404ms、展开1.515ms，证明高效循环实现有空间，反驳“展开必然更优”。
Mesa的4.133/1.584ms为上一窗口同条件有效timer；本轮实测候选原循环587.8fps，
只证实通用展开绕过生效，未提供新后端实现或厂商机器码等价证明。

原版首个片段变体反汇编（日志`compiler-proof-final/baseline-loop-verbose.log`）的热路径：

```text
clause_6:             # 每次迭代
  FMA r2, 0.01, 0    # p.y*0.01，重复计算不变量
  FMA r1, 1.01, t0
  FROUND.rtn t0      # fract分解
  IADD r3, 1
  FADD r1, -t0
  ICMP.s32.ge r3, 128
  BRANCHZ.i16.eq ... clause_13
clause_11: JUMP clause_15  # 结束
clause_13: JUMP clause_6   # 继续：独立的回跳clause
```

clause_6有5个tuple，继续路径另有1个jump tuple；循环体128次、回跳127次、退出1次，
热区约768个动态tuple，尚未计首尾。而显式展开整个shader仅268个tuple，且不变量共享。
粗略比值约2.87，与约2.61倍GPU区间差相容；**这不是精确cycle模型或各因素的百分比分解**。
27条是静态指令数，循环动态执行量远大于27；静态cycles=0.75同样没有乘入循环次数。
工作寄存器7/9且零spill，不能归因溢出；不是仅增加寄存器数就能修复。

## 已定位的改进点及正确性门槛

| 排序 | 源码证据（M下） | 改进方向与边界 |
|---|---|---|
| 1 不变量重复计算 | src/panfrost/compiler/bifrost/bifrost_nir.c:374–381的move_all没有nir_move_alu，也没有调用nir_opt_gcm；src/compiler/nir/nir_opt_move.c:29只在同块接近使用点移动；nir_opt_sink.c:63–119的ALU移动受选项与压力规则限制 | 评估在后端lowering前使用nir_opt_gcm的循环外放置能力（nir_opt_gcm.c:602–606、896），或局部LICM。先限制纯ALU、可安全推测运算，禁止错误移动带副作用/导数/内存/不满足执行掩码条件的操作；测live-range/寄存器和code-size，不能全局打开所有hoist选项便称修复 |
| 2 回跳和退出布局 | src/panfrost/compiler/bifrost/bifrost_compile.c:3700、3741生成if/loop块与jump；bi_opt_control_flow.c:115–135遇已见successor，即后向跳转，明确拒绝simple-block折叠 | 改进规范化单出口、uniform迭代循环的layout与条件方向，争取热路径直接回header，退出fallthrough；必须建立reconvergence/执行掩码证明，测试divergent break/continue、嵌套循环和helper invocation |
| 3 归纳/比较成本 | 原ISA每次IADD＋ICMP＋BRANCHZ，与fract依赖链相邻；bifrost/ISA.xml:3162有BRANCH.s32及widen/encoding限制 | 评估合法比较分支融合、归纳变量范围收窄和条件反向，消除bool中间值；不能假定所有i32比较都能直接替换为硬件branch。验证符号、溢出、精确trip count及打包限制 |
| 4 clause与调度 | bifrost/bi_schedule.c:1993、2190按block调度，bi_pressure_schedule.c:227、285亦按block；bifrost_compile.c:4578–4598在RA后做control-flow优化和clause调度 | 先修控制流形状，再测branch尾tuple、跨clause转发/依赖和打包空洞。完整跨迭代软件流水需处理循环携带依赖，工程量大，当前没有实现 |

`bi_opt_control_flow.c:115–121`明确引用
[MR36021的reconvergence讨论](https://gitlab.freedesktop.org/mesa/mesa/-/merge_requests/36021#note_3020690)。
这解释了为何看似可删的单jump块被保留：它是已知正确性保护，不是随手漏跑DCE。
该讨论页仍无法直接读取，本结论依据本地26.2.6源码注释，未声称审阅了整个MR。
不能简单删除`!succ_seen`保护。需要最小MIR/NIR回归用例和Bifrost硬件语义验证后才实现新折叠规则。

因此目前确定的是**冗余不变量运算＋受保护的额外控制流＋局部调度结构**；
分支延迟、clause边界与I-cache分别占多少尚未取得独立干预/perfcnt证据，不编造“唯一根因”比例。
建议下一离线候选先做有边界的纯ALU循环外放置，保留循环；再独立做循环布局。
两个候选分别对照原版、展开版，不把它们混为一次改动，否则无法归因。

## shader-db更大语料对照

本轮使用Mesa官方shader-db归档，源URL
`https://gitlab.freedesktop.org/mesa/shader-db/-/archive/main/shader-db-main.tar.gz`，
SHA256 `651208a606fa0af28c970f287762bfc57b6991cf9f88cc86d4f782187306d5c2`；
同窗读取main为`6ec450899fb1cb9d6d4829bbf864288c4e7a5dbb`。
随后取得固定commit归档SHA `c32024f380407a9aec409cabfbd52bfc97f33d8952fa264a525f464d5c486f99`，
逐文件比较4263个shader及run.c/Makefile/COPYING共4266项，内容与实测输入完全相同。
复现脚本已改用该固定commit与SHA，[输入锁](../packaging/gpu/corpus.lock.json)记录语料及deb下载URL，避免依赖移动的main。
首个下载因20秒限制截断，已舍弃；最终完整归档通过tar遍历与解包，保留于`build/gpu-candidates/`。
不是以自造探针代替语料，也没有将库内所有shader都宣称为GLES CTS。

归档提供4263个shader_test文件；真实G52 API限制下，3744个文件产生11123个可配对编译变体，
其余文件没有纳入机器码统计，不将它们计为通过。基线/候选共同键完全一致，没有只在一侧出现的变体。
使用shader-db自己的run，单线程、同一drm-shim、PAN_GPU_ID=0x7402、禁用cache、precompile；
不强制GLSL版本越过设备能力。两个run均退出0，stderr无ERROR/SKIP消息；这不是CTS运行正确性验收。

| 共同变体合计 | 原26.2.6 | unroll1 | 差异 |
|---|---:|---:|---:|
| code bytes | 6,820,512 | 7,075,488 | +254,976，+3.74% |
| 静态指令 | 567,027 | 589,623 | +22,596，+3.99% |
| 静态loop节点 | 178 | 138 | -40 |
| spill / fill | 20 / 41 | 20 / 41 | 总数不变 |
| 有统计变化的变体 | — | 28 / 11,123 | 27个Skia片段＋1个volumetric fog片段 |

变化子集代码157,504→412,480字节，约2.62倍，不能只用全库平均3.74%掩盖局部膨胀。
例如Skia/49-23片段448→4256字节（9.5倍）；Skia/1768为16576→29552字节。
Skia/2047寄存器使用数31→33，但shaderdb的threads原本就是1、之后仍1，**不能由此宣称新增occupancy减半**；
仍提示live-range压力需逐shader审查。无新增spill不等于没有I-cache/编译时间/运行性能回退。
本轮没有硬件语料执行、I-cache计数或严格编译时间对照；不宣称这些28项都加速。

这支持把1024成本/256次阈值留为实验，不作为默认上游补丁结论。若继续展开路线，
应增加展开后代码增长上限、嵌套循环总成本/热度和寄存器压力约束，而非仅调大循环次数。
同时优先循环本身优化，以保留厂商原循环比展开更快所体现的机会。

## 可复现检查

[corpus-check.sh](../packaging/gpu/corpus-check.sh)校验语料及libepoxy两包SHA，
将额外依赖解到私有目录，不修改sealed builder或运行时包；`--network none`编译run并对照。
libepoxy-dev/libepoxy0版本1.5.10-1build1，取自builder既有Ubuntu20261012 snapshot；
SHA分别为`976557dd0a474f859db69f092c15ae83c366c7a42400be45ccf7921b314c257f`和
`103381283fcdbb4af06c155568c1e945f0a647d75f2522e0c2418ebb70b855ba`。
原shader-db run.c有既有asprintf返回值编译warning，未修改其作者/许可证。

输入位于本机`build/gpu-candidates/`，额外deb在其corpus-deps目录；容器可复用候选卷：

```sh
# 联网封存阶段（在仓库根，独立输入目录）：
python3 packaging/ubuntu/fetch.py packaging/gpu/corpus.lock.json build/gpu-corpus-inputs
mkdir -p build/gpu-corpus-inputs/corpus-deps
mv build/gpu-corpus-inputs/libepoxy*.deb build/gpu-corpus-inputs/corpus-deps/
# 下列命令在--network none容器内；本轮已封存输入在build/gpu-candidates：
bash /repo/packaging/gpu/corpus-check.sh \
 /opt/vim4-mesa-26.2.6 /opt/vim4-mesa-26.2.6-unroll1 \
 /output/build/src/panfrost/drm-shim/libpanfrost_noop_drm_shim.so \
 /repo/build/gpu-candidates /output/corpus
python3 /repo/packaging/gpu/corpus-report.py \
 /output/corpus/baseline.out /output/corpus/candidate.out
```

两个/opt前缀先分别指向stage-baseline与stage；原始命令/日志位于`build/gpu-candidates/corpus*`，
完整容器结果在`vim4-gpu-candidate26:/output/corpus`。
report仅使用stdout带文件名的统计，避免stderr重复计数；键含路径、阶段及同阶段变体序号，
只比较共同键并报告缺失覆盖，不能把编译缺失误判为体积变小。对应真实边界已加入主仓unittest。
主仓全量unittest：311项、7项跳过、无失败；shell语法及任务文件diff检查通过。
