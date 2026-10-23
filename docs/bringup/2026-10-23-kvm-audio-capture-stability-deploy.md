# 2026-10-23：HDMI 音频 PCM 生命周期修复与部署

承接[诊断与27轮历史](2026-10-23-kvm-audio-capture-stability.md)。最新用户决定停止重复
5/20轮验收，按[内核开发门禁](../subsystems/deployment.md#内核开发流程与部署门禁)推进：
驱动修复、一次性启动针对性测试与约5分钟冒烟，通过后与SARADC单提交合入，正式部署跑一次九类。
物理链路失锁只记录现场对照方案；本轮不扩大源/线缆/PHY调查。

## 历史正式窗口为何回退

da19093a…的27轮有24轮完整通过，3轮旧source-change断言失败但应用自动恢复。
后续三个正式窗口都回到7b8372b8…，没有finalize：

| 窗口 | 实际结果 |
|---|---|
| formal-window | 19模式通过，H.264 1680×1050成功快照后遇到ENOLINK及空DMA，旧即时断言中止 |
| formal-recovery-window | 原始模式、H.264/H.265及4K60过；音频48k失锁产生21/35个track/tab坏窗口，约3.18秒恢复，旧零中断门禁失败 |
| formal-qualified-window | 九类及四次HPD恢复全过；正常音频310/308个窗口、HPD616/613个窗口均零bad；最终health发现两条ASoC -11 |

最后两条发生在启动后360.718/360.719秒，分别为snd_soc_dai_hw_params和
__soc_pcm_hw_params的EAGAIN。音频虽恢复，仍违反无ASoC残留错误要求。
b076a35c／d5740fac…日志降级候选只离线构建，未上板；最新方案撤回通用ASoC改动。
上述窗口均另查三服务、UDC、隔离、taint和真实HID；没有同方法7b基线数据，不补跑。

## 驱动方案与离线证据

功能分支fix/hdmi-capture-stability已rebase到最新origin/vim4-kvm-7.3的c1315a95691e，
驱动候选41002d035f1a19596012dc054ee7862a29738f3e；生命周期修复为6ed0155c0e2b和41002d035f1a。
后续9a842d455a957只加PLL启动中失锁的实际C测试，不改变候选驱动代码，已推送功能分支。
ASoC通用snd_soc_ret恢复基线实现，最终差异仅HDMI RX/VDIN驱动及其测试。

- hw_params只验证PCM通道/格式并保存协商速率、substream，不读取异步ACR/AIF或开PLL。
- prepare在audio_lock下核对实时包、连续资格格式和协商速率；匹配后才配置PLL及FIFO。
  源未就绪或变化时返回成功但保持FIFO门控，100ms监控通过snd_pcm_stop_xrun通知运行中的PCM。
- snd_pcm_stop_xrun只处理RUNNING状态，因此监控在无效PCM存续期间重试，覆盖先监控后START的竞态。
  hw_free清substream，取消待发XRUN。标准ALSA同采样率XRUN恢复可直接prepare，重新配置硬件；
  不锁死在audio_invalid状态。不同采样率仍须用户态重新资格确认并协商。
- 真正时钟使能失败、FIFO被占用、稳定源PLL超时保留错误与回滚；PLL超时同时发生源变化才转XRUN。
  不在锁内等待源重新就绪，不改厂商已验证的寄存器配置序列。

One-KVM保持672b8fd9fdec1c35c35149265f901dc43da79394：退避后重新读取ready，
同格式/generation跨200ms资格确认再重开；原生ENOLINK/EAGAIN/ERANGE保持兼容处理。
其read循环在XRUN恢复前也检查HDMI资格，真正换源走串行、可取消重开。

VM实际C测试覆盖七档ACR/AIF、损坏/矛盾包、hw_params后失锁、monitor-before-START、
关闭取消XRUN、同速率prepare恢复、时钟/FIFO/PLL失败回滚。HDMI驱动全套通过；
rebase后整体差异checkpatch为0 errors、0 warnings（756行），git diff --check通过。
日志：logs/kvm-stability/pcm-lifecycle-rebased-tests.log、pcm-xrun-reprepare.log。
完整候选build ID为8d6ee8e4d0e6844b933a64402ac605218a8548df，2334模块；
M0 DTB仍为a635f894…，有效配置只新增显式禁用CONFIG_DRM_MESON_T7_HANDOFF一行。
一次性归档83,927,040字节，已完成逐文件哈希与静态ARM64 PID 1检查。

## 一次性窗口与正式发布计划

候选以display-once.py prepare/stage和静态PID 1暂存完整匹配模块，仅在U-Boot RAM选择，
默认Image/DTB/extlinux、运行时登记与基线模块原件保持不变。One-KVM用私有候选文件的
临时只读bind替代，重启即撤销。上板预置独立rollback.sh，请求有界正常重启回默认基线；
窗口finally同样重启并核对基线。所有服务stop有30秒上限。未修改final-board.py。
正式包直接采用主仓2a34982已合并的恢复helper，保留bounded_command、文件本地同步和
application-restore-pending，不再编辑该文件；Linux VM恢复故障注入10项通过。

针对性顺序：48/44.1/48k切换、四次HPD（48/44.1/32/48k）恢复、300秒H.264画面/帧推进，
真实HID、UDC configured、三服务active、isolated=0、taint=0、无新增ASoC/oops告警。
全程board/heavy双锁；完成即释放。不跑重复轮数组。

## 首个针对性窗口：未通过，已恢复

logs/kvm-stability/pcm-once-window/记录一次性启动8d6ee8e4…：
候选GNU build ID、完整模块bind、五个基线文件哈希、三服务/UDC/隔离/taint均通过，
临时One-KVM进程1313的实际可执行文件SHA为3d3cf276…。
48k段track/tab各104窗口零bad，44.1k段103/102窗口零bad；第三次切回48k，
5秒宽限之后仍有坏波形窗口，探针报Audio failure without observed RX link loss，故中止。
应用14:56:19.662观察源变化，14:56:20.871自动恢复，PID不变；候选完整内核journal中
ASoC error计数为0。首次探针在输出第三段坏窗口前断言，已补充诊断输出，未修改阈值。
四次HPD和300秒冒烟尚未执行，不能把该窗口记通过。

finally正常重启回7b8372b894c98ffae12e636a325c86f2b6c85e00；restored.json确认
三服务active、UDC configured、isolated=0、taint=0，应用/manager运行哈希回到
72db30c0…／d7a15868…；五个基线文件哈希不变，restored-hid.log确认键盘、绝对/相对鼠标、click、wheel通过。
候选私有目录、上传包和临时应用bind已清除，释放双锁。

再次申请窗口时HEAD预检发现正式分支已推进39d42b6393f92c4a5bc4bf6d73877dcb83c7d257，
在改变板子前中止（pcm-once-window-2.log）。功能分支重新rebase为
5b60d643af5ffcd395298d1df12b74145ab6a74e并推送；HDMI全套及整体差异checkpatch重新通过，
782行0 errors/0 warnings。新完整候选build ID为b0cf6a7264aa9c5e5247b9f5f9f21aec36fb60e4。

## 最新针对性验证

窗口3（logs/kvm-stability/pcm-once-window-3）使用b0cf6a72…及同一One-KVM进程1317：
48/44.1/48k的track/tab窗口合计308/307，全部零bad。四次HPD各拉低5秒，
48/44.1/32/48k最终窗口分别154/154、154/154、154/154、150/150，全部零bad；
从恢复开始到AudioRecovered分别6.234、6.488、6.233、6.234秒（包含故意失锁5秒）。
最后一段另遇真实tmds-invalid，原有5个坏窗口保留，应用1.208秒自动恢复；
保持同速率、浏览器与PID，补采一个完整20秒段通过原阈值。未放宽波形阈值。
完整候选journal无ASoC错误。冒烟源选择器误用AML而实际为RTK，故该窗口的运动冒烟不计通过。

窗口4（pcm-once-window-4）只纠正运动源并完成300秒冒烟，不重复音频组：
3840×2160 H.264平均58.3454fps，浏览器freezes=7、dropped=0、lost=0、PLI=0。
同一进程1316的7次采集停止均在约1.0–1.2秒自动重开；内核末态stream_stops=6、
last_stop_reason=tmds-invalid，日志另有TRY_FMT失锁、缓冲池重建及poll错误。
不能逐一证明7次浏览器停顿都是物理失锁，也不能宣称零停顿；声音恢复3次均约1.21秒。
画面截图、运动源帧号推进、真实HID、UDC configured、三服务active、isolated=0、
taint=0通过，完整journal无新增ASoC/oops/BUG/panic。11个已加载模块build ID与完整候选一致。
两个窗口均恢复7b8372b8…、原应用/manager哈希、五个受保护文件、真实HID后清理私有候选并释放双锁。

针对性门禁已通过。Linux正式分支已快进到0a775305f0ad8（含5b60d643与单提交
SARADC d0c36b0f），One-KVM vim4已快进到672b8fd9，均已推送。
合并后的HDMI实际C测试全过，整体checkpatch为790行0 errors/0 warnings。
正式完整包沿用最新主仓uhd1.config的M1驱动编译开关，但仍安装已验M0 DTB，不启用M1。
正式九类回归、finalize及已部署锁更新仍待完成。物理失锁仍为
[厂商差距待办](../vendor-parity.md)，需用户现场受控源或厂商5.15同链路对照。
