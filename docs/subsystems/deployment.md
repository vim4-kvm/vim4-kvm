# 构建与部署

板级自动化先读 [board-tools.md](../board-tools.md)：组件包部署、远程进入 OOWOW、
本地镜像刷写、启动日志与只读服务检查统一使用 tools/board.py。

Ubuntu 隔离构建与组件打包先读 [ubuntu-build.md](../ubuntu-build.md)。
PiKVM 使用 `--component pikvm` 单独构建和验证，部署仍使用 board.py；复用 `.24`
或更新板级组件。切换应用前先在 USB 主机安全弹出虚拟介质。
内核打包与离线候选镜像组装见 [ubuntu-image.md](../ubuntu-image.md)。

先读 [工作区](../workspace.md)、[硬件](../hardware.md)，再按目标读
[内核](../kernel.md)、[USB-PD](../usb-pd.md) 或
[应用安装](../../NanoKVM/VIM4.md)。

SSH 为 ssh vim4（khadas@192.168.50.210），串口 /dev/cu.usbserial-100，921600 8N1。
命令使用 tools/uart-run.py，只读日志用 tools/uart-log.py，输出放不入库的 logs/。
串口超时不表示板上命令终止，长任务后台运行并轮询。

默认账户 khadas/khadas、root/khadas 见 [硬件](../hardware.md#默认账户开发环境)；
日志和命令行参数不写入密码，经 stdin 传给 sudo。
配置先 scp 到临时位置再 sudo cp，避免密码与 heredoc 共用 stdin。
长期命令使用 nohup setsid command </dev/null >log 2>&1 &，避免 sudo -b 挂住 SSH。

内核安装用 tools/kernel-install.sh。重装清空 eMMC，须用户明确确认；
优先使用 tools/board.py recover 远程进入 OOWOW；系统无法响应时，按住 FUNCTION、
短按 RESET、松开 FUNCTION。刷写见板级工具文档，禁止直接用 OOWOW /shell/write。

镜像构建需记录各仓库提交、模块、插件、板级服务和应用配置。
上板关键发现按 [上板记录索引](../bringup/README.md) 新建条目，跨子系统教训归
[LESSONS.md](../../LESSONS.md)、子系统教训归对应文档的「错题」，临时实验配置不能写成已验证默认值。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| 部署后不久内核 panic，刚装的 sudoers 变成 0 字节 | 原根分区 data=writeback、commit=600。新部署配置 ordered/commit=5；所有组件安装成功前 sync，网页更新复核文件后再重启。它不保证升级原子性，也不证明其他文件没有损坏 | tools/rootfs-policy.py、[上板记录](../bringup/2026-10-13-hid-lifecycle-deploy-reliability.md) |
| 从 HDR 分支构建管理器后，已部署的趋势图表消失 | 图表在另一工作树的未提交改动中。部署前同时核对固定分支与已部署功能，合并到同一可构建提交；保留原工作树不等于保留线上功能 | vim4-manager onekvm 分支、logs/one-kvm/manager-final.png |
| 提高应用包对平台包的版本下限后，网页更新一律失败 | 五个更新入口都只允许替换自身一个包，APT 预演需要升级 vim4-kvm-board/vfmcap/amlvenc 时直接拒绝。只有在新平台组件已部署或已进镜像后才提高下限，并先单独发布 platform；CI 通过不代表现有板子能网页升级 | packaging/ubuntu/package.py PLATFORM、vim4-manager-helper update |
