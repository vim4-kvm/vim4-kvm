# 2026-11-06：无线屏蔽.36完成HEVC 8bit全集，102/132通过

**132条计划内码流全部执行且各执行一次：102 Success、16 Fail、11 Error、3 Timeout，
Not run=0。** 30条失败保留输出及日志，不重跑求通过，不修改驱动。
另有4条8bit超尺寸码流按原计划Known unsupported、未执行；11条Main10不在本轮范围。
HEVC streaming compliance六窗中4窗56/56、2窗在epoll/EOS检查失败，缺陷未修。
每窗均恢复正式fd41fb5、通过2372项proof和视频检查；没有部署、合并、push或saveenv。

## 范围、身份与统计规则

沿用[全集计划](2026-11-06-vdec-integration36-full-plan.md)、
[147条输入清单](2026-11-06-hevc-full-vectors.csv)与
[参考核验](2026-11-06-hevc-full-reference.md)。Fluster锁为
`45d6dca42398305ac3a3ad9a0712028a2d08d97a`，JCT-VC-HEVC_V1共136条Main/Main Still
8bit输入，132条安排解码；Not available=0。执行器为vdec-capture/v4l2h265dec，
报告是“Fluster套件经vdec-capture执行”，不是Fluster原生runner输出。
输入在宿主校验，板上再次核SHA；没有下载新码流。

全部使用[无线屏蔽变体](2026-11-06-vdec-integration36-no-radio-plan.md)：

| 对象 | 身份 |
|---|---|
| release | 7.3.1-vim4-20261106.36 |
| 源码 | 943198734a1c803d780af845a49ed04fa2e933d6 |
| GNU build ID | 355061dc85a2fd695429b501c0c2b87078cf1f89 |
| RAM SHA256 | 5d6e262cf6044e1cee23b65fd37dff6fb7ad82aba9ea2fb01dfa0d1065de3c6d |
| 系统stateful插件SHA256 | 1bf3a1c01363f3bc1e9847923c7abe2ea8513e218918fd912cf382bb1217d818 |

同一Image/模块/DT，只在候选cmdline屏蔽brcmfmac/hci_uart/btbcm、
mmc_pwrseq_simple_driver_init与bluetooth.service。正式默认cmdline未改。
官方1.24.2 h265parse位于私有前缀；stateful解码器属于系统video4linux2，
stateless属于私有v4l2codecs。按实际Plugin Details精确核name/path/version，
私有文件核封存SHA，系统插件核入场冻结SHA；不将同窗SHA锁误称发行包签名验证。
[r79b身份门禁误停与回放](2026-11-06-vdec-r79b-no-radio.md)已单独保留。

[132行结果CSV](2026-11-06-hevc-full-results.csv)包含逐流结果、批次/窗口、同窗compliance、
实际/参考帧数、首个不匹配或缺失帧（从0起）、实际/发布者MD5、失败原因及证据路径。
Success要求逐帧MD5和整流发布者MD5全部相同、帧数正确、status0、LAST及队列顺序合格。
Fail为正常结束但像素不符；Error包含捕获/EOS/队列错误，可能同时像素不符，不重复计数。
Timeout三条均检测到内核解码超时，均0字节输出，不能算“不支持”或忽略。

## 八批结果与实际窗口

| 批次 | 总数 | Success | Fail | Error | Timeout | Not run |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 18 | 15 | 2 | 1 | 0 | 0 |
| 2 | 18 | 11 | 6 | 0 | 1 | 0 |
| 3 | 17 | 16 | 0 | 0 | 1 | 0 |
| 4 | 16 | 14 | 0 | 2 | 0 | 0 |
| 5 | 18 | 12 | 2 | 4 | 0 | 0 |
| 6 | 17 | 16 | 0 | 1 | 0 | 0 |
| 7 | 11 | 9 | 0 | 2 | 0 | 0 |
| 8 | 17 | 9 | 6 | 1 | 1 | 0 |
| 合计 | 132 | 102 | 16 | 11 | 3 | 0 |

| 窗口/FIFO | 实际新增执行 | S/F/E/T | HEVC compliance | 归档文件数 | 恢复视频fps |
|---|---|---|---|---:|---:|
| r79c/1498 | 第1批18条 | 15/2/1/0 | 56/56 | 1042 | 59.376 |
| r80/1499 | 0，旧前置门禁阻断 | 0/0/0/0 | epoll失败，无总计 | 802 | 59.379 |
| r81/1500 | 第2批前11条 | 7/3/0/1 | epoll失败，无总计 | 940 | 59.566 |
| r82/1501 | 第2批余7条、第3批前16条 | 19/3/0/1 | 56/56 | 1085 | 59.569 |
| r83/1502 | 第3批末条、第4–7批、第8批前15条 | 61/6/10/1 | 56/56 | 1762 | 59.563 |
| r84/1503 | 第8批最后2条 | 0/2/0/0 | 56/56 | 835 | 59.580 |

所有窗口stateless带流compliance 60/60、media 8/8、DOS step=0。
r79c另完成全I HEVC门禁（56/56、98304字节精确首帧、status0、初始SOURCE_CHANGE先于
CAPTURE且只一次STREAMON）及cip_B_NEC_3五帧逐帧一致/status0。
r80之后按协调者决定跳过重复全I/短回归，HEVC compliance改为每窗一次非阻断观测。
132条统计不混入这些短回归，失败码流没有重跑。

后续所有窗口由用户一次授权自行FIFO续跑；每批开始前核完整批预算加420秒恢复余量，
时间允许则同窗多批。普通像素/捕获错误收集后继续。内核超时使现有journal检查失败、
该次解码状态不可继续信任时，先结束当前窗恢复，再从下一条未执行码流续跑；
这是继续全集而非把超时隐藏或重复测试。三条超时分别发生于r81/r82/r83。
窗口间均先恢复/核验/归档清理，原始结果中的Not run随后只在新窗口执行一次。

## 失败清单，交HEVC修复worker离线定位

**16条像素Fail**：CAINIT_G_SHARP_3、CAINIT_H_SHARP_3、DBLK_A_SONY_3、
DBLK_C_SONY_3、DBLK_D_VIXS_2、DSLICE_A_HHI_5、DSLICE_B_HHI_5、DSLICE_C_HHI_5、
RPLM_B_qualcomm_4、RPS_B_qualcomm_5、TILES_B_Cisco_1、WPP_A_ericsson_MAIN_2、
WPP_B_ericsson_MAIN_2、WPP_C_ericsson_MAIN_2、WPP_E_ericsson_MAIN_2、WPP_F_ericsson_MAIN_2。

**11条Error**：BUMPING_A_ericsson_1、NoOutPrior_A_Qualcomm_1、NoOutPrior_B_Qualcomm_1、
OPFLAG_B_Qualcomm_1、OPFLAG_C_Qualcomm_1、RAP_B_Bossen_2、RPS_D_ericsson_6、
RPS_E_qualcomm_5、SLIST_B_Sony_9、SLIST_D_Sony_9、VPSSPSPPS_A_MainConcept_1。
不能一概归因“少末帧”：例如BUMPING实际49帧等于参考49帧，但像素从索引4不符且status1；
RPS_D输出22/68帧，其已输出前22帧一致。CSV保留这些区别。

**3条内核Timeout**：DELTAQP_A_BRCM_4（r81）、LTRPSPS_A_Qualcomm_1（r82）、
WPP_D_ericsson_MAIN_2（r83），各保留0字节capture、GST/ioctl及内核超时原始journal。
不对这些失败宣称固件/私有ABI不可实现，尚需根因分析和修复；本轮不改驱动或厂商源码。

**额外接口缺陷**：r80及r81的HEVC compliance select/REQBUFS阶段捕获16缓冲并通过，
epoll OUTPUT#15之后报`v4l2-test-buffers.cpp:1392: !got_eos && !got_source_change`，
exit1且未输出最终总计。按协调者审查登记为间歇性驱动缺陷，疑似EOS事件/epoll唤醒竞态，
根因尚未证实。r79c/r82/r83/r84同包56/56不能覆盖这两次失败。
r81随后仍有7条Success、3条Fail及1条Timeout；结果CSV明确标注compliance=false，
保留同窗关系，不把相关性当根因。

交接首先读取`run80/archive/results/hevc/{hevc-compliance.log,dynamic-debug.log,kernel.log}`
及r81对应文件，再按CSV定位30条流的comparison.json、capture.log、ioctl.log和capture.i420。
正常流保存逐帧摘要后删除成功I420，失败I420全部保留。
内核超时先触发journal异常，逐流kernel.log可能还未追加该错误：对应完整原始
`archive/results/kernel-journal-*.jsonl/.error`保留，失败目录的posthoc-kernel.json
列出源路径/SHA及消息；posthoc-pixels.json只补像素证据，不改变Timeout判定。

## 未运行范围与冷复位边界

132条计划内Not run=0；136条8bit输入中的PICSIZE_A/B/C/D_Bossen_1因超过当前节点
尺寸上限预分类Known unsupported，均未尝试。其尺寸分别为1056×8440、8440×1056、
528×4216、4216×528，见原清单。11条Main10明确排除，不计入132分母。
没有本轮5.15对照，不能宣称5.15 parity；失败和超尺寸限制也未修复。

本轮保持Mac→USB-C功率计（型号待补）→VIM4的供电/HID拓扑。用户报告能力15W、
平时约3W、r79b候选启动显示最高约5W，未确认峰值保持，不是同步电压/电流测量。
插拔功率计造成一次正式断电启动，按协调者要求不计入既有非请求冷复位统计。

原.36配置维持6次/4冷复位；无线屏蔽变体含r79b共7次/0次，全集相关r79c–r84为6次/0次。
同期间正式恢复7次/0次，既有正式eMMC累计口径更新为至少48次/8次冷复位。
两组拓扑/启动参数不同，不据这些小样本认定无线或Mac供电是根因。
lsmod/rfkill、SDIO deferred及initcall黑名单证明Linux未执行无线初始化，
不能证明共享电源轨已断电。功率计和冷复位后续调查按用户决定留到全集之后。

## 恢复、归档及最终核验

每窗恢复`7.3.1-vim4-20261105`，源码fd41fb5，build ID
`bdbfa439f298e92b5bad092528d11119a974f262`；2372保护文件逐项相同，原cmdline恢复，
Wi-Fi/BT模块及设备恢复，UDC configured/HID功能保留。视频均有新帧、≥57fps，
零新增丢帧/冻结/丢包，不向Mac发送键鼠。所有票已释放，无后续候选启动。

原始目录为`logs/hwdecode-parity-r79c/`和`logs/hwdecode-parity-r80/`至`r84/`；
每窗的`build/hwdecode-parity/run*/brief.json`列UART SHA/跨度、启动身份、归档数和恢复fps。
board-upload.tar逐文件对板端SHA后才删除本任务上传，只清理拥有且哈希匹配的固件副本，
清理helper预先检查/重传。未删Mac历史证据；收到磁盘约束后每窗入场保存df，
低于8GiB则拒绝入场，最终仍约18GiB。

`build/hwdecode-parity/hevc-full/verification.json`实际通过：132个名字唯一且覆盖全部
计划输入；102个Success逐帧/整流摘要与锁定参考全同；30个失败原始I420（含空文件）
SHA对归档清单一致；六窗候选/正式启动身份及2372 proof/视频全部复核。
CSV SHA256为`effcfc7a45695b0489fb9188a35747c700f82131062b4de87fa2584695ef2558`。
离线插件回放、继续失败/不重跑失败流、compliance非阻断回放均有build/原始日志。
没有内核/DT改动，不新增驱动Python测试，不把未重跑的KUnit/构建记为本轮通过。
主仓库全套607项OK、11项跳过（跳过不计通过），输出保存为
`build/hwdecode-parity/hevc-full/final-main-tests.log`。

交付30条失败及间歇性接口缺陷给协调者转t4r；后续修复合入、正式cmdline部署另起计划，
本次只完成一致性采样、记录与本地提交。
