# 2026-10-21：7.x VDIN 缩放与硬件 MJPEG

7.3 已接通 VDIN 硬件下采样、HCODEC JPEG 和 One-KVM MJPEG。真实 4K60 运动输入下，
H.264/H.265 网页原生 4K60、1080p60 通过；硬件 JPEG 原生 4K 约 47fps，
1080p/720p 达到 60fps。4K MJPEG60 未达到，不能把采集 60fps 当作编码 60fps。
缩放保持物理 HDMI 3840×2160 时序与原 EDID，截图跟随当前采集输出尺寸。
默认 5.15 启动项、生产应用和系统编码插件保持原样。

## 实现与固定版本

- 内核 `50e811ce861f0acfc64d788b7627cd5b13569e46`，包含 VDIN 缩放提交
  `294ca351efdc5`：区分输入时序与输出几何，设置 HSC/VSC 相位与滤波系数，
  DMA/MIF 使用输出尺寸，STREAMON 仍校验物理输入时序。
- One-KVM `c1e7b88d91cf5ff90560cc8a2f832a652da0827b`：按输出尺寸设置采集和编码 caps，
  保持 Wave5 DMA lease；MJPEG 使用私有 `vim4jpegenc`，7.x 不静默降级软件编码。
- 新 `t7-jpeg` 驱动提供 `/dev/jpegenc`，接受有界 NV12/NV21 和连续 DMA-buf，
  等待生产者 fence，完成后停止输入引擎再释放导入。关闭先完成安全断电，再回收 DMA；
  断电失败则隔离分配并固定模块，避免硬件继续访问已回收内存。
- HCODEC 时钟与 OP-TEE/boot-completion 接入随内核保存。签名固件由既有厂商包及
  `tee-supplicant` / `video-firmware-preload-khadas` 装载，不把许可固件放入 Git。
  edge 服务显式等待预加载成功后再启动。

Image、完整模块包、板用 DTB、插件和固件哈希固定于
[sources.toml](../../packaging/kernel-edge/sources.toml)。模块 2334 个，保留 split BTF；
测试内核 build ID `cd02c1e079f4fbdf65395d337677824762e1e121`。
最终应用 SHA256 `9520b8005a94a553fd544fc36fa0415e0eb71e1fd0c9c40c2bad34f017cf89c7`。
板用 DTB 含本板 MAC；其哈希不是其他板子的通用安装产物。

## 接入时修正的问题

1. T7 固件宣称支持动态共享内存，但运行时配置可能关闭，普通 RAM 调用参数被拒绝。
   T7 专用 compatible 查询实际配置，不启用时采用固件保留共享内存；其他平台不变。
2. HCODEC P1 虽能显示 666.7MHz，安全固件加载仍触发 SError。指定 P0 后加载成功；
   两次失败启动自动回到默认 5.15，未把失败候选作为最终可用版本。
3. 新内核 DMA-buf map/unmap 接口要求 reservation lock；改用 unlocked helpers，
   离线导入测试覆盖该 API 约束。最终完整模块重启后 taint 为 0。
4. 网页保留自己选择的 codec。测试工具从外部改 codec 前先释放旧页，再加载新页；
   同 codec 的尺寸/帧率切换保留页面。不能把测试控制竞争当作编码驱动故障。

OP-TEE 的 RPMB PTA 查询仍有不支持日志；本轮验证安全视频固件装载，不宣称完整 TEE 功能验收。

## 实板结果

源为 Mac 物理 `VIM4-UHD-60` 显示器上的运动场景，三条横向带编码同一帧号，
避免只确认解码帧数却遗漏冻结、裁切或上下帧混合。HCODEC 使用 P0 666666656Hz。

`tools/edge-jpeg-check.py` 六次各 180 帧，逐轮销毁管线：

| 输出 | JPEG 质量 | 帧率 |
|---|---|---|
| 3840×2160 | 50 / 80 / 100 | 46.82 / 46.69 / 45.75 |
| 1920×1080 | 80 | 60.00 |
| 1280×720 | 80 | 60.00 |
| 返回 3840×2160 | 80 | 46.68 |

每轮 JPEG IRQ 增长，DMA-buf 归零，CMA 回到约 505200KiB（小幅采样波动），taint 为 0。
首尾 JPEG 均可解码，三条标记完整、帧号一致并持续推进。

排除 Python 观察器后，原生 C 基准预热 30 帧、测量 300 帧，4K 质量 80：
46.839fps，进程 CPU 7.70%（单核 100%），source→encoder 中位 0.009ms，
encoder sink→src 中位 20.139ms、P95 21.295ms。后者包含驱动、插件和压缩输出复制，
不是纯硬件时间。单轮结果定位当前瓶颈，不替代三轮性能比较或功耗测量。
没有尝试超频来宣称 4K60，也没有完成与 5.15 的同条件多轮对齐。

网页 SDR 和 HDR 矩阵覆盖 H.265 原生→1080p→720p→原生、H.264 1080p→720p→原生、
MJPEG 1080p/720p/原生及返回 H.265。实际协商的 H.264/H.265 在 60fps 档约 60fps，
30fps 档约 30fps；MJPEG 网页以 30fps 请求，约 30fps，不能据此声称网页 MJPEG60。
最终 HDR 矩阵每阶段均核对 RX `hdr_input=1`、`hdr_capture=1` 与输入 3840×2160，
同时检查实际解码尺寸和三带运动帧号。结束恢复模式、尺寸、质量，DMA 归零。

UU 开启时原应用不允许 MJPEG。测试仅在 UU 无连接、无会话时临时关闭，结束恢复；
这一现有产品约束保留。支持 HDR 输入映射到 SDR JPEG，不输出 HDR JPEG。

## 验证与证据

- Rust：723 通过、2 忽略；前端：9 通过、构建成功。全局 rustfmt 检查仍有原先其他文件的
  格式差异，未为本任务重排无关代码。
- VDIN/RX 离线 C 回归 11 组通过；新 JPEG codec/命令边界、100 档质量、ASan/UBSan、
  DMA 导入失败与引用生命周期回归通过；原生基准 C 回归通过。
- 最终 kernel Image/dtbs/modules 构建通过，整套匹配模块上板，最终应用及服务依赖已部署。
  没有完成该新组合的隔夜长测、强制断电/编码中杀进程或整机休眠验收。
- 主仓库离线测试 130 项，125 通过、5 项因本机依赖缺失跳过。启动器回归检查预加载失败
  和未完成时不加载视频模块，并在限定次数后退出。
- 旧版应用、默认 `/boot/Image`、extlinux 配置、系统 JPEG 插件、HDR EDID/曲线受保护，
  未用本轮新结果覆盖此前配置的长测、音画漂移或端到端延迟结论。

本地未入库证据：`logs/kernel-edge/jpeg-dma-scaling2.log`、`jpeg-frame-integrity.json`、
`jpeg-native-q80.json`、`jpeg-final-native-build-tests.log`、`scaling-web4.jsonl`、
`scaling-final-hdr.jsonl`、`scaling-final-app-build.log`、`scaling-driver-full-tests.log`。
测试工具及部署文件入库；本板备份在 `/var/backups/vim4-onekvm-edge-20261021-jpeg/`。
