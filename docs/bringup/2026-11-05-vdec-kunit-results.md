# 2026-11-05：解码 KUnit 迁移结果

内核 vdec 目录的七个 Python 文件全部移除，五套 KUnit 共 17 项在 arm64 QEMU
实际通过。原来的 49 个方法含大量硬件 mock；逐项风险与替代路径已在删除前写入
[迁移清单](2026-11-05-vdec-test-migration.md)，不能把删除或 KUnit 通过当作硬件通过。
本轮未访问板子，HEVC 首帧超时仍未解决。

## 实现与提交

以下路径均相对内核 `drivers/media/platform/amlogic/vdec/`。
测试调用实际生产函数，static 函数按 KUnit visibility 接口条件导出。
没有抽取 C 源码再编译、假的 vb2/V4L2 实现或寄存器 mock。

| 提交 | 内容与实际覆盖 |
|---|---|
| `02ad5d554b85630919801af399747568e4dbd49a` | Kconfig 补选 REGMAP_MMIO，修复最小配置缺失依赖 |
| `32885171b804a8c01a822ae5c0708d90fd1d03ee` | `h264_headers_kunit.c` 3 项：矩阵/constraint 位序、有符号极值/长 POC 周期、容量/转义边界；删除 `test_h264_headers.py` |
| `b62429eff9d476b933b937debccac8fcc29e960b` | `mjpeg_kunit.c` 2 项：截断头、采样/输出容量；删除 `test_mjpeg.py` |
| `5e6a4f897940988f417a748a43678995e4587448` | `hevc_kunit.c` 5 项：POC 回绕/随机访问、非法固件参数、tile 边界、缺失/重排参考、SAO 容量；删除 `test_hevc.py`、`test_hevc_core.py`、`test_hevc_power.py` |
| `be19158d5547bc3ca8239ff311a034ffbeaf448c` | `mpeg12_kunit.c` 2 项：首个场对参考选择、VBV/矩阵/场标志；删除 `test_mpeg12.py` |
| `fc0d109e2bbb4b90bbeffdb97c2da26e95e1db83` | `h264_kunit.c` 5 项：重复加权参考、独立 B 帧参考、参数 slot/有符号字段、输入 padding、canvas 地址；删除 `test_t7_lifetime.py` |
| `e6f9f06b06d3765148ae6a271c64d8482a175531` | 仅本文件使用的 `aml_S4_dec_ops` 改为 static const，消除实际 sparse 缺少声明诊断 |

`hevc_priv.h` 和 `h264_priv.h` 承载原有内部结构；HEVC 测试处理微码 RPM 元数据，
没有新增内核码流解析。MPEG-2 提取纯参考时间戳选择，实际 DPB 查询仍在原调用者。
H.264 提取 SPS/PPS 表、canvas 编码与 padding 纯函数。PPS 表构建现先于 DPB 发布，
二者都在启动微码之前；这个重构仍需标准码流回归，QEMU 不证明寄存器时序。

## 实际验证

入口为内核 [.kunitconfig](https://github.com/vim4-kvm/linux/blob/fc0d109e2bbb4b90bbeffdb97c2da26e95e1db83/drivers/media/platform/amlogic/vdec/.kunitconfig)。
最终 QEMU 运行对应 `fc0d109e2bbb4b90bbeffdb97c2da26e95e1db83`，17/17 通过；
随后只改操作表链接属性，重新编译内建与模块并运行 sparse，通过后提交。
测试模块已编译，未在 QEMU 里另做模块加载测试。

实际命令的核心参数如下，均在构建 VM 中运行，构建持 heavy 锁、不持板锁：

```sh
python3 tools/testing/kunit/kunit.py run 'amlogic-*' --arch arm64 --jobs 8 \
  --timeout 120 --build_dir /home/deepdream/build/hwdecode-parity-kunit \
  --kunitconfig drivers/media/platform/amlogic/vdec/.kunitconfig \
  --json=/home/deepdream/build/hwdecode-parity-kunit/result.json
make O=/home/deepdream/build/hwdecode-parity-kunit W=1 C=1 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  drivers/media/platform/amlogic/vdec/
make O=/home/deepdream/build/hwdecode-parity-kunit-module W=1 C=1 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 \
  M=drivers/media/platform/amlogic/vdec modules
```

生产配置也单独构建驱动模块。有效 sparse 固定为
`84ec0658c81db4ccc4aabc420d3dc118c2c6a310`（`v0.6.5-rc1-21-g84ec0658`），
日志有实际 CC/CHECK；最终 vdec 范围零诊断。系统旧 sparse 不能作为有效结果。
每步 strict checkpatch 为零 error/warning/check；新文件只忽略 FILE_PATH_CHANGES，
人工确认 MAINTAINERS 的 vdec 通配已覆盖。改动头文件 `kernel-doc -none` 无诊断。
未改 DT binding/DTS，因此本轮无新增 binding 检查；smatch 未安装、未运行。

原始文件保存在 `build/hwdecode-parity/`，不入版本库：

| 阶段 | 原始输出 |
|---|---|
| H.264 headers | `h264-kunit-run3.log`、`h264-kunit-qemu.log`、`h264-kunit-result.json`、`h264-kunit.config`、`h264-kunit-static-module.log`、`h264-kunit-module-config.log`、`h264-kunit-style.log`、`h264-kunit-commit.log` |
| MJPEG | `mjpeg-kunit-run.log`、`mjpeg-kunit-qemu.log`、`mjpeg-kunit-result.json`、`mjpeg-kunit-static.log`、`mjpeg-kunit-style.log`、`mjpeg-kunit-commit.log` |
| HEVC | `hevc-kunit-run.log`、`hevc-kunit-qemu.log`、`hevc-kunit-result.json`、`hevc-kunit-static.log`、`hevc-kunit-style.log`、`hevc-kunit-commit.log` |
| MPEG-2 | `mpeg12-kunit-run.log`、`mpeg12-kunit-qemu.log`、`mpeg12-kunit-result.json`、`mpeg12-kunit-static.log`、`mpeg12-kunit-style.log`、`mpeg12-kunit-commit.log` |
| 最终 17 项 | `h264-params-kunit-run.log`、`h264-params-kunit-qemu.log`、`h264-params-kunit-result.json`、`h264-params-kunit-static.log`、`h264-params-kunit-style.log`、`h264-params-kunit-commit.log` |
| 操作表修复 | `vdec-sparse-cleanup.log`、`vdec-sparse-cleanup-commit.log` |

保留失败记录：`h264-kunit-run.log` 的全内核 W=1 被未修改的 arm64 syscall 表
override-init 警告阻断；`h264-kunit-run2.log` 的缺少 REGMAP_MMIO 由独立提交修复。
正常标志下完整 KUnit 内核通过，之后针对修改目录运行 W=1；不宣称全树 W=1 通过。
早期准备还出现未修改 vdso 的 `__kernel_getrandom` sparse 诊断，不宣称全树零警告。

## 尚未验证

带流 compliance、fluster、调试内核 KASAN/泄漏/锁/DMA 检查、同板 5.15 对照、
性能与 KVM 共存均待下一批窗口。LAST/EOS、DRC、重开、多实例、电源、时钟、
超时停机、失败分配和 DMA 隔离不能由这些 KUnit 结果证明。
历史正常路径记录见迁移清单；故障注入只用标准机制，不保留 mock 作为替代。
