# 候选 WC DMA heaps

仅用于专用 kbase 候选 DT，不改变正式 7.3 的 system/CMA exporter。
GPL-2.0-only；没有 libmali 或其他专有数据。

5.15 固定厂商源码的 `drivers/dma-buf/heaps/system_heap.c` 提供
system-uncached：普通可不连续 system pages，WC mmap/vmap，首次 DMA map/unmap
清掉 cached 清零别名，后续 attachment 跳过 CPU cache sync。
`common_drivers/drivers/media/common/dma-buf-heaps/amlogic_heap_cma.c` 的 heap-gfx
从专用 reusable CMA 区分配连续页，同为 WC CPU 映射、skip CPU sync。
kvim4n.dts 为它保留 300 MiB，按 4 MiB 对齐池；单次分配 alignment 为
min(get_order(size), CONFIG_CMA_ALIGNMENT)。它供 GBM/图形分配；连续与 WC 是
跨显示/视频导入的必要条件，格式、stride、modifier、fence 合同仍须各 importer 验证。
不能从 heap 名字推断任意 Wave5 格式都能导入。

本模块保持上述可观察的缓存/连续性合同：

- system-uncached 逐页清零分配，首次 DMA cache 维护之后仅暴露 WC 映射；
  不加高阶页池，先减少维护面，不承诺厂商 allocator 的分配性能。
  exporter设备使用64位DMA mask，使高地址原页的清零cache维护不落到bounce buffer；
  heap-gfx的低地址限制由独立CMA池的alloc-ranges/物理范围校验保证。
- heap-gfx 通过非 coherent 平台设备的 DMA API 分配 WC 连续内存，设备绑定独立
  reusable CMA 池。校验单一物理 SG 段且整个 buffer 位于该池；拒绝 DMA-direct
  的池耗尽 buddy fallback，绝不把 default_cma_region 伪装成专用池。
  候选池为 128 MiB，容量小于厂商，不能宣称分配容量 parity。
- 每次 attachment mapping 独立 SG table，经目标设备的 dma_map_sgtable 获得 DMA
  地址；不复制另一设备的 DMA 地址。release 成对回收页/DMA 分配。
- WC CPU access 使用屏障，应用仍须遵守 DMA_BUF_IOCTL_SYNC 与设备 fence 完成顺序。
  这里只提供内存 exporter，不补造显示/视频的隐式同步模型。

与早期 system-uncached 提案的关系是相同的 WC/初次 cache 清理设计方向，
本模块不是“已合入上游”的功能，也没有复制整份 system heap/page-pool 实现。
提案作者的[原始 Android 提交说明](https://android.googlesource.com/platform/frameworks/av/+/6a40788b59a8d898add800ce04f5a9aa06f476e1)
记录了当时计划上游化的 system-uncached；本次实际 7.3 源码没有该 heap。
后续若上游有等价且可选的 WC exporter，优先替换本模块。

当前基线公开 dma_heap API 只有 add，没有 unregister。首次注册后永久持模块引用，
禁止 sysfs unbind，回收只能重启。第二个 heap 注册失败时保留首个并明确报错，
不能返回失败让模块卸载、留下悬空 heap 回调。只支持候选 DT 的单个设备。
此限制及候选私有 compatible 使它适合一次性 RAM 试验，尚不是通用可热插拔驱动。

build.py 与 kbase 一起 W=1/Werror 构建、modpost、记录源码及 ko 哈希并放入 stage。
check-heaps.py 运行实际 mmap 代码的 host VMA/DMA 模型，覆盖偏移越界/溢出与 WC 路由；
硬件 cache 一致性、内存压力、跨设备 fence 与 pool 容量仍须实测。
独立构建：`make -C KERNEL_BUILD M=$PWD W=1 KCFLAGS=-Werror modules`。
加载顺序为 `modprobe vim4_kbase_heaps`、`modprobe mali_kbase`；不能在默认 DT 上创建假设备。
