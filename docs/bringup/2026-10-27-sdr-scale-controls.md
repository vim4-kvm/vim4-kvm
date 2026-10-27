# 2026-10-27：超宽屏 SDR 硬件缩放与 JetKVM/PiKVM 尺寸控制

One-KVM 带填充行宽的 SDR 缩放改用公共 `vim4scale` GE2D DMA，替代 CPU 慢路径。
JetKVM 视频设置、PiKVM 视频菜单新增独立输出高度：原尺寸、480/720/1080/1440/1700/2160。
保持输入比例、不放大，不改 EDID 或 HDMI 输入模式。HDR 仍用 Mali/P010。

## 实现与部署边界

GE2D 的 canvas 宽使用实际 DMA 行跨度，矩形宽使用可见像素宽，输出带独立 VideoMeta。
缩放输出固定三个 codecmm 缓冲；停止/flush 唤醒等待，编码器持有的输出独立保留 fd。
目标不小于输入时直通原 DMA，不分配输出池、不执行 blit。
八位 HEVC 缩放宽向下对齐16，H.264和Main10宽向下对齐2。

实测发现 VDIN1 默认给 JetKVM/PiKVM 两个 DMA 平面；One-KVM 原本已选连续 DMA。
共用启动器在5.15统一设置 `GST_V4L2_PREFER_CONTIGUOUS=1`，7.3仍显式取消该变量。
采集包提供 `vim4-sdr-scale-api-1`，并依赖启动器的 `vim4-dma-capture-api-1`。
平台的 board/capture/encoder须一起升级，再升级三个应用包。

公共 `vim4h265src` 的 SDR 缩放也使用同一GE2D路径。保留 VDIN1 原尺寸采集，
避免其缩放宽度向下取64倍数造成超宽屏比例变化；0保持既有原尺寸路径。
PiKVM 在5.15的 JPEG/MJPEG及快照仍保留原尺寸，H.264/H.265分别缩放。
JetKVM保存JSON偏好；PiKVM保存 `/var/lib/kvmd/video-output-height` 并只重建视频组件。

## 测量方法

板子：`5.15.137-vim4kvm-hdrdual6`，HDMI接收服务始终为PID1081。
源端：Mac mini物理RTK HDMI屏，3440×1440p60 SDR及3840×2160p60 PQ。
接收端：本机Chrome headless，经管理器认证与SSH转发；WebRTC媒体走局域网。
没有重启内核或HDMI服务，没有调整EDID。性能采样与构建、独立编码测试串行。

每档预热后读取实际浏览器解码计数，抽取画面内的帧号及校验字节验证内容推进。
One-KVM每项采样约10秒，JetKVM/PiKVM每项约6秒；均为短测，不能证明长期稳定或光子延迟。
HDR同时核对浏览器VideoFrame的PQ/BT.2020，不能替代接收屏亮度验收。

## 已验证结果

同一3440×1440运动输入降到720p，One-KVM前后对照：

| 编码 | 旧CPU路径 | GE2D路径 | 实际输出 |
|---|---:|---:|---|
| H.264 | 35.36fps | 59.90fps | 1720×720 |
| H.265 | 25.07fps | 59.87fps | 1712×720 |

两种编码均20次有效且不同的运动帧号，解码丢帧和freeze增量为0。
独立合成图检查3440可见宽/3456行跨度，输出1720和1712宽、1728行跨度，
有毒输入填充未混入画面，亮度、NV21→NV12色度与PTS通过。吞吐仅代表GE2D阶段。

| 应用/链路 | 输入与档位 | 实际解码率 |
|---|---|---|
| JetKVM WebRTC SDR | 超宽屏，H.264/H.265各720/1080/原尺寸 | 59.84–59.95fps |
| PiKVM WebRTC SDR | 超宽屏，H.264/H.265各720/1080/原尺寸 | 59.52–59.97fps |
| JetKVM WebRTC HDR | 4K PQ，480/720/1080/1440/1700/原尺寸 | 59.95–60.15fps |
| PiKVM WebRTC HDR | 4K PQ，同上六档 | 59.91–60.09fps |
| PiKVM Direct HDR | 4K PQ，同上六档 | 59.80–60.08fps |

上述档位每项12次有效且不同的运动帧号。JetKVM设置页和PiKVM菜单的选择器实测生效。
HDR输出分别为852×480、1280×720、1920×1080、2560×1440、3022×1700、3840×2160。

原尺寸直通的首次实测发现多持有输入引用，耗尽采集池，后续重开编码器还出现CMA分配失败。
按BaseTransform的同缓冲引用转移契约修正，补充关闭DMA fd的回归检查：修正前失败、修正后通过。
JetKVM复测4K SDR的1700/2160两档、H.264/H.265均59.88–60.03fps，运动帧号持续推进。
PiKVM相同四项复测59.85–60.00fps，均12次有效且不同的运动帧号。
另以4K PQ输入转SDR重跑JetKVM的1700→2160切换，两档约60fps，未再出现连续内存分配错误。
最终插件重测One-KVM超宽屏720p，两种编码均59.96fps，20次帧号有效且不同，无解码丢帧或freeze增量。

## 离线验证与记录

采集Meson测试含真实transform协商、带填充DMA、错误布局拒绝、输出持有生命周期、
原尺寸直通及输入DMA释放；公共HEVC源测试检查SDR保留原始采集尺寸、偶数高度与HDR链路。
JetKVM Go测试、两个目标go vet、设备UI构建及部署助手测试通过。
One-KVM库测试789通过、3忽略，release构建通过。PiKVM部署/API测试23项通过。
PiKVM离线浏览器验证真实HEVC解码/重连，以及尺寸菜单发送数字值、状态广播不回写设置。
主仓库离线测试共282项，7项跳过，其余通过。源码固定于本次更新的 `workspace.toml`。

本地原始记录：`build/sdr-scale/`，含构建/测试、像素对照、前后浏览器结果和配置快照。
板上回退：`/var/backups/vim4-sdr-scale-20261027/`。本次不包含7.3硬件验收、
Safari、UU客户端或长时间运行测试。
本轮为候选文件部署，未新建组件包或发布Release；板上dpkg版本仍为原正式版。
收尾恢复One-KVM、原配置及Mac模式111（4K60 HiDPI，HDR关闭），移除测试图与临时尺寸偏好。
