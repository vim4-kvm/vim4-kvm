# 2026-10-16：4:4:4 编码能力核验与错误声明修复

- 板上 libamvenc `0.2-202406~noble`、正式路径 amlvenc 插件，独占停止 One-KVM
  与管理器，以 khadas 用户运行，沿用 `/opt/vim4-onekvm/lib` 的兼容 allocator。
  1920×1080 RGB 运动球、60fps 预算，H.264/H.265 各编码 30 帧；ffprobe 检查实际
  码流分别为 High/yuv420p 和 Main/yuv420p。直接 v308 输入不能链接。
- 发现插件错误声明：显式请求 H.264 `high-4:4:4`，管线成功完成，但实际码流仍是
  High/yuv420p。底层 amvenc_info 无 profile/chroma 输出配置，RGB 输入不等于
  真彩输出。结论限定为现有 vendor API/固件链路，不断言芯片所有潜在模式均不支持。
- gst-plugin-venc `a61a497` 修正正式构建入口 amlvenc 的源 caps：移除 H.264
  4:4:4/4:2:2/10-bit 等未经支持的声明，HEVC 只声明 Main。
  `tests/encoder-chroma.py --exclusive` 同时检查拒绝不支持的能力和真实码流；
  ARM64 构建通过，临时候选插件实机 H.264/H.265 回归通过。构建有既有 unused
  参数/变量警告，无编译错误；未修改未使用的历史编码器构建目录。
- 软件编码对照（无实时采集和网络，不能当作端到端性能）：

  | 负载 | 编码设置 | 结果 |
  |---|---|---|
  | 4K 单帧测试图循环 120 帧 | libx264 ultrafast/zerolatency、CRF23、High444 | 7.256 秒，约 16.5fps，yuv444p |
  | 1080p testsrc2 运动图 180 帧，转 yuv444p | 同上 | 4.405 秒，约 40.9fps，yuv444p |
  | 4K 单帧测试图循环 30 帧 | libx265 ultrafast/zerolatency、CRF23、main444-8、pools=4 | 16.352 秒，约 1.84fps，Rext/yuv444p |

  4K 源为此前捕获的标准 v308 测试图，先按字节拆成 Y/U/V 三平面；静态重复是较轻
  编码负载，仍不足 60fps。1080p testsrc2 原始色度为 4:2:0，转为 4:4:4 后编码，
  该轮仅测吞吐，不能证明输入原本具有完整色度。未测全部参数组合或其他编码实现。
- 当前完整 4:4:4 采集可达 4K60，但现有编码路径无法兑现 4K60 真彩；不添加 UU
  可用能力声明或全局切换。后续若继续此目标，需要验证另一条保留色度的硬件编码路径，
  或接受较低分辨率/帧率的软件方案，并另做官方客户端兼容验收。
- 测试后 One-KVM、管理器和 HDMI 服务 active，HTTP 200，近期无内核 BUG/Oops/panic；
  未部署候选插件、未重启。证据为 `logs/encode444/initial.log`、`regression.log`、
  `restored.log`；构建日志 `build/encode444/build.log`。
