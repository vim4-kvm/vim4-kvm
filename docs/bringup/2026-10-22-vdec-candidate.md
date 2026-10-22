# 2026-10-22：T7 H.264 解码第三轮离线候选

完成 secure loader、停机失败隔离、DOS 互斥、显式电源域管理及完整候选构建。
**本轮未连接板子 SSH/串口；没有正确帧、compliance、性能或基线恢复实测。**
候选只待现场验证，不代表已可用。沿用
[第二轮平台准备](2026-10-22-vdec-t7-offline.md) 的硬件依据；该文的 probe 拒绝描述是当时状态。

## 分支、固件依据

VM worktree `~/src/linux-7.3-vdec`，分支 `vim4-vdec`；不改主工作树，不推送。
本轮提交：`6fc3c73a13772`（binding）、`c0d473c9da0f2`（platform PM ownership）、
`de12117b219fb`（解码候选、仲裁、测试）。基于第二轮 `7bd0f8328e8a4`。

下列厂商路径相对 `~/src/linux/common_drivers/`，提交
`4cfb128d36f8511b2db1bd13c08d5704347ded49`；厂商内核为 `80a07ad5406d`。

| 事项 | 证据和实现 |
|---|---|
| SMC ABI | `drivers/tee/tee.c:59–62,626–644`：`tee_load_video_fw()` 直接执行 `arm_smccc_smc(0xb200000f,index,core,swap,0,0,0,0)`，没有 OP-TEE session 或用户态 TA 调用 |
| H.264 参数 | `drivers/media_modules/frame_provider/decoder/utils/amvdec.c:631–638,670–675`：`mh264` 选择 index15、legacy core0、swap0；枚举见 `common/firmware/firmware_type.h:45,92`（补前缀 `drivers/media_modules/`） |
| swap 所有权 | `decoder/h264_multi/vmh264.c:9366–9411`：TEE 模式不复制普通世界 swap；`9135–9136,11424–11437` 保留 AV_SCRATCH_G（decoder 前缀同上） |
| 本轮加载 | T7 `load_firmware()` 直接调用上述 SMC；非零返回失败，保留安全 loader 的 scratch G，跳过 S4 raw/extra loader；不覆盖安全 swap 地址 |
| 7.3 支撑 | `CONFIG_HAVE_ARM_SMCCC=y`、`CONFIG_OPTEE=y`；不依赖厂商 `tee.ko` 导出函数。已运行的 JPEG 使用同入口 index21/core3，仅证明入口存在，不能证明 index15 或 H.264 消息协议可用 |

仅查已有 `logs/kernel-edge/final/uart.log:260–261,289,794`：BL31
`v1.3.2(release):2dd964006`（2026-02-01）、U-Boot
`2019.01-00006-g0d5a3d7848`、OP-TEE/BL32 报告 `3.8 (00000000ec8c40b0)`。
这些是历史离线证据，本轮没有重查当前固件。

现有 NEWP `video_ucode.bin` 的 H.264 项只有 CODE 元数据，没有可直接供旧 loader
复制的 raw/swap 字节；详见第二轮固件分析。`common/firmware/firmware_drv.c:931–938`
在 TEE 模式直接跳过普通固件 reload。厂商有非 TEE 分支，但不能由该包证明可用的
非安全转换方案。本轮不做猜测性 fallback、不依赖重新分发固件；仍依赖板上安全固件的 index15 服务。

## 停机、缓冲与资源协调

| 路径 | 已实现行为与依据 |
|---|---|
| 解码超时 | worker 等待最多500ms；IRQ 只报告结果，先停机再完成 request/缓冲。去掉超时后的重复 PC/MMIO 诊断 |
| 停机成功条件 | mask mailbox、同步 IRQ → MPSR/CPSR=0 → IMEM/LMEM bit15 分别最多100ms → WRRSP low12 最多12.5ms → CPU reset11/12，前后各三次 readback → DBUS disable=ffff，最多100ms等待相等，200次 settling；依据 `utils/amvdec.c:1079–1138`、`utils/vdec.c:773–817,1072–1093` |
| 停机失败 | 任一错误立即返回，不重试 reset；`faulted=1`，拒绝新 open/prepare/stream，mask IRQ，固定模块、设备和 DOS lease，queue error，不 panic、不执行电源关闭或 codec DMA 释放 |
| vb2 关闭 | T7 只接受 MMAP；每 plane 私有 dma-buf 引用固定原始 dma-contig allocation/映射。故障后即使 close/REQBUFS 销毁 vb2 对象也不 put；workspace/LMEM/colocated/canvas 同样保留到系统复位。S4 imported DMABUF 生命周期不在此保证内 |
| 正常回收 | 只有停机全部检查通过才释放本帧 canvas；修正无符号 `-1` sentinel、分配失败、丢失参考、FIFO padding 越界和错误返回。T7 暂限逐行8-bit420、单实例、每帧单 slice；不接受中途复用 canvas 的多 slice |
| DOS 互斥 | `t7-dos.ko` 提供模块生命周期 lease：JPEG/Wave 共享，VDEC 独占；冲突 `-EBUSY`，任一引擎不确定停机后永久 poison 为 `-EIO`。VDEC 实验前须卸载 Wave/JPEG；不依赖用户态 `/tmp/vpu_mutex.map`，避免其覆盖不到的 probe/reset/SMC 并发 |
| 电源/复位 | SYS_DOS gate 共享；VDEC/HCODEC/Wave 是 NIC3 下不同域，不复位共享 NIC3。VDEC 只用自己的 DOS reset0，不写 HCODEC/HEVC/Wave reset |
| runtime PM | platform driver 明确自行管理域，core 不执行自动 POWER_ON attach；`attach_by_name` 得到未上电的虚拟域，device link 不隐式 runtime resume。首次 open：SYS_DOS/VDEC clocks500MHz → domain resume → DOS/IRQ；关闭：IRQ mask → clock off → domain put；probe 只映射资源，不读 DOS。依据 `utils/vdec_power_ctrl.c:151–176,195–203,268–299` |

厂商没有独立、已确认的 outstanding-DMA 计数；这里采用其正常停机的全部检查点，
不把超时当成功。离线无法证明 DBUS 回读在硅片上的 drain 语义；一次挂起的 MMIO/SMC
也不能被软件 timeout 打断。故障状态不支持热解绑、DT overlay 移除或强制卸载，需复位。

## 构建、检查与产物

独立 `O=~/build/kernel-vim4-vdec-r3`，起始配置为保留基线配置，仅改变 localversion
并增加 DOS 仲裁模块。候选 `7.3.0-vim4kvm-vdec3+`，完整 Image/模块同次配置构建，
不混用基线 vermagic/BTF。普通 DT 的 vdec 保持 disabled；单独 `vdec-test.dtb`
继承基线 audio-test 并设 okay，但仍须 `modprobe aml-vdec-drv enable_t7=1`。

```sh
# Mac，已执行；最终构建/打包日志：logs/kernel-edge/vdec-round3/candidate-final.log
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build make \
  -C /home/deepdream/src/linux-7.3-vdec \
  O=/home/deepdream/build/kernel-vim4-vdec-r3 ARCH=arm64 -j8 \
  Image amlogic/amlogic-t7-a311d2-khadas-vim4-vdec-test.dtb \
  amlogic/amlogic-t7-a311d2-khadas-vim4-audio-test.dtb modules
```

完成后在 O= 目录生成 `vdec-build.json`（源提交及原始 Image/DTB/vmlinux/config/全模块哈希）；
`package-vdec.py` 校验该 stamp 和干净源码，在同一 heavy 窗口打包，命令见日志。
VM 产物 `~/build/vim4-vdec-r3-bundle-final`，Mac 副本 `build/vdec-round3/bundle`，
2336个模块；manifest 含全模块哈希及四个相关模块的 build ID。它不调用正式版 runtime 登记器。

| 项目 | 最终值 |
|---|---|
| kernel build ID | `1193e92f714e6b5f7a0e1b50d6935e4236e19d64` |
| Image SHA256 | `310bc6f1ec1355bff67bb21f323a3f40518fe958672722a417d683073314df37` |
| vim4.dtb SHA256 | `6161d0b47337b203f4063f56b405e27c128de24f1a328d3c3e0e0f4e6b03462d` |
| disabled DTB SHA256 | `7ded145471554590970dfb2f054622bc10b655494d482c7c8411230898fc9707` |
| modules.tar.gz SHA256 | `3c6a69c2f9463c3ce9800a3f6b05c160d7837fd1d18fc8055414611ebb245589` |
| config SHA256 | `e7fb97bea72806cd062b00ab0bf56116bb98711bb96ac65d78c2a5ed342aa8ed` |

`test_t7_lifetime.py` 六项离线测试编译实际 C 函数配合可控故障后端：逐次 MMIO 错误、
四种 busy 状态、停止前禁止 finish、故障关闭持有 plane、lease/poison、canvas 分配失败、
platform core 不自动上电；无硬件、重试或 sleep。三次提交分别 strict checkpatch，
均0 errors/warnings/checks；binding 的 dt-doc-validate 通过。最终全构建无 warning/error。
主仓178项测试通过（5跳过），含窗口脚本7项；生命周期另6项通过。
未运行硬件 dtbs_check、v4l2-compliance、1080p/4K、错误码流或多实例测试。

## 下次现场窗口：由低到高，以下均未执行

工具 [vdec-window.py](../../packaging/kernel-edge/vdec-window.py) 默认仅打印离线计划，
所有实际动作还需 `--execute --at-board --manifest <本地清单>`。
若其他任务尚未恢复上述基线，安装直接拒绝。不要使用正式版部署前备份来替代本轮新备份，
旧备份可能保存的是 rc7。候选 release 不在 KVM 运行时白名单，本轮不扩充该白名单；
解码窗口停 One-KVM，返回基线后才做编码/HDMI/HID验收。

1. 离线核对 SHA、vermagic、BTF；准备 `v4l2-ctl/compliance`、ffmpeg、GStreamer
   `h264parse/videoconvert` 与 `v4l2codecs` 插件。S4 使用动态 factory `v4l2slh264dec`，
   Wave 使用 `v4l2h264dec`；板上是否装有前者本轮未查询，缺插件先停，不触发解码。
2. Mac 以双锁打开一个现场 shell；整个候选启动、单组测试、返回基线都在该窗口内完成。
   在此 shell 调用工具须加 `--locked`，避免重复拿同一锁。暂存 bundle/fixtures 也在锁内，
   不覆盖现有目录。`boot-install` 验基线 build ID/启动文件、备份至
   `/var/backups/vim4-vdec-r3-20261022`，安装独立模块和 Image/DTB，不动应用/部署锁。
3. 手工一次重启，SSH 最多等90秒；失败看串口，不循环重启。候选回来立即执行
   `arm-baseline`：恢复磁盘上基线 Image/DTB，sync并核对 SHA；此后 RESET 即回基线。
   未恢复启动文件时，工具拒绝所有 codec 测试。
   首次启动若失败而尚未 arm，RESET 会再次启动候选：须在串口菜单一次性选已有
   `Stock`，进入5.15后从本轮新备份复制 Image/DTB 回 `/boot/edge/`、核对基线 SHA、
   sync，再启动 FullKvm；不改 U-Boot、不刷写或格式化。现场先确认此救援入口可操作。
4. `probe`：只注册并读取 sysfs 名称，不 open video、不上电；健康即卸载。
   `power`：`v4l2-ctl --info`，8秒；`compliance`：20秒，每项独立加载/关闭/卸载。
   任一步异常停止升级风险，不把 compliance 非零当通过。
5. `h264`：仅已知320×256、8-bit、单参考、无B帧、单slice的6帧码流，10秒；
   与软件 I420 逐字节对比。`build/vdec-round3/fixtures` 含 SHA256、逐帧 MD5；尚无硬件输出。
   之后才计划1080p、复杂参考/错误流与性能；本候选不承诺4K。
6. `wave` 最后做：`wave5 t7_decode_test=1` 临时仅注册 DEC，不保留 ENC，硬覆盖旧固件
   缺失的 AVC/HEVC capability 位。仅单实例、小于等于640×480、8对齐、8-bit420；
   脚本仍只喂同一320×256 H.264。此模式没有证明固件命令兼容，禁止并发编码、HEVC
   非8对齐和自动重试。能力原值见 [第二轮实机证据](2026-10-22-vdec-wave5-capabilities.md)。

```sh
# 只在用户在板边时；本轮未执行
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock zsh
# 在该锁内 shell 暂存后，按顺序逐条调用，不用循环串联硬件测试：
python3 packaging/kernel-edge/vdec-window.py boot-install --locked \
  --execute --at-board --manifest build/vdec-round3/bundle/manifest.json
# 手工 reboot、等待、arm-baseline，再任选一组 probe / power / compliance / h264 / wave。
# 每条仍带上述四个参数；每组完成即正常重启基线、verify-baseline，然后退出 shell 释放锁。
```

每条板端命令有15秒默认 timeout，解码10秒、compliance20秒、解包90秒；SSH总上限180秒。
健康路径卸载候选，恢复本窗口卸载的编码模块及原先 active 的 One-KVM。
超时、`faulted=1`、Wave 命令失败则写 `/tmp/vim4-vdec-reset-required`，保留资源，
不卸载、不恢复编码、不重试。SSH timeout 不代表远端结束，先看串口；无响应或 DMA
无法确认停止时由现场人员按 RESET。Wave 仍沿用上游关闭路径，不具备本轮 T7 stateless
的完整 DMA quarantine 保证，因此最后尝试。

回到基线后 `verify-baseline` 核对 build ID `3ed254bf…`、Image/DTB SHA、服务 active、
UDC configured；还必须按既有验收工具确认实际 HID 按下/抬起、H.264 编码和 HDMI 帧推进。
只通过 sysfs/服务检查不能报告 KVM 完整恢复。本轮未改板，无新增恢复基线的实测证据。
