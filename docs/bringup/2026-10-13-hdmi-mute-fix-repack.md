# 2026-10-13：HDMI 静音修复及重新打包验证

- 确认默认 TDM-B 输入选了外部引脚，HDMI 有音频包但录音和 WebRTC 都静音。
  HDMI 服务 ExecStartPre 在 ALSA restore 后设置 hdmirx；板级包依赖 alsa-utils。
  包与镜像校验检查路由及先后顺序，实测旧 .6 包被新校验拒绝。
- 修复 VIM4 音频采集和发送重复等待 ticker 的问题；单轮 6 秒稳态从约 42–46
  包/秒改善到约 50 包/秒，缺音补偿增量为 0。后续复测仍有少量补偿，不能作为
  长期零缺音保证。原界面的音量默认静音行为未改。
- 最终组件 1.0.3+vim4.20261013.9 来源全为干净提交，配方 0cd08f1，应用 d175ecd。
  38 项工作区测试、两种 Go 目标、前端、依赖及包校验通过，四组件上板通过。
- 故意把输入重置为 tdmin_b，再整机重启；boot ID 已变化，NanoKVM/HDMI 服务
  active，路由自动成为 hdmirx（值 6）。包完整性和服务检查通过。
- 重启后原音量菜单打开播放，6.007 秒非静音音频测试收到约 47.94 包/秒，
  丢包 0，补偿 3924 个采样、7 次事件。它证明声音恢复，不证明无间断播放。
  视频随后单独采样 10 秒，3840×2160、601 帧（60.08fps），丢帧/丢包 0。
- 官方 Ubuntu 基础镜像加入同一 .9 组件重新组装，通过只读校验、文件系统检查、
  音频启动顺序和 amixer 依赖检查，导出到
  build/images/vim4-kvm-ubuntu-1.0.3-audio9/（约 692MiB，附 SHA256SUMS）。
  没有擦写板子；此候选镜像的全新刷机启动验收仍未执行。
- 证据：build/audio-final-{build,verify,image-assemble,image-export}.log，
  logs/audio-final-{deploy,reboot,health,state}.log、audio-final-browser.json、
  audio-final-video.json。功能缺项纠正见 [功能状态](../feature-status.md)。
