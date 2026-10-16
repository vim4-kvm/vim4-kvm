# 2026-10-15：Screen Sharing 退出后物理桌面未恢复：同步取证

用户反馈同一台 Mac 连接普通物理显示器可以自动恢复；当前 VIM4 则需要重新
协商。板子运行 `5.15.137-vim4kvm`、板级包 `2.5.1+vim4.20261014.24`，
使用 One-KVM 和 VIM4-4K60 EDID。本轮没有修改或部署生产代码。

首次现场：RX 为 3840×2160、YUV420 10bit、约 59.98Hz，avmute skip=0；
vfm_cap 为 sm_state=5、fmt_valid=1，接收和交付计数继续增长，发送日志约
60fps。Mac 在线显示器只有 1920×1080、vendor=`0x756e6b6e`（unkn）、
model=`0x76697274`（virt），没有 AML TV。`HDMI_HPD=Yes`、
`HDMI_HPD-Debounced=0` 在恢复前后相同，不能据此判定连接故障。

用户配合重新进入、退出高性能 Screen Sharing，同步记录两端状态。以下为 UTC，
Mac 原始 unified log 使用 UTC+8：

- 06:02:57：WindowServer 创建 Screen Sharing Virtual Display（ID 341），
  明确记录 `Disconnecting display 2 due to exclusive display`；板端 RX 失锁。
- 06:03:09.770：WindowServer 释放 ID 341；DCP 启动 3840×2160@60 链路，
  startLink 返回成功；WindowServer 插入并处理物理 display 2 的 hotplug in。
- 06:03:09.969：移除共享虚拟屏后，桌面却切入新的兜底虚拟显示器 ID 342
  （unkn/virt）。不是共享虚拟屏对象一直没有销毁。
- 06:03:10：VIM4 自动回到 FSM_SIG_READY，恢复 4K60 采集。与此前一次记录
  不同，本轮确实有失锁/重锁，不能把“虚拟屏切换不产生 RX 状态变化”泛化。
- 06:05:38–39：执行 `hpd0 1`、间隔 0.5 秒、`hpd1 1`，Mac 重新枚举 AML TV；
  用户确认画面恢复。06:00:13 的首次现场也用相同方法恢复，用户同样确认。

两次都没有写 EDID 内容、调用 EDID_UPDATE ioctl 或重启应用/HDMI 服务。
debug HPD 路径调用 rx_set_cur_hpd，可能条件性复位 EDID 模块，因此不能称为
完全隔离所有接收端副作用的电气实验。第二次脉冲前 TOP[8] 和 TOP[25] 都是 0，
按当前源码的 offset 判断不满足 EDID 模块复位条件；未跟踪分支实际执行。
HPD 操作本身仍导致正常失锁与重锁。

已确认故障边界：物理 HDMI 链路与采集恢复后，Mac 的桌面未重新挂到物理屏；
无信号/无帧看门狗无法识别此状态。尚未确定普通显示器与 VIM4 的具体差异，
不能归结为 macOS 必然如此，也不能据 HPD 有效证明 EDID 内容损坏。
DDC/SCDC 快照不是总线事务或 ACK 记录，不能排除瞬时握手问题。
Mac 的 HDCP 重试在正常显示期间也存在，当前不能作为本故障的特异性判据。

后续应在相同连接条件下对照普通显示器与 VIM4：优先用已知能恢复的显示器
EDID 做 A/B，再分离模式/色深/SCDC 能力与 HPD/DDC 时序的影响；每次需完整
进入和退出共享会话，不能以切 EDID 当场恢复替代回归。未部署周期 HPD，
未声称自动恢复已修复。实验结束保留原 4K60 EDID 与已恢复桌面。

证据：`logs/hdmi-virtual-20261015/`，含 control-transition.jsonl（180 秒）、
kernel-transition.txt、mac-transition.txt、mac-display-detail.txt、
mac-kernel-display.txt 和两次恢复记录。内核日志跟踪用 timeout 正常结束（124）。

## 普通物理显示器也复现（同日后续）

用户修正此前的对照结果：同一台 Mac 直接连接普通显示器，退出高性能共享后
也无法恢复。现场 IOKit 识别 `RTK UHD HDR`（RTK、product 6938），在线桌面
却仅有 1920×1080 的 unkn/virt 显示器 ID 359。系统为 macOS 27.0.1（26A434）。
这推翻了“普通显示器正常，所以优先查 VIM4 独有兼容问题”的前提。

06:16:43 UTC，Screen Sharing 创建 ID 358，WindowServer 记录断开物理屏 2，
CoreAnimation 记录 `Display 2 setEnabled:0`。06:16:48 共享屏销毁，DCP 报告
startLink 成功、linkStable=YES；WindowServer 处理物理屏的 hotplug in 后仍
选择兜底虚拟屏 359。不是 VIM4 采集服务导致，也不是共享虚拟屏未销毁。

06:20:51，用临时诊断程序在当前会话对 display 2 调用
CGSConfigureDisplayEnabled(true)，begin/enable/complete 均返回 0；日志确实
出现 `Display 2 setEnabled:1`，但在线列表仍只有 359。返回成功不能作为
物理桌面恢复的证据，也不能仅凭缺少 setEnabled:1 判定根因是启用开关残留。
两份 WindowServer 显示配置 plist 已备份，没有删除或重置用户显示设置。

用户授权暂时停止 UU 对照。已退出 UU GUI、用户服务和 UURemoteServer；
系统级 UURemoteDaemon 仍运行（停止需要管理员权限）。停止用户进程后现有
故障没有自行恢复，尚不能据此排除 UU 造成的历史状态或系统服务影响。
另一个 UUDisplay 辅助工具未在运行，其日志最后退出时间为前一天，磁盘中
没有 disabled-displays.json；不能仅因找到其禁用物理屏代码就认定它是原因。

证据：`logs/hdmi-physical-20261015/`。当前调查重点转为 Mac 显示配置恢复；
06:24:35–39 用户拔插物理显示器恢复后，06:25:02–07 只使用 Apple Screen
Sharing 再次进入退出，仍黑屏。此次 UU 用户进程全程没有运行，root daemon
仍在；Screen Sharing 虚拟屏 ID 360 被销毁后出现兜底屏 361。
完整流式日志明确记录退出时 `Display 2 setEnabled:1`，纠正此前只看部分日志
产生的“没有重新启用调用”线索：有启用调用也未成功恢复在线物理桌面。

随后尝试当前会话内禁用再启用 display 2：禁用返回 1001，取消该事务；
启用和提交返回 0，但仍只有兜底屏。因此这次不能声称完成了有效的开关循环。
没有继续操作低层寄存器、重启 WindowServer 或删除显示偏好文件。

UUDisplay 源码 PhysicalDisplays.swift 明确记载其私有 API 禁用状态可能在进程
退出后保留，与现场有相似性，但本轮没有调用者追踪，不能证明是它留下的状态。
用户提出重启；下一项有效对照是正常重启 Mac 后先不启动 UU/UUDisplay，
从物理屏正常显示开始只测试 Apple Screen Sharing，以排除当前会话历史状态。
测试中 bootout 了 UU 用户 launch agent，没有写入持久禁用设置；系统 daemon
未停止，重启后需核对 UU 是否自动启动，不能默认环境已干净。

## 重启后 EDID 对照与保留 RTK（同日后续）

用户重启后报告普通物理显示器可以自动恢复。切回 VIM4 后，原 VIM4-4K60
仍复现：06:39:56 UTC 进入共享导致失锁，06:40:09 自动重锁 4K60，但 Mac
选择 unkn/virt 兜底屏。UU 用户服务、GUI、Server 和 root daemon 已自动启动，
UUDisplay 未运行；因此不能把这轮叫作没有 UU 的环境。

从此前 RTK UHD HDR 的 IOKit EDID 提取原始 256 字节，两块校验和均有效，
经同一个 vim4-edid 助手加载后进行实际进入/退出共享对照：

| EDID | 实际输入 | 退出后自动恢复 |
|---|---|---|
| 原 VIM4-4K60 | 4K60 YUV420 10bit | 失败 |
| 完整 RTK UHD HDR | 4K60 YUV444 8bit | 成功，06:42:52 退出 |
| 回切原 VIM4-4K60 | 4K60 YUV420 10bit | 再次失败 |
| 原表取消深色能力 | 4K60 YUV420 8bit | 失败 |
| 上一表允许完整色度 4K60、TMDS 上限 600MHz | 4K60 YUV444 8bit | 失败 |
| 原表仅增加 DPMS Active Off 位 | 4K60 YUV420 10bit | 失败 |
| 再次加载完整 RTK UHD HDR | 4K60 YUV444 8bit | 成功，06:48:43 退出 |

两次 RTK 成功均有用户画面确认、Mac 在线显示器枚举和板端采集状态支持。
原表失败时采集仍推进。结果支持 EDID 内容/身份所触发的 Mac 显示配置差异；
不能归结为单独的色深、YUV420 或 Active Off 能力位。尚未区分其他能力字段
与按显示器身份保存的 Mac 配置；用户选择停止进一步身份对照，保持 RTK。

完整 RTK 原件保存为 `board/edid/rtk-uhd-hdr.bin`，SHA256 为
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。
板上 `/var/lib/vim4-kvm/edid/active.bin` 哈希相同，active.name 为 RTK-CONTROL，
当前 One-KVM 继续使用它。未替换默认预设、未部署周期 HPD；也未同步修改
JetKVM 独立保存的 EDID，不能声称四套应用切换与整机重启回归已通过。
证据与实验变体位于 `logs/hdmi-post-reboot-20261015/`。

用户随后要求 JetKVM 也使用 RTK。在 vim4-kvm.service 为 inactive、One-KVM
继续运行时，仅将 `/var/lib/jetkvm/config.json` 的 hdmi_edid_string 更新为
RTK 原件的十六进制值，读回比较确认其他配置字段未变。原配置保存在板上
`/var/lib/jetkvm/config.json.before-rtk-20261015T065353Z`（0600）。读回 EDID
SHA256 与 RTK 原件一致；调用 JetKVM 自身 edid-apply 助手返回 loaded=false，
即接收端已经加载相同表，未再次脉冲 HPD。当前 One-KVM 与采集继续正常。
没有改 JetKVM 内置默认预设，也没有实际切换四套应用或重启验收。
