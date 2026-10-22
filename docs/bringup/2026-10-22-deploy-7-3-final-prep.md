# 2026-10-22：v7.3 正式版运行时、PD-USB 与部署离线准备

本轮仅离线准备：未拿板锁/重型构建锁，未改板子、未构建最终内核，未推送、未在主仓提交。
第二轮实际执行及自动回退见 [部署尝试记录](2026-10-22-edge-7-3-final-deploy.md)；
这份第一轮记录保留当时状态，脚本后续修正以第二轮记录为准。
音频会话仍持板锁，最终内核/One-KVM 提交尚待用户给出。本记录不是上板通过证明。
成功后保留正式版；失败恢复旧基线的策略只由下一轮实际双锁窗口执行。

## 版本与文件

manager 从 `pd-firmware-handoff` 的 `6c3220c69fefbec91d39f1c1186ad5faa8ef24d7`
新建独立 `deploy-7.3-final`，工作树 `build/deploy-7.3-final/manager`，提交
`7a69cedb6d5263dfb2a348708b07928986975d43`。没有修改原 main 工作树或合并 main。
包含固件 PD 卡、正式版标记和初始化日志与固件记录保持分离的回归测试。

Mac ARM64 交叉构建，Go 元数据为 `go1.27.1`、`GOOS=linux`、`GOARCH=arm64`、
`CGO_ENABLED=0`、`vcs.modified=false`，内嵌 revision 与上述提交相同：

| 产物（`build/deploy-7.3-final/`） | SHA256 |
|---|---|
| vim4-manager | `ad7b8aa3e068cb4f5e4ef8e8c2fb6df623c791a1c4ed82949e616cd6fd01f67c` |
| vim4-nasdisk | `9191b8775c2e79f6bf386b500f3724806ac79cf613c1baf2de59a584558a2aa7` |

这些是 release 二进制，尚未打 deb 或安装。原工作树、主仓已有修改与其他会话产物保留。
`workspace.toml` 的 manager/One-KVM 锁及 `sources.toml` 的 revision/tree/tested_build
本轮不更新：最终内核/应用及实测产物尚未确定，且功能分支提交未推送，不作为共享发布锁。

## release 判断审计

以下 rc7 精确门禁均同时接受 `7.3.0-vim4kvm-uhd1+`，没有放宽为任意 7.x：

| 源文件 | 用途 |
|---|---|
| board/vim4-board-runtime | 板级 HDMI、gadget、PD、音频路由 |
| board/vim4-kvm-run | 四应用硬件后端 |
| packaging/kernel-edge/one-kvm-edge-prepare | 安装为 vim4-mainline-prepare 的驱动准备器 |
| packaging/kernel-edge/one-kvm-edge-usb-prepare | 安装为 vim4-mainline-gadget-prepare 的 gadget 准备器 |
| packaging/kernel-edge/register-runtime.py | 完整 Image/模块校验后的双内核登记 |
| packaging/kernel-edge/one-kvm-edge | 独立实验入口 |
| packaging/kernel-edge/one-kvm-edge.service、one-kvm-edge-usb.service、one-kvm-edge-gateway.service | systemd 两个精确版本 OR 条件；启动参数限制保留 |
| tools/board.py | check 的主线采集健康路径，仍匹配调用方给定的 release |
| tools/wave5-lifecycle-check.py | 独占生命周期检查 |

`tools/kernel-install.sh` 原本没有 rc7 判断，但它覆盖厂商 `/boot/Image`/Default 布局；
现在在解包前拒绝 7.x，指向 edge 窗口与登记器，避免误用厂商安装流程。
新部署脚本的 rc7/build ID 判断有意仅用于旧基线备份/恢复前提。

以下原本按 `7.` 大版本选择，已支持正式版，保留原实现：manager helper 的
EDID/风扇/介质/内核元数据路径，manager App.tsx 的无合同时文案；One-KVM
video_backend.rs 的 Wave5 校验及 vim4-onekvm USB 助手；NanoKVM 的 vim4-video、
vim4-edid；JetKVM 的 vim4-jetkvm。manager KernelPanel 按清单 release 显示及比较
正在运行项，没有旧 release 白名单；新增正式版 tag，rc7 不显示 tag。
通用诊断的版本判断（vim4-driver-bench、edge-jpeg-check/profile、kernel-switch-check）
也按后端/大版本识别。save-wifi-coredump 与 check-wifi-p2p 的既有 7.x 判断未改，未执行。

保留专属早期实验门禁：`tools/crg-udc-check.py` 的 `-crg`，
`hdmirx-resource-check.py`/`hdmirx-ddc-host-check.py` 的 `-hdmirx`。
它们操作早期试验的硬件路径，不纳入正式版验收。uhd1.config 的 rc7 文本仅是生成注释，
不决定 release；源码锁/历史记录的 rc7 为证据数据，不批量替换。

## PD-USB 开机修复

板级新增 `board/vim4pd.py`，随手工安装与平台包进入
`/usr/lib/vim4-kvm/python/`；7.x 的 board-runtime pd 调用它。
只读 `/proc/device-tree/chosen/khadas,usb-pd-boot`，16 个大端 u32，格式见
[固件交接](2026-10-22-pd-firmware-handoff.md)。条件：v1/64 字节、flags bit0
PS_RDY 完成，无 bit4 超时/bit7 回退/bit5 I/O 错误，RDO 所选 PDO 在数量内，
cell4 的 bit25 USB Communications Capable 缺失。满足后仅运行一次现有
`/usr/sbin/usb-pd-init`，没有另写寄存器、改变固件策略或加入 TCPM。

缺属性/不完整/回退/已有 USB comm 位均打印明确原因并跳过；只读快照不当作当前合同。
判断前用 O_EXCL 创建 `/run/vim4-kvm-pd-boot.done`，即使协商失败也不在同次启动重试。
服务额外用 ConditionPathExists 守住该标记，保持 oneshot、RemainAfterExit、30 秒超时、
Restart=no；所有安装路径均不启动/重启 PD。现有 5.15 初始化路径保持不变。
manager 优先展示本次 invocation 完成的 Linux 合同，同时保留固件快照，避免把旧 RDO
冒充修复后的 Linux 合同。未做真实冷插拔，也不为测试拔线。

本轮唯一板端查询为只读 SSH（运行时、服务、ELF SHA、设备树）：

```text
uname -r: 7.3.0-vim4kvm-uhd1+
vim4-manager / one-kvm / vim4-kvm-pd: active / active / active
manager SHA256: 4494f89ce85ef8da13c6dd07b7aca0e9d397aba054b594357b920ab1107ffea7
handoff: version=1, flags=0xd0, RDO=0, PDO count=0, Rp=3
```

这是音频会话的测试窗口，不能当作本任务部署；0xd0 为超时/Type-C 回退，候选逻辑应跳过。
本轮没有恢复动作，也没有声称旧基线已恢复。下一轮预检必须重新确认 rc7 release、
build ID `52d5e46fb006230785110a1fa5ba0dd1383b732f` 和 manager active。

## 下一轮操作

所有路径从主仓根目录使用。内核只在 VM 独立 worktree/分支中构建，独立 O=；
不要改变 `/home/deepdream/src/linux-7.3` 主树。最终 HEAD 由用户指定；先更新并复核
候选 sources.toml revision/tree/upstream，再在 Mac heavy 锁内运行 build.sh 的 uhd1.config
流程，同次生成 Image/dtbs/全部模块。不要直接执行其他会话的 build-app-final.py，
它还含停启服务/部署动作；应用应仅在独立工作树中构建。

打包工具仅消费已经完成的构建；以下命令本轮未运行：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build python3 \
  "$PWD/packaging/kernel-edge/package-final.py" VM_SOURCE VM_OUTPUT VM_PAYLOAD \
  --commit KERNEL_FULL_SHA --mac c8:63:14:74:70:0d
```

打包核对 source/build.json 与产物哈希，modules_install 至临时目录、depmod，保留
配置/内核及 11 个自动加载模块 build ID、所有模块文件哈希；使用 audio-test DTB，
只保留既有以太网 MAC。将 VM_PAYLOAD 复制到 Mac 后 stage：

```sh
python3 packaging/kernel-edge/final-window.py stage \
  --kernel-payload MAC_PAYLOAD --kernel-commit KERNEL_FULL_SHA \
  --one-kvm-source ONEKVM_WORKTREE --one-kvm-binary ONEKVM_ELF \
  --one-kvm-commit ONEKVM_FULL_SHA \
  --manager-source build/deploy-7.3-final/manager \
  --manager-binary build/deploy-7.3-final/vim4-manager \
  --manager-commit 7a69cedb6d5263dfb2a348708b07928986975d43 \
  --regression build/deploy-7.3-final/regression/regression.json \
  --bundle build/deploy-7.3-final/bundle
python3 packaging/kernel-edge/final-window.py window \
  --bundle build/deploy-7.3-final/bundle \
  --backup /var/backups/vim4-deploy-7_3-final-20261022 \
  --logs logs/kernel-edge/deploy-7.3-final --dry-run
```

stage 校验源提交/干净状态、manager ELF 的内嵌提交和 clean 标志、两应用 ARM64 ELF、
Image release、DTB magic、完整模块归档/清单/登记 proof 相互一致，再生成安装映射。
One-KVM 二进制须来自所指定工作树本次构建，Rust ELF 没有通用的 Git 身份证明，
下一轮必须同时保留应用构建日志与哈希；不能仅用旧 ELF 配新提交参数。
未 stage 时 dry-run 明确显示 NOT_STAGED，不能作为产物校验通过。

将 window 的 `--dry-run` 替换为 `--execute` 才进入板上窗口；脚本自行持
`vim4-board.lock`、`vim4-heavy.lock`，全程备份/安装/重启/回归/保留或恢复。
运行时用终端重定向或 tee 留完整 transcript，不记录密码。备份包含启动文件、完整旧模块、
被替换应用/助手/PD unit/运行时、两份清单及原状态；Mac logs/baseline 中再留全部 tar 和状态，
逐 SHA256 与板端核对后才安装。Stock/5.15 和 /lib 符号链接保留，旧模块不覆盖。
新内核预检要求目标 release 模块目录不存在，不覆盖残留目录；远端 staging 也必须是新目录。

独立回退（重新持双锁）用同一个 bundle 和 backup：

```sh
python3 packaging/kernel-edge/final-window.py rollback \
  --bundle build/deploy-7.3-final/bundle \
  --backup /var/backups/vim4-deploy-7_3-final-20261022 \
  --logs logs/kernel-edge/deploy-7.3-final-rollback --execute
```

自动回归复用旧 board-window 的合格夹具，已复制至本会话 regression/ 并登记 SHA：
19 模式每种两帧实际图案/stride/颜色；H.264 九模式与 H.265 八模式正反向；4K60 双编码；
音频 48→44.1→48kHz 的实际标签页播放波形；Mac HID、专用 EDGEUSB21 只读/可写盘；
GPU 自动调频/恢复；manager 实际正式版面板、PD 数据与手机布局。
HEVC 排除非 8 对齐尺寸（1366×768 已知退出等待风险）；没有 Wi-Fi/P2P 操作。
本轮只 prepare，未执行任何 run。夹具依赖 build/ 下历史本地工具和专用测试盘；
迁移机器须重建这些依赖，fixtures.json 校验可发现快照损坏。

board health 另外检查配置/完整模块/已加载 build ID、HID configured、hwrng、IR 默认键表、
风扇/HDMI/taint/五服务及 PD journal；err/warn 与本次备份逐条比较，新日志即失败，
不会自动扩充忽略清单。失败立即尝试恢复、重启并核验原文件/链接/模块/build ID/服务；
SSH 不通或恢复未能验证会明确输出 RECOVERY_NOT_VERIFIED，需串口/OOWOW，不能宣称自动兜底。
成功完成后登记 runtime-build 的组件提交和 SHA 并保留正式版，随后才按实际产物更新主仓发布锁。
主仓和子仓合并/推送仍由用户执行。

## 离线验证与限制

- manager：锁文件安装、前端生产构建、Go 全部测试、vet、Linux ARM64 两个程序构建通过；
  Python 助手 149 项通过、12 项因 Mac 缺 Linux FAT 工具跳过。
- 本地真实 Chrome 跑 updates.mjs 与 power.mjs 通过，覆盖正式版/rc7、确认后切换、
  固件额度/来源 PDO、Linux 优先、回退、功耗未知与 390px 布局；不是连接板子的 UI 验收。
- PD 单测覆盖 vendor 无 comm、已有 comm、超时/回退、I/O 错误、坏属性、缺属性、
  协商失败及同次启动只尝试一次；部署单测用临时伪产物覆盖损坏/不匹配拒绝、
  dry-run 无进程/网络、安装/健康/回归失败恢复顺序、全部通过才保留。
- 主仓完整离线 unittest 159 项通过、5 项跳过，日志在 `build/deploy-7.3-final/main-tests.log`；
  源码/快照 Python、JS、shell 语法检查通过。硬件回归、最终内核/One-KVM 构建、
  板端备份/恢复、Linux 上 FAT/FUSE 验证均未在本轮执行。

本机 Go 最初因继承 GOROOT 与工具链不匹配失败，后用 `env -u GOROOT` 完整重跑通过；
隔离 manager 测试所需 board 相邻目录通过 build/ 内符号链接补齐，未修改全局配置。
