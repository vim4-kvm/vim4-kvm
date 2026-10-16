# 2026-10-16：4:4:4 采集接口实现与生命周期修复

- common_drivers `a20928655`：8-bit YUV444 以自定义 fourcc `VUY3` 暴露，
  单平面 Cr/Cb/Y、canvas stride；加入格式枚举。同步停止与交付，
  vb2 buf_cleanup 释放已完成/已出队缓冲的导出引用，修复关闭设备后模块引用泄漏。
- gst-plugin-vfmcap `46a54c3`：识别 VUY3，连续拷贝到缓存内存后用 ARM64 NEON
  重排为标准 `v308`，保留每个像素的两路色度；NV21/NV12/UYVY 维持零拷贝。
  HDMI 脚本新增 `HDMI_CAPTURE_FORMAT=YUV444`，默认仍为 NV21。
  此为共享采集配置，未添加 UU 真彩按钮、编码切换或 4:4:4 硬编码声明。
- 使用独立名称 `vfm_check`、`video_nr=73` 在当前 5.15.137-vim4kvm 内核实测，
  不替换已加载或磁盘上的正式驱动。ARM64 模块、GStreamer release 构建通过；
  重排测试覆盖 SIMD 与尾部、非对齐、带填充行以及原地转换。
- 最终生命周期程序分别在 YUV444 和 NV21 下完成 30 轮，共 60 轮：
  同时保留 DONE 与 DEQUEUED 缓冲，覆盖直接 close、STREAMOFF 后 close、
  REQBUFS(0)，并持有独立导出 fd 到设备关闭后继续 mmap/read。
  两种格式的测试后模块引用均归零，最终 rmmod 正常完成。
- 4K v308 → fakesink：release 版本输出 300 帧耗时 22.701 秒，约 **13.2fps**。
  保存帧的字节序为 Y/Cb/Cr；红/青单像素纵条纹为 `(62,103,240)` /
  `(188,153,16)`，横条纹为 `(188,154,16)` / `(63,102,240)`，
  与原始 DMA 实测对应，未损失横向或纵向色度。
  未优化构建及直接对 write-combine 内存执行 NEON 重排的 release 版本，
  均未在 75 秒内输出 1800 帧。当前 CPU 全帧读取/重排路径不满足 4K60，
  不能拿此前只采样标记的原始 DMA 60fps 结果代替应用吞吐。
- 4K NV21 → fakesink 回归：300 帧耗时 5.014 秒（含启动），约 59.8fps；
  结束后模块引用归零。两条路径均未包含编码或网络，未进行端到端 UU 真彩验收。
  后续达到应用 4K60 需解决原始格式直接消费或硬件转换，并单独验证编码能力。
- 收尾：新测试模块已正常卸载，原 NV21 采集、One-KVM、管理器恢复，HTTP 200，
  近期内核日志无 BUG/Oops/panic。此前泄漏的旧 `vfm_probe` 仍待正常重启清除；
  未强卸载、未重启、未部署新内核或插件到正式路径。
- 证据：`logs/capture444/check-debug.log`、`check-release-direct.log`、
  `check-release-copy.log`、`check-final-regression.log`、`v308.raw`、
  `v308-pixels.json`、`implementation-restored.log`；测试入口随驱动和插件提交。
