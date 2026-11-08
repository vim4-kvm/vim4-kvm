# 正式部署夹具

[formal-deploy.py](../formal-deploy.py) 的 plan 默认离线；先准备不同 release 的
tested_build 与 retained_runtime 来源锁、候选整包和匹配 retained_runtime 的回退整包。
参数及门禁名见两个入口的 --help。plan 输出目录必须不存在，产物在 build/。
execute 用 --plan 指定封存计划，并由 tools/board-queue run 提供有效板票；
publish 读取同一计划指定的日志，在验收成功后离线写收据和 retained_runtime。

单门禁可运行 formal-gates.py GATE --logs DIR；默认读 DIR/plan.json，也可显式
--plan 指向 plan 产物。它校验封存输入并建立 SSH 转发，仍要求有效板票。
fan-persistence 要求部署入场留下 fan-before.json。M6 门禁要求运行本目录
m6-bridge.py，环境 VIM4_FORMAL_ASSETS 指向计划的 assets，VIM4_FINAL_LOGS
指向窗口日志；VIM4_RECEIVER_IP 默认沿用既有接收机地址。部署入口自动管理这些进程。

M6 bootstrap 复用既有截图审阅和有界回复，不自动批准未知桌面，也不向开发机注入 HID。
会保存输入法和显示模式、启动原生接收窗口，并在 cleanup 恢复。
四个 Mac 原生程序在 plan 用 swiftc 编译；input-source 源码在 m6/，其余在 tools/。
gpu-probe 源码在 packaging/gpu/，选择 gpu 门禁时通过 --gpu-cc 指定本机可用的
ARM64 编译器和 EGL/GLES/GBM sysroot 参数。编译失败会阻止生成计划，不沿用历史二进制。

1080p60 EDID 由 hdmi-mode-fixture.py 从仓库 EDID 生成并核对跟踪的哈希。
USB 镜像为固定 FAT16 布局、卷标与 marker 的专用测试盘，不读取用户介质。
decode-smoke 必须显式提供码流/插件工具归档及其来源 SHA256；decode-smoke.json
记录已验证归档和逐文件期望，hevc-refs.json 记录逐帧参考。归档和二进制不入库，
本目录脚本与期望值覆盖归档中的历史副本。

HDMI 只验 1080p60/4K60/无信号往返；编码只验当前模式，4k60 为既有十分钟接收；
音频只验服务及设备状态。19 档 HDMI、9/11 档编码矩阵尚未恢复。
PD 按当前 pd-b-state.json 的固件 B 状态检查，不沿用旧 TCPM 已加载的合同。
离线测试和编译不证明板端安装、恢复或门禁已经实测通过。
