# ADLA：正式7.3集成审查草案

2026-10-30用户已批准并完成[uhd3正式合入与回归](bringup/2026-10-30-uhd3-formal-regression.md)。
下面为原uhd2草案与历史验收；当前精确源码/构建锁见sources.toml，已含nodebug正式配置。

本轮离线，未访问板子，未修改GPU代码或正式内核pin，未push。
后续[uhd2上板](bringup/2026-10-30-npu-uhd2-acceptance.md)已完成：输出/并行通过，
DenseNet性能门槛失败，继续保持pin待定；下文保留离线交付与原窗口计划。
统计重评和新的≤30分钟窗口见[多启动门禁](npu-performance-gate.md)，不以历史单组判跨启动资格。
保页例外仍为**用户已于 2026-10-30 接受**；真实软复位失败注入不进入下一窗口。
已验收[npu4](bringup/2026-10-30-npu4-acceptance.md)的旧分支和载荷保留，
新序列供审查与讨论，不宣称厂商字符设备ABI已经符合上游接收条件。

## 提交序列与行为一致性

VM `~/src/linux-7.3-npu-review`：`vim4-npu-adla-review`，基于213f271505411。

| 顺序 | 提交 | 边界 |
|---|---|---|
| 1 | 3b3b70be472f0 | 核心和字符设备ABI导入，尚不接入Kconfig |
| 2 | 7fecc129445ad | T7C ADLA binding |
| 3 | 3d7e1fd06c49f | T7资源及VIM4 enable/supply |
| 4 | af3bf7eed020d | 7.3适配并接入可选模块；CCF/PM/regulator/DMA |
| 5 | e8e61f526eee8 | 固件IRQ、缓存fixup、恢复错误、取消/close生命周期和trace修复 |
| 6 | f71b5c6289cb3 | ABI、边界、IOVA、供电回滚与生命周期宿主测试 |

每段保留原作者/版权/许可证/MODULE_AUTHOR；提交含说明及Signed-off-by。
前3段不启用未适配的核心，第四段才启用模块；不要求尚未修复的中间版本上板。
树级证明：最终tree为`f3f8877c70e547bc53f2ca0469c25fcffb7f15a6`，
与npu4 `34f345566a1b9^{tree}`全树相等，包含trace和测试，不只比较驱动目录。
没有引入正式基线以外的Panfrost/Mesa或其他分支补丁。
六个format-patch在VM `~/build/npu-review/patches`，本机副本`build/npu-integration/patches`。
strict checkpatch第2–6段均0 errors/0 warnings/0 checks；原样核心导入段单列
5207 errors、11233 warnings、678 checks，多为缩进/行首空格、函数花括号及旧类型风格。
这是已验收核心的存量，不通过机械格式化隐藏，也不宣称整套补丁符合上游格式要求。

## 集成候选与待批准pin

独立VM `~/src/linux-7.3-npu-integration`，分支`integration/npu-uhd2`，
在正式213f2715上快进上述序列，HEAD为f71b5c6289cb3254690e57292327e73514f0715f。
`~/src/linux-7.3-hdmi-integration`、原NPU及GPU工作树均不改。
正式命名采用下一独立release **7.3.0-vim4kvm-uhd2+**，不覆盖uhd1或npu1–4模块目录。

草案为`packaging/kernel-edge/npu-integration.toml`和`uhd2.config`；
sources.toml只加草案指引，kernel/tested_build/integrated_runtime实值仍为原正式版本。
草案不会被当前build/deploy入口自动替代使用，标记pending-user-approval、board_verified=false。
有效配置对比npu4只改LOCALVERSION，ADLA=m；启动CMA仍为
`512M@0x10000000-0xf0000000`，保留npu4的首次HDMI模块选项和冷插拔黑名单。
输出`~/build/npu-integration`、载荷`~/build/uhd2-candidate`；最终bundle仍须下一窗口新证明。
build.sh仍严格校验现有sources.toml，拒绝未pin的草案源码，这是预期保护；
本轮在VM明确指定草案工作树与配置直接make，不放宽正式构建器的版本锁：

```sh
# VM，新输出目录；主仓在VM的挂载路径。
repo=/mnt/mac/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm
src=$HOME/src/linux-7.3-npu-integration
out=$HOME/build/uhd2-review-new
test "$(git -C "$src" rev-parse HEAD)" = f71b5c6289cb3254690e57292327e73514f0715f
mkdir "$out"
cp "$repo/packaging/kernel-edge/uhd2.config" "$out/.config"
make -C "$src" O="$out" ARCH=arm64 olddefconfig
make -C "$src" O="$out" ARCH=arm64 -j8 Image dtbs modules
```

源码树相同不意味着Image/模块哈希相同：release、编译路径、时间和BTF/build ID均可能变化，
模块必须与本次Image成套使用；不能复制npu4的ko到uhd2模块目录。

待批准内容是：采用六段审查序列并入正式分支、正式pin及匹配运行时清单更新/push。
草案branch是当前集成分支，target_branch才是批准后快进的vim4-kvm-7.3；正式pin应指后者。
上板集成复验后才能填写新的tested_build及真实运行时证明，不把离线清单冒充板上验证。
本轮仅本地准备，不合入已登记的正式分支、不推送、不登记板上默认启动。

## 离线交付结果

| 门禁 | 结果 |
|---|---|
| 六段构建 | 每个前缀完整Image/dtbs/modules通过；前3段核心未接入，后3段ADLA=m |
| 说明整理证明 | 前缀1–4/6与已构建tree相等；第5段仅MAINTAINERS条目移动，另作完整构建通过 |
| 集成完整构建 | Image/dtbs/modules、匹配2338模块与静态ARM64 PID1通过 |
| build ID | `b5f919294867c4a1853406d10bf1f8997bf135de` |
| Image SHA256 | `a391ca015375ca6e063bda5497dd3b262f6df544cb1792783b49c915b790e289` |
| schema/DT | ADLA binding和目标schema匹配DT检查通过 |
| 宿主 | 四个Python harness及bounds/ABI C通过 |
| W=1/sparse | 实际执行24个CHECK；源代码与npu4相同，存量诊断保留，不宣称全驱动零警告 |
| 主仓unittest | 最终共享工作树311项、7跳过，OK；保留并行任务改动 |

载荷16文件的SHA、归档2338模块的release、静态PID1 ELF及release均独立复核。
本机副本`build/npu-integration/candidate`，含manifest和runtime清单；主仓运行时提交558bab7。
runtime清单记录的主仓快照为975d8ae（并行任务提交后的HEAD），五个实际输入文件已逐SHA
证明等于558bab7的内容，载荷未复制任何GPU工具或补丁。
VM `~/build/npu-review`保存prefix-1至6.log、final-prefix-5.log、prefix-equivalence.json，
以及final-checkpatch-1至6.log，记录旧说明版本到最终序列的树对应关系。
集成输出保留final-build.log、verified-build.log、schema.log、dtbs-check.log、host-tests.log、
w1-sparse.log、package.log及build.json；不使用复制的npu4日志冒充本轮通过。
DTB包内MAC处理与npu4相同，SHA仍49a858fae2f9a66e8db96ea6eee7011e620b3d116c572995bfca57fc56cb0462。

## 共用rootfs的用户态部署方案与测试

现有libadla/libnnsdk 1.4.0.2与模型输入保持同一份、同SHA，两个内核都使用/dev/adla0。
这部分没有按内核复制或替代的必要：兼容ABI的目的就是让闭源SDK与模型直接复用。
内核专属部分是/lib/modules/RELEASE中的KMD及匹配依赖；5.15继续厂商模块，
7.3通过DT modalias/udev加载adla_core，必要时在独占预检用modprobe显式加载，
失败立即报错，不从其他release兜底加载。SDK使用设备/版本合同，不切换库来掩盖KMD缺失。

沿用vim4-kvm-run及vim4-board-runtime的显式release白名单，新增uhd2路由，
匹配HDMI/gadget准备器及One-KVM助手共5文件；5.15仍走vendor，uhd2走Wave5。
NPU不是视频后端，不向One-KVM界面增加不存在的NPU功能，也不新增持久守护进程。
这五个助手沿用已有的库路径/任务CPU策略；本轮不改GPU环境变量逻辑。
推理使用已验收的khadas用户与环境；npu4记录过root SDK建网失败，不能以提权替代部署。
root仅用于模块安装、启动准备与诊断控制，普通推理权限仍须下一窗口核对/dev/adla0。

部署时持锁备份当前五助手和启动文件，校验SDK/模型/输入/probe SHA、候选完整模块与build ID，
安装匹配助手后刷新现场证明，再prepare/stage，U-Boot RAM选择uhd2。
结束回5.15并恢复助手；按本窗口备份核对哈希、权限、服务与UDC。
批准正式部署后，助手随board/edge包发布，模块按release安装；默认5.15仍保留，
不覆盖共享库、不手工替换模块、不清空应用状态。

离线测试已扩展真实边界：uhd2一次性归档的模块目录/CMA/HDMI选项，
助手SHA与证明不符时拒绝prepare；应用启动器覆盖5.15、uhd1和uhd2的后端环境选择。
这些测试不运行SDK或板上modprobe；闭源库兼容的硬件证据来自npu4，集成仍须复验。

## 下一窗口≤20分钟

真正同窗口两内核交替配对、三模型及十分钟并行再回退会挤占恢复余量，
因此预留回退时间，并行稳定性取6分钟（≤10分钟），不削减输出校验。

| 分钟 | 操作 |
|---|---|
| 0–3 | 锁空闲、5.15身份/服务/UDC/备份核对；同一工具/输入重测三模型101轮，另取VGG16独立501轮作配对参考 |
| 3–6 | 匹配助手、现场证明与RAM一次性启动uhd2；512MiB CMA、ADLA/HDMI probe及运行build ID核对 |
| 6–9 | 三模型101轮全张量比对旧5.15和本窗口参考，另取VGG16同样501轮；报告P50/P99/max与平均退化≤5%，超门槛直接失败，不重跑挑样本 |
| 9–15 | 先NPU关的视频短基线，再连续NPU＋HDMI/Wave5约6分钟，逐组有界；记录完整组、帧推进/编码错误/丢帧与NPU延迟，失败立即停本项 |
| 15–20 | 回默认5.15、恢复助手，重测VGG16独立501轮作温漂参考，核对文件哈希/权限、四服务、UDC，保存证据并释放全部锁 |

两次5.15 VGG夹住候选，分别报告对前/后参考的退化与漂移，不能只选较快参考。
配对组各去首轮，使用相同用户、亲和策略、输入和CPU/视频负载，记录温度与实际频率；
普通性能组关闭trace，分报单轮尾延迟与各组均值，不以增大样本数消除真实系统差异。
六分钟并行只证明该观察时长，不登记为长稳；每个子进程timeout≤10分钟。
不发HID（Mac mini M6）、不测声音、不ptrace视频进程、不写PWM/电压、不测真实复位失败，
测量不并行编译。失联无法自动恢复就停止报告，不能延长窗口现场修驱动。
