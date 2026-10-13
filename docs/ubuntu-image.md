# Ubuntu 候选镜像

导出后的远程刷写与首次启动检查见 [板级工具](board-tools.md)。

以锁定的 Khadas Ubuntu 24.04 Server / Fenix 1.7.5 镜像为基础，离线加入自编
内核和四个 KVM 组件包。保留原厂引导程序、BSP、用户与密码；不从工作板克隆磁盘。
工具只接受普通镜像文件，不刷写设备。离线验证通过仍不代表 VIM4 实机能启动。

## 前置条件

- 按 [ubuntu-build.md](ubuntu-build.md) 构建并验证组件包，组装时显式传入同一组件版本。
- Mac 通过 OrbStack 的 vim4-build 执行 Linux 操作，主仓库路径须在 VM 中同路径可见。
  原生 Linux ARM64 可直接运行。同一镜像不要被多个任务同时操作。
- VM 中安装 fdisk、cloud-guest-utils、e2fsprogs、xz-utils、rsync、Python 3.11+，
  并可使用 sudo。挂载只关联本次创建的镜像文件，不访问板子。
- 主内核位于 VM 的 ~/src/linux，common_drivers 位于其内部。源码提交必须匹配
  workspace.toml 且无改动；.config 必须与 packaging/kernel/vim4.config 完全一致。
  修改配置或源版本应先审查清单，工具不会自动覆盖工作树。

## 命令

```sh
python3 tools/ubuntu-image.py fetch
python3 tools/ubuntu-image.py kernel
python3 tools/ubuntu-image.py assemble --components 0.1.0~dev4
python3 tools/ubuntu-image.py verify
python3 tools/ubuntu-image.py export
```

kernel 输出 build/packages/kernel 下的 deb 和构建记录。内核版本仍为
5.15.137-vim4kvm；包版本包含内核与驱动提交。模块直接打包到 /usr/lib/modules，
不携带 /lib 目录或符号链接。包安装只执行 depmod，initramfs 与启动切换由镜像阶段负责。
内核编译器版本写入 kernel-build.json；目前仍使用 VM 工具链，并未证明逐字节可复现。

assemble 要求主仓库干净，输出 VM 的 ~/image-build/NAME.img；默认名称
vim4-kvm-ubuntu-0.1.0-dev2。可用 --name 指定名称；assemble 必须提供 --components，
其值须与 ubuntu-build.py package/verify 的 --version 相同，避免默默使用旧包。
已有输出拒绝覆盖；失败文件保留用于诊断。重新构建应选新名称或人工清理失败产物。
默认镜像名称表示当前验证样本，不是自动选择最新发布版本。

export 再次执行结构检查，以 xz 压缩并复制到主仓库 build/images/NAME/，附带
压缩包校验和、原始镜像校验和、系统包版本列表和配方提交。该目录不入 Git。
压缩文件或目标目录已经存在时不会覆盖。

## 基础镜像与组装

packaging/image/base.lock.json 记录官方 URL、SHA256 和固定布局。这套脚本只支持
该版本布局，不能把另一个镜像换进去继续运行。

该官方镜像实际采用 DOS/MBR 分区表：p1 从扇区 32768 开始、240MiB，p2 从
524288 开始。虽然 p1 的 MBR 类型标记为 FAT32，文件系统实际为 ext4。
解压数据末尾有 OOWOW 元数据；工具先截取真实磁盘大小，去掉旧尺寸元数据，
再扩展至 8GiB 并扩大 p2。引导区域和文件系统 UUID 保留。

离线安装使用 Ubuntu 固定软件源快照补齐缺失依赖，policy-rc.d 禁止启动服务。
仅挂载临时 proc/dev，不把 VM 磁盘设备映射给安装脚本。安装完成后恢复解析器
链接并移除临时策略与安装包。原厂 APT 源保留，构建快照不强制冻结运行时更新。

新内核成为 Default，原厂 5.15.137 保留为 Stock；新 DTB 复制原厂 overlay 配置，
并生成对应 initramfs。启用 HDMI、gadget、PD、CPU 调频和 NanoKVM 服务，禁用
冲突的原厂 USB gadget 与 audioserver。通用镜像不自动启用设备专用的 RTP 1400 覆盖。

保留原厂账户与密码，清空 machine-id 并移除镜像内 SSH 主机密钥。
首次启动服务生成主机密钥，ssh.service 对该服务有显式依赖。
首次启动的硬件行为和写入 eMMC 后的扩容仍需实机回归。

## 验证范围

verify 以只读方式挂载镜像，并检查：

- 分区布局、MBR 表以外引导区域逐字节未变、fstab 与 UUID 一致。
- 新内核启动链接、Stock 文件与菜单、initramfs 模块列表。
- vfm_cap 的模块依赖、应用及编码插件动态库解析、sudoers。
- 服务启用关系、无共享 SSH 密钥、machine-id 清空及临时构建策略已移除。
- dpkg 无未配置包。assemble 卸载后还检查两个 ext4 文件系统。
- HDMI 服务在 ALSA 恢复后、NanoKVM 启动前通过 ExecStartPre 选择 HDMI 音频路由，
  并确认镜像内 amixer 可运行；缺少这项修复的旧组件包无法通过新验证。

镜像内 /usr/share/vim4-kvm/build 保存组件提交、内核配置摘要、基础镜像锁、
配方脚本与系统包列表。候选镜像未执行实机启动、HDMI/USB 回归或端到端延迟测试。
刷机仍需单独授权，不能把 assemble/export 当成刷机命令。
