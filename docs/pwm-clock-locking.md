# VIM4 PWM/CCF 锁依赖分析

不同 chip 的 lockdep 建模修正已获授权并提交，同 chip 真实 ABBA 仍未解决。
提交、验证与下一窗口条件见 [离线修复记录](bringup/2026-11-05-debug-splat-fixes.md)。

## PWM 锁依赖分析与修复边界

核对主线、linux-next、PWM 维护者 `pwm/for-next` 和 clk 维护者 `clk-next`：
最新 Meson waveform 改写仍调用 clk rate API，PWM core 仍持 chip 锁调用驱动，
clk-pwm 仍在 CCF 回调里调用 PWM API，未找到可直接移植的改序补丁。
参考[原始讨论](https://lore.kernel.org/r/d90c0eec-728b-4607-b480-86b2534559c4@brivo.com)、
[可读镜像](https://lists.openwall.net/linux-kernel/2026/09/21/2743)、
[PWM 维护者树](https://git.kernel.org/pub/scm/linux/kernel/git/ukleinek/linux.git/tree/drivers/pwm/core.c?h=pwm/for-next)、
[clk 维护者树](https://git.kernel.org/pub/scm/linux/kernel/git/clk/linux.git/tree/drivers/clk/clk-pwm.c?h=clk-next)。

涉及的锁及当前调用链（行号以本轮起点为准）：

| 方向 | 调用链 |
|---|---|
| chip → CCF | `pwm_regulator_probe` → `pwm_adjust_config` → `pwm_apply_might_sleep` (`drivers/pwm/core.c:747` 取得 `nonatomic_lock`) → `meson_pwm_apply:324` / `meson_pwm_enable:235` → `clk_round_rate` / `clk_set_rate` → `prepare_lock` |
| CCF → chip | `__clk_register` → `clk_core_update_duty_cycle_nolock` → `clk_pwm_get_duty_cycle` (`drivers/clk/clk-pwm.c:71`) → `pwm_get_state_hw` → `nonatomic_lock` |
| 同样的反向入口 | `clk_core_prepare` → `clk_pwm_prepare:43` → `pwm_apply_might_sleep`；`clk_pwm_unprepare` → `pwm_disable` |

CCF 的 `drivers/clk/clk.c:272` / `:287` 对同线程的 prepare 锁维护 owner/refcount，
允许 provider 回调重入 clk API；这不能解决另一个线程先取得 chip 锁再等 CCF 的
ABBA。`meson_pwm_get_state:349` 本身也调用 `clk_get_rate()`。
不同 chip 当前共用一个 lockdep class 不足以证明只是误报：同一个 chip 的另一个
通道、get_state、prepare/unprepare 都需要纳入分析。更换 class 或屏蔽验证不能
作为本任务修复。

协调者已否决在 PWM core 取得 CCF 全局锁：串行范围和 core 耦合过大，未实施。
随后按要求核对实际拓扑。部署打包入口 `packaging/kernel/package-vdec.py:70`
选择 `amlogic-t7-a311d2-khadas-vim4-vdec-test.dtb`，其 include 链为
vdec-test → display-m0 → audio-test → hdmirx-test → udc-test → 基础 VIM4 DTS；
这些 profile 未替换以下 PWM 消费者。r32 候选清单的源码为
`e6f9f06b06d3765148ae6a271c64d8482a175531`，其 PWM DTS 定义与本分支起点一致。

| 消费者 | 基础 VIM4 DTS 行号 | 控制器与通道 | T7 DTSI 节点 |
|---|---|---|---|
| Wi-Fi/BT `wifi32k` | 316–320 | `pwm_ab` 0 | `pwm@58000`，总线地址 `fe058000` |
| VDDEE | 194–203 | `pwm_ao_ab` 0 | `pwm@5e000`，`fe05e000` |
| VDDCPU_B | 272–281 | `pwm_ao_ab` 1 | 同上 |
| VDDCPU_A | 257–266 | `pwm_ao_cd` 1 | `pwm@60000`，`fe060000` |
| VDDGPU / VDDNPU | 209–233 | `pwm_ao_ef` 0 / 1 | `pwm@30000`，`fe030000` |
| VDDDDR | 179–188 | `pwm_ao_gh` 0 | `pwm@32000`，`fe032000` |

基础 DTS 为 `arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4.dts`，
控制器定义在相同目录 `amlogic-t7.dtsi:1270,1281,1297,1330,1341`。
r32 dmesg 第 324–415 行打印当前 `nonatomic_lock` 实例地址
`ffff0001093567c8`、regulator probe 栈和此前 clk-pwm 注册栈，**没有打印 regulator
设备名或此前锁实例地址**，因此不能单凭日志指定是哪一个 regulator 触发。
由唯一 `pwm-clock` 节点和上述全部 regulator 的拓扑，可以确定它们使用不同 chip。
原来的同 class 建模确实把这些不同实例折叠了。

但同 chip 的环也不能排除，而且有现成源码路径：生产/调试配置开启 DEBUG_FS，
`drivers/pwm/core.c:2671` 的 debugfs 展示对所有通道（包含已被 clk-pwm 请求的
通道）调用 `pwm_get_state_hw()`，在 `core.c:812` 持有 Wi-Fi chip mutex 后，
`pwm-meson.c:349` 再调用 `clk_get_rate()`。另一个线程的 clk-pwm duty 查询或
prepare 则持 CCF 锁等待同一 Wi-Fi chip。这个路径不需要另一个通道被 regulator
使用，独立 key 仍会正确报出它。`core.c:996` 的 PWM 初次 request 也读取硬件，
若此时 CCF 有竞争，就可能在 clk-pwm 注册前记录同实例反向边；所以不能保证独立
key 令所有启动调度顺序都零告警。r32 日志并不证明这些同实例并发已经发生。

上游讨论须分开看：[2024 年维护者回复](https://lkml.rescloud.iu.edu/2404.0/05306.html)
当时认为全局 prepare 锁的报告是误报，建议研究 per-clock 锁，明确没有现成的
简单修复；不能把该判断泛化到所有并发。上面链接的 2026-09-21 Sean Anderson
邮件则具体列出了 debugfs/CCF 同 chip ABBA，并以征求解决思路结束，未给修复。
未检索到其后可移植的独立 key 补丁；不能把未找到后续回复表述为讨论已形成共识。

按协调者授权，独立 key 的局部实现在每个 `pwm_chip` 内嵌动态 key，在分配时
register，在非原子 mutex 初始化后 set_class，在 `pwmchip_release()` 中 unregister；
这样覆盖 add 失败和设备引用延迟释放，不在 remove 时提前销毁 key。
它能准确区分不同实例，且不屏蔽同实例错误，但**单独实施不足以证明零 splat**。
协调者确认允许先提交独立 key、保留同 chip 问题后，已实施上述分配/释放方案。
提交 `0a35577b8de2` 修改 `drivers/pwm/core.c:1616,1638,2480` 和
`include/linux/pwm.h:350`；key 生命周期覆盖未 add 的 chip、add 失败和延迟释放。
没有导出 CCF 锁，也没有改变锁获取顺序、调频或实际硬件状态查询。
`CONFIG_LOCKDEP=n` 时动态 key 接口按内核标准退化为空操作。

新增 `drivers/pwm/core_kunit.c` 使用实际 PWM/CCF API：一个 fixture chip 的
get_state 调用 `clk_get_rate()`，另一个从 CCF duty 回调进入 PWM。通过 completion
和线程阻塞状态协调，确定前者真的走了 CCF 的阻塞路径，避免其 trylock 快路径
没有记录依赖而产生无效的单线程通过。随后检查另一个 chip 的回调确实执行，且
`debug_locks` 仍开启。fixture 只替代无硬件环境的 provider 回调，不复制 PWM/CCF
核心实现，不模拟寄存器。独立 key 仍允许 lockdep 检出同一实例的反向依赖。

局部选项及限制：

- clk-pwm duty 查询改用缓存：消除 duty 查询的 CCF → chip，但 prepare/unprepare
  仍会取得同一 chip，因此不是完整修复；还会改变“读取实际硬件占空比”的契约。
- Meson 在固定且独占的输入时钟下缓存频率、在 apply/get_state 中只访问寄存器：
  能消除 chip → CCF，保留 CCF → chip；但现有驱动会按请求动态调输入频率，
  直接固定频率会改变 PWM 精度及电源行为，必须先审查是否只对 Wi-Fi 控制器采用
  明确的固定时钟模式，不能无条件改全部 regulator 所在控制器。
- 若先仅修启动不同实例的建模：独立 key 是准确的建模修正，须明确保留上述
  debugfs 同 chip 问题，不能宣称整个锁设计已解决。协调者已批准这种分阶段范围；
  不以默认不读 debugfs 为永久修复。


