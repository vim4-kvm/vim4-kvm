# 2026-10-23：T7 VDEC MDEC 远程分级窗口

probe、DOS-top 上下电通过；MDEC 前置 GCLK_EN 写后回读触发 SError，看门狗自动
回默认基线，未进入 compliance 或解码。本轮使用 RAM 一次性启动，默认基线不正式更新。
前置依据见 [MDEC 离线修正](2026-10-22-vdec-mdec-offline.md)、
[看门狗实测](2026-10-23-wave5-parity-window.md)和
[一次性启动合同](2026-10-23-display-m1-safety.md)。

## 候选与执行合同

独立 worktree `~/src/linux-7.3-vdec` 的 `vim4-vdec` 无冲突 rebase 到
`0afc7546402608f52ce99596d0f153a519be3e81`，新增提交 `e8ebc2e827347`
让 vdec-test DT 继承 display-m0，保留基线 framebuffer reserved-memory/交接。
独立 `O=~/build/kernel-vim4-vdec-field`，从 `packaging/kernel-edge/uhd1.config`
完整构建 Image、DTB、模块。`package-vdec.py --once` 只接受正式 release，供
`display-once.py` 私有模块挂载；不可覆盖正式 `/lib/modules`。

完整候选 build ID `b3803fdaf6a2c11d6c9e4b89dc06a5d1e0a66c5d`，release
`7.3.0-vim4kvm-uhd1+`，2335模块；四个选定模块均有匹配 vermagic、split BTF 和
独立 build ID。VM 包 `~/build/vim4-vdec-mdec-window-bundle`，完整清单为 manifest.json。

| 产物 | SHA256 |
|---|---|
| Image | `167f7391ea77ea98869aef3dd30e1ae8283a3f6dd8c3f3e6fe0bd41a3dafe114` |
| vim4.dtb | `f4167525a8cc6401cfe05d3f5a49d2a709f42467235965f46bd3070e876bfa1f` |
| modules.tar.gz | `bf87f5b171633eb6cbff592894e8fc7f06fd7cbd33d3485edb3ef2b767adb073` |
| config | `fa46af2fa8213cd91d24dcad70b16a92b6b1b34f76394919951dce75cf5cadb6` |

基线 build ID 为 `eeddb005df059a850853876d52ef603aa1af192b`。
主分支源码与已部署源码不同，不能以 branch HEAD 替代内核 build ID。
私有 display-once 副本只调整预期基线 ID；五个保护文件均重新取证：
Image、DTB、extlinux.conf、kernels.json、runtime-build.json。
串口 RAM sysboot 选择私有 extlinux；不 saveenv、不修改默认启动/登记文件。

`vdec-window.py --once-baseline BOARD_JSON` 禁止旧 boot-install/arm-baseline 动作，
每步要求候选 build ID、私有 init cmdline、只读私有 modules bind、五文件哈希及
PID 1 持有 `/dev/watchdog0`、RuntimeWatchdogUSec=30s。
WATCHDOG_SYSFS 未启用时不把缺少 state 文件当作未启用看门狗。
入场只读查询发现基线 panic=20、panic_on_oops=0；候选一次性 cmdline 中的
`oops=panic panic=20` 保证候选为20/1，并在硬件步骤前再次核对。未持久修改基线 sysctl。
执行仍默认离线，只有 `--execute` 才连接板子；Mac 按 heavy→board 顺序持双锁。

现场顺序为 probe→power→mdec→compliance→H.264 320×256→1080p。
每次重新加载 VDEC 后进入 open 前均重新完成 power/mdec 收据；失败不越级、不重试，
不能确认 DMA 停止时不卸载。原始串口 921600 与各步日志保存于
`logs/vdec-mdec-window/`，执行辅助脚本在忽略的 `build/vdec-mdec-window/`。
故障后最多等 180 秒回默认基线，仍未恢复则请求人工 RESET 并停止。

1080p 路径限六帧、8-bit420、单实例，与软件 I420 全字节比较并打印逐帧 MD5；
短片计时包含 pipeline 启动，不能作为稳定吞吐。当前继承的 S4 格式表上限
1920×1088，4K 尚需驱动扩展，不能把输出放大当作硬件 4K 验收。

## 实际结果

首窗口在 codec 命令前被脚本挂载检查拦截：Ubuntu `/lib → usr/lib`，mountinfo
记录 `/usr/lib/modules/...`，原检查错误地比较 `/lib/modules/...`。候选 build ID、
私有 Wave5 文件/已加载模块、20/1 panic 与30/60秒看门狗均已核实；尚未执行
手动 probe/power/mdec，没有失败的硬件事务重试。正常重启回基线后完成冒烟和清理，
修正为比较规范化目标路径并增加 usr-merge 回归用例，再开新窗口。
首窗口原始日志保留在 `logs/vdec-mdec-preflight/`。

修正后的窗口按顺序执行，首个硬件失败后立即封锁后续阶段：

| 阶段 | 实际结果 |
|---|---|
| 候选启动 | build ID 为 b3803fda…；私有 modules 只读 bind、五文件哈希、20/1 panic 和看门狗检查通过 |
| probe | `OPEN_BLOCKED_EPERM`；allow=N，`VDEC[4]=1 NIC3[39]=0`，runtime suspended；无 DOS MMIO |
| power | `POWER_TEST passed=1 DOS_SW_RESET0=0x0`；工作频率799999987Hz，域4/39为0；下电后域4=1、runtime suspended；原编码器重载成功 |
| mdec | 前置初始化 GCLK_EN 写后回读 SError；没有 PIC_DC 成功值，未加载 H.264 微码、未启动解码 DMA |
| compliance、小 H.264、C01 1080p/4K | 全部未执行，没有正确帧、逐帧MD5、解码吞吐或CPU结论 |

`pstore-after/var/lib/systemd/pstore/dmesg-ramoops-0:547–587`（相对上述日志目录）：

```text
23.369024 pre-DOS power: VDEC[4]=0 NIC3[39]=0 rate=799999987
23.369055 pre-MDEC: CONFIG_DEVICE_SECURE(13,0) a0=0x0
23.369065 pre-MDEC: reset=0x0 mem_pd=0x0
23.369071 pre-MDEC: DOS_GCLK_EN0=0x3ff
23.369077 pre-MDEC: writing GCLK_EN offset=0x260c
23.369108 SError Interrupt on CPU0, code 0x00000000bf000002
pc: _regmap_read+0xd4/0x270; x20=x4=x3=0x260c; x24=0x3ff
regmap_read -> t7_prepare_mdec+0x1ac/0x200
 -> aml_vdec_t7_mdec_test+0x58/0x110 -> mdec_test_store
```

DOS基址0xfe320000，因此异常现场的寄存器是 **GCLK_EN=0xfe32260c**，不是
本次尚未执行的 PIC_DC=0xfe322638。日志只到GCLK写前，没有读回成功行；
SError异步，不能区分该写与紧随的读究竟哪笔引发。策略SMC成功、top memPD=0
及800MHz均不足以证明MDEC内部可访问；本轮不能宣称前次SError已修复。
完整dump SHA256 `931852b5d830fd06376e2f865b7a385c4417e38c7de77030675ed7e3d9700c6c`。

串口 `stages-uart.log` 保存panic→BL启动→`reboot_mode : watchdog_reboot`→默认cmdline。
MDEC步骤Mac时间21:05:10Z开始，21:06:11Z已读回基线build ID；未发出故障后的软件重启，
未请求或使用人工RESET。脚本外层60秒停止等待失败命令，随后确认恢复，未重试。
故障连接曾留下一个本机孤立SSH进程，已只终止该进程；runner补上3秒alive、两次失联
退出及BatchMode，避免后续窗口长留旧连接。
两个pstore目录均打包：/sys/fs/pstore已被systemd归档而为空，console与dmesg dump在
/var/lib/systemd/pstore。候选源码e8ebc2e…已加入 FAILED_SOURCES，禁止再次执行硬件窗口。

## 最终恢复、清理与通过项合入

双锁窗口UTC20:53:06–20:59:52（6.78分钟，脚本前置修正）、
21:04:13–21:11:31（7.30分钟，硬件分级测试），均已释放。
VM完整构建仅持heavy锁，未持board；窗口之间让出两锁给显示任务。

`restored-after-smoke.json` 在最终清理前再次验证：

```text
build ID: eeddb005df059a850853876d52ef603aa1af192b
one-kvm / vim4-manager / vim4-wave5-monitor: active / active / active
UDC: configured; taint: 0; private module mount: []; VDEC modules: []
Wave5 installed SHA256: e88df353c730e5d82bbef8335788a28d5f71cfc7a4e1b8b5854ef00046d4b667
Wave5 loaded build ID: 8e2dedd2579d126adb8ba710eec2082ec1753b05
```

五个保护文件、cmdline、Wave5文件与已加载build ID逐项和入场相同；panic设置回20/0。
UDC始终configured，未运行usb-pd-init。两轮均运行300秒 H.265 浏览器冒烟与运动输入：
最终3840×2160、18308帧、60.0016fps，dropped/lost/freezes/PLI为0，
回调间隔最大37.4ms。真实HID验证键盘按下/松开、绝对/相对鼠标、点击、滚轮全部通过。
这些数值仅验证恢复后的KVM采集/编码链路；最终dmesg无新增oops/SError，taint=0。
清理本轮板上私有候选目录、上传包、fixtures、阶段收据和故障marker，保留pstore归档。

Wave5只读诊断在三次固件probe中得到一致原始值：

```text
product=0x521c fw[118]=0x0003458e version[120]=0x0000521c
DEF0[124]=0x000d0908 DEF1[128]=0x08018000 FEATURE[12c]=0x0000020c
DATE[130]=0x0133f0de REVISION[134]=0x00027a7b TYPE[138]=0 ID[13c]=0
caps: ENCODE
```

只将这14行只读GET_VPU_INFO诊断独立收录到正式内核分支：
`vim4-kvm-7.3` 从0afc7546快进到 **1d80e6ccc364161425714c9f7e07f48769b52f41**，
已推送fork；与候选中的f46d06a…具有相同patch-id，W=1独立MO编译通过，
严格checkpatch为0/0/0。使用独立稀疏worktree `~/src/linux-7.3-vdec-validated`，
未修改/切换VM主工作树。首次普通worktree检出遇VM空间不足，自动回收失败检出；
只清理本轮O目录可重建的链接中间文件后改稀疏检出，保留完整产物、vmlinux、BTF及stamp。

`vim4-vdec` 保留并已推送e8ebc2e…；VDEC平台、时钟、电源和解码代码仍在实验分支。
本轮未启用Wave5 DEC caps、未运行Wave5解码，未改变正式部署或sources/workspace锁。
主仓工具提交为ca1cda8，随后补失败候选拒绝与SSH断连回收、本文及索引。

## 复盘命令与后续

实际构建/窗口入口如下，辅助脚本为本轮忽略目录内的执行留档：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build sh \
  /mnt/mac/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/build/vdec-mdec-window/build-vm.sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-mdec-window/field.py
# 修正挂载检查且首窗口完整恢复后，新窗口从probe重新开始：
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-mdec-window/retry-preflight.py
```

执行器逐阶段调用 `vdec-window.py ACTION --execute --locked --once-baseline BOARD_JSON
--manifest MANIFEST --payload REMOTE --fixtures REMOTE/fixtures`；本次失败源码现已拒绝执行。
下一步先离线复核厂商EN0与domain SMC的先后差异、功能时钟及secure内部隔离/APB权限，
不能把返回0的DMC策略当作APB已经可访问的证明。修复后须使用新候选与相同分级门禁；
compliance、正确帧、DMA停机实测和4K仍未完成。

## 离线检查

VDEC 生命周期故障注入 9 项通过；新增 DT 提交严格 checkpatch 为 0/0/0。
完整VDEC series 的提交级checkpatch未全通过：5个历史提交缺Signed-off-by，另有提交
说明与新增文件MAINTAINERS告警。正式分支仅收录上面已修好提交说明和签名的诊断项。
现场脚本测试17项通过；主仓最终完整离线测试231项，225通过、6跳过。
