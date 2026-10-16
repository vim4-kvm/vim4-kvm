# 2026-10-14：JetKVM 默认 EDID 改为 4K60 并部署

JetKVM `165f0aa` 将 VIM4 首次启动、空配置回退和界面“恢复默认”统一到已有的
VIM4 3840×2160 60 Hz 厂商表。已保存的预设和自定义 EDID 保留，原生 JetKVM
预设仍可手动选择。清单由主仓库 `4b98ca1` 固定该提交。独立源码验证通过
VIM4 全部 Go 测试、两种目标 go vet、前端与 ARM64 构建。

板上已有“重新连接显示器”功能，其对应未提交补丁在独立构建目录中保留，
没有纳入本次 Git 提交；助手与板上版本 SHA256 一致。部署包
`2.5.1+vim4.20261014.2` 的 sources.json 明确记录 kvm dirty=true，补丁归档为
`build/jetkvm-edid-deploy/preserved-kvm.patch`。完整组件构建及隔离包校验通过，
实际仅安装 vim4-jetkvm，短暂停止并重启该服务，没有重启板子或其他应用。
旧二进制、助手及配置备份在 `/var/lib/vim4-kvm/jetkvm-edid-20261014.2/`。

部署前保存的 EDID 已是 VIM4 4K60，配置文件在安装和服务重启前后哈希一致。
真实 Chrome WebRTC RPC 返回新应用版本，getEDIDPresets 第一项与 getEDID
均逐字节匹配该 4K60 厂商表。4K H.265 在 10 秒内解码 600 帧，dropped=0、
packetsLost=0；G.722 收到 500 包，但音频能量接近零，不能据此确认可听声音。
board.py check 通过，dpkg audit 无输出，无 failed units；NanoKVM、管理器和
HDR 曲线工具哈希未变。未另测恢复出厂设置、冷启动及运动画面质量。
本轮记录在 `logs/jetkvm-edid-deploy/`，构建产物在 `build/jetkvm-edid-deploy/`。
