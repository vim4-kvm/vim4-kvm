# 2026-10-23：Wave5 正式批次，HDMI 模式门禁失败并回退

本记录对应用户批准的无人值守正式窗口，范围为已合入的内核 `9d33f6ad2789`、
One-KVM 非8对齐 HEVC 回退移除及板级 panic 策略。多子系统按九类全量回归，
所有检查通过才 finalize；任何失败恢复入场基线。本次第一类 HDMI 模式回归失败，
已自动回退并完成基线冒烟；未 finalize，未更新 sources.toml/workspace.toml，
未合入 One-KVM 生产分支。

## 入场与候选

入场主仓 `967b0ec`；内核已部署 `b1300eb808f43`，build ID
`eeddb005df059a850853876d52ef603aa1af192b`，M0 DTB。
One-KVM `672b8fd9fdec`、manager `9b141c5833c0`；三个服务 active，
taint=0。只读查询确认 `panic=20`、`panic_on_oops=0`，PID 1 的
RuntimeWatchdog=30s、RebootWatchdog=60s。入场默认回退点为
`/var/backups/vim4-kvm-tmds-final`，依赖旧 staging，建立新备份前不删除。

内核 fetch 后 `origin/vim4-kvm-7.3` 为 `9d33f6ad27898d4cb1b5cb52dc328edceca96f7f`。
独立源码 worktree `linux-7.3-wave5-encoder-parity`、O=`~/build/wave5-release-kernel`；
未切换或修改内核主工作树，正式配置为 `uhd1.config`、display-m0 DTB。
完整重新构建通过，候选 build ID 为 `0b2385440a358dddcd5d96b496c5fab4d187808d`；
配置 SHA256 仍为 `8af98a1fbefdf163c407f9f04bb31372178b8f8d7d6f00f5dff162b930c968bf`。

## 变更与离线检查

`board/60-vim4-panic.conf` 经 board/install.sh 与 Ubuntu board 包安装到
`/usr/lib/sysctl.d/60-vim4-panic.conf`，正式窗口也将它纳入文件备份/回退。
下一次启动设置 `kernel.panic_on_oops=1`，不在安装/构建容器时修改宿主 sysctl。
启动后的门禁同时检查实际 panic=20 与 panic_on_oops=1，管理员仍可用 /etc 覆盖。

One-KVM 两处临时 AVC 回退及相关 SDP 收尾分支移除。Wave5 S_FMT 将请求的
可见宽高写入默认 crop，编码参数内部补齐并写 conformance window；应用保留原尺寸
及所选 H.265。代码依据是 `wave5-vpu-enc.c` 的 s_fmt_out/conf_win 与编码初始化；
固件与 SPS 实板证据见 [E02 窗口](2026-10-23-wave5-parity-window.md)。
此应用须与 E02 内核一同部署；厂商 5.15 路径保持原行为。

主仓加入包内 sysctl 内容、权限、安装路径与无宿主 sysctl 修改测试；运行236项，
10项跳过，其余通过；合并最新 main 后完整复跑结果相同。应用增加可见尺寸保持、
HEVC 选择及非对齐 DMA 平面布局回归。
One-KVM 功能分支 `vim4-wave5-visible-hevc` 提交 `20d8010d000a2cfae082ec72b398f8e4feb9d332`
已推送；30项部署辅助测试通过，Rust release 测试740通过/2忽略，另以
`VIM4_VIDEO_BACKEND=wave5` 单独运行 HEVC 可见尺寸选择测试通过。
release 构建成功，二进制 SHA256 为
`3d5fec3602521a63c52672aadac5f0d8068e4d2cdb67c0cfcade35b2af1bfd93`。
内核 package-final 完整清单2334个模块通过，正式 bundle stage/dry-run 校验通过。

## 窗口入口与门禁

所有重型构建在 Mac heavy 锁内；板上安装、重启、回归与收尾全程同时持有
heavy → board 两锁，排队期间不改变板子状态。内核使用独立 recipe 的精确源码锁构建，
package-final.py 校验完整 modules.order、BTF 配对与 artifact 哈希。

```text
final-regression.py prepare --hevc-visible-sizes --gpu-load <ARM64-gles-load> ...
final-window.py stage --ir-keytable <ARM64-ir-keytable> --require-all-checks ...
lockf /tmp/vim4-heavy.lock lockf /tmp/vim4-board.lock \
  python3 final-window.py window --execute --locked ...
```

回归固定九类：19种 HDMI 模式、H.264、H.265、4K60、音频、HID、虚拟介质、GPU、manager。
HEVC 增加1366×768、1440×900、1680×1050，核对 MIME、可见尺寸和解码内容；
E02 开关只用于有该功能的内核。GPU/IR 测试工具随本次 bundle 保存，不依赖已被清理的
旧板上临时文件。GPU 沿用 `logs/gpu-devfreq/gles-load.c`，不测试系统挂起、不扫描 Wi-Fi。

## 实际结果与回退

候选启动后的精确 build ID、完整模块与已加载模块 build ID、应用哈希、
One-KVM/manager/监控、UDC、RNG、IR、风扇、GPU governor、taint 与新增告警检查通过。
实际 `panic=20`、`panic_on_oops=1` 通过；这是候选启动证据，不是保留部署。

| 九类门禁 | 本轮结果 |
|---|---|
| HDMI 模式 | 失败；640×480、720×400、800×600 两帧图案/颜色/前进检查通过，1024×768 抓帧失败 |
| H.264 模式矩阵 | 未执行 |
| H.265 模式矩阵（含非8对齐） | 未执行 |
| 4K60 | 候选未执行 |
| 音频 | 未执行 |
| HID | 候选未执行 |
| 虚拟介质 | 未执行 |
| GPU 负载 | 未执行（启动健康检查仅核对模块/governor） |
| manager | 候选未执行（启动健康检查已通过） |

1024×768 在初次接收器就绪后，读取 debugfs frame 返回 `Link has been severed`。
同步状态为 `link_ready=0`、`tmds_aligned=0`、PLL 当时仍锁定，宽高读数变为585×0；
dmesg 记录 `link readiness revoked: reason=5v-or-align error=-67`。
这是 HDMI 链路失败；未运行 Wave5 编码矩阵，不能据此判断是 Wave5 回归，
也未做基线同模式复现来区分源端切换、既有 RX 问题或候选新增问题。
门禁保持失败，没有放宽检查或将重试写成通过。

协调器执行 restore → reboot → verify-restore，实际输出：

```text
RESTORED_REBOOT_REQUIRED
BASELINE_RESTORED eeddb005df059a850853876d52ef603aa1af192b
RuntimeError: Regression hdmi-modes failed: 1
```

回退后的独立冒烟（两锁仍持有）通过：

| 项目 | 实际证据 |
|---|---|
| 4K60 H.264，运动图案，15秒采样 | 3840×2160，59.9836 fps，dropped/lost/freezes=0 |
| 4K60 H.265，运动图案，15秒采样 | 3840×2160，59.9757 fps，dropped/lost/freezes=0 |
| HID | 键盘按下/释放、绝对/相对鼠标、点击、滚轮均通过 |
| manager | API、登录与移动布局检查通过 |
| 板状态 | one-kvm、vim4-manager、vim4-wave5-monitor active；UDC configured；taint=0；isolated=0 |

最终 build ID 为入场的 `eeddb005df059a850853876d52ef603aa1af192b`；
内核 `b1300eb808f43`、One-KVM `672b8fd9fdec`、manager `9b141c5833c0`。
实际 `panic=20`、`panic_on_oops=0`（配置随失败批次一起回退），
PID 1 持有 watchdog，RuntimeWatchdog=30s、RebootWatchdog=60s。
未启动5.15，未重新测试停止喂狗，未注入真实固件挂死。

## 保留、清理与后续

Mac `logs/wave5-release/formal/baseline/` 六个备份文件在安装前复制并逐一核对板端哈希；
回退后删除候选备份前再次核对。保留入场正式回退点
`/var/backups/vim4-kvm-tmds-final`，原 staging 恢复到 `/var/tmp/vim4-deploy-7.3-final`。
删除本轮失败点 `/var/backups/vim4-wave5-formal-20261023` 和候选板端 staging，
不清理别的任务文件。收尾后两锁已释放。

删除 VM `~/build/wave5-release-kernel`（约7.6 GiB）、本轮 Docker 容器与独立 target 卷；
Mac build/wave5-release 删除重复 kernel-payload、旧 regression snapshot 与重复应用二进制，
仅保留一份115 MiB 的候选 formal.bundle。复现脚本/fixture 移至忽略目录 logs。
未删除共享 cargo 缓存、其他任务构建目录或内核源码 worktree。

代码仍可复用：板级 sysctl 安装及门禁、显式 E02 回归开关、GPU/IR 自带依赖已入主仓；
对应独立提交为 `Install persistent board oops recovery policy`、
`Qualify Wave5 visible HEVC sizes in final regression`、
`Bundle final regression GPU and IR dependencies`。
One-KVM `vim4-wave5-visible-hevc` 的 `20d8010d000a2cfae082ec72b398f8e4feb9d332`
保留在 fork 功能分支，生产分支未推进。下一轮需先对1024×768 链路失锁做基线/候选对照，
然后重新走完整九类门禁；非8对齐应用链路尚无本轮板端验收结论。

原始证据位于 `logs/wave5-release/`：window.log（安装/回退）、
formal/hdmi-modes.log、formal/video/raw-modes.jsonl、formal/failure-board.log、
formal/uart.log、formal/candidate-health.json、baseline-{4k60,hid,manager}.log、
restored-after-cleanup.json。离线检查见 offline-main.log、app-build.log 与 kernel-build.log。
