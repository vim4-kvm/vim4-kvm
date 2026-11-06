# 2026-11-06：HEVC 主线正式部署准备与两次入场停止

**尚未部署。** 正式默认仍为`7.3.1-vim4-20261105`/fd41fb5，manager与应用未升级。
新主线整包已完成离线核验；第一窗因启动分区空间停止，清理已授权的孤立旧目录后，
第二窗在未知工作界面前停止。两窗均零上传、零安装、零HID、零重启。
用户不在场；按协调者决定，等用户明确让出Mac给TestUFO约50分钟后再安排板窗。
源码验收背景见[.38全集](2026-11-06-hevc-integration38-results.md)，不能把这里的准备写成部署成功。

## 固定产物与范围

源码固定`d177f0dc1ca40a33dadee38f95c08fa332236f69`，tree
`ac460f9af1c70b607686af8a30d69ed5ded5d8c4`；未纳入第三轮或架构重构。
实际`git log --stat fd41fb5..d177f0dc`为41提交、33文件、8055增/1927删，涉及VDEC各
codec、队列/HOLD/共享上电、T7 DTS与binding；不涉及HDMI RX/VDIN/编码数据路径改动。

| 项目 | 正式首包 |
|---|---|
| release | `7.3.1-vim4-20261106` |
| GNU build ID | `5a9cb11e34240d25a47a6ca4f9013d189ad7385a` |
| tar.gz SHA256 | `e3fc8a30828036a304d456e82f5862172fe5fe44f28a89e20978c8a299fbf972` |
| manifest SHA256 | `3305d330bee3f7f1926fb94f94d6f3cc617cb50ad900caa86b7f134cdf811b0e` |
| Image SHA256 | `a0ebb040b690ed60b534765f49404e3aaaad2743b188b50abeffbcbb4b6cb676` |
| config SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |

整包69,591,879字节，独立VM源码`linux-7.3-deploy-hevc`、全新O=`build/deploy-hevc/kernel`。
全部本机文件限`vim4-kvm-deploy-hevc`工作树。原正式包SHA为
`a12069066760768a833803ad11e7e1fc212674e4ff09f40bdf2017cc1d55e204`，继续完整保留回退。
manager仍dev.10.g85ef0b1，其他组件沿当前锁；不替换系统parser，不调节节能或CPU策略。

用户明确保持解码器默认关闭：`enable_t7=false`、`allow_t7_power=false`、
`t7_snapshot_only=true`，不增加modprobe/modules-load配置。验收仅由测试入口显式加载，
完成后移除测试加载并恢复原应用。正式cmdline保留无线，不使用.38无线屏蔽变体、不saveenv。

## 已执行的离线核验

- production build.sh构建Image/DTB/完整模块及匹配的kbase/heaps/governor；
  2338基础+3外部模块，2354个模块目录文件，外层24文件/10运行时文件完整集合与SHA通过。
  全模块vermagic、BTF、build ID和depmod均核验；Mac复制包再次独立核对。
- .config逐字节匹配生产配置，实际auto.conf共4623项按Kconfig值严格相等；
  链接产物无kasan_report。包内没有新增默认解码器启用配置。
- 独立arm64 QEMU实际39/39，无跳过；dtschema2026.9的binding和板DT实例检查退出0，
  两条既存pinctrl DTC告警保留。六区90个fan trip与90个cooling map属性均与原正式DTB相同。
- 全部构建/检查经heavy队列。只删除本任务kernel/external/kunit下的*.o，共约4.31GB；
  不删历史证据，保留首包、原BTF、模块、清单、日志及W=1诊断ELF。

### W=1调用纠正及二进制边界

初稿在环境导出W=1，未触发本版Kbuild的额外检查；Makefile只读取命令行W。原命令与首包
保留，随后显式`make W=1 Image dtbs modules`重编，并另目录安装全部基础模块。
**W=1为同源同config的独立构建，非同一二进制。** 其build ID为
`bef047617528000ca9a8ed1137c4c49ddc103b46`，告警1168条，与.38按文件及告警文本
比较新增0、减少0；`drivers/media/platform/amlogic/vdec/`零告警。

整文件比较确实失败，不能改写为字节一致：Image与2338模块文件均不同。按协调者限定的
快速确认，抽样aml-vdec-drv、Wave5、TCPM、brcmfmac的.text/.rodata逐字节相同。
Image相应区段各2字节差异，定位为btf_parse_vmlinux中的BTF末地址常量及
kallsyms_offsets的__stop_BTF项：

| 证据 | 首包 | W=1 |
|---|---|---|
| BTF头计算总长度 | `0x7211b6` | `0x721282` |
| ADRP+ADD得到的__stop_BTF | `ffff8000823c21b6` | `ffff8000823c2282` |
| kallsyms索引128632解析 | 同左末地址 | 同左末地址 |

首包BTF头为24+4,332,456+3,143,158字节，W=1为24+4,332,676+3,143,142字节，
相差204字节；两侧指令及符号表项均与各自BTF头完全相符。该.text/.rodata差异仅是
BTF长度派生的末地址常量，非版本串猜测。协调者据此明确认定首包5a9cb11e合格，继续使用
原封存整包，绝不混装W=1模块。原链接ELF已在同O重编时被覆盖；当前kernel/vmlinux是W=1
诊断版本，首包原BTF仍在package/vmlinux.btf。比较失败与所有定位输出均保留。

## 两次部署入场及空间清理

| 窗口 | FIFO / 实际秒数 | 结果 |
|---|---|---|
| window-1 | 1553 / 5.932 | 原正式2372项proof、2341模块及manager通过；/boot可用46,407,680B，完整7启动文件需58,021,151B，缺11,613,471B，安装前停止；视频尚未运行 |
| boot-space-1 | 1555 / 10.938 | 新授权的SSH-only盘点与孤立目录清理，无串口/HID/重启操作，见下节 |
| window-2 | 1558 / 119.750 | 空间与原正式proof/manager通过；原4K H.265五秒300帧/59.964fps，新增掉帧/丢包/冻结均0；只读截图不是已知TestUFO，任何HID/上传/安装前停止 |

window-2可见现有工作终端，未把其他项目内容入库，也未向其注入任何按键。为避免旧清理
流程在未改EDID时仍调用restore，终止仅本任务进程组，并清理自己的bridge/tunnel；板票释放。
这一次是受控停止前尚未实现的早期拒绝分支，不包装成自动回退通过。原默认本来就是fd41fb5，
所以没有恢复重启，result中的restored=false不表示内核被留在候选。

两窗均未到安装提交点，未切换Mainline、未升级manager/应用、未写modprobe配置。
入场和清理前后boot_id均为`c239a0cb-5af7-4a57-a767-7613042e5923`，没有新增Linux启动计入
冷复位统计，正式最低口径仍≥61/12。两次UART记录器已打开但捕获为0字节，仅说明静默；
未借此证明串口响应或物理复位恢复能力。USB-C功率计拓扑未动，本轮没有功率新读数。

### 有条件授权的旧启动目录删除

协调者预先明确允许删除同时满足“任一启动项无引用、installed()未登记、不是当前fd41fb5、
不是Vendor/5.15”的孤立目录。完整盘点只有：

- `7.3.1-vim4-20261104.3`：58,016,673B，启动项引用和installed登记均为空。
- `7.3.1-vim4-20261105`：Mainline引用且已登记，必须保留。

.3符合这次条件授权，删除前7文件SHA清单先持久保存到logs，再逐项复核、检查配置/登记
未变后删除其启动目录并sync。原7文件摘要还与既有.3发行收据全部相同。释放58,040,320B，
/boot可用增至104,448,000B，超过新包+20%余量69,625,382B。保留.3模块/固件/Mac原整包；
fd41fb5启动目录/模块/固件/整包和Vendor均未删，配置/登记SHA、boot_id均不变。
不是借清理授权注销已登记内核，也未触碰/boot其他大文件；这些文件一并只读盘点留证。

## 早期拒绝修正与当前暂停点

修正位于本任务私有无人值守编排：只在通过初始画面审核、即将进行本任务第一次fixture/HID
操作时设置fixture_changes；初始拒绝不执行任何EDID/fixture cleanup或回退。
SceneRejected正常结束执行，finally只关闭自建bridge/tunnel和释放票。真正开始修改以后
的失败仍走已审恢复分支，且恢复过程中保持连续UART。未来窗口另保存输入和执行源码快照。

离线实际调用该早期失败处理器，以本次未知场景拒绝为输入；对象没有票、SSH执行器或MCP，
仍正常生成accepted=false/restored=false且没有cleanup/recovery_error。没有模拟解码硬件。
输入摘要篡改在SSH/取票前拒绝、真实r92 UART冷复位回放不误判为splat、嵌入SSH脚本编译、
源码/build身份、12代表及默认关闭门均通过；私有Playwright1.56.1与Chrome156导入冒烟通过。

本次明确缩减HDMI为1080p/4K及无信号恢复；**编码非9/11模式，仅4K单档10秒+600秒运动**。
原19/9/11夹具丢失已登记issues，不能以缩减口径声称完整矩阵通过。其余九类与解码计划不减，
但两次停止后均未执行，HEVC/H.264/MPEG-2/JPEG冒烟、600秒运动、HID/介质、GPU及管理页
本次验收仍全部未运行。原正式短视频不能充当新包验收。

协调者已禁止继续取板票或向当前Mac发HID/切EDID。等用户明确让出测试源约50分钟后再派；
届时仍用首包、正式无线cmdline、解码器默认关闭，首错回退fd41fb5，420秒恢复保留。
SSH/串口都不可达或420秒内不能自然恢复即停止交接，不主动循环reboot或做物理恢复。
正式来源锁/发行收据未推进，本地release tag未建，未部署、未push、未合并。

## 原始证据

本工作树build/deploy-hevc/保存artifact-identity、package-verification、production-gate、
W=1编译命令、warnings、section-comparison、image-difference-symbols、btf-difference-check、
KUnit/schema/fan-DTB报告和原始日志。短记录提交前主仓全套为607 tests / OK / skipped17，
34.868秒；跳过项不计已验。输出为final-main-tests.log，早期拒绝为early-rejection-check.log。
logs/deploy-hevc/window-{1,2}/保存逐步SSH输出、proof、截图及result；
boot-space-1/保存删除前/后完整盘点、逐文件SHA、df与登记不变证明。
