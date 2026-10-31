# 2026-10-30：ADLA 首次上板验收，npu1 在 probe 门禁失败

结论：**未通过，不能登记7.3 NPU功能或性能追平。** 5.15三模型基线、
ATTACH与SDK正向profiling完成；npu1启动后取IRQ失败，没有`/dev/adla0`。
已回默认5.15，恢复临时运行时文件，服务和UDC正常，启动文件哈希不变。

## 窗口与身份

用户授权独占上板；持本地board/heavy/串口锁、板上媒体锁。
没有发送HID、测试声音、ptrace视频进程或改动编码器锁文件；未push。
推理测量没有并行编译；所有探针与观察有进程超时，单项少于10分钟。
源端是另一台Mac mini M6，本轮没有操纵源端产生运动。

| 项目 | 身份 |
|---|---|
| 默认基线 | `5.15.137-vim4kvm-hdrdual6` |
| 基线GNU build ID | `4a9b69d62ba7b3a5adeb41b213f7f3e573006165` |
| 候选 | `7.3.0-vim4kvm-npu1+`，2338个匹配模块 |
| 候选GNU build ID | `5f66186d0cc2e53b89c4bbf91226ec7b0b70d6ce` |
| 候选源码 | VM `~/src/linux-7.3-npu`，`vim4-npu-adla@40c653d43f711` |
| ABI版本 | 基线`/sys/module/adla_core/version`为1.4.0.3；SDK打印1.4.0.2 |
| 三模型探针SHA256 | `509eee645a022f923c58aa614b14b98009a714edd85df55ca89dd1b08a839aed` |
| libadla.so SHA256 | `cd5fc35e273939a50cfe14585d1fb15b60939037a670f679b209c85cdc50a5f8` |
| libnnsdk.so SHA256 | `10778d0ff47815c039804fb4c814fd064a0eeeb4700cb416a57067e5dac1537a` |

库为`/lib/aarch64-linux-gnu/`中的板上原文件，没有替换。
模型固定Khadas `3e87c7d2832b7cbd4dc727a325c4a89146e7a952`，
模型SHA见[模型清单](../../tools/npu-models.json)；同一份输入使用Pillow 12.3.0生成。
输入SHA：VGG16 `2e39c24811b1c0e9384b61f49002f96010aeae0551d3a325bec5f65f384aaa99`，
DenseNet `45bc9f9aee66a42e39d360b67a03ce042818e81defbf7a9030415682b482da40`，
YOLOv8n `8cfba485bd774bafea38808c0f4fb5b2a70645c350d1a374e7399c10ed5e648e`。

## 5.15基线

使用`npu-validate.py run`，每模型101轮，去第一轮后100个样本。
计时为`aml_module_input_set + aml_module_output_get`，逐轮张量落盘在计时区间外。
探针进程组超时90秒；服务保持正常，没有启动视频测试客户端。
以下是5.15单侧基线，不是跨内核配对比较结果。

| 模型 | 完整张量文件数 | 平均ms | P50 ms | P99 ms | 最大ms |
|---|---:|---:|---:|---:|---:|
| VGG16 | 101 | 0.560168 | 0.548009 | 0.720012 | 0.854847 |
| DenseNet CTC | 101 | 1.951742 | 1.928531 | 2.097492 | 2.113867 |
| YOLOv8n | 303 | 30.133937 | 29.870935 | 32.019094 | 34.344173 |

全部505份输出已下载并重新校验文件大小/SHA，损坏0份；输出浮点值均有限。
每模型每个张量在101轮内字节一致，轮内差异0。
**7.3没有任何推理输出，因此跨内核输出差异、平均退化百分比均为未测，不能写0%。**

完整张量SHA256（每轮相同）：

| 张量 | SHA256 |
|---|---|
| VGG16 output0 | `53d32943889b740c6999c1ddd9e65ee00c5409b46d79671ea724bb5d0bad31a9` |
| DenseNet output0 | `b6e4879d2147524bb94b47e8ff9c9fd42798ec7b497977e301da69948fc023e5` |
| YOLOv8n output0 | `d84c727378f3086cc2bcb507334b713c7800fa036d4c9487628011e20f34c66c` |
| YOLOv8n output1 | `3b985ae449edd3113eab3c6a6ed388a17e3e22af41a28394002f12cb4d7e7ddf` |
| YOLOv8n output2 | `675265f58397173ffa9f9d1f35b5fd75dadb81e1450727a09c09789942fd4e01` |

修正后的ATTACH探针先SET_CONTEXT_ATTRIBUTE，再REQBUF、buf_type=0物理页导入、
比较4096字节别名、detach/free，退出0。没有导入猜测的任意物理地址。
正向SDK profiling另用VGG16跑3轮：`profile_inference_us=371`、
`profile_memory_bytes=3298400`，destroy rc/status均0；不混入上表性能样本。
负向PROFILE_CFG无network测试没有在5.15执行，其厂商错误路径漏解锁。
工具现主动拒绝该基线版本，板上验证拒绝码2，未进入设备ioctl。

5.15 `nn_adj_vol=0, package=1, efuse=2`，请求890000 µV；
`/sys/class/regulator/regulator.4/name`为vddnpu，microvolts读回890000。
厂商代码证据为`common_drivers/drivers/adla/kmd/drv/port/platform/linux/adlak_regulator.c:159`，
`:198`起的零调整分支和`:231`的set_voltage。这是框架读回，不是物理电压测量。
独立PM观察使用1000轮DenseNet、外层15秒超时，退出0，不纳入性能表。
`debug/clk_core`实际读回从0到799999988 Hz，再回0；设定值800000000 Hz。
空闲后`debug/clock_gating`为`ADLA is in clock gating state and suspended.`。
这只证明5.15基线门控/唤醒；7.3 runtime PM未测。

## 故障、候选启动与门禁

1. 初版独立UAPI探针遗漏SDK的SET_CONTEXT_ATTRIBUTE握手。
   在5.15的REQBUF阶段、尚未执行ATTACH时触发空指针访问0x48。
   pstore栈为`adlak_os_mutex_lock → adlak_alloc_from_bitmap_pool_reverse →
   adlak_smmu_iova_map → adlak_smmu_alloc → adlak_mem_alloc_request → drv_ioctl`。
   板子自动重启到5.15；收集pstore后修正探针，正常SDK基线及修正后的ATTACH通过。
   这是测试工具前置条件缺陷，同时说明厂商驱动不能安全处理该非法调用顺序。
   工具握手修复不能代替候选驱动拒绝非法顺序；后续须增加明确错误返回的回归检查。
2. 备份并校验12个启动/登记/运行时文件；临时安装仅增加npu1路由的5个助手，
   再取当前5.15 release/build ID/cmdline/文件哈希证明，生成和stage私有bundle。
   首次流式传输归档哈希不符，stage在解包前拒绝；改用宿主挂载复制再scp并核对SHA。
3. 第一次RAM sysboot成功加载候选，但无initramfs，沿用的`root=UUID=`无法解析，
   VFS unknown-block(0,0) panic；经自动重启回5.15，不改默认启动配置。
   修正打包器，以当前根块设备的`PARTUUID=bcb80000-02`生成候选APPEND并加rootwait；
   stage另核对该分区设备号等于当前根挂载设备号，原始基线cmdline仍用于身份核验。
   错误归档/阶段目录保留为取证，不被默认启动引用。
4. 修正后的bundle SHA256为
   `149b74a6b9ace095d0bca55991603c5efd34b4c05a9d3223d7004bbc579ecee9`。
   第二次RAM sysboot进入npu1，实际release/build ID与载荷一致。
   ADLA在启动约5.23秒报`get irqnum failed`，probe错误-22，没有设备节点。
5. 现场DT有`interrupt-names="adla"`、`interrupts=<0 185 4>`，并非节点漏写中断。
   代码证据（均为VM候选树）：
   `drivers/misc/adla/drv/port/platform/linux/adlak_platform_config.c:269`按资源表取IRQ；
   `drivers/of/platform.c:120`只填充reg资源；
   `drivers/base/platform.c:481`起的IRQ接口先从fwnode解析，`:509`提供
   `platform_get_irq_byname()`。应修正API并传播负错误码，尤其-EPROBE_DEFER。
   本轮未临时替换候选模块、未重建/启动另一内核。
6. 视频方面另有`HDMI receiver is already loaded with different experimental settings`，
   `vim4-kvm-hdmi`反复失败，One-KVM inactive；候选dmesg中VDIN probe为-67。
   `packaging/kernel-edge/one-kvm-edge-prepare:34`起会设置并核对模块参数，
   初判自动加载与运行时参数设置顺序不一致，具体参数尚未定位。
   没有启动第二编码器，也没有强行卸载接收器。

| 候选验收项 | 结果 |
|---|---|
| RAM启动、匹配模块/内核身份 | 修正根参数后通过 |
| ADLA probe、三模型完整输出 | probe失败；推理未运行 |
| 输出字节一致、配对平均退化≤5%、P50/P99/max | 无候选数据，未通过验收 |
| ATTACH与profiling | 仅5.15通过；候选未运行 |
| runtime PM、超时/取消/进程退出后恢复 | 候选未运行 |
| HDMI＋Wave5并行的帧推进/错误/丢帧及NPU延迟 | 未运行，无并行影响数据 |

软复位失败时拒绝请求并保留可能仍被DMA使用的页直到重启，该例外用户已于 2026-10-30 接受。
候选源码`adlak_device.c:44`只发布一次故障，`:59`打印
`recovery failed: <error>; reboot required`，后续open/ioctl返回EIO，WAIT/GET_STAT报告失败。
这些为源码与离线测试合同，**本轮没有验证真实硬件软复位失败或故障日志**。

## 回退与证据

从npu1发起普通reboot，未在U-Boot选候选，回到5.15相同build ID。
恢复5个助手后，12个文件的内容SHA与uid/gid/mode全部等于窗口原备份。
One-KVM、vim4-manager、vim4-kvm-hdmi、vim4-kvm-gadget均active，
`/sys/class/udc/fdd00000.crgudc2/state=configured`，`/dev/adla0`及基线工作点正常。
没有修改默认内核、extlinux、uEnv或正式部署锁，没有刷写U-Boot。

关键启动文件最终SHA256：

| 文件 | SHA256 |
|---|---|
| /boot/edge/Image | `61dda2420c55623baf7c1f5f5d2a4af1a79c7f528dceb24f3462e373e93eca9d` |
| /boot/edge/vim4.dtb | `893ea6c8990860f1ee0d8c1910fc210e39728e941128d52f465618a5f0c3958d` |
| /boot/extlinux/extlinux.conf | `0f34f14cbaaca91c802c59476ccb06bdba0d782e738f006be412df0e4bf22b73` |

本机证据目录`build/npu-board-20261030/`（不入git），板上目录
`/var/tmp/vim4-npu-accept-20261030-r4/`。保留原始/最终JSON、pstore、串口、
候选dmesg/服务日志、三个baseline目录中的全部张量/result.json/probe.log。
私有stage目录仍在`/var/lib/vim4-kvm/display-m1/`，默认启动没有引用。
三个result.json SHA256依次为VGG16
`1af55e2767d1febc8ecca439d37fb85f50f814b38ddac011260d3e84285310e5`、DenseNet
`2c3dc418224922f493cba7add68d85667189e02534d6d821a0fcafbf7751d54e`、YOLOv8n
`4906d2eaef73aeb2bc71662a4306630027f10f7b3a157226d3704efb6bf5ec6b`。

下一轮先修IRQ API、HDMI参数加载顺序，完成独立候选离线门禁；
再按[完整顺序](../npu-adla.md#下一轮上板顺序)重采5.15与7.3配对窗口。
候选正常时仍预留55–75分钟独占；本轮失败数据不能替代PM、恢复或运动视频并行验证。

本轮工具离线验证：主仓unittest 305项，7项跳过，其余通过；
Linux VM另跑一次性启动9项测试全部通过，含真实PID1挂载失败回退的宿主harness。
最终UAPI探针以候选UAPI头在ARM64 VM用`-Wall -Wextra -Werror`编译通过；
5.15负向PROFILE_CFG保护退出码2。内核工作树保持清洁，本轮没有新增内核提交。
