# 2026-10-13：组件包部署闭环验证

- 主仓库 e72154b 的干净源码构建四组件包 1.0.3+vim4.20261012.1；隔离构建
  包含主仓库 17 项测试、部署辅助工具 7 项测试、两种 Go 目标及前端构建。
  包校验、ARM64 动态依赖、sudoers 和配置保留验证通过。
- 上传现有 Ubuntu 板子增量安装，未刷 eMMC、未替换内核或重新协商 USB-PD。
  手工服务和编码插件路径迁移到包管理路径；保留 rtp-lan.conf 的 1400 参数。
- 发现旧 sudoers 仍引用 /usr/local/libexec，修复为包内 /usr/libexec；发现开机
  wants 链接仍指向已迁移的 /etc 服务，安装工具使用 reenable --force 重建链接。
- board.py check 通过，USB UDC 为 configured；应用进程映射确认实际加载
  /usr/lib/vim4-kvm 下编码插件及系统目录中的 vfmcap。特权 ssh-get 查询成功。
- Chrome 无头浏览器采样 15.006 秒，3840×2160，解码 901 帧（60.04 fps），
  framesDropped/packetsLost 增量均为 0。当前场景的冒烟结果不能代表高运动负载、
  音频、HID 实际输入或端到端延迟；本轮未重启验证。
- 构建/包验证日志在 build/deploy-{build,verify}-20261012.1.log，视频数据在
  logs/deploy-video-smoke.json。安装与浏览器测试已固化为 install-components.sh
  和 video-smoke.mjs，入口见 docs/board-tools.md。
