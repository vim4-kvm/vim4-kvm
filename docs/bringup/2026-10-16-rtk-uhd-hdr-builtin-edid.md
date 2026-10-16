# 2026-10-16：RTK UHD HDR 4K60 成为各应用内置 EDID

按用户要求，板级助手 vim4-edid 内置 `board/edid/rtk-uhd-hdr.bin` 原表，沿用板上已保存的
`RTK-CONTROL` 标识；NanoKVM、One-KVM 与 JetKVM 菜单显示为 RTK UHD HDR 4K60。
vim4-manager 已有该预设，仍以 `apply RTK-CONTROL` 传入安装副本；助手只接受与内置表一致的数据。
PiKVM 沿用板级输入，无独立 EDID 选择。

离线：vim4-edid 11 项、NanoKVM router（ARM64 容器）、JetKVM EDID 测试与 vet、One-KVM
board_changes 测试、两套前端类型检查通过。板上仅用临时副本核对：内置表与当前 active.bin 一致，
错误数据被拒绝且 status 仍为 RTK-CONTROL；未执行 preset 加载，避免 HPD 重新协商。
随后构建、隔离验证并部署单组件包 NanoKVM `2.5.1+vim4.20261016.92`、One-KVM `.93`、
JetKVM `.94`，三次 board check 通过。部署后板上 vim4-edid status 仍为 RTK-CONTROL，
active.bin 哈希与 tvserver 加载记录不变；三套网页或二进制均含 RTK UHD HDR 4K60。
未执行 preset 加载或界面切换，被控机未重新协商；实际切换仍待在各应用界面验证。
日志：`logs/rtk-edid-preset/`。
