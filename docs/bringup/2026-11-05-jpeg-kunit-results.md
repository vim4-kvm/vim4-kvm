# 2026-11-05：T7 JPEG KUnit 迁移结果

内核 `bebd278ea650c` 删除 t7-jpeg 的两个 Python 文件，独立 KUnit 2/2 在
arm64 QEMU 通过。风险先在主仓库 `fd6f7ea` 登记于[清单](2026-11-05-kunit-inventory-jpeg-1.md)。
本轮仅离线，DMA、故障路径及像素替代验证全部待实板。

`drivers/media/platform/amlogic/t7-jpeg/t7_jpeg_kunit.c` 直接调用生产量化函数与
JPEG 头序列化函数，覆盖百档质量的范围/单调性、DQT zigzag、DHT 段、SOF 几何、
SOS 扫描边界和对齐。量化循环原样提取，仍先于 header 构建及首个 MMIO；
所有寄存器、DMA 同步和启停调用次序保留。未重建设备、DMA-BUF 或 MMIO 框架。
纯头部 KUnit 不证明硬件输出符合 JPEG 或像素正确。

在 VM `/home/deepdream/src/linux-7.3-kunit-migration`、分支 `kunit-migration`
持主仓库 heavy 锁构建，没有板锁。实际命令中 `out=$PWD/.kunit-jpeg`：

```sh
python3 tools/testing/kunit/kunit.py run 't7-jpeg*' --arch arm64 --jobs 8 \
  --timeout 120 --build_dir "$out" \
  --kunitconfig drivers/media/platform/amlogic/t7-jpeg/.kunitconfig \
  --json="$out/result.json"
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  drivers/media/platform/amlogic/t7-jpeg/
make O="$out" ARCH=arm64 M=drivers/media/platform/amlogic/t7-jpeg clean
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  M=drivers/media/platform/amlogic/t7-jpeg modules
scripts/kernel-doc -none drivers/media/platform/amlogic/t7-jpeg/t7-jpeg-kunit.h
git diff --cached | scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

内建、测试模块及 KUNIT=n 的生产模块均构建；每次配置切换后完整构建匹配符号表，
再清理自身目录模块产物并重编。W=1 和有效 sparse 范围无诊断；sparse 为
`84ec0658c81db4ccc4aabc420d3dc118c2c6a310`。准备阶段保留未修改 vDSO
`__kernel_getrandom` sparse 声明诊断，不宣称全树零诊断或全树 W=1 通过。
strict checkpatch 零 error/warning/check；仅忽略 FILE_PATH_CHANGES，现有
MAINTAINERS 的目录通配覆盖新文件。新增头文件 kernel-doc 无诊断，未改 binding/DTS。
smatch 未安装；测试模块未另做加载验证。

原始输出在主仓库 `build/kunit-migration/`：`jpeg-run.log`、`jpeg-gates.log`、
`jpeg-final.log`、`jpeg-final2.log`、`jpeg-commit-style.log`。
VM `.kunit-jpeg/` 保留 QEMU test.log、result.json、builtin.config、module.config。
保留初次长行和续行对齐的 checkpatch 失败；最后仅修格式并复编，不改变生产行为。
主仓库离线全测日志 `main-tests-jpeg-inventory.log`：534 项，14 skipped，OK。

未验：真实 producer fence/reservation、SG/4GiB/存储范围、逐次 attach/map 分配失败、
busy/未供电、首帧及变长输出 DMA 所有权、重复启停和标准样本像素比对。
兼容 jpegenc ABI 本轮未改，也未把它当作 V4L2 compliance。
