# 内核与驱动

## 架构与约束

内核身份、配方及Mainline与Vendor布局见[主线](../kernel-mainline.md)。
无线固件/配套模块见[源码锁](../../packaging/kernel/sources.toml)；PHY trap固件根因未明，P2P缺真实对端协商/传输验收。
风扇分Linux温控与U-Boot上电测试，后者早于Linux；改温控不会取消上电测试。
[安静风扇/验证入口](../bringup/2026-10-20-edge-quiet-fan.md)、[U-Boot禁用/验证](../bringup/2026-10-17-uboot-quiet-fan.md)。
[标准thermal迁移与待验清单](../bringup/2026-11-05-fan-thermal.md)：DT档位与标准trip调参，旧故障输出/限速不再保留，尚未上板。
IR/按键及NOR与eMMC引脚限制见[设备树记录](../bringup/2026-10-21-edge-ir-keys-spinor.md)。
厂商VDIN、vfm_cap、Wave521和CRG驱动见common_drivers；新板DT/安装按[内核](../kernel.md)，保留stock回退，不替换/lib符号链接。
模块替换、initramfs及整包操作均按该文档；构建成功不证明启动、温控、采集或USB通过，硬件回归须独占。

## 按任务读取

- [构建、安装与回退](../kernel.md)、[VM工作树](../workspace.md#构建)、[部署门禁](deployment.md#内核开发流程与部署门禁)。
- [Wi-Fi、WPA3及P2P证据](../kernel-mainline.md#相关记录)。
- [内存、拷贝与锁调试](../memory-copy-audit.md)、[PWM/CCF 锁拓扑与修复边界](../pwm-clock-locking.md)。
- [电压、温控、空闲与挂起差距](../parity/platform.md)、[板测清单](../parity/platform-pm-board-checklist.md)。
- [kbase 产品合同](../gpu-kbase-7x.md)、[GPU 候选维护](../gpu-maintenance.md)。
- [HEVC 接口与固件参数证据](../bringup/2026-11-05-hevc-interface-review.md)。

## 内核驱动开发与验证

- 整个内核树按 Linux process 及对应子系统规范实现；每个改动先明确验证方法，实际运行并保存原始输出才标记已验证。短期不向上游投稿，不准备投稿材料或对外发送邮件、补丁。
- 所有驱动不新增 Python/宿主 mock 测试，现有项目测试按[全树清单](../bringup/2026-11-05-kernel-test-migration.md)分批迁移；未确认风险保留待确认。纯逻辑迁 KUnit；接口语义用 V4L2 compliance、ALSA、DRM 等标准接口及带流测试；像素与数据用标准样本；时钟、电源与 DMA 停机用实板。故障注入只用内核标准机制且限调试配置，不能模拟整套 vb2/V4L2/DRM/ASoC。上游源码生成工具保留，板端工具迁出内核树。
- KUnit 直接调用实际生产函数，必要时按 visibility 接口暴露 static 函数；使用各目录 `.kunitconfig` 在 arm64 QEMU 实际运行。不得抽取源码、拼假框架或用宿主断言调用顺序替代。为可测性重构时保留执行顺序与硬件访问时序；必须改变行为时另作提交，并记“需实板回归”。[vdec 清单](../bringup/2026-11-05-vdec-test-migration.md)与[结果](../bringup/2026-11-05-vdec-kunit-results.md)为记录范例；删除测试不等于替代验证通过。
- 提交说明写清改了什么、为什么、怎么验证，并带 Signed-off-by；checkpatch 对每个提交的 `git format-patch` 输出运行，只查 diff 会漏掉提交说明和签名。
- 改动范围提交前完成 strict checkpatch、W=1 和有效 sparse、模块/内建构建、改动头文件 kernel-doc；smatch 可用则运行。改 binding 时先 schema 后板 DTB 检查。工具缺失、跳过或失败不得记通过。
- 提交单一目的且可独立构建；binding 先于其驱动/DTS 使用者。作者、版权及来源按[代码规范](../code-standards.md)保留。
- H.264/MPEG-2 节点使用 stateless，HEVC 使用 stateful，JPEG 独立。HEVC 内核只消费固件元数据，不解析码流；确需解析先报告，不新增私有用户态 ABI。
- 标准码流、调试候选与同板性能按[解码验收合同](../vdec-validation.md)，入口复用 vdec-window；锁定码流在宿主校验，板上不下载，未运行与超时单列。

## 错题

| 触发 | 做法 | 验证 |
|---|---|---|
| debugfs audiobus读触发abort/重启 | 只读也访问未上电MMIO，dump不受head限制；诊断持板锁，只读已审阅具名状态，不盲扫 | [事故](../bringup/2026-10-25-audiobus-read-abort.md) |
| 板NFS loopback挂自己卡死、RESET后无日志 | 服务端放Mac/VM，冻结用docker pause或VM内nft丢包 | [NAS/USB](../bringup/2026-10-18-nas-storage-usb-disk.md) |
| checkpatch记通过、提交却缺说明和Signed-off-by | 只对diff跑漏查提交信息；对format-patch输出跑并保存原始结果 | `git format-patch -1 --stdout <提交> \| scripts/checkpatch.pl --strict -` |
| make C=2成功但未跑sparse | 旧版被警告跳过；固定工具、查实际CHECK行，拒绝不可用日志，不只看退出码 | [门禁](../bringup/2026-10-31-hdr2-uhd4-gate.md) |
| 切换配置后 M= 仍复用旧模块对象 | 跨配置先清理自身目录模块产物，确认实际 CC/CHECK，并检查配置敏感导出/注入符号；退出码不能证明对象属于新配置 | [HDMI RX 迁移](../bringup/2026-11-05-hdmirx-kunit-results.md) |
| Bifrost回边补丁主机通过、G52挂起 | 分支偏移误算前块而重置计数，须加layout回归；CFG和静态统计不能替代最终编码与硬件验证，短负载全帧正确且无新增timeout才测FPS，出错即否决并正常重启 | [板测](../bringup/2026-10-30-gpu-repair-window.md) |
| 根目录解包破坏/lib，动态程序失效 | 安装保目录符号链接、留stock启动项，按工具参数 | tools/kernel-install.sh、[内核](../kernel.md) |
| 换Image后模块BTF错、SSH失联 | 分离BTF依赖原vmlinux类型ID，release/vermagic不足；同次构建完整模块、核实际加载，不关BTF掩混装 | [DDC](../bringup/2026-10-19-hdmirx-ddc.md) |
| 回5.15网口carrier正常却不收包 | 热解绑/重绑实测Oops，保留串口、优先正常重启，不作通用恢复 | [恢复限制](../bringup/2026-10-19-hdmirx-ddc.md#恢复与限制) |
| USB重绑后关hidg触发list_del panic | f_hid须同时修队列生命周期与独立cdev，只修前者仍崩；保留应用保护，重启进新Image才生效 | [HID修复/提交](../kernel.md#hid-重新绑定)、tools/hid-rebind-check.py |
| SET_ADDRESS触发double add | 仅UDC状态检查不足；登记gadget.irq使解绑前同步中断，锁内查回调开关，禁用时不补STALL/处理新SETUP；继续消费旧完成事件，不重置硬件仍持有请求链 | common_drivers/drivers/usb/crg/test_setup_events.py、[CRG](../kernel.md#crg-usb-控制端点重连) |
| FUSE上inotify使守护进程挂死/僵尸 | 厂商非标准opcode，旧go-fuse不回复；未知opcode须回错误，空成功会越界；卡死用连接abort清理 | [版本/恢复实测](../bringup/2026-10-18-nas-storage-usb-disk.md) |
