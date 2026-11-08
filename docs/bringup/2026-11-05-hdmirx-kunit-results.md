# 2026-11-05：T7 HDMI RX KUnit 迁移结果

> 本页保留原验证时的 SHA。修订后的对应、完整提交检查与当前利用率修复边界见
> 审查返工记录。

`drivers/media/platform/amlogic/t7-hdmirx/` 的 20 个 Python 文件全部迁出或删除。
独立 KUnit 模块 9 项在 arm64 QEMU 实际通过。四个生产校验函数体未改；
环槽选择与 READY→COPYING 循环原样提取，仍在原 `irq_lock` 临界区中执行，
没有移动 MMIO、DMA 请求或解锁时机。本轮无板端访问，V/B/F 均待实板。

删除前的风险分类先在主仓库 `e350172` 提交，见清单
1、
2、
3、
4。

## 提交和实际覆盖

内核工作树为 VM `vim4-build` 的 `/home/deepdream/src/linux-7.3-kunit-migration`，
分支 `kunit-migration`。以下路径相对该驱动目录。

| 提交 | 内容 |
|---|---|
| `3e974b369efca` | `t7_hdmirx_kunit.c`、`.kunitconfig`、Kconfig/Makefile；四个校验函数按 visibility 条件导出，新增私有测试声明；环槽类型移至 `t7-vdin-ring.h`，纯选择函数由原锁内调用；删除六个含 K 类风险的 Python 文件 |
| `610d4b7218873` | 删除其余 14 个 Python 文件，包括已迁出的独立拷贝基准；无生产 C 改动 |

测试直接调用生产函数或生产 inline helper，没有抽源码编译，也没有重建
vb2/V4L2、ALSA、MMIO 或 IRQ 框架。9 项覆盖：

- EDID 完整块、逐块 checksum、header/扩展数，即使 checksum 修复也拒绝错误 header/块数；长度边界。
- 音频七种 ACR 采样率与 N/CTS、无时钟/无计数器、错率、压缩/HBR/多声道拒绝。
- LUT 右移后的 little-endian CRC，使用独立 zlib 固定向量，包括空输入。
- HDR 双曲线的完整事务、所有前缀截断、额外数据、非法数字/范围、gain/OETF 单调性和端点。
- 三个真实环槽的序号回绕、最旧 READY 选择、COPYING 转移与非 READY 排除。
- HDR/PQ/HLG 编码变化使旧 lease 失效，SDR 不依赖遗留 EOTF。

`test_buffer_layout.py` 的首成员要求由原生产 `static_assert` 继续保证；
不保留另建假结构或故意改坏源码的宿主回放。真实分配/队列边界另交标准接口。
主仓库 `6e031e0` 将独立 SIMD 候选工具迁为
[t7-vdin-copy-bench.py](../../tools/t7-vdin-copy-bench.py)，显式指定内核源码，
仍与真实 `memcpy_generic` 对照。VM 的保护页、尾部及 scalar fallback 校验通过，
未运行生成程序的板端 MMAP benchmark。该候选没有因此接入驱动数据路径。

## 实际验证

构建均经主仓库 `tools/board-queue run --heavy`，没有持板锁。
在上述内核工作树内运行，`out` 为 `$PWD/.kunit-hdmirx`：

```sh
python3 tools/testing/kunit/kunit.py run 't7-hdmirx*' --arch arm64 --jobs 8 \
  --timeout 120 --build_dir "$out" \
  --kunitconfig drivers/media/platform/amlogic/t7-hdmirx/.kunitconfig \
  --json="$out/result.json"
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  drivers/media/platform/amlogic/t7-hdmirx/
make O="$out" ARCH=arm64 M=drivers/media/platform/amlogic/t7-hdmirx clean
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  M=drivers/media/platform/amlogic/t7-hdmirx modules
scripts/kernel-doc -none drivers/media/platform/amlogic/t7-hdmirx/t7-hdmirx-kunit.h \
  drivers/media/platform/amlogic/t7-hdmirx/t7-vdin-ring.h
git diff --cached | scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

QEMU 最终 9/9 对应提交的测试实现；之后只调整导出宏空行、增加锁约束注释并删除
Python，没有改变测试或生产函数体。内建 W=1/sparse、模块 W=1/sparse、
KUNIT=n 的生产模块构建完成。模块配置先启用 MODULES 并将驱动/测试设为模块，
运行 olddefconfig、完整构建生成匹配符号表后再做模块检查。
测试模块已编译，未在 QEMU 单独加载。

sparse 为 `84ec0658c81db4ccc4aabc420d3dc118c2c6a310`，版本
`v0.6.5-rc1-21-g84ec0658`，日志有实际 CHECK，驱动范围无诊断。
准备阶段有未修改 arm64 vDSO 的 `__kernel_getrandom` 声明诊断，不宣称全树
零诊断或全树 W=1 通过。strict checkpatch 最终零 error/warning/check；
仅忽略 FILE_PATH_CHANGES，人工核对现有 MAINTAINERS 的目录通配覆盖新文件。
新增头文件 kernel-doc 无诊断。未修改 binding/DTS；smatch 未安装，未运行。

原始输出在主仓库 `build/kunit-migration/`，不入库：

| 阶段 | 输出 |
|---|---|
| 初次与最终 KUnit | `hdmirx-run.log`、`hdmirx-gates.log`、`hdmirx-final-qemu.log`、`hdmirx-final-result.json` |
| 模块/生产/最终静态 | `hdmirx-final.log`、`hdmirx-kunit-style.log`、`hdmirx-remove-style.log` |
| 生产对象清理后重编 | `production-clean-rebuild.log`；切换配置时 M= 复用了旧对象，最终以清理自身目录后实际 CC/CHECK 和无 KUnit 导出符号检查为准 |
| 初次样式与保留失败 | `hdmirx-style-initial.log`；续行对齐及导出前空行问题已修正复验，无生产行为修复 |
| 工具 | `hdmirx-copy-help.log`；实际编译与 VM 正确性输出在 `hdmirx-gates.log` |
| 主仓库 | `main-tests-hdmirx-inventory.log`、`main-tests-hdmirx-tool.log`、`main-tests-hdmirx-results.log` |

VM 的 `.kunit-hdmirx/` 保留 builtin.config、module.config、production.config
和编译产物。主仓库完整离线检查已运行 534 项，14 skipped，结果 OK。

## 待实板

标准带流 compliance、ALSA 实流、DDC/HPD、格式/色彩/时序和动态 source events、
HDR/PQ/HLG 标准样本像素、native plane 预算、DMA-BUF/export 身份和引用、
多线程 ioctl/remove、direct/copy 环饥饿及停流、CPU copy/IRQ 交错、源丢失、
PLL/时钟/电源故障、超时隔离与分配失败全部待实板。
生产首成员 static_assert 和 QEMU 纯逻辑均不证明真实 vb2/DMA 生命周期通过。
板端故障注入只用标准调试机制，不能继续使用删除的框架 mock。
