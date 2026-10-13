# 构建与部署

板级自动化先读 [board-tools.md](../board-tools.md)：远程进入 OOWOW、本地镜像刷写、
启动日志与只读服务检查统一使用 tools/board.py。

Ubuntu 隔离构建与组件打包先读 [ubuntu-build.md](../ubuntu-build.md)。
内核打包与离线候选镜像组装见 [ubuntu-image.md](../ubuntu-image.md)。

先读 [工作区](../workspace.md)、[硬件](../hardware.md)，再按目标读
[内核](../kernel.md)、[USB-PD](../usb-pd.md) 或
[应用安装](../../NanoKVM-Pro/VIM4.md)。

SSH 为 ssh vim4（khadas@192.168.50.210），串口 /dev/cu.usbserial-100，921600 8N1。
命令使用 tools/uart-run.py，只读日志用 tools/uart-log.py，输出放不入库的 logs/。
串口超时不表示板上命令终止，长任务后台运行并轮询。

sudo 使用既定本地凭据，不在新文档和日志中复制凭据。
配置先 scp 到临时位置再 sudo cp，避免密码与 heredoc 共用 stdin。
长期命令使用 nohup setsid command </dev/null >log 2>&1 &，避免 sudo -b 挂住 SSH。

内核安装用 tools/kernel-install.sh。重装清空 eMMC，须用户明确确认；
优先使用 tools/board.py recover 远程进入 OOWOW；系统无法响应时，按住 FUNCTION、
短按 RESET、松开 FUNCTION。刷写见板级工具文档，禁止直接用 OOWOW /shell/write。

镜像构建需记录各仓库提交、模块、插件、板级服务和应用配置。
上板关键发现记入 [bringup-log.md](../bringup-log.md)，可复用教训归
[LESSONS.md](../../LESSONS.md)，临时实验配置不能写成已验证默认值。
