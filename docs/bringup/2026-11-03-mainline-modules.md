# 2026-11-03：uhd7 三模块持久安装与四应用会话验收

三个模块已持久安装并正常重启，实际加载身份匹配。One-KVM AVC/HEVC 和 NanoKVM
网页均通过 4K60 短窗。首窗 JetKVM 未出首帧，后续补测通过 JetKVM 两浏览器接入、
PiKVM 和恢复后的 One-KVM；UU 官方客户端接收报告通过。发现并修正临时测试编排的
HTTP 就绪门禁，产品代码未改。两个窗口累计持板 659.573 秒，板上保留本次模块，正式远端待协调者推进。

## 离线来源与构建

主仓输入 `403e0e29b14a`。八个用户态子仓均快进至 workspace.toml 的正式远端提交，
工作树干净。内核本地 `vim4-kvm-7.3` 从旧本地提交快进至
`4111568841bd83ca33b9b9a044ed9a7077f95004`，较正式 origin 的 `52b95c8493264` 多 16 项。
协调者转交的 review-bsbuf 审查结论为无必须修改项。
HFR/YUV 的硬件资格沿用[前一窗口](2026-11-02-hfr-yuv-window.md)，
BSBUF 满中断到恢复时延仍缺实板证据，见[第三轮记录](2026-11-02-wave5-refresh.md#第三轮cpbvbv-与低延迟)。

在 tools/vm 登记的 mainline-merge 工作树、独立输出目录进行三模块 W=1 构建。
配置与正式 uhd7 逐字相同，沿用其 vmlinux 和 Module.symvers，三个模块均保留 BTF。
vermagic 为 `7.3.0-vim4kvm-uhd7+ SMP preempt mod_unload aarch64`。
正式 vmlinux BTF SHA 为 `99f681a065c24ce09478be6ad52e728e77e44db32014d5776cec5e79bc2dcddc`。

| 模块 | 未压缩 SHA256 | GNU build ID |
|---|---|---|
| t7-hdmirx | 85f2437f522a240f202f7a37fe542c63704eb24765eb704baa183adc792458b2 | 21120d73455c9218820ddaf9fd0a36af19a2a805 |
| t7-vdin-test | cae6dd2dbd8af3ce2d6c4448b1b84cfcff7f3033b0cc2ad5c39a0d843f2a4f7f | 77cb81557f27057cf530217d3f0a693fbd28568f |
| wave5 | 5b197d412d86cf9326df425ede837a7c3af11711d4f28397a768a6a410e36ce1 | 83e8eb222b68f512e7515f410b8c0497df35cf61 |

导入符号数为 57/168/207，联合正式符号表与候选导出检查，未解析为零。
VDIN 新导入 `t7_hdmirx_vrr_rate` 和 `t7_hdmirx_yuv444_format` 由新版 HDMI RX 提供，必须成套安装。
12 个 Wave5 和 12 个相关 HDMI RX/VDIN 宿主测试程序通过。
归档 SHA 为 `9170d6458c75c3d56d49b5ac7fac9c786d0c4774b6c44792be6dcf0d50e0768c`。

## 安装与重启

FIFO 717，票据 `f0049276293d4c61a6254273c7026577`，持板 243.117 秒，含恢复。
先核对 kernels.json 两个登记项的所有产物哈希，再将三个 ko 按现有路径压缩为 xz，
逐个验证解压内容哈希、替换、depmod，并更新登记中的模块和依赖文件哈希。
当前 FullKvm 启动项没有 INITRD。sync 后正常重启，没有新建回退副本。

重启后完整登记哈希、三个模块解压 SHA 和 `/sys/module/*/notes/.note.gnu.build-id` 全部匹配。
boot ID 为 `ee91f4dc-fcc7-4d22-a14a-a5550d079550`，taint=4096，与外部 GPU 模块基线一致。
one-kvm、vim4-manager、vim4-kvm-hdmi、vim4-kvm-gadget 均 active，UDC configured。
panic=20、panic_on_oops=1、RuntimeWatchdog=30s、RebootWatchdog=60s。

## 首窗网页结果与阻塞

测试使用本机 Chrome、SSH 转发管理器与应用网关，真实产品页面，未发送 HID。
接收画面为源端 Chrome 低运动桌面，没有运行运动图样，未测试声音。

| 网页 | 首帧等待 | 约 10 秒新增解码帧 | 尺寸 |
|---|---:|---:|---|
| One-KVM AVC | 1210 ms | 600 | 3840×2160 |
| One-KVM HEVC | 861 ms | 600 | 3840×2160 |
| NanoKVM | 1737 ms | 600 | 3840×2160 |

三窗口 framesDropped、packetsLost、freezeCount、pliCount 增量均为零。
保存了原始 getStats 和网页截图。首帧时间包含页面加载与协商，不能当端到端显示延迟。

经管理器 `/api/select` 切 JetKVM，vim4-kvm.service 启动，但页面等待 45 秒未取得
framesDecoded>0。测试在第一观看者阶段失败，未启动第二观看者或后续 PiKVM、UU。
目前证据不足以区分页面、协商和视频管线原因，也未证明由本次内核差异引入。
双观看者编排仅保存在本机忽略目录，未修改产品代码。

finally 经同一管理器 API 恢复 One-KVM，确认原 H.265、Custom 40000 kbps，服务与 UDC 正常。
恢复后没有再次开网页验证，恢复画面推进仍待后续窗口补验。
本次内核日志未见 WARN/Oops/BUG/Call trace；simple-framebuffer 的 clock 4/-5 错误在安装前也存在。
停止采样、释放票据并结束 SSH 转发。

## 补测与测试编排修正

协调者授权继续诊断，取得 FIFO 718，票据 `ae06bba8564d4356ad424f4d911618ca`，
持板 416.457 秒。内核模块和用户态二进制均沿用首窗安装状态，期间没有构建或部署新程序。
实取 JetKVM SHA 为 `63682fb3bebabb6b1e1dfd8eaac6483c693e687460977a15d8f0885dca9b6b6a`，
匹配此前 Wave5 round6 安装收据。

独立 One-KVM→JetKVM、NanoKVM→JetKVM 两轮均出首帧，第二浏览器分别在 506/241 ms
取得首帧，首个统计点已解码一个关键帧，PLI/FIR 为零。RX 为 3840×2160、link_ready=1、
capture_users=1，接收持续约60fps，没有格式协商或编码错误。第二浏览器加入时原网页按
JetKVM 既有接管行为转入 other-session 页，因此本轮证明接管接入关键帧，未证明持续双观看者并播。

同一序列切 PiKVM 时保存到 HTTP 502，peer 列表为空。旧编排在 `/api/select` 返回后立即
导航，没有检查 HTTP 状态，把服务尚未就绪的错误页等待45秒后当成视频失败。
临时脚本改为既有切换工具采用的有界 HTTP 就绪轮询，随后再检查解码推进。
另一次 One-KVM 恢复导航实测连续四个502后返回200，确认该启动窗口存在。
首窗 JetKVM 没有保存 HTTP/peer 证据，不能追溯断言其唯一根因；现有证据支持编排问题，
未复现 t7-vdin-test 格式检查或 JetKVM 按需关键帧逻辑缺陷，没有据此修改产品代码。

一次中间轮次与前轮浏览器收尾重叠，已作废、清理进程后重新独立执行。
就绪轮询与浏览器 finally 清理只放在本机 logs/tmp。最终独立轮次结果如下。

| 网页 | 首帧等待 | 约10秒新增解码 | 首个统计点关键帧 |
|---|---:|---:|---:|
| JetKVM 首个浏览器 | 1991 ms | 604 | 1 |
| JetKVM 第二浏览器接管 | 237 ms | 608 | 1 |
| PiKVM | 8169 ms | 605 | 1 |
| 切回 One-KVM | 3298 ms | 604 | 1 |
| UU 断开后最终 One-KVM | 3353 ms | 603 | 1 |

各行均为3840×2160；JetKVM、PiKVM的丢帧、丢包、冻结、PLI增量均为零。
完整 SDP、candidate、peer/getStats、HTTP状态和截图保存在 jetfirst-verified 子目录，
最终 One-KVM 位于 final-onekvm。原始失败轮次另行保留。

UU 使用官方 uuyc-cli 连接已核对的板子设备，再断开本次会话。15次一秒采样中持续取得
H.265 connected 会话和新鲜 Receiver Report，total_lost=0、loss_percent=0，直连UDP。
最后三份报告年龄为156–166 ms、RTT约1.08–1.24 ms，发送窗口约60fps。
官方客户端窗口截图命令失败，未取得客户端解码/渲染统计，结论限定为官方客户端接收通过。
UU 断开后重开 One-KVM 网页确认持续推进，最后 H.265、Custom 40000 kbps，四服务active，
UDC configured，内核日志无新增 WARN/Oops，sampling、板票和SSH转发均已关闭。

## 交付与后续

原始证据及封存产物在本机 `logs/mainline-merge/`，包含 module-manifest.json、installed.json、
modules.tar.gz、构建和测试日志、三个成功网页窗口的 JSON/PNG、apps.log、失败及最终状态日志。
已封存产物和编排后，通过 tools/vm worktree rm 清理本轮登记的 mainline-merge。
旧工作树及分支由协调者处理，passthrough-73 和 gpu-kbase-7x 保留。

首窗 JetKVM 失败的原始根因受当时证据缺失限制；补测已完成要求的网页接入、关键帧和UU接收项。
正式源码锁仍记录上一完整内核包，本次模块安装来源和身份以本文为准。协调者负责正式分支推送。
