# AGENTS.md

Khadas VIM4 → IP-KVM 项目。开发机是 Mac mini M4（arm64），板子通过串口和 SSH 访问。

- 板子访问：`ssh vim4`（khadas@192.168.50.210，sudo 密码 `khadas`）；串口 `/dev/cu.usbserial-100` @ 921600
- 串口执行命令：`tools/uart-run.py [-t 秒] '命令'`。命令超时后板上 shell 仍可能在执行，后续输入会排队——长任务放后台并轮询结果文件
- 抓串口日志：`tools/uart-log.py -t 秒 -o logs/xxx.log [--send '命令']`；日志放 `logs/`（已 gitignore）
- 重装系统：先让用户按 FUNCTION+RESET 进 OOWOW，再 `tools/oowow-flash.sh --yes [镜像]`（清空 eMMC，需用户确认）
- 不要用 OOWOW 官方 `/shell/write` 脚本或流式管道写盘，原因见 `docs/bringup-log.md`
- 每次上板操作后把关键发现追加到 `docs/bringup-log.md`
