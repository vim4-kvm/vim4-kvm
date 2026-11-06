# 2026-11-06：T7 HEVC 固件身份与 secure swap 缺口

**存在明确的主机选择差异**：f21dfc47请求非swap的h265_mmu；按已归档T7包4.129及
厂商默认参数，decoder_v4l会先请求hevc_mmu_swap，失败才回退非swap。
新候选`2a622cf6204e6c3f67678cadcc6dbe5c58a074f4`补选择、回退、SCRATCH8保存恢复和读回。
未上板，不能据此认定已经解释[r71的08前停滞](2026-11-06-hevc-pre08-analysis.md)。

## 当前究竟加载了什么

要区分文件包身份、SMC请求的variant与安全世界实际驻留代码。只有前两项可离线核对。

| 对象 | 证据及边界 |
|---|---|
| 来源文件包 | 板上已有`/lib/firmware/video/video_ucode.bin`，NEWP包，389696字节，SHA256 `59e242bd63d6372d6462d2a2d6815e7bdea1a2cd12cd29fac093f38e73294e4b`。原始目录解析见[硬件审计](2026-10-22-vdec-hardware-audit.md#板上-video_ucodebin-的只读目录)；r71的validation-plan.json仍将此路径锁为同一SHA。没有记录证明本轮发生替换 |
| 包版本 | package header version=4（主版本0、次版本4）、submit_count=129、total=15；CODE目录统一版本`v0.4.81.If60661d.7f05035`、commit `7f05035`。字符串81是十六进制129，不能当作另一版提交号。包的Debian发行包名/版本未在可用证据中保留，本轮未查询板子 |
| 非swap条目 | 包目录名`t7_hevc_mmu.bin`，声明data_size=36864字节（9000），对应format `hevc_mmu`、请求别名`h265_mmu`、VIDEO_DEC_HEVC_MMU=17 |
| swap条目 | 包目录名`t7_hevc_mmu_swap.bin`，声明data_size=40960字节（a000），对应format/request名`hevc_mmu_swap`、VIDEO_DEC_HEVC_MMU_SWAP=TAG('2','6','5','S')=32363553 |
| f21实际请求 | `aml_vdec_hw.c:1354`在核心reset后发`SMC 0xb200000f(index=17, core=0, swap=0)`，r71日志a0=0。这明确是非swap请求，并没有请求hevc_mmu_swap。DMC配置为另一个调用`0xb200000e(4,0,0)`，不要与固件core选择混淆 |
| 实际执行blob | 主线驱动未request_firmware该文件，而是复用已预装的TEE固件。历史预装服务/TA证据见[安全微码审计](2026-10-23-vdec-timeout-audit.md)。SMC只返回a0，不返回版本、字节数、装载地址或哈希；本轮无法证明驻留代码逐字节等于哪个CODE条目，也无法给出可验证的单blob SHA |

15个包目录项的length均512，仅有CODE元数据；后部是尚未在本任务解析的377920字节。
目录声明data_size不是可直接切片的明文长度。不能对512字节头取哈希后冒称blob哈希，
也不能用整个NEWP包SHA代替单条微码SHA。原始包副本在当前可用工作区未找到；这里引用
既有解析记录及r71受保护文件哈希，不宣称本轮重新解析过二进制。

## 厂商实际分支计算

以下`v4l:`指`common_drivers/drivers/media_modules/frame_provider/decoder_v4l/h265/vh265.c`；
其他media路径相对`common_drivers/drivers/media_modules/`。

1. `v4l:199-203`阈值3/42，enable_swap默认1。
2. `v4l:12946-12961`：只有`version<=3 && submit_count<42`才先关swap；旧GXM及更老非4K例外与T7无关。包4/129使整个条件为false，执行else，enable_ucode_swap=true。
3. 版本来自`common/firmware/firmware_drv.c:300-314`的package_head；不是从CPU ID或secure decoder位推断。`:1100-1117`模块初始化调用fw_pre_load，`:878-891`加载目录，`:660-674`复制package header。不能因get_firmware_data在TEE模式返回0就推断package_head必为零：预载目录是另一条调用链。
4. `v4l:12967-12984`取MMU_SWAP。`common/firmware/firmware_drv.c:132-145`的TEE分支直接返回0，因此这一步不会因目录未返回raw数据而设置is_swap，也不会在此探测到“安全世界缺少swap variant”。实际决定在run时的安全加载结果。
5. `v4l:14654-14698`：先amhevc_vdec_loadmc_ex(...,"hevc_mmu_swap",...)；负错误时回退"h265_mmu"并关闭enable_ucode_swap，成功才置is_swap并保存SCRATCH8。
6. `decoder/utils/amvdec.c:577-584,670-675`将swap映射为format=32363553、core=2、is_swap=1，非swap为17/0/0；`common/firmware/firmware_type.h:47,67,92-96`定义常量，`common_drivers/drivers/tee/tee.c:626-645`发SMCCC。

所以：**已知包与默认参数下厂商首先请求swap，可确定；该次是否成功并最终运行swap，
仍需加载返回值，不能离线宣称。**若板上模块参数被改、元数据加载失败或存在额外固件
覆盖，需以那次运行记录为准；本候选固定本轮已锁定的T7包，不增加通用包解析或模块参数。

## swap时主机的完整准备

| 顺序 | TEE路径（本轮实际对照） | 非TEE路径（说明边界，不实现） |
|---|---|---|
| 初始化 | 不分配普通overlay内存。`v4l:12995-13012`外层是`!fw_tee_enabled() && is_swap` | 分配16KiB DMA coherent缓冲，复制解包后fw->data+3000起的4000字节；4000/3000为十六进制，不是字数 |
| run reset及输入准备 | `v4l:14519`起reset core，准备输入、WAIT；与既有协议顺序对应 | 相同主机框架 |
| 首次加载 | SMC(32363553,2,1)，失败再SMC(17,0,0)。安全世界负责overlay数据、目的存储与初始IMEM装入 | 本地IMEM loader后由普通DMA缓冲供overlay使用 |
| 加载后 | 成功swap时立即读`HEVC_STREAM_SWAP_BUFFER2`（HEVC_ASSIST_SCRATCH_8，DOS word30c8/byte偏移c320）到hevc->swap_addr，`v4l:14688-14689` | 普通mc_dma_handle作为overlay地址 |
| prot_init | workspace→decoder/parser→mailbox/NAL/mode/aux；TEE路径不覆盖SCRATCH8，`v4l:12823-12826`写SCRATCH8只属于非TEE分支 | prot_init写SCRATCH8=mc_dma_handle |
| 启动 | enable_input→ACTION ff→SHIFT0/SIZE→picture table（若已建立）→CPU reset/start，`v4l:14703`起；CPU运行后自行进行所需overlay换入 | 相同框架；overlay内容由普通缓冲提供 |
| 后续run | 若mc_loaded，`v4l:14654-14657`恢复SCRATCH8=保存值，不重新分配或复制overlay | 恢复普通缓冲地址 |
| 结束 | 停机/排空后保留或释放当前实例状态；本驱动PM引用释放即失效固件缓存与overlay地址 | 原本分配的DMA缓冲按生命周期释放 |

在T7 TEE路径没有找到需要主机逐次处理的“swap IRQ/overlay请求ack”，也没有证据支持
额外写某个HEVC_SWAP命令。`HEVC_STREAM_SWAP_BUFFER`是scratch7；T7 MMU map改用
ASSIST_MMU_MAP_ADDR后不应把它再当旧map地址补写。共享input的STREAM_SWAP_ADDR/CTRL
用于保存/恢复输入parser上下文，**不是**SCRATCH8这个固件overlay地址，不能混为一套寄存器。
IMEM_DMA_CTRL/ADR/COUNT的overlay执行由安全固件/微码管理，当前不能按主机源码伪造其写序。

## 明确缺口与新提交

f21缺少正确的首选variant/core/swap标志、加载后SCRATCH8保存和缓存run恢复。
这足以提交一个有来源的候选修正，尚不足以判“无08的根因已经证明”。

`2a622cf6204e6c3f67678cadcc6dbe5c58a074f4`（experiment/hevc-vendor-port）：

- `aml_vdec_hw.c:1351-1377`先请求swap，非零错误回退17，记录两次请求及返回值；保存安全世界返回的SCRATCH8。当前错误处理继续采用原驱动的非零即失败，厂商判断负数；对正数错误同样回退，避免把未知非零当成功。
- `aml_vdec_hw.c:1351-1355`缓存固件时在核心reset后恢复SCRATCH8；`:1095-1097`在PM引用释放时清variant/地址，旧地址不跨电源生命周期复用。
- `aml_vdec_hw.h:173,227`记录实际加载variant及地址；`hevc_regs.h:8`补SCRATCH8具名别名。
- `hevc.c:h265_dump_start`现有启动/header/timeout快照多读SCRATCH8和IMEM_DMA_CTRL，不新增轮询或中断应答。

未强行检查SCRATCH8非零：厂商没有该检查，接口也未公开地址有效范围；先保留原值证据。
没有分配普通16KiB缓冲、没有复制受限固件字节、没有更换板端包或预装服务。
本驱动仍先prepare/reset/load再准备input，装载相对input顺序未在此提交混改。

strict checkpatch：0 errors/0 warnings/0 checks；分支干净。按t48安排由协调者代跑
W=1模块与QEMU KUnit；本worker未把f21的通过继承到新尖端。原始补丁/静态输出保存
build/vdec-hevc-port/swap-candidate.diff、checkpatch-swap.log。
协调者随后经heavy队列对该尖端跑同一validate.sh：W=1模块零诊断、arm64 QEMU KUnit 25/25，
验证模块SHA256 `7caf9de2b015c52327a9a3adbd8661e21f322d2a1242f632dc83512edcb02c1e`；日志
`logs/vdec-hevc-port/heavy-t48-swap.log`。

## 最少补证点（给t48/t3k，不由本worker执行）

1. 同次运行核包路径/大小/SHA、预装服务成功；若需Debian来源，只读dpkg归属和版本。厂商侧记录实际模块名、enable_swap、package version/submit_count，不仅核磁盘包。
2. 一次SMC加载边界：index/core/swap、a0及紧随其后的SCRATCH8。新候选已有日志；厂商金标准需同样记录，确定swap成功或回退17。
3. 同一AU的before-reset/after-reset/after-start/timeout：SCRATCH8与IMEM_DMA_CTRL。新候选已有读回。SCRATCH8应与加载后保存值相符；如果仍停且DMA控制提示等待，再扩只读IMEM_DMA_ADR(3341)/COUNT(3342)，不要预先添加整套dump。
4. 仍以08/RPM、SOURCE_CHANGE及最终正确首帧判断进展；swap加载a0=0、非零地址或PC改变都不等于解码成功。失败按现有窗口判停，不现场换variant重试。

本轮仍无法给出安全世界实际代码的SHA；如果没有额外固件身份接口，普通世界的包SHA、
请求/返回和执行轨迹是可保留的证据边界，不能虚构“读回了blob哈希”。
