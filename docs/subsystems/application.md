# NanoKVM 应用

先读 [VIM4 集成](../../NanoKVM/VIM4.md)，其中维护功能覆盖、
构建、安装和限制；代码规范见 [code-standards.md](../code-standards.md)。

当前可用功能、缺项与实测边界见 [功能状态](../feature-status.md)。
当前基线的迁移范围与软件验证见 [NanoKVM 基线切换](../nanokvm-migration.md)。

nanokvm.service 与 JetKVM 的 vim4-kvm.service 都监听 8080、以 khadas 运行，
互相 Conflicts=，不能并发占用编码器或 HID。由 vim4-manager（80 端口）选择开机启用哪一个，
部署时保留当前选择。板级服务拥有 HDMI、gadget、PD 和编码器时钟。
应用更新不能替代平台依赖。独立编码测试以相同用户共享 /tmp 锁空间，
不能删除活跃的 /tmp/vpu_mutex.map。

VIM4 后端使用 -tags vim4，保留上游目标实现。共享代码修改检查两个构建目标；
前端按锁文件构建，具体命令以 VIM4.md 为准。
账户、网络、更新沿用原 UI/API，经平台适配实现 Ubuntu 行为；
不能将上游整机固件更新部署到 VIM4。缺失外接硬件保持未配置。
