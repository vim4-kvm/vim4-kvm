# 2026-10-27：共享编码的 SRT 与 RTMP 输出

One-KVM 增加设备持有的两路网络输出，入口为设置「第三方接入」。默认关闭，
视频复用已有共享编码，不另开采集设备或硬件编码器；音频复用 HDMI Opus 包后转 AAC。
本条记录网络输出；后续 HEVC 无损／固定 QP 见[画质模式验证](2026-10-27-hevc-quality.md)。

## 来源与范围

- One-KVM：`e61202cf3f206fc313e9ffd4f0eb1319519649e4`。
- 板子：VIM4，`5.15.137-vim4kvm-hdrdual6`，HDMI 为 Mac mini 的 3840×2160 60Hz SDR。
- 输出码率沿用当前 KVM 的 40000kbps 设置；该值不是静态桌面的实际码率。
- Chrome `156.0.8078.48` 在开发 Mac 无界面运行，经 SSH 回环转发访问板端服务。
- SRT/RTMP 接收器为板内 ffmpeg 回环；保存文件在隔离 ARM64 容器中解码检查。
  Docker 到板子局域网地址不通，不能将本轮结果称为跨局域网接收验证。

SRT 为 listener / MPEG-TS，支持 H.264、H.265，可选 AES-256 口令；
RTMP/RTMPS 为发布端，使用 H.264 + AAC。两路跟随现有视频配置，不争抢编码选择，
RTMP 在 H.265/MJPEG 下显示等待 H.264。没有浏览器也保持设备端订阅。
音频可分别关闭；开启时要求音频采集已启用，不静默丢弃音轨。
参数、凭据处理和恢复边界见 [One-KVM 集成](../../One-KVM/VIM4.md#共享编码-srt--rtmp-输出)。

## 交织时间戳修复

最初的实时 appsrc 声明导致 FLV 封装在 AAC 尚未到达时先推进视频，随后把音频
时间戳挤到视频帧时间上。板上文件出现 AAC DTS 重复，虽然能出声音，不能算正确。
加 100ms 固定等待仍未通过回归；最终让封装管线沿用已有包的节奏，不声明独立实时源，
交织等待两路实际数据。队列和捕获超时仍限制等待，不影响共享 KVM 的生产者。

离线回归故意将 Opus 到达延后 60ms，并用独立 ffmpeg 接收、ffprobe 检查 AAC 包的
时间戳间隔。修复前失败（相邻 PTS 差为 0），最终版本通过，AAC 48kHz/1024 采样的
间隔保持为 FLV 毫秒精度下的约 21/22ms。
GStreamer 对跨流时间戳调整的契约见
[flvmux 文档](https://gstreamer.freedesktop.org/documentation/flv/flvmux.html)。

## 验证

- Rust `cargo test --locked --features vim4 --lib`：798 通过，4 忽略。
  覆盖实际 SRT H.264/H.265 解码、加密、RTMP H.264/AAC、非静音波形、
  延迟音频的时间戳、积压队列上限、配置合法性与凭据脱敏。
- 前端构建通过，9 项前端测试通过；Linux 部署助手 35 项测试通过。
  macOS 无 `/proc` 等 Linux 环境，部署助手必须在容器中运行。
- 根仓库离线测试：282 项，7 跳过，其余通过。
- 非 VIM4 desktop 检查被现有 `hwcodec` 的 RKMPP 定制 FFmpeg 头依赖挡住
  （系统头没有 `AV_HWDEVICE_TYPE_RKMPP`）；没有把它算作通过。

硬件验证已确认无浏览器时两秒增加 120 帧、SRT H.265 接收与重新加入，
以及加密 SRT H.264 和 RTMP 同时输出。RTMP 接收器停止及重新启动时，
SRT 输出的重启计数保持 0，网页继续解码。
最终候选 Chrome 4K H.265/SRT 并行为 59.97fps，H.264 双输出并行为 60.05fps，
对应 10/12 秒窗口均无新增 freeze、解码丢帧或丢包，呈现回调最大间隔分别为
22.3/27.9ms。这不是运动内容或光学延迟测量。RTMP 接收器停止、重启并再次
解码成功，SRT 持续发送、重启计数为 0；修改 RTMP 音频设置也不重启 SRT。
最终 RTMP 文件检查 469 个 AAC 包，468 个间隔全部为 21/22ms，无重复时间戳；
接收端解码的测试音峰值 3392（S16）。

证据位于忽略目录 `build/broadcast/`：`full-tests-final.log`、`rtmp-clock-before.log`、
`rtmp-clock-nonlive.log`、`board-test.log`、`dual-test-before-clock-fix.log`、
`board-srt-browser.log`、`board-dual-browser.log`、`dual-test.log`、
`rtmp-final-audio-packets.json` 和接收文件的 `*-probe.json`。

## 部署与边界

候选直接更新 `/opt/vim4-onekvm/one-kvm`，原二进制保留为
`one-kvm.pre-broadcast-20261027`，不更新内核或其他 KVM 应用。
最终候选 SHA256 为
`d13cecd02f7485102854496ffc58dc587edc7914c0ef17c1df0eba530eabd6a9`。
测试结束关闭两路输出、清除测试口令与推流 URL，恢复 H.265 模式和原有视频设置。
运行依赖 `gstreamer1.0-libav` 已在板上存在，Ubuntu 包依赖与构建环境声明也已补齐。
构建环境刷新因 Ubuntu snapshot 下载返回 503 失败；临时构建容器使用同一官方源的
签名索引和 SHA256 校验补齐依赖，完成 VIM4 编译与测试。本轮未生成新的正式组件包。

未验证外部 OBS/VLC、真实直播平台、RTMPS 证书握手、长时间弱网、HDR 接收端显示和
7.3 内核。发送状态来自插件字节统计，不能代替接收端画面或端到端延迟。
