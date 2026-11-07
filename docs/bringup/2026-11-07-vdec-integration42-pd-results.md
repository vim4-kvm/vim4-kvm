# 2026-11-07：integration42 在固件 PD 默认下续验

本轮沿用 `.42` 的源码、内核及模块二进制，只将已采用的 `fusb302` 黑名单加入无线屏蔽 RAM 变体。
r113 首次完成 K9 全生命周期：三方自然绑定、编码器在位时三个解码节点 busy-open、
解码后编码器重载及推流恢复均通过。其他格式十份输出与 `.38` 同包补测逐字节一致。
HEVC 8-bit 132条全部完成：**127 Success / 0 Fail / 3 Error / 2 Timeout / 0 Not run**，
旧120条Success全部保持，七条旧Error转为Success。本记录不代表部署或合入批准。

## 身份与保护边界

源码 `3facfaa37284f7193508c2a16fbf5162c6242616`，release `7.3.1-vim4-20261107.2`，
build ID `fa5a9fa53dc3f84802722702f18623730ab81d83`，构建证据沿用
[原 .42 记录](2026-11-06-vdec-integration42-results.md)，未重新编译。
原无线屏蔽包 SHA256 `5be8eca765f2fda0ea2d7008cb0a9dbad959196dfdd9527d3fd4edcfedce7843` 不变。
新包 SHA256 `7a32b63ceaeaa0f460015a2f545344ee3ff2e0833999611dd8f9a08096d29457`：
仅 `extlinux.conf` / `trial.json` 变更，其余2357文件内容相同。
候选参数是合并后的 `module_blacklist=brcmfmac,hci_uart,btbcm,fusb302`，保留既有 SDIO/BT 屏蔽。

每窗恢复正式 `fd41fb5` / `7.3.1-vim4-20261105` / `bdbfa439f298e92b5bad092528d11119a974f262`，
使用[正式 B 状态的2372项清单](../../packaging/kernel/releases/7.3.1-vim4-20261105/pd-baseline.json)，
SHA256 `0514bdab3aac0a0c9f0d9fa63be8df94d50aff533c7890a1608d23bcc9333126`。
本任务不改默认、Image/FDT、固件原件或 saveenv；不发HID、不切EDID。
Mac→USB-C功率计→板子拓扑保持，未采物理VBUS，不据无复位小样本推断根因。

## 两次安全停止及一次性离线审计

r111 的 `cip_B_NEC_3` 实际5帧、MD5及逐帧参考均通过，比较器却因冻结 `.39` 报告缺少
`output_tail_contract.capture_last_count` 而停止；不算像素或驱动回退。
按协调者裁决从原始 ioctl 直接计数，并记录来源文件SHA；没有用 drain 的LAST计数推断。
冻结报告不追改，比较器只在缺字段处应用独立派生元数据，不能覆盖旧值、结果或像素。

一次扫描全部132条HEVC、H264三流/MPEG2四流/JPEG三样本及三个compliance结果：
缺82个 `output_tail_contract`、51个 `drain_contract.streamoff_lines`、7个 `error_cleanup_contract`。
两个旧内核Timeout（LTRPSPS_A、WPP_D）的完成字段不能派生，单列未覆盖；只记录原始已完成DQ的LAST计数。
[独立派生元数据](data/2026-11-07-vdec-integration42-derived.json) SHA256
`fab081c6e3e9b991d35e66ed68d02738980810a0e9a457db3d5a2ce6998dd7a2`，
来源证据均先与原归档清单核SHA；120条旧Success自比较及像素/LAST/ERROR反例、r111实际失败回放通过。

r112 的优先K9实解码入口把首AU文件错配给完整流SHA，门禁在解码前拒绝。
首AU5999字节、完整流71437字节、VHDR71565字节分别绑定各自字段后再准备新目录，未现场放宽或重试。
r111/r112均已恢复2372 proof及被动4K视频；其未执行部分不补算通过。

r113排票前逐项验算[335行文件对应表](data/2026-11-07-vdec-integration42-file-pairs.csv)：
包括上传文件、首AU/完整流/VHDR、各格式输入及旧实际输出。
入库副本只将CRLF换为LF，原宿主审计CSV不变；摘要分别记录两份SHA，行内容一致。
132份 `frames.json` 均与封存 `frame_md5_sha256` 一致，帧数和逐帧数组与封存计划一致，
流名、输入路径及发布者MD5与conformance包条目一致；输入SHA及长度逐项通过。
没有重新生成参考YUV。JPEG保留软件参考与硬件已知舍入差异的区别；MPEG2比较使用旧实际 `.out`，
不将ISO参考输出冒充硬件基准。固件和系统插件在只读FIFO1632复制到宿主核SHA，未改板端文件。
检查原始输出位于本工作树 `build/hwdecode-parity/integration42-pd/{audit113,check113,k9-offline113}.log`。

## r113：共存、PM、格式与首批

自然启动后Wave5、JPEG encoder、decoder同时绑定，`fe320000-fe32ffff` 仅JPEG登记，
decoder无region申请错误。原decoder绑定在编码器卸载、实解码、编码器重载过程中保留。
三个解码节点在编码器活动时均返回EBUSY。busy-open前/中/后三段各600次Wave5 CAPTURE DQ，
均约59.998fps；两次重载后的统计也各600次、约59.998fps，零ERROR、零丢事件，
每段应用PID保持不变。重载probe成功证明独占运行期租约已释放。

prime先完成全I首帧98304字节及参考SHA，再验证decoder suspended后重载编码器；
完整解码段结束后再做一次重载和推流验证。genpd中decoder与平台runtime_status均suspended，
共享域由 `fe09a000.temperature-sensor`（无runtime PM）保持on，符合已审判据。

stateless media 8/8、stateless 60/60、JPEG 60/60；HEVC两次56/56。
全I像素/EOS/status0/初始SOURCE_CHANGE先于CAPTURE建立通过；三条HEVC短流逐帧参考通过。
H264三条Success，MPEG2 sony-ct1/ct2仍为已知参考Fail、ct3/mcp为Success；JPEG三样本保留已知舍入差异。
十份硬件输出长度、整文件SHA和逐帧SHA均与r97补测基准一致，未借旧窗口代替本轮结果。
首批18条为15 Success/3 Error，七条旧Error转为Success，已跑的旧Success无回退。
RPS_D已解码POC847，已交付的49帧MD5均与参考一致，但参考共68帧，首个未交付帧索引49，仍为Error。
RAP_B的80帧像素及status0/LAST通过，事件顺序判据失败，仍计Error。
VPSSPSPPS首AU因invalid RPM被拒绝，首个ERROR后没有已完成的后续OUTPUT DQ；
另一个已排队AU在收尾时仍pending，不把它当已消费或成功隔离的证据。

本工作树 `run113/archive/results/k9/` 保存before/prime/restore/after/restore-final/after-final，
原始trace、绑定inode、PM、iomem及统计均归档。正式恢复2372项及被动4K59.57fps通过，
1533项归档逐SHA核对后才清理板端任务上传。r111–r113共6次Linux启动、零冷复位。

## 全集收口与窗口恢复

范围为既有 JCT-VC-HEVC_V1 的 Main/Main Still 8-bit 132条，官方parser、原系统stateful插件，
逐帧MD5及整文件MD5对发布者已匹配参考；没有新增下载或修改驱动。
[132行逐流总表](data/2026-11-07-vdec-integration42-pd-full.csv) SHA256：
`f071330e29d4e75ac510328a2b08bb50d3c3f0f664a1d3b0f7da02143e2e201a`。
[摘要及证据索引](data/2026-11-07-vdec-integration42-pd-summary.json)保留每窗UART、归档清单、
正式身份SHA、恢复时长、逐启动账本及K9统计原文件SHA。

| 窗口 / FIFO | 本窗正式全集结果 | 恢复SSH就绪（秒） | 恢复被动4K fps | 核SHA归档项 |
|---|---|---:|---:|---:|
| r111 / 1630 | 0；旧报告缺字段停止 | 26.79 | 59.55 | 887 |
| r112 / 1631 | 0；首AU配对门禁停止 | 29.50 | 60.16 | 817 |
| r113 / 1633 | 15 Success、3 Error | 30.21 | 59.57 | 1533 |
| r114 / 1634 | 112 Success、1 Timeout | 30.62 | 59.58 | 2911 |
| r115 / 1635 | 1 Timeout | 26.84 | 59.55 | 888 |

每窗均是一张30分钟sampling票、一次无线屏蔽候选启动，420秒恢复时间保留；
每窗正式恢复2372项逐一通过、视频帧数推进，归档核SHA后删除板端本任务上传及归属明确的候选/固件副本。
窗间按正式启动monotonic时戳等足300秒，入场再核boot_id/uptime；未持票空等。
最后队列及板/构建锁均空闲。全部五窗共10次Linux启动、**零冷复位**：候选5/0、正式恢复5/0；
r110采用旧PD状态的3次恢复复位仍保留在历史记录，不混入本轮额度。
没有物理VBUS测量，不能从这一小样本证明PD是唯一根因。

七条新增Success：SLIST_B、SLIST_D、BUMPING_A、NoOutPrior_A/B、OPFLAG_B/C；
原120条Success全部再次运行并通过严格像素及既有队列合同，不追改冻结 `.39` 报告。
剩余失败不重试求通过，分别记录：

| 流 | 结果 | 实际边界 |
|---|---|---|
| RAP_B_Bossen_2 | Error | 80/80帧、总MD5、status0及LAST通过；出现3次SOURCE_CHANGE/CAPTURE建立，现有非DRC事件合同拒绝 |
| RPS_D_ericsson_6 | Error | POC847已解；前49帧MD5一致，68帧参考的后续19帧未交付，无LAST/status0 |
| VPSSPSPPS_A_MainConcept_1 | Error | 首AU invalid RPM、1个OUTPUT ERROR、零帧；另1个已排队AU未完成DQ，不声称后续AU已消费 |
| LTRPSPS_A_Qualcomm_1 | Timeout | 与旧基准相同的内核decoder timeout、零输出，r114立即结束解码并恢复 |
| WPP_D_ericsson_MAIN_2 | Timeout | 与旧基准相同的内核decoder timeout、零输出，r115立即结束解码并恢复 |

两个Timeout分别独立收尾，没有在同一启动里继续操作可能仍有DMA的设备；未将它们归一化成普通Error。
失败I420及逐流kernel/GST/ioctl留在 `run113/114/115/archive/results/`；
各原始 `board-upload.tar` 和清单保留，板端只在归档核对后清理。
没有观察到新增WARN/Oops/BUG/DMA/IOMMU诊断；本轮是生产配置功能验收，不代替调试锁/内存检查，
KVM统计不覆盖端到端延迟。本轮H264/MPEG2是指定短回归，不宣称各自标准全集或5.15 parity。

离线检查覆盖实际上传配对、缺helper/错误保护清单拒绝、EBUSY/错误errno/无活动/错误队列过滤、
旧Success回退拒绝及原始ioctl派生回放；离线全套616项，599通过、17跳过，原始输出保存在
`build/hwdecode-parity/integration42-pd/final-tests.log`。未部署、合并、push或改默认；板子停在正式B状态。
