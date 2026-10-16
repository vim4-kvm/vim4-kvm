# 2026-10-13：采集分辨率菜单部署

- 干净构建并校验 `1.0.3+vim4.20261013.20`，应用提交 `a7c0630`；通过
  `board.py deploy --exclusive` 安装四组件，服务检查通过，没有重启内核。
- Chrome 打开板上实际页面，确认菜单显示分辨率、最高 FPS 和采集输出说明，
  当前 3840×2160 配置被勾选；没有切换分辨率或 EDID。
- 当前信号实际输出 1920×1080；H.264 WebRTC 采样 10.007 秒解码 600 帧，
  59.96fps，丢帧/丢包均为 0。菜单配置值不代表实际输入尺寸或实时帧率。
- 证据：`logs/package-20261013-20.log`、`logs/verify-package-20261013-20.log`、
  `logs/deploy-20261013-20.log`、`logs/video-20261013-20.json`、
  `logs/deployed-resolution-menu-20.png`。本轮未重新测试音频、HID 或端到端延迟。

- 后续设置页改为 EDID 相同的标题/说明加 Select 布局，应用提交 `da6150a`，
  干净构建、校验并部署 `1.0.3+vim4.20261013.21`。本地浏览器模拟接口验证
  下拉框与快捷菜单双向同步、保存失败保留旧值并提示错误；板上 Chrome 确认
  下拉框显示三档尺寸及最高 60 FPS，视频正常显示，没有切换实际采集设置。
  部署服务检查通过，截图 `logs/deployed-resolution-settings-21.png`；构建、
  包校验和部署日志分别为 `logs/{package,verify-package,deploy}-20261013-21.log`。
