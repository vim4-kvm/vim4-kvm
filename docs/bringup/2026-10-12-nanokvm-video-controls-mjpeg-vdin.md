# 2026-10-12：NanoKVM 原版视频控件、MJPEG 与 VDIN 缓冲区释放

采用最小侵入适配：继续使用 NanoKVM 原版屏幕菜单、设置窗口和传输模块。
新增 1280×720、1920×1080、3840×2160 的采集分辨率选项；原有码率、GOP、
FPS、JPEG 质量接口接到 VIM4 后端。H.264 仍用 amlvenc，码率限制 1–12 Mbps，
GOP 1–200，FPS 0（跟随输入）或 1–60。UI 滑块结束操作后再重配编码器。
全局参数写入 `/etc/kvm/video.json`；分辨率写入 HDMI 服务的 EnvironmentFile。
受限 root helper 仅接受三档分辨率，Web 服务仍使用 khadas 用户。

MJPEG 复用原版 HTTP multipart 实现，修复由后台线程写已取消请求响应的问题：
请求自己写响应，每个观看者只排队最新 JPEG。旧模式退出不会关闭新模式的编码器。
连续硬件 JPEG 测试只得到 4 帧后停住，因此使用软件 JPEG，最高限制 10fps；
4K 实际速度低于这个上限，不宣称 MJPEG 4K60。

反复切换发现 codec CMA 泄漏：NV21 使用两个 canvas ID，canvas 初始化会缩小
`vf_mem_max_cnt`，停止时却按缩小后的数量释放已分配缓冲区。剩余缓冲区逐次泄漏，
最终日志出现 `Failed to alloc dma buffer amvenc_multi`。修复遍历全部非空分配槽位，
释放后清空指针；修改限于 `vdin_canvas.c`，提交 `common_drivers:a0d3a8546`。

VM 使用既有 gcc-12/5.15.137-vim4kvm 配置增量构建 modules，安装 `aml_media.ko`
并更新 initramfs。第一次重启打断了 initramfs 更新，仍加载旧模块；随后完整重跑
update-initramfs、等待退出成功再重启。新模块 build-id 已通过 sysfs 核对为
`f7adab7ca175365865683fa578a8decf9757e84a`，boot-id
`89911371-09a6-4e5e-9f7c-f7b484fd3e3f`。临时 `.new`/`.dpkg-bak` 已由成功更新清理。

验证：

- 重启保留 1080p；NanoKVM、HDMI、PD、gadget 均 active，UDC=configured。
- Chrome 连续 10 轮 720p→1080p→4K（30 次切换），每次实际解码尺寸正确。
  每轮回到 4K 时 DriverCma 始终 378792 KiB，与基线一致；CmaFree 约 1331288 KiB。
- 原版菜单的三档分辨率、MJPEG/H.264 切换及原版设置 FPS 滑块已实测。
- 30fps H.264 在切换过渡结束后，两个 5 秒窗口分别增加 150、151 帧。
- 两个同时连接的 4K MJPEG 客户端各在 6 秒内收到 34 帧、12279704 字节。
- ARM64 Go 全套测试、VIM4 后端和原版目标编译、前端 TypeScript/生产构建通过。
  新增测试覆盖无效参数不改变采集、JPEG 可解码、旧传输不关闭新会话、慢 MJPEG
  观看者不阻塞其他观看者。未宣称 Go race 检测通过，板上 VMA 限制仍存在。

用户确认只连接 HDMI 和 USB-C，USB-C 同时供电和传输。完整功能接入仍在进行；
音频、虚拟介质、终端/脚本、网络与应用管理等剩余项见 NanoKVM-Pro/VIM4.md。
缺少的 ATX、外接串口、屏幕和灯带应报告未配置，不能映射到无关 GPIO。
