# 2026-10-22：Wave521C GET_VPU_INFO 实机取证

第二轮 A；前置调查见[可行性](2026-10-22-vdec-feasibility.md)与[硬件明细](2026-10-22-vdec-hardware-audit.md)，
B 见[T7 离线准备](2026-10-22-vdec-t7-offline.md)。**本轮取到真实响应，但仍不能确认 T7 Wave521C 可解码。**
未增加 DEC caps、未注册解码节点、未运行任何硬件解码。没有安装 Image/DTB，也没有改磁盘上的模块。

## 改动与构建

VM 独立 worktree `/home/deepdream/src/linux-7.3-vdec`，分支 `vim4-vdec`，
基于 `e0346697f25035c7eaa77fa44641a54d6e31e327`。
诊断提交 `cc46f2e76e98f`（`media: wave5: report legacy firmware capability registers`），
仅改 `drivers/media/platform/chips-media/wave5/wave5-hw.c`，14 行新增。
在现有 `setup_wave5_properties()` 的 GET_VPU_INFO 成功之后，
对 `legacy_firmware` 打印已经读到的 DEF/FEATURE 及同一返回窗口的 DATE/REVISION/TYPE/ID。
没有发送额外 firmware command；必须在后续命令复用返回寄存器之前读取。

独立 O=`/home/deepdream/build/kernel-vim4-vdec`，从
`/home/deepdream/build/kernel-7.3-deploy-final` 复制 `.config`、`Module.symvers`、`vmlinux`。
该 vmlinux build ID 为基线 `3ed254bfa838ab50732fdce1c5134400a1663fd5`，
SHA256 `b1339bb93f3523173ce122fdbe34ff637fdfa8d530711b3faed344bd316a11dc`。
另一个历史目录 `kernel-7.3-final` 的 vmlinux build ID 不匹配，不能用来生成本次 BTF。

构建在 Mac heavy 锁内完成；没有构建整个 Image/modules：

```sh
/usr/bin/lockf -t 600 /tmp/vim4-heavy.lock orb -m vim4-build bash -lc '
make -C ~/src/linux-7.3-vdec O=/home/deepdream/build/kernel-vim4-vdec ARCH=arm64 olddefconfig modules_prepare &&
make -C ~/src/linux-7.3-vdec O=/home/deepdream/build/kernel-vim4-vdec ARCH=arm64 -j8 M=/home/deepdream/src/linux-7.3-vdec/drivers/media/platform/chips-media/wave5 MO=/home/deepdream/build/kernel-vim4-vdec/wave5 modules'
```

输出包含 `BTF .../wave5/wave5.ko`；`.BTF`、`.BTF.base` 均存在，配置与基线相同。
vermagic=`7.3.0-vim4kvm-uhd1+ SMP preempt mod_unload aarch64`。
诊断模块 SHA256=`dd9fa627af9b6f506c0f5eab7766aa13dcfb68cb0e332c7f5849d27a9a21cf57`，
build ID=`b72005e7b96bda7ea54829957a73c2a5ff614f05`。checkpatch：0 errors、0 warnings。

## 上板窗口与原始响应

临时文件 `/tmp/vim4-vdec-wave5-diag.ko`。完整窗口由 Mac 执行：

```sh
/usr/bin/lockf -t 600 /tmp/vim4-board.lock /usr/bin/lockf -t 120 /tmp/vim4-heavy.lock \
  python3 -u build/vdec-round2/window.py
```

等待音频任务释放锁后进入；同时持 heavy 是为了让编码/HID 回归不受编译干扰。
脚本与日志保留在忽略目录 `build/vdec-round2/`、`logs/kernel-edge/vdec-round2/`。
板端命令序列如下，每条子进程有 20 秒超时，编码 25 秒，SSH 整体 150 秒；
`finally` 卸载诊断模块、加载未改动的原模块、启动服务。没有硬件无响应重试。

```text
systemctl stop one-kvm
检查 /proc/*/fd：无进程持有 /dev/video*
modprobe -r wave5
insmod /tmp/vim4-vdec-wave5-diag.ko
读取新增 dmesg，检查只注册一个 encoder、无 decoder
modprobe -r wave5
modprobe wave5
恢复编码验证
systemctl start one-kvm
实际原生 HID 验证
```

dmesg 原样：

```text
[  277.752615] vdec fe310000.video-codec: GET_VPU_INFO product=0x521c name=WAVE version[120]=0x0000521c fw[118]=0x0003458e customer[140]=0x00000000
[  277.752633] vdec fe310000.video-codec: GET_VPU_INFO DEF0[124]=0x000d0908 DEF1[128]=0x08018000 FEATURE[12c]=0x0000020c
[  277.752639] vdec fe310000.video-codec: GET_VPU_INFO DATE[130]=0x0133f0de REVISION[134]=0x00027a7b TYPE[138]=0x00000000 ID[13c]=0x00000000
[  277.752739] vdec fe310000.video-codec: Added wave5 driver with caps: 'ENCODE'
[  277.752744] vdec fe310000.video-codec: Product Code:      0x521c
[  277.752748] vdec fe310000.video-codec: Firmware Revision: 214414
```

## 能力判读的边界

运行固件仍是 `/lib/firmware/amlogic/t7-wave521c-enc.bin`，952192 字节，
SHA256=`873103d7520d5cad737cfe4458a2891c065d566ff556a47ab735e60f27acf031`。
它与已有受限源码包 `build/jpeg-libs/multiEnc/vpuapi/chagall.h` 的转换结果一致；
header SHA256=`5c3d8bb687d95920a6f40fa7373c27312500574ed73f5047ad7498423c55c9da`。
参见[既有固件转换说明](2026-10-19-wave521-uhd.md#固件与复现依赖)，本轮不复制受限字节进仓库。

同包 `vpuapi/enc_regdefine.h:367–376` 与本次偏移一致。
`enc_driver.c:137–171` 读取 DEF0/DEF1/FEATURE；`:174–189` 却按 product ID
硬编码 HEVC/AVC decoder，`:60–68` 把 `0x5210` 与 `0x521c` 都映射到 PRODUCT_ID_521。
这是一份 encoder 库的通用属性初始化，既不检测 T7 解码熔丝，也没有成功解码证据。
`supportDecoders` 不能当作这颗集成实例的能力报告。

当前 wave5 的 W521 定义把 DEF1 bit 3/2 作为 AVC/HEVC decoder、bit 1/0
作为 AVC/HEVC encoder。本次 `0x08018000 & 0xf == 0`，四个位全为零。
这套位定义不能直接套到本固件：已经正常工作的两种编码器也会被报告为不支持，
基线为此已有 `encoder_mask` override。不能据零位宣布硬件无解码，也不能用
库里的硬编码反向宣布有解码。FEATURE 的 10bit **编码**位同样不是 decoder 存在位。
还没有找到能对 firmware revision 214414、hardware revision 162427
解释独立 AVC/HEVC 解码开关的可靠厂商定义。

**A 的结论为未证实。** 用户要求的“确认具备后才准备 DEC 候选”条件尚未满足，
因此没有增加 T7 DEC flags 或 decoder capability override；没有可上板的 Wave 解码候选。
下一步需要对应版本的 521C 集成配置说明/decoder firmware API，或厂商对该实例的明确确认。

## 恢复证据与限制

恢复原模块后运行两条管线（H264/H265 分别替换 `$codec`），每条 25 秒超时：

```sh
GST_PLUGIN_PATH=/usr/lib/vim4-kvm/gstreamer-1.0 \
GST_REGISTRY=/tmp/vdec-round2-gstreamer-registry.bin \
gst-launch-1.0 -q videotestsrc num-buffers=60 ! \
  video/x-raw,format=NV12,width=640,height=480,framerate=30/1 ! \
  v4l2${codec}enc ! ${codec}parse ! filesink location=/tmp/result
```

实际结果：H.264 与 HEVC 均为 640×480、`nb_read_frames=60`；
`ffmpeg -v error -i ... -f null -` 两条均成功。这是原编码功能恢复检查，
ffmpeg 此处为软件解码，不是硬解验收；未测 1080p/4K 解码性能。
新建私有 GStreamer registry 时出现现有插件依赖缺失/属性安装提示，管线仍正常结束；
kernel 窗口无 timeout/Oops，唯一新 taint 是外部模块标记。

窗口结束输出与随后只读复核：

```text
ORIGINAL_MODULE_RESTORED 394dcc4fb305b48ce7e69756c45b1cf5ffa2665e
/sys/kernel/notes 3ed254bfa838ab50732fdce1c5134400a1663fd5
/sys/class/udc/fdd00000.usb/state configured
systemctl is-active one-kvm vim4-manager: active / active
native-hid: keyboardDown=1 keyboardUp=1 absoluteMouse=true click=true wheel=true
relativeBefore=[0.6999959309895833,0.5999891493055556]
relativeAfter=[0.7099039713541667,0.6117332175925926]
ENCODING_AND_NATIVE_HID_RESTORED
```

磁盘 `wave5.ko.xz` SHA256 仍为
`615795a99dbcecb846a21478fb1e8770a997142ef9a0c8f7d309ffa63d8ad8fa`。
只有 `t7-vdin-test`、`C&M Wave5 VPU encoder` 两个视频节点。
诊断模块由独立 MO 构建，加载产生 `TAINT 4096`（out-of-tree），卸载不能清除此内核标记。
运行内核/原模块/固件/服务/USB 功能已恢复；**不能声称运行时 taint 也恢复为零**。
本轮没有为清 taint 重启共享板子，下一次正常基线重启会清除。

## B 提交与本轮离线检查

同一 `vim4-vdec` 分支，未推送，worktree clean：

| 提交 | 范围 |
|---|---|
| `134d542abdd7c` | T7 decoder binding、追加 clock ID、MAINTAINERS |
| `d71c3a63ac894` | VDEC/HEVCF/HEVCB CCF provider |
| `fd9cd287e0e19` | 带 probe 拒绝的 T7 平台、PM、DBUS 分支 |
| `7bd0f8328e8a4` | disabled T7 VDEC DT 节点 |

CCF object、`amlogic-t7-a311d2-khadas-vim4-hdmirx-test.dtb` 和独立 MO 的
`aml-vdec-drv.ko` 编译成功，包含 BTF，无编译 warning。四组提交边界的 strict
checkpatch 均为 0 errors / 0 warnings / 0 checks；新 binding 的 `dt-doc-validate` 通过。
没有打包或部署 B 产物。[B 记录](2026-10-22-vdec-t7-offline.md)列明实现与剩余缺口。
主仓库按要求运行 `python3 -m unittest discover -s tests -p 'test_*.py'`：
169 tests、OK、skipped=5；检查的是当时含其他任务改动的工作区，不是 DOS 硬件测试。
主仓库仅更新本任务记录及索引，未提交；部署版本锁没有为本任务变更。

## 用户在板边时的清单（风险递增）

1. 只读复核 build ID、服务、UDC 和固件哈希；核对本记录及 B 的阻塞项。
2. 如需干净 taint，协调其他任务后持 board 锁正常重启基线，再验编码/HID。
3. Wave 路线先补齐对应版本的解码能力证据。确认后才能离线增加 DEC 候选，
   先验证 probe/节点/格式枚举，再准备单实例、8 对齐尺寸、短 AVC/HEVC 码流。
   两个硬件实例共用 Wave 资源，测试时停止 one-kvm 并排除 `/tmp/vpu_mutex.map` 的厂商用户。
   每次 decode 最多 10 秒；失败先检查进程能否退出、DMA 是否静止，再卸载；不反复重试。
4. DOS 路线必须先完成 secure firmware、DMA timeout 所有权处理，以及 platform core
   单电源域自动上电与厂商时序的衔接，才可移除 B 的 probe gate。
   首次上电/DBUS/reset 测试需要用户可按 RESET；disabled DT 或 gate 仍在时没有硬解可测。
   probe gate 不阻止 platform core 的自动电源域附着，不能以改为 okay 来做“只读 probe”。
   不访问未上电的 DOS，不同时运行 HCODEC/JPEG，不申请共享全局 reset 或其他 mailbox IRQ。
5. 两条路线任一能稳定启停后，再持 board+heavy 锁做已知帧的 MD5/PSNR、
   v4l2-compliance、1080p/4K 性能及错误流/关闭回收；每个窗口结束恢复上述基线并验证。
