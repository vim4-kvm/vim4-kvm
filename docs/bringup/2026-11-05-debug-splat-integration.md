# 2026-11-05：启动修复重放到 KUnit 迁移基线

新内核分支 `debug-splat-fixes-v2` 已在原任务工作树离线重放完成，HEAD
`e8c40f17b20ead654c5d6c714da9b2762ff62d2a`。两个提交的format-patch输出均通过
未过滤strict checkpatch（0 error/warning/check）。按协调者要求没有编译或运行
合并后的KUnit，等待统一集成构建；不把原分支通过的测试写成新树通过。

## 拓扑与提交映射

基线 `7e35e3bcc51a2e78cda4f7988dede7a1182b2cb9` 已含前四个启动修复及KUnit迁移。
只重放其后的两个修复，没有重复移植前四项。原分支 `debug-splat-fixes` 保留在
`53d7db5f377e86998295aeb082eedba3aec108de`，没有reset、改写或合并到其他分支。
仍使用 `/home/deepdream/src/linux-7.3-debug-splat-fixes`，未创建或修改其他工作树。

| 原提交 | v2提交 | 内容 |
|---|---|---|
| `f911e1d8817fb` | `5deb393be15017edd94aa10bcd06e9517a5bfb0f` | MMC完成回IRQ线程，SDIO短锁改raw；patch-id与原提交相同 |
| `53d7db5f377e8` | `e8c40f17b20ead654c5d6c714da9b2762ff62d2a` | ADLA调用点mutex宏，并入现有独立KUnit suite |

保留原作者、正文和Signed-off-by。第二个提交追加冲突处理说明，明确原验证属于
重放前源码，合并suite的编译/QEMU验证尚待集成窗口。没有设置git配置或更换身份。

## ADLA 冲突如何解决

`.kunitconfig` 合并两边需求，保留原配置并加DEBUG_KERNEL、PROVE_LOCKING和KASAN，
每项只出现一次。`Kconfig` 只保留迁移分支原有的一个tristate
`AMLOGIC_ADLA_KUNIT_TEST`，继续允许独立测试模块，帮助文字补充mutex类测试。

保留原Makefile的 `adlak_kunit.o` 独立模块结构，将真实device→SMMU锁嵌套测试
加入既有 `adlak_kunit.c`，复用其销毁action。全套为5个case，不再增加单独的
`adlak_os_test.c` 或第二个suite。未启用PROVE_LOCKING时只skip无法检查锁类的case，
原分配器/取消/边界case仍运行；提交的 `.kunitconfig` 会启用它需要的lockdep。

迁移分支曾为旧init函数增加KUnit导出。它现在已是宏，必须把导出改为
`adlak_os_mutex_alloc`，并为独立测试模块的真实lock/unlock调用补
`EXPORT_SYMBOL_IF_KUNIT`；destroy的既有测试导出和测试namespace import保留。
生产KUNIT=n没有新增导出，不使用nested或关闭验证来绕过启动报告。

原分支原有Python测试未被本任务修改；v2上这些文件的删除来自已指定的迁移基线，
本次重放没有重新引入或再处理它们。

## 静态检查与未验项

逐提交format-patch和完整日志位于本机 `build/debug-splat-fixes/v2/`，以完整SHA命名。
两份strict检查均0/0/0，没有忽略FILE_PATH_CHANGES或其他消息。另确认：

- 原分支指针未动，v2是7e35e3bcc51a2后恰好两个提交，工作树干净。
- MMC patch-id不变；ADLA只保留一个配置项、一个suite和5个case。
- `git diff --check`通过；新增导出与宏调用目标、现有测试namespace逐项核对。

按照heavy暂停指示，本轮没有运行v2的W=1、sparse、模块/内建/生产构建或QEMU。
原分支 `53d7db5` 的KUnit 1/1与构建记录见
[ADLA修复记录](2026-11-05-adla-mutex-pd-timing.md#adla-修改与来源)，仅作历史验证。

协调者后续把fan-thermal接到此HEAD，再由kunit-migration构建唯一的生产/调试
集成候选；本任务不再另建候选。未来调试A须取得零目标告警、debug_locks持续开启、
ADLA/Wi-Fi绑定及真实eMMC/SDIO流量；生产B仍需同方法600秒单TCP接收，与历史
369.55 Mbit/s及分位比较，明显下降报告而不恢复硬IRQ完成。

`.83` 实板仍发生cold_boot，已恢复 `.3` 与4K视频；完整门禁和生产B均未通过验收，
不得以重放成功或零静态诊断替代。[本轮实板与PD对照](2026-11-05-adla-mutex-pd-timing.md#83-实板与新的-pd-尾部)
