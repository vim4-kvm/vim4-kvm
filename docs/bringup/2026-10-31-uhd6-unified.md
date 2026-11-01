# 2026-10-31：uhd6 统一候选

状态：首窗启动门禁失败，未持久安装。5.15 保持默认；`tested_build` 仍是
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
| Image/两份 DT/全部模块/三外部模块/BTF/完整清单 | 构建中 |
| checkpatch --strict、DT、宿主夹具、主仓离线 unittest | 待运行 |
| HDMI 模式、H.264、H.265、4K60 | 未上板 |
| 音频服务（按本任务不测声音） | 未上板 |
| M6 HID、虚拟介质、GPU、管理页 | 未上板 |
| 原生 HDR、HDR2 各一次短验收 | 未上板 |
| HEVC 非 8 对齐三轮切换和独立裁剪夹具 | 未上板 |
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
