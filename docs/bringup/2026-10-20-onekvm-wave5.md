# 2026-10-20：One-KVM 接入 7.3 V4L2/Wave5

摘要：独立安装的 One-KVM 已在 Chrome 播放固定 RGB8 HDMI 输入的 4K60 H.264
和 H.265。码率切换测试暴露了 CMA 分配失败后重复释放 DMA 的驱动错误，板子曾
挂死并需 RESET。已提交修复及故障注入回归；不能把首次出画面当作稳定性验收完成。

## 隔离与恢复

- 默认仍启动 `5.15.137-vim4kvm`，原服务、程序、数据库和插件保留。
- 实验程序 `/opt/vim4-onekvm-edge/one-kvm`，数据 `/var/lib/one-kvm-edge`，
  回环端口 8082；原服务使用 8081。
- [实验服务](../../packaging/kernel-edge/one-kvm-edge.service) 同时检查匹配的
  `7.3.0-rc7-vim4kvm-uhd1+` 与 `vim4.one_kvm=1` 启动参数。5.15 下跳过，
  不通过 Conflicts 停止生产服务。
- 一次性选择 `OneKvmTest` 启动项；该项屏蔽生产 KVM、HDMI、USB/PD 服务，
  只启动实验视频服务。普通重启回默认 5.15；内核挂死时软件重启没有恢复保证。
- 启动准备器校验 Wave521c 固件和 UHD EDID，再加载固定 UHD60/NV12 驱动。
  固件及私有 GStreamer 插件依赖见 [前轮编码记录](2026-10-19-wave521-uhd.md)。

生产文件及 SQLite 一致性备份位于板上
`/var/backups/vim4-onekvm-edge-20261020/`，含受保护文件 SHA-256 清单。
这些备份不进入 Git。RESET 回 5.15 后已核对 `/boot/Image`、原应用、兼容分配器
和生产服务文件哈希未变；应用、管理器、HDMI、gadget、PD 服务均 active，UDC configured。

## 实现与版本

源码锁见 [sources.toml](../../packaging/kernel-edge/sources.toml)。One-KVM 新增
`VIM4_VIDEO_BACKEND=wave5`，默认仍为 vendor；Wave5 启动拒绝生产数据目录及
非 7.x 内核。按 sysfs 设备名称发现采集与编码节点，不固定 video 编号。
前端继续使用逻辑视频设备，底层采用 V4L2 DMA-buf 导入。

Rust appsink/appsrc 桥接为同一 NV12 分配建立两个平面视图，并用 ParentBufferMeta
保留采集池租约。1080p 分配容量允许 1088 行对齐，UV 地址仍在有效 Y 数据之后。
桥接不复制像素；VDIN 私有 cached 环到 vb2 缓冲仍有内核复制。

实验数据默认禁用 HDMI 音频及 USB 功能，拒绝调用旧版 EDID/HDR/USB 写接口。
目前只接受 H.264/H.265，缩放与 MJPEG 未接入。固定 UHD60 模式不代表自动时序识别。

Linux `48356a59f03d` 增加 V4L2 强制关键帧控制，命令中强制类型值为 3（IDR），
不能与输出报告的 `PIC_TYPE_IDR=5` 混用。
Linux `aa68a1aade1c` 修复编码辅助 DMA 所有权：所有分配成功后才交给实例；
SET_FB 提交后，即使命令失败，也必须先停止固件才能释放辅助及重建缓冲。
Linux `702421daa1a1` 按 H.264 NAL 5、H.265 NAL 19/20 标记 IDR，并清除复用
缓冲的旧帧型标记；否则 GStreamer 无法完成 H.264 强制关键帧请求，后续请求被合并。

## 网页结果与边界

Mac Chrome `155.0.8059.85`，真实物理 HDMI 桌面上的运动源，20 Mbps，GOP 60。
通过 SSH 转发到实验端口，使用 `one-kvm-smoke.mjs --exclusive --local-backend`。
该选项只允许显式 HTTP 回环地址；正常管理器登录仍要求密码。

| 格式 | 20 秒解码 fps | 解码丢帧 / 网络丢包 / freeze | 呈现间隔 p99 / 最大 |
|---|---:|---|---|
| H.264 | 59.989 | 0 / 0 / 0 | 40.9 / 53.5 ms |
| H.265 | 59.990 | 0 / 0 / 0 | 65.4 / 83.6 ms |

证据：`logs/kernel-edge/onekvm-edge-h264-browser.json`、`onekvm-edge-h265-browser.json`。
两者均有较长呈现间隔，平均 60 fps 不等于已对齐 5.15 的流畅度。
H.264 浏览器画布抽样 151 个运动帧号，invalid/incoherent 均为 0，见
`onekvm-edge-h264-coherence.json`；这是抽样，未检查每个视频帧，也不是光学延迟。

首次码率切换失败，不能计为通过。`onekvm-edge-full-reconfigure-failure.log`
记录 CMA 剩余约 19 MiB、申请约 9.4 MiB 失败，局部回滚和实例关闭先后释放相同
辅助缓冲，随后出现 vunmap/cma_release 告警和页分配器 Oops。普通 reboot、定时
回退和串口 SysRq 均未能恢复，用户 RESET 后回到默认 5.15。
CMA 耗尽随后定位到 GStreamer，而非重建帧释放循环缺失。1.24.2 的编码器只在
缓冲池首次启用时释放临时引用，后续每帧遗漏一次 unref。独立 videotestsrc 编码
100 帧后，leaks tracer 显示输入缓冲池 ref-count=100；每次重建残留一个设备句柄。
另一个 EOS 错误在返回空 LAST 缓冲时先清除 QUEUED，STREAMOFF 因而遗漏回收，
导致没有视频 fd 时仍残留整组 MMAP 分配。分别用
[缓冲池补丁](../../packaging/kernel-edge/gstreamer-v4l2-pool-lifetime.patch) 和
[EOS 补丁](../../packaging/kernel-edge/gstreamer-v4l2-eos-buffer.patch) 修复。

三轮 EOS 图案测试修复前逐轮损失 128 MiB CMA；修复后 H.264/H.265 各三轮、
每轮 120 帧，视频 fd 均为 0，CMA 固定 469736 KiB（初始 469760 KiB）。
见 `onekvm-cleanup-lifecycle-final.json`；可通过
`tools/wave5-lifecycle-check.py --exclusive --cycles 3` 重跑。测试停止应用后使用
图案源，不代表 HDMI 采集、颜色或端到端性能验收。该轮故障定位曾触发 CMA 分配
WARN，taint=512；没有重现重复释放/Oops。后续需在全新启动后复核无新告警。

私有插件需要对前轮固定的 gst-plugins-good 1.24.2 源码依次应用 offset、pool lifetime、
EOS buffer 三个补丁，再 `ninja -C ../gst-build`。不替换系统插件；修复版私有插件
SHA-256 为 `0112fdd70ca2a618eb453bd42be982e7a10d66992d93a38af2cbe12440f1bf8f`。

修复私有插件后，原失败的网页测试已通过：同一 peer 切换 8000/20000 kbps，实收
约 8.07/21.07 Mbps，均约 59.96 fps；红绿蓝检查通过。三次网页重连各继续解码
119–120 帧/2 秒，MJPEG 请求被拒绝且 H.264 配置保留。退出后 DMA-buf 数量为 0，
CMA 回到 469760 KiB。证据为 `onekvm-edge-browser-features.json`；该轮仍使用
`aa68a1aade1c` 内核，尚未含最终的 H.264 帧型标记修复。

回退后的旧版网页 10 秒验证为 59.961 fps，丢帧、丢包、freeze 均为 0；
呈现间隔 p99 21.9 ms、最大 23.0 ms，见 `onekvm-production-after-reset.json`。

## 离线验证与待办

- One-KVM：`cargo test --locked --features vim4 --lib`，717 通过、1 ignored；
  ARM64 release 构建通过。Linux 中板级 helper 的 23 项测试通过。
- 默认 Rockchip 功能构建受 Ubuntu FFmpeg 缺少 RKMPP 枚举阻挡；未修改该路径，
  不能声称默认构建通过。
- 内核实际函数提取测试 `test_encoder_cleanup.py`：32 组分配/命令失败及关闭所有权
  检查，启用 ASan/UBSan；旧代码在该测试中触发重复释放，新代码通过。
  `test_buffers.py` DMA 平面范围及偏移检查通过；完整 Image/dtbs/modules 构建通过。
- 长时间测试、低 CPU、动态 HDMI、音频、USB 及发布安装流程另行验收。

## 最终内核复测

最终内核为 `702421daa1a1`，Image SHA-256
`f912fcf358bdd3724c3893d539264d42a082a0d2a72a6e102db7206c973299b3`，
2333 个模块均由同次构建安装，模块归档 SHA-256
`267b74603b29aa45c4ddaef27ebc064a4e7dcdcea10908884acab98d7cacb7b4`。
实验程序代码来自 One-KVM `34df7ad5ca88`，`e56c28e3b152` 仅补充插件依赖文档。

4K60 两种格式各 240 帧，GOP 1000，分别在第 80/160 个已编码帧后发出关键帧请求。
H.264 实际请求 84/162，IDR 为 85/164；H.265 请求 83/161，IDR 为 85/163。
GOP 长于片段，排除周期 IDR。见 `onekvm-idr-h264-final.log` 和 `onekvm-idr-h265-final.log`。
两段转到构建 VM 软件解码后，全部 480 帧运动标记和颜色检查通过，见
`onekvm-idr-h264-verify.json`、`onekvm-idr-h265-verify.json`。

网页在最终内核上再次通过 8000/20000 kbps 切换（59.950/59.971 fps）、三轮重连和
颜色检查；见 `onekvm-edge-browser-features.json`。一次此前尝试遇到运动源定时退出，
画面为白色，已明确判失败；重新运行运动源后才通过，没有放宽检查。

该轮开机早期 PHY 初始化曾超时。源端稳定在 UHD60 后，停止实验应用并重新加载
接收/采集模块恢复，video 编号发生交换。准备器现在检查真实驱动绑定，避免 modprobe
返回成功却未 probe 成功；注册缓存改到 `/run/one-kvm-edge` 并在准备时清除，防止
GStreamer 工厂沿用旧编号。自动处理协商和时序切换仍属动态 HDMI 适配，尚未完成。

最终内核的独立 H.265 网页 10 秒测得 59.982 fps，丢帧/丢包/freeze 为 0；
呈现间隔 p99 64.9 ms、最大 76.6 ms，见 `onekvm-idr-h265-browser-isolated.json`。
独立 H.265 运动抽样 114 帧号，invalid/incoherent 均为 0，见
`onekvm-idr-h265-coherence-isolated.json`；此前两个浏览器测试有过短暂重叠，
不使用该次重叠结果作为独立性能或 H.265 一致性结论。

最后再次停止应用，H.264/H.265 各三轮 120 帧 EOS 启停通过；每轮无视频 fd，
CMA 固定 469736 KiB，初始 469776 KiB，没有累计增长。
`onekvm-idr-lifecycle-final.log` 同时记录内核 taint=0，dmesg 未出现分配失败、
WARN 或 Oops。主仓库离线测试 99 项通过（4 skipped）。

结束时正常重启回 `5.15.137-vim4kvm`，未再需要 RESET。原应用、管理器、HDMI、
gadget、PD 服务均 active，UDC configured；实验服务因内核条件不匹配而跳过。
生产四个受保护文件哈希再次全部吻合备份。旧版网页重新解码 3840×2160 H.264，
8 秒采样约 60 fps，丢帧/丢包/freeze 为 0，见 `onekvm-production-final-return.json`。
该回退检查未注入键鼠，也未验证 HDMI 音频。
