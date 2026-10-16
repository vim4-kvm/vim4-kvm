# 2026-10-15：管理器 EDID 预设接口验证

vim4-manager 新增清单驱动的 EDID 选择，初始包含 RTK UHD HDR、原 VIM4 4K60、
VIM4 1080p60。应用时同步板级持久配置和 JetKVM 的独立配置；运行中的 JetKVM
先停止再保存，失败尝试恢复原保存配置。默认安装不改变现有 EDID。

候选助手在板上临时目录运行：三个预设均通过校验，当前 selected/active 均为
RTK-CONTROL，jetkvmSynced=true。重复选择 RTK 无服务停启、无 HDMI 重载，
加载记录时间戳与 JetKVM 配置字节均不变。保持 One-KVM 运行；未做其他预设的
实机切换或 Screen Sharing 新一轮回归。

Python 助手测试、Go 测试与 vet、前端构建通过，已交叉编译 Linux ARM64 二进制。
组件暂存检查确认 RTK 二进制与 board/edid/rtk-uhd-hdr.bin 一致。尚未部署新版管理器；
本机 Docker daemon 未运行，未执行隔离组件包构建与安装验证。
