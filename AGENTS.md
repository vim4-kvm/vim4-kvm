# AGENTS.md

Khadas VIM4 → IP-KVM 项目。开发机是 Mac mini M4（arm64），板子通过串口和 SSH 访问。

- 板子访问：`ssh vim4`（khadas@192.168.50.210，sudo 密码 `khadas`）；串口 `/dev/cu.usbserial-100` @ 921600
- 串口执行命令：`tools/uart-run.py [-t 秒] '命令'`。命令超时后板上 shell 仍可能在执行，后续输入会排队——长任务放后台并轮询结果文件
- 抓串口日志：`tools/uart-log.py -t 秒 -o logs/xxx.log [--send '命令']`；日志放 `logs/`（已 gitignore）
- 重装系统：先让用户按 FUNCTION+RESET 进 OOWOW，再 `tools/oowow-flash.sh --yes [镜像]`（清空 eMMC，需用户确认）
- 不要用 OOWOW 官方 `/shell/write` 脚本或流式管道写盘，原因见 `docs/bringup-log.md`
- 本仓库位于 `~/Developer/github/localhost-copilot/vim4-kvm/vim4-kvm/`（目录结构镜像 GitHub org vim4-kvm）；内核驱动在同级 `common_drivers/`，内核树在 OrbStack VM `vim4-build` 的 `~/src/linux`，构建见 `docs/kernel.md`
- 板上 sudo 用 `echo khadas | sudo -S -p "" cmd`，**不要**和 heredoc 混用（凭据缓存后 sudo 不读 stdin，heredoc 会吃到密码）；写配置文件用 scp 到 /tmp 再 `sudo cp`
- 装内核用 `tools/kernel-install.sh`；**禁止**不带 `--keep-directory-symlink` 往 `/` 解 tar（会把 `/lib` 符号链接换成目录，系统全挂）
- 后台跑板上程序用 `nohup setsid prog </dev/null >log 2>&1 &`（`sudo -b` 会卡住 ssh）
- 每次上板操作后把关键发现追加到 `docs/bringup-log.md`
