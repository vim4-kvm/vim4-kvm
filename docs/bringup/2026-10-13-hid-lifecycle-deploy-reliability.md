# 2026-10-13：HID 生命周期与部署可靠性

- 官方 Khadas fork vim4-kvm/linux 的 dbcef7c1f 把等待队列初始化移到实例分配，
  b86c7e5bd 为每次绑定分配独立 cdev，旧描述符关闭后才释放旧设备；补齐分配及
  注册失败清理。原作者保留，应用 Reenumerate 保护保留。CONFIG_USB_F_HID=y，
  修复必须通过完整 Image 与重启生效。
- 第一轮只含等待队列修复，保持 epoll 注册跨 UDC bind 的测试仍触发
  list_del corruption，SSH 失联，串口只捕获到错误开头，需要 RESET 恢复。
  因此单项补丁与候选 reliability19 均不能作为完整修复交付。恢复后所检查的
  应用、板级和内核包未报告文件校验差异；不能据此证明所有未纳管文件都未损坏。
- 最终内核 b86c7e5bd 启动 ID 79719ee3-c0ec-4495-a097-0991d465ee6f，Image SHA256
  e689f0b003375663d19643fbf3dcc6c54185966d3f4bc7ebae38dd24a6fdfdd1。
  三个 HID 文件在 epoll 中保持打开，重新绑定后注销/关闭，连续 20 轮通过。
  原查看页面在线时再做 3 轮麦克风→只读 ISO→弹出→NCM，均通过，启动 ID 未变化，
  未发现新的 list corruption/BUG/Oops/panic。没有验证所有并发读写与拔线场景。
- 原根分区为 data=writeback、commit=600。rootfs-policy 仅修改 Default 启动行，
  明确追加 rootflags=data=ordered；根分区和 /boot 的 fstab commit=5。
  Stock 行未变。重启后的 findmnt 和 ext4 启动日志确认生效；这不保证任意断电无损。
- 在线发布改为封装组件 deb，消除 /usr/local/libexec 与 /usr/libexec 不一致，
  统一依赖、服务路径、配置保留和安装检查。更新前模拟 APT，需平台升级则拒绝；
  成功后核对辅助程序与 sudoers、visudo、sync，再安排应用重启。所有组件 postinst
  增加 sync，部署在建立服务链接后再次 sync。空 sudoers 的组件配置测试明确失败。
- 干净构建 .19：40 项工作区测试、27 项部署测试、两种 Go 目标、前端及包检查通过。
  原手动更新 API 上传同一组件的封装包，任务 succeeded，NanoKVM PID 从 1299
  变为 1534，安装文件校验通过。本轮验证了同版本重装，尚非全新刷机后的跨版本升级。
- 最终板子保持用户的 1080p EDID：board.py verify 键鼠/音频/视频 PASS。
  10 秒视频 600 帧、59.95fps、丢帧/丢包 0；定向测试音录音峰值 3277。
  Chrome 音频 6.005 秒约 49.96 包/秒，非零能量、丢包及补偿 0。
- 新候选 reliability19b 使用 .19 组件及完整 HID 内核修复；结构、文件系统、
  启动策略、依赖、sudoers、音频路由校验通过。没有擦写板子，也没有完成该候选
  的全新刷机启动验证。版本清单已更新；子仓库提交需先于主仓库清单推送。
- 证据：build/reliability-{build,verify,final-image,export}.log，
  logs/reliability-{hid2-rebind,hid2-uart,usb-switch,final-verify}.log，
  reliability-update-{inspect,confirm,result}.json、reliability-browser-audio.json。
