# 2026-10-23：VDEC APB 候选第九步仍失败，看门狗恢复

`c7e7e28f…` 的 probe、显式上电/下电、十三步中的第1–8步通过；
第9步首次读 `GCLK_EN (0xfe32260c)` 仍触发 `SError 0xbf000002`。
补开两个 CPU/APB 门控不足以解决故障。首错即停，没有进入 compliance 或解码。
看门狗自动复位回默认基线，不需要人工 RESET。恢复冒烟结果见下文。

候选来源、厂商活体对照见[前轮记录](2026-10-23-vdec-vendor-live.md)，
十三步的原始条件见[离线审计](2026-10-23-vdec-gclk-offline.md)。
本轮用户明确批准无人值守窗口；没有额外启动其他硬件候选。

## 入场与命令

排队获得 heavy→board 双锁，全部准备、重启、探针、恢复与冒烟均在同一窗口内：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-apb-window/field.py
```

入场 build `eeddb005df059a850853876d52ef603aa1af192b`，release `7.3.0-vim4kvm-uhd1+`。
one-kvm、vim4-manager、vim4-wave5-monitor 均 active，UDC configured，taint=0。
PID1 持有 `/dev/watchdog0`，systemd Runtime/RebootWatchdog=30s/60s，
journal 确认使用硬件看门狗。7.3 未配置 WATCHDOG_SYSFS，故无 state 文件；
不是把文件不存在误作看门狗停用。无挂载 USB 媒体。

从当前五文件、cmdline、已加载与磁盘 Wave5 身份生成新的 baseline.json，
没有依赖旧窗口的静态恢复快照。`display-once.py prepare/stage` 核验完整候选，
串口 921600 在 U-Boot RAM 执行 sysboot，未 saveenv、未覆盖默认启动文件或基线模块。
候选私有完整模块只读绑定于该次启动；panic=20、panic_on_oops=1。

候选 source `a915603f5efb795afc72b5d92aa2c72e0e939a14`，
build `c7e7e28f315cbadd4846ea975e27255e5a985472`。
使用现成 `build/vdec-vendor-live-candidate/bundle`，未重建或换入别的候选。
启动器核验 manifest 中 Image、DTB、模块包的完整 SHA256。

## 分级实际结果

| 步骤 | 实际结果 |
|---|---|
| probe，禁止上电 | 通过；`allow_t7_power=N`，open `/dev/video1` 得 `OPEN_BLOCKED_EPERM`，无硬件初始化 |
| power | 通过；显式 opt-in，SMC 报 VDEC[4]/NIC3[39]=0/0，单读 RESET=0；结束 VDEC[4]=1、runtime suspended |
| 1，APB/DOS clocks、NIC3 | 通过，VDEC off |
| 2，EN0 read | 0 |
| 3，EN0 write | 完成，写 0x3ff，保留共享 HCODEC 位 |
| 4，EN0 verify | 0x3ff |
| 5，800MHz、VDEC on、安全策略、CLKCTRL | 通过；见原始值 |
| 6，EN0 verify | 0x3ff |
| 7，RESET read | 0 |
| 8，MEM_PD read | 0 |
| 9，GCLK_EN first read | **SError，终止**；没有执行 GCLK 写入 |
| 10–13 | 未执行；没有尝试在故障设备上继续回收/卸载 |
| compliance、640×368 H.264、1080p H.264 | 未执行，前置门禁失败 |

每个 sysfs 单步独立子进程、8秒超时；SSH keepalive 有界，主控不重试故障步骤。
正常的 power 阶段及 mdec 阶段内重复的预检 power_cycle 都通过。

pstore 中失败前的完整关键信息：

```text
[24.811256] post-EN0 power: VDEC[4]=0 NIC3[39]=0
[24.811287] CONFIG_DEVICE_SECURE(13,0) a0=0x0
[24.811299] CLKCTRL: SYS=0x7f89ff2 APB=0xff99ffd0 VDEC0=0x2000000 VDEC1=0x8100 path=1
[24.894843] DOS step 6: read offset=0xfc04 value=0x3ff complete
[24.978444] DOS step 7: read offset=0xfc00 value=0x0 complete
[25.062253] DOS step 8: read offset=0xfcc0 value=0x0 complete
[25.146148] DOS step 9: read offset=0x260c begin
[25.146183] SError Interrupt on CPU1, code 0x00000000bf000002
pc : regmap_mmio_read+0x60/0x80
t7_register_access+0x98/0x240 [aml_vdec_drv]
aml_vdec_t7_register_step+0xe4/0x1b0 [aml_vdec_drv]
x4 : 000000000000260c
```

物理 CLKCTRL 证明 SYS_DOS、两个 APB gate 及选中的 p1 gate 已开启，
选源/分频符合800MHz检查；CCF rate=799999987。
这能排除“仅补两个 APB 门控即可修复”的假设，不能证明内部 MDEC 已可访问。
值得下一轮单独核查的是：厂商活体使用 p0（140=0x100，148=0x80000000），
本轮用 p1（140=0x02000000，148=0x8100）。二者选源相同仍不足以断言路径等价；
本轮不切换父源、不重试，也不猜写隔离或安全位。

## 已准备、但没有执行的解码比较

上电前在基线上准备软件参考，600帧逐帧 MD5 已存档。640×368 使用与厂商窗口
完全相同的20秒、30fps、600帧码流，SHA256：
`449bf8a077c6b4a9d2b356c644f373042ee0c7a0842e34e15e3f15acddcce9f8`。
软件 I420 为 `0bfb235006f2204c302740c64f6bb74cf263553d51b256dec5017e1bbf7d86b0`。
1080p 为单实例、6帧、baseline/ref1/b0；码流 SHA256
`e991417b795432af6f7a09ce103eee43d2727bcc66a31b4b823b7fdf1475eb98`。

`vdec-window.py` 现在拒绝替换成另一份同尺寸码流，640阶段超时30秒；
1080p仍15秒，逐帧比较完整 I420 并打印每帧MD5。
Wave 小样本使用独立 wave.h264/wave.i420（320×256六帧），本轮未运行。
失败 source 已加入黑名单，避免下一窗口误用相同候选。
新增离线回归验证错样本在停服务、加载模块或创建阶段凭据之前被拒绝。
软件参考不是硬件解码通过证据，没有新解码速度、CPU 或正确帧结论。

## 恢复与清理

串口报告 `reboot_mode : watchdog_reboot`，自动启动原默认项。
首个 SSH 失败后约45秒确认回到基线，未达到180秒上限，未触发人工复位请求。
两处 pstore 已归档；systemd 已把新 dump 从 `/sys/fs/pstore` 归档到
`/var/lib/systemd/pstore`，保留原系统归档，不清空历史证据。

双锁窗口 UTC 22:35:59–22:43:26，已释放。恢复后运动 H.265 连续300秒，
3840×2160，18,307帧、60.0018fps，dropped/lost/freezes/PLI均0；
呈现回调最大38ms，无超过50ms。真实HID keyboardDown/Up各1，
绝对鼠标、相对鼠标、点击、滚轮全部通过。音频 energy=0，本轮不是非静音音频验收。

```text
build ID: eeddb005df059a850853876d52ef603aa1af192b
one-kvm / vim4-manager / vim4-wave5-monitor: active / active / active
UDC: configured; taint: 0; panic/panic_on_oops: 20/0
Wave5 file SHA256: e88df353c730e5d82bbef8335788a28d5f71cfc7a4e1b8b5854ef00046d4b667
Wave5 loaded build ID: 8e2dedd2579d126adb8ba710eec2082ec1753b05
module_mounts: []; experimental_modules: []
BASELINE_RESTORED_SMOKE_PASSED_CLEANED
```

脚本在冒烟前后逐项比较入场 build、五文件SHA256、cmdline、Wave5安装文件及
已加载build ID、服务、UDC、taint、panic参数，全部一致；恢复启动没有新SError/oops。
UDC一直configured，无需运行PD init。
删除本轮候选私有目录、板上码流/软件raw参考、临时JSON与输出，保留pstore系统归档。
新dmesg-ramoops-0 SHA256：
`1a48335c891da602e3d7d8b28f853cd91957aad2bde798796643693c2e671779`。

## 时钟声明的独立合入范围

为避免将失败的实验驱动带入正式分支，另建独立 worktree
`~/src/linux-7.3-vdec-clocks`，从 fork 的正式头 `1d80e6ccc3641` 起步。
只提取七个 VDEC clock ID 和33行 provider 声明，不包含未测 HEVC 路径、
解码驱动、DT 节点、APB 消费者、SMC 或上电顺序。

基线行为不变的审查依据：两个文件只有新增，无旧 clock ID/位域/flag 改动；
新增 VDEC 仅占140/148低半字，既有 HCODEC 高半字原样；
gate 为 CLK_IGNORE_UNUSED，没有自动 enable/critical/init 回调，
正式 DT 没有这些新增 ID 的消费者，注册不能申请频率或上电。
本轮通过800MHz设置及其物理门控/选源/分频检查，尚未证明该时钟到达内部MDEC；
内部 DOS 故障不视为解码通过。
这项合入只描述可用时钟，不宣称已修复 SError，不部署新基线。

提交 `4e3418b038587`（ID）、`323350fc77dff`（provider），
逐提交 strict checkpatch 均0 errors/warnings/checks，独立O=的
`drivers/clk/meson/t7-peripherals.o` 编译通过，目标SHA256为
`159b498783331626246647606be992f50e22aeef2c9d4ddb0bdf9b7a94bedd85`。
没有把对象编译记成完整内核构建或新的板上冒烟。
两提交由独立分支快进合入 fork 的 `vim4-kvm-7.3`，未修改/切换原主源码工作树。
完整实验分支 `vim4-vdec` 仍为原 `a915603f…`，失败的APB消费者与解码路径未合入。
未构建/安装正式新Image，当前部署仍为上文基线。

主仓离线全套233项通过，6项跳过；VDEC相关19项通过。新记录先纳入git索引后
再跑全套，因此包含文档体积与链接检查。前轮记录精简到11,387字节。

## 证据位置与下次门禁

原始资料在忽略目录 `logs/vdec-apb-window/`：window.log、candidate-boot-uart.log、
stages-uart.log、probe/power日志、pstore前后归档、software-fixtures.log、
baseline/restored JSON、视频/HID冒烟，以及本轮脚本快照。
记录只保留判定所需原始值；前轮长记录进一步精简到12,000字节以下，
完整产物 manifest 另存于 `logs/vdec-vendor-live-candidate/manifest.json`。
本轮临时打包目录和时钟对象O=目录在归档后删除，仍只保留当前c7e7候选bundle；
没有删除其他任务的构建产物。

下一次先离线确认 p0/p1 的厂商切换条件及 secure 上电是否要求固定路径，
再准备新的候选，仍需用户安排窗口。新候选按 probe→power→十三步顺序，
第9步以前的通过不能授权越过第9步；compliance、两档 H.264 继续被阻塞。
