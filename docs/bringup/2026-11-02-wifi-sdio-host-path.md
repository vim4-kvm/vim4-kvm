# 2026-11-02：BCM43752 SDIO 主机路径优化与 5.15 同窗对照

[每聚合周期拆解](2026-11-02-wifi-glom-cycle.md)确认 7.3 下载受主机每周期开销限制。本轮按上游方式
修改 meson-gx-mmc 与 brcmfmac/DT，RAM 启动候选逐个测量，最后与 5.15 同一窗口对照。
结论：主机侧已基本追平；同窗口下 D2 高于 5.15，剩余周期主要是等待固件交付数据。

## 改动

基于 origin/vim4-kvm-7.3 `923aa01fdd7d4`，五个独立提交，均通过 `checkpatch --strict`：

| 提交 | 作用 |
|---|---|
| A `mmc: meson-gx: use a cacheable DDR bounce buffer` | 中转缓冲区由 `dmam_alloc_coherent`（非缓存）改为 `dma_alloc_noncoherent` 加流式同步，消除约 130 µs/周期的非缓存复制 |
| C `mmc: meson-gx: respect the SDIO interrupt enable state` | 中断按 `SD_EMMC_IRQ_EN` 过滤；原实现按能力位把 DAT1 数据传输锁存的 SDIO 状态当卡中断，约 2500 次/秒空跑 `sdio_irq_work` 并争抢主机锁。启用时检查锁存与 DAT1，不丢带内中断 |
| B `mmc: meson-gx: complete simple requests in the hard IRQ` | 无错误、无中转读复制、无后续命令的请求直接在硬中断完成 |
| `wifi: brcmfmac: allow a traffic IRQ without system wake support` | meson GPIO irqchip 无唤醒回调，`enable_irq_wake` 返回 -ENXIO 时保留业务中断，不声明 WoWLAN |
| `arm64: dts: amlogic: wire the VIM4 Wi-Fi host interrupt` | wifi@1 `interrupts-extended = <&gpio_intc 27 IRQ_TYPE_LEVEL_HIGH>`（GPIOX_7），`interrupt-names = "host-wake"` |

独立审查：A/B/OOB 未发现新缺陷；继承问题（错误恢复中停止超时后仍归还缓冲区、`dma_map_sg` 失败写越界、
OOB 路由写失败未检查等）评分低或为既有代码，另行登记。

## 结果

候选均 RAM 启动，复用正式 uhd6 配置与模块集。40 秒带 tracepoint 周期拆解（p50/p90，µs）：

| 内核 | 超帧读取 | 主机忙碌 | 周期 | 中断→读取 | 命令/周期 |
|---|---:|---:|---:|---:|---:|
| 默认 7.3（同窗） | 736 | 794 | 972/1031 | 228 | 8 |
| C1 = A | 621 | 679 | 784/1106 | 154 | 8 |
| D1 = A+C+OOB | 639 | 697 | 893/1356 | 168 | 6 |
| D2 = A+C+B+OOB | 629 | 659 | 825/1010 | 126 | 6 |
| 5.15（前一窗口，49.4 KB 聚合） | 535 | 549 | ~670 | — | 2 |

按字节计超帧读取已持平（7.3 55.5 KB/629 µs，5.15 49.4 KB/535 µs，均约 90 MB/s）。
D1/D2 trace 中 `sdio_irq_work` 为 0，`brcmf_oob_intr` 计数随流量增长。

同一窗口、同一 Mac、单 TCP 反向下载，120 秒不带跟踪（Mbit/s）：

| 内核 | 平均 | p10 | p50 | p90 |
|---|---:|---:|---:|---:|
| 默认 7.3 | 371.8 | 354.4 | 374.3 | 392.2 |
| D1 | 378.5 | 359.7 | 381.7 | 399.5 |
| **D2** | **397.8** | 374.4 | **401.6** | 421.5 |
| 5.15 | 330.8 | 130.0 | 363.3 | 396.4 |

5.15 在 120 秒内出现 17 次跌到 60–260 的周期性低谷（启动后不久），去掉低谷后中位数 368.1；
7.3 各版本无低谷。本窗口空口偏差，绝对值低于此前 600 秒记录（5.15 p50 429）。
单独看 B：上一窗口在空跑 `sdio_irq_work` 存在时无收益，加 C 后 D2 比 D1 平均高 19 Mbit/s。

## 剩余差距

D2 周期仍比 5.15 长，但约一半周期在等固件（等待 p50 79 µs、p90 258 µs）。主机侧余量：
中断→读取 126 µs（工作队列唤醒加 3–4 条短命令），忙碌减传输约 30 µs（5.15 约 12 µs）。
进一步只能改 brcmfmac 读取协议（首读覆盖聚合描述、减少中断状态读取），预计约 20 µs/周期，
低于空口波动，未做。

## 窗口与恢复

共约 32 分钟板时：六次 C 系列尝试（前三次在预检、eMMC 选择和候选启动处失败，均未改动板子）、
一次 D 系列 15.3 分钟窗口。暴露并修复的工具问题：extlinux 路径相对 /boot 分区；
USB 串口丢失“Hit SPACE”前缀导致 RAM 候选未被选中，`tools/board-window` 改为同时匹配 `autoboot` 尾部；
重启后 /tmp 清空需重新拷贝检查脚本；暂存候选目录需在恢复后删除。各候选 eMMC 读回哈希与基线一致，
dmesg 无 MMC 错误。结束为默认 7.3，Wi-Fi disabled，默认路由 eth0，服务 active，UDC configured。
原始数据在本地 build/sdio-bounce/tooling/logs/ 与 logs/wifi-glom-cycle/。
