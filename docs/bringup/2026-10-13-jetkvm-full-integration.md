# 2026-10-13：JetKVM 完整功能接入

kvm 仓库去掉 basic_kvm 限制，按能力上报接入 JetKVM 原有功能；特权操作只经
/usr/libexec/vim4-jetkvm（JSON 经 stdin，sudoers 仅此程序），功能与边界见
kvm/VIM4.md。上板为开发构建，随后以网页更新安装 1.0.3+vim4.20261013.33
（--allow-dirty 构建，其余组件仍为 .30）。测试工具 tools/jetkvm-smoke.mjs
通过页面自身的 rpc 数据通道调用接口。证据 logs/jetkvm-full/。

- H.264/H.265 1080p 与 4K 约 60fps、10 秒丢帧 0；画质系数实测重开编码器
  6000/12000kbps、60fps（静态桌面码率远低于上限，不能用码率证明画质）。
- HDMI 音频 G.722 50 包/秒；440Hz 测试音能量 0.079，静音约 1e-7。JetKVM 默认 EDID
  使 Mac 音频设备名变为 “JetKVM v1”，hdmi-audio-tone 改为可传设备名。
- EDID：JetKVM 加载配置时把空值迁移为其默认表（1080p），保留为默认；追加厂商
  4K60/1080P60 预设，4K 预设使 Mac 输出 3840×2160。空闲隐藏显示经 hdmirx debug
  拉低 HPD，无查看端时 Mac 显示器消失，有查看端时恢复 4K。
- ISO 经 HTTP 上传，CD-ROM/Disk 挂载，Mac 读出镜像内文件；弹出恢复 NCM；
  重新枚举后绝对/相对指针正常。USB 模拟关闭使设备消失，打开后恢复输入。
- 网络设置往返（mDNS 改为仅 IPv4 再恢复）、avahi 解析、Wi-Fi 扫描与测试网络
  保存/连接失败/删除；SSH 公钥写入 authorized_keys2；443 自签 HTTPS；终端为 khadas；
  诊断包含 journal；本地密码设置与删除；Tailscale 登录链接与控制服务器。
- 网页更新首次失败两处并已修复：上游 OTA 下载后写 /proc/sys/vm/drop_caches 需 root；
  vim4-jetkvm 依赖同版本平台包，单包更新必然被 APT 拒绝，改为固定下限。修复后下载、
  校验、安装、dpkg --verify、重启全部通过，重启后服务、gadget、4K 视频、音频、指针正常。
- 恢复出厂设置清除 JetKVM 配置、镜像、TLS 后重启，保留 ~/.ssh/authorized_keys。
- Ubuntu 的 tailscale 1.104 没有 `set --login-server`，控制服务器改为登录时指定。

测试结束切回 NanoKVM，并以 `vim4-edid preset VIM4-4K60` 恢复测试前的厂商 4K EDID。
板上 vim4-jetkvm 为 .33 开发包，比最终提交少“安装后删除下载包”一处改动。
未覆盖：经 URL 挂载（内核无 NBD）、真实 Wi-Fi 连接、修改当前以太网地址、真实
tailnet/MQTT、唤醒睡眠主机、长时间与复杂运动画面、HDMI 热插拔、断电冷启动。

本轮另一会话同时打包 NanoKVM。kvm 的 gstcapture 接口修改到一半时，对方
2.5.1+vim4.20261013.2 构建在 JetKVM 测试处失败（logs/nanokvm-migration-package.log）。
