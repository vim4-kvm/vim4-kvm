# 2026-10-31：正式uhd4完整构建与短烟测

用户审阅[r18](2026-10-31-hdr2-recovery.md)后认可两向恢复中位数持平、两栈都有长尾，批准集成。
停止完成至下一次STREAMON的额外等待作为不阻塞后续项，不再调整信号资格或DMA退休。
本轮承接[准备记录](2026-10-31-uhd4-formal-preparation.md)，用新队列等待合法长构建，未抢旧锁。

## 固定版本与完整产物

内核`8bca939d6bbd3e4d91e9f23b812e920172c99b3d`，tree
`0ce3bf8d9a1e57a97bdbaffa67610eceaddba579`，与r18相同。
以`uhd4.config`重编`7.3.0-vim4kvm-uhd4+`，Image/DTB/2338模块完整成功，没有磁盘满失败。
build ID `ef3b8573007371472c73ef61ec352a20c00faee7`。

| 封存项 | SHA256 |
|---|---|
| 完整内核包 | 032e0a3864a135b584de8c78785e11ba43d4ed9ef888301c628a098ac5d39432 |
| RAM payload | dcfabfeaa44314eda9f9050c9631dc13422681cd0cb70f02678f990619ca1831 |
| payload inventory | c804ec3c59e1899e59d078fc36cdf4d1672a6a365662f32811fd37c9bffa6d71 |

VM保留`~/build/hdr2-uhd4`正式构建及`hdr2-uhd4-formal-stage.tar.gz`、
`hdr2-uhd4-formal-candidate.tar.gz`封存档；Image、DTB、配置、模块与live proof细项锁入sources.toml。
One-KVM保持已审阅db848a52及926535c6…程序，私有GStreamer保持ffee02fb…，不换算法。

## 窗口与门禁

编译仅取heavy票据，结束释放；板票据排在kbase r9之后。复用当天r18的5.15基线，未重测。
最终有效窗口05:06:30–05:15:19 PDT，约9分钟；独立receiver的sampling互斥阻止其它编译。
前序工具失败均独立保留、退出释放票据，再排队重试，没有续租或连续占板绕过预算。

| 项目 | 结果 |
|---|---|
| 正式构建身份 | release/build ID/config及11个加载模块GNU build ID与新包匹配，taint=0 |
| 干净启动 | 无内核WARN调用栈、BUG/Oops、CMA失败；已有iwconfig弃用提示与已批准r18完全相同 |
| PQ | M6 HDR开关截图蓝色，活动HDR2 profile=1；实际网页3840×2160，60秒59.998708fps |
| SDR | HDR关回截图，活动HDR2 profile=0；实际网页3840×2160，30秒59.895670fps |
| NPU | VGG16、DenseNet CTC、YOLOv8n各3次，15个完整输出SHA均与5.15基准一致 |
| Panfrost | Mali-G52 MC4、正确像素、gl_error=0，fault/timeout零增量 |
| 最终交还 | 5.15默认、One-KVM/manager/HDMI active、UDC configured、16项保护文件SHA全部一致 |

MCP先截图判断空闲；页面/标签与较早截图一致，网页动画和菜单栏统计不作人类操作证据。
只操作显示器HDR及本次设置窗口，没有输入文本、裸Shift、声音测试或ptrace。
结束HDR关闭、设置关闭、原Chrome页面/滚动位置保持；5.15下再次截图确认。
HLG已实现，无真实源未验；此次不重复像素/VUI/逐buffer退休长测，沿用同树r18已验合同。

## 新工具发现与修正

1. reboot原先阻塞等SSH退出再读UART，首次丢失短autoboot提示，实际仍启动5.15。
   改为发起独立SSH进程后立即读串口，离线模拟SSH未退出时的提示/命令/登录流，硬件重试选中候选。
2. `/api/snapshot`仅返回缓存，无查看器时503“No frame available”。原就绪检查在offer之前要求JPEG与fps>0，
   会自锁。服务/API/UDC准入与receiver真实framesDecoded门禁分开，仍要求实际4K解码、同SSRC/codec及帧数推进。
3. 不设置RAM ethaddr时U-Boot使用02:ad:…，DHCP变为.162。通过既有SSH主机密钥核对新地址上的uhd4并正常回退。
   工具现在从运行基线读取实际MAC，仅在RAM setenv ethaddr后sysboot；不saveenv、不改默认项。
4. HDR切换中源状态暂为UNKNOWN。自动流程实际已进入设置并尝试切换，而非“所有点击前失败”；
   此前即时归因已更正。补有限等待及双向UNKNOWN宿主回归；最终板测由MCP逐屏确认、驱动profile与receiver验证，
   未声称修正后的自动M6整段流程另做了硬件重测。
5. 不覆盖已有同build ID封存目录是预期保护。失败重试在5.15下将本会话旧staging改名留证，再走原验证。

本地`logs/hdr2-r19/`、`logs/hdr2-r19-smoke*`保留原始UART、失败及有效窗口证据；用户屏幕不推远端。
检查器曾把ramoops误匹配为Oops，同时把已批准r18的iwconfig提示混作WARN调用栈；
按完整词边界、taint、真实调用栈重新核验，保留弃用提示，不把所有日志称零warning。

## 正式推广边界

通过后正式内核vim4-kvm-7.3指向8bca939d6bbd3，One-KVM vim4指向db848a52，主仓锁uhd4完整包。
5.15仍为默认，`retained_runtime`仍为uhd1，未将RAM验收写成持久安装；不发布外部Release或上游补丁。
**kbase与hdr10-remote分支需要rebase到uhd4，使用各自匹配的新构建并重跑回归。** 不改它们的工作树。
主工作树由用户自行fast-forward，本轮只在独立集成工作树合入。
