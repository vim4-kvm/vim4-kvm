# 2026-10-23：M2 首个一次性窗口——60Hz 翻页、PRIME 上屏与颜色错误

接续 [原生 ENC2 离线实现](2026-10-23-display-m2-modeset.md)。候选能切换时序、
60Hz 翻页及 Panfrost PRIME 上屏，但**颜色错误，M2 整体验收未通过**。
TX/RX PCM 可同时运行，尚无 HDMI-OUT 物理音频证据；采集连续性受正式基线已有
`tmds-invalid` 重锁影响，不能写成“模式切换不影响采集”。未正式部署。

## 版本与一次性启动

窗口开始时正式内核为 `0a775305f0ad8`，build ID
`3a3cd15ca69e6084238d3bda54e41c56f6a16776`。M2 的 20 个提交干净 rebase 到该版本，
候选 HEAD 为 `c00b7b09c146b0be112468f3ef8d8de2f82963e2`，已推送 `vim4-display-m2`。
独立源码 `~/src/linux-7.3-display-m2`、输出 `~/build/kernel-display-m2`；
Image、DTB、2334 个模块、显示/RX/Wave5 离线测试、binding/schema 和逐提交 checkpatch
均通过；checkpatch 为 0 errors、0 warnings。候选 build ID：
`050266a8f8e4230da465e92487f9db0791606ccd`。

| 文件 | SHA256 |
|---|---|
| Image | `c3f6abf8a0d8130b3bf54001f7894e453cdce34a4d916639f8d9d9078cf41548` |
| 原始 M2 DTB | `8235b78e032b0c90bee426f4736ca814a295aae93b4c416830b6a87364725c31` |
| 修正板级 MAC 的安装 DTB | `2e011ba6e03438a89d43df4256cda15007d5343a281f308bde0c3e757bd88789` |
| 模块归档 | `bc16297ea112b73e7f8f747e23c1ae8d91e0e66466f5ee219637881fcb640ccc` |

在 Mac 的 `lockf vim4-heavy.lock → lockf vim4-board.lock` 等待前一采集窗口结束；
持双锁完成全部板上操作和采样，之后释放。静态一次性 PID 1 以
`-static -Os -Wall -Wextra -Werror` 构建，Linux 六项启动/失败回退测试通过。
使用现有 display-once prepare/stage；仅窗口副本的基线 ID 更新为 `3a3cd15c…`。
完整候选模块只读 bind，默认 Image/DTB/extlinux、模块原件和运行时登记不变。
串口只在 U-Boot RAM 执行：

```text
sysboot mmc 1:2 any ${pxefile_addr_r} /var/lib/vim4-kvm/display-m1/050266a8f8e4230da465e92487f9db0791606ccd/extlinux.conf; reset
BOOT_LOGIN_REACHED
```

未 saveenv、刷 U-Boot、改分区或部署锁。候选和默认启动各自核验 build ID，
两次均确认五个受保护文件哈希相同。RESET/看门狗本轮未主动触发；
实际验证的是正常重启离开一次性入口后自动回默认基线。

## 针对性结果

HDMI-OUT 连接 Mac 的 MACROSILICON/BUER 采集卡；HPD connected，EDID 256 字节，
monitor 为 `HDMI TO USB`，DRM 枚举 33 个有效模式。热拔插需要用户，按要求跳过。
物理帧由用户普通 Chrome 的 `http://localhost:8766/` 抓取，没有用 Playwright 打开摄像头。
connector=39、CRTC=37、OSD1 plane=35。

| 项目 | 实测 |
|---|---|
| 720p60 | EDID 未列出，跳过，未强制时序 |
| 720p50 | atomic 设置/关闭成功，采集到图案；颜色错误 |
| 1080p50 / 60 | atomic 设置/关闭成功，采集到图案；颜色错误 |
| 1440p60 | EDID 未列出，跳过 |
| 4K30 | atomic 设置/关闭成功，采集到图案；颜色错误 |
| 4K60 / SCDC | EDID 未列出，跳过，未验证 scrambling |
| 1080p60 page flip | 20 秒测试，稳定 60.00Hz；物理帧确认缓冲交替 |
| Panfrost PRIME | 1080p60 XRGB8888 可上屏，渲染器为 Mali-G52；同样颜色错误 |
| TX 音频 | ELD 有效，48k/S16/2ch PCM 播放成功；物理声音未验证 |
| HDMI-IN 共存 | 4K60 H.265 和输入音频可工作，但发生 RX 重锁冻结，连续性未通过 |

实际 atomic 命令示例（720p50、1080p50、4K30 分别替换尺寸和刷新率）：

```sh
sudo modetest -M meson-t7-handoff -a -F smpte \
  -s 39@37:1920x1080-60@XR24 -P 35@37:1920x1080@XR24
sudo modetest -M meson-t7-handoff -F smpte -s 39@37:1920x1080-60@XR24 -v
```

修正了两个测试调用问题后才保留正式模式结果：该 libdrm 的 atomic CLI 必须同时
提供 `-s` 和 `-P`；仅 `-s` 会零退出但不 modeset。跨进程使用 `#模式索引` 不稳定，
首次 720p50/1080p50 实际选到 100/59.94Hz；最终改用完整名称和刷新率，并核对
modetest 输出与 DRM state，重新抓取四种模式的帧。

翻页输出为首个频率 `60.16Hz`，随后 18 个 `60.00Hz` 样本；物理帧差异指标 61.39，
RMFB/进程退出均成功，无旧 M1 NULL fb 崩溃或锁存超时。这验证了当前候选的
RDMA 翻页路径，不能推导为所有 EDID 模式均能达到同样速率。

### GPU 与颜色问题

glmark2 2023.01，`DRI_PRIME=1`、显示 card0、Panfrost renderD128，
`--swap-mode fifo --visual-config red=8:green=8:blue=8:alpha=0:buffer=24`。
DRM 后端默认选择 4K，`--size` 没有改变选择；使用私有 LD_PRELOAD 测试 helper
仅过滤客户端看到的模式为 EDID 原有 1080p60，没有覆写内核 EDID。

```text
GL_RENDERER: Mali-G52 r1 (Panfrost)
GL_VERSION: OpenGL ES 3.1 Mesa 25.2.8-0ubuntu0.24.04.4
Surface Size: 1920x1080 fullscreen
[build] duration=5:use-vbo=true: FPS: 61
[texture] duration=5: FPS: 61
glmark2 Score: 60
```

strace 确认 card0 的 PRIME_HANDLE_TO_FD、renderD128 的 PRIME_FD_TO_HANDLE、
显示 ADDFB2 与连续 PAGE_FLIP 均成功，且物理帧出现 GPU 模型；这证明 PRIME
共享缓冲参与 GPU/显示路径，并非 llvmpipe 或离屏测试。没有总线级的每帧拷贝计数。
该分数带 vsync 和 strace，只表示这两个场景达到显示刷新率，不是 GPU 性能基线。
默认 4K 测试的 CREATE_DUMB EINVAL、1080p 默认带 alpha 格式的 ADDFB2 EINVAL，
以及恢复原 inactive CRTC 的 `-2` 均保留日志；这些失败测试的分数不作为上屏结果。

所有原生模式及 GPU 图案偏色：SMPTE 灰条应为约 `(192,192,192)`，采集为
`(196,127,132)`，黑背景呈青色。**疑似固件遗留 VPP RGB→YUV 矩阵与新 TX RGB
bypass 不一致，尚未读回证明根因**；本窗口没有裸写矩阵或共享寄存器试错。
离线复核已找到具体差异：厂商 `hdmi_tx_hw.c:config_hdmi21_tx()` 固定输入为
`HDMI_COLORSPACE_YUV444` / LIMITED，RGB 输出时启用 CSC0 `0x65/0x08`；
当前候选错误假设“VPP sends RGB”，强制 CSC0/1 bypass。后续应以这个实际输入约定
核对矩阵和量化范围，不能只改 AVI 的颜色声明。
后续须从厂商矩阵/输出总线路由补齐一致性及颜色测试，不能以“有画面”判 modeset 通过。

### TX/RX 音频与采集连续性

`VIM4HDMITX` 与 `VIM4HDMIRX` 同时存在。启动早期 ELD 快照为空，后续 DRM
查询/模式设置后为 `HDMI TO USB`、LPCM 2ch、32/44.1/48k、16/20/24-bit；
仍需检查初始 ELD 更新时序。按声卡 ID 启用 `FRDDR_A SRC 1 EN Switch` 和
`TOHDMITX I2S OUT EN Switch` 后执行：

```sh
speaker-test -D hw:VIM4HDMITX,0 -c 2 -r 48000 -F S16_LE \
  -t sine -f 997 -p 1024 -b 4096 -l 2
```

命令退出 0，TX/RX `/proc/asound/.../status` 同时 RUNNING；输入为 Mac HDMI 440Hz
测试源，WebRTC 解码音频峰值 0.12317。临时给普通 Chrome 抓帧页增加 BUER 音频探针，
得到 `No labelled BUER audio input`，没有改用默认麦克风或绕过授权；因此没有确认
TX 的 997Hz 真正经过 HDMI 到达采集卡。页面和服务已恢复原版，ALSA 持久状态已恢复备份。

120 秒模式切换共存段为 3840×2160 H.265、57.47fps、4 freezes、0 dropped/lost，
输入音频峰值 0.18192；35 秒音频共存段 55.90fps、2 freezes。
候选在显示模式测试前就有 `tmds-invalid users=0`，测试期间有 `users=1` 撤销/重开。
恢复后的同一正式基线五分钟也有 6 freezes，见下节及
[同链路 RX 对照](2026-10-23-hdmirx-vendor-comparison.md)。这些数据不能隔离显示的影响；
需要先部署/合入 RX 修复，再做匹配负载的显示开/关对照。含重锁的
`presentationCadence.presentedFps` 出现负值，不作为有效帧率指标。

## 回默认基线、冒烟与清理

正常重启没有拦截默认启动，串口再次 `BOOT_LOGIN_REACHED`。实际恢复结果：

```text
build_id: 3a3cd15ca69e6084238d3bda54e41c56f6a16776
protected_files: 五项均 true
one-kvm / vim4-manager / vim4-wave5-monitor: active
UDC: configured; isolated: 0; taint: 0
modules_mount: /dev/mmcblk0p2 / rw,...,data=ordered
```

simpledrm 的物理 HDMI-OUT 帧为正常登录控制台。约五分钟运动源冒烟：4K60 H.265
平均 58.55fps，0 dropped/lost，6 freezes，输入音频峰值 0.13818；残留问题是已知
RX TMDS 重锁，没有新增 oops、显示 timeout 或 taint。首轮 HID 检查相对鼠标断言失败，
原命令复测键盘按下/抬起、绝对/相对鼠标、click、wheel 全过：

```text
relativeBefore=[0.6999959309895833,0.5999891493055556]
relativeAfter =[0.7099039713541667,0.6117332175925926]
keyboardDown=1 keyboardUp=1 absoluteMouse=true click=true wheel=true
```

回基线、撤销模块 bind、保存证据后，清理本窗口的 `/var/tmp/display-m2-window-1`、
私有候选目录及三个过期 `vim4-kvm-stability-final{,-qualified,-recovery}` 内核回退点。
删除前核对旧回退点均为 `7b8372b8…`，保留当前正式部署的
`/var/backups/vim4-kvm-stability-pcm-final`（152MiB）；系统包管理、PD/U-Boot 备份及
其他任务临时文件保留。同步仅针对本地 ALSA 文件和本地目录，不做会等待 CIFS 的全局 sync。
实际释放 584454144 字节，磁盘空闲 18625458176 字节，使用率 38%。
最后再次查询三服务 active、UDC configured、isolated=0、taint=0 和目录已删除，
两把锁均已释放。用户离开期间没有要求手动 RESET 或拔插。

## 合入范围与下一窗口

仅提取已验证的 SMC 访问、HPD 当前连接状态与完整 EDID/DDC 四个基础提交，
基于窗口期间新推送的正式 `b1300eb808f43` 整理；不包含 RGB32/RDMA、TX PCM 声卡、
PLL/VENC/PHY 或原生模式切换。原生候选的 60Hz/GPU 路径有正面证据，但本次组合
存在颜色和采集连续性问题，不将整个候选推进正式分支。热插拔状态机只有离线测试。

基础集成提交依次为 `7f989123f128f`（SMC）、`d48cc30eea934`（binding）、
`30df22db36204`（监测）、`cb3b9f1a69051`（DDC 边界）。已基于 `b1300eb808f43`
快进推送 `origin/vim4-kvm-7.3`，未正式部署。独立输出
`~/build/kernel-display-m2-qualified` 的 Image、M1/M2 DTB、2334 模块完整构建通过，
显示/RX/Wave5 实际 C 模型测试和 DT schema 通过，四提交 checkpatch 均零错误/警告。
构建 ID 为 `db46842077ca98bba08de2d8e47a25549b6b0234`。
这个仅监测的组合没有再次启动上板；HPD/EDID 硬件证据来自上述完整候选的公共读取路径。
默认部署 DT/配置没有切换，M2 profile 此时只监测并保留固件固定模式。
主仓全量离线测试 223 项通过、10 项跳过。没有由本任务更新 sources.toml 或 workspace.toml。
下一次先离线修复输出颜色与初始 ELD，分析 4K GBM 分配边界；合入届时最新 RX/Wave5
后重新构建一次性候选。用户在场时验 HPD 拔插，换支持 4K60/SCDC 的 sink 验表外项目，
准备已授权的物理音频采集，并复测显示开/关的 4K60 输入连续性。

原始证据位于主工作区 `logs/display/m2/window-1/`：`build.json`、`offline-tests.log`、
`candidate-uart.log`、`mode-results.json`、四模式 PNG/state、`native-1080p60-flip.json`、
`gpu-xrgb.log/trace/png`、`audio-live-state.log`、两份 coexistence 日志、
`baseline-uart.log`、`restored-smoke.log`、`restored-hid{,-retry}.log`、
`restored-final-health-dmesg.log`、`cleanup.log` 和 `last-board-query.log`。
