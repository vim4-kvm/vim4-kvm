# 2026-11-06：r66 插件身份拦截与正式恢复冷复位

同一`.31`候选启动一次，在H.264插件身份门禁停止，compliance、10条H.264、
29次MPEG-2和HEVC全部未运行。没有绕过门禁或现场补跑。正式默认最终恢复，未部署。
候选源码/包身份与[r65](2026-11-06-vdec-r65-joint.md)完全相同。

## 失败与离线修复

我的临时计划转换仅替换字符串中第一次出现的r65根目录，导致GST_PLUGIN_PATH为
`r66/tools/official:r65/tools/plugins`。r65目录已按归档流程清理，GStreamer回退加载
`/usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstv4l2codecs.so`；实际Filename与私有
manifest不符，身份断言在发起解码前停止。不是驱动回退，也不是用户动过系统插件。

增量journal工具提交4d75fa4在排票前通过29项专项及590项全套检查（11跳过），
含游标失效、命令超时、截断JSON、新WARNING失败路径；原始日志均保存。
本窗初始和收尾两批journal成功、游标连续、没有采证超时；尚未验证逐码流长窗口。

离线修复将计划重定向放入vdec-window：逐个目录组件改写，处理冒号多项列表，
覆盖GST_PLUGIN_PATH、LD_LIBRARY_PATH、GST_REGISTRY以及嵌套路径键/值。
通用计划门禁拒绝任何不属于本轮的run目录（包括宿主video_check）。
新增真实失败回归，确保旧目录残留会拒绝；protected_files仍与正式baseline逐项相等。
r67计划已生成并离线校验，视频脚本复制到本轮目录，无旧运行路径。
路径修复后30项vdec专项与591项全套检查通过，11项跳过；原始输出为
path-tests.log和main-tests-path-fix.log。

## 启动时间线

FIFO1389，一次候选启动；因身份失败请求正常恢复一次，之后只被动观察两次自然启动。
以下间隔按连续UART主机monotonic时间戳，从Linux version所在块到T7 ROM所在块计算，
不是最后一条内核时间戳，也不等同电气RESET边沿。

| 本窗顺序 | 内核/路径 | 结果和距Linux起点 |
|---|---|---|
| 1 | .31 RAM候选 | 无非请求复位；正常恢复reboot在26.073秒回到ROM |
| 2 | 正式20261105 eMMC，唯一请求恢复 | 冷复位7.239385333秒；末条`[4.920638] brcmf_c_preinit_dcmds`固件身份 |
| 3 | 正式20261105 eMMC，自然恢复1 | 冷复位7.257657708秒；末条`[4.828865] brcmf_c_preinit_dcmds`同版身份 |
| 4 | 正式20261105 eMMC，自然恢复2 | 成功，SSH/proof/视频通过；Linux起点monotonic 675709688275875 |

两个冷复位前无已观察panic，末条Wi-Fi日志不是归因证据。不改MMC/PWM/ADLA/PD。
相对r60的正式eMMC累计下界≥17次/2复位，新增r61/r63/r64/r65四次无复位恢复，
加本轮三次/两复位，已覆盖下界为**≥24次/4复位**。RAM正式对照仍2次/1复位，
`.28`既有9次/2复位不变；`.31`在r65/r66共2次/0非请求复位，不据小样本推稳定性。

## 恢复与证据

最终正式7.3.1-vim4-20261105，2372项保护文件核验通过；4K视频推进299帧、
59.769fps，丢帧/冻结/丢包无新增。helper重传，候选及owned固件按归属/哈希清理，
777文件归档Mac核验后删板端目录。没有追加票或修改默认启动项。

原始资料：`build/hwdecode-parity/run66/`中的journal-tests.log、path-tests.log、
main-tests.log、board-upload.tar及哈希清单、archive/results/插件身份和两批journal；
`boot-timeline.json`保存逐启动起点/间隔/末条日志；`logs/hwdecode-parity-r66/`
保存连续UART/主机时间戳、passive-recovered、最终proof、视频与complete。

r67沿[r66计划](2026-11-06-vdec-r66-plan.md)，同.31不重建，只在本修复和记录获审、
协调者push后排单张30分钟sampling票，一次候选启动；当前未排票。
