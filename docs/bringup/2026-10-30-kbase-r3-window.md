# 2026-10-30：kbase r3加载门禁通过，EGL设备门禁失败

结论：r3的workqueue/hrtimer WARN已在本次启动消失，/dev/mali0和UK11.39正常；
HDMI、gadget、One-KVM及manager均active。但首个GBM/FBO EGL/GLES设备探针退出2，
未返回设备信息。按用户门禁立即取证并正常回5.15，**不继续其他API、性能或并行负载**。
没有现场改驱动、DT或用户态库，不将/dev/mali0存在当作API/性能验收。
离线修复及准备合同见[r3修复](../gpu-kbase-repair.md)。

## 独占、产物与助手同步

Mac日期10月30日，板端UTC 10月31日04:07–04:13，约6分钟。
开始时锁文件无持有者，按board→heavy的lockf顺序持有整个硬件窗口，先确认板子在
5.15.137-vim4kvm-hdrdual6、四服务active、UDC configured。结束验证后才释放双锁。
未操作HDR工作树，主仓原工作树保持main。

- 内核f71b5c6289cb，7.3.0-vim4kvm-uhd3+，build ID a3572361d542e5505bd159ad8a327cf364fe25f3。
  2351个原模块逐个SHA核验，加入r3 extra模块后depmod，由静态PID1检查build ID并绑定只读完整私有模块集。
- 模块SHA256：4ff4bbf3490d34a3f5f59e3b8b92f33c6199f6ae0d7dcf533ec1f1f26163359d。
- Image SHA256：9daea7a17e228cb5ef93b6b9cc926ccce43ec3b8eafb1b22aee447fdcfcb7000。
- 候选DTB SHA256：393c32e053572395b89ce4eed04ba6791ce2d4acfa4d865dc2c1de7beee79149。
- runtime-files.json SHA256：2166af94c5bb956b6e74b1d6a8f74e64d14240c961d523447ae68b8b63dd74fa。
  本轮保存了板上旧board-runtime全文，确认仅接受uhd1，不接受uhd3，消除此前仅凭包版本推断的边界。
  五个助手逐文件备份内容/模式/属主与原先是否存在，校验封存SHA后暂时更新；check-kernel返回mainline。
- 新目录/var/lib/vim4-kvm/kbase-r3-once/a3572361d542e5505bd159ad8a327cf364fe25f3，
  没有覆盖上轮私有目录或系统模块。RAM sysboot选择mmc 1:2的该目录extlinux.conf，
  不写saveenv或默认启动项，默认Panfrost DT与5.15均不修改。

## 加载门禁与失败位置

完整dmesg在初次取证及EGL失败后均无WARNING/BUG/Oops/Call trace；
只有预期的out-of-tree模块taint提示，不能称完全无taint。
4.400s报告r44p0 DDK，4.439s识别GPU arch7.4.0 r1p0，4.444s输出Probed as mali0。
大写IRQ误报、队列默认标志WARN、timer NULL回调WARN及长队列名提示均未重现。
/dev/mali0为字符设备10:262，模块版本r44p0-01eac0 (UK version 11.39)。
四服务active，UDC configured；这只证明启动/绑定，不是视频帧验收。

通过加载门禁后仅执行：

```sh
python3 /var/tmp/kbase-r3-window/run.py --graphics direct -- \
  /var/tmp/gpu-board-20261030/gpu-probe-gbm 0 /dev/dri/card0
```

耗时0.234秒、退出2、stdout/stderr均空，输出未到EGL vendor/设备版本行。
此时/dev/dri只有card0，没有Panfrost renderD节点。既有探针在DRM open、gbm_create_device
或eglGetPlatformDisplayEXT入口缺失时均可能无诊断退出2；现有日志不足以区分这些分支。
不能直接断言eglInitialize失败，更不能断言Vulkan/OpenCL不可用。
未换节点、预加载方式或blob重试，未ptrace探针或视频进程，立即取dmesg/服务日志回退。

下一轮前应离线补足探针分阶段错误与errno，再审查libmali GBM对显示DRM节点/后端的需求，
以及能否在不依赖Panfrost render节点的情况下建立上下文；本轮没有实施或验证这些后续修复。

## 三栈API与性能

| 项目 | 5.15 libmali，本轮 | 7.3 kbase＋libmali，本轮 | 7.3 Panfrost，历史 |
|---|---|---|---|
| EGL / GLES | ARM EGL1.5 / GLES3.2，Mali-G52 | GBM/EGL设备探针退出2，无设备信息 | EGL1.5 / GLES3.1 |
| Vulkan设备API | Mali-G52 1.3.231 | 未查询，按门禁停止 | Mesa26.2.6为1.0.354实验；系统Mesa无ICD |
| CL设备 / OpenCL C | 3.0 / 3.0 | 未查询 | 私有Rusticl 3.0 / 1.2，系统无CL平台 |
| GLES FPS三轮 | 609.266 / 616.805 / 613.862，均值613.311 | 未测 | 旧均值233.730，非本轮配对 |
| DMA compute submit_wait，ms | 1.951 / 1.875 / 2.020，均逐字校验PASS | 未测 | 旧中位数8.038，非本轮配对 |
| CL kernel latency | 81.65µs，约5.89秒完成，退出0 | 未测 | 无同子集样本 |
| CL compute-sp float | 101.73 GFLOPS，子集约15.30秒完成，退出0 | 未测 | 无同子集样本 |

Panfrost列仅引用[旧三栈验收](2026-10-30-gpu-acceptance.md)，没有本轮第三次启动。
本轮5.15查询为真实Mali，未使用llvmpipe/lavapipe。完整扩展保留vendor.json。
GLES使用与候选完全相同的direct前缀、card0与GPU探针：512² RGBA FBO、128次循环、
每轮5秒，pixel=179/128/128/255、gl_error=0。
DMA仍为24,883,200字节/6,220,800 uint、heap-codecmm，沿用gpu-acceptance SPIR-V；
submit_wait为主机等待口径，不是GPU独立执行时间。
未锁频、未记录配对热状态，且候选没有负载样本，因此**未形成性能配对，不计算追平比例**。

clpeak仅选择--kernel-latency（30秒预算）和--compute-sp（90秒预算），platform/device均0，
使用纯ICD模式，未执行旧的完整全项目测试。SP向量float2/4/8/16依次为
101.69/101.35/101.11/95.40 GFLOPS；超时包装保留TERM后最多5秒KILL。
后续dma-buf互操作、五档devfreq、thermal绑定及HDMI＋Wave5并行均因设备门禁失败而未执行。

## 回退与原状态恢复

SSH正常reboot回5.15.137-vim4kvm-hdrdual6；五个助手按原内容、权限、属主恢复，
原先不存在的vim4gpu.py移除，恢复脚本逐项SHA验证通过。
首次回退检查One-KVM为inactive，其余三个服务active；显式启动One-KVM后重新逐行确认
one-kvm、vim4-kvm-hdmi、vim4-kvm-gadget、vim4-manager全部active，UDC configured。
不能用active的子串计数误把inactive算作通过；最终断言采用完整行相等。
六个保护文件（extlinux.conf、uEnv.txt、edge Image/DTB、5.15 hdrdual6 vmlinuz/initrd）SHA与入场逐项相同。
候选目录仅留作取证，不被默认项引用。无HID发送、声音测试、PWM/电压写入或blob推送。
产品服务本身有自动音频采集日志，本轮没有创建声音测试或播放声音。

原始证据在主仓忽略目录logs/kbase-r3-window/：before.txt、vendor.json、vendor-cl/、
boot-uart.log、uart-gate.txt、gate.txt、candidate.json、candidate-final.txt、final.txt、
services-restored.txt、runtime-restoration.json.txt。控制/备份脚本在build/kbase-r3-window，
VM封存完整包在~/build/kbase-r3-board-window。
GPU探针SHA为20efbc206a9f51267ba5a0897a7e38f2d5f2e89e078d0b784615124b7a2be078；
DMA探针2448e9e26b3ae353430b56732a9f2c35095355442f0b8820b744b390f9a78c8f；
clpeak为70b1b67912dc6b8c3bf720977137dee0d58d05d965497f0513c49ff94cd7c735。

主仓离线unittest：317项、13项环境跳过、无失败；git diff --check通过。
内核分支本轮只新增试验记录，提交481c465abf946，没有更改DT或驱动实现。
