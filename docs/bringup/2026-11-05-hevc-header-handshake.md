# 2026-11-05：r70 后 HEVC 首个 slice 握手定位

接续 [启动差异表与下一窗短清单](2026-11-05-hevc-start.md#r70-结论与差异表补充)。
本任务只读 t48 提供的 r70 归档，未碰板。WAIT_FLAG=0 的候选没有打通首帧；
下一候选把首次格式探测移至厂商手动 NAL 搜索路径，以提前暴露 IRQ/主机应答边界。
不是已证实的修复，也没有证据表明自动模式缺少某条必须发送的头命令。

## 固件与主机的可见协议

厂商路径相对 common_drivers 的 `drivers/media_modules/frame_provider/decoder/`，
版本同启动记录；微码源码不可见，下面只陈述主机调用及寄存器约定。

| 边界 | 厂商证据 | 本驱动及结论 |
|---|---|---|
| 初始命令 | `h265/vh265.c:14268` 每次run写ff，之后CPU reset/start；`:721` 定义00为IDLE | 当前相同；r70 ff被清为00，00不等于“有一个待应答的slice事件” |
| 搜索选择 | `:803` 注释：NAL_SEARCH_CTL bit0=0自动头解析；bit0=1手动。`:12335` 提供手动1和正常自动8/4/0 | 当前0x200008为自动检查VPS/SPS/PPS/I slice；没有逐头IRQ属于此模式允许的行为，不能据此单判mailbox坏 |
| 手动逐头 | `:11109` 收09，读scratch J的NAL；回复VPS01/SPS02/PPS03/slice04或discard f0，再写MCPU_INTR_REQ=4 | 已有 `h265_irq_thread`/`h265_command` 实现；候选首次格式未知时选1，逐头显示事件和应答 |
| 切回自动 | `:11265` VPS/SPS/PPS和起始slice齐备后search=2，再config_decode_mode，回复所选命令 | 本驱动同样在首个有效IRAP切回自动；手动只选择NAL动作，语法仍由固件解析 |
| slice参数 | `:11311` 收08才读RPM或RPM_CMD_REG，建图像/参考，`:11650` 回复05并写MCPU请求 | 当前首次header pass在08后交SOURCE_CHANGE并停机，CAPTURE就绪后重投同AU；r70没有08，因此不能靠预发05绕过 |
| 路由 | `:12325` mailbox0 clear=1/mask=1；`:12301` mode高字节0x80选MBX0；`:11746` ISR清mailbox再读状态 | 当前mask、mode相同；r70只看到Linux IRQ不增，尚未读IRQ_REG/FIQ_SEL，不足以区分固件不报事件与路由不通 |
| AMRISC唤醒 | `:11306,:11653` 主机发布命令后写MCPU_INTR_REQ=4 | 这是ARM→AMRISC请求，与mailbox的AMRISC→ARM事件方向相反；不对IDLE盲发请求 |
| RPM/调试应答 | `:5024` 正常写RPM DMA地址；`:3079` 寄存器RPM流只在特定调试模式下读F的bit16并清零；`:11788` debug G非零按tag处理 | 当前走DMA RPM，F写LMEM地址，G初始0；不擅自将F当RPM请求ack。新增G/H、F、RPM/INFO和LMEM DMA读回，先证明是否命中调试路径 |
| WAIT | 厂商新AU初始写0；主机仅续帧/完成等路径改值 | r70启动后由固件改1，单凭此值不能认定主机写坏或强行持续清零 |

`hevc.h` 的 H265_DECODE_MODE/CUR_NAL_UNIT_TYPE 共用J、RPM_BUFFER/DECODE_INFO
共用1、DEBUG_REG2/DECODE_MODE2共用H。启动写入与运行读回语义不同，日志按原值记录。
PC在a1d–a1f间变化、MPSR=5不能从主机源码推断具体等待条件；debug tag、parser状态
和头应答序列才是下一窗要取得的证据。r70相同输入到IDR说明自动NAL识别有进展，
不证明SPS/PPS/RPM或slice语法已正确解析。

## 候选、诊断与验证

内核提交 `857b5a2e2442f8d17cb024869b4e1aba035c84aa`，基于 `f065c6712f7e…`。
`hevc.c:h265_prot_init` 仅在format_known=false选手动1；既有handler逐头应答，
遇首个有效slice后切2；获知格式后的解码重投仍选自动8。bit21等其他差异保持。
没有新模块参数、IRQ注入、轮询fallback、内核码流解析或伪造SOURCE_CHANGE。

`h265_dump_start` 追加IRQ_REG、FIQ_SEL、AMRISC group/mask/request、parser
INT_STATUS/core、debug G/H、RPM/INFO、LMEM F/DMA、STREAM_LEVEL，在启动各阶段、
每次头应答后和timeout记录。寄存器地址对照厂商 `include/regs/dos_registers.h`。
只读原值，没有写FIQ或IRQ寄存器；IRQ_REG读回的完整硬件语义未证实，零值本身不排除路由问题。
handler已清mailbox，所以header-reply时IRQ_REG为零也不能当丢事件。

通过 `tools/board-queue run --heavy --who vdec-hevc`，复用本任务的kunit/module O=：
arm64 QEMU 25/25；`make O=…/module W=1 -j8 modules` 编译链接通过，五个既有
KUnit missing MODULE_DESCRIPTION警告，修改文件无编译诊断。没有新增纯逻辑，
不增加写值/寄存器mock测试；真实IRQ和头状态机需板验。生产整包与逐提交门禁仍留合入评审。

| 产物 | SHA-256 |
|---|---|
| hevc.c | `825d3efc63766c7e2066669dc07c44dddd861da376bbf5f498b0901303d7c6d2` |
| hevc_regs.h | `fc9a75b44f1d00d8c92defd123f98f9ef99c796dce3a026398d19aa4577dd183` |
| 最小验证配置模块，不能混装integration | `539b00d74865370d67d590deb85565f322db552b2ca6fe2c6a69f9649853f25d` |

Mac证据在 `build/vdec-hevc/r70-evidence.log`、`source-r70.sha256`、
`kunit-r70.log`/`kunit-r70-qemu.log`/`result-r70.json`、`module-r70.log`/
`module-r70.sha256`、`vm-validation-r70.tar`，VM同名构建根保留原件。
队列及主仓库全套测试原始输出在 `logs/vdec-hevc/heavy-r70.log`、`repo-tests-r70-final.log`。

## 下一窗分流与判停

只跑带有效全I输入的compliance，通过后再捕获同样本首帧，逐平面对软件参考；
执行顺序/身份门禁见启动记录短清单。首次search应0x200001，期待09/32→01、
09/33→02、09/34→03、09/20→04，随后08/RPM及SOURCE_CHANGE；允许after-start
快照已进入运行态，不要求它保持启动mode或初始WAIT。

- 首个VPS就无09/IRQ：自动解析还未进入slice，优先看mailbox/FIQ/AMRISC和parser状态；
  raw IRQ有值而Linux不增支持查路由，不能仅凭raw IRQ=0证明IRQ未置位。
- 有09但头应答后停：看command/status/request与下一NAL，定位主机请求或固件头解析。
- 四个头握手正常但无08：IRQ通路已有证据，重点转向slice解析/RPM/LMEM或debug等待。
- 有08而无正确画面：单独归入参数/重建/输出，不能继续称首个头IRQ失败。

任何WARN/Oops/复位/超时/错误帧/停机失败即停HEVC，不换输入重试，保存三阶段、
header-reply/timeout快照、UART/IRQ和AXI停机证据，由t3k统一隔离/恢复。不同时修改
另一寄存器继续猜；诊断关闭复验及更大码流覆盖留后续。
