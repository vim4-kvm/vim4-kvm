# 2026-10-23：厂商 H.264 活体对照与物理时钟检查候选

厂商5.15实际解出600个NV12输出buffer并正常EOS。解码中普通MMIO读取
`fe32260c=3ff`、`fe322638=2a008`，退出解码后两处读取均返回0，没有SError。
两个CPU/APB门控厂商开启、7.3基线关闭；候选显式持有并核验CLKCTRL。
**尚未证明这就是SError根因**。本轮排除只写寄存器/每次SMC代理假设，未验证7.3解码。

前次失败见[GCLK窗口](2026-10-23-vdec-gclk-window.md)，厂商出处与十三步接口见
[离线审计](2026-10-23-vdec-gclk-offline.md)，启动依据为
[厂商一次性启动](../vendor-boot-baseline.md)。本轮用户明确批准无人值守厂商窗口；
没有启动新的7.3候选，没有正式部署或合入正式内核分支。

## 实际窗口与工具

入场/恢复目标均为7.3 build `eeddb005df059a850853876d52ef603aa1af192b`。
两轮厂商启动均使用U-Boot RAM中的一次性sysboot，未saveenv、未改默认项。
版本化5.15 Image/initrd/kvim4n DTB、完整模块目录与既有同次构建清单逐文件核验；无USB媒体LUN。
临时配置另建`/boot/perf-vendor-vdec-live-20261023.conf`，不覆盖已有启动文件。

每窗口全程持heavy→board双锁，完整构建在窗口释放后开始，不干扰采样。

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-vendor-live/field.py
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-vendor-live/field-second.py
```

预置缺ffmpeg已清理；码流在板上7.3生成，640×368、30fps、20秒。第一窗口硬件输出成功，但`CONFIG_DEVMEM=n`，
open `/dev/mem` 得ENOENT，**未执行MMIO**。回基线冒烟后第二窗口改debugfs，完整解码、
全部读取成功。两轮均正常重启返回，未触发看门狗或人工RESET。

厂商实际release `5.15.137-vim4kvm`，build
`389f77352dc8ab21aa80d8cf36819bb9da31d7ee`。串口921600与dmesg记录：
BL31 `v1.3.2 2dd964006`，2026-02-01构建；OP-TEE `3.8 ec8c40b0`。
与前次7.3候选BL31相同。
5.15读寄存器前确认watchdog sysfs `active`、debugfs `enabled=true`、
PID1持有`/dev/watchdog0`、timeleft=28、`stop_after_panic=0`，systemd为30s/60s。
仅核验运行期配置，未注入5.15故障。保留180秒失联预算、15秒轮询及恢复输出约定，未触发。

## 解码与原始读取

实际使用已安装的`libgstamlv4l2.so`，没有安装模块、厂商工具或修改配置：

```sh
GST_REGISTRY=/var/tmp/vdec-vendor-live-20261023/decoder-registry.bin \
gst-launch-1.0 -v filesrc location=/var/tmp/vdec-vendor-live-20261023/sample.h264 \
  ! h264parse ! amlv4l2h264dec ! identity silent=false ! fakesink sync=true
```

以khadas运行，首个identity输出且进程存活才读寄存器。主控65秒、单读3秒、EOS等待30秒，首错停。
实际输出caps `video/x-raw, format=NV12, width=640, height=368, framerate=30/1`，
`Got EOS from element "pipeline0"`，`VENDOR_DECODE_EOS chain_count=600`。
活动时`vdec_status`为`ammvdec_h264_v4`、frame count=8、drop/fra err/hw err均0；
这是早期快照，非吞吐或逐帧正确性测试。

读取接口为`/sys/kernel/debug/aml_reg/paddr`：写入**一个地址token仅设置缓存地址**，
随后一次`os.read(fd,80)`触发一笔4字节物理读，避免EOF二次读取。
没有向该接口传第二个数值，没有用户主动MMIO写。依据固定厂商common_drivers
`4cfb128d36f8511b2db1bd13c08d5704347ded49`：
`drivers/memory_debug/reg_access/reg_access.c:34–51,84–149`，最终为
`ioremap/readl_relaxed`，不经过TEE代理。

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
| DOS基址 | 物理读fe32xxxx成功；DT为fe320000/10000 | 映射与word×4偏移一致，无换bank依据 |
| 功能时钟 | fclk_div2p5→vdec_p0_mux/div/gate→vdec_mux，799999988Hz，引用1；p1 gate关闭 | 旧候选CCF为799999987Hz，缺140/148原始值，不能证明物理门控一致 |
| 系统总线 | t7_dos/sys_clk为166666664Hz，活动引用1、EOS后0，044 bit1关闭 | 基线SYS_DOS同频率，缺故障窗口原始门控值 |
| CPU/APB门控 | t7_pclk_sys_cpu_apb、t7_a73pclk_cpu_apb，166666664Hz，软件引用0但hardware Y | t7_sys_pclk_sys_apb、t7_sys_a73pclk_apb均N；同一4c bit19/20，确定存在门控差异 |
| 共享AXI桥 | am2axi0/1/2均hardware Y | 三者也均Y，主线为critical；没有证据再开启未知NIC/AXI位 |
| VAPB | 活动vapb_sel为666666656Hz | 7.3基线vapb为499999992Hz；它用于VPU/采集，未找到VDEC依赖证据，本候选不调整 |
| VDEC域 | 活动on、EOS后off，genpd:0:vdec active→suspended | 旧候选GET4=on、reset/memPD=0，仍不充分 |
| NIC3 | 三个阶段均on | 旧候选GET39=on并持有父域，无新增域ID证据 |
| 其他DOS域 | HEVC均on（thermal），HCODEC均off；WAVE为基线KVM使用 | 7.3基线HEVC也on、HCODEC off；不能仅凭HEVC on认定H.264依赖HEVC |
| RAM/隔离 | secure genpd控制；活动memPD=0 | 本轮未读未知PWRCTRL ISO位，未观测BL31内部执行序列，不猜测补写 |
| TEE | 普通物理读在解码时及解码后均可用 | 排除每次读必须TEE代理；不能排除厂商早期安全配置的作用 |

时钟位定义见`drivers/clk/meson/t7.c:3733–3855,7129`；EN0→频率→secure域顺序沿用
前述离线审计。`drivers/media_modules/frame_provider/decoder/h264_multi/vmh264.c:11223–11238,11424`
中amvdec_enable先于reset/微码加载；同一decoder目录`utils/amvdec.c:72–87`
直接写GCLK、读改PIC，未找到SMC代读写。本轮未跟踪全部SMC，不能排除早期TEE配置的影响。

新增CPU/APB差异来自完整clock表：厂商active-clk.txt:368–369的Y，对照
mainline-idle-state.txt:444–445的N；这是硬件is_enabled列，不把零软件引用误作关闭。
厂商`t7.c:7105–7123,7191–7192`的SYS_GATE统一CLK_IGNORE_UNUSED；主线
`drivers/clk/meson/t7-peripherals.c:1285–1286`对应两gate flags=0，未被消费者持有时会关闭。
缺内部APB连线说明；保留这两个gate是受控假设，尚不能断言两者均为VDEC必需。

## 候选改动、构建与下次门禁

独立worktree `~/src/linux-7.3-vdec`、分支`vim4-vdec`，三个新提交：
`20d6e5ec44ec9`物理门控检查、`6bb00c29fa04e`绑定、
`a915603f5efb795afc72b5d92aa2c72e0e939a14`CPU/APB引用与DT；基于原c6fc96a…，没有更改正式源码树。
`aml_vdec_hw.c`复用首个clock provider的regmap，只读CLKCTRL；allow_t7_power默认关闭。

DT新增sys-apb/a73-apb引用，在显式power/单步诊断时通过CCF先于DOS时钟开启，
secure下电、释放NIC3后再释放。probe不开时钟，普通DT节点disabled，不把全局gate改critical。

在power_test的DOS读前、十三步第5步secure域/策略之后，记录044/04c/140/148原始值并核验：
SYS_DOS bit1、04c bit19/20开启，实际选中的p0或p1 gate bit8开启、source[11:9]=0、div[6:0]=0，
与本轮800MHz recipe相符；HCODEC高位及非选中路径不参与拒绝判断。
读失败或不匹配返回错误并下电，不进入后续DOS访问。正常open复用同一检查。
门禁修正CCF缓存频率不充分的缺口；若内部读仍失败，继续查安全初始化/隔离，不猜写。

Mac/VM实际C函数各12项通过，覆盖桥时钟生命周期、错误门控/选源/分频、读取失败回收且无DOS事务。
三个提交分别strict checkpatch为0/0/0。
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
Mac哈希、静态init、候选门禁、debug stamp已核验。
主仓离线全套232项，226通过、6项跳过；没有把跳过项记成硬件验收。

| 产物 | SHA256 |
|---|---|
| Image | 32a7367b265f829c89abe05488c5c7b8fb0a087dad7aa8f858161a80e65ddff8 |
| vim4.dtb | 871e931bb4d901c563ffa292577664a8bdeb2d6c2dcc32f4e93ada36165b59c9 |
| baseline-layout.dtb | b2e99a0efb250a102bc69585b89dc5c2871ae654b822eef928b8566bd0625564 |
| modules.tar.gz | 2e898d3b4182d8a4b7bd202ff856219255c7078da5850b7d3f624503d7eebe9d |
| config | fa46af2fa8213cd91d24dcad70b16a92b6b1b34f76394919951dce75cf5cadb6 |

新包等用户安排上板，每次重新抓取入场基线。
下次仍按probe→power→十三步→compliance→小H.264→1080p逐帧比较推进，任一步失败即停。
审阅CLKCTRL原始值；匹配也不能保证第9步安全。继续使用看门狗、一次性回退和180秒上限。

## 恢复、清理与证据

第二窗口UTC22:02:16–22:09:24，已释放双锁；恢复后300秒3840×2160运动H.265，
18306帧、59.9987fps，dropped/lost/freezes/PLI均0，最大回调36.6ms，无超过50ms。
HID keyboardDown/Up=1、绝对/相对鼠标、点击、滚轮通过。第一轮相同冒烟也通过。
这是原Wave5编码/HID恢复证据，不是新VDEC或非静音音频验收。

```text
build ID: eeddb005df059a850853876d52ef603aa1af192b
one-kvm / vim4-manager / vim4-wave5-monitor: active / active / active
UDC: configured; taint: 0; panic/panic_on_oops: 20/0
private module mounts: []; experimental modules: []
Wave5 SHA256: e88df353c730…; loaded build ID: 8e2dedd2579d…
BASELINE_RESTORED_SMOKE_CLEANED
```

恢复前后JSON逐项比较Image/DTB/extlinux/kernels.json/runtime-build.json五文件、
cmdline、原Wave5安装文件与已加载build ID，全部一致。UDC始终configured，无需PD init。
删除板上本轮fixture、数据库备份、插件registry、临时配置，保留systemd历史pstore。
无本轮SError/oops，两处pstore已归档；dmesg SHA仍为前次`6519f8f6…`旧dump。

原始证据在忽略目录`logs/vdec-vendor-live/`及`logs/vdec-vendor-live-second/`：
sample/window/UART日志、三个阶段完整clk/genpd、decode.log、前后JSON与pstore归档。
脚本另行归档。scp有root-owned registry.bin权限错误；所需clk/genpd、码流、decode.log均已保存，未重试窗口。

关键SHA256：sample.log `00038235396533d500984ba290db1391e7d28048d0f4b14adfd88770638c6365`；
fixture `449bf8a077c6b4a9d2b356c644f373042ee0c7a0842e34e15e3f15acddcce9f8`。

最后只保留当前候选：VM bundle含vmlinux/System.map/Module.symvers/原始四模块与
build stamp调试输入，共396MiB；Mac bundle约77MiB。删除本轮完整O目录、旧
`vim4-vdec-gclk-offline-bundle`、Mac旧gclk候选和已归档的vendor窗口辅助目录。
未删除其他任务的构建目录；VM磁盘收尾可用约63GiB。原始日志和历史pstore保留。
