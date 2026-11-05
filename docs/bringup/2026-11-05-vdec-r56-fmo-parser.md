# 2026-11-05：r56 AVC 续跑与 Khadas parser 来源

`.28` 正常启动，stateless media/video compliance 分别 **8/0、60/0**。
index 61–94：**26 Success、7 Fail、1 Timeout**。FM1_FT_E 触发已有 H.264
内核 timeout 后立即停止并恢复，95–134 本窗未运行；未在超时后重载驱动继续解码。
合并 r54 的唯一输入，目前 **79 Success / 17 Fail / 1 Timeout / 38 Not run**。

## 停止、恢复和 ioctl 证据

原始目录 `logs/hwdecode-parity-r56/validation-fluster-1793911524978444000/`。
逐码流结果把 FM1_FT_E 的 Fluster Error 按内核日志分类为 Timeout，理由为
`Kernel decoder timeout; recover before another stream`，原始 JSON/日志仍保留。
不把 FMO 的已知不支持静默跳过，也不把普通像素 Fail 当成窗口错误。

生产配置没有 CONFIG_FTRACE_SYSCALLS；宿主下载 Ubuntu arm64 strace 6.8-0ubuntu2，
校验后放临时工具包，未安装到系统。deb SHA-256
`41a1f7409e46251b6e66db834456cbda1e4f0bf58c52d015a0130630f6ef0a24`，
可执行文件 SHA-256 `33b3ea325915f1213dc477d80e0f0b2b09ffeff5e81d98b25a35320fbcbcaf42`，
纳入测试计划文件校验。宿主真实 ioctl 冒烟原始输出为
`build/hwdecode-parity/strace/probe.log`（TIOCGWINSZ 对管道返回预期 ENOTTY）。
首条 CAWP5_TOSHIBA_E 的 `vector-0061-ioctl.log` 实际记录 OUTPUT/CAPTURE
两次 VIDIOC_STREAMOFF 均返回 0，没有 VIDIOC_DECODER_CMD。
Sharp 尚未续跑到，**本窗不能证明 held 第二场缺失时的 FLUSH 释放**。

恢复新正式 `7.3.1-vim4-20261105` 的 release/build ID、2372 个保护文件全部匹配，
实际 4K H.265 298 帧、59.56 fps，零新增 dropped/freeze/lost。636 个上传文件
逐项归档、复核后删除。恢复与归档原始日志分别位于本轮 logs/、build/hwdecode-parity/run56/。
`.28` 累计 6 次启动/2 次冷复位，新正式覆盖下界 11 次/0 次，本窗两次启动均未复位。

## 来源闭环：Khadas 包，未发现安装后文件替换

`build/hwdecode-parity/run56/parser-identity.json` 保存逐命令原始输出、库时间戳、
APT index 路径/源 URI、本地 md5 数据库及安装历史。采证只读；失败不阻断解码。

- `dpkg -V gstreamer1.0-plugins-bad` 返回 0、无差异；库 MD5
  `286f1d386246c766607df37130cffa92` 与本地 md5sums 一致。
- APT policy 把已安装 `2:1.24.2-1ubuntu4` 对应到
  `http://dl.khadas.com/repos/vim4 noble/main arm64`；Ubuntu 源提供的是没有 epoch
  的 `1.24.2-1ubuntu4`，不能只看末尾版本号当作同包。
- dpkg 历史显示 2025-09-21 安装无 epoch Ubuntu 版本，2025-09-25 升级到
  Khadas 的 `2:` 版本。结合包校验，证据支持厂商包内构建差异，没有发现安装后覆盖。
- 系统 parser SHA-256 仍为 `2da88e7aa1c9bd39a74f5cf6806d24f1c7cd80ec11aab712b25f0975e89bb017`；
  与[官方包对照](2026-11-05-vdec-r55-parser-identity.md)不同。
- 私有 `libgstv4l2codecs.so` SHA-256
  `ca9b5d41cd5cb4e1971778e3db99171c66bc78a24a6b9bcd906cfe7de2e8f601`，
  来源是 vdec-gstreamer.toml 的官方 bad recipe；不是系统 parser，也不是
  sources.toml 的 good recipe。

因此 Sharp 的已观察到尾帧缺失登记为 **Khadas 系统 h264parse 排空限制**。
官方 1.24.2 在 `drain && current_off == size` 完成当前 AU，Khadas 实际日志却
返回 Need more data；源码级对照仅覆盖官方路径，尚未取得厂商该库的精确补丁/源码提交，
不虚构修改位置。已有帧逐字节正确；套件仍 Fail，HOLD+FLUSH 未单独验收。
不替换系统库，不打私有插件补丁。r57 从 index 95 继续，仍沿用冷复位和 timeout 停止条件。
