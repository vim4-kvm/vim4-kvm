# 2026-10-24：厂商 5.15 HDMI 透传

后续 OUT 热插拔问题与修复见 [HPD 恢复记录](2026-10-24-vendor-passthrough-hpd.md)。

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

详细源码、带宽和备选路线分析见 [5.15 TEE 设计](2026-10-24-vendor-passthrough-design.md)。
选择 `vdin0 vfm_cap amvideo`，不增加第二个采集所有者、不降低 KVM 设置。

## 实验与接入原则

双锁内备份并接入 TEE，分别核对输入/显示/编码推进与丢帧，未完成项不写通过。
候选内核部署需独立确认；用户最终授权保留现状、合入推送，不能以合入代替验收。

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

细节与证据见 [周期黑屏修复](2026-10-24-vendor-passthrough-blackout.md)。
RX 报告在约 59.970Hz 的 60/59.94 分界两侧抖动，导致旧跟随逻辑反复重设 TX。
`bf878a5` 加中值、滞回、稳定防抖和每意图单次提交；状态轮询只读、watch 单写入者。
修复后 15:16:56–15:26:56 UTC 的 600 秒 TX 重设为零，实际为 4K60。
用户随后取消 1080p 观察与额外目视，授权按现状合入，不将取消验收写成通过。

## 最终合入

- common_drivers：`vim4-5.15-passthrough` 快进合入 `vim4-kvm-5.15@746f93e09`。
- vim4-manager：`main@205b3f7` 含 `e59e187` provider、`bf878a5` 黑屏修复及测试；
  合并时同时保留 `9b141c5` Wave5 隔离状态 API。前端与用户 `passthrough-ui` 设计逐文件一致。
- 主仓：`a5976fa` 接入单独用户态 TEE 配置与 manager 打包文件，本记录与索引随后提交 main。
- common_drivers 原有离线 CRG 事件回归通过，VDIN 补丁模块构建/checkpatch 与已上板修复见前文；
  manager 合入后 Go 全套、vet、Python 174 项（12 跳过）及主仓全套测试在推送前执行。

离线验证：主仓 unittest 243 项（7 跳过），初次 manager Python 162 项（12 跳过）、
Go 全套测试与 vet、前端构建、Linux ARM64 交叉构建通过；黑屏修复后 Python 为上述 174 项。
