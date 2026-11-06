# 2026-11-06：r98/r100 的合法 drain 尾部归一化

r98 的 cip_B_NEC_3 像素和状态通过，原严格比较器因 DQBUF 数不同停止。
协调者核对两版 drain 代码后裁决：这是 STOP 时机选择了另一条既有合法路径，
不是驱动修复。旧 .38 原始记录已找到同一路径的佐证；归一化后 r98 等价，
获准从 r99 续未跑项，不重跑 r98 已过项。原始记录与第一次停止不改写。
r100又观察到空LAST路径的末OUTPUT未被客户端DQ；协调者补充裁决，
两条路径都允许仅最后一个OUTPUT尚未DQ，下述统一规则包含此补充。

## 原始观察

.39 身份为 `0ae8beaa56d3a798e8078c5f727c34ed3acafd9c`，release
`7.3.1-vim4-20261106.39`，build ID `76042204fe7ec153b8e42f77372d037b4d065740`。
同一无线屏蔽 RAM 包 SHA256：
`a204f1b03b3600f4cd507316d3cc2ba4be28699cf6820ab36539cf98dbb9f5e7`。

r98 已实测：节点编号与补采 .38 全同；stateless60/60、media8/8、JPEG60/60、
HEVC56/56；debugfs 两个预检入口通过，secure swap a0=0、overlay非零；DOS step=0。
全 I 首帧98304字节及三平面摘要与.38相同，status0、一个LAST；
SOURCE_CHANGE 在 CAPTURE 分配前消费，仅一次 CAPTURE STREAMON。

cip_B_NEC_3 输出5帧、748800字节，逐帧/整流MD5均与.38相同，status0、零ERROR。
整流MD5为 `1315714c7b3f3237b469259f66d9b7aa`。

| 观察 | .38 r92短流 / .38全集 | .39 r98 |
|---|---:|---:|
| OUTPUT QBUF / 成功DQBUF | 5 / 5 | 5 / 4 |
| CAPTURE QBUF / 成功DQBUF | 9 / 6 | 9 / 5 |
| 数据帧 | 5 | 5 |
| LAST | 数据之后的空缓冲 | 末数据帧自带LAST |

.38 短流：最后 OUTPUT ts4 在完成行204 DQ，DECODER_CMD在205，
最后数据CAPTURE在221，空LAST在227。GST明确记录两个平面bytesused=0及
`Empty last buffer, signalling eos.`。
.39：DECODER_CMD在200，末数据CAPTURE ts4在222带PFRAME|LAST，
最后OUTPUT未由客户端DQ；GST的LAST两平面payload均非零，完整5帧已交给appsink。
行号为既有拆行合并器保留的完成行号，不把线程PID或地址作为语义。

第一次停止发生在后续MERGE/TMVP、格式像素和独立132条之前；不将短流重复计入全集。
r98正常恢复正式fd41fb5、2372 proof通过、被动4K视频59.5688fps，计数9→307且
丢帧/冻结/丢包无新增；本窗零冷复位，任务累计仍1次。

## 代码与旧驱动佐证

协调者逐行核对 .38 的 `hevc.c:aml_hevc_device_run/aml_hevc_decoder_cmd` 与
.39 的 `aml_vdec_stateful.c:stateful_buffered_device_run/stateful_buffered_decoder_cmd`：

- STOP到达时最后OUTPUT仍在队列，drain分支冲刷pending，最后数据帧带LAST，
  OUTPUT在CAPTURE之后DONE。客户端见LAST后可不再DQ末OUTPUT。
- STOP在输入已被消费后到达，decoder_cmd冲刷后由m2m helper给空CAPTURE标LAST。
  客户端OUTPUT DQ与内核消费并不是同一时点。

旧 .38 的 **r94 / AMP_A_Samsung_7** 已走前一条路径：
末OUTPUT QBUF完成行283，DECODER_CMD行289，末数据CAPTURE LAST行331；
17个OUTPUT只DQ16个，17个CAPTURE均为数据帧。
末LAST两平面bytesused=4194304/2097152，17帧逐帧MD5正确。
原始ioctl SHA256：
`ded3ed128dc52dcf59961f3d9b6647baa8e6967a29c1553279315e2912239e44`。

对.38全部120条Success离线回放，87条为数据LAST、33条为空LAST。
每条ioctl/GST都重新核对原board-upload-files.json摘要。
另有旧CIP_A_Panasonic_3：空LAST、2个OUTPUT仅DQ1个，说明不能用客户端DQ数量
直接断言内核是否已消费。这个原始OUTPUT计数保留，不把它自动改成已全部DQ。

## 比较器边界与续跑

只在build编排中实现，未改受跟踪工具或内核。派生expected-normalized.json另存，
不覆盖原comparison、I420、CSV或第一次差异记录。

- 数据CAPTURE帧数、顺序、逐帧/整流MD5、字节、status0、零ERROR仍必须相同。
- Success必须恰好一个末尾LAST。用GST实际平面payload区分数据LAST/空LAST；
  空LAST只从CAPTURE成功DQ总数扣除，不计入数据帧。
- OUTPUT计数只允许差1，唯一未DQ的确实是最后一次OUTPUT QBUF；
  两条路径均可，但必须证明最后QBUF早于DECODER_CMD，客户端收到LAST后才STREAMOFF。
  按MMAP槽位每次复用匹配QBUF/DQBUF，
  不假设PTS递增；OUTPUT QBUF的timestamp未被strace展开，不能凭空补值。
- 其他QBUF/DQBUF计数、事件、帧数据或失败类别差异继续停止。
  旧Error不套用Success的CAPTURE drain归一化；OUTPUT末尾规则与结果类别无关。
  Timeout保持原判据，旧失败转成功仍停止。
- r98的合法尾部通过新规则；真实.37→.38的Fail转Success证据仍被拒绝为“不等价”。

按裁决，r99仅补MERGE/TMVP、H264三流/MPEG2四流/JPEG三样本和独立132全集。
r98已过compliance/全I/cip不复测；各窗身份、无线屏蔽、节点、debugfs/固件、DOS、
420秒恢复和2372 proof/视频门禁不变。第二次累计冷复位仍立即停。

## r100补充裁决

r99完成H264三流/MPEG2四流/JPEG三样本，硬件输出及逐帧摘要全同.38补基准；
独立全集完成52条：50 Success、1 Error、1 Timeout，均等价。
已知LTRPSPS_A_Qualcomm_1内核超时后结束该窗恢复，异常类别相同、输出仍0字节。

r100只到剩余第3批末条MAXBINS_A_TI_5：两帧、299520字节，整流MD5
`1386fb149ddc11bd5a1d9111879acfa4`，逐帧正确、status0、零ERROR。
OUTPUT由.38的Q2/D2变成Q2/D1，空LAST路径；按当时只允许数据LAST路径少1的规则停止。
最后QBUF完成行140、DECODER_CMD190、空LAST202，客户端之后STREAMOFF。
CAPTURE原始DQ为3，扣空LAST后仍为2个数据帧。

协调者确认：驱动消费OUTPUT与客户端DQ不是同一事件，旧CIP_A已有同形，
因此统一允许A/B下最多最后一个OUTPUT未DQ，其他计数保持严格。
离线重判MAXBINS、r98 cip、r99所有comparison及其内核超时证明均成立：
55份实际comparison加1份kernel-timeout proof，原始证据未改、码流未重跑。
至此独立全集已执行53条（51 Success/1 Error/1 Timeout），剩79条从r101继续。
r100恢复正式2372 proof/被动4K视频59.7844fps通过，零新增冷复位；累计仍1次。

## r101：旧Error的OUTPUT规则

r101推进至RAP_B_Bossen_2时再次因OUTPUT90→89个DQ停止，恢复后未重跑。
该条仍为Error，80帧、11980800字节、全部帧MD5、首错67和status1均与.38相同；
CAPTURE Q103/D82、3次DQEVENT、2个LAST、4次STREAMOFF也完全相同。
两次早期LAST对应重新建立CAPTURE，不能把Error强行套成Success的“一个末LAST”。

协调者补充：结果类别不影响客户端是否DQ最后OUTPUT，故同一OUTPUT规则也适用于旧Error。
CAPTURE Q/D、帧数/字节/MD5、首错、状态、LAST/ERROR计数及失败类别一律不归一化。
原始顺序已证明：最后OUTPUT序号89的QBUF完成行964，DECODER_CMD970，
最后OUTPUT没有DQ；最终OUTPUT/CAPTURE STREAMOFF在1008/1010。
早期LAST完成行398/830、对应CAPTURE STREAMOFF405/837，原始数目均保留。

离线重判及回看83份comparison和1份kernel-timeout证明后仍等价。
独立全集累计81条（74 Success/6 Error/1 Timeout），剩51条从r102继续；
不重跑RAP_B或已完成项。r101恢复proof/视频通过，无新增冷复位，累计仍1次。

## r102：首错之后的客户端控制调用

r102推进6条后在RPS_D_ericsson_6停止。40帧、5990400字节、全部帧MD5、
首错30、status1、无LAST、零ERROR缓冲以及两队列Q/D均与.38相同。
唯一差异为成功DECODER_CMD从0变1；第一次严格停止仍保留。

离线已确认：.38原始ioctl中根本没有该命令，包含失败调用也是0，不能写成旧命令失败。
.39首个poll error在GST相对时间2.571062071秒，`Finishing decoding`在2.573053315，
`Waiting for decoder stop`在2.573967665；其间唯一DECODER_CMD成功完成行519，
发生在首错交付之后。两侧内核错误串逐字相同：invalid reference lists，
POC847/type1/refs2/0及完整RPS参数相同，随后均为slice setup failed(-22)。

协调者核对两版decoder_cmd及m2m STOP无新增失败路径后，给出一般Error规则：
首个ERROR缓冲或queue error交付之前全部严格比较；之后仅有原始顺序证明的客户端
收尾控制调用（DECODER_CMD/DQEVENT/STREAMOFF/末OUTPUT DQ）不作为驱动差异。
数据、CAPTURE Q/D、首错位置、类别/status、LAST/ERROR个数和内核错误签名继续严格。
若旧命令曾返回错误则本豁免不适用，必须单列errno。

编排按真实ERROR/EIO或GST首错及finish调用区间建立保守证明；没有证明的调用仍严格。
RPS_D已离线重判，未重跑。累计87条等价（79 Success/7 Error/1 Timeout），
余45条从r103继续。r102恢复proof/视频通过，无新增冷复位。

## 证据

- build/hwdecode-parity/baseline38：expected.json（原冻结值）、expected-normalized.json、
  drain-decision-proof.json/log；run98/drain-equivalence-v2.json是派生裁决结果。
- run98/archive/results：原comparison/equivalence、GST/ioctl/kernel.log、compliance、
  firmware-load.json、eos-order.json、首帧及三平面摘要。
- logs/hwdecode-parity-r98：连续UART、身份、恢复proof与returned-video。
  UART SHA256 `6b07d981b4e51bc374f9418d62f284c40fcb0ca8a78c3d873704499617a3fcd9`。
- 编排和输入清单随每窗board-upload.tar归档，宿主缺文件/旧API拒绝、
  r72拒绝/r73与r75通过的真实拆行ioctl回放均有离线输出。
