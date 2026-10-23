# 2026-10-22：VDEC 自动 open SError 的离线修正

本轮**不上板**。修正 probe 与硬件上电之间缺少权限边界的问题，增加 secure
电源状态核验和独立的单次 DOS 读取/下电测试。现有现场只能定位异常附近的
MMIO，尚不能证明电源实际关闭、隔离未解除，或断言总线故障已经修复。
前次实测见 [现场记录](2026-10-22-vdec-field.md)，后续见
[第二次现场](2026-10-22-vdec-field2.md)：单读通过，compliance panic后已恢复。

## 故障定位：已知与未知

证据使用前轮已有文件，未重新连接板子：
`logs/kernel-edge/vdec-field/uart.log`、`dos-enable-offline.txt`，以及
`pstore-after/var/lib/systemd/pstore/dmesg-ramoops-0`（完整栈和寄存器在510–573行，
42641字节，SHA256
`908ad8443c8cec21eaf715442a5fa78a7a4b8b072cbcecee80882de262bdeaff`）。
候选源码 `5bf7d6359df9ff68d8746851cf45de40611988a1`，build ID
`1ca661edb9a6e76a88d78af1fa852b47d647e5b7`。

```text
SError CPU6 code=0xbf000002, PID=1481 Comm=v4l_id, t=82.022008
pstate=600000c5 pc=do_raw_spin_unlock+0x70/0x110
lr=_raw_spin_unlock_irqrestore+0x38/0xc8 sp=ffff800087ba3870
x29=ffff800087ba3870 x28=ffff0001018f2a60 x27=1
x26=0 x25=ffff800082ef2da0 x24=1
x23=ffff0001165d6000 x22=0 x21=3ff
x20=0 x19=ffff0001166d4000 x18=0
x17=0 x16=0 x15=0 x14=4 x13=20 x12=1c
x11=0 x10=0 x9=ffff8000815a9768 x8=ffff0001166d4018
x7=80721 x6=ffff800080d98b28 x5=ffff800080da7bb0
x4=260c x3=ffff800087ba3834 x2=dead4ead x1=6 x0=ffffffffffffffff
regmap_unlock_spinlock -> regmap_write+0x60/0x88
  -> dos_enable+0x4c/0x88 -> vdec_enable+0x18c/0x280
  -> aml_vdec_runtime_resume+0x20/0x38 -> pm_generic_runtime_resume
  -> __rpm_callback -> rpm_callback -> rpm_resume -> __pm_runtime_resume
  -> fops_vcodec_open+0x19c/0x280 -> v4l2_open -> chrdev_open
  -> do_dentry_open -> vfs_open -> path_openat -> do_file_open
  -> do_sys_openat2 -> __arm64_sys_openat -> invoke_syscall
  -> el0_svc_common.constprop.0 -> do_el0_svc -> el0_svc
  -> el0t_64_sync_handler -> el0t_64_sync
```

DOS 基址为 `0xfe320000`，厂商 DT `mesont7.dtsi:2687–2700` 及当前 DT 一致。
前轮模块的反汇编中 `dos_enable+0x48` 调用 `regmap_write`，返回地址为 `+0x4c`。

| 顺序 | 寄存器 word index → byte offset → 物理地址 | 现场意义 |
|---|---|---|
| 第一笔尝试的 DOS 访问 | DOS_GCLK_EN0：`0x3f01 → 0xfc04 → 0xfe32fc04` | read/modify/write，低10位写 `0x3ff` |
| 异常所处调用 | GCLK_EN：`0x0983 → 0x260c → 0xfe32260c` | 写 `0x3ff`；x4仍为偏移260c，与反汇编一致 |
| 后续计划访问 | MDEC_PIC_DC_CTRL：`0x098e → 0x2638 → 0xfe322638` | 清 bit31；没有证据证明已执行到此 |

**可确认的软件根因**：udev 的 `v4l_id` 自动 open 新节点，原 `enable_t7=1`
只准许 probe，没有阻止 open 进入 runtime resume。旧代码在 CCF/PM helper 返回
成功后直接访问 DOS，没有记录 VDEC/NIC3 的硬件电源状态。异常早于固件加载、
codec reset 和 DMA 提交。**电气层根因未定**：SError 为异步异常，不能将 PC
当作精确故障指令；第一笔 GCLK 读改写也可能是来源。没有 FAR/总线事务记录可排除它，
也没有现场状态证明“在未上电/未解除隔离时访问”。

## 厂商顺序与 7.3 核对

厂商依据 common_drivers `4cfb128d36f8511b2db1bd13c08d5704347ded49`，
厂商路径相对该树；7.3路径相对 `linux-7.3-vdec`。

| 项目 | 实现及出处 | 本轮处理 |
|---|---|---|
| T7 上电顺序 | `drivers/media_modules/frame_provider/decoder/utils/vdec_power_ctrl.c:151–176,195–203,268–282`：clock on/hi enable → domain get；T7 的 dos_local_config 返回，不做本地 PD/iso/reset | 保留厂商功能时钟先行；SMC 管理 RAM/隔离/电源转换，Linux 无可照搬的 T7 AO 隔离位 |
| 内部全局门控 | `drivers/media_modules/common/media_clock/clk/clkg12.c:479–486` 在 clock helper 中访问 DOS_GCLK_EN0；`utils/amvdec.c:72–87` 开内部 gate、写 GCLK_EN、清 PIC_DC bit31 | 候选更保守：secure 状态确认之前连 DOS_GCLK_EN0 也不访问 |
| 电源 ID | 厂商 `include/dt-bindings/power/t7-pd.h` 与 7.3 `include/dt-bindings/power/amlogic,t7-pwrc.h` 一致：HCODEC=2、HEVC=3、VDEC=4、WAVE=5、NIC3=39 | DT 原 VDEC=4 正确；不改成 HEVC，不借用 Wave 电源域 |
| 层级与 SMC | 7.3 `drivers/pmdomain/amlogic/meson-secure-pwrc.c:335–338,381`：四个 DOS 子域的父域为 NIC3；`drivers/firmware/meson/meson_sm.c:49–50`：SET=82000093、GET=82000095 | 存在 T7 secure provider；没有额外 DOS 顶层域。genpd 自动管理 NIC3；驱动只读核验4和39 |
| 状态返回 | 厂商 `drivers/power/sec_pwr_ctrl.c` 的 status SMC；7.3 secure provider `:57–66` 将 GET 的0视为on、1视为off | 其他返回值一律错误；拒绝 DOS MMIO |
| helper 成功的局限 | 7.3 secure provider `:68–97` SET 的 ret 指针为 NULL；`meson_sm.c:109–127` 将实际 a0 写入可选 ret，自身成功返回0 | 驱动补 GET 后置核验；没有改共享 provider 的 Wave/JPEG 行为 |
| 时钟 | SYS_DOS=SYS_CLK_EN0_REG0 bit1；功能 VDEC=VDEC_CLK_CTRL/VDEC3_CLK_CTRL 低半字双路 mux/div/gate。见7.3 `drivers/clk/meson/t7-peripherals.c:1035–1061,1221`，厂商 `drivers/clk/meson/t7.c:3860–3974` | 原 DT 两项映射正确，保留500MHz实验频率；不动 HCODEC 高半字、不增加共用 reset |
| genpd 自动 attach | `drivers/pmdomain/core.c:3365–3526`，attach_by_name 创建虚拟设备并不主动上电；platform 的 driver_managed_pm 跳过自动 attach/power-on | 保留显式 attach 和不含 PM_RUNTIME 的 link，避免 core 越过驱动顺序；video 注册前先初始化 runtime PM |
| 地址转换 | 厂商 `common/chips/decoder_cpu_ver_info.c:236–239` T7 reg_compat=NULL；`common/register/register.c:95–138` 没有 T7 重映射 | 排除照搬其他芯片寄存器偏移修补；DT 增加 secure 隔离/reset 所有权注释 |

BL31/BL32内部隔离步骤仍需现场确认。“上电前检查”用厂商只读GET SMC，
**不访问 DOS MMIO、不主动上电**，不猜电源寄存器或其他SoC的reset位。

## 新的驱动边界

- `enable_t7=1` 仍只准许 probe；新增 `allow_t7_power`，默认false、仅root可写。
  未许可或未完成本次模块生命周期的 power_test 时，video open 返回 `-EPERM`，
  不分配解码上下文、不调用 PM、不访问 DOS；runtime resume 再检查一遍。
- 平台设备 `power_state` 为只读状态查询；`power_test` 读取只返回缓存。
  root显式写 `1` 才执行：CCF → genpd → GET确认VDEC/NIC3都为0 → 只读一次
  `DOS_SW_RESET0`（byte `0xfc00`，物理 `0xfe32fc00`）→ 关时钟/domain → GET确认VDEC为1。
  不开IRQ、不写DOS门控/复位、不加载微码、不启动DMA。
- 未找到厂商可确认的 VDEC 只读 silicon ID；HEVC_VERSION 属另一电源域，不能借读。
  所以该采样明确称为 reset-register readback，不冒充 ID 检验；值没有伪造的预期常量。
- 只有上述读与下电均成功，才缓存 passed=1。普通 open 仍每次在首次 DOS 前
  GET核验域状态。下电无法确认则 faulted、pin模块/device、poison共享DOS租约，
  不再发 DOS MMIO，不自动重试/卸载。原 DMA 超时 quarantine 保留。
- JPEG/Wave 的互斥租约及编码默认能力未改变。实验期间须停One-KVM并卸载两者；
  每个正常窗口结束后恢复。没有修改基线配置、已部署锁或 U-Boot。

## 离线构建与验证

内核分支 `vim4-vdec`，独立 worktree `~/src/linux-7.3-vdec`，基于 `1262da082ba5`；
新提交 `34ab72b7fbeca`（完整哈希见 bundle manifest）。新 release
`7.3.0-vim4kvm-vdec4+`，复用本任务独立 `O=~/build/kernel-vim4-vdec-field`，
重新完整构建 Image、两个测试 DTB、所有模块，持 Mac heavy 锁。
`package-vdec.py` 现在只接收 vdec4，核验 clean source、全构建 stamp、模块
vermagic/split BTF及哈希清单；没有生成能替换基线模块目录的同名 release。

完整构建/打包成功，2336模块，build ID `c2c9d49116accf8b68a845c77aa7df20c5b75801`。
VM包 `~/build/vim4-vdec-power-fix-bundle`，Mac副本 `build/vdec-power-fix/bundle`。

| 产物 | SHA256 |
|---|---|
| Image | `12812a67af020ebaaf96d94dac1f0927a0bc368d7f562bfcd1e488f737f93f72` |
| vim4.dtb | `04cc3d480cdb8ee462f5263508114ddec449331f9216db93f286ca02407ed540` |
| modules.tar.gz | `6cb29323de54f32e2139941efb5e5e11cfe08c87d9a12900841e27cb2d9cc91b` |

构建日志无warning/error。驱动故障注入8项通过，严格checkpatch为0/0/0；主仓离线测试
182项、跳过5项。日志在 `logs/kernel-edge/vdec-power-fix-{build,tests}.log`。

## 下次现场清单（本轮未执行）

用户在板边备好串口/RESET，先协调并行任务、核对基线；若有变化须更新脚本基线和备份目标。
默认离线，`--execute --at-board --manifest` 才连接并取得双锁。每窗口完成释放锁；
手动重启、UART采样、恢复验收也持board/heavy双锁。

```sh
# 以下为准备好的下一次现场命令，未执行；bundle和tools先传到payload。
python3 packaging/kernel-edge/vdec-window.py ACTION --execute --at-board \
  --manifest build/vdec-power-fix/bundle/manifest.json \
  --payload /var/tmp/vim4-vdec-power-fix \
  --backup /var/backups/vim4-vdec-power-fix-20261022
```

1. **安装/候选启动/arm-baseline**：全模块配套，新的独立release；启动后先把原
   Image/DTB写回并校验，确保下一次 RESET 回 `f283ab1f…`。未 arm 不允许 codec 操作。
2. **probe，无上电，风险最低**：`ACTION=probe`；开关为N、udev settle≤8s，
   脚本主动open验证 `OPEN_BLOCKED_EPERM`；只读SMC状态、缓存passed=0、runtime suspended。
   成功后健康卸载、恢复原模块/One-KVM。预期文字不是本轮实测输出。
3. **单次总线读取，仍有挂总线风险**：`ACTION=power`，要求本boot/build已通过probe。
   新加载模块仍默认关，udev settle后显式设Y，sysfs测试≤8s。
   应看到 pre-DOS VDEC[4]=0/NIC3[39]=0、DOS_SW_RESET0原值、VDEC下电为1；然后开关关回N。
   状态拒绝访问时停下收日志；不得靠改caps/跳过检查继续。
4. **compliance，风险高于单读**：`ACTION=compliance`；要求power已通过。
   每次重新加载都必须再过同一power_test，然后才开video权限、compliance≤20s，
   close后runtime必须suspended。该步开始会再次触及前轮 GCLK_EN 故障附近。
5. 后续小H.264≤10s、正确帧比较、1080p和性能、Wave521C小尺寸解码仍按
   [原候选](2026-10-22-vdec-candidate.md) 分阶段；本轮只准备前述更细的门禁。
   原脚本 h264/wave 仍仅320×256、6帧、单实例；没有添加1080p自动性能阶段。

脚本在 `/tmp/vim4-vdec-stages.json` 记录 boot ID/build ID和阶段结果；未完成/失败/已完成
的窗口不能重试或越级。超时、异常运行状态或quarantine时写reset-required标记，
不强卸载、不恢复编码器争用硬件；正常结束才卸载实验模块并恢复原服务。
即使有8s用户态超时，单笔MMIO不返回仍可能使整板卡死，不能保证可由kill回收。

失联时单独打印以 `NEED_RESET` 开头的复位请求，15秒探测一次、最长10分钟，等用户RESET；
重新连上后保存 `/sys/fs/pstore` 与 `/var/lib/systemd/pstore`、串口、dmesg和boot身份，
不重新运行候选。基线验收必须包括build ID `f283ab1f8a001a19bab5247afc4f9b0c00c1da99`、
Wave5原模块、manager/One-KVM active、UDC configured、实际HID及编码/采集；
UDC not attached时锁内执行 `sudo /usr/sbin/usb-pd-init` 再验。没有这些实测不能记为恢复通过。

本轮没有安装、加载模块、访问寄存器或重启板子；不重复宣称上一轮恢复证据是本轮验证。
