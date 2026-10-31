# HDR2a3：VUI、色差、buffer退休与CMA离线修复

后续[a3完整构建和上板](bringup/2026-10-30-hdr2a3-window.md)：VUI、固定图p99、诊断4K60与无内核WARN通过；inode关联假设错误、One-KVM非DMA恢复仍阻断合入。以下保留此前离线设计快照。

2026-10-30，承接[a2上板记录](bringup/2026-10-30-hdr2a2-window.md)。本轮未连接板子/MCP，未修改kbase工作树、正式配置或正式内核分支。
用户已确认VDIN HDR2主路径。以下为待上板特性候选，**四项硬件门禁尚未复验，不建议并main/正式7.3**。

## 源码与提交

内核工作树`~/src/linux-7.3-hdr2-pq`，分支`vim4-hdr2-pq`，基于a2 `5b32e1eb2b951`：

| 提交 | 内容 |
|---|---|
| f1005476aa891 | Wave5从OUTPUT色彩生成AVC/HEVC VUI、coherent RBSP生命周期与SPS回归 |
| 4dba1218cdf05 | PQ precise gamut、PQ/HLG预偏移写值、产品709视频合同 |
| 7c9284da44273 | VDIN池总量边界，包括CREATE_BUFS追加 |
| 450100ce27911 | capture generation/ticket与Wave5 DMA所有权trace |
| 7614e04a56408 | 修复宿主夹具落后的HLG依赖与函数提取边界 |

[邮件补丁及工具](../packaging/hdr2-pq/README.md)按0006–0010接在0001–0005后；十份补丁从正式f71b5c6289cb重放的tree与候选HEAD逐字相同（fad6d66c2598d5adc1e44701c06ada749d1ea571）。
厂商V指`~/src/linux-native-hdr-5.15/common_drivers@8648a716befda5ec2837a7764cd61b8493db8d99`；
下文V行号相对`drivers/media/enhancement/amvecm/set_hdr2_v0.c`。

## 1. VUI放在驱动；默认采用产品709合同

a2的GStreamer已将实际caps `2:3:7:1`传到V4L2 OUTPUT，内核保存了四字段，但`wave5-hw.c:2043`仍禁用VUI。
本轮核对的[上游wave5-hw.c](https://raw.githubusercontent.com/torvalds/linux/master/drivers/media/platform/chips-media/wave5/wave5-hw.c):1887同样写0；
下载文件SHA256 `f68e9f1c189b64aa385d459448b18d42399bf0b966c872095bd7c114ab77ecba`。
因此修驱动序列初始化，不在GStreamer剥掉或强塞colorimetry。

新增`wave5-vui.h:6`显式映射V4L2原色、transfer、YCbCr和range；DEFAULT按V4L2规则解析，未知值拒绝。
支持本产品709/limited，也可表达sRGB transfer13、BT2020/PQ16/full，不将所有输入硬编码为709。
`wave5-vpuapi.c:1039`为每实例分配4KiB coherent存储，写5字节，AVC有效38bit、HEVC39bit；
`wave5-hw.c:2043`写VUI地址及`(bits << 4) | 1`，不启用HRD。
字段依据为[TI既有Wave5接口](https://git.ti.com/cgit/ti-linux-kernel/ti-linux-kernel-next/tree/drivers/staging/media/wave5/wave5-hw.c?h=ti-linux-5.10.y-next-20220818&id=4c9aff667ee7bb101378666e629f8bc55c150ee8)及同版本API头的bit-size定义。
缓冲跟随现有实例DESTROY/reset/quarantine寿命；失败不提前释放硬件可能仍读的RBSP。

**本候选PQ/HLG映射后的NV12统一为709原色、709 transfer、709 matrix、limited，即ISO 1/1/1/0。**
RGB24仍sRGB/full，HDR准入范围不变。这是对齐现有产品接收端解释的兼容选择：

- a2真实5.15产品HEVC插件测试码流为1/1/1/0；AVC直播探针没有colour description，不能说所有厂商流都显式709。
- One-KVM共享RX secondary caps为bt709，私有`gstvim4hevc10.c:138–143`显式写709 VUI。
- 保留厂商当前sRGB形状OETF和像素目标。**数学sRGB不等于709**；此处选择复现既有视频合同，不声称改了OETF曲线。
- a2尚未成功取得实时PQ→厂商HEVC的完整链路，亦没有709与13在浏览器中的新配对实验。
  故此选择依据限于已采产品码流/产品代码；下一窗补实时PQ VUI与浏览器固定画面，不能离线宣称显示色准闭合。

这取代a1的“必须准确标transfer13”候选决定。私有GStreamer sRGB probe仍可用，但当前产品默认协商bt709；显式sRGB输入仍应产出13。

离线`test_vui.py`运行真实C序列化函数，将其RBSP插入CPU编码的AVC/HEVC SPS夹具，再用独立FFmpeg `trace_headers`解析。
709、sRGB、PQ/full共6组四字段均正确；DEFAULT与不支持字段拒绝也通过。此测试**不证明T7固件接受新VUI命令**。
`test_encoder_cleanup.py`在32种分配/固件失败情形检查VUI随所有DMA一起保留、成功close后释放。

## 2. 色差：确定修正两处，p99≤2是目标

比较a2已存`logs/hdr2a2/vendor.json`（真实PQ）与`edge-registers.json`，同一受限白名单中仅两项不同：

| 项 | 厂商5.15 | a2 | 本候选 |
|---|---|---|---|
| gamut shift字索引0x12b0 | 0x1b | 0x18 | 0x1b |
| matrix-I PRE_OFFSET2，0x128d | 0x1e00 | 0x0e00 | 按厂商写完整有符号-512，待读回 |
| 输入/输出矩阵、其余已采offset及HDR_CTRL | 同 | 同 | 保留 |
| gain/OETF端口样本shadow CRC | 5868f499 / 47745310 | 同 | 保留 |

PQ `t7-vdin-hdr.h:104–122`改用V `:816–818, 2021–2025`的precise系数
`3401,-1204,-149,-255,2320,-17,-37,-206,2291`，不再先舍入成/256表。
V `:2011–2012`对单独PRE_OFFSET2写完整有符号值；PQ/HLG原先多加了`&0xfff`，本轮去掉，与packed offset低字段仍需mask的写法区分。
没有猜测硬件字段宽度；下一窗通过既有白名单核对实际readback。
UBSAN另外抓到负系数打包左移的signed溢出，改成先转u32，写入位模式不变。

其它来源的判断：

- NV12/NV21：比较器已做VU→UV与尾padding校正，且有跨帧回归；不能再把UV整体错序当当前细小色差根因。
- 色度位置：V `vin/tvin/vdin/vdin_ctl.c:2503–2586`中NV12/NV21只差swap_cbcr，hconv=2、vconv=0；
  7.3 `t7-vdin-test.c:526–530`对应相同采样模式。厂商运行时debug override、实际滤波/色度相位仍未读回，不把源码默认等同板上状态。
- limited/full及709矩阵：已采矩阵寄存器相同，不改系数来补偿未知差异。量化/定点舍入、HDR2 gamut模式精度可能贡献数码差。
- OETF/gain配置样本相同，PQ EOTF表来自固定厂商表；shadow CRC不是硬件LUT读回，更不能排除内部插值/运行时重配差异。

a2灰阶Y p99=1、彩区Y p99=5、整帧Y/U/V p99=4/4/3。旧gamut舍入误差在OETF之前会被非线性放大，不能据系数接近推导最终必≤2。
下一窗目标：**稳定同源固定画面，逐通道p99≤2码**，分别报告整帧、灰阶、平坦色块和色度边缘；不删异常区域制造通过。
鼠标/菜单覆盖需先消失，否则画面不同判无效；a2整帧最大Y212就是顶部覆盖，不应归于HDR2。
新目标可作为门禁，但离线无法承诺可达；若仍超限，先按空间差图区分边缘采样与平坦区域曲线误差，再审查相应具名寄存器。

## 3. 跨generation退休的可执行证明

内核trace增加`t7_vdin:t7_vdin_buffer`和`wave5_buffers:wave5_buffers_buffer`。
前者为每次获得硬件slot的buffer分配单调ticket及stream generation，用实际导出DMA-buf inode关联后者的提交/完成/取消。
首帧丢弃重装同一buffer不产生新ticket。source-change立即记录切点，之后再提交旧代已完成buffer也判失败。

[check_retirement.py](../packaging/hdr2-pq/check_retirement.py)逐代输出armed/completed/retired/encoded，检查：
旧代未退休/encoder未完成不得开始新代；编码输入必须来自已完成且未退休的capture ticket；
编码持有时不得回收；切点后不得新提交旧代；retained fault、丢trace、ring覆盖、缺BEGIN/END、无实际编码均失败。
CLI还要求source change及至少两代。宿主回归覆盖正常交接、旧帧新提交、提前复用、故障保留和不完整轨迹。

只证明**所记录直接DMA路径中的硬件/编码所有权**，不证明所有用户态FD已关闭，不适用于CPU拷贝后新inode。
需要全生命周期trace：起流前启用两事件、停止全部管线并释放buffer后再停trace，不能只截中间片段。
示例在已持锁的实验窗口，tracefs使用独立instance避免覆盖其他trace：

```sh
T=/sys/kernel/tracing/instances/hdr2-retire
mkdir "$T"
echo global > "$T/trace_clock"
echo 8192 > "$T/buffer_size_kb"
echo 1 > "$T/events/t7_vdin/t7_vdin_buffer/enable"
echo 1 > "$T/events/wave5_buffers/wave5_buffers_buffer/enable"
echo 1 > "$T/tracing_on"
# timeout包围完整PQ→SDR→PQ停流/释放/重开诊断；不在稳态性能项开trace
echo 0 > "$T/tracing_on"
cat "$T/trace" > /tmp/hdr2-retirement.trace
cat "$T"/per_cpu/cpu*/stats >> /tmp/hdr2-retirement.trace
python3 packaging/hdr2-pq/check_retirement.py /tmp/hdr2-retirement.trace
# 新instance的per-CPU overrun/dropped/commit overrun非零即失败
echo 0 > "$T/events/t7_vdin/t7_vdin_buffer/enable"
echo 0 > "$T/events/wave5_buffers/wave5_buffers_buffer/enable"
rmdir "$T"
```

切换需要应用处理SOURCE_CHANGE并完整drain/重开；本轮没有把观测工具冒称自动切换实现。

## 4. CMA：实际分配路径与两层修正

a2 `kernel.log:556–606`：encoder:src线程`VIDIOC_CREATE_BUFS → vb2_dc_alloc → wave5_plane_alloc`追加32MiB，
CMA只余8904/131072页（34.8MiB但不够连续32MiB）；随后`:607–612`VDIN申请12,443,648字节也失败。
“vdec”是共享codec设备名，不代表当时另有解码进程。GStreamer日志也对应encoder:pool0:src动态分配失败。
因此旧记录“下游query导致耗尽”只解释观测到的规避，不足以单独定位分配根因。

根因中的确定部分：GStreamer 1.24.2 `gstv4l2object.c:3847–3856`使用设备最大width/height给编码buffer估值，
8192×8192×8/8/2恰好32MiB；`:4103,4123`将其传给S_FMT，Wave5按请求保留sizeimage，pool随后可CREATE_BUFS增长。
[私有补丁](../packaging/hdr2-pq/gstreamer-encoded-size.patch)仅对固定尺寸编码器按本次分辨率计算，4K8bit变4,147,200字节，约原来1/8；
最小256KiB和驱动S_FMT增大要求仍有效，解码器保留最大尺寸以允许分辨率变化。不是压低码率、删颜色或屏蔽WARN。
诊断bridge已有空allocation query处理继续保留；VDIN总池另限制四硬件slot加两个下游lease=6，CREATE_BUFS累计也受限。

结束后a2 CmaFree恢复505208/524288KiB，未见持续占用证据；**没有分配历史证明绝无泄漏，也未取到所有并发持有者**。
本轮不删除故障隔离的必要DMA保留，不修改CMA容量。新候选干净启动、重复建销池、峰值/回收和无WARN仍是门禁。

## 离线结果与下一窗口（≤30分钟）

- 受影响Wave5、RX/VDIN及DOS依赖四模块W=1编译、modpost、BTF成功；sparse C=2无诊断。
  首次只指定Wave5/VDIN单模块链接漏了DOS符号，补同次DOS目标后通过，不忽略未定义符号。
- Wave5 11份与RX/VDIN 17份宿主测试全部通过，包含SPS独立解析、ASAN/UBSAN失败回收、precise写值、池追加边界和实际IRQ停流。
  修复旧夹具漏HLG policy头、错误提取debugfs函数的问题；没有跳过失败断言。
- 私有GStreamer实际probe/size测试及编译成功；`.so` SHA256为`535eb772b2a7335a5dd4619591eae49f3aafd38d955da0a4146a8a78ef270a02`。
- checkpatch strict原始结果0error/1warning/4check：新文件MAINTAINERS提示（已有目录覆盖）及TRACE_EVENT惯用宏排版。
  仅对这三类复核排除后0/0/0，保留原始日志，不称原始strict零提示。主仓全量unittest320项，跳过13项，无失败。
- 本轮是目录模块构建，沿用私有a2输出验证链接；**没有新a3完整Image/dtbs/modules归档**，不得直接拿a2 release名部署新模块。
  上窗前须完整构建独立`7.3.0-vim4kvm-uhd3-hdr2a3+`并封存新manifest；a2归档保留，正式配置不变。

下一窗口编译全在测量前完成；沿用锁、RAM一次性启动、板卡真实MAC传递及恢复检查。每项timeout≤10分钟：

| 顺序/预算 | 操作与硬门禁 |
|---|---|
| 5.15基线4分钟 | 确认锁/服务/hash；MCP截图、固定图、确认实际PQ；同源3帧、VUI（优先实时PQ HEVC）及已审阅寄存器/配置CRC |
| 候选启动及门禁5分钟 | 只用独立a3归档RAM启动；确认MAC/MCP、干净taint、CMA基线；先编码短片，实际SPS必须1/1/1/0、无firmware错误，否则停止编码性能项 |
| 色准4分钟 | 同画面3帧，逐通道p99与区域/空间差图；0x12b0=1b、0x128d=1e00、gain/OETF shadow保持；不读LUT数据口 |
| 切换/退休5分钟 | MCP PQ→SDR→PQ，各代完整drain/重开，保存全生命周期trace并过逐代退休检查；过渡帧无错误代编码；timeout/fault/WARN零增量 |
| 4K60/CMA4分钟 | trace关闭；3600帧采集→Wave5；SPS再核、帧数/延迟/CPU；最多3次建销池，记录CmaFree前/峰值/后、缓冲size/count；零CMA失败、零WARN |
| 恢复5分钟 | 回5.15，MCP恢复HDR初值与输入法/测试标签、截图；启动文件hash、服务、UDC、锁核对 |

合计27分钟，余3分钟处理正常启动波动；故障提前终止并恢复。无HLG信号则只记录未覆盖，不伪造HLG像素通过。
不测声音、不ptrace、不写PWM/电压、不盲扫寄存器；新寄存器写仅限上述已审阅配置序列。
