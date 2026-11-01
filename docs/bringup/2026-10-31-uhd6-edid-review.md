# 2026-10-31：uhd6 EDID故障取证与待审修复

状态：板子已自动恢复5.15，未执行用户RESET。修复`f951e2d24d32d5df0e701e7c355b3db4c91eaf74`
位于独立内核分支`p0-1-unified73`。独立review已认可修复方向，未发现新增乘积≥5缺陷；允许同条件定向实测。
此前4.1秒只读取证已确认恢复；本节记录审查与离线准备，实板修复结果在通过后追加。
统一候选进度见[主记录](2026-10-31-uhd6-unified.md)。

## 已恢复的身份与重启证据

`logs/p0-1-recovery-readonly/`保留board-window collect、身份、journal及pstore原件。

| 检查 | 实读结果 |
|---|---|
| 5.15身份 | 5.15.137-vim4kvm-hdrdual6；build ID 4a9b69d62ba7b3a5adeb41b213f7f3e573006165 |
| 受保护文件 | 与N窗前证明的13项SHA256全部一致，包括默认/edge Image、DT、extlinux、initrd和两份运行时登记 |
| 服务/USB | one-kvm、vim4-manager、vim4-kvm-hdmi、vim4-kvm-gadget均active；fdd00000.crgudc2为configured |
| 当前启动 | boot ID 7a7684a71cee4a2c95baf49d252b0085；取证时uptime 1317.51秒；journal始于11月1日03:57:40 UTC |
| 前次启动 | boot ID 6e0616ca868a4cb19cee034bfeaa0ccb，正是N窗；journal为03:56:21–03:56:58 UTC，无正常关机尾 |
| 固件原因 | 当前cmdline为reboot_mode=watchdog_reboot；其余cmdline及文件通过原证明比较 |

systemd-pstore在当前启动归档了`dmesg-ramoops-0`。它的uhd6/r3 init路径、43.039秒SError
与N窗串口逐项相同，补齐了此前没读到的panic和调用栈：

```text
[43.039041] SError Interrupt on CPU2, code 0x00000000bf000002 -- SError
[43.039065] Workqueue: events t7_hdmirx_link_work [t7_hdmirx]
[43.039083] pc : t7_hdmirx_video_status_reason+0x38/0x928 [t7_hdmirx]
[43.039089] lr : t7_hdmirx_link_work+0x9c/0xba4 [t7_hdmirx]
[43.039134] Kernel panic - not syncing: Asynchronous SError Interrupt
```

因此应记录为**N窗panic后自动复位到默认5.15，固件报告watchdog_reboot**，不能写成用户RESET。
return-baseline在SSH身份前置检查就退出，未发出它的正常重启命令。
前次journal最后的内核行仅到36.45秒；panic由pstore补证。pstore未留下最终复位行，未采到完整重启UART；
无法仅凭现有资料区分硬件看门狗到期与panic=20路径最后怎样触发复位。
归档还含旧的`dmesg-ramoops-1`和无boot ID的console片段，不能把其中99秒的Restarting system拼接成N窗时间线。
先前“需要物理RESET”的判断已被此次取证纠正；本轮没有要求用户操作。

## f951修复的根因分析与边界

已证实的调用顺序：N窗停止One-KVM并读到capture_users=0，随后`VIDIOC_S_EDID(blocks=0)`撤回EDID。
在dc220366a122的`t7_hdmirx_set_edid()`中，此分支持有link->lock后调用`t7_hdmirx_ddc_stop()`。
后者不仅拉低HPD，还写回探测前的saved_port_sel、saved_reset，清空edid_blob并释放DDC归属。
这套动作属于驱动退出的硬件清理；此时core_active仍为真，link/audio工作队列也仍存在。
释放link锁后，link_work继续执行update_drm/video_status_reason等接收器访问。

`capture_users=0`只证明没有采集租约，不能证明接收器工作队列已停止。恢复探测前TOP配置与这些访问
构成明确的生命周期错误；完整pstore把故障定位到同一link工作队列，支持该因果分析。
但SError是异步异常：+0x38的反汇编在函数序言，不是某个确定的MMIO指令，不能据此断言是哪一次寄存器读失败。
本轮不读现场寄存器、不盲扫regmap；硬件因果闭环仍须修复后的定向门禁。

f951只改变零块分支：拉低HPD并把可读EDID长度设为0，保留DDC资源归属。
重复撤回仍幂等，G_EDID零块读回为0；重新发布仍走现有DDC编程路径。
最终驱动清理仍调用原ddc_stop来恢复硬件。没有删除该退出清理，也没有关闭工作队列、延迟超时或屏蔽SError。
非零EDID编程、DDC读回失败恢复及驱动移除的其他路径未改；review应检查资源归属和清理次序是否完整。

### 为何厂商5.15不走这条故障链

源码对照使用主仓锁定的common_drivers `31619c527655514b4c89516ef609b6db1dd47db6`：
`drivers/media/vin/tvin/hdmirx/hdmi_rx_hw.c`中的`rx_set_port_hpd()`只调整HPD/DDC端口和终端控制；
`rx_edid_module_reset()`在T7仅写EDID复位位0x2，随后写0释放，不恢复探测前完整TOP reset/port快照。
`hdmi_rx_edid.c:hdmi_rx_top_edid_update()`重编EDID；`hdmi_rx_wrapper.c:rx_edid_update_handler()`
再把端口状态机设为FSM_HPD_LOW。厂商流程没有调用7.3的t7_hdmirx_ddc_stop。
当前5.15是独立新启动，运行厂商驱动，没有加载本次7.3接收器模块。
这解释本次恢复及该故障链的实现差异；不据此宣称5.15对所有SError免疫，也没有额外在5.15注入零块EDID。

### 可供review复查的离线证据

- 独立VM工作树`~/src/linux-7.3-p0-1`；修复提交仅2文件、17行新增/8行删除。
- `test_edid_runtime.py`执行实际C getter/setter，覆盖撤回、重复撤回、零块读回、DDC归属与重新发布。
- 接收器全部`test_*.py`宿主夹具通过，包括原DDC/HPD排序、失败回滚、时序、租约和源变化。
- 提交级`checkpatch --strict`为0 errors、0 warnings、0 checks；t7-hdmirx.ko及BTF编译通过。
- 日志：`logs/p0-1-unified73/edid-{withdrawal-tests,all-host-build,fix-kernel-commit}.log`。
- [定向包清单](../../packaging/kernel-edge/uhd6-edid-repair.json)固定Image、BTF、替换模块源码/哈希和RAM包摘要。
  2373文件全部SHA256核对通过；该包仅用于修复门禁，不能安装为正式保留运行时。

## 缩放模式准备的结论与回归

M窗的CoreGraphics调用成功选择800×600 backing raster，接收器日志和浏览器却仍为3840×2160@60。
可确定的工具错误是把backing尺寸当成线上的时序；解码尺寸断言正确。M窗没另存QUERY_DV_TIMINGS，
未取得真实800×600输入的证据，不能把这次准备失败归为“驱动把800×600编码成4K”。
macOS模式列表现在只用于源端诊断，不作为HDMI模式覆盖证明。

新增[单DTD夹具工具](../../packaging/kernel-edge/hdmi-mode-fixture.py)和固定19档
[时序数据](../../packaging/kernel-edge/hdmi-modes.json)：prepare离线删除其他时序、保留音频及HDMI/SCDC；
measure用VIDIOC_QUERY_DV_TIMINGS读取真实输入；verify必须匹配目标几何和刷新率。
矩阵在真实输入资格确认后才接收视频，并继续核对实际解码尺寸、三处帧号和RGB色块。
离线回归包含M窗的“800×600 backing/UHD60输入”反例、19份EDID解码/音频/单时序约束、
同尺寸错误刷新率、失锁查询和真实Linux UAPI结构解码，共5项通过；新夹具仍待M6硬件验收。
导出的正式Linux UAPI与C夹具逐字节一致；主仓全套372项通过、14项环境跳过，日志为
`logs/p0-1-unified73/review-prep-unittest.log`。

## 待review后执行的窗口

独立报告为`/tmp/herdr-workers/review-uhd6.result.md`。其审查时尚无完整pstore栈，
现已用上述新取证补齐link worker定位；异步故障具体MMIO及修复效果仍待实测，不提前宣称解决。
既有issue仅登记：重新发布遇EDID RAM读回失败且previous_size=0时，ddc_active可能被清除，
随后退出遗漏probe快照的最终恢复责任；频率1×严重3=3，与本次新增路径无关，本轮不扩改。

| 阶段 | 准备与门禁 | 目标占板 |
|---|---|---|
| 修复定向门禁 | 已封存f951模块RAM包；撤回/重复撤回/发布、工作队列存活、实际视频恢复、无新WARN/SError；批末回5.15 | ≤5分钟 |
| 正式来源与封包 | 定向通过后吸收修复至正式分支，核对最终HEAD；新独立O=完整Image/双DT/全部模块+外部模块/BTF重建重封 | 不持板，heavy队列 |
| 正式矩阵 | 19档真实单DTD输入，H.264/H.265内容及4K60；音频仅服务；其余九类、原生HDR/HDR2及尺寸门禁分窗执行 | 每窗≤15分钟 |
| 稳定性 | M6运动源，同一接收会话≤600秒，记录逐窗帧推进、冻结/丢包/告警和内存前后值 | ≤15分钟 |
| 持久安装 | 全部通过后，kernel-install.sh --edge ... --keep-directory-symlink安装同次完整模块；复核5.15默认与新retained清单 | ≤10分钟 |
| 登记交付 | 更新tested_build/retained_runtime、摘要与证据；合入main前核对他线完整提交，全套离线测试后push | 不持板 |

所有窗口均预写无人值守脚本，失败立即取证、释放；修复review前不执行候选启动。
若后续再次需要物理RESET，立即停止并报告，不继续窗口。

本worktree的`build/p0-1/`已备好edid-target-window.py、edid-matrix-window.py、
runtime-window.py、stability-window.py、build-formal.py，脚本摘要在prepared-windows.json。
矩阵/稳定性入口须显式传入新正式RAM归档和来源SHA，旧r3归档不准入；
正式构建脚本要求源码与远端正式HEAD一致、打包源码锁已更新，才在新O=目录完整构建。
runtime窗串行执行M6原生HID、kbase像素、manager、介质、HDR双路径与HEVC尺寸/裁剪；
HDR前重新预热，沿用外层sampling锁，避免嵌套receiver释放采样锁。稳定性源不再用CG模式充当4K60证明。
旧r3及修复单模块试验包都不会由此脚本安装。安装仍只走既有kernel-install.sh的显式edge入口。
