# 2026-10-27：管理器资源趋势 GPU 使用率

管理器 `894216f` 在资源趋势的 CPU 后新增 GPU 页签，复用 5 秒采样与 5/15 分钟历史。
`history[].gpu` 读取 `/sys/class/mpgpu/utilization`；缺失或无效时为 null，网页显示缺口，
不沿用上次读数或当作 0%。旧 API 缺少字段时同样可用。

核对 VM 的 `linux-native-hdr-5.15/drivers/gpu/arm/midgard/platform/devicetree/`
`mpgpu.c` 与 `meson_main2.c`：sysfs 返回 DVFS 回调保存的 0–100 百分比，
不是时钟回调另行换算的 0–255。此值为驱动最近周期的忙碌比例，不是整个 5 秒区间平均，
也不包括独立的视频编码器。当前未接入 7.3 Panfrost 计数器；没有接口时显示暂无数据。

验证：Go 全套测试与构建、前端 TypeScript/Vite 构建通过；helper 214 项通过（Mac 跳过 12 项）。
新增历史回归覆盖空闲、满载、非法值、缺失与恢复；浏览器回归覆盖页签位置、缺口、
旧 API、恢复和 1280/390px 布局。管理器开发包的 ARM64、依赖、sudoers 和配置保留隔离验证通过。

板子为 `5.15.137-vim4kvm-hdrdual6`。实际 API 与网页 GPU 均为 0%，无浏览器异常，
1280/390px 截图见本地 `build/gpu-manager/`；未施加板端 GPU 压力负载。
管理器重启前后 One-KVM PID 90197、HDMI PID 1081 未变。
沿用当前 H.265 配置的 4K 视频冒烟 5 秒：300 帧、59.95fps，零丢帧、零丢包。

安装器因开发包基线标签旧于板上包而在安装前拒绝降级，未改变包或服务。
随后仅替换新构建的管理器 ARM64 程序并重启管理器，保留原包登记版本
`2.5.1+vim4.20261026.2`；未发布 Release。
原程序备份为 `/var/backups/vim4-manager-gpu-20261027/vim4-manager`，
部署程序 SHA256 为 `126b6e941beaada5ed87f0c185328e119f91a7b2d9c6b783d25110b034f2fc72`。
构建、隔离验证、部署与网页日志保存在本地 `build/gpu-manager/`。
