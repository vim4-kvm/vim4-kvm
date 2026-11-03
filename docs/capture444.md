# 4:4:4 采集

`tools/hdmi-setup.sh` 接受 `HDMI_CAPTURE_FORMAT=NV21`（默认）或 `YUV444`。
该设置属于共享 HDMI 服务，变更需要重启服务，不能当作单个 UU 会话的选项。
YUV444 要求新版 vfm_cap，报告 `VUY3`：8-bit 单平面 Cr/Cb/Y，stride 来自 canvas。
新版 vfmcapsrc 将其重排为 GStreamer `v308`（Y/Cb/Cr），保留全部色度；
此路径需要 CPU 拷贝，NV21 等现有路径仍是 DMA-BUF 零拷贝。

已有原始 DMA 采集 4K60 实测，不代表重排、编码或网络端到端达到相同帧率。
驱动的 CPU 映射现为只读可缓存页，每次导出完成帧时按需执行缓存失效；
CPU 读取必须使用 DMA_BUF_IOCTL_SYNC READ，禁止写入共享帧。
插件融合复制与 NEON 重排，并复用输出缓冲。旧 write-combine 映射下仅约 13.2fps，
优化后 4K 全帧读取、重排到 appsink 已实测约 60fps；细节和帧连续性见上板记录。
现有 KVM 硬件编码路径继续使用 NV21；在编码器与客户端验证前不开放真彩开关。
编码实测：现有 libamvenc 接受 RGB 但 H.264 输出 High/yuv420p，H.265 输出
Main/yuv420p；不能用输入格式或插件 caps 证明真彩。插件已移除未经支持的
4:4:4/4:2:2/10-bit profile 声明。软件编码未达到 4K60，详见上板记录。
驱动的 `test_lifecycle.c` 用于独占测试 close、STREAMOFF、REQBUFS(0) 后的
DMA-BUF 生命周期；测试结束应确认模块引用归零并可正常卸载。

## 7.3 原生采集候选

`yuv444` 候选在 direct DMA 模式新增标准 `V4L2_PIX_FMT_YUV24`（`YUV3`），
单平面 Y/Cb/Cr，每像素三字节、stride 为 `ALIGN(width*3,16)`。
VDIN 分量选择器反转 packed MIF 的 2/1/0 输出顺序，旁路矩阵、HDR2 和缩放，
保留输入尺寸。此为源码与宿主夹具验证，真实字节序、色度和4K60仍待上板。

仅准入 dynamic RX 的 SDR YCbCr444/8，支持601/709及full/limited，按源报告色彩。
RGB、420、422、10/12bit及HDR输入在TRY/S_FMT返回可协商的`EINVAL`，
STREAMON仍明确拒绝；失锁和暂态保留原错误码。成功S_FMT保存完整配置，
G_FMT在拔线或重新打开设备后仍返回该配置。STREAMON的新lease颜色/range
必须与配置一致，否则释放lease并返回`EPIPE`要求重新协商。
运行中输入变化沿既有lease/source-change停流。
旧内核缺YUV3或源不合格时显式失败，调用者须重新选择原有采集格式。
原有NV12/RGB24/AMLY选择规则保留，不增加服务级格式开关。

4K为11520×2160=24,883,200字节，192MiB预算扣除discard后最多7个用户缓冲，
8帧合计199,065,600字节。预算按页对齐大小计算，CREATE_BUFS只接受协商大小
所在的分配页范围，拒绝额外的大sizeimage。仅在空队列切到需要更大容量的YUV3时
扩容discard，离开时恢复原容量；分配失败保留旧配置和存储。
未选YUV3的NV12/AMLY使用原discard容量及缓冲上限。
沿用vb2 coherent DMA及现有生命周期，不新增CPU重排或像素拷贝。

标准GStreamer路径如下，`DEVICE`须由V4L2 QUERYCAP识别为T7采集节点。
必须同时部署私有GStreamer补丁链新加的`gstreamer-v4l2-yuv24.patch`，它补齐
1.24.2的YUV24/v308枚举、排序和双向协商；旧插件在链接阶段明确失败。
无需videoconvert或新source元素。
sources.toml的candidate_plugin_sha256登记YUV3候选实际哈希，native_hdr_plugin_sha256
保留r13历史已验插件。使用package-hdr10.py封装时显式选择`--v4l2-profile yuv444`，
打包器在复制前后核对插件哈希，默认native-hdr仍使用历史身份。

```sh
gst-launch-1.0 v4l2src device="$DEVICE" io-mode=mmap num-buffers=3600 \
  ! video/x-raw,format=v308,width=3840,height=2160 \
  ! fakesink sync=false
capture-integrity --v4l2 "$DEVICE" 3600 /tmp/yuv444-last.raw
```

`capture-integrity`来自gst-plugin-vfmcap的Meson构建，`--v4l2`复用三处帧号与横纵
色度检查，最后一帧保存为紧密Y/Cb/Cr。该路径直接映射完整帧并采样标记，
只在保存时逐行复制，计时表示raw→appsink交付，不表示每帧CPU全量读取吞吐。
5.15不带该选项的vfmcapsrc路径保留原重排测试。

### 合并窗口中的15分钟上板清单

候选构建与工具编译在取板前完成，由协调者部署匹配完整包。

| 分钟 | 步骤与资格 |
|---|---|
| 0–2 | 核对候选身份、direct_dma、CMA/taint、采集节点和YUV3枚举；停止其他采集消费者 |
| 2–4 | M6 3840×2160p60、HDR关、1920×1080 HiDPI，运行既有capture-pattern.swift；实读AVI space=2、depth code=0/4并确认SDR。只有RGB则记录跳过444验收，验证YUV3请求失败后恢复NV12 |
| 4–7 | 跑上述raw交付和3600帧appsink完整性检查，保存stride/sizeimage、帧率/最大间隔、帧号和色度错误计数及末帧；目标约60fps、所有完整性错误为0 |
| 7–10 | 有界重复启停及REQBUFS释放，核对每轮CMA回收；确认上限7、CREATE_BUFS拒绝25MiB sizeimage；停流且持有导出fd时验证帧仍可读，最后关闭fd；拔线/重新打开仍可G_FMT |
| 10–12 | 释放池后YUV3→NV12→YUV3，再回NV12并核对discard额外容量归还；如M6能提供RGB则测试v308/RGB候选回退与固定v308拒绝；核对旧SDR/PQ主路径 |
| 12–15 | 恢复进入前源模式、应用和采集状态，保存CMA/taint/错误日志，由协调者完成合并窗口恢复 |

无法获得YCbCr444/8就保留未验状态。HLG、隔行、像素重复、真12bit、444编码、
JPEG444和应用UI均不属于此候选。
本候选验收只用V4L2队列和实际AVI/DRM记录。
