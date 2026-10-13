# NanoKVM-Pro 的 VIM4 功能状态

2026-10-13 按当前 VIM4 路由与前端条件核对；上游目录中存在代码，不代表
已注册对应接口或已完成 VIM4 适配。硬件仍只有 HDMI 和 USB-C。

| 功能 | 当前状态与边界 |
|---|---|
| H.264 WebRTC | 已接入，4K60 已测；延迟与测试范围见 latency.md |
| H.265 WebRTC、H.264/H.265 Direct | 已接入，4K60 静态桌面约 60fps 已测；Direct 需 WebCodecs（HTTPS 或安全上下文）；H.265 需浏览器支持解码 |
| MJPEG、分辨率、码率、GOP、帧率、缩放/旋转 | 已接入；MJPEG 是软件编码，限制为最多 10fps，不等于 H.264 的 4K60 能力 |
| HDMI 声音 | WebRTC 视频随附音频；MJPEG/Direct 通过独立纯音频 WebRTC 会话播放，四种模式 50 包/秒已测 |
| 键盘、绝对/相对鼠标、快捷键、文本粘贴 | 已接入；长按与 Mac 滚轮的实测见 input-latency.md；输入法/断网/多客户端边界未全部验证 |
| 镜像上传、下载、管理、虚拟磁盘/CD-ROM | 已接入并验证 Mac 枚举；被控端完整文件读写仍待验证；虚拟介质与 NCM 互斥 |
| 终端、脚本、Wake-on-LAN | 已接入；WOL 报文验证过，真实睡眠主机唤醒未验证 |
| 网页账户、网络设置、SSH、mDNS、时间、主机名 | 已接入；网页账户独立于 Ubuntu；Wi-Fi 真实连接、改当前 IP 和关闭 SSH 未实测 |
| 应用更新 | 手动包与自定义源更新已验证；没有公开更新源，不接收原厂 AX630 固件 |
| Ubuntu 系统镜像 | 已有官方基础镜像组装、校验、导出和刷写工具；候选镜像首次实机启动回归仍待完成 |
| 浏览器麦克风→被控机 | UAC2 已接入：开启时替换 USB 网卡，可与虚拟介质并存；浏览器到板端 aplay 已验证，主机实际录音待授权复测；需安全上下文 |
| CBR/VBR | CBR 为厂商目标码率控制（运动时约超出 1/3）；VBR 加 QP 上限 36，画质优先、码率可超出目标 |
| 自定义 EDID | 已接入：厂商 4K60/1080P60 预设和上传 128/256 字节 EDID，开机自动恢复 |
| HDMI passthrough、HDMI 采集开关 | 未接入；HDMI-OUT 未连接，按用户决定暂不实现 |
| Tailscale | 已接入：签名 apt 源安装、登录链接、启停、卸载已测；真实账号组网未验证 |
| AI 助手 | 已接入：venv 安装、启动、预览、HID 映射已测；需用户自备模型 API Key，推理任务未验证 |
| 鼠标防休眠 | 已接入，相对/绝对模式和重启保持已测 |
| 原机低功耗设置 | 原对应控制未启用，不能声称已支持 |
| ATX 开关/重启、指示灯、外接串口、OLED、灯带、屏幕策略 | 无配套硬件；硬件操作未适配/验证，不能用不相关 GPIO 代替 |

保留原 NanoKVM 控件的外观与行为，并不意味着所有上游功能已经启用。
支持状态以 VIM4 构建注册的接口、硬件实现和验证记录为准。

## 本轮静音原因

HDMI RX 报告 48kHz 音频正常，Chrome 音频 ICE 已 connected，但收到的是
3 字节静音 Opus 包，totalAudioEnergy=0。播放定向 AML TV 的 440Hz 测试音仍静音。
ALSA 的 `TDMIN_B source select` 为硬件默认 `tdmin_b`，录音设备实际读外部引脚。

切换为 `hdmirx` 后，48kHz 双声道录音检测到 440Hz；浏览器收到非静音 Opus。
修复由板级 HDMI 服务 ExecStartPre 负责，每次启动明确设置路由，并排在 alsa-restore.service
之后；board 包补充 alsa-utils 依赖。不依赖工作板偶然留下的 mixer 状态。
使用 ExecStartPre 确保服务被认为启动成功、NanoKVM 可以开始录音之前已完成路由设置。

浏览器原音量控件每次页面初始化默认静音，需要主动调高；这与板端静音是两个问题。
当前同一台 Mac 兼任音源和查看端，系统默认输出是 AML TV：网页声音即使解码成功，
也不会自动从内置扬声器播放。同机监听需分别安排音源的 HDMI 输出和浏览器的监听
输出，不能把所有系统声音改到扬声器后仍期待 HDMI 携带相同声音。

证据：logs/audio-current-*（故障）、logs/audio-route-*（修复后）、
logs/audio-pcm-tone.log 和 logs/audio-route.pcm。浏览器测试使用原音量菜单，
没有绕过自动播放策略；验证的是非静音音频到达浏览器，不是扬声器的实际听感。

恢复路由后还发现发送节奏问题：VIM4 的阻塞采集已经按 20ms 输出 Opus，发送
循环又等待 20ms ticker，实际只发约 42–46 包/秒，接收端产生缺音补偿。VIM4
成功读取时改为直接发送，空闲/失败仍限速；非 VIM4 保持原节奏。修复后的
6 秒稳态区间收到 300 包、288000 个采样，丢包与缺音补偿增量为 0；启动阶段
仍可能发生补偿，不声称长期或所有网络条件下零缺音。证据 logs/audio-pacing-*。

复测非静音链路（Mac 有 AML TV HDMI 输出时）：

```sh
clang tools/hdmi-audio-tone.c -framework AudioToolbox -framework CoreAudio \
  -framework CoreFoundation -o /tmp/hdmi-audio-tone
/tmp/hdmi-audio-tone &
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  node tools/audio-smoke.mjs http://192.168.50.210:8080 --expect-signal
wait
```

测试音仅发送到 AML TV，不改变系统默认输出。audio-smoke 使用独立 Chrome
与原音量菜单，报告包速率、缺音补偿和音频能量。未播放测试音时不要使用
--expect-signal；能采到全零 PCM 不等于验证了实际声音。

最终 .9 组件重启后的 6 秒复测有声音、丢包 0，但仍有 3924 个补偿采样（7 次
事件），所以此前单轮零补偿不能推广到所有会话。音频长期稳定性还需专门测试。

当前含修复的候选镜像：build/images/vim4-kvm-ubuntu-1.0.3-reliability19b/。
它从官方 Ubuntu 基础镜像和干净源码组件组装，启动配置、依赖、文件系统与
校验和已检查；没有执行这份镜像擦写 eMMC 后的首次启动验收。

最新可靠性回归：组件 .19 配合内核 b86c7e5bd，HID epoll 描述符跨重新绑定
20 轮、原查看端在线时麦克风/虚拟介质组合切换 3 轮通过。默认启动改为 ext4
ordered、commit=5；网页更新使用与组件部署相同的应用 deb。当前用户选择的
1080p60 视频及非静音 HDMI 音频通过冒烟测试，不代表长期零卡顿或全新刷机通过。
