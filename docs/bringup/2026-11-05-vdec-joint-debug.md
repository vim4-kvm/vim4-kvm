# 2026-11-05：解码与启动修复联合调试

本次候选只作 RAM 调试，已结束并恢复正式 `.3`。`.23` 在 MMC IRQ 的 DMA
调试路径报 Invalid wait context，随后发生未解释的冷复位，未进入解码验收。
三项旧启动问题不能判为全部通过，HEVC 草稿仍未验证。

## 候选与验证范围

独立工作树 `linux-7.3-vdec-joint-debug` 的合并提交
`bdb6c78125e2f0bd05e34777a80f81b1f708dcd1`，父提交为解码分支
`e6f9f06b06d3765148ae6a271c64d8482a175531` 和启动修复分支
`0a35577b8de28ff232799209c28f4b1e008fd685`。没有把启动修复合入
`hwdecode-parity` 本身。启动修复范围与已知 PWM 同控制器 ABBA 见
[修复记录](2026-11-05-debug-splat-fixes.md)。

完整包基于上述已提交合并树。解码前单独加载同次配置、BTF 和版本构建的私有
HEVC 模块，另含尚未提交的[握手与 FIFO 草稿](2026-11-05-hevc-stateful.md)：
WAIT_FLAG、启动 ACTION_DONE、FIFO 末端/写指针对齐及使能顺序和超时状态记录。
不在内核解析码流。草稿是否正确由本轮真实解码验证，未通过前不提交。

| 身份 | 本次值 |
|---|---|
| release | `7.3.1-vim4-20261105.23` |
| 配置 SHA-256 | `16e40afca3bc9019d1c7379268ea23ea36dfbc781444abf45f9cab16b4be47bc` |
| Image SHA-256 | `aa1db15663a344ade74335800127a8822b58689c893caf4f00d90268f792c2e5` |
| Image build ID | `97e677996d426589d1f176d6d005ccce21ccba7c` |
| 完整包 SHA-256 | `3128c209475aa43033a3ebc89f302621e7978cbcfdc00266ab0353b7ad625a0a` |
| RAM 包 SHA-256 | `3507da4e8dcd010398d2888855391a0e61bc27554d0ffbb4dcab98f8c0f8db82` |
| 私有解码模块 SHA-256 | `3aad424f54ee0dcea28ecf41d39f3b79b69c732b22ed7dbd29151fd709d4c575` |
| 私有模块 build ID | `65952b1c036ab2a8553921e81124e2491bea97c4` |
| HEVC 草稿 SHA-256 | `9d081f4235dd70bf184ecb33c749adb951683b64c6145fbc6d2710efb7482909` |

原始证据在 `build/hwdecode-parity/` 的 `joint-debug-build.log`、
`joint-package.log`、`joint-private-module.log` 和 `run33/prepare.log`、
`run33/config-proof.log`。私有模块 W=1/C=1 实际执行 sparse CHECK 并成功链接。
配置开启 KASAN、kmemleak、PROVE_LOCKING、DEBUG_ATOMIC_SLEEP、DMA_API_DEBUG。
RAM 包经现有 validate_bundle 全量检查，模块 vermagic 与 Image release 一致。

本次窗口复用已封存的完整标准码流，先运行节点 compliance，再运行 HEVC
`AMP_A_Samsung_7`；任一步失败即停止。新增联合门禁要求启动后、首次解码前和结束时
无调试告警，且 lockdep 仍开启、ADLA 已绑定、Wi-Fi 固件已加载。结束时重新保存
完整内核日志。门禁工具离线回归 537 项、跳过 11 项，原始结果为
`joint-runner-tests.log`。不访问 PWM debugfs，不修 PWM。

## 实板结果

首次窗口 `hwdecode-parity-r33` 在候选启动前退出：旧 `.22` 的 `/tmp` 上传
归档已经不存在，清理脚本却要求它存在。正式身份与视频已验证，未停服务或启动
候选，未删除旧候选目录。离线改为只在归档存在时核验并删除，旧候选目录仍须
逐文件校验；原日志保留在 `run33/preflight-abort.log`、`preflight-video.json`。

实际启动窗口为 `hwdecode-parity-r33b`。清理旧候选、上传 `.23` 后，串口确认
加载正确 Image，并由私有 init 挂载匹配模块。启动约 4.81 秒出现：

```
BUG: Invalid wait context
swapper/0/0 ... &dma_entry_hash[i].lock ... context-{2:2}
debug_dma_unmap_sg → dma_unmap_sg_attrs → meson_mmc_post_req
→ meson_mmc_irq → __handle_irq_event_percpu
```

这是本次先出现的锁检查错误，不是 PWM 跨实例锁环，也不据此推断复位原因。
此后不能用“没有新的锁告警”证明解码锁检查有效；尚未取得 `/proc/lockdep_stats`
快照，首次解码前及结束时的候选门禁都未运行。

候选约 18 秒仍打印 Wi-Fi `BCM43752/2` 固件初始化成功，未看到旧 brcmfmac
KASAN 特征；但随后串口直接回到 BL2，U-Boot 报 `cold_boot`，没有保存到 panic
或正常关机过程。默认启动回到 `.3`，导致候选 release 就绪断言一直失败，外层
启动命令在 180 秒超时。不能把这次复位写成已证实的看门狗、供电或 lockdep
导致的复位。没有更改 PWM，也没有重试解码或加载私有 HEVC 模块。

| 验收项 | 结果 |
|---|---|
| `.23` Image/匹配模块启动 | 串口确认进入候选 Linux，未完成就绪 |
| 三项旧 splat | 本段串口未见旧特征；ADLA 成功 probe 未取得证明，且新的 lockdep 错误先发生，因此不通过联合验收 |
| Wi-Fi 固件初始化 | 候选串口有成功记录；不等同于整轮 KASAN 验收通过 |
| compliance（三节点） | 未运行 |
| HEVC `AMP_A_Samsung_7` | 未运行，不能计作码流超时或解码失败 |
| HEVC 全集 | 0/147 已验证通过，147/147 未运行 |
| H.264/MPEG-2 标准集、5.15 对照 | 本轮全部未运行 |
| kmemleak、性能、长期共存 | 未运行 |
| 正式基线恢复 | `.3` build ID、2,370 个证明文件核对通过；One-KVM/管理器/UDC 就绪 |
| 恢复后实收视频 | 3840×2160 H.265，约 5 秒解码增加 298 帧，59.55 fps；新增丢帧/冻结/丢包均 0 |

恢复脚本正常重启一次并完成基线证明与视频接收，窗口释放板锁；候选临时 Wi-Fi
固件副本已清理，正式默认与配置不变。恢复只是短接收验证，不是延迟或稳定性结论。

原始证据目录 `logs/hwdecode-parity-r33b/`：

- `uart-1793865297808564000.log`：候选身份、MMC IRQ 锁错误、Wi-Fi 成功和冷复位；
- `uart-1793865406645872000.log`：恢复串口；
- `returned-baseline-identity.json`、`returned-video.log`：最终身份与真实接收；
- `dmesg-1793865425943670000.log` 是**已经返回 `.3` 后**采集，不能替代候选日志。

`build/hwdecode-parity/run33/window.log` 保存启动超时及
`WINDOW_FINISHED baseline restored=True`。文档和门禁的主仓库检查
`run33/main-tests.log` 为 537 项、11 跳过。后续应先解决启动锁检查错误并查明
冷复位，再安排解码验收；本次没有将未验证 HEVC 草稿提交到解码分支。
