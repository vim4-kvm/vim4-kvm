# 2026-10-30：kbase候选首窗加载门禁失败

结论：候选完成RAM启动、创建/dev/mali0，但出现新的workqueue/hrtimer内核WARN，
**加载门禁未通过，取日志后立即正常回5.15**。没有现场改驱动或DT、没有继续API/性能负载。
运行时助手也拒绝该候选，HDMI/gadget服务未启动；本轮没有HDMI＋Wave5回归通过结论。
计划与离线候选见[维护方案](../gpu-kbase-7x.md)、[r2集成](../gpu-kbase-integration.md)。

## 入场、版本和一次性启动

主仓在独立vim4-kvm-kbase-r2工作树。开始时两把锁均无持有者；按board→heavy顺序
以lockf持有整个窗口，首次SSH确认已回5.15，串口无其他持有者后才stage/reboot。
未操作HDR工作树。板端UTC为2026-10-31 03:47–03:52，Mac本地日期为10月30日。

- 5.15：5.15.137-vim4kvm-hdrdual6，r44p0-01eac0 UK11.39；blob SHA256
  536ee80c17dc5c54e7c6ff029ca43270da8efc3fdc5b3aeb263f364419368494。
- 7.3：正式f71b5c6289cb基线，build ID a3572361d542e5505bd159ad8a327cf364fe25f3，
  Image SHA256 9daea7a17e228cb5ef93b6b9cc926ccce43ec3b8eafb1b22aee447fdcfcb7000。
- 外部模块：r2 final，SHA256 f41e1573dba86b5d5054190629d69ef5c451818a8097b2f1ceec0d0bfefdc4b8。
  核验同次2351个原模块哈希，加入extra/mali_kbase.ko后重新depmod，保留BTF。
- 候选DTB SHA256 393c32e053572395b89ce4eed04ba6791ce2d4acfa4d865dc2c1de7beee79149，
  是保留display-m0副本，只换compatible与删除mali-supply。默认/boot/edge/vim4.dtb未改。
- 独立目录/var/lib/vim4-kvm/kbase-once/a3572361d542e5505bd159ad8a327cf364fe25f3，
  静态PID1复用display-once-init合同，检查build ID并绑定只读完整私有模块目录后exec systemd。
  没有覆盖/lib/modules。未打包或上传新blob。
- 串口实际节点/dev/cu.usbserial-1100，921600。匹配Hit SPACE中止自动启动，发送
  `sysboot mmc 1:2 any ${pxefile_addr_r} /var/lib/vim4-kvm/kbase-once/a3572361d542e5505bd159ad8a327cf364fe25f3/extlinux.conf; reset`。
  没有saveenv、默认启动项/默认initramfs写入。候选额外blacklist panfrost。

## 三栈API与性能

| 项目 | 5.15 libmali（本轮） | 7.3 kbase＋libmali（本轮） | 7.3 Panfrost（历史，非本轮重测） |
|---|---|---|---|
| 内核设备 | Mali-G52 | ID识别7.4.0 r1p0，Probed as mali0；加载有WARN | Mali-G52四核 |
| EGL / GLES | ARM EGL1.5 / GLES3.2 | 未查询，加载门禁已失败 | EGL1.5 / GLES3.1 |
| Vulkan设备API | Mali-G52 1.3.231 | 未查询 | Mesa26.2.6为1.0.354实验；系统25.2.8无ICD |
| CL device / OpenCL C | 3.0 / 3.0 | 未查询 | 私有Rusticl 3.0 / 1.2；系统无CL平台 |
| GLES FPS | 608.642 / 596.417 / 611.953，均值605.670 | 未测，无法配对 | 旧三轮均值233.730，不能与本轮直接比 |
| DMA compute主机submit_wait，ms | 1.910 / 1.848 / 1.938；三轮逐字校验PASS | 未测，无法配对 | 旧中位数8.038，不能与本轮直接比 |
| 有界clpeak | 45秒预算超时，已输出部分带宽 | 未测 | 旧120秒全程序预算超时 |

Panfrost列来自[三栈验收](2026-10-30-gpu-acceptance.md)，不是本窗新的第三次启动。
全部本轮5.15设备查询明确为真实Mali-G52，无llvmpipe/lavapipe。完整扩展原文保留在vendor.json。
GLES使用r2 direct前缀、同一/var/tmp/gpu-board-20261030/gpu-probe-gbm、
/dev/dri/card0、512² RGBA FBO、128次循环，每轮5秒，像素179/128/128/255、gl_error=0。
VK/CL使用纯ICD模式；DMA沿用同目录mali-dma-probe及SPIR-V，heap-codecmm，
24,883,200字节、6,220,800 uint逐字校验。这里的数值仍是主机submit_wait，不是GPU独立执行时间。
未锁CPU/GPU频点或暂停产品后台服务，温度与频点未配对记录，故只记录基线，不宣称性能追平。

clpeak的45秒是全程序预算；日志停在global bandwidth float16输出期间，
不能称为map死锁，更不能把历史5.15完整clpeak通过替代本轮超时。
每个命令经bounded包装，超时TERM后5秒KILL进程组；全轮vendor另加150秒timeout。

## 新故障及停止理由

串口与dmesg表明：

1. 4.226s，IRQ JOB/MMU/GPU名称查找各报ENXIO。后续GPU识别与probe成功，
   所以不能把这三条日志单独写成probe返回失败。源码依次尝试大写、小写及索引，
   默认DT的小写job/mmu/gpu仍可命中；下轮应避免已知名称差异产生误导性报错。
2. 4.227s，workqueue.c:5938 WARN，mali_mmu0未指定WQ_PERCPU/WQ_UNBOUND，
   内核补为WQ_PERCPU；调用栈kbase_mmu_as_init→kbase_device_misc_init。
3. 4.228s，hrtimer.c:1944 WARN，调用栈kbase_vinstr_init→hrtimer_setup→__hrtimer_setup。
   离线复核确认7.3此处WARN_ON_ONCE(!fn)；r1兼容宏把旧hrtimer_init变成带NULL回调的
   hrtimer_setup，而DDK在下一行才赋function。编译通过没有验证这个运行时合同。
4. job fault workqueue名称超长被截断。4.230s仍输出Probed as mali0；采集到字符设备
   /dev/mali0和mali_kbase已加载记录。该事实不抵消上述新WARN，taint含W/O。
5. 候选SSH地址变为192.168.50.162；使用既有VIM4公钥与原host-key别名取得dmesg后重启。
   未关闭host-key校验。根文件系统vim4-board-runtime报No validated VIM4 platform for this kernel，
   HDMI、gadget和其依赖服务失败；说明还缺实际rootfs与候选内核的运行时匹配预检。

一见启动错误即停止负载路径；未运行7.3 EGL/GLES/VK/CL、dma-buf、五档devfreq、
thermal读回或HDMI/Wave5并发。没有在板上改任何驱动、DT、服务助手来绕过门禁。
下一轮前须离线修正真实hrtimer回调注册与workqueue标志/命名，完成内核接口审查，
并核对实际部署运行时助手支持/哈希，重新打包；本记录不包含修复或再次上板授权。

## 回退和最终状态

通过SSH正常systemctl reboot，按原默认返回5.15.137-vim4kvm-hdrdual6。
one-kvm、vim4-kvm-hdmi、vim4-kvm-gadget、vim4-manager均active，UDC configured。
六个入场保护文件的SHA逐项相同：extlinux.conf、uEnv.txt、edge/Image、edge/vim4.dtb、
5.15 hdrdual6 vmlinuz及initrd。约5分钟硬件窗口后释放双锁。
未发HID、未测声音、未ptrace视频进程、未写PWM或调电压；未推送blob。
独立候选目录留作取证，不被默认项引用。

原始本地证据：忽略目录logs/kbase-window/中的vendor.json、vendor-run.log、before.txt、
boot-uart.log、boot-control.log、candidate-state.txt、return-uart.log和final.txt。
VM打包脚本和候选归档位于~/build/kbase-board-window；主仓忽略目录build/kbase-window保存控制脚本。

主仓离线unittest：315项、13项因独立工作树环境跳过、无失败；构建入口语法检查和
仅允许候选DT/试验记录的源码差分门禁通过。内核分支仅新增试验记录，提交9d2bd227f58fa，
没有把已失败候选修成“通过”或推送任何blob。
