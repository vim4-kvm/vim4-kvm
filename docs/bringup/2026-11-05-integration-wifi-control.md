# 2026-11-05：集成生产内核与正式基线同窗 Wi-Fi 对照

结论：同窗`.3`为342.08、集成`.90`为328.88 Mbit/s，下降3.86%，通过不超过10%的
性能门槛。两段完整600秒，生产配置身份核对通过，无目标splat或非请求复位；已恢复`.3`
完整proof及4K视频。调试A仍未通过，本次没有重跑A或验证PD补丁。

协调者不合入 `pd-fifo`；此前生产 `.93` 的 326.97 Mbit/s（相对历史369.55下降11.52%）
混合了集成、PD补丁与无线环境变量，不能据此归因MMC修复。此次只比较正式`.3`与不含
PD补丁的集成生产`.90`。结果和恢复证明见下；没有重编、改驱动、push或合并。

前序：PD A/B、
MMC修复、
[集成边界](2026-11-05-debug-splat-integration.md)。

## 范围、身份与执行方法

协调者显式授权一个最多35分钟窗口，FIFO排在hwdecode-parity `.27`后。
队列工具上限30分钟，因此申请30分钟，执行前计划已追加worker结果文件。
前一票`64443c1e7969453ba340aece0b6d8cb9`释放后，本票
`1407d8c2be2046f2adf443fbb1822b68`（order1201）获得板锁，并持sampling锁。

先在正式`7.3.1-vim4-20261104.3`测600秒，再正常reboot至U-Boot一次性RAM加载
`7.3.1-vim4-20261105.90`，确认生产配置后测600秒，最后恢复`.3`并验实际视频。
两段使用同一Mac `192.168.50.239:5217`、保存的5GHz连接
`974bbec1-7e28-4f64-91b4-674c72bc37e9`，iperf3单TCP反向、每秒统计、600秒。
客户端绑定`wlan0`与其IPv4，默认管理路由仍为`eth0`；测试结束关闭Wi-Fi。
阈值是`.90`均值相对**同窗`.3`**下降不超过10%，历史369.55仅作旁列参考。
首错即停，不换变量重试；每步保留恢复预算，未物理断电，不改默认启动文件。

`.90`直接复用kunit-migration产物
`/home/deepdream/build/integration-73-candidates/production/ram/candidate.tar`：

| 身份 | 值 |
| --- | --- |
| 源码 | `fd41fb5950b9da1fb336ce00d5137d27ee9755fa`，integration-73，无pd-fifo |
| RAM归档SHA256 | `83d87c9014e0a7a4160adc84e1e3b19b2548bad566486a28e067c500e04145ad` |
| Image SHA256 | `5d9111aa91b95b8df92815399d0f8510ce6e95b09c2255bf95bd20ce4df6ec91` |
| GNU build ID | `6c5ebf0605c190d7670374fb6ea880958f54cba1` |
| config SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |

归档、2358个文件逐项SHA、源码与身份均在取板锁前核对。旧配方未保存生成头，不能用
现在共享O=中的头追认原构建；此次运行门禁另核`/proc/config.gz`与归档config一致，
KASAN/PROVE_LOCKING/DMA_API_DEBUG关闭，实际kallsyms没有DMA-debug、ASAN和
lockdep函数，dmesg没有DMA调试启用信息，以区分此前`.93`旧生成配置问题。

## 同窗结果与恢复

票实际占用1310.021752秒（21分50秒），子进程exit0，板票及sampling锁已释放。

| 内核 | 均值 Mbit/s | p10 | p50 | p90 | 相对历史369.55 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 正式`.3`，本窗先测 | 342.08 | 287.31 | 348.65 | 392.17 | -7.43% |
| 集成生产`.90`，本窗后测 | 328.88 | 272.63 | 334.49 | 375.39 | -11.01% |
| 11-02历史`.3` | 369.55 | 337.64 | 372.24 | 398.46 | 0% |

均值取iperf `end.sum_received.bits_per_second`；分位数沿用原方法：600个逐秒区间
排序后p10取index60、p90取index540，p50取中位数。两段各600个区间、单TCP反向，
实际接收时长600.001055/600.001046秒；均连接同一BSSID `c8:bf:4c:fc:69:3a`、
5200MHz，测试开始时信号均-38dBm。TCP重传5739/3431，仅作环境旁证，不据此定因。
两段前后boot ID分别保持不变；实际`.90`GNU ID与归档一致，config一致、debug函数符号
列表为空。前后完整dmesg与UART均无目标splat。两内核既有WEXT提示分别在5.038000/
4.892126秒，作为非splat保留。

同窗比值`328.88004617245286 / 342.0833374901316 - 1 = -3.85967098%`，
通过协调者定义的门槛。`.3`自己相对历史也下降7.43%，说明不能用历史369.55单独
判MMC退步；本轮没有对`.93`做同窗交叉，仍不能把它的下降归因PD，也没有据此改变MMC实现。
一次顺序对照不是长期无线性能或冷复位稳定性证明。

恢复后release为`7.3.1-vim4-20261104.3`、GNU
`e595ad243d663f6c33b92678a4de6e0b78ec16d5`，2370个基线文件及默认启动proof核对通过。
原应用实际4K视频5002.53ms、95次采样、解码帧3→304，60.17fps；新增drop/freeze/loss均0。
没有对默认启动文件或正式模块树安装候选。`.90`payload原已存在，只验证复用并保留；
本次创建的候选模块挂载点由恢复工具按marker清理，临时固件覆盖若由本次创建则删除。
证据为`returned-baseline-identity.json`、`returned-video.log`与窗口`result.json`。

主仓库`python3 -m unittest discover -s tests -p 'test_*.py'`：543项通过、跳过14项；
`git diff --check`通过。没有新增内核代码，故不重复构建、sparse或KUnit。
尚未做调试A的debug_locks/eMMC/ADLA/SDIO完整门禁和重复启动，原因仍为
前轮调试启动cold_boot；本次仅获批生产对照窗口，不扩展实验。

原始证据目录为`logs/debug-splat-paired90/`：分开的`formal/iperf.json`和
`integration/iperf.json`、UART及主机时戳、前后identity/dmesg、运行config、
debug-symbols、baseline proof与恢复视频。脚本位于
`build/debug-splat-fixes/paired90/window.py`，使用已修正的告警分类：大写`WARNING:`
仍是splat，既有小写iwconfig WEXT弃用提示保存在完整dmesg和单独列表中，不误判为WARN栈。

## 旧目标首报与 .92 覆盖范围

离线重读r32/r33b/`.81` UART，辅以r32同次启动的完整dmesg。
表中行号按原始LF分隔计数，不把CR当新行，不混入自动恢复`.3`或pstore历史输出。

| 目标 | 原始首报：内核秒 | 来源：行 | `.92`该时段的新目标splat |
| --- | ---: | --- | --- |
| PWM prepare/nonatomic锁循环 | 4.201298 | r32 `dmesg-1793857262099786000.log`:324 | 未见 |
| MMC IRQ Invalid wait context | 4.805574 | r33b `uart-1793865297808564000.log`:859 | 未见 |
| ADLA 73728 > 65536 DMA段 | 16.700311 | r32同一dmesg:590 | 未见 |
| brcmfmac NVRAM strchr越界 | 17.584444 | r32 `uart-1793857252712817000.log`:1171 | 未见 |
| ADLA mutex类别递归锁 | 18.567267 | `logs/debug-splat-a81/uart.raw`:1111 | 未见 |

r32 UART缺少PWM和DMA告警头，不能假称直接从串口读到了这两个精确时刻。
其第818行保留4.240921秒的prepare_lock反向依赖栈；NVRAM串口和dmesg
首报同为17.584444秒，支持与同次启动dmesg对齐。DMA附随WARN在16.700361秒，
属于同一超限问题，不另算一个目标。

`.92`候选Linux标记所在chunk的主机UTC为13:27:34.390894，回ROM为
13:27:58.131162；host monotonic差23.740267917秒，候选前缀最后一个
printk时间戳为20.012253秒（Wi-Fi固件初始化）。主机时长与内核printk时钟不能
直接等同，因此以更保守的20.012253秒核对；五个旧首报均在其内，前缀未命中目标
lockdep/KASAN/DMA-API分类。按旧启动时序，这五项本应已到首报时刻而此次没有出现，
**没有某一项旧首报落在窗外**。

这只证明这些旧启动特征在已捕获区间消失，不能证明所有相关调用已执行或修复全部通过。
未取得`.92`的debug_locks、ADLA绑定与eMMC/SDIO门禁；其后阶段、原先首次锁告警
关闭lockdep后可能被遮住的问题、PWM同chip真实ABBA及冷复位均无法由这个前缀判断。
主机23.740秒以后的行为没有覆盖，也没有做三次重新RAM启动。

离线可复核输出：`build/debug-splat-fixes/paired90/splat-timing.json`保存各原件SHA、
行号、首报文本与两端UART chunk；同目录`audit-timing.py`生成它。原始r32/r33b
来自主仓库`vim4-kvm/logs/`，`.81/.92`来自本工作树既有日志。
