# 2026-10-23：T7 GCLK 十三步探针远程短窗口

`4aaef538…` 一次性候选的 probe、DOS-top 上下电及探针1–8通过；第9步首次读取
GCLK_EN触发SError，尚未写GCLK_EN，立即停止后续步骤。看门狗自动回默认基线。
没有进入compliance、H.264或逐帧比较，不能宣称解码可用。
前置实现和厂商出处见[GCLK离线审计](2026-10-23-vdec-gclk-offline.md)，
恢复机制见[一次性启动](2026-10-23-display-m1-safety.md)和
[看门狗实测](2026-10-23-wave5-parity-window.md)。

## 候选、锁与证据入口

本轮获得无人值守批量窗口授权，使用已有候选，没有重新构建或修改内核。
独立分支`vim4-vdec`提交`c6fc96a347d0929a9385c09b408c333a50834091`；
候选build ID为`4aaef5382254d02368d0f49efc680a2059c04289`，release
`7.3.0-vim4kvm-uhd1+`，完整2335模块。准备器校验Image/DTB/逐模块哈希，
只暂存根分区私有目录；UART 921600在U-Boot RAM选择一次，未修改默认启动项。
候选cmdline为`oops=panic panic=20 init=<私有路径>/init`，模块目录只读bind。
每个动作检查候选build ID、五保护文件、模块挂载与PID 1看门狗所有权。

原始日志保留`logs/vdec-gclk-window/`：`window.log`、`manifest.json`、
`candidate-boot-uart.log`、`stages-uart.log`、逐阶段日志、基线/候选/恢复JSON、
前后pstore归档。执行辅助脚本归档到该目录`scripts/`，属于忽略的现场证据。

实际入口：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-gclk-window/field.py
```

执行脚本依次调用`vdec-window.py probe/power/mdec`，使用
`--locked --execute --once-baseline /var/tmp/vdec-gclk-window-20261023/baseline.json`
和当前候选manifest。十三步每条sysfs命令8秒超时，SSH有alive上限，阶段外层60秒；
首错不重试、不强卸载，等待看门狗回默认基线，最多180秒。

## 各步实际结果

入场为`eeddb005df059a850853876d52ef603aa1af192b`，三个服务active、UDC configured、
taint=0；PID 1持有`/dev/watchdog0`，systemd报告硬件Meson GXBB Watchdog、
`RuntimeWatchdogUSec=30s`、`RebootWatchdogUSec=1min`。
WATCHDOG_SYSFS未启用，state文件不存在；以PID 1持有设备和journal交叉核验。
基线panic为20/0，候选实测20/1，不持久修改基线sysctl。

| 阶段 | 实际结果 |
|---|---|
| 一次性启动 | build ID 4aaef538…、私有模块挂载、五文件、看门狗检查通过 |
| probe | `/dev/video1` open得到`OPEN_BLOCKED_EPERM`；allow=N，无DOS MMIO；runtime suspended |
| power | `POWER_TEST passed=1 DOS_SW_RESET0=0x0`；频率799999987Hz；下电后VDEC[4]=1、runtime suspended |
| 1：时钟和NIC3 | 通过；VDEC[4]=1、NIC3[39]=0（0=on，1=off） |
| 2：断VDEC域读EN0 | 通过；offset fc04，值0 |
| 3：写EN0低10位 | 通过；写3ff，保留HCODEC高位 |
| 4：读EN0核验 | 通过；值3ff |
| 5：800MHz/VDEC域/策略 | 通过；4/39均为0，CONFIG_DEVICE_SECURE(13,0)返回a0=0 |
| 6：上电后读EN0 | 通过；仍为3ff |
| 7：读DOS_SW_RESET0 | 通过；fc00=0 |
| 8：读DOS_MEM_PD_VDEC | 通过；fcc0=0 |
| 9：首次读GCLK_EN | **失败：260c读取触发SError 0xbf000002**，无complete收据 |
| 10：写GCLK_EN | 未执行 |
| 11：读回GCLK_EN | 未执行 |
| 12：只读MDEC_PIC_DC_CTRL | 未执行 |
| 13：正常下电与确认 | 未执行；故障后由硬件复位回基线，不访问abort/卸载接口 |
| compliance、小H.264、1080p逐帧比较 | 全部未执行；无解码正确帧、MD5、PSNR、性能或CPU结论 |

## SError与收敛结论

`pstore-after/var/lib/systemd/pstore/dmesg-ramoops-0:546–610`：

```text
25.056524 pre-EN0: VDEC[4]=1 NIC3[39]=0 rate=799999987
25.329248 DOS step 4: read offset=0xfc04 value=0x3ff complete
25.427158 post-EN0 power: VDEC[4]=0 NIC3[39]=0
25.427189 CONFIG_DEVICE_SECURE(13,0) a0=0x0
25.516593 DOS step 6: read offset=0xfc04 value=0x3ff complete
25.609845 DOS step 7: read offset=0xfc00 value=0x0 complete
25.702886 DOS step 8: read offset=0xfcc0 value=0x0 complete
25.792039 DOS step 9: read offset=0x260c begin
25.792076 SError Interrupt on CPU0, code 0x00000000bf000002
pc: regmap_mmio_read+0x60/0x80; lr: regmap_mmio_read+0x4c/0x80
x20=x4=x3=0x260c
regmap_read -> t7_register_access+0x98/0x240
 -> aml_vdec_t7_register_step+0xe4/0x1b0 -> register_step_store
```

完整dump SHA256：`6519f8f6ff96191dff81c00e445e751de0bd2c9e3e91d7a81a4b1d39c40bbbb8`。
DOS基址fe320000，因此本次访问为**fe32260c**。当前模块生命周期尚未执行GCLK写，
故本次失败不依赖它之前的GCLK写；EN0前置及NIC3持有仍不足以使该读成功。
SError仍是异步异常，不把PC当作完整总线归因证据；不能据此证明整个MDEC均不可访问，
也不能证明GCLK是write-only或secure-only。厂商没有找到该寄存器的合法读用例；
需要访问属性、匹配BL31内部隔离/时钟/内存电源实现，或受控的厂商运行时对照。
没有猜写PWRCTRL/AO位或改用无合同的TEE代理。

Mac阶段21:40:55Z开始，21:41:51Z确认基线build ID，约56秒。
`stages-uart.log:588`为`reboot_mode : watchdog_reboot`，后续默认cmdline没有私有init。
未发故障后的软件重启、未请求人工RESET；180秒上限未触发。
两处pstore均已打包；sysfs副本已被systemd归档，完整dump在`/var/lib/systemd/pstore`。
runner将c6fc96a…加入已知失败源码拒绝表，禁止再次执行该候选硬件窗口，恢复入口保留。

## 恢复与清理

双锁窗口为UTC21:40:00–21:47:15，约7分15秒，已释放。恢复后两次快照逐项核对
build ID、五保护文件、cmdline、Wave5安装文件/已加载build ID、服务、UDC、taint和
panic设置，均与入场一致：

```text
build ID: eeddb005df059a850853876d52ef603aa1af192b
one-kvm / vim4-manager / vim4-wave5-monitor: active / active / active
UDC: configured; taint: 0; panic/panic_on_oops: 20/0
private module mounts: []; experimental modules: []
Wave5 installed SHA256: e88df353c730e5d82bbef8335788a28d5f71cfc7a4e1b8b5854ef00046d4b667
Wave5 loaded build ID: 8e2dedd2579d126adb8ba710eec2082ec1753b05
```

`baseline-video.log`：H.265、3840×2160运动输入，测量300秒，18307帧，
60.0017869fps，dropped/lost/freezes/PLI均为0；回调最大38.5ms，无超过50ms回调。
`baseline-hid.log`：keyboardDown/Up均为1，绝对鼠标、相对鼠标、点击和滚轮均通过。
这些仅为恢复后KVM采集/编码/HID通过证据，不代表VDEC解码或音频验收。
最终dmesg没有新的SError/oops，taint=0；UDC始终configured，无需usb-pd-init。

板上删除本轮私有候选目录、上传tar/脚本/fixtures、阶段收据与故障marker；
保留systemd pstore归档。默认Image/DTB、原模块和运行时登记未被覆盖。
没有合入或正式部署VDEC，本轮内核分支无新提交，仍为已推送的c6fc96a…。

按用户要求清理本任务构建产物；释放board锁后排队取得heavy锁，未干扰显示任务构建。
`cleanup.log`逐目录记录实际`du -sk`及删除结果。VM只保留
`~/build/vim4-vdec-gclk-offline-bundle`（395MiB），先核对build ID和哈希，再保留
当前`vmlinux`、System.map、Module.symvers、config、stamp及四个原始模块到
`debug/`（约319MiB，附sha256.json），随后删除：

- `kernel-vim4-vdec-field`、`kernel-vim4-vdec-validated-wave5`、`vdec-field-tools`。
- `vim4-vdec-field-bundle`、`vim4-vdec-mdec-bundle`、`vim4-vdec-mdec-window-bundle`。
- `vim4-vdec-power-fix-bundle`、`vim4-vdec-r3-bundle`、`vim4-vdec-r3-bundle-final`、
  `vim4-vdec-r3-fixtures`。

上述目录合计6.41GiB，扣除另存当前调试符号约净减6.10GiB。
Mac只保留`build/vdec-gclk-offline`（77MiB，含当前bundle与静态init），删除
`vdec-field`、`vdec-round2`、`vdec-round3`、`vdec-power-fix`、`vdec-mdec-offline`、
`vdec-mdec-window`、`vdec-gclk-window`，合计约551MiB。
旧辅助脚本文本、当前fixture和日志先归档到`logs/vdec-gclk-window/`；源码worktree、
其他任务构建和历史logs均未删除。以上为目录统计，不以并行构建期间整盘df差值估算。
两处当前候选manifest的全部产物哈希重新核验通过；当前O目录已删除，后续构建需重新生成。

## 后续边界与离线检查

先离线补齐GCLK_EN的读写属性及当前BL31内部电源/隔离实现证据，再形成新候选。
现有源码不能因看门狗已可恢复而重复尝试；不跳过第9步去写GCLK或读取PIC_DC。
下一现场窗口仍须重新批准，按新证据设计最小访问，再恢复compliance/正确帧门禁。

本轮只改runner失败候选拒绝表及其真实执行入口回归用例：有效vdec5和once包均在
获取锁/SSH前被拒绝，旧包恢复入口保留。主仓全套离线测试232项，226通过、6跳过；
`git diff --check`通过。本轮没有内核代码改动，因此没有重新构建或运行checkpatch。
