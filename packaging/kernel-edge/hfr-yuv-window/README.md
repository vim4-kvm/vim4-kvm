# HFR + YUV444 uhd7 临时窗口

阶段一只构建、验证本机文件。阶段二须协调者明确发出「开始上板」。
当前产物基于第二轮复审输入，协调者给出简化后的最终提交后重跑构建并核对 SHA。

## 入口

`rebuild.sh KERNEL_SHA ENCODER_SHA [ONEKVM_SHA]` 在独立登记的
`hfr-yuv-window` VM 工作树快进到指定完整 SHA。构建自动持 heavy 票，
使用正式 uhd7 配置、导出符号和 BTF。GStreamer 严格比较当前 sources.toml
的 candidate_plugin_sha256，不匹配就退出。可选第三参数重建 One-KVM。
源码导出到新临时目录，构建日志和产物保存在主仓忽略的 build/、logs/。

`python3 packaging/kernel-edge/hfr-yuv-window/window.py` 只做本机产物检查。
实际入口如下，窗口时长包括准入和恢复。

```sh
tools/board-queue run --who hfr-yuv-window --purpose combined --max-min 30 -- \
  python3 packaging/kernel-edge/hfr-yuv-window/window.py --execute
```

## 分钟预算

| 分钟 | 工作 |
|---|---|
| 0–3 | uhd7 release、Image ID、模块 notes、默认 FullKvm、服务、无活动 UU/介质、RTK 表一致、M6 原生 4K60 SDR 准入 |
| 3–6 | 原程序与候选各 10 秒 4K60，比较 fps、freeze、drop、loss；加载三个临时模块和程序/插件 bind |
| 6–10 | M6 固定原生 1080p119.88，若无则120。raw/AVC/HEVC各600帧，保存码流和SPS，网页12秒 |
| 10–14 | 原生1440p120，raw/HEVC各600帧、网页12秒；AVC生产路径50–61fps |
| 14–17 | 4K60 SDR8 YCbCr444，3600帧完整性及末帧；7帧池上限、25MiB拒绝、关闭采集后导出fd读取、回NV12 |
| 17–21 | 1080p Variable，120→80→60→48→120，输出限60；真实PTS、事件、VTEM基准、Vtotal及双编码网页 |
| 21–24 | 4K Variable，60→48→60，双编码网页与基准60；关VRR后基准归零 |
| 24–25 | 撤回EDID形成失锁，G_FMT重开不变、控件失效、原表恢复和解码重启 |
| 25–30 | M6模式/测试源恢复，正常重启一次，核验原模块/程序/EDID/配置/服务/UDC及4K60解码 |

25分钟触发恢复。后两项还单独检查剩余预算，时间不足直接裁掉。
不存在原生模式或Variable菜单时记录跳过。选择Variable但基准未确认时失败收尾。
脚本的失锁操作是EDID撤回，物理拔插另记未验。运行中不编译、不做码流解码分析。

## 临时加载与恢复

准入要求已经选用当前 RTK-CONTROL，保存表、安装表和RX读回完全一致。
通过现有manager选择和共享EDID助手恢复，不替换持久EDID资源。初始不是该状态则退出，
由协调者另行安排源准入。本窗口不尝试猜测或覆盖自定义EDID。

三个模块从 /tmp insmod，沿用原模块参数，比较实际notes与候选ELF。
程序覆盖目标由已安装launcher对应的usb-ffc6130路径固定，启动前核对当前进程身份。
候选GStreamer插件作为r14e私有目录的临时overlay，可加入原目录没有的libgstvim4rate.so。
One-KVM数据目录也使用临时overlay，
帧率、编码配置、插件缓存的写入随重启消失。所有已安装模块文件与启动文件原样保留。
结束和异常均安排一次正常重启，逐项比较原文件/notes并验证新boot ID。
SSH中断后仍检查恢复，不以SSH命令退出码代替实际boot ID。

M6切模式、启动图样、Variable菜单均通过One-KVM MCP。源端命令先核验Apple M6及
单一RTK显示器，只在M6运行Swift图样；本机只编译，不运行显示/HID工具。
Variable菜单由当前截图OCR定位，识别不确定就退出。初始键盘布局须为英文。
源端看门脚本在超时或接收恢复请求时恢复原模式，候选MCP失效也能触发。
MCP隧道为本机18081→板子127.0.0.1:8081。receiver复用tools/board-window，
当前工作树缺kvm子目录时使用同级vim4-kvm/kvm/ui/node_modules/playwright/index.mjs。

每段板命令由timeout约束，主进程为恢复预留5分钟。硬锁或DHCP异常仍可能导致恢复
校验失败，须保留证据报告，不能把finally的存在视为恢复已验。宿主mock只验证
中途激活失败会进入重启/身份校验/sampling-off链。

## 离线分析与边界

原始证据在logs/hfr-yuv-*，receiver的独立目录以相同前缀命名。
HFR码流在板外用ffprobe读取profile/level/像素格式、ffmpeg解码并核验三个内容标记。
PTS日志用于逐秒和慢转快第一完整秒输出数统计，网页getStats仅证明接收解码推进。
YUV444读取的是原始Y/Cb/Cr，编码器输出仍为420。

本脚本的普通v4l2src caps短采每次重新打开，按最终驱动和插件实际能力记录。
自然同尺寸range变化、未知基准控件−1、PQ、物理拔线、音频和长稳均未承诺覆盖。
源端4K HiDPI、Variable菜单与候选服务恢复均待实际板窗确认。
