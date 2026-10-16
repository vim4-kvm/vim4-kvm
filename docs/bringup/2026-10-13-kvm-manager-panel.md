# 2026-10-13：KVM 界面管理面板

新增 vim4-kvm/vim4-manager 仓库（本地 main，尚未推送）：Go 后端嵌入 React 前端，
以 khadas 监听 80 端口，选择开机启用 NanoKVM-Pro 或 JetKVM，并显示 HDMI、USB、
温度、内存和底层服务。特权操作只经 sudoers 限定的 /usr/libexec/vim4-manager-helper。
JetKVM 打包为 vim4-jetkvm（/opt/vim4-jetkvm，状态目录 /var/lib/jetkvm）。
之前沿用 StateDirectory=vim4-kvm，会把含 NanoKVM EDID 的 root 目录改归 khadas，已改名。
包不启用 JetKVM；install-components.sh 保留当前选中的应用，不再固定重启 nanokvm。
重刷后板上原 JetKVM 和配置已不存在，首次打开时用其 /device/setup 选择了免密码模式。

版本 1.0.3+vim4.20261013.30 由仅含已提交源码的 worktree 快照构建（另一会话的
NanoKVM-Pro 工作区未提交改动不在其中），ubuntu-build verify 通过，board.py deploy
六包一致、check 通过。证据 logs/package-30.log、logs/deploy-30.log。

- 切换到 JetKVM 约 1.4 秒：nanokvm 停止并禁用，jetkvm 占用 8080。
  Chrome 10 秒 3840×2160 约 60.0fps、丢帧 0；通过 JetKVM 网页移动指针，
  Mac 光标到 (0.235,0.300)、(0.712,0.601)，目标 (0.25,0.30)、(0.70,0.60)。
- 切回 NanoKVM 后 video-smoke 10 秒 3840×2160、60.2fps、丢帧和丢包 0。
- 重启 HDMI 采集：日志顺序为 nanokvm 停止 → HDMI 重启 → nanokvm 启动，之后
  4K 约 60fps、丢帧 0。重启 gadget 的请求被拒绝；跨站表单式 POST 返回 415。
- 选择 JetKVM 后整机重启：jetkvm、manager 及 HDMI/gadget/PD 均 active，
  UDC=configured，JetKVM 4K 约 60fps、丢帧 0。之后切回 NanoKVM 作为板子当前选择。

未覆盖：JetKVM 键盘输入、长时间运行、多浏览器同时操作面板、断电冷启动。
面板 API 无认证，仅适用于可信局域网。
