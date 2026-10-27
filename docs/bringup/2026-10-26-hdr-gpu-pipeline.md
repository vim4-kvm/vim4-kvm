# 2026-10-26：GPU 转换、DMA Main10 与网页真 HDR 60fps

## 结果

5.15 One-KVM 原尺寸4K60 PQ输入，保留 HDR 的 H.265 Main10 网页从约34–35fps提升至约60fps。
链路为 VDIN0 AMLY → Mali Vulkan 小端解包/P010 → 连续 DMA-buf → Wave521 DMA_TYPE → WebRTC。
本轮不改内核、EDID、HDMI OUT，也不重启板子。

同条件对照：Mac mini 物理3840×2160p60、真实PQ，运动网格、三处带校验帧号、RGB色块；
5.15.137-vim4kvm-hdrdual6，Main10 30000kbps、目标60fps，输入源始终保持HDR开启。

| 路径/端点 | 吞吐 | 编码入口→输出 |
|---|---:|---:|
| 同版插件强制 CPU 转换/VMALLOC，240帧 | 34.764fps | 平均28.690ms |
| GPU/DMA 独立链路，1200帧 | 60.001fps | 平均12.695ms，p95 12.856ms |
| One-KVM 网页 HDR 转 SDR 开→关→开 | 59.974 / 60.017 / 59.962fps | 另见下面运行统计 |

独立链路去掉前30帧预热；按首末帧序号差和 CLOCK_MONOTONIC 时间差算吞吐。
首次合并stdout/stderr日志有一条帧行被插入打断，不能用解析行数当实际帧数；后续分开保存。
1200帧版本为最初四槽输出池、不含快照；最终双槽/并行快照以网页和运行统计为准。
这是编码/吞吐验证，没有重测光学端到端显示延迟，不能把阶段耗时差直接当成端到端收益。

## 实现与所有权

- `gst-plugin-vfmcap 99433a9d`：GPU shader按实际输入行宽读取小端 Cb,Y0,Cr,Y1，
  相邻两行色度向上取整平均，输出标准高位P010，保持PQ/BT.2020标签。
  不做HDR曲线。输出pitch按64字节对齐，UV在pitch×height。
- Vulkan只接受真实Mali-G52及DMA导入能力；输入和输出导入都使用dup(fd)，
  每帧 EXTERNAL acquire/release、fence、释放导入、device idle 后才归还采集帧。
  不缓存原始输入导入，避免其持有dma-buf耗尽VDIN池。
- 连续 `heap-codecmm` 输出池固定两槽，4K共49,766,400字节；创建时预分配，
  不在编码器200MiB工作区打开后无限增长。flush唤醒阻塞获取，停止不提前关闭仍被持有的fd。
  半途分配失败必须显式清空已预分配缓冲；GStreamer基类start失败不会自动stop。
- `gst-plugin-venc 0cd588d0`：支持单fd、零offset、真实pitch的P010 DMA输入，
  不CPU映射；不兼容布局保留VMALLOC路径。输入GstBuffer按SDK退休fd保留，
  错误/停流/重配先destroy编码器，再释放未退休输入。两槽预算依赖当前SDK低延迟配置，
  每次同步完成编码即退休当前输入；运行统计验证peak=1、pending=0。
- `One-KVM 4f473f54`：HDR队列降至一帧；专用SDR快照通道仅为JPEG消费者预留缓冲，
  V4L2实际申请由10帧减到7帧，保留3840×2160输入。普通SDR编码通道仍用原预算。

`gpu-conversion=false`可强制CPU对照；GPU/连续内存初始化失败时回退CPU。
已提交GPU任务出错则报流错误并清理，不能把未完成像素送给编码器。

## 连续内存问题与失败尝试

最初四槽GPU输出约100MB，独立编码可跑60fps，但网页带原快照池时，
编码器无法申请连续200MiB；`web-hdr.log`为失败记录。
VDIN0固定十帧约237MiB、编码工作区200MiB、原VDIN1快照十帧约119MiB，
再加GPU四槽约95MiB，超过580MiB codec CMA的可用布局。
codec_mm自己的已分配计数不包含VB2直接申请的快照内存，不能仅看它的free值。

最终保留两槽重叠，并单独减少HDR快照下游预算；V4L2还会叠加驱动最小缓冲数，
所以不能把allocation query中的3直接当成实际只分配3帧。
网页期间dma-buf可见：两个P010、七个NV21及一个既有DRM heap-gfx对象，合计153,460,736字节。
`heap-gfx`虽独立连续，但当前位于4GiB以上；SDK的PhysicalAddress为Uint32，
不能直接改用它，否则编码源地址截断。未移动CMA区域或改驱动。
源端HDMI实际HDR/SDR切换的历史分配问题未在本轮修复；本次开关测试是网页输出转换。

## 像素、快照与生命周期验收

独立 `amly-gpu-compare` 在真实Mali上通过12组极值/随机样本、行宽padding、
NEON尾部、工作组边界及1440p/超宽/4K，与现有CPU输出逐字节相同，输出padding不被覆盖。
历史实际4K AMLY帧（9600-byte pitch）也通过同帧比较。
初次把page-aligned导出文件当成必须恰好等于可见行长而拒绝；测试器现接受可见长度到页对齐尾部。
该对照的CPU映射来自uncached heap，耗时不能与生产cacheable采集转换直接比较。

网页开→关→开每轮20个推进帧号，三处一致，无校验失败，RGB主色顺序正确；
HDR为H.265 profile2、PQ/BT.2020，SDR为profile1、BT.709。
三次HDR网页重连均约60fps，测量窗口无新增丢帧/冻结；每轮同时通过One-KVM MCP截图，
JPEG中三处帧号一致，返回1920×1080图像、源尺寸仍为3840×2160。
另外三次主动关闭/重开HDR输出，强制重建GPU上下文及缓冲池，均约60fps，
每轮20个运动帧号一致、无新增丢帧/冻结，未重启板子。
没有进行HDR光度/显示器亮度验收，SDR canvas的PQ映射不能代替它。

临时 `VIM4_VIDEO_TIMING=1` 运行统计中，2640帧全部DMA输入、CPU输入0、
pending_peak1/pending0，SDK encode均值12.659ms；GPU import0.532、dispatch0.107、
wait7.226、free/idle0.255ms（累积均值）。生产不启用计时。
停止测试后只剩既有heap-gfx对象16,588,800字节，未残留GPU输出/VDIN1导出；
内核taint沿用12800。已移除临时计时配置并重启应用，两个服务均active。

离线：ARM64 Meson四项、SPIR-V校验通过；buffer pool测试覆盖阻塞获取时flush唤醒、
持有输出跨deactivate及半途申请失败清理。Main10 fake codec覆盖无法CPU映射的DMA、
真实padding、延迟退休、CPU交替、错误/停止/重开及可选计时。
One-KVM Rust783通过、3忽略，release构建通过。
主仓库离线278项通过、7项跳过。

## 构建、部署与证据

Ubuntu构建加入 `libvulkan-dev glslang-tools`，Meson编译shader并嵌入插件；无Vulkan开发依赖
时仍可构建CPU版本。捕获包依赖libvulkan1并提供完整对应源码目录。
编码包按固定URL/SHA携带私有r44p0 Mali库，记录上游CLOSED标记，不替换系统EGL/GLES链接。
5.15 One-KVM启动器选择私有ICD，7.3启动器清除它；其他应用仍使用原视频路径。
在ARM64容器中用已验证产物组装两个组件deb，解包md5、私有ICD位置和Mali固定哈希通过；
从采集包内附源码重新构建插件并运行Meson四项通过。没有重建完整Docker镜像/系统镜像。

部署SHA256：

- capture：`1e221c9e5e422a8ddb03cdf6daa5df51595cd5c083a36d85c19a58193e326d2b`
- Main10：`5820350255375216b8b7848fa35921b38e99e46d3b68d6f899542c445cee449c`
- One-KVM：`df136324b31fa4b819860aa29cdf51b659a150b718adbd43f43445f45aa986c6`

生产SDK仍为先前P010修复版本，未安装临时SDK计时库。
板端 `/var/backups/vim4-hdr-gpu-20261026` 保存三个旧二进制与旧启动器；
停应用、恢复对应文件后重启应用可回退。内核仍为旧模块8b300e74，boot ID沿用
`5c6b0cb6-2523-43fe-a4a4-c2cbdb0850f5`。

忽略目录 `build/hdr-gpu/`：`compare-synthetic.log`、`compare-captured-visible.log`，
`full-cpu-control.log`、`full-gpu-long.log`、`full-gpu-long-stderr.log`，
`web-hdr-budget.log`、`web-hdr.png`、`web-hdr-reconnect-mcp.log`、`snapshot-hdr-*.jpg`，
`web-hdr-recreate.log`、`runtime-timing-and-release.log`，
`capture-gpu-budget-build.log`、`onekvm-gpu-budget-build.log`、`package-validation.log`、`root-tests.log`。
本轮未测试官方UU客户端、7.x Main10和HDMI OUT；高刷/超宽GPU只做独立同帧像素检查。
