# 2026-10-12：4K60 编码预算与局域网 RTP 分包

从官方 `khadas/multimedia-gst-plugin-venc` 创建 org fork
`vim4-kvm/gst-plugin-venc`，本地 `vim4` 分支起点 `997f264`。修复 amlvenc
framerate 属性只能到 30 的限制，允许 0–120；0 使用输入 caps 的帧率，未知时
回退 30，分数帧率四舍五入到编码库整数 API。初始化码控和逐帧 metadata 使用
同一个值。原版权声明保留，没有替换为第三方实现。

vfmcapsrc 当前报告不定帧率，因此 NanoKVM 创建 pipeline 时读取 HDMI RX 的
`Frame Rate`（单位 1/100 fps），与用户 drop-only FPS 上限取较小值后传给编码器。
同尺寸但源帧率变化、且没有 caps 变化时需要重开采集。GOP 120、performance、
现有 RTP 时间戳/PLI 修正保留，前端没有改动。

同一组 360 帧 4K SMPTE 样本，bitrate=12000：旧 30fps 预算产生 24.11Mbps，
60fps 预算产生 11.51Mbps；周期性关键帧约 86KB→66KB。软件生成测试图耗时约
30 秒，不能把这个过程当成真实采集帧率测量。

新插件安装在 `/usr/local/lib/vim4-kvm/gstreamer-1.0`，通过 nanokvm 的
`encoder.conf` drop-in 选择；原系统插件仍在原路径。原版应用更新包不包含该
平台依赖，未来系统镜像需执行新仓库的构建与 `install-vim4.sh`。

NanoKVM 新增可选 `VIM4_RTP_PACKET_SIZE`（1000–1400），默认/无效值仍是 1200。
本机验证 eth0 MTU=1500，通过 `rtp-lan.conf` 持久启用 1400。数值是 packetizer
预算，不包含后加的 RTP 扩展、SRTP、UDP/IP 开销；未知/VPN 路径应删除该 drop-in
并重启，恢复默认。通用安装器不会自动启用局域网选项。

Mac HDMI 上显示滚动文字/色块动画，Chrome headless 每轮测量约 20 秒：

- 旧预算/1200：24.51Mbps、59.99fps、52192 包，平均组帧 1.41ms。
- 新预算/1200：12.31Mbps、59.99fps、26499 包，平均组帧 0.63ms。
- 新预算/1400：12.32Mbps、59.99fps、22822 包，平均组帧 0.54ms；复测
  12.42Mbps、59.99fps。各轮网络丢包、解码丢帧、freeze 均为 0。
- 解码帧间隔标准差约 6.08ms→3.42ms，1400 两轮为 3.54/3.74ms。
  呈现回调采到的解码耗时 p99 从 5.6ms 降到 4.6ms。
- 浏览器呈现最大间隔仍有波动：旧 49.9ms，新预算 35.3ms，1400 两轮为
  33.9/47.5ms。不能声称大包已经稳定消除显示卡顿，也未测玻璃到玻璃延迟。
- 原版 FPS 切换 30→自动：5 秒分别解码 150、300 帧，最终恢复自动。

VIM4 Go 全套测试、默认 Go 全套测试、两种后端编译通过；改分包选项后再次通过
WebRTC 测试和两种后端编译。没有使用 strace/pprof 参与对比，没有开启严格跳帧
码控、固定 QP、帧内刷新或批量发送。原有未提交优化没有合并进本轮提交。
原始浏览器统计保存在 gitignored `logs/vim4-{before-rate,after-rate,after-1400,
after-1400-repeat}.json`。`/tmp/NanoKVM-Server` 未改，构建使用独立文件名。
