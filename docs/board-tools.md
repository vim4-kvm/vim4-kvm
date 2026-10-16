# Agent 板级操作入口

> 摘要：日常操作先读「日常选择」和「操作前约定」；部署读「增量开发闭环」；
> 进 OOWOW/刷机读「远程进入恢复环境」「本地候选镜像一键刷写」；其余节只在
> 对应回归测试时读取。

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
| 首次接入（公钥 + 免密 sudo） | tools/board.py provision | 默认密码登录一次，写 authorized_keys 与 sudoers |
| 开发板免密 sudo（单独） | tools/board.py enroll | 安装 sudoers 文件 |
| 增量安装七组件包 | tools/board.py deploy --exclusive（板上调用 install-components.sh） | 板上安装，恢复管理器所选应用 |
| 部署后功能验证 | tools/board.py verify | 移动 Mac 光标、录 1 秒音频、打开一个 WebRTC 会话 |
| 浏览器视频冒烟测试（单独） | tools/video-smoke.mjs | 打开一个 WebRTC 会话 |
| 从 Ubuntu 进入 OOWOW | tools/board.py recover --exclusive | 重启，中断 KVM |
| 整机刷写 | tools/board.py flash（见下） | 清空 eMMC，重启 |
| 原始串口命令/日志 | tools/uart-run.py / uart-log.py | 取决于命令；不要并行使用 |

现有 tools/oowow-flash.sh 保留为手工 URL 刷写入口；新的本地候选镜像测试优先使用
board.py，以便校验导出清单、限制文件共享范围并记录全过程。
组件包构建见 [ubuntu-build.md](ubuntu-build.md)，增量部署见下。board.py 不自动
删除 /etc 下的手工服务，也不把整机刷写用于每次应用迭代。

仅更新管理器时，包清单 `sources.json` 可声明 `component: "manager"`，目录只包含
对应版本的 vim4-manager deb、sources.json 与 SHA256SUMS，仍使用 `board.py deploy`。
此路径取得管理器操作锁，仅停止和启动 vim4-manager，不重启 KVM 应用、HDMI、USB
或修改 EDID，适用于保留显示故障现场。它是部署入口；ubuntu-build.py 尚不提供
manager 单组件构建选项，开发交叉编译包需如实记录构建方式。

仅更新 One-KVM 时可声明 `component: "onekvm"`，只打包并安装 vim4-onekvm。
此模式沿用应用升级流程：暂停 KVM 应用，安装后恢复管理器所选应用并重启管理器，
不升级其他组件包；并非 manager 模式的无中断路径。需记录单组件构建来源。

## 增量开发闭环

协调板子独占后，选择新的版本号；三个构建/验证/上传步骤使用同一版本：

```sh
version=1.0.3+vim4.20261012.1
python3 tools/ubuntu-build.py package --version "$version"
python3 tools/ubuntu-build.py verify --version "$version"
python3 tools/board.py deploy --exclusive --packages "build/packages/$version"
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs python3 tools/board.py verify
```

board.py deploy 先在本地按 SHA256SUMS 校验七个 deb 和 sources.json 并输出脏源码仓库
（--dry-run 到此为止），记录板上原有版本（Previous 行，回退时用对应目录再次 deploy），
上传整个包目录与安装脚本到板上临时目录，以 sudo 运行 install-components.sh，
确认七包版本一致后运行 check。已 enroll 的开发板无需密码。
安装失败时应用保持停止，先 `dpkg --audit` 检查，不要连续重试。

示例版本已部署，重新构建使用新版本。安装脚本验证七包的 SHA256、名称、架构、
相同版本和非降级条件，先模拟 APT 安装，随后暂停应用并恢复原选择。保留应用配置。
只迁移与候选包内容相同或仅已知旧路径不同的服务、udev 和 sudoers 文件；sudoers
也允许由 dpkg 登记且内容仍与旧包 Conffiles 校验和一致的文件随新版升级。未知覆盖
会在停服务之前拒绝；RTP 等其他管理员 drop-in 保留。修复启用链接指向包内服务，
不重新执行 USB-PD 协商、不重启系统、不更新内核。失败不自动启动可能混装的应用。
这是现有 VIM4 系统的升级入口，不代替完整镜像首次安装。

video-smoke.mjs 需要 Playwright 和 Chrome，默认采样 15 秒，输出实际解码帧数、
尺寸、丢帧和丢包；无视频或连接断开返回失败。它使用当前页面配置，需要无认证
页面且默认显示 WebRTC 视频，不修改账户认证。此测试不测输入响应、音频或端到端延迟。

One-KVM 使用 `tools/one-kvm-smoke.mjs --exclusive`，通过 ONEKVM_USERNAME 和
ONEKVM_PASSWORD 环境变量提供独立网页账户。可加 `--mode=h265` 或 `--mode=mjpeg`，
结束恢复原模式；首次初始化必须显式加 `--initialize`。音频解码验证使用
`one-kvm-audio-check.mjs --exclusive`，输入端应播放有声内容；USB 主机为本机 Mac 时，
`one-kvm-usb-check.mjs --exclusive` 检查键鼠、测试 ISO 和重新枚举后的键鼠，
ONEKVM_TEST_ISO 指向包含测试标记的 ONEKVM_TEST 卷。三套应用切换使用
`kvm-switch-check.mjs --exclusive`，结束恢复初始选择。这些实机测试依次运行，
不要并发登录同一个 One-KVM 账户，以免会话替换干扰结果。

`one-kvm-smoke.mjs --exclusive --audio` 会通过 Web Audio 检查 WebRTC 解码波形，
需从 HDMI 输入播放非静音测试信号；不以浏览器 totalAudioEnergy 单项统计替代声音证据。
`one-kvm-features-check.mjs --exclusive` 检查终端、扩展及看门狗，本地 FRP 测试服务
须监听 127.0.0.1:17700，使用脚本中的测试 token。结束恢复关闭状态和原配置，
`--restore-drive` 仅用于测试前原本已连接虚拟盘的场景。测试 FRP 服务不得监听公网。

`one-kvm-usb-profile-check.mjs --exclusive` 检查 HID 组合、禁用/重新启用、UAC 枚举、
三种 USB 网卡、超限回滚及网页保存；保存原配置到日志并在 finally 恢复。
`--audio` 另要求 macOS 已授予录音终端麦克风权限，以及编译好的
`/tmp/uac-record-level`。录音器可按名称或厂商选择 USB 输入，不改变系统默认输入。
VIM4 UAC2 在 macOS 可能显示为 `Capture Inactive`；设备名本身不代表无音频。
板端 `one-kvm-usb-board-check.py` 只能在应用停止且介质已安全弹出并卸载时运行，
直接验证助手的枚举与恢复。实际键鼠及 ISO 读取仍用 `one-kvm-usb-check.mjs`。

board.py verify 先运行 check，再逐项输出 PASS/FAIL/SKIP，并写入日志目录的 verify.json：

| 项 | 方法 | SKIP 条件 |
|---|---|---|
| hid | 向 /dev/hidg1 写两次绝对坐标，用 osascript 读取 Mac 光标核对（误差 2%），最后恢复原位置 | 本机不是 gadget 的 USB 主机 |
| audio | arecord 读 hw:AMLAUGESOUND,0 一秒，要求帧数完整；输出峰值，0 表示信源静音 | PCM 被应用音频会话占用 |
| video | video-smoke.mjs 采样 10 秒，地址取自 ssh -G | 无 node/Playwright |

SKIP 不算通过。hid 假定 Mac 只有一个显示器；会短暂移动光标，不点击。
不覆盖键盘输入、音频内容、运动画面和端到端延迟（见 [latency.md](latency.md)）。

## 操作前约定

- recover/flash 必须先协调其他 agent 释放板子，并关闭 tio 等串口终端。
  --exclusive 是调用者对独占状态的声明，不会自动发现其他机器或任务。
- flash 需要用户明确授权清空 eMMC。--yes-erase-emmc 表示已有授权，不是获取授权的替代。
- 同一工作区的 board.py 有进程锁；串口工具也有端口锁。外部终端未必遵守这些锁。
- SSH 使用现有密钥与 known_hosts，日常保持主机身份校验，不更改 SSH 配置。
  只有 flash 成功后（或显式 provision --replace-host-key）才删除该地址的旧主机密钥并接受新密钥。
- 开发板先运行一次 `printf 'khadas\n' | python3 tools/board.py enroll --sudo-password-stdin`
  （默认密码见 [硬件](hardware.md#默认账户开发环境)），安装
  board/vim4-dev-nopasswd.sudoers，之后 deploy/recover 全自动，不存储任何密码。
  该文件不进入组件包和整机镜像；新刷的镜像需重新 enroll。撤销：
  `sudo rm /etc/sudoers.d/vim4-dev-nopasswd`。不修改账户密码。
- 未 enroll 时交互提示密码；无终端用 --sudo-password-stdin 经 stdin 传入，不放进参数或日志。

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

新镜像没有开发者公钥，SSH 主机密钥也会重新生成。flash 在启动日志采集后自动运行
provision 和 check：等待 22 端口，删除 known_hosts 中该地址的旧密钥并接受新密钥，
公钥登录失败时用默认账户密码（见 [硬件](hardware.md#默认账户开发环境)）登录一次，
把 ssh -G 中 IdentityFile 对应的 .pub 追加到 authorized_keys，再 enroll 免密 sudo。
密码只经临时 askpass 的环境变量传给 ssh，不进入参数和日志。

已有公钥和免密 sudo 的板子上 provision 不做任何修改，可重复运行。板子曾手工重装时：

```sh
python3 tools/board.py provision --replace-host-key
```

首次完整测试还需确认根分区扩容、分辨率切换、H264/MJPEG、音频和 HID 实际输入
（board.py verify 覆盖其中一部分）。

软件恢复依赖 Ubuntu/SSH 可用；系统死机、供电故障仍需物理复位或独立控制硬件。

## KVM 应用切换回归

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  node tools/kvm-switch-check.mjs --exclusive http://192.168.50.210
```

保留上一界面的视频连接，通过管理器接口执行两轮 NanoKVM → JetKVM → NanoKVM。
每次核对服务互斥、开机启用状态，再在 Chrome 采样 10 秒实际解码帧数、丢帧和丢包。
最终保持 NanoKVM。两个入口使用不同的 `?kvm=` 参数，避免共用 8080 时复用另一应用的首页缓存。
测试要求两个应用已完成初始化；不会自动创建账户或修改认证。
`Conflicts=` 不保证退出顺序，管理器必须等旧服务完全停止后再启动新服务。

## USB 切换回归

必须先启动包含两项 HID 生命周期修复的内核，详见 [内核](kernel.md)。
`tools/hid-rebind-check.py` 在应用停止、板子独占时验证 epoll 描述符跨 UDC
重新绑定。旧内核不能运行此测试，会触发 panic。

应用层回归先上传可丢弃的 ISO，并确认麦克风关闭、没有挂载其他镜像：

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  node tools/usb-switch-check.mjs http://192.168.50.210:8080 \
  /var/lib/vim4-kvm/images/test.iso --exclusive
```

脚本保持原查看页面连接，执行三轮麦克风/镜像组合切换，结束时弹出镜像并恢复
NCM。它会短暂断开 USB，不能与用户输入或其他硬件任务并行。验证的是 API
切换和恢复，不包含被控机录音、镜像文件读写或音画延迟。

## 工具验证边界

浏览器镜像上传与 Bash 终端回归（会在板上保留上传的镜像，重名不会覆盖）：

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  node tools/media-upload-check.mjs --exclusive /path/to/image.iso
```

使用原生 File/FormData 验证上传响应，并通过真实终端 WebSocket 回读 Bash 版本。
此命令不验证镜像可启动、USB 挂载或文件系统写入；这些证据单独记在上板记录中。

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

离线测试覆盖损坏镜像拒绝、确认开关、dry-run 无硬件访问、HTTP 文件隔离、写入失败
禁止重启、串口退出码和缺失完成标记；部署覆盖包集合校验、委托板上安装脚本、
版本不一致时不报告通过、sudo 密码不进入命令行。此工具尚未实际重启或刷写 VIM4，不能仅凭
离线测试将它标记为已完成实机验证。
