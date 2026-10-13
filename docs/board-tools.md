# Agent 板级操作入口

主机需要 Python 3.11+、OpenSSH 和已接好的串口。默认 SSH 别名 vim4，串口
/dev/cu.usbserial-100，921600 baud；Linux 可用 --device 指定 /dev/ttyUSB0。
所有命令从主仓库根目录运行。不要把构建成功、刷写校验成功与硬件回归通过混为一谈。

## 日常选择

| 任务 | 入口 | 是否影响板子 |
|---|---|---|
| 初始化/查看源码 | tools/workspace.py bootstrap / status | 否 |
| 用户态打包与隔离验证 | tools/ubuntu-build.py package / verify | 否 |
| 内核包与整机镜像 | tools/ubuntu-image.py kernel / assemble / verify / export | 否 |
| 只读服务检查 | tools/board.py check | SSH 读取、HTTP GET |
| 从 Ubuntu 进入 OOWOW | tools/board.py recover --exclusive | 重启，中断 KVM |
| 整机刷写 | tools/board.py flash（见下） | 清空 eMMC，重启 |
| 原始串口命令/日志 | tools/uart-run.py / uart-log.py | 取决于命令；不要并行使用 |

现有 tools/oowow-flash.sh 保留为手工 URL 刷写入口；新的本地候选镜像测试优先使用
board.py，以便校验导出清单、限制文件共享范围并记录全过程。
组件包安装与服务迁移仍按 [ubuntu-build.md](ubuntu-build.md) 操作；board.py 不自动
删除 /etc 下的手工服务、不批量覆盖配置，也不把整机刷写用于每次应用迭代。

## 操作前约定

- recover/flash 必须先协调其他 agent 释放板子，并关闭 tio 等串口终端。
  --exclusive 是调用者对独占状态的声明，不会自动发现其他机器或任务。
- flash 需要用户明确授权清空 eMMC。--yes-erase-emmc 表示已有授权，不是获取授权的替代。
- 同一工作区的 board.py 有进程锁；串口工具也有端口锁。外部终端未必遵守这些锁。
- SSH 使用现有密钥与 known_hosts，保持主机身份校验。工具不存储密码、不更改 SSH 配置。
- sudo 免密或现有缓存可用时直接运行；否则交互提示密码。agent 无终端时可以用
  --sudo-password-stdin 从安全凭据提供方读取一行，不把密码放在参数、代码或日志中。

## 远程进入恢复环境

```sh
python3 tools/board.py recover --exclusive
```

先检查串口与板型，SSH 调用板上 /usr/local/bin/reboot2oowow，记录 60 秒串口日志，
再确认 OOWOW shell 和 eMMC 存在。不会刷盘。超时不自动反复重启。
此入口已确认存在于当前板子；实际远程切换尚未在本工具中执行验证。
官方说明：[远程进入 OOWOW](https://forum.khadas.com/t/how-to-switch-to-boot-with-oowow-remotely/21754)。

## 本地候选镜像一键刷写

把示例 192.168.50.2 替换成 Mac 在板子所在局域网的实际 IPv4 地址。
先离线预检，--dry-run 不连接 SSH/串口、不启动 HTTP 服务：

```sh
python3 tools/board.py flash --exclusive --yes-erase-emmc \
  --image build/images/vim4-kvm-ubuntu-0.1.0-dev2/vim4-kvm-ubuntu-0.1.0-dev2.img.xz \
  --serve-address 192.168.50.2 --dry-run
```

取得刷盘授权并完成独占协调后，删除 --dry-run 执行。若已经在 OOWOW，增加
--already-oowow 跳过 SSH 重启步骤。必须保留网线和 USB-C 供电；TF 卡可能改变启动优先级。

流程：本地压缩包和解压内容 SHA256 → 串口预检 → 远程进入 OOWOW → 板型、磁盘容量、
挂载状态检查 → 临时 HTTP 下载 → 板上 SHA256/xz 校验 → OOWOW API 写盘 → 按原始镜像
长度读回 SHA256 → 重启并记录 180 秒启动日志。
HTTP 仅绑定指定地址的临时端口，只开放本次随机 URL，下载结束关闭，不暴露目录。
Mac 防火墙需允许板子连接该端口。整个镜像在 OOWOW /tmp 中下载，需有足够 RAM。

结果写入 logs/board-时间-随机值/；可用 --log-dir 指定一个尚不存在的目录。
operations.log 保存步骤输出，recovery-uart.log/firstboot-uart.log 保存启动过程。
校验失败不会重启。后台下载、写入、读回任务超时会报告板上 .done/.log 路径；
任务可能仍在运行，必须先检查，不能直接重试刷机或断电。无自动续刷。

## 首次启动与检查

```sh
python3 tools/board.py check
```

检查预期内核（可用 --kernel 指定）、tvserver/HDMI/gadget/NanoKVM 服务、采集和 HID
设备节点、本机 8080 HTTP，并输出 UDC 状态和失败单元。UDC 未连接会显示，但不表示
HID 实测失败；检查成功也不代表实际键鼠、画面、音频或延迟通过。

新镜像没有注入开发者公钥，SSH 主机密钥也会重新生成。因此刷写入口只自动做到
写盘校验和启动日志采集，**不会声称首次启动检查已通过**。需要通过可信串口核对
新主机身份、安装开发公钥后再运行 check；不自动清理 known_hosts 或关闭主机校验。
首次完整测试还需确认根分区扩容、分辨率切换、H264/MJPEG、音频和 HID 实际输入。

软件恢复依赖 Ubuntu/SSH 可用；系统死机、供电故障仍需物理复位或独立控制硬件。

## 工具验证边界

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

离线测试覆盖损坏镜像拒绝、确认开关、dry-run 无硬件访问、HTTP 文件隔离、写入失败
禁止重启、串口退出码和缺失完成标记。此工具尚未实际重启或刷写 VIM4，不能仅凭
离线测试将它标记为已完成实机验证。
