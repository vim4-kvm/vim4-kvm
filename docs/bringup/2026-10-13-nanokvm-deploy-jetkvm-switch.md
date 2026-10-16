# 2026-10-13：NanoKVM 正式部署与 JetKVM 往返切换

六个 Ubuntu 组件完整更新到 `2.5.1+vim4.20261013.5`，保留 Ubuntu 账户、
内核与当前 NanoKVM 选择。干净构建使用 workspace `355cee7`、NanoKVM
`93d8fc0`、manager `1575c43`、JetKVM `1e469f5`；包校验覆盖校验和、ARM64
ELF/依赖、sudoers、配置保留和损坏文件拒绝。正式部署使用
`board.py deploy --exclusive --packages build/packages/2.5.1+vim4.20261013.5`。

初测发现并修复：

- manager 仅靠 systemd Conflicts 切换，旧 NanoKVM 尚未退出时 JetKVM 已启动，
  导致 8080 bind panic。助手在 select/restart 中等待另一应用停止，再启动目标；
  单元测试覆盖顺序及 stop 失败时不得启动。
- 共用来源的首页缓存会让 JetKVM 页面加载成 NanoKVM。管理器链接增加应用查询参数，
  NanoKVM 的 `/` 和 `/index.html` 返回 `Cache-Control: no-store`；上板核对通过。
- NanoKVM VIM4 不再写设备固件专用的 `/kvmapp/kvm/now_fps`，仍更新帧率 API。

此前 JetKVM 恢复出厂后仍处于初次设置状态；通过原生 setup API 按既定本地免密码
模式完成初始化。没有修改 Ubuntu 账户密码。

新增 `tools/kvm-switch-check.mjs --exclusive`，保留旧浏览器会话直到切换完成，
调用真实管理器 API，检查两个服务 active/enabled 状态并读取 Chrome WebRTC stats。
正式包结果（当前桌面场景，每段 10 秒）：

| 顺序 | 应用 | 切换到首帧 | 解码 fps | 丢帧 / 丢包 |
|---|---|---|---|---|
| 1 | NanoKVM | 2117 ms | 60.07 | 0 / 0 |
| 2 | JetKVM | 2124 ms | 59.98 | 0 / 0 |
| 3 | NanoKVM | 1888 ms | 59.97 | 0 / 0 |
| 4 | JetKVM | 1981 ms | 60.04 | 0 / 0 |
| 5 | NanoKVM | 1950 ms | 60.08 | 0 / 0 |

全部为 3840×2160。最终 `board.py verify`：USB 绝对指针真实移动 Mac 光标并恢复；
ALSA 一秒取得 48000 帧，但峰值 0，仅证明采样运行，不证明声音可听；H.264 视频
60.07fps、零丢帧/丢包。服务无 failed 项，UDC configured，dpkg audit 无输出。
新版本切换日志未见 bind panic 或 now_fps 错误；关闭测试浏览器时仍有上游记录的
WebSocket close 1001，不影响下一次连接。

证据：`logs/nanokvm-switch-{package,verify,deploy}.log`、
`logs/nanokvm-jetkvm-switch-packaged.log`、`logs/nanokvm-switch-final-verify.log`、
`logs/nanokvm-switch-journal-installed.log`。未测端到端输入延迟、键盘、长时间复杂运动、
重启及新镜像刷机；当前结果不能代替这些验证。最终 NanoKVM active/enabled，
JetKVM inactive/disabled，通过管理器 `http://192.168.50.210/` 可切换。
