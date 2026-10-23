# 2026-10-23：厂商5.15一次性启动往返与GPU用户态识别

摘要：5.15.137-vim4kvm经RAM sysboot启动，SSH可达；正常重启自动返回未修改的7.3
默认基线。5.15实际EGL/GLES是Mesa/llvmpipe，未找到匹配的专有libMali；相同glmark2
命令得19分，实际4096×2160，与M1/Panfrost历史925分的1920×1080不可直接比较。
本轮没有安装GPU库、修应用或部署内核；整夜采样只形成[待确认计划](../overnight-performance-plan.md)。

## 基线与暂存边界

开工先git pull，主仓为`16f44c0`。sources.toml仍固定正式内核`aa2f875bec2fc`、
build ID `7b8372b894c98ffae12e636a325c86f2b6c85e00`；新M1/Wave5分支合入不代表已部署。
用Mac持久shell按board→heavy顺序等待并取得两把lockf锁，覆盖全部启动、测量和恢复。
没有打断采集任务；取锁后才访问板子。基线one-kvm/manager/monitor active、UDC configured、
isolated=0、taint=0，无挂载虚拟介质，pstore为空。

入场记录Image/DTB/extlinux/uEnv、运行登记、应用、两个内核完整模块目录与journal。
5.15对照登记清单核对1532项、7.3核对2349项，匹配项无哈希差异；完整目录快照分别
包含1529/2347个文件。5.15 initrd包含其自身release模块，保留`/lib -> usr/lib`。
两DT的ramoops同为0x07400000/1MiB、record=0x20000、console=0x40000，厂商另有
ftrace/pmsg分区；启动参数仍含厂商尺寸参数，因此不把跨内核pstore兼容视为已验证。

只在boot分区增加两个临时配置，不覆盖默认extlinux、Image/DTB、模块或登记文件：

- `/boot/perf-baseline-check-20261023.conf`：当前7.3文件及原APPEND，增加一次性标记。
- `/boot/perf-vendor-c6446a1ce640df9d.conf`：显式5.15版本化Image、initrd、kvim4n DTB。

厂商APPEND从实际U-Boot `bootargs`与 `/boot/uEnv.txt`解析，root UUID经blkid核对；
`boot_source=emmc`来自实际固件日志，保留厂商console/PD参数及最终ordered根挂载。
不复制7.3的黑名单或systemd masks。使用[生成器](../../tools/vendor-boot-plan.py)拒绝
残留变量及init覆盖，追加oops=panic/panic=20和一次性识别标记。

## 四次启动结果

| 操作 | 实际结果 | 请求重启到UART login |
|---|---|---:|
| RAM sysboot当前7.3独立配置 | 从mmc1:1读取成功，cmdline有一次性标记，服务/UDC正常 | 18.955秒 |
| 正常重启到原默认7.3 | 标记消失，build及受保护文件/应用一致 | 25.638秒 |
| RAM sysboot厂商5.15 | Image、initrd、DTB加载成功，SSH可达 | 27.522秒 |
| 5.15正常重启 | 无串口干预、未改默认，自动回7.3 `7b8372b8…` | 24.907秒 |

时间含SSH请求/串口观察开销，只作本次启动观察，不是三组启动性能基线。
实际当次命令为：

```text
sysboot mmc 1:1 any ${pxefile_addr_r} /perf-vendor-c6446a1ce640df9d.conf; reset
```

不执行saveenv或持久启动选择。固件自己的启动日志有既有`Unknown command 'saveenv'`
提示，不是本窗口向串口发送了saveenv。硬挂死/看门狗超时/物理RESET没有测试，
这次证明的是正常重启后的默认返回路径。

5.15实际build ID `389f77352dc8ab21aa80d8cf36819bb9da31d7ee`。初到login时One-KVM
尚未启动，随后自行成为active；manager active、两服务HTTP均200、UDC configured。
未修复或手动启动服务，未测5.15完整应用视频/音频兼容。taint=12288，journal对应
厂商模块缺签名及vfm_cap树外模块；未检出Oops/BUG/Kernel panic，不能将其写作taint=0。

## GPU发现与一次离屏结果

内核加载`mali_kbase`，设备`/dev/mali0`存在；DRM card0/renderD128属于厂商`meson`。
这没有提供可由Mesa使用的Panfrost内核接口。用户态实际安装GLVND 1.7.0和
Mesa 25.2.8，EGL vendor目录只有`50_mesa.json -> libEGL_mesa.so.0`；
ldconfig及 `/opt`、`/usr/lib`、`/usr/local/lib`未找到专有libMali。
`mali-dp_dri.so`属于Mesa DRI库，不据其文件名认定为专有Mali栈。

复用M1窗口提取的glmark2 2023.01二进制/数据，临时解到`/var/tmp/perf-vendor-20261023`，
没有apt安装或替换EGL链接。二进制SHA256：
`d731c7eca4322ce12ad08afd49a8e130e91489995c5f0f80afeb7eaae856afa9`。

```sh
sudo env DRI_PRIME=1 /var/tmp/perf-vendor-20261023/gpu-root/usr/bin/glmark2-es2-drm \
  --off-screen --winsys-options drm-device=/dev/dri/card0 \
  --data-path /var/tmp/perf-vendor-20261023/gpu-root/usr/share/glmark2 \
  --size 800x600 -b :duration=2
```

运行加110秒有界超时，实际88.677秒、退出0。原始结果与历史口径：

| 项目 | 本次5.15 | [M1第七窗口7.3](2026-10-23-display-m1-window7.md) |
|---|---|---|
| GL_VENDOR | Mesa | Mesa |
| GL_RENDERER | llvmpipe (LLVM 20.1.2, 128 bits) | Mali-G52 r1 (Panfrost) |
| GL_VERSION | OpenGL ES 3.2 Mesa 25.2.8 | OpenGL ES 3.1 Mesa 25.2.8 |
| 命令请求/场景时长 | 800×600、每场景2秒 | 相同 |
| 实际Surface Size | 4096×2160 fullscreen | 1920×1080 fullscreen |
| glmark2 Score | 19，软件渲染 | 925，硬件渲染 |

DRM flavor忽略请求的窗口尺寸、使用显示面尺寸。两结果的后端、实际尺寸和内核构建
不同，**不计算925/19倍速比，不据此判断硬件性能追平**。5.15硬件GPU比较属于测量缺失，
下一轮先取得匹配的合法用户态和双方共同离屏接口。7.3的925来自M1候选
`844bfec2…`，不是本次默认M0 `7b8372b8…` 的新样本。
5.15日志有async page flip不支持和退出恢复原CRTC=-2；不修显示，随后按计划重启回基线。

## 恢复冒烟与证据

恢复后首先核对build/cmdline、五个启动/登记文件与两个运行应用哈希，UDC configured、
isolated=0、taint=0。Chrome 156.0.8078.47在同一H.264连接预热15秒后测300秒：
3840×2160、18008解码帧、59.99938fps，丢帧/丢包/冻结增量均0；每30秒像素摘要变化，
收尾截图可见运动网格、三带帧标记与RGB色块。初次运动源按旧VIM4显示名启动失败，
只影响Mac测试进程；发现实际是RTK UHD HDR后改为RTK，首个30秒窗口前运动源已启动，
未改EDID或模式。该轮是恢复冒烟，不作为端到端延迟或性能配对样本。

随后真实HID测试：keyboardDown=1、keyboardUp=1、绝对/相对鼠标、点击、滚轮均通过，
原生窗口关闭并恢复指针。最终完整文件与两个模块目录逐项与入场一致，内核journal无
Oops/BUG/Kernel panic/WARNING；one-kvm/manager/monitor active、UDC configured、
isolated=0、taint=0，boot ID为`f53c8769-d834-4b88-9c05-8300246dd03e`。
删除两个boot临时配置及私有GPU目录、上传包并同步boot目录，未安装软件或修改持久配置。
15:32:26 UTC前已退出持锁shell、释放两把锁，随后才进行离线检查和文档提交。

本地原始证据位于`logs/vendor-baseline/2026-10-23/`：`before.json`、`before-health.json`、
`baseline-once-uart.log`、`baseline-default-uart.log`、`boot-plan.json`、
`vendor-once-uart.log`、`vendor-gpu-stack.txt`、`vendor-glmark2-run.log`、`vendor.json`、
`vendor-final-journal.txt`、`return-default-uart.log`、`restored-smoke.log`、`smoke-result.json`、
`restored-picture.png`、`restored-hid.log`、`after.json`、`final-health.json`、`cleanup.log`。
日志不入Git。整夜任务未启动，待用户确认时间；硬件GPU、外部仪器等缺失项须按计划先处理。
主仓离线验证：`python3 -m unittest discover -s tests -p 'test_*.py'`，223项、6项跳过，无失败。
