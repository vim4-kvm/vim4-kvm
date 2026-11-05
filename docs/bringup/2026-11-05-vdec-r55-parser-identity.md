# 2026-11-05：r55 采证提前退出与系统 parser 身份

`.28` 正常启动，无冷复位。新增身份脚本在 acceptance 尚未加载解码节点时查询
`gst-inspect v4l2slh264dec`，动态元素不存在，断言使窗口提前恢复；index 61 起的
续跑和 compliance 全部未运行。这是采证脚本错误，不是驱动回归。
原始错误保留在 `build/hwdecode-parity/run55/window.log`。

恢复新正式默认及全部 2372 个保护文件通过，H.265 4K 实际推进 298 帧、59.57 fps，
零新增 dropped/freeze/lost。516 个上传文件校验归档后删除。
证据为 `logs/hwdecode-parity-r55/returned-baseline-identity.json`、`returned-video.log`
及 `build/hwdecode-parity/run55/upload-cleanup.log`。截至本窗 `.28` 共 5 次/2 次冷复位，
正式默认覆盖下界 10 次/0 次；不据小样本推断根因。

## 只读补证

恢复后短 FIFO 票只读采集 `gst-inspect h264parse`、dpkg 版本/归属及库 SHA，
不重启、不更换库，保存于 `run55/system-parser-identity.json`。

- 系统库：`/usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstvideoparsersbad.so`。
- 声明版本 1.24.2，dpkg 归属 `gstreamer1.0-plugins-bad:arm64 2:1.24.2-1ubuntu4`。
- 实际 SHA-256：`2da88e7aa1c9bd39a74f5cf6806d24f1c7cd80ec11aab712b25f0975e89bb017`。
- 官方 Ubuntu 同版本 arm64 deb 提取库 SHA-256：
  `6b8523110912868c168e1c5b85be2883fbafd925c4996bc1069b65915e1d7cf2`，**与板端不同**。
  [官方下载](https://ports.ubuntu.com/pool/universe/g/gst-plugins-bad1.0/gstreamer1.0-plugins-bad_1.24.2-1ubuntu4_arm64.deb)
  包 SHA-256 `4948ce79d4e173ec50605188784082f2161e7fd374a584e28db38d44e8cf46ff`，
  VM `build/hwdecode-parser-provenance/` 保存下载与解包文件。

锁定官方 source.tar.xz 的 `gst/videoparsers/gsth264parse.c:1399` 在
`drain && current_off == size` 时跳到 end，完成 AU；宿主实跑日志显示
`draining with no new data`，两条流全部 slice 保留。官方 deb 的库也包含该日志字符串。
板端 r54 同位置却报告 `Need more data, current_off ... size ...`，之后直接 EOS。
可以认定当前板端 parser 的排空限制，**不能归因为官方 1.24.2 或 Ubuntu 原包缺陷**。
仅有 dpkg 包名还不能区分厂商同版本重编与安装后覆盖，留待本地 md5 数据库、源仓库
及安装历史补证，不猜测归属。

`sources.toml` 私有 GStreamer recipe 构建 gst-plugins-good；
`vdec-gstreamer.toml` 构建 gst-plugins-bad 的私有 v4l2codecs。测试上传包只有后者
`libgstv4l2codecs.so`，未包含系统 `libgstvideoparsersbad.so`，不能混用两者来源。
后续按库路径查询私有插件，采证异常只记录未覆盖，不阻断解码主流程。
不安装插件补丁，不替换系统库。
