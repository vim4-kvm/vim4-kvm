# Ubuntu ARM64 构建与组件包

系统保持 Ubuntu 24.04。这里定义的是用户态组件构建与打包，不是可刷入镜像；
启动加载器、分区、内核及完整 Khadas BSP 根文件系统仍按后续镜像阶段集成。
构建不挂载板子设备、不执行 SSH、不停启板子服务。

## 固定输入

- packaging/ubuntu/Dockerfile 固定 Ubuntu 基础镜像摘要及 ARM64 架构。
- APT 指向 20261012T000000Z 的显式 Ubuntu 快照，保留签名校验。
  check-valid-until=no 只允许历史 Release 过期，不跳过签名。
- downloads.lock.json 固定 Go、Rust、Node、pnpm 和 Khadas 开发库下载 SHA256。
  厂商 deb 只解包到构建容器，不执行其安装脚本；不从工作板抓取二进制。
- 源码版本来自工作树，sources.json 记录各仓库提交、脏状态、内容摘要和实际
  builder image ID。默认拒绝脏工作树，开发试构建需显式 --allow-dirty。

快照方法见 [Ubuntu Snapshot Service](https://snapshot.ubuntu.com/)。快照服务有
保留期限，长期发布需保留构建镜像与输入归档；固定地址不能替代长期存档。

## 使用

需要 Docker、Python 3.11+ 和已克隆的源码仓库：

```sh
python3 tools/ubuntu-build.py environment
python3 tools/ubuntu-build.py package --version 0.1.0~dev4
python3 tools/ubuntu-build.py verify --version 0.1.0~dev4
```

构建容器原生使用 linux/arm64，源码只读挂载并复制到容器独立工作目录；Mac
上的 node_modules、编译产物不参与 Linux 构建。输出在 build/packages/VERSION，
已有目录会拒绝覆盖。失败目录保留以便诊断，重跑请选新版本或人工清理该次产物。

verify 在新的临时容器检查校验和、ARM64 ELF、动态库解析、sudoers 和网页文件，
并执行首次配置与重复配置测试，确认已有 server.yaml 不被覆盖且没有自动启用应用服务。
不要把 packaging/ubuntu/verify.sh 当作宿主机安装脚本执行。
校验也检查 HDMI 音频的启动顺序、ExecStartPre 路由和板级包的 alsa-utils 依赖，
防止当前板子有声音、重新打包后却恢复为静音的遗漏。

package/verify 必须显式提供 --version；后续镜像 assemble 的 --components 使用同一值。
示例版本已有产物时，请三个命令一起换成新的版本，不覆盖已有包。

构建先检查 PD 边界、工作区工具和 NanoKVM deploy/vim4 下的 Python 部署测试，
再编译两个插件，运行 VIM4 Go 测试并构建
服务端、前端，随后验证上游 Go 目标和 sudoers。完整测试日志应由调用者保存。
这里的通过不意味着硬件采集、编码、PD 和端到端延迟通过。

## 包和安装边界

| 包 | 内容 |
|---|---|
| vim4-kvm-board | PD 工具、HDMI/gadget 脚本、udev 和 systemd 配置 |
| vim4-vfmcap | 系统 GStreamer 目录中的采集插件 |
| vim4-amlvenc | /usr/lib/vim4-kvm 下的编码插件及服务搜索路径 |
| vim4-nanokvm | /opt 应用与网页、/usr/libexec 特权工具、sudoers 与应用服务 |
| vim4-jetkvm | JetKVM 应用、特权工具与服务 |
| vim4-onekvm | One-KVM 应用（嵌入网页）、Ventoy 引导资源、虚拟介质助手与互斥服务 |
| vim4-manager | 三套应用选择、板级状态与 HDR 曲线 |

包不占用 /usr/local，遵循 [Debian 路径约定](https://www.debian.org/doc/debian-policy/ch-opersys.html)。
NanoKVM 特权调用与手工安装脚本同步改为 /usr/libexec，新服务端必须与新工具一起安装。
原有手工安装的 /etc/systemd/system 单元和编码插件 drop-in 可能覆盖包提供的
/usr/lib 单元；迁移前应人工核对，不由包自动删除管理员文件。

这些包供 Khadas Ubuntu 基础系统使用：必须已有 khadas 用户、tvserver、hdmiin-demo、
固件、自编内核及厂商运行库；不能单独把普通 Ubuntu 容器变成可启动 VIM4 系统。
编码包明确依赖固定的厂商运行库版本，下载清单中的 deb 不随组件包重新发布。
板级包依赖固定版本 hdmiin-demo，它同时提供 tvserver.service。

安装不自动启用或重启服务，不在 postinst 操作 configfs、I2C、网络或密码。
应用首次配置建立所需目录，只在 server.yaml 不存在时写入既定默认值，升级保留
用户配置。需要在镜像集成阶段显式设置服务启用和冲突服务禁用；不要直接运行
现有 board/install.sh 来模拟离线安装，因为它会操作正在运行的系统。

组件包 postinst 在成功返回前 sync；应用包同时检查辅助程序和 sudoers。
One-KVM 将仓库内 Ventoy 资源解压到 `/usr/share/vim4-onekvm/ventoy`，
安装检查与包验证拒绝缺失的引导文件；用户虚拟盘保留在 `/var/lib/one-kvm/msd/ventoy`。
`tools/one-kvm-drive-check.mjs --exclusive --initialize --mount-host` 可在独占板子时
创建缺失的 256 MiB 虚拟盘并验证网页读写与 macOS USB 读取；已有盘不会重新格式化，
测试结束保留虚拟盘，移除本次测试文件。认证环境变量与其他 One-KVM 检查相同。
网页更新包直接封装这里生成的应用 deb，不另行编译或生成安装配方。更新助手
预检 APT 安装计划：需要新增/升级平台依赖时拒绝安装，要求先部署完整组件。
成功安装后比对辅助程序与 sudoers 内容、执行 visudo、sync，再安排应用重启。
这些检查不能把 dpkg 升级变成断电原子事务；失败后仍需检查并恢复完整安装。

组件部署和镜像组装运行 vim4-rootfs-policy：Default 启动项明确选择
rootflags=data=ordered，根分区和 /boot 的 commit 改为 5 秒。Stock 启动行保持
不变；应用镜像校验检查该配置。现有系统需重启后检查 findmnt / 确认生效。
自定义 rootflags 或显式 fstab data= 设置会要求先审查，不静默覆盖。

每次输出包含七个 deb、sources.json、Ubuntu 包版本列表、外部下载清单及 SHA256SUMS。
SOURCE_DATE_EPOCH 来自主仓库提交；当前尚未证明所有工具链产物逐字节可复现。
默认发布前还需运行 workspace.py bootstrap --locked，并先推送清单引用的组件提交。

## PiKVM 组件

PiKVM 复用已部署的 `.24` 或更新的板级、VFM 与编码组件，单独构建两个包：
`vim4-pikvm`、`vim4-manager`。先构建本页的基础 builder，再执行：

```sh
python3 tools/ubuntu-build.py environment --component pikvm
python3 tools/ubuntu-build.py package --component pikvm --version VERSION
python3 tools/ubuntu-build.py verify --component pikvm --version VERSION
python3 tools/board.py deploy --exclusive --packages build/packages/VERSION
```

配方在 `packaging/ubuntu/pikvm/`。CPython 3.14、Python 依赖、Janus 与 PiKVM 的
Janus JS 补丁均固定版本及校验和；Python 和 nginx 使用私有路径。Janus 直接使用
固定上游源码，无需维护额外 fork。安装不切换应用，管理器新增 PiKVM 选项。
组件模式由 sources.json 记录，部署验证仅比较本次两个组件，保留其他组件版本。
`all` 仍指原有七包，不隐式包含 PiKVM。镜像组装使用 `--pikvm-components VERSION`
加入两个 PiKVM 集成包，并用 `--default-app pikvm` 选择默认界面，见 ubuntu-image.md。

隔离验证检查实际 Janus WebSocket 插件会话、ARM64 动态库、kvmd 配置、nginx 配置、
升级保留认证文件及不自动启用服务。上板检查使用 `tools/pikvm-smoke.mjs --exclusive`，
设置 PIKVM_USERNAME、PIKVM_PASSWORD；`--usb --motion --audio --media --mjpeg` 扩展到
macOS 主机键鼠、画面变化、HDMI 声音、虚拟光盘与视频切换。
`--settings` 检查参数修改与刷新，`--media --switch-guard` 经 VIM4_SSH（默认 vim4）
检查挂载介质时拒绝应用切换。音频需要
PIKVM_TEST_AUDIO WAV，介质需要 PIKVM_TEST_ISO（卷标 PIKVM_TEST，readme.txt 内容
`PiKVM VIM4 virtual media validation`）。测试期间需要独占板子、USB 主机和 HDMI 输出。

## 下一阶段

内核包、锁定基础镜像与离线组装流程见 [ubuntu-image.md](ubuntu-image.md)。
本流程不会改变工作板；实机启动回归和发布 CI 仍未完成。

## 已完成的隔离验证

开发包 0.1.0~dev3 已在固定 ARM64 容器完成四组件构建；PD 边界测试、六项
Python 测试、VIM4 与上游两种 Go 目标测试/构建、前端构建和 sudoers 检查通过。
verify 的 ELF/动态依赖、校验和、配置初始化与升级保留测试通过。
首次干净构建暴露的 GStreamer 测试插件缺失及上游 libkvm 链接桩生成步骤均已补齐。
这些结果不包含板级运行验证或可刷入镜像验证。
