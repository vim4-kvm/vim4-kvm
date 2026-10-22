# 2026-10-21：VIM4 7.3 Panfrost 调频与供电

独立内核工作树 `/home/deepdream/src/linux-7.3-gpu`、分支 `vim4-gpu-devfreq`，
基于 `ffdadae5b3f85`。本次只处理 GPU，不改 Wi-Fi/P2P，不停 manager。
两个提交为 `3a5508bc9094f`（Panfrost 纯频率 OPP）与
`d003a661b08d5`（VIM4 DTS）。未推送，不提交主仓库文档。

## 厂商证据与电压边界

核对 VM 中的 5.15 内核 `80a07ad5406d57855c996285ae75a50a1b9147ae`、
common_drivers `4cfb128d36f8511b2db1bd13c08d5704347ded49`、
U-Boot `b60ff51ece0fb05456261b1aabb043db6bd923d5`。

- `common_drivers/arch/arm64/boot/dts/amlogic/kvim4n.dts` 包含 `mesont7.dtsi`。
  后者 `&gpu` 的实际 `tbl` 指向 `dvfs250_cfg/400/500/666/800`，最高档重复一次用于 preheat。
  定义在 `mesong12a-bifrost.dtsi`，分别为 250000000、400000000、500000000、
  666666666、800000000 Hz。另一张通用 `gpu_opp_table` 首档是 285714281 Hz，
  与实际 `tbl` 不同；本次采用实际 DVFS 路径的五档，不混入未启用的档位。
- `drivers/gpu/arm/midgard/platform/devicetree/mali_clock.c` 的 Linux ≥4.4 路径中，
  `critical_clock_set()` 只调用 `clk_set_rate()`。厂商配置为
  `CONFIG_MALI_MIDGARD_DVFS=y`、`CONFIG_MALI_DEVFREQ` 未启用。
  表中的 `voltage=<1150>` 只被读取、打印；通用 OPP 的 `opp-microvolt=<1150>`
  也不能解释成可用的 1150µV 或自行乘为 1.15V。
- [Khadas V13A 原理图](https://dl.khadas.com/products/vim4/schematics/vim4-sch-v13a.pdf)
  POWER 页列出 `VDDGPU_PWM`，不是物理固定电源。U-Boot
  `board/khadas/kvim4/firmware/timing.c` 明确 `GPIOE_4 / PWMAO_E / VDDGPU`，
  BL2 初始化 AO_EF 的 A 通道；`board/khadas/configs/kvim4.h` 定义初始化 830mV。
  此固件表与现有主线 PWM regulator 的线性换算不是同一套标度，不能用来推导逐档电压。
- 主线已有 `regulator-vddgpu`：SY8003ADFC、`pwm_ao_ef` 通道 0、1500ns，
  声明范围 700000–922000µV，反向 duty range。原板 debugfs 请求 416/1500ns，
  实际 415/1498ns；regulator 报 859mV 是驱动模型值，未经万用表实测。

因此本次仅调频，保留固件 PWM 设置；**不声称 VDDGPU 硬件不可调，也不提供调压支持**。
没有可靠的频率/电压对应表，电压修改停在这里。

## 修改

VIM4 DTS 给 GPU 增加 `mali-supply = <&vdd_gpu>` 和不含 `opp-microvolt` 的五档 OPP。
Panfrost 只在 OPP 表描述电压时把 regulator 交给 OPP 核心；纯频率表由设备路径
取得、启用真实 supply，并保留原有 runtime PM 的关闭/恢复配对。
无 OPP v2 表的平台保留原 regulator 设置行为；没有增加 T7 专用寄存器操作。

板上实际 `FullKvm` 使用 `/boot/edge/Image`、显式 `FDT /edge/vim4.dtb`，
不是 `/boot/dtb.img` 指向的 5.15 `kvim4n.dtb`。通用构建 DTB 不含已部署的全部
USB/HDMI/音视频实验配置，不能直接覆盖。测试 DTB 在原始 DTB 上合并 GPU overlay，
只新增 OPP 节点、两个 GPU 属性、regulator phandle 和 overlay symbols；
二进制 FDT 属性对比确认原有属性逐字节不变，含 MAC、USB 和音视频配置。

本机证据与负载源码位于 `logs/gpu-devfreq/`；VM 产物位于
`~/build/kernel-edge-gpu`，与其他任务的 O= 目录独立。

## 构建与验证

```sh
orb -m vim4-build bash -lc 'make -C /home/deepdream/src/linux-7.3-gpu \
  O=/home/deepdream/build/kernel-edge-gpu ARCH=arm64 -j6 Image dtbs modules'
```

配置直接复制 `uhd1.config`，olddefconfig 后 SHA256 仍为
`610ff17daf5bb40085ca657f40a7436c1ff257c57aabb65367fb2aa3a4709ae9`。
GCC 13.3，完整构建成功、无编译 warning/error；2334 个模块保留 BTF，
`modules_install INSTALL_MOD_STRIP=1` 后压缩归档，安装带 `--keep-directory-symlink`。
构建前保存的完整 diff 与最终两提交相对基线的 diff 逐字节相同。
`checkpatch.pl` 为 0 errors、0 warnings。
原始构建 DTB 和保留运行时配置的测试 DTB 均通过 Mali Bifrost / OPP 定向 schema 检查；
未声称全板 dtbs_check 通过。

| 产物 | SHA256 / build ID |
|---|---|
| Image | `8a1b7918012e479b07abb063d95b1bed719046df82868f97b3f9768cd4604b0e` |
| 完整模块包 | `25747ed1239fcb920542c3779136be29ee80790cb2142bf3433413d4a693057d` |
| 保留运行时的测试 DTB | `4c552096541342e5b52f79436d075ba19124be7a3533acb4b70e8b4fefa6842b` |
| vmlinux / 实际运行内核 | `fc3726474b0c82c528172d0e589844b8fc9fb90b` |

实际运行 build ID 从 `/sys/kernel/notes` 解析，并与本次 vmlinux 对照。
运行 Panfrost 的 `/sys/module/panfrost/notes/.note.gnu.build-id` 为
`c957c7cdfacb429819c7fef2096fb5f13d63212b`，与本次完整模块包中的模块一致。
候选 release 与原系统同为 `7.3.0-rc7-vim4kvm-uhd1+`，候选 `uname -v` 为
`#1 SMP PREEMPT Thu Oct 22 12:48:04 +08 2026`，不能只靠 release 判断安装成功。

## 上板命令与实际结果

Mac 用 `/usr/bin/lockf -t 1 /tmp/vim4-board.lock /bin/bash --noprofile --norc`
取得一个持续 shell，安装、两次重启、负载、恢复与清理均在其持锁期间执行。
SSH 使用 `-n`，避免吸收交互 shell 后续输入。
原文件和完整模块先备份至 `/var/backups/vim4-gpu-devfreq-20261021`，
原模块目录另行保留；未重写 extlinux、5.15 启动链接或 runtime inventory。
Image 与全部模块同次构建，FullKvm 无 INITRD，不修改 5.15 initramfs。

候选启动后执行：

```sh
ssh -n vim4 'cat /sys/class/devfreq/fe400000.gpu/{available_frequencies,cur_freq,governor}'
# 250000000 400000000 500000000 666666666 800000000
# 250000000
# simple_ondemand
ssh -n vim4 'sudo dmesg | grep -iE "panfrost|mali|gpu|devfreq"'
# panfrost fe400000.gpu: clock rate = 799999987
# panfrost fe400000.gpu: mali-g52 id 0x7402 major 0x1 minor 0x0 status 0x0
# [drm] Initialized panfrost 1.6.0 for fe400000.gpu on minor 0
```

完整 dmesg 未检出 `no regulator (mali)`、`supply mali not found`，
也无 GPU job timeout、MMU fault 或 Panfrost error/fault/timeout。
`regulator_summary` 显示 `fe400000.gpu-mali` 已接到 `VDDGPU`，没有 dummy supply。

板上未找到 glmark2-es2-drm/kmscube/vkmark；使用已有 GCC、EGL/GLES 开发库编译
`logs/gpu-devfreq/gles-load.c`，不安装额外软件。程序用 surfaceless EGL 1.5、
1024×1024 pbuffer、全屏三角形和 128 次迭代片元着色器，每帧 `glFinish()`，
最后 `glReadPixels()` 检查颜色与 GL 错误，拒绝非 Mali-G52 renderer。

在持锁 shell 中执行以下板端命令（实际由 `ssh -n vim4` 调用）：

```sh
cd /var/tmp/vim4-gpu-devfreq-20261021
gcc -std=c11 -O2 -Wall -Wextra -Werror gles-load.c -o gles-load -lEGL -lGLESv2
sudo python3 validate-gpu.py
```

`validate-gpu.py` 在 userspace governor 下边渲染边对五档升降，随后切回
simple_ondemand，运行低占空比、连续负载、空闲、runtime resume。
约每 100ms 读频率、runtime 状态和六个温区，退出时恢复原 governor。

| 验证 | 实际输出 / 观察 |
|---|---|
| 渲染器 | `Mali-G52 r1 (Panfrost)`；`OpenGL ES 3.1 Mesa 25.2.8-0ubuntu0.24.04.4` |
| 五档往返、25 秒渲染 | `frames=477 elapsed=25.035 pixel=14,128,128,255 gl_error=0` |
| clk_summary 实际五档 Hz | `249999996 399999994 499999992 666666656 799999987`，每次与请求相差 <1000Hz |
| 低占空比，帧间暂停 500ms | `frames=38 elapsed=20.334 pixel=199,128,128,255 gl_error=0` |
| 连续 60 秒 | `frames=1827 elapsed=60.021 pixel=72,128,128,255 gl_error=0` |
| 挂起后的再次渲染 | `frames=152 elapsed=5.030 pixel=199,128,128,255 gl_error=0` |
| 温度 | 连续阶段 GPU 50.0–59.1°C，六温区最高 62.7°C；全测试 GPU 最低 49.9°C |
| 软件状态 | `systemctl is-active vim4-manager` → `active`；`/proc/sys/kernel/tainted` → `0` |

连续阶段 583 次采样中初始 2 次为 250MHz、之后 581 次为 800MHz。
结束后的空闲 50 次采样均为 runtime suspended、`cur_freq` 缓存 400MHz；
再次渲染升到 800MHz，全部测试结束后读到 250MHz、suspended。
**runtime suspended 时 cur_freq 是缓存频率，不代表关钟期间实际运行频率**。
低占空比阶段多数缓存读数仍为 800MHz，不能据此声称每次帧间都降到最低档。

从原内核、候选启动到负载前后，GPU PWM 均为请求 416/1500ns、实际 415/1498ns，
每档快照也一致；859mV 仅是现有 regulator 模型的读数。本次不变更电压换算、
PWM period、父时钟或 GPU 时钟驱动；已有双路径时钟切换满足本次五档测试。

## 恢复证据

恢复脚本复制原 Image/DTB、移回原模块目录，启动前和恢复重启后均核对清单。
没有对原模块重新 depmod，保留原有依赖文件和符号链接。

```text
uname -v: #12 SMP PREEMPT Thu Oct 22 06:14:20 +08 2026
/boot/edge/Image: OK
/boot/edge/vim4.dtb: OK
/boot/extlinux/extlinux.conf: OK
/boot/uEnv.txt: OK
/boot/vmlinuz-5.15.137: OK
/boot/vmlinuz-5.15.137-vim4kvm: OK
/boot/initrd.img-5.15.137: OK
/boot/initrd.img-5.15.137-vim4kvm: OK
module_files_verified=2347
manager: active
taint: 0
```

原 Image SHA256 为 `25241ef8c402619e6917e6826129ba301c4b4dfacc4665db365620e9489faa48`，
原 DTB 为 `471fc2881ed6c83726ac1db85277aaeadbb63eb6b608d821f2e0bc177d96a567`。
候选 boot ID `37019c48-4ddb-45e7-91e8-80ac0880179e`，
恢复后为 `c89298af-6dc6-48f8-881f-c62d879fedd7`。
恢复后的 devfreq 目录为空，原版本的两条 mali regulator 警告重新出现，符合原状态。
`/lib -> usr/lib`、5.15 Image/DTB/initrd 链接与备份一致，Stock 启动项保留。
板上候选 Image、DTB、模块包及候选模块目录已删除；保留原备份与测试日志。
完成后退出持锁 shell，确认锁已释放。

主仓库离线检查 `python3 -m unittest discover -s tests -p 'test_*.py'`：
`Ran 147 tests ... OK (skipped=5)`。本条文档 12KB 以内，已登记索引；主仓库未提交。

## 限制

本次不覆盖显示输出、Vulkan、长期稳定性或所有主线 Panfrost 平台回归；
短时离屏 GLES 负载不能代替这些验收。最终合并和永久部署由用户处理。
