# Ubuntu ARM64 构建与组件包

> 摘要：打组件包读「使用」；改包依赖或安装逻辑读「包和安装边界」「单独发布与网页
> 更新」；PiKVM 读「PiKVM 组件」。「已完成的隔离验证」是历史证据，通常不必读。

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
  builder image ID。开发构建自动编号并记录脏状态；指定正式版本时必须全部源码干净。

快照方法见 [Ubuntu Snapshot Service](https://snapshot.ubuntu.com/)。快照服务有
保留期限，长期发布需保留构建镜像与输入归档；固定地址不能替代长期存档。

## 使用

需要 Docker、Python 3.11+ 和已克隆的源码仓库：

```sh
python3 tools/ubuntu-build.py environment
python3 tools/ubuntu-build.py package --component manager
# 使用上一步输出的版本（示例，序号和提交号以实际输出为准）
python3 tools/ubuntu-build.py verify --component manager --version 2.5.1+vim4.20261016.1020.dev.1.g49c45f2.dirty
```

构建容器原生使用 linux/arm64，源码只读挂载并复制到容器独立工作目录；Mac
上的 node_modules、编译产物不参与 Linux 构建。输出在 build/packages/VERSION，
已有目录会拒绝覆盖。失败目录保留以便诊断，重跑请选新版本或人工清理该次产物。
打包前会比对构建镜像记录的 Dockerfile、下载锁及构建脚本摘要；旧镜像或输入变化
会明确要求先重跑 `environment`，避免沿用缺少新 SDK 的同名标签。
构建使用的镜像另以 `vim4-package-builder:<镜像摘要>` 保留，重建可变 builder 标签
不会移除 `sources.json` 记录的镜像；该保留镜像供后续 `verify` 使用。
APT 对暂时下载失败重试三次，索引仍不完整则停止，不继续使用部分索引安装。

verify 在新的临时容器检查校验和、ARM64 ELF、动态库解析、sudoers 和网页文件，
并执行首次配置与重复配置测试，确认已有 server.yaml 不被覆盖且没有自动启用应用服务。
不要把 packaging/ubuntu/verify.sh 当作宿主机安装脚本执行。
校验也检查 HDMI 音频的启动顺序、ExecStartPre 路由和板级包的 alsa-utils 依赖，
防止当前板子有声音、重新打包后却恢复为静音的遗漏。

package 不传 --version 时自动生成开发版；verify 和后续镜像 assemble 的 --components
必须使用 package 输出的同一版本，不隐式选择旧产物。

版本约定：正式版为 `x.y.z+vim4.YYYYMMDD.N`（UTC 日期、递增编号），开发版在
所属组件最新正式 tag 后追加 `.dev.N.g<提交号>`，有未提交修改时追加 `.dirty`。
开发序号在本机已有包目录上递增，分配时持锁；失败目录也占用序号，不要覆盖或清空后复用。
组合构建以所含组件的最高正式版本为基础。构建会刷新 tags；离线时警告并使用本地 tags，
没有 tag 时以 `0.0.0+vim4.00000000.0` 为基础，部署前应先联网同步正式版本。
排序为「基础正式版 < 开发版 < 下一正式版」，版本格式同时兼容 dpkg 与各应用更新器。
`sources.json` 记录实际版本、开发标记、各仓库提交和内容摘要；干净源码的本地试构建也标为开发版。
`--allow-dirty` 已移除；未提交源码不能通过 `--version` 冒充正式版。
CI 编号从 run number 推导，并超过已有同日 tags，兼容旧的 1000 段编号与重跑。
CI 发布前再次拒绝开发版本号、开发标记或脏源码；网页更新只接收正式版。

构建先检查 PD 边界、工作区工具和 NanoKVM deploy/vim4 下的 Python 部署测试，
再编译两个插件，运行 VIM4 Go 测试并构建
服务端、前端，随后验证上游 Go 目标和 sudoers。完整测试日志应由调用者保存。
这里的通过不意味着硬件采集、编码、PD 和端到端延迟通过。

## 包和安装边界

| 包 | 内容 |
|---|---|
| vim4-kvm-board | PD 工具、HDMI/gadget 脚本、udev 和 systemd 配置 |
| vim4-vfmcap | vfmcapsrc / vim4vdin1src、原生 HDR 的私有标准 V4L2 插件；提供 vim4-vdin1-api-1 |
| vim4-amlvenc | /usr/lib/vim4-kvm 下的编码插件及服务搜索路径 |
| vim4-nanokvm | /opt 应用与网页、/usr/libexec 特权工具、sudoers 与应用服务 |
| vim4-jetkvm | JetKVM 应用、特权工具与服务 |
| vim4-onekvm | One-KVM 应用（嵌入网页）、Ventoy 引导资源、虚拟介质助手与互斥服务 |
| vim4-manager | 四套应用选择、板级状态、HDR 曲线、EDID 兼容性预设与风扇曲线 |

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

## 单独发布与网页更新

每个应用在各自仓库发布，板子从对应仓库的 `releases/latest/download` 读取更新：

| 组件 | 仓库 | 包 | 板上更新入口 |
|---|---|---|---|
| nanokvm | NanoKVM | vim4-nanokvm | NanoKVM 设置 → 更新（`nanokvm_pro_latest.json` 与 tar.gz） |
| jetkvm | kvm | vim4-jetkvm | JetKVM 设置 → 更新（`releases`） |
| onekvm | One-KVM | vim4-onekvm | One-KVM 设置 → 更新（`onekvm-*.json`） |
| onekvm-board | vim4-kvm | 板级＋One-KVM 两包 | 涉及共享介质 API 的组合部署，不做网页更新 |
| pikvm-app | kvmd | vim4-pikvm | 管理面板 → 更新（`vim4-pikvm-latest.json`） |
| manager | vim4-manager | vim4-manager | 管理面板 → 更新（`vim4-manager-latest.json`） |
| platform | vim4-kvm | 板级、采集、编码三包 | 组件部署或镜像，不做网页更新 |
| capture | gst-plugin-vfmcap | vim4-vfmcap | 组件部署或镜像 |
| encoder | gst-plugin-venc | vim4-amlvenc | 组件部署或镜像 |

`--component` 只构建并验证所选组件，`packaging/ubuntu/feeds.py` 按各应用原有更新协议生成清单，
`check-feeds.py` 校验清单哈希、大小与下载地址。五个更新入口都只允许替换自身一个包：
APT 预演需要新增或升级平台包时拒绝安装，先部署平台组件。

镜像仍用 `--component pikvm` 同时构建 PiKVM 与管理器；独立发布使用 `pikvm-app`，
避免把另一个仓库尚未发布的管理器版本混入更新源。

CI 使用主仓库的可复用工作流 `.github/workflows/release-component.yml`，在 GitHub
`ubuntu-24.04-arm` 原生运行。各仓库的 `vim4-release.yml` 在分支推送、PR 与普通手动运行时只构建验证；
推送 `release-*` 标签或手动勾选 publish 才发布。发布时其他仓库取 workspace.toml 固定版本，
本仓库取触发提交。版本为 `2.5.1+vim4.UTC日期.(1000+2×运行序号)`，排在同日本地构建之后；
同一次整机镜像构建的 PiKVM 补充包序号再加 1，避免两个组件目录相撞。
Release 标签与包版本相同并标为 latest。uStreamer 验证完整 PiKVM 集成后独立发布源码；
其二进制随 kvmd 的 PiKVM 包发布。linux/common_drivers 共用 `kernel.yml` 构建内核 deb。
CI 不访问板子，发布不代表实机回归通过。
构建任务只有读取权限，独立发布任务才取得 Release 写权限。构建镜像缓存按 Dockerfile、
下载清单、Python 锁文件及下载脚本的哈希失效；PR 可以读取缓存，但不保存缓存。
首次运行仍需从 Ubuntu 快照源下载完整依赖，可能比本地复用 builder 慢很多。
主仓库另有手动触发的 `Ubuntu image` 工作流：构建完整组件、PiKVM 补充包和
固定内核，再在 Linux ARM64 上组装、离线验证并上传镜像。默认只上传 Actions
artifact；显式选择 publish 才发布整机候选镜像，不代替上板启动测试。

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
