# 2026-10-24：厂商 5.15 HDMI 透传

独立于 [7.3 透传](2026-10-24-hdmi-passthrough.md)，不相互替代。
本记录区分源码判断、配置实验和验收结果；未完成项不能写成通过。

## 默认内核恢复

用户更新授权：默认启动改为厂商 5.15，不再要求结束回 7.3。
接线已通过 need-user 协议确认 Mac mini → IN、OUT → 实体显示器。
用既有 `vim4-manager-helper kernel-select vendor true` 切换，没有手写启动文件。
切换前 `vim4boot.validate_entry(hashes=True)` 校验 vendor 1535 项、mainline 2349 项通过；
备份 `/var/backups/vim4-default-515-20261024`。7.3 正式启动文件、模块及选项保留。
最初在一次性候选内看到的 mainline 模块哈希差异来自候选模块 bind mount，
候选复位后全量校验通过，不是通过修改清单消除错误。

已启动 `5.15.137-vim4kvm`，vendor selected，One-KVM、manager、tvserver、HDMI 服务 active，
UDC configured。首次无信号为输入线漏接，补接后 RX YUV4448、3840×2160、59.98Hz 锁定。
真实 HID 第二轮通过键盘 down/up、绝对/相对鼠标、点击、滚轮；第一轮前台保护拒绝发送。
用户随后取消默认切换后的冒烟：H.265 浏览器窗口被中断，没有完整五分钟结果，H.264 未跑。
编码设置曾恢复原 H.264；随后用户 UU 会话要求 H.265，本次共存测量沿用 H.265。
taint=12288（厂商树外/未签名模块），不写成零。
原始记录位于 `logs/passthrough-515/`。

## 第一阶段：离线源码结论

最初核对 VM `~/src/linux/common_drivers@4cfb128d3`，构建前同步到主仓基线 `563cff9da`；候选分支
`vim4-5.15-passthrough`，管理器从 `passthrough-ui` 建 `passthrough-5.15`。

原生链：RX port 1 → VDIN0 → VFM tvpath → amvideo → VPP VD1 → hdmitx21。
`drivers/media/common/vfm/vfm.c:vfm_init()` 原始 tvpath 包含 deinterlace，可含 ppmgr；
当前板级 `tools/hdmi-setup.sh` 将其替换为 `vdin0 vfm_cap` 并运行 `hdmiin-demo`。
tvserver 管理 RX 的打开、信号事件与 VDIN 解码；`vdin_drv.c` 的
`TVIN_IOC_OPEN/START_DEC/STOP_DEC/CLOSE` 是底层接口，不再增加第二个 VDIN0 所有者。

VFM 本身不是广播：`vf_get_receiver_name()` / `vf_get_provider_name()` 返回首个匹配端点。
给 vdin0 加两个 map 不会获得两份有独立归还语义的帧。现有 `vfm_cap.c` 则已有真正的 TEE：
注册上游 receiver 与下游 provider；显示、V4L2 token、DMA-buf 分别持引用，最后归还才 vf_put。
最小实验优先用 `vdin0 vfm_cap amvideo`，逐行输入绕开 deinterlace/ppmgr 的额外处理。
VDIN 8-bit NV21、3840×2160、completed-frame game_mode=3 及 KVM 编码设置均不降低。
KVM 原有上一帧完整帧保护保留；显示读取不增加 CPU 拷贝，也不增加一次 VDIN 写入。

UHD60 NV21 每次整帧读写约 746.5 MB/s；直接 TEE 的新增负载主要是 VD1 读约 746.5 MB/s。
FHD60 对应约 186.6 MB/s。这是理论有效载荷，不是 DDR 实测或零丢帧承诺。
显示持帧会占用共享 VDIN 缓冲；现有 ready_list 未限长、源重置强制回收的生命周期需重点验证。
不能为了显示关掉 KVM 的完整帧保护、降低码率/尺寸/帧率或开启同缓冲读写 game-mode bit2。

备选 VDIN1/2：驱动确有多个实例和 `start_tvin_service()`，但 RX frontend/时钟/端口控制共享；
双实例直接接同一 RX 的 4K60 能力不能从实例数推断。额外采集至少增加一次约 746.5 MB/s 写入，
CMA 与仲裁也增加，先不选。amvideo 后经 VDIN1 的 VIU writeback 可取 VD1/VPP，
但受输出缩放、OUT 热插拔与显示时钟影响，并增加读写/整帧等待，会把 KVM 质量绑定显示器，拒绝作为默认。
video_composer 是显示提交/合成层而不是 VFM 自动广播，首轮无需引入。

输出颜色采用 [厂商对照](../display-color-vendor.md) 已验证的 SDR YCbCr444 8-bit limited，
4K60 可在 sink 实际允许时用 420；不使用已测原色误差最高 23 的 RGB 路径。
首轮保持真实 2160p60，不通过重命名刷新率或降低采集尺寸制造成功。
后续跟随输入真实帧率与 sink 能力交集；OUT 热插拔不重写 RX EDID、不脉冲 PC HPD。

音频：`sound/soc/amlogic/auge/card.c` 的 `HDMITX Audio Source Select` 仅列
Spdif/Spdif_b/Tdm_A/B/C，不含直接 RX；RX 由 `extn.c/frhdmirx_hw.c` 进入采集路径。
不能把 SPDIF→RX ARC 路由当作 RX→TX 直通。tvserver/audio HAL 是否有可与现有 KVM
PCM 所有者共存的路由仍待实机核对；不并发独占打开同一个 RX PCM，不承诺声音已支持。

## 实验与接入原则

先在双锁内暂停 KVM，备份当前输出/map/服务状态，干净停止 HDMI source 后接入 TEE，
设置 TX 为 sink 允许的 YCbCr4448、启用 VD1 并隐藏遮挡视频的 OSD，先请求用户目视。
之后恢复 One-KVM，分别核对输入/显示/编码计数推进和丢帧，而非只看配置写入成功。
候选内核模块部署需单独确认。用户最后要求停止后续上板测试、合入并推送，
保留已安装版本和当前日常 KVM；本次收尾不再重启，不用合入代替未完成验收。

管理器维持既有 API 和前端；provider 必须探测实际 sysfs/TEE 路由，不能仅凭 5.15 版本
报告 supported。开关优先只控制 VD1 可见性，保持 TEE/采集所有者不变；若停显示导致队列积压，
先修引用/有界队列，再接受开关。输入、sink、输出、缩放与无信号状态必须来自读回。
若需要新内核包，部署前另行说明并请求用户确认；manager 仅在验证通过后备份并部署。

## 首次画面与字节序修复

`vdin0 vfm_cap amvideo` 已在未降低采集设置下出图。首次图像有分块字节镜像，
不是缩放或 HDMI 色彩属性问题：KVM 的 `no_swap_en=1` 将 VDIN 写入改为线性小端，
但 `vdin_vf_init()` 未在 vframe 标记 `VFRAME_FLAG_VIDEO_LINEAR`，VD1 使用厂商默认字节序。
common_drivers `746f93e09` 对与 VDIN 写入配置相同的条件补上该标记，仅三行，
不改变采集缓冲内容、编码格式、完整帧保护或 USB。checkpatch 0 error / 0 warning。

全量模块构建成功，剥离候选 `aml_media.ko` SHA-256：
`eee93aa3dcc1437f768f785f6c579a51197bf4998e59d843e6312d631075b4d5`。
新旧模块 619 个导入符号 CRC 全部一致，无新增导入，vermagic 同为 `5.15.137-vim4kvm`。
用户通过协议明确同意单模块安装、更新 initramfs、重启。备份为
`/var/backups/vim4-passthrough-515-20261024`（旧模块、旧 initrd、内核清单及启动配置）。
`/boot` 仅余 13MB，首次原地生成 initramfs 因空间不足失败，未重启；改用
`update-initramfs -u -k 5.15.137-vim4kvm -b /var/tmp/vim4-passthrough-initrd` 暂存，
验证包含模块后替换已备份的旧 initrd，未删除 Stock 或正式 7.3 产物。
用既有 register-runtime 工具重新核验登记 vendor 1535、mainline 2349 项，默认仍 Default。
新 initrd SHA-256 `8a14a30ea964735692e759b073fa2ba06c59302e9bce96e702c7a34f7e786b58`。

重启后运行模块 note SHA-256 为
`cedb8f03fd5a455e5ae22a407a1f88eab07807b5a24252c40407fda271d8adcc`，
`video_state` 显示帧 flag `0x420`（包含线性标记），新帧和显示计数持续推进。
没有依赖临时 MMIO 写入；用户随后确认“画面正常了”，真实 2160p60、YCbCr444 8-bit、SDR。
首轮 20 秒并发仅作探索：59.98786fps、区间 drop/lost/freeze/PLI 均零，不代替十分钟验收。

## 已完成数据与验收边界

4K 测量：同一 Mac mini 实体 HDMI 运动图案，3840×2160 SDR YUV444 输入，
输出 2160p60 YCbCr4448，TEE 与 One-KVM H.265 同时启用；预热 15 秒、稳定窗口 600 秒。
接收端 Chrome 156.0.8078.47，平均 **59.98974fps**，区间 decoded drop、packets lost、
freeze、PLI 均为 **0**，无重新请求关键帧。解码均值 2.153ms/帧。
呈现间隔 P99 33.2ms、最大 67.5ms，超过 50ms 两次、超过 100ms 零次；
浏览器回调漏采 1733 次，不将它写成编码/解码丢帧，也不据此宣称显示每帧完全无重复。
较宽的板端采样区间 14:40:42–14:51:10 UTC 内 vfm_cap received/delivered 各增 37657、
dropped 保持 0；池占用 2→3/16，pending=0，ready=0→1；VD1 显示计数持续推进。
窗口开始之前曾有 `put: unknown vframe idx` 日志，尚无重配生命周期安全结论。
原始证据为 `logs/passthrough-515/patched-4k-{before,after}.log`、
`patched-4k-h265-600.log`、`patched-4k-motion.log`（本地日志不入 Git）。

用户在初次收尾指令确认 **4K60 十分钟目视正常、1080p 模式跟随正常**。
1080p 当时只有用户目视结论，没有独立十分钟物理时序采样；随后诊断仍读到 4K。
Mac 显示 API 的 1920×1080 不足以证明线缆时序已变化；用户最终说明当前仍发送 4K，
1080 只是逻辑缩放，与 RX/VDIN/TX 的 3840×2160 读回一致。
因此先前的“1080 跟随正常”不记为真实 1080p 通过。
初次 4K 十分钟测量是静态 TX 配置，尚未运行后来引入黑屏的模式跟随服务，
不能用该测量掩盖后续 manager 跟随逻辑的回归。

## 管理器交付与板上收尾

provider 提交 `vim4-manager@e59e187`，基于用户设计的 `passthrough-ui@974ab40`。
未修改该设计的前端布局、文案或组件源码；构建生成的 tsbuildinfo 已撤销。
限定助手探测 5.15、准确 TEE 路由、sysfs 和 root 管理的模块资格文件，
其 `moduleNoteSha256` 必须匹配运行模块，不能只看 uname。
独立 `vim4-passthrough.service` 跟随输入和 OUT HPD，报告实际 input/monitor/output/scaled，
输出读回和显示计数推进后才报告 running；关闭只隐藏 VD1、恢复 OSD，保留采集路由。
仅启用已验证的逐行 SDR YCbCr4448；HDR/隔行/未支持刷新率明确拒绝。
音频 true 请求明确拒绝并保留原状态，不抢占 One-KVM 音频 PCM。

板上已备份 `/var/backups/vim4-manager-passthrough-515-20261024/manager-and-platform.tar`，
包含旧 manager 可执行文件、helper、manager/HDMI 单元、hdmi-setup 与 manager 状态目录。
安装已构建验证的 e59e187 测试版并保留，不因正式合入重新安装、重启板子或改默认内核。
配套用户态配置已安装：`HDMI_DISPLAY_TEE=1` 单独位于
`/etc/default/vim4-kvm-passthrough`，由 HDMI 服务在源启动前核验模块并接入 TEE。
原 `/run` 测试 ExecStart 覆盖已删除，已实际重启一次 HDMI/One-KVM 验证正式配置可启动；
这发生在初次停止测试指令之前。随后黑屏修复仅替换脚本、重启跟随服务，不重启 KVM 或板子。
板上资格文件 `/etc/vim4-kvm/passthrough-5.15.json` root:root 0600。

已有 API 记录：GET supported=true、running；POST off/on 返回 200 并读回 off/running；
audio=true 返回 500 和明确未验证错误，随后 audio 仍 false、透传仍 running。
这些是控制接口读回，**不等同于用户目视实际开关或关闭态长测验收**。
初次收尾 One-KVM 已恢复测试前 H.264；最后只读确认是用户 UU 正在使用的 H.265，
按用户“不再改动板子”的新指令保留当前编码模式，不再次切换。
One-KVM、manager、HDMI 与生产透传跟随服务 active，UDC configured。
初次收尾时临时浏览器、性能采样、运动图案均已结束，用户协作文件清空、双锁释放；
后续黑屏修复按新授权重新取双锁并进行只读观察；最终用户取消剩余观察，
观察进程随中断退出，已确认没有残留观察/动态图案进程，双锁再次释放，不再请求用户操作。
生产 `vim4-passthrough watch` 为实际 provider，不当作测试进程关闭。
默认仍厂商 5.15，正式 7.3 eeddb005 保留。此次不重打或安装完整内核包：
正式分支为同一三行修复快进，已安装模块与已验证候选内容相同。

管理面板登录后进入 **HDMI 输出**（`#/output`），使用“透传”开关；声音保持关闭。
当前可读到 supported=true、enabled=true、running，input/output 为 4K60、scaled=false。
回退时先停生产透传服务，再恢复上述备份及旧用户态配置并重启相关服务；
驱动回退另用前述模块/initrd 备份，需独立窗口，不在用户 UU 使用中执行。

## 待验证

- 真实 1080p60 与十分钟稳定/并发编码；当前 Mac 仍发 4K、1080 为逻辑缩放。
- 黑屏修复后的长时间无黑屏目视确认；零 modeset 计数不代替显示器目视验收。
- HDMI IN/OUT 拔插、源重配后的引用生命周期及 KVM 自动恢复。
- 音频直通及与现有 RX PCM 所有者共存，当前未实现可用音频开关。
- manager 开关实际画面动作、关闭态长期采集、重启后偏好恢复。
- sink 限制下的缩放、420 输出、HDR 与其他刷新率；当前只交付已验证 SDR 444 路径。

## 周期黑屏：诊断与修复

用户报告正式使用中周期黑屏、自动恢复，暂停合入并追加定向修复授权。
只读诊断不改 TX、VDIN 或请求文件：35 秒记录 227 次读回变化，RX 报告
59.86–59.99Hz，其中 59.98/59.99 各 102/94 次；41 次不匹配全部为
`frac_rate_policy`，没有 attr、sname 或 ready 不匹配。原始例：
RX 59.97Hz 时旧算法选 fractional=true，而 TX 仍为 `"0\\n"`；
attr 为 `"444,8bit\\n\\n"`、ready 为 `"1\\n"`、sname 为 `2160p60hz`。
旧代码已 strip 外围空白，实际根因不是 attr 换行，而是每次取最接近的 60/59.94Hz，
在约 59.970Hz 分界两侧反复翻转，再以读回不相等为由整批重设 TX。
相应 78 秒内 kernel 日志有 18 次 `hdmitx_set_dispmode`，HPLL frac_rate 0/1 交替。
证据：`blackout-readonly-diagnosis.jsonl`、`blackout-readonly-kernel.log`（同一日志目录）。

代码审计及回归测试确认 status 路径只读，没有调用 tick；与 manager 轮询交错不是
多个 writer 的证据。实际写入者为独占 flock 的 watch 服务。
`vim4-manager@bf878a5` 修复如下：

- 七次 RX 采样中值，60/59.94 分界 ±0.005Hz 滞回，新输入/sink 模式稳定两秒才允许重配。
- 缓存输入尺寸、稳定刷新率类别与 sink EDID 指纹；同一意图不因 TX 读回漂移反复 modeset。
- 规范化 sname 别名、颜色空白/后缀、数值字段；ready=0 先防抖两秒，不能触发 modeset。
- 重配失败也不每 0.5 秒重试；异常状态保留读回，真正重配记录原因、不匹配字段和原始值。
- status 不写硬件、不触发 tick；第二个 watch 在获得写权限之前被 flock 拒绝。

离线新增回归覆盖真实刷新率轨迹回放、59.94/60 真实切换、输入抖动撤销、
模式更改一次性提交、失败不循环、别名规范化、ready 瞬态/持续下降、只读轮询与双 writer。
manager Python 全套 174 项（12 跳过），Go 全套与 vet 通过。
备份 `/var/backups/vim4-passthrough-blackout-20261024`，仅替换
`/usr/libexec/vim4-passthrough` 并重启 `vim4-passthrough.service`；
新脚本 SHA-256 `0f99b055660f1fffafb61a6761a26653183733ef0253c67d1c33c7791c45118f`。
未重启 One-KVM、manager 或板子，不改内核与默认启动项。
修复后 15:16:56–15:26:56 UTC（排除服务初启五秒）的 600 秒 kernel 日志
`hdmitx_set_dispmode` 为 **0 次**；服务持续 running，实际 RX/VDIN/TX 仍为 4K60。
证据 `blackout-fixed-actual-4k-600.json`、`blackout-fixed-observe.jsonl`。
真实 1080p60 的 kernel cursor 观察未开始，未将 4K 替代 1080p 门禁。
用户最终明确取消 1080p 十分钟观察与新的目视请求，认可修复后从 15:16:51 起
`hdmitx_set_dispmode` 为 0 次的现状，要求保持板子不变、直接合入推送。
这属于取消剩余验收，不写成真实 1080p 或修复后长期目视无黑屏已通过。

## 最终合入

- common_drivers：`vim4-5.15-passthrough` 快进合入 `vim4-kvm-5.15@746f93e09`。
- vim4-manager：`main@205b3f7` 含 `e59e187` provider、`bf878a5` 黑屏修复及测试；
  合并时同时保留 `9b141c5` Wave5 隔离状态 API。前端与用户 `passthrough-ui` 设计逐文件一致。
- 主仓：`a5976fa` 接入单独用户态 TEE 配置与 manager 打包文件，本记录与索引随后提交 main。
- common_drivers 原有离线 CRG 事件回归通过，VDIN 补丁模块构建/checkpatch 与已上板修复见前文；
  manager 合入后 Go 全套、vet、Python 174 项（12 跳过）及主仓全套测试在推送前执行。

离线验证：主仓 unittest 243 项（7 跳过），初次 manager Python 162 项（12 跳过）、
Go 全套测试与 vet、前端构建、Linux ARM64 交叉构建通过；黑屏修复后 Python 为上述 174 项。
