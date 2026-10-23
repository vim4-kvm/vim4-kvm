# 2026-10-23：Wave5 超时隔离与十轮验收（第二轮）

正式窗口进展与构建产物修正见[窗口复验](2026-10-23-wave5-isolation-final.md)。

本轮按新的边界实现超时后隔离，不实现运行时复位或固件重载。
离线测试、完整构建与十次注入/重启/4K60 恢复通过，临时窗口已恢复基线与实际 HID。
完整模块重打包与第二次正式窗口九类回归通过，已保留并推送；详情见窗口复验记录。
厂商复位证据与未解问题保留在
[第一轮审查](2026-10-23-wave5-recovery.md)。测试起点为
[M0 基线](2026-10-23-display-m0-r4.md)，build ID `f483ea42fee88be39ea67c43478638be67334d6e`。

## 独立分支与实现

内核 worktree `/home/deepdream/src/linux-7.3-wave5-recovery`、分支
`vim4-wave5-recovery`，基于 `47878a0c611d1e1deb3699c4f225963a37a218c0`，继承第一轮
`473b3ba430c01a865faad165f4ef16226d564371` 的底层错误传播修复。本轮提交：

- `78e913a85fbb777e709b83cbd06f4ccff6e4b453`：T7 超时、job_abort、隔离、内存保留与测试。
- `4f1e15605fac8a14cd4d1e3bae2f6d867b30c050`：polling IRQ 线程有界停止、sysfs ABI 文档。
- `0489619d3d692a01b6fc9d7e18649e1b5f88e7bb`：声明修复与取消后迟到报告保护。
- `ad5c552037069763f6836e85e8382fc0e6f858f7`：软件保存提交的 opcode，注入不依赖命令寄存器读回保持值。
- `aa2f875bec2fc7c9a4952fccb9dcaa6fbfc4aa64`：先填完整原因、时间与保留引用，再向 sysfs 发布故障状态。

manager worktree `build/vim4-manager-wave5-isolation`、分支 `wave5-isolation-api`，基于
已部署 `4ea7484`，提交 `9b141c5833c06a1cc876f9979ff21523c8af0558`。仅新增状态 API，
未改前端。原内核、One-KVM 与 manager 的主工作树没有切换或编辑。

### 有界等待与调度

命令 BUSY 轮询保留 10 秒上限，改为可睡眠轮询；T7 IRQ completion 最长 5 秒。
每个 M2M 帧有 5 秒 watchdog，STREAMOFF report drain 共用 5 秒截止时间。
job_abort 先允许正常完成最多 1 秒；失败即隔离，在 irq_lock 下结束当前 M2M 调度任务。
该锁可能等待正在执行的有界命令，因此 **1 秒不是整个取消调用的硬上限**。
取消与 device_run、IRQ、watchdog 的调度完成串行化，检查当前实例后才 job_finish，
阻止迟到完成重复结束任务。隔离后 job_ready=false，open/ioctl 返回 EIO，poll 返回 POLLERR。

隔离限于 probe 成功后的 T7 legacy encoder 运行时；启动阶段失败沿用原有电源回退，
未纳入本轮注入验收。未宣称 Wave515、TI decoder 也有相同生命周期保证。
每个现存实例的两条 vb2 队列均 queue_error，唤醒 completion；不等待固件配合。

### DMA 生命周期与卸载

不能把 M2M job_finish 等同于 DMA 已停止。单纯 queue_error 后，vb2 STREAMOFF 仍可能
unmap 导入的 DMA-buf，所以本候选使用薄包装 allocator：正常时调用原 dma-contig memops；
隔离后保留原 allocation ref、映射和独立的 DMA-buf ref，跳过 finish/unmap/detach/put。
用户解除 mmap 或关闭导出 fd 也不会丢失驱动原有的引用。辅助 coherent DMA 与 SRAM
释放函数同样检查隔离状态；隔离后的 close 只摘除用户 fh，保留实例、M2M 队列及所有背书。
正常 T7 close 先确认 DESTROY 成功再释放队列；STILL_RUNNING 即隔离，不反复等待。

首次隔离固定模块和 device 引用，保留时钟、固件、工作区及 DMA 映射到下次启动；
禁用 IRQ 后不再向设备写命令。用户态 unbind/bind 属性关闭，rmmod 不能卸载固定模块。
隔离 shutdown 不调用固件、不复位、不关电源，不等待 completion；isolated remove 分支
直接返回。正常 remove 原有的有界复位保留；polling IRQ 的 semaphore 等待改为 100ms，
避免 kthread_stop 永久卡在没有后续 IRQ 的等待者上。强制卸载、内核中删除静态 platform
device、kexec 不属于本轮支持或验收路径，不能把禁止用户解绑解释成通用热拔插支持。

### 状态、注入与运行时

设备目录的只读 `isolated`、`isolation_reason`、`isolation_time_ns`（CLOCK_BOOTTIME 纳秒）
与 `KOBJ_CHANGE` 的 `WAVE5_ISOLATED=1` 事件暴露首次故障；不可写回清除。
`/sys/module/wave5/parameters/timeout_command` 是 root 读写的一次性 opcode 注入，默认 0。
只在 probe 完成后、真实命令确认成功时模拟软件超时，不制造固件实际挂死；例如帧命令
opcode 为 256。不会写入复位寄存器或重载固件。注入成功后该参数恢复 0。

板级 `vim4-wave5-monitor.service` 每 2 秒检查状态，默认只记 journal，并原子写
`/run/vim4-wave5/alert.json`。自动重启配置默认关闭；开启时，必须全部 KVM 服务 inactive、
虚拟介质为空且连续满足配置间隔（默认 60 秒、至少 30 秒），才通过 systemctl 请求一次
正常重启。同次启动先写标记，服务重启或请求失败不重复请求。运行中但空闲的 One-KVM
暂不计为无需求：现有 clients 不覆盖 UU、RTSP、录屏等共享消费者，不据此猜测空闲。

manager 的 `GET /api/status` 新增 `encoder`：`known`、`isolated`、`needsReboot`、`reason`、
字符串 `timeBoottimeNs`。旧内核无接口时 known=false，不误报健康。前端告警由后续 UI 实现。
final-window 的可选 `stage --wave5-monitor` 把监控脚本、单元和 manager Wants drop-in
一起备份、安装、回退；不覆盖管理员的自动重启配置。普通窗口默认行为不变。

## 离线验证

- 实际驱动 C 的 ASan/UBSan 回归通过：原有 buffer、geometry、profile、refresh、cleanup、
  close/IRQ、47 项 FIO/reset；新增隔离用例覆盖取消交错、所有实例错误、迟到完成、
  watchdog 截止时间，以及 MMAP/export/import 引用保留。日志
  `logs/wave5-isolation/offline-final.log`。
- checkpatch strict：新逻辑及后续修正均为 0 errors/warnings/checks；新增文件提示
  FILE_PATH_CHANGES 单独过滤，目录已由既有 Wave5 MAINTAINERS 通配覆盖，不过滤其他类型。
- manager `env -u GOROOT go test ./...` 通过，ARM64 静态编译通过；构建元数据为上述
  `9b141c5` 且 vcs.modified=false。首次复用了主工作树旧 dist，正式门禁发现其缺失现有内核标记；
  已按 pnpm 锁文件重建资产并重新编译，未修改前端源码，后续窗口重新完整验收。
- 主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：共享工作区初版 195 项、5 项跳过；
  隔离主仓 worktree 最终 197 项、9 项跳过（未展开其子仓），均通过。
  监控器回归验证默认从不请求重启、持续空闲计时、忙碌/未知/有介质拒绝、每 boot 一次。
- 独立 O= `/home/deepdream/build/kernel-wave5-isolation`，完整配置 SHA256
  `bca0e45df6eb43177bd82f251b4133c0468dd05195b7bae8ed8f639ba21f971c`。
  首次完整编译发现 close 新调用缺声明，已在 `0489619` 修复；该版完整构建及打包通过。
  `ad5c552` 与最终 `aa2f875` 的完整构建和打包均通过；只使用最后一包作为板测候选。
  最终 Image SHA256 `9fca5c6fc2a7c8943b5802198977df97857d89717f8da0041329bc070061c41a`，
  DTB `a635f8947ee77f67a43714aaa87276aff70edc0952bf40188d46853e055ce652`，
  modules.tar.gz `d9a29202547820a87c563710a4adb43ca52db07f7e9351acdbf56f18653f054c`。
  不使用旧 module-only 产物安装到 M0，保留 BTF，Image 与全部模块必须同次匹配。

## 双锁临时窗口：十轮通过，已恢复基线

执行入口（本地忽略目录保留完整测试脚本和日志）：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf -t 0 /tmp/vim4-board.lock \
  python3 -u build/wave5-isolation/temp-window.py
```

窗口备份 `/var/backups/vim4-wave5-isolation-r2b`，下载并逐项核验六个备份文件；候选 build ID
`7b8372b894c98ffae12e636a325c86f2b6c85e00`，Wave5 模块 build ID
`52f71181453475bd188db808c4da04fde8b419b4`。日志入口
`logs/wave5-isolation/temporary.log`、`temporary-window/state.json`，逐轮保留 inject、recovered、
uevent 和 previous-journal 日志。取锁顺序切换曾中断首次备份；未安装或注入，该备份保留，
新窗口重新通过 PREFLIGHT_OK 并独立完整备份后才安装。

每轮用 RGB8 UHD60 EDID、Mac 动态画面和 Chrome WebRTC，稳定 SSRC 的 15 秒统计差值
采样 3840×2160 解码；保持第二个 idle encoder 实例后，执行：

```sh
sudo sh -c 'echo 256 > /sys/module/wave5/parameters/timeout_command'
cat /sys/bus/platform/drivers/vdec/*/isolated
sudo systemctl reboot
```

| 轮次 | codec | 注入前 fps | 正常重启秒数 | 重启后 fps |
|---|---|---:|---:|---:|
| 1 | H.265 | 60.051 | 27.777 | 59.985 |
| 2 | H.264 | 60.051 | 26.644 | 59.988 |
| 3 | H.265 | 59.988 | 26.681 | 59.983 |
| 4 | H.264 | 59.989 | 26.743 | 59.982 |
| 5 | H.265 | 59.987 | 26.596 | 59.984 |
| 6 | H.264 | 59.984 | 26.794 | 59.984 |
| 7 | H.265 | 59.985 | 26.662 | 59.989 |
| 8 | H.264 | 59.991 | 26.756 | 60.056 |
| 9 | H.265 | 59.986 | 26.652 | 59.981 |
| 10 | H.264 | 59.985 | 26.630 | 59.993 |

十轮均得到 `IDLE_INSTANCE_EIO_CLOSE_AND_NEW_OPEN_REJECTED`、
`INJECTION_RESPONSIVE_AND_TAINT_ZERO`，One-KVM MainPID 不变、info/stream/status 有响应，
三个服务均 active、taint=0；uevent 含 `WAVE5_ISOLATED=1`，manager 返回 known/isolated/
needsReboot=true、原因与时间。首轮示例时间 `48691504679`，原因 command acknowledgment timeout；
kernel 记录 command 0x100，One-KVM 记录 `Input/output error (os error 5)`。
监控 journal 有 `Wave5 isolated; reboot required:`。所有重启均为普通 systemctl reboot，
未用 SysRq、强制重启、RESET 或故障尺寸；每次重启后 isolated=0 且核验候选及匹配模块。
这是命令超时隔离与普通关机路径证据；真实固件挂死、真实总线堵塞未测试。

第十轮后 health 输出 `NEW_WARNINGS []`；自动 restore/reboot/verify-restore 输出
`BASELINE_RESTORED f483ea42fee88be39ea67c43478638be67334d6e`，核验原模块目录、文件、
cmdline、one-kvm 与 manager active。随后真实主机 HID 输出 keyboardDown=1、keyboardUp=1、
absoluteMouse=true、relativeMouse 坐标改变、click=true、wheel=true，最终标记
`TEMPORARY_WINDOW_BASELINE_AND_REAL_HID_RESTORED` 后释放双锁。

### 完整模块打包门禁

对比备份与候选清单发现 4 个未加载 netfilter 模块丢失：xt_DSCP、xt_HL、xt_RATEEST、xt_TCPMSS。
原因是 package-final.py 把 modules_install 临时目录放在 Mac 共享卷，大小写文件名被覆盖。
改为 VM 本地临时目录，并逐项对照 modules.order；新增两项回归验证缺件拒绝和完整压缩清单。
十轮测试的 Image、Wave5 和其余已加载模块匹配，隔离证据成立；这份 2330 模块的包不正式部署。
VM 本地重打包通过，清单恢复为 2334 模块，Image/Wave5 字节及全部已加载模块 build ID 不变。
完整包 SHA256 `770213bb108478a263be61f2b1b59031813ad639fd53232ed51f3b5393479cb1`；
日志 `logs/wave5-isolation/package-complete.log`。已重新 stage formal-complete.bundle，
第一次正式窗口 manager 前端资产失败已回退；修正后第二次九类全部通过并保留。

下一阶段仍缺独立寄存器手册、挂死态总线停止确认、两个 reset mask 差异与固件 SLEEP
不可响应时的安全顺序，以及复位后实例上下文保留证据。软件故障注入不能补足真实挂死态
DMA 排空或硬件复位安全性的证明。
真实挂死后的热重启与编码恢复也未验证；本轮没有制造真实挂死。
