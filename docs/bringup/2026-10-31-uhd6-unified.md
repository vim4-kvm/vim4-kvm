# 2026-10-31：uhd6 统一候选

状态：r3已启动，部分门禁通过，全量验收未完成，未持久安装。5.15 保持默认；`tested_build` 仍是
已验 uhd5，`retained_runtime` 仍是 uhd1。构建通过不能代替下表验收。

## 来源与冲突处理

| 层 | 已核对差异 | uhd6 选择 |
|---|---|---|
| 内核 | uhd4/uhd5 Image 均为 8bca939；r13 在其上加 Wave5 P010/HDR10 和 VDIN AMLY/metadata 两提交 | 正式远端 vim4-kvm-7.3 HEAD dc220366a1222a03423d5b5987fab3f027ec1d7a；独立 VM worktree/O=，不混入实验分支 |
| 配置 | uhd4/uhd5 只差 LOCALVERSION 与 THERMAL_EMULATION | uhd6.config 以 uhd5 为基，只改 release，保留模块 BTF；2338 基础模块全部重编 |
| DT | 两项原生 HDR 提交无 DTS 改动；uhd5 的 kbase DT 由完整 M0 DT 生成 | 同次构建 M0 DT 生成互斥 kbase/Panfrost 两份；默认 kbase，Panfrost 可选 |
| 外部模块 | uhd5 有 mali_kbase、vim4_kbase_heaps、governor_vim4；r13 没有 | 沿用已验补丁和源码，对新 vmlinux/Module.symvers 全量重编三模块及 BTF，不复制 uhd5 .ko |
| One-KVM/capture | uhd4 为 db848a52；r13 为 2cf9ef4d / b43e5645 | 复用 r13 封存的已验二进制及逐文件摘要；7.3 One-KVM 单独安装，5.15 程序保留 |
| 私有 GStreamer | r13 增加 P010、完整 PQ、运行库 transfer ABI 修复 | r13 V4L2 b9269d05… 和对应 capture；Wave5 共享插件沿用 0240de1c…，不覆盖系统库 |
| manager | 两套 GPU/HDR 锁不提供新的统一 manager 构建 | 保留当前已部署版本，窗口内核对实际哈希、认证状态和管理页；不从其他线未提交树构建 |
| GPU 用户态 | uhd5 为 r44p0 UK11.39/libmali；r13 仅验 Panfrost/PanVK 26.2.6 | 沿用 uhd5 按绑定驱动选择的私有 ICD/直接 EGL 前缀，blob 单独 provision；kbase 原生 HDR 必须重新验 |

默认 kbase 的依据是 [r11/r12 正式锁](2026-10-31-uhd5-main-integration.md)：
同协议 DMA submit_wait 1.535/3.570ms、GLES 646.280/648.065fps、CL SP 101.74GFLOPS，
厂商分别为 1.692/3.618ms、616.361/617.773fps、101.69GFLOPS，且已验五档策略与限频恢复。
这只决定候选默认，不代表原生 HDR 已在 kbase 通过；失败须修复并重新排队。
Panfrost 保留其原生 HDR 已验路径，不把 r7b–r11、coherent 故障 DT 或其他未通过候选纳入。

## 本轮门禁

| 项目 | 状态 |
|---|---|
| Image/两份 DT/全部模块/三外部模块/BTF/完整清单 | 全部构建、逐文件验证通过 |
| checkpatch --strict、DT、宿主夹具、主仓离线 unittest | 代码差异、限定DT schema、宿主夹具与367项主仓测试通过，14项环境跳过；历史提交元数据诊断见下文 |
| HDMI 模式、H.264、H.265、4K60 | r3 H.264 UHD短接收通过，其余待验 |
| 音频服务（按本任务不测声音） | r3 One-KVM检测到VIM4HDMIRX；HDR切换后48k采集自动恢复，无声音测试 |
| M6 HID、虚拟介质、GPU、管理页 | HID/GLES像素/当前管理页通过；窗口J完整只读/可写/重启保留/安全弹出通过 |
| 原生 HDR、HDR2 各一次短验收 | 窗口E通过；Main10/PQ/BT.2020与SEI见下文 |
| HEVC 非 8 对齐三轮切换和独立裁剪夹具 | 窗口F九次切换、窗口J三个独立SPS/裁剪/解码夹具均通过 |
| 持久安装完整同次模块、登记 retained_runtime、回 5.15 | 未执行，须全部门禁通过 |

所有上板和重负载操作分别经 board-queue 板票与 heavy 票；单板窗口≤30分钟。
优先 board-window RAM 启动与 return-baseline，分窗记录，声音与开发 Mac HID 禁止。
不改默认启动、不刷 U-Boot、不新增备份或回退脚本。

## 首窗：USB 助手遗漏 release，停止验收

完整内核 build ID `0db732dfaf0d7f1fb60e5cd61b1423ef7cb403d4`，Image
SHA256 `9cf35c4485bcc58b88691591ec1d9e1a9e3c85edd5facaf17fc656ba3d0180b5`。
全部2341模块均逐个核对vermagic/GNU build ID/BTF；运行时包剥离基础模块debug信息、保留BTF，
不把最初未strip的625MiB开发包作为正式候选。M0 DT通过Panfrost/shared-dma-pool限定schema检查。
主仓366项通过、14项环境跳过；HDMI/Wave5宿主夹具通过。
严格代码差异检查零错误/告警/check；历史原生HDR两提交缺说明/签署的元数据诊断原样保留，未伪造签署。

RAM包`uhd6-r2` SHA256 `bf5aa00ad6f03e71b7d516b35559654880bbc8ee5bdd163d69d548f750ea6215`。
实板进入uhd6，HDMI服务active、三个kbase模块加载；taint=4096为外部模块标记。
USB准备助手仍拒绝uhd6，gadget失败，One-KVM因依赖未启动。未开始九类/HDR/尺寸/GPU负载验收，
不把驱动加载写成GPU烟测通过。保存`logs/p0-1-window-a/`串口、完整dmesg及服务日志后回5.15；
修复助手准入并扩展既有活跃gadget不重绑定回归，再重新排队。不在失败窗口现场修补。

## r3：部分门禁及测试驱动失败

修复USB准入后重新构建三个外部模块并封包，基础2338模块仍来自同次uhd6 vmlinux，全部BTF匹配。
完整包`p0-1-uhd6-r3.tar.gz` SHA256
`3afb18e92a0eee055d991845ee9662bee3f9157aa1c229bf87037bea6a51e2ae`；
清单`907eeb49145d379e25efdb99db5f0490cee24f414e6f920387b86f129c8e25cf`；
RAM包`714e6bf671b2ed9f69fb01ea8b7c16233ef6c4c02a6ce81f9cdc49f0a2008d2b`。
VM目录为`~/build/p0-1-uhd6-r3*`，原始证据在本worktree的`logs/p0-1-window-b/`和`logs/p0-1-window-c/`。

| 实测 | 结果 |
|---|---|
| 同源5.15 / r3 H.264网页 | 15秒分别59.790 / 59.860fps，实际UHD解码推进；仅健全检查，不作为性能提升结论 |
| kbase最小烟测 | EGL1.5/GLES3.2、Mali-G52，512×512像素179/128/128/255，gl_error=0；未据单帧宣称吞吐或CTS |
| M6 HID | Apple M6 / Mac18,5上原生事件：Right down/up各1次，绝对位置约(480,270)/(1344,648)，相对正向位移、click、wheel均收到 |
| 只读虚拟盘 | 专用P01UHD6 FAT32，USB/WritableMedia=false，marker读出、touch拒写、主机eject后LUN为空 |
| 当前管理器 | 认证/API/运行内核/5.15默认选中/移动端无横溢出/无JS错误；实际包f4b823b、SHA256 f619943882710022afbde5a973af4d2812526898c7971e6ebc430127bbdcd676，保留当前版本 |

窗口B约25分钟。HDR切到PQ后，采样锁等待另一会话编译，取消测量并恢复SDR，记为未测。
可写盘已挂载、尚未开始写入时，测试驱动24分钟预留收尾触发自动回5.15，未先完成主机eject；
M6出现P01UHD6未正确弹出的提示。窗口C确认卷消失、LUN为空，只读fsck报告dirty bit、4文件/4簇，
未修写；随后通过One-KVM删除仅本轮创建的夹具。可写验收不算通过。测试驱动已补先弹出专用卷再回退，
后续使用新夹具重测；不把这个测试驱动失误归为内核回归。

窗口C首次stage因窗口B相同payload目录已存在而按预期拒绝；在5.15下逐文件核验后只重命名旧私有暂存目录，
不复制、不备份已安装运行时，再使用同一已封存归档启动成功。
HDR配置请求当时仍在H.264模式，等待目标输出超时返回500，未进入原生HEVC接收；已恢复原设置及源SDR，
保留日志。修正测试前置顺序为先选HEVC、再开HDR，回5.15后重新排队。无新内核WARN/Oops，taint保持外部模块4096。
管理器旧夹具的.kernel-panel已不存在，按当前组件和实际运行release重新验证通过；首次LAN进程EHOSTUNREACH
经SSH回环转发完成认证，未改Mac网络。截图、码流不推Git。

## 后续无人值守窗口

窗口D的源静止检查为0.001992，超过原阈值0.001，故没有开始HDR采样。
在M6增加正常窗口层级的专用静态桌面夹具后，窗口E在225秒内完成：

| 实测 | 结果 |
|---|---|
| 原生HDR | 真实M6 PQ输入，HEVC 3840×2160，30秒59.996fps；收到编码前缀和实际解码帧 |
| 码流头 | Main10，Y/UV bit_depth_minus8均2；primaries/transfer/matrix为9/16/9；Mastering Display及Content Light SEI存在。未另做V4L2元数据逐字节对照 |
| HDR2映射 | 同一PQ源关闭原生HDR，H.264 UHD，15秒59.921fps；不是SDR源冒充映射验收 |

E随后无订阅者的尺寸配置请求超时；日志显示管线3秒自动停止，而配置等待5秒。
修正测试端保持实际视频订阅者，不修改应用超时或验收阈值。窗口F在160秒内完成
720→900→原尺寸三轮共九次HEVC切换，实际1280×720、1600×900、3840×2160，
每窗推进113–121帧；第二、三轮均约59.9fps。
原始证据分别在`logs/p0-1-window-{d,e,f}/`，包括接收统计、码流头和完整journal。
每窗恢复原视频配置、源SDR及5.15，受保护启动文件哈希均不变。

窗口G在首次MCP截图超时后停止，未开始介质或裁剪夹具；113秒内自动收证据并回5.15。
窗口H预检发现他线heavy任务仍在运行，立即释放、完全未触板。
后续窗口先确认实际解码后再准备M6，持板期间只运行预先准备的无人值守脚本。

窗口I解码通过，但M6 Terminal命令首字母丢失，辅助端未启动；205秒内回5.15。
改为先确认提示符、命令前加空格后，窗口J的完整介质验收通过：只读拒写、可写1MiB，
SHA256 `bd8a5183fdafb052402b7f52480145004a781b927f0d376e4fbd922da44f6926`；
One-KVM重启保留同一LUN，M6再次校验后安全弹出，板端读回一致，fsck -n零错误，
随后仅删除本轮夹具。三个独立NV12夹具也通过：1366×768的SPS为1368×768、右裁2px，
1440×900为1440×904、下裁4px，1680×1050为1680×1056、下裁6px；均解码5帧、无错误。
证据在`logs/p0-1-window-j/`的media-summary.json和encoder-fixtures.jsonl。

J共162秒，回5.15及受保护文件核对通过；收尾旧MCP会话因应用重启失效，主机已弹盘、LUN为空，
但辅助端退出任务未送达。K的截图证实仍是本轮辅助循环占用Terminal，故身份握手超时，
202秒内回5.15，模式矩阵未开始。下一窗先停止这个已确认的本轮前台命令，
辅助端遇本地服务关闭即退出；清理不再依赖重启前的MCP会话。
