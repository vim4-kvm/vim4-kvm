# 2026-10-13：NanoKVM 终端、镜像上传与可写 U 盘

最终应用为 `2.5.1+vim4.20261013.8`（NanoKVM `b6bc786`），其他组件保持 `.7`。
管理器工作树有另一项任务的未提交修改，因此 `.8` 在独立目录按清单构建，只更新应用包。
构建、默认/VIM4 后端测试与构建、两种前端构建、sudoers/配置保留/包校验均通过。
新增 USB helper 的首次创建失败清理、已有数据不重建、符号链接拒绝测试；Linux 容器
内 media helper 7 项测试通过。此前删除 Smart Assistant 的更新也已部署并核对旧目录消失。

- 终端优先查找 Bash，不存在时使用 `/bin/sh -l`；真实网页 WebSocket 回读
  `BASH_VERSION=5.2.21(1)-release`。未在板子上移除 Bash 测 fallback。
- 上传失败源于应用无权创建 `/run/nanokvm-transfer-in-progress`。curl 的早期响应
  显示 permission denied，Chrome 的原生 File/FormData 请求表现为 Failed to fetch。
  VIM4 使用 systemd `RuntimeDirectory=vim4-nanokvm`、0700/khadas 和专用传输锁；
  上游平台保留原路径。前端文件选择与拖放同时接受 ISO/IMG。
- Chrome 上传 Ventoy 1.1.18 LiveCD（约 186 MiB）成功，板上 SHA-256 为
  `ee3917bd5a9973c0b2f8f3ef85048bf68ae089ec88f5561ad78b6ad308b51ab5`，与官方及本机一致。
  CD-ROM 模式在 Mac 自动挂载 VentoyLiveCD，读取 EFI/boot/bootx64.efi 成功。
  Mass Storage 模式被识别为 196 MB USB 磁盘，但 Mac 未能挂载其中的 0xEF 分区；
  不把枚举通过等同于这个混合 ISO 在磁盘模式下可读，也未测试启动 Ventoy。
- 设置里的虚拟 U 盘开关原先返回 unsupported，现使用独立的
  `/var/lib/vim4-kvm/usb/disk.img`，首次创建 512 MiB FAT32，后续不重新格式化。
  不导出 Ubuntu 根分区，也不与镜像上传目录共用文件系统；它与镜像挂载共用一个 LUN。
  `/var/lib/vim4-kvm/usb/enabled` 保存开启意图，应用启动前恢复；普通应用重启时若已挂载
  则不重新枚举 USB。挂载其他镜像/弹出会清除 U 盘开启意图，麦克风切换保留它。
- Mac 实际写入 29 KiB 测试文件，弹出、关闭/开启 U 盘后回读哈希一致；重启 NanoKVM
  服务后仍可读。测试文件已删除，U 盘已关闭、NCM 恢复；Ventoy ISO 保留供用户使用。
  开启时 USB 网卡让出端点，HID 保留。此轮未测试整板冷启动或突然断电时文件系统恢复。

最终 `board.py verify`：USB 绝对指针通过；4K H.264 10 秒 59.98fps、零丢帧/丢包；
音频取得 48000 帧但峰值为零，不能证明可听声音。无 failed units，dpkg audit 无输出，
测试窗口内内核日志未见 panic/Oops。证据位于 `logs/media-tests/`。
新增 `tools/media-upload-check.mjs` 复测浏览器原生上传及终端 Bash，它不会自动删除上传镜像。
