# 视频优化的本地基准

日常先测不接触采集/编码设备的生产 buffer helper，再用离线驱动回归验证所有权。
最后在 7.x 测真实采集、编码和网页解码。无需为每次用户态改动重启或更新内核。

## 软件路径

复用已运行的 Linux ARM64 `vim4-wave5-build` 容器，要求当前 `One-KVM` 绑定到
`/work`，具备现有 VIM4 构建依赖。命令会增量编译 release 库测试，不安装应用。

```sh
python3 tools/onekvm-local-bench.py --output logs/kernel-edge/buffers-before.json
# 修改后；仅同一环境和负载允许自动对比，20% 是本次选择的门槛。
python3 tools/onekvm-local-bench.py --output logs/kernel-edge/buffers-after.json \
  --baseline logs/kernel-edge/buffers-before.json --max-regression-pct 20
```

直接调用生产 `plane_view` 与 `cached_bitstream`，覆盖 1080p 的 1088 行容量、4K、
62,500 字节平均压缩帧和 1 MiB 大帧；后两者是合成内容，未执行 H.264/H.265 解析。
另测普通缓存内存中的完整 NV12 复制作为参考。先校准预热，再采九个批次，输出每次
操作的中位数、P95 和原始批次样本；P95 是批次均值的分位数，不是单帧尾延迟。
报告记录源码、dirty 状态、关键文件 SHA、环境、尺寸及每次复制字节数。

默认不会 SSH；运行时禁用插件扫描并使用独立临时 registry，避免 gst_init 探测视频节点。
file-backed GstDmaBufMemory 仅用于布局、持有关系和 CPU 路径；
它不是硬件 DMA 映射，Mac/容器的内存带宽不能用于预测 VIM4 CPU 占用。
复制字节数描述代码路径，不是 DMA 或硬件总线计数器。

## 在板子当前内核运行同一测试

```sh
python3 tools/onekvm-local-bench.py --board vim4 --cpu 0 \
  --output logs/kernel-edge/board-buffers.json
```

上传校验后的独立测试程序至临时目录，只给该进程设置 CPU 亲和性，完成后删除。
不停止服务、不覆盖程序、不改 governor、不打开视频节点、不重启。5.15 和 7.x
都能跑，但不同内核报告不自动混作同环境回归；保留应用负载信息。测试会占用一个
CPU 和内存带宽，已有观看者可能受到短暂影响，避免同时进行另一组性能测量。

可选 `--dma-heaps /dev/dma_heap/system` 使用真实私有 DMA heap 缓冲，CPU 读写明确
执行 START/END 同步；这些 case 包括同步 ioctl 开销。只填写当前内核存在且可映射的
heap，不自动选择厂商安全内存。分配与初始化在计时外，测完自动释放。
heap 与 VDIN/VPU 的映射类型可能不同，不能据此认定驱动已提速。

## 驱动回归与复制候选

为软件 benchmark 增加 `--kernel-source /path/to/linux-7.3` 可先在本机编译运行
实际 IRQ/环/vb2 C 代码、Wave5 平面偏移检查、profile 转换、逐行刷新预算，
以及 ASan/UBSan 分配失败/关闭回归。
需要本机 C 编译器；实际 IRQ 和 DMA 由可控桩替代，属于生命周期回归，不是硬件仿真。

Linux ARM64 中另运行内核源码的
`drivers/media/platform/amlogic/t7-hdmirx/test_copy.py --output /tmp/vdin-copy-bench`。
它编译独立 SIMD 候选汇编和当前内核实际 `memcpy_generic`，先校验越界、非整块
尾部和标量回退。候选未链接到驱动；编译出的程序可复制到板上单独运行。

`taskset -c 0 /tmp/vdin-copy-bench --benchmark /dev/videoN` 在**无视频观看者且采集队列
未被其他进程占用**时，申请实际 VDIN 的四个 MMAP 输出缓冲。先通过 sysfs 的
`name` 找到 `t7-vdin-test`，不能假定节点编号。不会 STREAMON、不会改 EDID。
交替比较当前内核标量汇编和 SIMD 候选，逐轮比较完整输出内容，结束后释放队列。
该测量包括实际输出映射的写入成本，但不含源 DMA 同步、IRQ、编码、调度及内核
SIMD 上下文开销；采集线程 CPU、浏览器帧完整性和启停恢复仍需上板验收。

每份结果使用新文件名，避免覆盖基线。阈值失败返回 2；构建、回归、执行或环境
不兼容返回 1。受干扰的结果保留并说明原因，不通过放宽帧正确性标准来接受优化。
