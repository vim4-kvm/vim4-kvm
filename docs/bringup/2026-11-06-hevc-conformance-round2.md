# 2026-11-06：HEVC 一致性第二轮 RPM、LT 与 CRA 修复

在 `hevc-conformance-fixes` 的 `3cbab82167a1dc3de870165a5a01fd7c66d48a86` 后追加四提交，
新尖 `d177f0dc1ca40a33dadee38f95c08fa332236f69`。自有VM worktree与O=沿用
`/home/deepdream/src/linux-7.3-hevc-conformance-fixes`、
`/home/deepdream/build/hevc-conformance-fixes`，未改其它worker目录。
本轮离线，无板操作、push、合并或主仓库提交。

基准是协调者交接的.37/run85–86定向结果：原30条中16转Success，仍1 Fail、11 Error、2 Timeout；
全I、三短流、六代表和四次compliance通过。新尖未上板，**不把候选记为新增Success**。
不混入r89起进行中的独立全集。第一轮背景见 [修复记录](2026-11-06-hevc-conformance-fixes.md)。
本轮 [14条映射CSV](2026-11-06-hevc-conformance-round2.csv) 保留各流原证据与候选边界。
完整.37记录目前在主仓库main checkout的 `docs/bringup/2026-11-06-hevc-integration37-results.md`。

## 四个追加提交

| SHA | 最终源码位置 | 行为 |
|---|---|---|
| `b3b0a84ffc81c5361cd8fd7df30ef898b037b7f7` | hevc.c:1065、1247 | 首slice地址语法不存在时采用推断0；后续slice保持边界检查；picture/tile配置统一用有效地址 |
| `5992b3b7ddfb48219f73230c993b546222672df0` | hevc.c:492、544 | LT条目按POC LSB位宽匹配已保留DPB；在改变引用状态前完成RPS解析，ST仍全POC精确匹配 |
| `56097375bd1be48859e80ffef49da0ba68c12cda` | hevc.c:259、1137、1242 | 连续CRA留在原输出epoch；DPB重分配后重建随机访问状态，跳过依赖已释放旧图的RASL |
| `d177f0dc1ca40a33dadee38f95c08fa332236f69` | hevc.c:1033、1191、1322 | 动态调试打印完整RPM、失败DPB；错误行补first/address/crop/tile，保留未知输出标志的原始证据 |

厂商行号相对 `common_drivers/drivers/media_modules/frame_provider/decoder_v4l/h265/vh265.c`。
不改固件、不增加内核码流解析、不按码流名添加特殊分支。

## 1. SLIST：确定校验契约错误，仍需验证是否就是现场拒绝字段

SLIST_B/D的已打印字段全部合法：832×480、CTU64、POC0/8bit、I/IDR19、TID1、
8bit420、refs0/0、DPB4/reorder3、merge0、tile行列minus1均0。
旧消息未包含slice地址、conformance window和具体tile flag；不能据这行诊断断言哪个字段错。
离线trace_headers确认SPS的window flag为1且四偏移为0；首图first_slice_segment_in_pic_flag=1。

确定错误是：first flag为1时地址不在语法中，厂商:6888–6897先推断slice地址0；
本驱动虽也设置软件地址0，却先检查原RPM地址，并在new-picture和tile选择中重新使用原地址。
新提交只让这三处统一遵守推断地址，不放宽后续slice、尺寸或crop的检查。
KUnit用832×480、首slice原地址0xffff验证应接受，后续地址26接受、104拒绝。
**这是SLIST候选，实际RPM地址未记录，不能承诺两条已修。** 新错误行和完整RPM可排除剩余crop疑点。

VPSSPSPPS的情况不同：08时NAL19/I，但尺寸0×0、chroma0、DPB0。
厂商:11966–11978也在08路径校验CSD并对无效尺寸报错，没有把它定义为可继续的正常参数通知。
不能把用户S_FMT尺寸替代固件尺寸、对0×0发SOURCE_CHANGE或假装完成一帧。
该流有大量参数集切换，既有FFmpeg日志报SPS/VPS不存在，HM仍完整解6帧并匹配发布者。
这支持继续查参数集保留/激活时机，不能据软件解析器失败宣称码流非法或固件不支持。
本轮保持错误，靠完整RPM继续核对，不加入猜测的continue/retry命令。

## 2. RPS_D：捕获数据证明 LT 的 POC 周期丢失

POC260时原始little-endian RPS为 `f6 3f ce 3f 42 60 e2 60 00 80`：

| 条目 | 旧计算 | 该流正确目标 |
|---|---:|---:|
| 0x3ff6，ST | 260−10=250 | 250 |
| 0x3fce，ST | 260−50=210 | 210 |
| 0x6042，LT | 260+66=326 | 70 |
| 0x60e2，LT | 260+226=486 | 230 |

码流POC LSB为8bit。离线header trace在LSB4的同一slice明确给poc_lsb_lt=70、230，
70还带delta_poc_msb_cycle_lt=1；先前硬件日志显示长期参考70持续被使用。
因此326/486不是可接受的完整POC。厂商:828–836、:4143–4193给位布局与delta算法，
但仅照抄算术不足以处理捕获到的跨周期LT条目。

新实现只对LT按当前POC LSB位宽在保留DPB中找唯一完整POC，尺寸必须匹配；
不同周期有多个候选则仍拒绝，不选最近图、不复活已释放引用，ST不做模糊替换。
先解析整个旧RPS，再修改referenced/long_term，避免slot遍历顺序改变匹配集合。
KUnit直接使用这份RPS、250/210/70/230四图调用生产retention/list函数，并验证歧义和缺失ST仍报错。
RPS_E在CRA256附近也含LT保留和回绕，属于同候选范围，完整流仍待板验。

## 3. RPS_B：不是只差一个reorder门限，而是CRA提前切epoch

run85实际解码顺序是POC26、28、30、31、27、29、CRA32、RASL25；
参考显示顺序应先25，再26…32。旧代码每遇CRA就增加epoch，导致待输出26…31立刻被当成旧序列冲刷。
这与实际显示索引25先出现参考26…31再出现参考25完全对应。

连续CRA允许leading pictures继续参加正常重排；只有IDR、BLA、从无旧参考状态开始的CRA建立新epoch。
厂商:7058–7085区分初始随机访问与后续CRA，:3960–3980按POC排序。
新KUnit用实际26…32/25序列调用生产随机访问和输出选择器：CRA后继续等待，RASL25到达后先选25。

RAP_B最后一次尺寸切换释放旧压缩池后，CRA32的RASL28仍尝试引用已释放的POC24/22，故-EINVAL。
软件参考同样在该段不输出这些RASL。新实现参考池重建后重置随机访问状态，
按厂商:2602–2612初始化及:7058–7085随机访问规则跳过这些图，而非放宽引用检查。
KUnit另测重启CRA、RASL_N/R跳过、RADL不跳过、IDR清旧随机访问门限。
RPS_E的连续CRA也不应强制冲刷旧epoch；它同时需要LT保留修复，收益不独立归因。

## 4. BUMPING、NoOutPrior、OPFLAG：已定位策略缺口，尚无可用标志ABI

离线trace与参考数量：BUMPING有66个首slice而参考49帧，6次no_output_prior=1；
NoOutPrior_B为50/47且有1次该标志；NoOutPrior_A为50/40，但没有显式该标志为1，
还需查推断的输出抑制/CVS条件，不能同样套“读到1”。
OPFLAG_B/C各100个首slice，pic_output_flag=0分别2/4次，正好对应参考98/96帧。

当前主机总是给重建图关联CAPTURE，在IRAP边界冲刷所有旧pending，不区分可解码但不显示，
也没有按no_output_prior丢弃旧pending。这是实际策略缺口，不能用新CRA顺序修复冒称输出抑制已实现。
厂商RPM union:852–924和输出:3890–4008、:6044–6074没有标明这两个标志的承载位置。
不能按NAL类型无条件丢旧图，也不能把I/P/B类型当可见性。
新动态调试每08记录完整0x80个u16（四行，每行64字节），可与同AU的已知语法标志逐项关联；
没有新增MMIO访问或私有ABI。引用失败还保留DPB槽，参数拒绝补地址/crop。
本轮未猜bit，五条输出抑制流仍列待修；新诊断提交预期修复数为0。

## 5. 两条 timeout

run85 LTRPSPS_A仍status02、PC0xda4、SHIFT0x5f，当前AU没有08；
run86 WPP_D仍08→05后PC0x6d9、SHIFT0x318，64像素宽/单CTU列。
两者和.36相同，普通slice模式已修掉其它五条WPP但没有修D。
本轮未找到与此对应的确定主机寄存器遗漏，不试猜阈值或放宽完成条件。
LTRPSPS需要固件参数解析/包契约证据；WPP_D需要同流5.15轨迹或固件单列WPP约束证据。
未归Known unsupported，不碰金标准worker的目录或分支。

## 验证与复测交接

四个完整format-patch逐提交strict checkpatch均0/0/0，正文75列（完整既有SoB例外），diff检查通过。
首次heavy票1517的keeper因沙箱Operation not permitted退出，未启动构建；日志保留。
随后检查现有租约已结束，再通过原入口取得FIFO1519；LT排除当前图的判据经审查改为按POC后，autosquash重排并经 **FIFO1521** 实际完成新尖端
**arm64 QEMU KUnit39/39（新增上一解码图作LT引用用例）、W=1模块构建成功**。复用自有kunit/module O=，未绕过队列或锁。
五条既存KUnit模块缺MODULE_DESCRIPTION的modpost告警保留，无新增编译错误。
模块SHA256 `43d3364739ccce1358fb958d91a0ce72fa81161acd51f0b6f3f22aeab7c0298f`。
VM入口 `/home/deepdream/build/hevc-conformance-fixes/round2/validate.sh` 已固定尖端。
原始日志、patch、hash、RPS/SPS摘录和票据在 `build/hevc-conformance-round2/`，Mac执行日志在
`logs/hevc-conformance-round2/`。本轮未跑板或新全集，主仓库不提交。

建议下一候选一次启动：先全I及三短流，再SLIST_B/D、RPS_D、RPS_B、RPS_E、RAP_B；
这些分别验证地址、LT、连续CRA和重启CRA。保持第一轮16条新通过中的代表回归：
WPP_A、DSLICE_A、CAINIT_G、DBLK_A、TILES_B、RPLM_B，并至少一轮select/epoll compliance。
要求逐帧/整流摘要、精确帧数、status0、LAST、零ERROR；不能以不再-EINVAL替代像素正确。
SLIST若仍拒绝，必须保存新first/address/crop行；RPS若拒绝保留DPB；输出标志组采完整RPM做对照。
两条timeout放末尾并遵守原timeout后恢复规则，不因诊断输出增加而现场改寄存器或重跑求通过。
