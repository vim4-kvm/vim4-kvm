# 2026-10-24：7.3颜色与透传源码合入

按用户决定，将颜色与透传工作合入正式源码分支，避免遗忘；仍优先推进厂商5.15透传。
本轮纯离线，未访问板子、取得板锁、打包、部署、切换默认项或更新已部署版本锁。
原始采集长测与自环启动证据见 [实现记录](2026-10-24-hdmi-passthrough.md)。

## 合入范围

起点为远端及本地 `vim4-kvm-7.3@302f6e0fffa6d`。它正是颜色分支的基点，
无需rebase；保留已推送的小提交和功能分支，用两个 `--no-ff` merge 保留主题边界。
正式分支工作树为VM `~/src/linux-7.3-hdmi-integration`，其他功能工作树保持原分支。

| 范围 | 原始提交 / 合并点 |
|---|---|
| 颜色10提交 | `302f6e0fffa6d..c24465df1dd70`；合并 `5a173e2dee1d8` |
| RX/VDIN七提交 | `c24465df1dd70..41c31fc123935` |
| 自环启动两提交 | `86c2ea484d38d`、`cf6e2381164af` |
| VD1三提交 | `d4e7e46533b37`、`8e0c1a641c061`、`06ba4ba9f2e27` |
| 透传12提交合并点 | `de26c7df1ce47` |
| 默认关闭状态的bus回归测试 / 新HEAD | `213f271505411845eecb3c6ef10df7565b895ebc` |

没有合入lowclock PHY候选、WIP HDR或linux-next迁移。RX测量修复本身对KVM采集有价值，
虽已随本轮合入，仍可按七提交单独评审；不依赖透传用户态消费者。
基线23.13% ERROR为短测观测且有传输干扰，四窗口候选的四档长测各约610秒、
36601有效帧、0 ERROR/观测失锁；适用范围和完整性限制沿用原记录。

## 已验范围与默认开关

这里“已上板验证”指此前功能候选的针对性证据，**不代表合并后的新HEAD已经上板**。

| 项目 | 验证状态 | 默认状态 / 生效条件 |
|---|---|---|
| POST2、OSD SDR矩阵与颜色资源 | 已上板验证短窗口颜色样本；完整颜色矩阵不是单次长测通过 | 只在显式M3 profile持有新增资源；正式M0不进入 |
| Broadcast RGB | 已上板验证full/limited样本 | M3 native connector挂接标准属性；M0不创建该connector |
| TX input bus格式提交c24465df | 仅离线协商验证；曾随HEAD启动不替代专项验收 | 既有 `amlogic,atomic-color`，仅M3/M3-video声明；关闭时仍固定YUV8 |
| RX FDET及四窗口重测、VDIN元数据/诊断 | 已上板验证真实源与自环四档持续采集 | 现有采集路径生效，不另加关闭测量修复的开关 |
| 自环无换线启动 | 已上板验证720p回退接管及1080p60/4K60重新modeset短测 | native ENC2且managed OSD SRAM的已知布局；M0不进入 |
| VD1 reader、退休fence、地址更新 | 仅离线，硬件完整性及60fps尚未验收 | 既有 `amlogic,video-planes`，仅显式M3-video启用；M0/M3不创建视频平面 |

没有新增私有sysfs、ioctl或默认开启的实验参数。视频旧帧仍保留锁存后的完整扫描周期；
地址更新只提前完成atomic依赖，reader退休与framebuffer引用保护保留，故障继续pin住可能在DMA中的帧。
源码包含驱动不等于启用DT实例；构建所有实验DTB也不会自动选择它们。
`packaging/kernel-edge/sources.toml` 仍固定已部署M0产物，本轮不改变该锁。
从合入前源码独立预处理/编译M0，与本轮完整构建的M0 DTB逐字节一致；五档DTB检查确认
atomic-color仅M3/M3-video存在，video-planes仅M3-video存在，M0没有native display实例。

## 离线验证

本地证据：`logs/hdmi-passthrough/integration/`；完整输出为VM
`~/build/kernel-hdmi-integration/`，使用先前完整验证配置，独立O=目录。
| 检查 | 结果 |
|---|---|
| 颜色合并点host fixtures | 68/68，干净源码 |
| 最终213f271505411 host fixtures | 69/69，干净源码 |
| 新增普通提交strict checkpatch | 23条全部0 error/warning/check |
| 两个merge的提交信息与签名 | 已核对；全部25条新历史签名齐全 |
| 完整Image/DTBs/modules | 通过，2339模块，含BTF；独立输出目录完整构建 |
| 三个显示binding及五档DTB schema | 全通过，零诊断 |
| M3 OSD/video实际DT资源fixture | 均通过 |
| M0默认profile及开关 | 与合入前M0逐字节一致；五档开关检查通过 |

M0 DTB SHA256为 `3f3125f10eaf7900849ca44dfa995501242b5a9766982cee25d96b457715cdb8`，
比较对象是合入前正式源码302f6e0，并非此前部署产物的版本锁。
完整构建build ID为 `62624239a50d72f8c13e657597610fa3ab38360f`，Image SHA256为
`e8f1397449b278edd81b66bec4c45e169b9ace1ba4d68627f6186dbc13734eca`；
有效配置SHA256为 `9d142f92c2ea15be0901abe57e535a8190c586a22ff1667410a368c670cef663`。

新增bus回归测试先因提交正文未换行触发strict warning，修正文案后全系列重跑；
首轮日志保留在 `attempt-1/`。KUnit/QEMU及本轮硬件测试未运行。
M0独立编译脚本首次漏取input头文件符号链接目标、其次TX节点定位错误，修正后比较及
五档开关断言通过；这些检查脚本的失败日志均保留，未因此修改内核或放松默认开关。

## 恢复7.3透传的顺序

1. 先协调5.15任务与双锁，在正式分支验证RX修复下的One-KVM有效帧率、ERROR和编码回归。
2. 用显式M3-video一次性候选验证真实stride/UV offset、60fps地址更新、逐行帧一致性、
   原退休期、源变化和fault pin；同时补bus格式提交的硬件协商验收。默认M0不切换。
3. 完成标准DRM属性/IN_FORMATS/PRIME与采集所有者实际EXPBUF的能力合同，以及最小参考工具。
   目前没有已实现的透传能力属性，不能因NV12枚举就让manager报告supported。
4. 在One-KVM原生采集后端增加显示消费者：单一VDIN队列、每缓冲只导出一次DMA-buf，
   generation感知的帧租约同时等待编码读完和显示READ退休；拒绝ERROR后再分发。
   OUT_FENCE只代表锁存，不能单凭它归还QBUF。
5. manager provider查询该采集所有者的能力与运行状态并控制显示消费者，避免另开采集队列。
   完成真实源两档各≥10分钟透传、热插拔/分辨率恢复及独立ALSA回送验收；自环始终禁音频回送。
