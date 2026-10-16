# 2026-10-13：无人值守部署

- `board.py enroll` 在开发板安装 /etc/sudoers.d/vim4-dev-nopasswd（khadas 免密 sudo），
  不进入组件包与镜像；`sudo -n true` 验证通过。Ubuntu 密码未改。
- 首次 enroll 失败的原因是 board.py 的第一个 ssh 子进程继承 stdin、吞掉了经管道传入的
  密码，sudo 收到空行。子进程改为不继承 stdin 后通过；不是密码错误。
- 随后 `board.py deploy --exclusive --packages build/packages/1.0.3+vim4.20261012.1`
  全程无密码：上传、install-components.sh 校验/迁移/重建启用链接、重启 nanokvm、
  版本核对与 check 均通过，UDC configured。
- video-smoke.mjs 15.005 秒，3840×2160，解码 900 帧（59.98 fps），丢帧/丢包 0。
  同版本重装，不代表新版本或运动场景、HID、音频、延迟通过；本轮未重启整机。
- 同日 `board.py verify` 首次实机运行：hid PASS（hidg1 绝对坐标移动 Mac 光标并恢复），
  audio PASS（1 秒 48000 帧，峰值 0，信源静音，未验证音频内容），video PASS
  （3840×2160 60.0 fps，丢帧/丢包 0）。日志 logs/board-20261013-122034-b9aa0b/。
- 同日 `board.py provision` 实机验证：在当前板子用临时 SSH 密钥模拟新镜像，公钥登录
  被拒后以默认密码登录一次，写入公钥，随后公钥登录与免密 sudo 均通过；临时密钥与
  SSH 配置已清理。未经实际刷机，flash 后自动 provision 只由离线测试覆盖。
