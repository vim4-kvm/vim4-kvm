# 2026-10-23：厂商 H.264 活体对照与物理时钟检查候选

厂商5.15实际解出600个NV12输出buffer并正常EOS。解码中普通MMIO读取
`fe32260c=3ff`、`fe322638=2a008`，退出解码后两处读取均返回0，没有SError。
因此不能把7.3故障解释为GCLK_EN只写、地址整体错误或每次访问必须SMC代理。
找到具体差异：两个CPU/APB门控厂商为开启、7.3基线为关闭；候选显式持有它们，
并补充CLKCTRL原始值与拒绝访问门禁。**尚未证明这就是SError根因**，未宣称修复硬件解码。

前次失败见[GCLK窗口](2026-10-23-vdec-gclk-window.md)，厂商出处与十三步接口见
[离线审计](2026-10-23-vdec-gclk-offline.md)，启动依据为
[厂商一次性启动](../vendor-boot-baseline.md)。本轮用户明确批准无人值守厂商窗口；
没有启动新的7.3候选，没有正式部署或合入正式内核分支。

## 实际窗口与工具

入场/恢复目标均为7.3 build `eeddb005df059a850853876d52ef603aa1af192b`。
两轮厂商启动均使用U-Boot RAM中的一次性sysboot，未saveenv、未改默认项。
使用已核验的版本化5.15 Image/initrd/kvim4n DTB和独立5.15模块目录；完整模块
清单与既有同次构建清单逐文件比较。不存在已挂载的USB媒体LUN。
临时配置另建`/boot/perf-vendor-vdec-live-20261023.conf`，不覆盖已有启动文件。

每个窗口全程先取heavy、再取board锁；包括准备、启动、读取、正常重启、恢复冒烟、
清理。完整构建等第二窗口释放heavy后才开始，未干扰恢复后的帧率采样。

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-vendor-live/field.py
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-vendor-live/field-second.py
```

预置第一次因Mac没有ffmpeg而在启动前失败，已清理独立小配置；改在板上7.3生成
640×368、30fps、20秒、单slice/ref1/b0 H.264 constrained-baseline fixture。
第一轮厂商窗口确认硬件解码输出，但厂商`CONFIG_DEVMEM=n`、没有`/dev/mem`，
原读取器open得到ENOENT，**没有执行MMIO**；正常终止解码、回基线并冒烟后才开第二轮。
第二轮改用厂商已有debugfs物理读取接口，所有目标读取和完整解码均成功。
两轮均正常重启返回，不需要看门狗触发或人工RESET。

厂商实际release `5.15.137-vim4kvm`，build
`389f77352dc8ab21aa80d8cf36819bb9da31d7ee`。串口921600与dmesg记录：
BL31 `v1.3.2 2dd964006`，2026-02-01构建；OP-TEE `3.8 ec8c40b0`。
与前次7.3候选使用同一BL31版本，未修改安全固件。
5.15读寄存器前确认watchdog sysfs `active`、debugfs `enabled=true`、
PID1持有`/dev/watchdog0`、timeleft=28、`stop_after_panic=0`，systemd为30s/60s。
这是运行期喂狗配置核验；本轮未注入5.15故障，不扩张为早期引导故障复位证明。
失联预算180秒、每15秒检查与现场恢复输出约定保留，但未触发。

## 解码与原始读取

实际使用已安装的`libgstamlv4l2.so`，没有安装模块、厂商工具或修改配置：

```sh
GST_REGISTRY=/var/tmp/vdec-vendor-live-20261023/decoder-registry.bin \
gst-launch-1.0 -v filesrc location=/var/tmp/vdec-vendor-live-20261023/sample.h264 \
  ! h264parse ! amlv4l2h264dec ! identity silent=false ! fakesink sync=true
```

以khadas运行；采样控制器确认首个identity输出、进程仍运行后才读寄存器。
主控65秒预算，逐个物理读取子进程3秒预算，解码EOS等待30秒；失败不重试MMIO。
实际输出caps `video/x-raw, format=NV12, width=640, height=368, framerate=30/1`，
`Got EOS from element "pipeline0"`，`VENDOR_DECODE_EOS chain_count=600`。
活动时`vdec_status`为`ammvdec_h264_v4`、frame count=8、drop/fra err/hw err均0；
这是早期快照，不将它的60fps字段当吞吐测试。没有保存像素逐帧比较，不给正确帧MD5/PSNR结论。
插件扫描有无关videosink/nvcodec缺库及属性警告；实际解码pipeline成功EOS。

读取接口为`/sys/kernel/debug/aml_reg/paddr`：写入**一个地址token仅设置缓存地址**，
随后一次`os.read(fd,80)`触发一笔4字节物理读，避免EOF二次读取。
没有向该接口传第二个数值，没有用户主动MMIO写。依据固定厂商common_drivers
`4cfb128d36f8511b2db1bd13c08d5704347ded49`：
`drivers/memory_debug/reg_access/reg_access.c:34–51,84–149`，最终为
`ioremap/readl_relaxed`，不经过TEE代理。先核对这段实现再使用该接口。

| 地址/寄存器 | 解码进行中 | EOS后、VDEC域off |
|---|---:|---:|
| fe32fc04 DOS_GCLK_EN0 | 000003ff | 00000000 |
| fe32fc00 DOS_SW_RESET0 | 00000000 | 00000000 |
| fe32fcc0 DOS_MEM_PD_VDEC | 00000000 | 00000000 |
| fe000140 CLKCTRL_VDEC_CLK_CTRL | 00000100 | 00000000 |
| fe000148 CLKCTRL_VDEC3_CLK_CTRL | 80000000 | 80000000 |
| fe000044 SYS_CLK_EN0_REG0 | ffffffff | fffffffd |
| fe32260c GCLK_EN | 000003ff | 00000000 |
| fe322638 MDEC_PIC_DC_CTRL | 0002a008 | 00000000 |

以上均有READ_BEGIN/READ_COMPLETE。断电读零只陈述总线返回，不能推导RAM真实内容，
也不授权在7.3断电访问内部DOS。140/148高半字属于HCODEC，未主动改动。

## 时钟、电源、地址和安全路径对照

| 项目 | 厂商活体 | 7.3已知情况与边界 |
|---|---|---|
| DOS基址 | debugfs直接物理读fe32xxxx成功；DT为fe320000/10000 | 与候选映射/word×4偏移相同，没有换bank依据 |
| 功能时钟 | fclk_div2p5→vdec_p0_mux/div/gate→vdec_mux，799999988Hz，enable/prepare=1；p1 gate关闭 | 旧候选CCF报告799999987Hz，但没有140/148原始值，不能声称父源/gate已实测一致 |
| 系统总线 | t7_dos由sys_clk供166666664Hz；活动引用1、EOS后0；044 bit1随之关闭 | 7.3基线SYS_DOS同166666664Hz；旧候选申请该时钟，缺故障窗口物理门控值 |
| CPU/APB门控 | t7_pclk_sys_cpu_apb、t7_a73pclk_cpu_apb，166666664Hz，enable/prepare=0但hardware Y | t7_sys_pclk_sys_apb、t7_sys_a73pclk_apb均hardware N；对应同一4c寄存器bit19/20，存在确定的门控状态差异 |
| 共享AXI桥 | am2axi0/1/2均hardware Y | 三者也均Y，主线为critical；没有证据再开启未知NIC/AXI位 |
| VAPB | 活动vapb_sel为666666656Hz | 7.3基线vapb为499999992Hz；它用于VPU/采集，未找到VDEC依赖证据，本候选不调整 |
| VDEC域 | 活动on、EOS后off，genpd:0:vdec active→suspended | 旧候选SMC GET4=on，reset/memPD均0；仍不足以证明所有访问条件 |
| NIC3 | idle-before/active/idle-after均on | 旧候选GET39=on并持有父域引用；未发现新增域ID证据 |
| 其他DOS域 | HEVC均on（thermal），HCODEC均off；WAVE为基线KVM使用 | 7.3基线HEVC也on、HCODEC off；不能仅凭HEVC on认定H.264依赖HEVC |
| RAM/隔离 | secure genpd控制；活动memPD=0 | 本轮未读未知PWRCTRL ISO位，未观测BL31内部执行序列，不猜测补写 |
| TEE | 普通物理读在解码时及解码后均可用 | 排除每次读必须TEE代理；不能排除厂商早期安全配置的作用 |

厂商时钟位定义见`drivers/clk/meson/t7.c:3733–3855,7129`；
`drivers/media_modules/common/media_clock/clk/clkg12.c:479–521,732–768`仍为EN0低10位→
频率配置；`drivers/media_modules/frame_provider/decoder/utils/vdec_power_ctrl.c:151–157,268–282`
随后取secure域。T7不走legacy AO隔离分支。候选已经采用这一顺序。
同一decoder目录下`h264_multi/vmh264.c:11223–11238,11424`中amvdec_enable在reset和微码加载之前，
`utils/amvdec.c:72–87`直接写GCLK并读改PIC；没有找到针对这两地址的SMC代读写。
本轮没有跟踪厂商全部SMC调用，不能声称已排除TEE初始化或微码加载的所有影响。

新增CPU/APB差异来自完整clock表：厂商active-clk.txt:368–369的Y，对照
mainline-idle-state.txt:444–445的N；这是硬件is_enabled列，不把零软件引用误作关闭。
厂商`t7.c:7105–7123,7191–7192`的SYS_GATE统一CLK_IGNORE_UNUSED；主线
`drivers/clk/meson/t7-peripherals.c:1285–1286`对应两gate flags=0，未被消费者持有时会关闭。
两处名称指向CPU/APB门控，但缺VDEC内部APB连线说明；候选保留厂商活体开启状态是一项
有依据的受控假设，尚不能断言两者都是VDEC硬件必需时钟。

## 候选改动、构建与下次门禁

独立worktree `~/src/linux-7.3-vdec`、分支`vim4-vdec`，三个新提交：
`20d6e5ec44ec9`物理门控检查、`6bb00c29fa04e`绑定、
`a915603f5efb795afc72b5d92aa2c72e0e939a14`CPU/APB引用与DT；基于原c6fc96a…，没有更改正式源码树。
`aml_vdec_hw.c`通过DT首个clock引用取得T7 clock provider现有regmap，只读共享CLKCTRL，
不另占映射、不绕过CCF写共享寄存器。probe仅绑定资源，allow_t7_power仍默认关闭。

DT新增sys-apb/a73-apb两个clock引用；只在显式power/probe步骤时通过CCF开启，
在DOS总线/功能时钟之前持有，直到secure下电、释放NIC3后才释放。probe默认不开时钟，
正常DT节点仍disabled；未把全局gate改critical，也不永久影响JPEG/Wave5。

在power_test的DOS读前、十三步第5步secure域/策略之后，记录044/04c/140/148原始值并核验：
SYS_DOS bit1、04c bit19/20开启，实际选中的p0或p1 gate bit8开启、source[11:9]=0、div[6:0]=0，
与本轮800MHz recipe相符；HCODEC高位及非选中路径不参与拒绝判断。
读失败或不匹配返回错误并下电，不进入后续DOS访问。正常open复用同一检查。
这修正了只依赖CCF缓存频率的前置检查缺口，**不是已验证的SError根因修复**。
若新门禁通过而内部读仍失败，应继续查安全初始化/隔离，不重复猜写或改地址。

Mac/VM实际C函数故障注入各12项通过，覆盖桥时钟先开后关与失败展开、选中gate关闭、
错误父源/分频、双路径选择、读失败提前返回及错误回收后不发DOS事务。
三个提交分别strict checkpatch为0 errors/0 warnings/0 checks。
独立O目录`~/build/kernel-vim4-vdec-vendor-live`，持heavy构建完整Image、两个DTB和模块：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build sh \
  /mnt/mac/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/build/vdec-vendor-live-candidate/build-vm.sh
```

完整构建和`package-vdec.py --once`通过；build
`c7e7e28f315cbadd4846ea975e27255e5a985472`，release仍为uhd1+，2335模块。
所选四模块vermagic及split BTF检查通过，build stamp绑定最终干净源码和全部ko。
VM包`~/build/vim4-vdec-vendor-live-bundle`，Mac副本
`build/vdec-vendor-live-candidate/bundle`。只供私有模块一次性启动，不可安装到基线模块目录。
Mac五个artifact哈希、静态AArch64 init、runner候选门禁和调试文件build stamp均已核验。
主仓离线全套232项通过，6项跳过；没有把跳过项记成硬件验收。

| 产物 | SHA256 |
|---|---|
| Image | 32a7367b265f829c89abe05488c5c7b8fb0a087dad7aa8f858161a80e65ddff8 |
| vim4.dtb | 871e931bb4d901c563ffa292577664a8bdeb2d6c2dcc32f4e93ada36165b59c9 |
| baseline-layout.dtb | b2e99a0efb250a102bc69585b89dc5c2871ae654b822eef928b8566bd0625564 |
| modules.tar.gz | 2e898d3b4182d8a4b7bd202ff856219255c7078da5850b7d3f624503d7eebe9d |
| config | fa46af2fa8213cd91d24dcad70b16a92b6b1b34f76394919951dce75cf5cadb6 |

新包仅离线准备，等下一次用户安排上板；每次窗口重新抓取入场基线，不复用旧快照。
下次仍按probe→power→十三步→compliance→小H.264→1080p逐帧比较推进，任一步失败即停。
先审阅CLKCTRL原始值，门禁不匹配时保留日志，不把回报800MHz当成已开gate；
即便匹配，也不能保证第9步不会SError。看门狗/一次性默认回退及180秒上限继续必需。

## 恢复、清理与证据

第二窗口UTC22:02:16–22:09:24，已释放双锁；恢复后300秒3840×2160运动H.265，
18306帧、59.9987fps，dropped/lost/freezes/PLI均0，最大回调36.6ms，无超过50ms。
真实HID keyboardDown/Up=1，绝对/相对鼠标、点击、滚轮通过。第一轮恢复也通过相同
300秒编码/HID检查。这些是原Wave5编码与HID恢复证据，不是新VDEC或非静音音频验收。

```text
build ID: eeddb005df059a850853876d52ef603aa1af192b
one-kvm / vim4-manager / vim4-wave5-monitor: active / active / active
UDC: configured; taint: 0; panic/panic_on_oops: 20/0
private module mounts: []; experimental modules: []
Wave5 SHA256: e88df353c730e5d82bbef8335788a28d5f71cfc7a4e1b8b5854ef00046d4b667
Wave5 loaded build ID: 8e2dedd2579d126adb8ba710eec2082ec1753b05
BASELINE_RESTORED_SMOKE_CLEANED
```

恢复前后JSON逐项比较Image/DTB/extlinux/kernels.json/runtime-build.json五文件、
cmdline、原Wave5安装文件与已加载build ID，全部一致。UDC始终configured，无需PD init。
删除板上本轮fixture、数据库备份、插件registry、临时配置，保留systemd历史pstore。
新旧dmesg没有本轮SError/oops；保存两处pstore归档，归档dmesg SHA仍为前次
`6519f8f6…`，没有把旧dump认作本轮故障。

原始证据在忽略目录`logs/vdec-vendor-live/`及`logs/vdec-vendor-live-second/`：
sample/window/UART日志、三个阶段完整clk/genpd、decode.log、前后JSON与pstore归档。
辅助脚本另作日志归档。第二轮scp有root-owned registry.bin权限错误；所需clk/genpd、
码流和decode.log均已保存，该registry不是硬件取证数据，未为它再开窗口。

关键SHA256：sample.log `00038235396533d500984ba290db1391e7d28048d0f4b14adfd88770638c6365`；
active-clk `e00c02862f67e77d7c7440e6b8c083c871a91f07c6b5643c64d8a53f64acb34b`；
active-genpd `1ee5fc06ea5df4f678320fd10fedd5831c965a06d72451d4a3198448b07c6d79`；
fixture `449bf8a077c6b4a9d2b356c644f373042ee0c7a0842e34e15e3f15acddcce9f8`。

最后只保留当前候选：VM bundle含vmlinux/System.map/Module.symvers/原始四模块与
build stamp调试输入，共396MiB；Mac bundle约77MiB。删除本轮完整O目录、旧
`vim4-vdec-gclk-offline-bundle`、Mac旧gclk候选和已归档的vendor窗口辅助目录。
未删除其他任务的构建目录；VM磁盘收尾可用约63GiB。原始日志和历史pstore保留。
