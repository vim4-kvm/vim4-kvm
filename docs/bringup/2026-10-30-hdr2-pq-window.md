# 2026-10-30：HDR2 PQ的SDR基线与受限shadow诊断

用户已于2026-10-30批准VDIN HDR2硬件路径。本会话唯一占板，另一会话仅离线开发HLG。
独占窗口约18:43–19:10 PDT，持有board/heavy锁；RAM一次性启动，不改变默认5.15。
**M6全程输出SDR，PQ颜色、PQ↔SDR切换和HDR性能均未验收。**

## 状态与有效结论

| 项目 | 5.15 hdrdual6 | 正式7.3 uhd3 | PQ诊断候选 |
|---|---|---|---|
| 输入 | SDR、YCbCr444、8bit | SDR，DRM候选EOTF=0 | 同源SDR |
| PQ识别 | hdmi_hdr_status=SDR，VDIN0/1 hdr_sdr=0 | hdr_input=0，drm_received_ns=0 | 同正式7.3 |
| 编码前捕获 | video71，3840×2160 NV21，单平面 | video0，3840×2160 NV12 | 同正式7.3 |
| 输出色彩标签 | colorspace/xfer=Default，YCbCr709、limited | REC709/xfer709、YCbCr709、limited | 不改标签 |
| 有效HDR2路径 | vdin0_native_hdr=1，SDR/native bypass | HDR_CTRL=0，HDR矩阵关闭 | 与正式7.3寄存器快照一致 |
| PQ shadow应用 | module数组只能证明配置值 | 无已应用CRC诊断 | profile_programmed=0；pending=1；已写CRC=0 |
| PQ实测 | 未测 | 未测 | 未测 |

当前384字节RTK-CONTROL EDID三块校验和均为零，HDR静态元数据EOTF mask=0x5，**已经宣告PQ**。
现有工具能改EDID能力，不能代替M6上的HDR开关；未发现无需HID就能强制当前源输出HDR的已有手段，因此未重写EDID。
已向用户说明需要在M6上**物理操作开启HDR**；未收到已切换确认，本轮最后只读状态仍为SDR。
HLG需要另外准备实际HLG信号，PQ能力或桌面HDR开关本身不能证明HLG。

输入状态来自具名接口，不靠EDID反推：厂商源树
`~/src/linux-native-hdr-5.15/common_drivers@8648a716befda5ec2837a7764cd61b8493db8d99`，
`drivers/media/vin/tvin/hdmirx/hdmi_rx_drv.c:2895–2978`为缓存颜色/位深/HDR状态回调，
`drivers/media/vin/tvin/vdin/vdin_debug.c:4868`附近为hdr_sdr状态。
7.3从`/sys/kernel/debug/fe398000.hdmi-receiver/status`核对有效包时戳、hdr_input与DRM候选字节。

## 寄存器、LUT与像素

先审查具名寄存器再读。5.15仅在VDIN0持流时，通过已审阅`aml_reg/paddr`地址选择器读取
`0xff000000 + 字索引×4`；选择器只提交地址，不提交寄存器值。7.3持流时只读相同白名单映射。
字索引清单：`1280,1281,12b0,1282–1286,128a–128d,128e–1292,1296,1297`。
未读取未持有的VDIN1银行，未读LUT address/data端口，未扫描整块MMIO。

- 5.15 HDR_CTRL=`0x1c040`，gamut=`0xb`，输入/输出矩阵为单位系数；这是其native bypass配置。
- 正式7.3与PQ诊断候选的19项快照逐项相同：HDR_CTRL=0、CLK_GATE=0、gamut=`0xe`、所取矩阵/offset=0。
  不以不同内核的原始CTRL字不相等判定颜色错误；当前有效路径都是SDR旁路。
- 新诊断额外只读具名HDR_CTRL、HDR_MATRIX_IN/OUT（12bb/12bc）与gamut。
  非开流或无receiver lease时明确输出`registers: not read without active stream lease`，不碰MMIO。

| 表/口径 | 厂商配置CRC32 | 7.3配置CRC32 | 解释 |
|---|---|---|---|
| 149点OOTF gain，LE u32 | 5868f499 | 728d4d9e | 既有厂商曲线与tables-edge高光肩部不同；本轮不静默换曲线 |
| 149点OETF，右移2后的LE u32端口样本 | 47745310 | 47745310 | 当前取样口径一致；厂商未截断12bit数组CRC为539ffb54 |
| 143点静态PQ EOTF，LE u32 | 本轮未读取厂商该数组 | 55057c14 | 仅候选静态表，不代表SDR时写入 |

候选开流/停流均为`profile_programmed=0, curve_pending=1`，last_programmed两CRC为0。
SDR期间保留待用PQ曲线是预期行为；**配置数组、最后写入shadow、硬件LUT读回是三个不同证据层级**。
目前只完成前两级可观测性，不宣称有硬件LUT读回。

三个阶段各捕获3帧编码前数据。厂商NV21每帧文件块12,443,648字节，有页对齐尾部；可见载荷12,441,600字节。
7.3 NV12可见载荷相同、stride=3840。跨栈比较必须去尾padding并交换NV21的VU顺序，不能直接比较原文件哈希。
首帧Y范围均16–235；示例位置(行,列)=(0,0)/(100,100)/(1080,1920)/(2000,3500)：
厂商28/204/235/235，正式7.3为28/203/234/234，诊断候选为28/204/234/234。
这些是**不同时刻的桌面图**，不是固定色块，1码差也不能据此归因或作为色彩门禁。
原始数据保留供之后固定图比较；无PQ输入，未产生PQ编码前像素误差结论。

## 修正、并行交付与离线验证

独立内核`~/src/linux-7.3-hdr2-pq`，分支`vim4-hdr2-pq`，基于正式`f71b5c6289cb`。

1. `eb156b545c8a2`：新增受限只读debugfs `hdr_status`；按实际端口样本生成CRC，
   在已有PQ初始配置/帧边界重载后记录shadow。mutex→irq_lock保护快照；无活动lease不读控制寄存器。
   合并后源码`drivers/media/platform/amlogic/t7-hdmirx/t7-vdin-test.c:219–241, 484–490, 1389–1432`。
   **不改任何PQ矩阵、LUT、电压或输出标签**；没有HDR证据，不做猜测式色彩修正。
2. HLG离线交付`c68407cb052be`在本会话合并成`bbf9ff89b284d`：保留HLG writer及PQ-only shadow记账，
   PQ曲线请求不在HLG期间重载。原HLG worktree/分支未改；[HLG证据](../hdr2-hlg.md)保留。
   合并后仅离线验证，**未在本轮上板，也未扩大EDID能力**。
3. `11f3239b7c849`：VDIN Kconfig显式select CRC32，避免其他配置遗漏诊断依赖；私有olddefconfig通过，uhd3原已启用CRC32。

[可复现邮件补丁及应用顺序](../../packaging/hdr2-pq/README.md)随主仓提交。诊断字段只描述PQ gain/OETF，不冒充HLG应用状态。
三份邮件补丁对干净f71源码顺序应用成功，8个新增/修改文件与最终内核工作树逐字节相同。
宿主执行真实CRC函数，独立zlib向量验证LE打包、OETF截断与空表；HLG表/端口字、实际DRM解析、lease切换、frame discard/stop/AXI-error夹具全部通过。
合并后的RX/VDIN目录W=1、C=2 sparse、BTF生成通过，无诊断；strict checkpatch为0 error/warning/check（650行，仅忽略FILE_PATH_CHANGES）。
系统sparse 0.6.4最初被内核拒绝，该次退出0**不算通过**；复制既有新版工具到本任务私有`~/build/pq-tools`后重跑，两C文件均有CHECK。
使用私有`~/build/pq-uhd3`与临时uhd3配置/符号/vmlinux副本，不改正式配置或NPU文件。
本轮是模块目录构建，未重新完整编译合并后的Image/dtbs/全modules；新HLG完整候选须单独构建后才能进下一窗口。

板测只替换PQ诊断模块，Image/DTB/全模块目录沿用正式uhd3，BTF依据同一正式vmlinux生成；
候选私有根`/var/lib/vim4-kvm/pq-hdr2/a3572361d542e5505bd159ad8a327cf364fe25f3`，release仍为`7.3.0-vim4kvm-uhd3+`。
正式payload路径`/var/lib/vim4-kvm/display-m1/a3572361d542e5505bd159ad8a327cf364fe25f3`，未覆盖它。

| 板测产物/证据 | SHA256 |
|---|---|
| PQ诊断stripped module，VM ~/build/pq-vdin.ko | eebd42351124b461afe823b1d867ce791e493155a461dbcfe2640a8246d56414 |
| 私有PID1，VM ~/build/pq-init | 7fa2e028efb0f20bd5335e1d497245a781c464f93d95ac8dc74f0fd036f94392 |
| 厂商首帧可见NV21 | 524d95618e4800077887010baa15b91f4fed64144087716d2ffa4543a8e13dbd |
| 正式uhd3首帧NV12 | 3fa7915081a8ebd55ffb099e7772705258deef94c0e76098087932b5bcd9a2ed |
| PQ诊断候选首帧NV12 | 7b410a30b55c04dbd70444ac3ccd58e3e2333539b5ac91811f68022247fedce6 |

原始记录/帧在主工作区`logs/pq-hdr2/`，包括vendor.json、两份edge-registers.json、hdr_status、格式、UART与final-ready.txt；
构建日志VM `~/build/pq-{modules,sparse-merged}.log`。这些本地证据未push，原帧不是跨时刻色彩一致性证明。

## 窗口异常与回退

首次正式uhd3 RAM启动成功，但磁盘助手未准入该release，服务未就绪；原始cycle.py超时记录保留。
用已通过uhd3回归的五个私有runtime助手只读bind mount临时准入；私有副本初始0644导致203/EXEC，修正私有副本0755后服务就绪。
没有替换磁盘助手。显式加载nv12/direct_dma采集并重启gadget，得到服务active和UDC configured后才采集。
候选taint=4096为树外模块O位（bit12），日志仅加载提示；不是WARN位（bit9），无WARNING/oops。
早期人工把4096误判WARN已更正，没有清taint或伪装intree。

最终正常重启回`5.15.137-vim4kvm-hdrdual6`，one-kvm/vim4-kvm-hdmi/vim4-manager均active，UDC configured。
7个受保护启动/锁文件与5个运行时助手共12项SHA256全部OK，临时bind随重启消失，默认5.15不变；释放board/heavy锁。
全程未发HID、不测声音、不ptrace视频、不写PWM/电压，未盲扫寄存器；测量期间未并行编译。

## 余项与下一窗口

- 用户在M6物理开启HDR，准备稳定PQ灰阶/高光/饱和色测试画面；先确认真实EOTF=2、BT.2020、位深/range再进入颜色门禁。
- 同源5.15与7.3固定white/peak和同一gain profile，受限CTRL/矩阵/offset/gamut与PQ shadow比对；仍不读LUT数据端口。
- 编码前NV21→NV12规范化后比较固定ROI/全帧；注册容差后再跑PQ↔SDR同分辨率切换、过渡帧丢弃与Wave5。
- sRGB表与V4L2 xfer709的合同仍未闭合；相同OETF CRC不证明标签正确，不只改标签掩盖曲线差异。
- HLG合并候选先完成独立完整构建；真实HLG源、色彩/切换/4K60必须另验。GPU shader与DMA适配保持暂停。

主仓全量unittest：315项、跳过13项、无失败；文档链接/索引/体积检查通过。
未将SDR基线提升为PQ/HLG推广结论。
