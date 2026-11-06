# 2026-11-06：HEVC 8bit 全集失败的首轮离线修复

交付四提交候选，**未上板，不能把30条失败记为已修复**。
从主线 `957910f06161aeda0fcf67fb162972203a16310b` 创建 VM worktree
`/home/deepdream/src/linux-7.3-hevc-conformance-fixes`，分支 `hevc-conformance-fixes`。
独立 O= 根 `/home/deepdream/build/hevc-conformance-fixes`，尖端
`3cbab82167a1dc3de870165a5a01fd7c66d48a86`，源码/index干净。
未碰板、排板票、使用子代理、push或合并；主仓库记录留工作树供协调者提交。

原结果为 [132条总表](2026-11-06-hevc-full-results.md)：102 Success /16 Fail /11 Error /3 Timeout。
本轮确认全集候选9431987与基线957910f0的hevc.c/hevc_priv.h/hevc_kunit.c/aml_vdec.c
四路径diff为空，分析对应实际运行代码。
[30条候选映射](2026-11-06-hevc-conformance-candidates.csv)逐条列证据、假设、厂商file:line和边界；
修复预计收益需要一次新候选板验确认，不能相加成新通过数。

## 已确定的代码差异和四提交

| SHA | 最终位置与行为 |
|---|---|
| `dd71a92779e7e1f8e4c6f6eefb3b291300204792` | hevc.c:392；不再为≤4K强制设置NAL_SEARCH_CTL bit21，保留普通逐slice主机配置 |
| `54b6ba1bf4db423f66baf87d9692237febfeeec8` | hevc.c:1784、1804、1870、1935、1945、1987；EOS/SOURCE_CHANGE先于LAST，最终OUTPUT在drain处理后完成 |
| `671b2944651f4d4e2e4ba820a9a6929f67a7461b` | hevc.c:1219、1728；每图保存RPM reorder门限，按最早待输出图的门限bump；保留drain/旧epoch强制输出，新增真实生产函数KUnit |
| `3cbab82167a1dc3de870165a5a01fd7c66d48a86` | hevc.c:1121、1264；区分非法RPM和引用列表失败，记录参数或RPS；不放宽检查、不改变失败缓冲状态 |

厂商依据均相对只读 `common_drivers/drivers/media_modules/frame_provider/`，
文件为实际 `decoder_v4l/h265/vh265.c`，不以非V4L实现代替。

**最重要的分支更正**：全局 `performance_profile=1`（:503–504）并非实例默认必开。
实例在:12106–12110只对有效8K尺寸设1，其它为0；:12722–12731按实例决定bit21。
本节点尺寸上限排除8K，当前一直设置bit21是确定差异。协议初始化每AU先写search=8，
删除后续强制OR即可；不增加8K、固件切换或模块参数。
板上DSLICE/CAINIT/WPP日志多为每AU一次08，无法证明后续slice的MC/MPRED/过滤配置已更新。
普通模式应让需要配置的slice回08，依次配置后05/REQ4；预期search=8，而非0x200008。
这证明应采用哪个厂商分支，尚未证明它能消除每条像素差异。

**逐图重排**：厂商:5909从当前RPM保存num_reorder_pic，:3973–3980用选中图的值比较。
当前只用首次格式探测值。RPS_B的实际索引25起包含参考26…31后才出现参考25，
RPS_E也含正确帧的错位；这是输出次序问题的直接证据，但单凭MD5不能确定门限是唯一根因。
新KUnit测试从初始门限0转为逐图门限4，保留四张图后插入更低POC，验证该图先输出；
另验证显式drain与跨epoch冲刷。不模拟vb2或硬件。

## 失败分组与三类根因假设

| 组及原表现 | 分类、优先假设与未证边界 |
|---|---|
| WPP_A/B/C/E/F，第9帧首错；WPP_D timeout | 主机寄存器/固件slice路径。先纠正bit21。D为64×240、CTU64单列，08→05后PC0x6d9、SHIFT0x318卡住；若普通模式仍卡，需查单列WPP固件限制，不能现在标不支持 |
| DSLICE_A/B/C，第1帧首错；CAINIT_G/H，第3/2帧首错 | 主机逐slice配置。:6888–6904区分dependent slice，:7346–7488配置引用/col/MPRED；快速路径可能跳过主机更新。先比普通模式08数量、slice地址、MV指针，不据名字直接修改CABAC位 |
| DBLK_A/C/D，首错0/1/1；TILES_B，首错4 | 主机过滤/边界。SAO/DBLK表达式与:5373–5698一致；tile路径见:4506–4668、:7287–7346。先恢复每slice更新；若DBLK_A首帧仍错，再作空间差异和滤波位对齐，不盲改已匹配位域 |
| RPLM_B，第1帧首错 | 主机引用表。:4263–4505支持modification，现实现也有；先普通模式核每slice L0/L1 canvas和MPRED，不先重写数组算法 |
| RPS_B/E及BUMPING | 输出/bumping，逐图门限有确定差异。BUMPING已捕49/49但从4起夹入参考中没有的图后整体偏移；RPS_E另在246/300处主机EINVAL，门限修复不能保证同时解决拒绝 |
| RPS_D 22/68；SLIST_B/D和VPSSPSPPS均0帧 | 主机参数/引用契约拒绝，均08后slice setup -EINVAL。缺失败RPM，无法判定是哪项边界。新增两条错误诊断；SLIST有合法8bit尺寸，不能因名字擅自声明scaling-list不支持或放宽检查。VPSSPSPPS的正确参考来自HM，FFmpeg自身只解2/6帧 |
| NoOutPrior_A/B、OPFLAG_B/C | 输出抑制/固件元数据契约。达到参考帧数后仍遇额外输出；多个后续图能匹配错位的参考。RPM union:852–924没有命名pic_output_flag/no_output_of_prior字段，厂商输出:3890–4008、:6044–6074也无直接对应主机字段。普通模式可能改变通知行为，仍需核固件是否传出标志，不能猜scratch位或在内核新增码流解析器 |
| RAP_B 70/80 | 主机几何/随机访问与引用拒绝。SPS在448×256和416×240间切换，CTU也变化；当前重配释放旧压缩池，后续EINVAL。对照:6990–7085、:7346–7461、:10600–10628，需新诊断的具体POC/尺寸，不能任意跨几何保留引用 |
| DELTAQP_A timeout，0帧 | 主机已回05后的固件路径。PC约0x7b5、SHIFT0xdbdf、status05，先切回普通模式；与LTRPSPS的08前停滞分开处理 |
| LTRPSPS_A timeout，0帧 | 固件参数解析契约未证。status02、PC0xda3/da4、SHIFT0x5f，当前AU没有08，不能靠08后MPRED写修复。先验普通路径，再查包/安全加载/解析能力；没有5.15同流结果，不能断言固件不支持 |

以上30条均保留在候选CSV，**没有新增Known unsupported**。
直接对比MD5与全部参考帧发现，DBLK/DSLICE/WPP大部分错帧不能匹配其它显示索引，
属于像素问题；输出标志组存在后续帧整体偏移，不能把两者统一叫“少末帧”。
证据读自Mac主仓库run79c、run80–84，未修改原I420或日志。
离线FFmpeg trace_headers只分析既有30条输入并核SHA256，不是新增内核解析器或驱动mock。

## EOS/epoll竞态结论

成立的窗口是**事件排队晚于缓冲完成**，不是v4l2_m2m_poll漏注册等待队列。
v4l2-mem2mem.c:948–976对OUTPUT/CAPTURE done_wq和fh事件等待都调用poll_wait；
:631–638的last_buffer_done先调用vb2_buffer_done，已可唤醒用户。
原hevc.c先完成最终OUTPUT、再flush LAST、最后queue EOS；用户可能已经读到LAST/EPIPE。
compliance源码v4l2-test-buffers.cpp:1254–1267只在本轮poll提示PRI时排事件，
:1390–1392在LAST后检查got_eos/source_change，恰可暴露该窗口。

修复使drain事件先于最终两队列完成；即时STOP无输入/有CAPTURE和延迟空LAST也同样处理。
即时STOP在hevc_lock内先确认非draining/非stopped、无source且有dst；
generic helper在该状态必归还该dst并返回0，故可在调用前排EOS而不复制框架状态机。
SOURCE_CHANGE也先更新格式/排事件再结束旧CAPTURE。没有改通用poll或JPEG路径。
这消除了已确定的生产者顺序窗口；是否解释两次间歇失败的全部原因仍需compliance复测。

## 复测清单与判停

同一integration候选先r77全I：compliance至少56/56、首帧逐字节及status0；
再cip_B_NEC_3、MERGE_E_TI_3、TMVP_A_MS_3三条已通过短回归（5/8/17帧）。
bit21改变每slice通知路径，若首个门禁退步立即停，不带失败状态继续。

候选收益按提交分配，详见30行CSV：

- dd71a927：优先DSLICE_A/B/C、CAINIT_G/H、WPP_A/B/C/E/F及WPP_D、DBLK_A/C/D、TILES_B、RPLM_B；再DELTAQP_A、SLIST_B/D、VPSSPSPPS，核普通slice路径与拒绝原因。
- 671b2944：RPS_B、RPS_E、BUMPING，逐帧MD5必须与参考显示顺序一致；RPS_E的晚期EINVAL另判。
- 54b6ba1b：同一hevc-intra带流compliance依次select和epoll，建议连续三次，全部56/56且LAST前有EOS/初始SOURCE_CHANGE，不靠重复直到过。
- 3cbab821：RPS_D/E、SLIST_B/D、VPSSPSPPS、RAP_B若仍拒绝，保留新invalid RPM或reference lists行；它是采证，预期修复数为0。

回归代表从原Success中取DBLK_B_SONY_3、MERGE_E_TI_3、TMVP_A_MS_3、ENTP_A_QUALCOMM_1、
TILES_A_Cisco_2、SLIST_A_Sony_5，均已核对为原132项中的Success。
逐流只跑完整原输入，逐帧/整流MD5、帧数、status0、LAST、零ERROR皆满足才过。
NoOutPrior/OPFLAG、RAP、LTRPSPS仍列定向复测，不承诺本轮解决。
像素或接口失败保留原始输出并按既有全套计划收集；内核超时/splat/DMA停机异常立即结束当前窗恢复，
不现场改寄存器、不修改参考、不把正常退出或08/0a当像素通过。

## 实际验证与产物

四提交完整format-patch逐个strict checkpatch均0 errors /0 warnings /0 checks；正文75列，
完整既有SoB不拆行。FIFO **1506**（heavy，已released）实际运行尖端：
arm64 QEMU KUnit **34/34**，包含新增output_respects_each_pictures_reorder_limit；
W=1模块构建成功，无编译错误。五个KUnit模块缺MODULE_DESCRIPTION的modpost告警与旧inter日志相同，
不是零告警；未顺便修改。模块SHA256
`88afa23addf82582f4b31249d8378da8cc11370d7f1f24455bcfabc71c3c5edc`。

VM入口构建根validate.sh固定上述尖端，Mac副本`build/hevc-conformance/validate.sh`；
先QEMU再独立module配置/构建，保留validated-head、source.sha256、JSON、QEMU/module日志。
原始输出已取回 `build/hevc-conformance/`；票据及history同存。
本轮未新跑实板、5.15对照或所有132条；未对8bit以外、超尺寸、多实例扩展。
