# 2026-11-06：.33 integration 离线候选与诊断窗口计划

本轮只离线构建和准备，**未排板票、未部署**。申请一张FIFO sampling票，目标15分钟、
上限30分钟，只启动一次候选。窗口等待协调者批准；正式默认仍为
7.3.1-vim4-20261105（fd41fb5），不改变默认启动项。

## 源码与封包身份

独立工作树`/home/deepdream/src/linux-7.3-vdec-integration33`从与`.32`相同的基线
5dd4f646bcd8af7b9749bf1396c2a9a2ebf04e5f依次no-ff合入：

1. HEVC `857b5a2e2442f8d17cb024869b4e1aba035c84aa`：首次格式未知时手动NAL握手，补寄存器读回。
2. quiet-power `efe8d3689a77ec36a3d02556bb6601cb9a22acef`：保持`.32`降噪。
3. MPEG-2 `1c711971d464cff398183e5873686f46b9161a09`：保留aaec509单向参考处理，新增请求失败诊断及KUnit。

三次均无冲突，最终源码`effc7d77e51fdf8cc303bb02a301d343be56f7c3`，tree
`ef7d69090dfec50c2132ff5230edb771fe9cc302`。不含其他HEVC实验或未提交草稿。
相对`.32`只改aml_vdec.c、hevc.c/hevc_regs.h、mpeg12.c及mpeg12_kunit.c；
MPEG-2新增提交是诊断，不是已证实的像素修复。未改binding或DTS。

生产O=复用`/home/deepdream/build/vdec-sequence/kernel`；模块/KUnit复用本任务原目录，
未动共享visl。生产配置与正式kernel.config逐字节相同，已有CONFIG_DYNAMIC_DEBUG=y。
构建、资产、执行草稿与原始检查输出保留在`build/hwdecode-parity/integration33/`。

生产W=1 Image/DTB/modules、外部模块和统一封包完成；前后cmp确认正式配置未变。
VM产物在`/home/deepdream/build/vdec-sequence/bundle33/`，Mac副本与源逐文件哈希相等。

| 产物身份 | 值 |
|---|---|
| release | `7.3.1-vim4-20261106.33` |
| GNU build ID | `0055df24ab8980d7e8f1adb8ce056f5fd1a94326` |
| RAM candidate.tar SHA256 | `9ac10d6b278eb9e845484d63536eb2cbc935f019e9dfc1517f902647c327329c` |
| package manifest SHA256 | `a5f776af5dbd1d4dc3760e73067cba299028f79dadb117bee70df530facb74e0` |
| config SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA256 | `2a532901fcee9c2a1411fa4bd883c3739f19fe0f2b8b1cd4150bd8ed560d6da9` |

`artifact-identity.json`保存复制源及实际哈希；候选锁为sources33.toml，正式锁未改。
`finalize.py`实际核验完整RAM包、源码身份、baseline身份及文件清单，计划的
protected_files由baseline.json生成，2372项逐项相等；计划路径已改为r71且通过
旧run路径拒绝检查。baseline为r70恢复核验过的正式包，本轮未访问板子更新它；
入场仍须重新实测全部proof，不把离线相等视为当前板端状态证明。

r70码流归档和16个工具/插件文件逐项哈希匹配；首AU/参考沿用原校验身份。
执行草稿保持--execute/--at-board门禁，window.py默认离线核验成功。
MPEG-2诊断门禁用r70实际ERROR ioctl回放，确认缺失/部分/完整诊断、无ERROR及
损坏时间戳路径，日志见diagnostics-check.log；不同码流间不复用同时间戳的旧诊断。
原始封包及离线检查见build33.log、copy-artifacts.log、offline-validation.log、
window-offline.log。

分支尖W=1完整modules目标实际编译链接通过，arm64 QEMU KUnit实际29/29通过、
无跳过，包含sony_zero_timestamp_anchor；原始输出为tip.module.log、tip.kunit.log/json
及tip.qemu.log。模块验证产物SHA256为
`76feaed26ac381ee43803852587940da3004b70223b70058dad8e70c7b5eb53d`，
不用于候选混装；封包实际生产未压缩模块SHA256为
`5952915895af639de98f7ad0771639c2cb7526c948063b9db799d68406a83f55`。
两次完整W=1日志各有1366条warning行（含kernel-doc），均不在解码目录，不能写成
全树零警告；warning-summary.json保留计数。按迭代门禁未重复逐提交sparse/内建/
strict系列审查，本轮未改binding/DTS，未另跑schema。硬件IRQ、像素及恢复仍待板验。
主仓库提交前全套实际运行595项，OK（11项跳过，不计通过），原始输出为main-tests.log。

## 顺序、预算与统一判停

顺序：入场 → stateless compliance和DOS step门禁 → H.264三条 → MPEG-2四条 →
HEVC有效输入compliance/首帧 → 正式恢复、视频、归档清理。

| 阶段 | 软预算 |
|---|---:|
| 入场、上传和启动 | 180秒 |
| stateless compliance | 90秒 |
| H.264三条 | 60秒 |
| MPEG-2四条和诊断核对 | 180秒 |
| HEVC短清单 | 180秒 |
| 恢复、归档、视频 | 420秒，绝对保留 |
| 可借用余量 | 690秒 |

单条Fluster30秒；HEVC仅在剩余≥3+7分钟时开始，捕获首帧上限30秒。软预算可借用，
恢复预算不可借用；不足的段明确记未运行。沿用进程树watchdog、增量journal游标和
采证失败门禁，不每条重复拉全量journal。

入场uptime≥300秒、连续UART无复位、前后boot_id一致；核正式proof、2372项保护文件、
视频、空间和宿主私有浏览器导入冒烟。候选身份以SSH的release、GNU build ID、
APPEND与新boot_id逐项匹配为准，UART负责复位/启动计数和时间线。

像素Fail保存后继续清单；Timeout、BUG/WARN/Oops、设备/DMA/停机异常或采证失败即
收尾。冷复位不追加候选启动，最多观察两次自然恢复，失败停下交协调者。
HEVC失败只停止HEVC并恢复，不抹去前面格式的结果，不换输入或改寄存器重试。

## compliance和H.264

关闭aml_vdec.c、aml_vdec_hw.c、h264.c、mpeg12.c、hevc.c的dynamic debug并保存状态。
stateless media/video带流compliance须通过；增量journal的DOS step行数须为0，
非0保存现场并停止后续测试。WARN/ERROR不被过滤；不替代调试锁和内存验收。

H.264使用r70同一官方parser/插件：MR3_TANDBERG_B验证存储归属，BA1_FT_C覆盖多slice，
cabac_mot_picaff0_full覆盖隔行。三条都是r70通过项；保留MR3输出及trace，出现Fail
标记回归，不扩大采样。不是全集复验，不改写r65+r69的129S/1F/5KU统计。

## MPEG-2请求失败采证

按[拒绝追踪清单](2026-11-06-mpeg2-r70-rejections.md#下一窗两条-sony-加两条对照)，
依次跑sony-ct1、sony-ct2、sony-ct3、mcp10ccett。固定r70 mpeg2-fixed用户态，
gst-inspect路径、ldd解析和SHA全部匹配才运行，不符跳过MPEG-2而不阻塞其他格式。
不修改系统插件。

该段启用`file mpeg12.c +p`和`file aml_vdec.c +p`，保留实际dynamic_debug/control，
确认rejected/completion/request failed三个诊断点都开启；aml_vdec_hw.c保持关闭。
段后撤销MPEG-2/公共worker规则，HEVC段才开启hevc.c。

保存完整增量内核日志、ioctl控制、QBUF/DQBUF、I420和ISO输出。对照必须继续通过。
Sony分别应有60/24显示帧；ERROR时间戳按ns=1000/2000对齐诊断，区别于ioctl的
tv_usec=1/2。逐条关联prepare/reference/canvas拒绝或微码out/info/errors，
单列显示帧0/1的零帧及ISO误差；帧2起逐字节对比r70，不提高容差。

Sony若ERROR没有对应时间戳的请求诊断，保存rejection-evidence.json，停止MPEG-2
子任务，其余项列未运行；核模块身份和dynamic debug，不继续猜参考策略。
诊断提交预期不改像素，ERROR消失也需解释，不能事先宣称修复有效。

## HEVC手动头握手与首帧

按[手动NAL短清单](2026-11-05-hevc-header-handshake.md#下一窗分流与判停)，
只开hevc.c +p；预检固件/电源，记录IRQ起点。使用r70同一全I hevc-intra.vhdr，
首AU5999字节、skip=0；不换输入。首次search预期0x200001，观察
09/32→01、09/33→02、09/34→03、09/20→04，随后08/RPM及SOURCE_CHANGE。
after-start快照可已进入运行态，不要求它保留初始mode或WAIT。

保存before/after reset、after-start、header-reply和timeout快照，包括mailbox、
FIQ/AMRISC、parser、debug G/H、RPM/INFO、LMEM及STREAM_LEVEL，结合Linux IRQ计数
判断停止在哪一阶段；raw IRQ=0不单独证明路由有错。

有效输入compliance通过后才捕获同首AU一帧，按`.32`已锁定的256×256 I420参考
逐帧/三平面比较，尺寸与stride一并保存；不等只离线量化误差、不放宽容差。
任何超时、WARN/Oops、错误帧或停机失败即停HEVC，保留AXI停机证据。
P/B、诊断关闭复验和全集未安排，不把短清单通过扩大为HEVC验收完成。

## 恢复与交付

沿r70/r60流程返回正式默认，清理helper前先检查，不在则从仓库重传。核全部保护
文件后仅清本任务候选/固件，按owned清单和哈希确认；正式模块和应用数据不动。
验证视频推进、丢帧/冻结/丢包，归档Mac逐项核验后删除板端本轮目录。

记录通过、Fail、Timeout和未运行、各次Linux启动/冷复位间隔、模块/插件身份、
原始日志与输出哈希。窗口结束清本任务O=的对象文件，保留封包和证据。计划只供
审核，未授权排票。
