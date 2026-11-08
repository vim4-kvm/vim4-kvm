# 2026-11-08：DOS regmap debugfs 修复设为正式默认

`.42` 遗留的风险是：解码器 DOS regmap 在 `DEBUG_FS=y` 下，root 读 debugfs `registers`
会绕过运行期租约直接 MMIO，域断电时可能挂总线。现已修复，release `7.3.1-vim4-20261108`
设为 Mainline 默认，按单子系统门禁通过针对性测试和冒烟。正式身份见
[sources.toml](../../packaging/kernel/sources.toml)、
[installed proof](../../packaging/kernel/releases/7.3.1-vim4-20261108/installed-proof.json)
和[新 2372 基线](../../packaging/kernel/releases/7.3.1-vim4-20261108/baseline.json)。

## 改动

内核主线 `vim4-kvm-7.3` 从 `3facfaa3` 快进到 `3eab9050`，两个提交：

- `3eab9050d53eb` media: amlogic: vdec: keep regmap debugfs off unpowered DOS registers：
  - `precious_table` 把 0–0xfbfc（VDEC/HCODEC/VDEC2/HEVC 各自电源域，HCODEC 属 JPEG 编码器）
    排除出 debugfs，只留 DOS-top 0xfc00–0xfffc 共 256 行；
  - `max_register` 由越界的 0x10000 改为 0xfffc；
  - T7 映射建立时即 `regcache_cache_only`，`t7_bus_on()` 成功后关闭，`t7_power_off()` 开头重新打开。
    REGCACHE_NONE 下 cache-only 读返回 -EBUSY、不做 MMIO，debugfs 显示 `XXXXXXXX`。
- `a4bcaf3b71558` media: amlogic: vdec: drop a stale T7 opt-in comment。

两个提交 strict checkpatch 均 0/0/0；W=1 加固定 sparse 无新增诊断。
生产构建共 1168 条既有警告，amlogic 目录为 0；QEMU KUnit 67/67 通过。
config 与 `.42` 相同，模块文件集合相同，运行时 10 个文件与 `.42` 逐项相同。
包 SHA256 为 `3dc376aa370489172276218bebc0cec8e83ac1081b3df3f0d9d6a5c92b27e508`，
build ID 为 `e5b33474e34ac9eec34a8e357a2f25709e8e0715`。

## 上板

一张 40 分钟 FIFO 票，自然启动一次，UART 只有一个 U-Boot/Linux 启动，没有冷复位；
boot_id 为 `b00efed5-883f-40be-a573-4016f3ec5972`。
此前另有一张票，入场 proof 时停止，零上传、零安装：`.42` 基线中的
`vim4pd.py`、`vim4-manager-helper` 两个文件已按[管理器 PD 记录](2026-11-08-manager-pd-firmware-display.md)更新。
执行器只接受这两项的已记录 SHA，`.42` 旧收据不改。

- **入场**：其余 2370 项 proof 相同。`/boot` 只剩 46 MB，不够整包。
  `7.3.1-vim4-20261105` 启动目录（7 个文件，SHA 存于数据文件）已无 extlinux/kernels.json 引用，
  删除后可用 104448000 B；其 `/lib/modules` 及 Mac/VM 整包保留。
- **安装**：沿用现有 `register-runtime.py install`，只切 Mainline 的 LINUX/FDT，APPEND 逐字不变（含 `module_blacklist=fusb302`）。
  自然启动后，release、build ID、完整 2354 模块文件、已加载模块 build ID、config、启动文件均相符，
  fusb302 未加载。
- **被动 4K 视频**：首次即收到 300 帧，59.96 fps。

| 解码器状态 | debugfs 256 行 | runtime |
|---|---|---|
| 空闲 | 全 `XXXXXXXX` | suspended |
| 编码器在位时 open | `EBUSY`（K9），全 X | suspended |
| 停应用、卸 wave5/t7_jpeg 后 open | 0 行 X，`DOS_GCLK_EN0=0x3ff` | active |
| close 后 | 全 X | suspended |
| 每条解码后、编码器重载后 | 全 X | suspended |

解码冒烟时保持解码器原绑定：
- **HEVC**：WPP_A_ericsson_MAIN_2 48 帧、DBLK_A_SONY_3 30 帧、TILES_B_Cisco_1 100 帧，
  逐帧 MD5 与发布者整流 MD5 全部相同，status 0。
- **JPEG**：mjpeg-420/no-app/1080p 各 16 帧，长度和 SHA 与 `.42` 硬件输出相同。

随后正常 modprobe 恢复两个编码器并启动 one-kvm。窗口内增量内核日志无 WARNING/BUG/Oops/SError。
冒烟后被动视频 297 帧，59.37 fps。最后写入运行收据并抓取新 2372 基线，只清理本任务上传目录。

逐步结果和日志 SHA 见[数据](data/2026-11-08-vdec-dos-regmap-deploy.json)；
原始文件在 `logs/vdec-followups/deploy-1/`，入场停止那次在 `deploy-0-entry-mismatch/`。
两个 GStreamer registry 缓存文件为 root 0600，回传失败，不影响结果。

## 未验证

单子系统门禁之外的项目没有运行，包括：
- 九类回归、600 秒运动、HID 注入、EDID、音频、介质、GPU；
- HEVC/H264/MPEG2 全集。

HEVC 仍以[.42 全集](2026-11-07-vdec-integration42-pd-results.md) 127 Success / 3 Error / 2 内核 Timeout 为准。
这次只覆盖本树 debugfs 路径，没有把 DOS 窗口建模为父节点/syscon。
一次无冷复位的启动不能说明冷复位已修复。
