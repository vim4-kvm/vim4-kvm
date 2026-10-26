# 2026-10-26：统一 RTK UHD HDR 入口

## 改动

按用户要求把已验证的高刷和VRR数据合并到既有 `RTK-CONTROL`，菜单显示为
「RTK UHD HDR」。管理面板和One-KVM收掉独立实验菜单项；NanoKVM、JetKVM的
现有RTK项同步同一张表。旧 `RTK-1080P120` 请求保留为兼容别名，保存为规范名称。
厂商默认项和自定义EDID不变。

合并数据SHA256：`45ed44250763f39561961829ff5f9f5f18a8fba6847afd088f8aab2636ceaf45`。
源文件沿用 `board/edid/rtk-uhd-hdr-1080p120.bin`；公共仓库的
`board/edid/rtk-uhd-hdr.bin` 保留原始物理表作离线回退，管理器安装副本使用合并数据。

声明4K60、1080p100/120和HDMI Forum VRR 48–120Hz，不加入4K120时序。
同数据此前已在5.15 One-KVM实测1080p约49–120Hz、4K约49–60Hz SDR8连续画面，见
[范围声明与4K验证](2026-10-26-vrr-range-4k.md)。HDR VRR、其他应用VRR、7.x及
本地HDMI OUT跟随仍未验证；此次整合不扩大这些结论。

## 验证与部署

NanoKVM部署助手42项（跳过8）、管理器部署助手213项（跳过12）、JetKVM部署助手
19项（跳过3）通过；包含旧实验ID映射、RTK预设升级和自定义字节保留的回归。
JetKVM的VIM4 Go全套测试及ARM64构建通过；三个应用网页构建通过，One-KVM网页
9项测试及ARM64发布构建通过。主仓库274项通过（跳过7）。

已更新板上共享助手、管理器助手/清单/RTK数据、One-KVM和JetKVM二进制及NanoKVM网页。
管理器应用 `RTK-CONTROL` 后，保存的 `active.bin` 与安装表均为上述SHA256，
JetKVM同步状态为true。原文件和配置保存在板上私有目录
`/var/backups/vim4-rtk-unified-20261026`；不修改启动包或内核、不重启板子。
启动ID仍为 `85ea2171-5a14-4674-bde4-6876f0211d1e`，内核5.15 hdrdual6。

One-KVM设置页实际检查为4个EDID选项，其中只有一个「RTK UHD HDR」；管理器清单
同样为4项。Mac保留1920×1080逻辑尺寸/3840×2160物理尺寸、固定60Hz，输入SDR8锁定。
IORegistry已识别合并表：1080p120模式VRR 48–120Hz，4K60模式VRR 48–60Hz。
这些是源端能力枚举，不能替代实际VRR画面验证；实际变频证据沿用上文同数据实测。

One-KVM H.264 4K60在预热3秒后测10秒，约59.96fps；测量窗口新增丢包、解码丢帧、
freeze、PLI均为0。此轮是固定刷新桌面视频冒烟，不是运动性能或延迟测试，未切换其他
应用重新资格验证VRR。UU保持启用，当前无客户端连接，不作为UU实测。
安装/网页/视频日志位于忽略目录 `logs/vrr-deploy/rtk-unified-*`，构建与软件检查日志
位于 `build/vrr/rtk-*`。源码版本固定在本次更新的 `workspace.toml`。
