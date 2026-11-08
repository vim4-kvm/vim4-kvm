# kbase 产品与维护合同

本页管 kbase 移植、打包、用户态隔离和验收；当前身份、默认项以[主线入口](kernel-mainline.md)为准。
最小产品烟测已通过，不能扩大到完整 CTS、功耗或新增互操作。
导航：[维护](#来源与更新路线)、[生命周期](#运行时与平台合同)、[部署](#内核选择与打包)、[许可](#用户态与许可证)、[边界](#验收边界)。

## 来源与更新路线

DDK、内核与 blob 的锁定值以[构建器](../packaging/kbase/build.py)为准，
补丁责任与顺序见[series](../packaging/kbase/series)；不向正式内核并入整棵 DDK。
内核 API 适配集中兼容层，T7 平台层独立，heap exporter 不混入 DDK。
新包须先核对 GPU 型号、JM 协商及全部 ioctl 布局与语义，
不能改版本常量伪装兼容，也不能用别的 GPU 或 CSF 版本作为 G52 兼容证据。
公开更新包未下载、构建或证明与现有 blob 匹配；旧检索仅见[离线记录](bringup/2026-10-30-kbase-offline.md)。

每次升级先固定完整内核构建，再按主题重放并审查构建器锁与白名单差异，不绕过检查。
核对 UAPI 字节与 payload，完成严格构建、modpost、语义检查、宿主模型及主仓测试。
语义变化不能藏在同名宏中；DT 生成器同步更新并保留 phandle 和风扇 map。
只验证过既定配置，不能承诺所有中间内核版本；页迁移未支持，不得启用编译占位路径。
DMA/MMU/PM 变化须重新安排移植验证，不能承诺零维护。

## 运行时与平台合同

timer 在初始化时绑定有效回调，栈 timer 使用对应接口；等待返回后先取消，再判结果、销毁或重启。
bound workqueue 保留 CPU 绑定、优先级及并发语义；API 改名不是语义移植。
dma-fence 适配保留锁和重复 signal 错误。OPP 遍历全部出口归还引用，
负计数不用于分配；可选 IRQ 立即传播延迟 probe。
实现与实际调用检查见[运行时补丁](../packaging/kbase/0005-runtime-api.patch)及[检查器](../packaging/kbase/check-semantics.py)。
宿主模型不证明真实 IRQ、调度或内存压力。

平台通过标准电源域供电，不直接发私有 SMC；先持域、开 bus、释放 reset，再由 DDK 管 core，
终止逆序回收。持域避免厂商已知的空闲 reset 问题；内部 shader gating 不等于外部域节能或系统睡眠。
保持启动 PWM 电压，不推断闭源固件绝不调压；无可信板型分档表不试电压。
r5 同时修正 PWR_OVERRIDE1 初始化与 DMA coherent 路径，[r6](bringup/2026-10-31-kbase-r6-window.md)才单独证明 override 必要；不能把同一轮联合修改都归因于单项。

默认 governor 必须复现已验厂商策略，不用 performance 成绩冒充默认能效。
softdep 须先加载 governor，避免异步 probe 与模块请求互等，见[策略补丁](../packaging/kbase/0008-t7-devfreq-policy.patch)。
thermal 模拟只证明限频路径，结束清除模拟并核对；不等于真实过热或功耗通过。
dma-buf 保留 SG DMA 地址、reservation 锁及 attach/CPU access 配对；
显式 fence 编译通过不代表完整 DRM 隐式同步、非连续内存或外部 IOMMU 已验。

## 内核选择与打包

Panfrost 和 kbase 由 DT 互斥，通过重启切换，不能热解绑；黑名单不能替代 DT 互斥。
从完整保留 DTB 派生，保留 HDMI、USB、MAC、风扇与其他配置，不拿通用板 DT 覆盖运行 profile。
构建参数和输入验证见[构建器](../packaging/kbase/build.py)帮助。
输出模块只是完整内核包的附加片段，须合入同次 Image 和模块集，再生成 initramfs。
保留 manifest 中全部身份检查；vermagic 相同不足以避免 BTF 或符号混装。

运行时按实际绑定 GPU 选私有用户态，视频后端独立选择；不能仅凭内核 release 选 Mesa 或 blob。
共用[启动器](../packaging/kbase/run.py)验证 UK 与 blob，Panfrost 清理继承环境。
已知内核路线检查不证明 build ID、完整模块或服务可用，须核对运行助手与收据逐文件哈希，
不能只更新源码或修改收据。
集成证据见[正式集成](bringup/2026-10-31-uhd5-main-integration.md)。

## 用户态与许可证

不覆盖系统 Mesa、EGL、GLES 或 GBM；逐进程选择 ICD 和私有图形前缀。
现有 blob 缺少 GLVND EGL vendor 入口，不能用 JSON 假装支持；未实现桥接层。
GBM 须选实际显示节点，kbase 不产生 Panfrost render node；库导出 GBM 也不证明 X11 支持。
产品推荐用 Vulkan/OpenCL ICD；需要 GLES 的独立进程用私有 EGL/GLES/GBM 前缀，不选 GLVND shim。

保留源码作者、版权和许可证；分发修改模块须提供相应源码、补丁与构建材料。
blob 为专有组件，公开可下载不等于获准再分发，通用 Arm EULA 也不自动授权第三方构建。
发布镜像前核对随附许可或供应商授权，blob 不进入 Git 或公开模块产物。

## 验收边界

[默认策略实测](bringup/2026-10-31-kbase-r11-policy.md)通过 API 基本执行、内存、默认策略性能、
模拟限频及服务级视频并发；恢复 coherent 声明的负向 DT 曾触发 MMU fault，已否决。
早期 performance 和失败候选成绩只属于各自记录，不能替代默认策略门禁。
正常候选回退通过，负向故障后的 DHCP 原因未定。

完整 CTS、真实热闭环、系统睡眠、外部域节能、故障恢复和内存压力仍欠独立证明；
实际 scanout 与 GBM 到编码器属于新增互操作，handle 导入成功不能替代像素与同步验收。
新窗口先核对匹配构建与回退，再测 API、同合同 heap、默认策略性能及视频并行；
普通计时关闭 trace，cache/频率归因另采。跨重启物理地址不能视为同一 buffer。
首错停止，不继续跑分；超时、恢复和占板遵守[窗口规范](board-window.md)。
