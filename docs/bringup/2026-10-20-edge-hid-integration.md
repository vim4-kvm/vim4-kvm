# 2026-10-20：7.3 One-KVM HID 接入

摘要：当前固定 UHD60 实验内核无需更换 Image，加载已有 CRG 驱动并创建三种
HID 后，Mac 成功枚举键盘、绝对鼠标、相对鼠标。实验 One-KVM 已启用 OTG，
API 报告 initialized/online；局域网 H.264 4K60 视频同时通过短测。本轮未注入
真实按键或鼠标移动，实际网页输入效果仍需用户或后续独占窗口确认。音频尚未接入。

## 接入方式

- [USB 准备器](../../packaging/kernel-edge/one-kvm-edge-usb-prepare) 仅允许 root
  在匹配的 `7.3.0-rc7-vim4kvm-uhd1+` 运行。加载 CRG/libcomposite，挂载 configfs，
  按顺序创建 hidg0 键盘、hidg1 绝对鼠标、hidg2 相对鼠标。
- [USB 服务](../../packaging/kernel-edge/one-kvm-edge-usb.service) 由
  [实验应用服务](../../packaging/kernel-edge/one-kvm-edge.service) 拉起并先于应用完成。
  应用补充 input 组。服务停止不销毁 gadget，避免影响打开的 HID 文件。
- 已准备的 gadget 只核对状态，不重新绑定；未登记的 gadget、其他应用的 gadget、
  非空 LUN 或不匹配内核均拒绝。创建失败的部分状态不冒充准备成功。
- 创建一个空、只读、**未链接**的 mass-storage 函数，供现有限定助手读取状态；
  不暴露磁盘、不挂载用户镜像。HID 配置复用 `/usr/libexec/vim4-onekvm` 的 configfs
  操作，该助手二进制与源码 SHA 相同且本轮未修改。
- One-KVM Wave5 支持键盘及两种鼠标的配置；消费者键、磁盘、USB 网卡、UAC2 和
  USB 串口仍拒绝。配置 API 在关闭现有 HID 句柄前检查这些限制，返回 400。
  初版在运行时才检查，返回 500 并回滚；最终版本已前移检查。

新实验数据库默认 `otg / full_no_consumer`。已有数据库保留原设置，本轮通过
`PATCH /api/config/hid` 显式切到该配置；未开启音频、虚拟盘或其他扩展。
UDC 为 `fdd00000.usb`，设备序列号 `VIM4-EDGE-HID`。

## 版本、验证与恢复

内核保持 `46f8489461869`，Image/DTB/完整模块集均未更换。
One-KVM 为 `9f457566ad789512d762dc3b68eb056c061cbee3`，ARM64 release SHA-256：
`5e937f5a67b394c0a2ae9987fd53a5eb8e54947dc67e7115b4d4bb97aeb04c03`。
生产 helper SHA-256：
`a4504aacd313ae34ea4ee10428f4de922d23ab26d123989eecf6ce332ccda209`。

- Rust 库测试 719 通过、2 ignored；ARM64 release 构建通过。构建的 19 个警告
  涉及既有代码，未在本轮按无关范围修改。Linux 板级助手 23 项通过。
- 准备器的离线回归检查重复准备不解绑、拒绝陌生 gadget、非空介质及 5.15。
  这些是假文件系统测试，不替代真实 configfs/USB 行为。
- Mac IOUSB/IOHID 树出现三种接口；UDC 达到 configured。以 khadas 连续提交
  10 个全零相对鼠标报告，前序请求均完成，不移动指针或操作键盘。
- 应用 API 为 OTG、initialized=true、online=true，支持绝对鼠标，视频尺寸
  3840×2160。重复运行准备器及重启实验应用后仍 online。
- 请求开启尚未支持的虚拟介质返回 400，既有 HID 保持 online/configured。
  对应旧版 500 负例保留在 `edge-hid-runtime.log`，不能将旧日志统称通过。
- Mac 经 LAN 登录网关观看 H.264，预热 8 秒、采样 20 秒，3840×2160、
  59.970 fps，解码丢帧/网络丢包/freeze 均为 0。未运行运动标记，未验收内容推进。

证据：`logs/kernel-edge/edge-hid-{rust-tests,build,helper-tests,runtime}.log`、
`edge-hid-video.json` / `.stderr`。最终 API 及内核状态另存 `edge-hid-final-status.json`。
原实验二进制、数据库一致性备份、服务文件及受保护生产文件哈希清单位于 root
专用 `/var/backups/vim4-onekvm-edge-20261020/hid-integration/`。
生产 Image、extlinux、One-KVM 程序和 USB 助手哈希不变，默认仍为 5.15。

## 音频缺口

当前 ALSA 没有声卡，原设备树声卡依赖 HDMI TX 的 DAI，在视频实验关闭 DRM 后
停留在 deferred probe；原声卡仅有播放路径，没有 TODDR 输入采集链路。
此外，当前 UHD60 EDID 的 CTA 块没有 Audio Data Block，Basic Audio 位也未置位。
需要同时补齐音频能力声明、RX 音频恢复时钟/FIFO、输入到 DMA 的路由与 ALSA
采集，再接入应用及测试有声波形，不能仅将应用 audio.enabled 改为 true。
