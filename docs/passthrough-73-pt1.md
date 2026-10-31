# pt1离线候选封存

基于uhd4 `8bca939d6bbd3`，源码分支`passthrough-73@a62fa298a57e8`。
完整Image、DTBs、2338模块构建/安装成功，未部署、未改默认启动。

| 项目 | 固定值 |
|---|---|
| release | `7.3.0-vim4kvm-pt1+` |
| GNU build ID | `fa6b010a9d60c223b25dba6e1f2a03bec2f94c40` |
| 封存包SHA256 | `7820f7bec7c69bd7994c0c5897ccc7493d541232aa451af515b2ff191b6ffcbb` |
| VM包 | `~/build/pt1-stage.tar.gz` |
| VM构建 / 清单 | `~/build/pt1` / `~/build/pt1-stage/manifest.json` |
| DT | `amlogic-t7-a311d2-khadas-vim4-passthrough.dtb` |

[构建器](../packaging/kernel-edge/build-pt1.py)使用相邻uhd4.config，只替换LOCALVERSION。
在Linux ARM64上经主机board-queue heavy调用；输出与stage必须为新目录。
封存包含Image、所选DTB、config、System.map和完整同次模块，逐文件SHA在manifest中。
初次模块统计仅匹配未压缩`.ko`而误报0；现已修正为匹配压缩模块，重封存后为2338。
`pt1-build.log`保留首次计数，最终以`pt1-seal.log`与上表归档SHA为准。

DT重用M3-video的VD1/ENC2、ASoC HDMI-TX/ELD和VDIN split VCBUS；
7个既有fixture在最终DT上通过，确认46个显示bank与15个供电域资源合同。
没有内核C改动。基线到候选的strict源差分检查通过，显式忽略新增文件的通用
FILE_PATH_CHANGES提醒；单提交检查保留旧提交缺正文提醒，不写成全系列零warning。
KUnit未跑：VM没有QEMU；这7个测试是host C fixture，不是KUnit或真硬件证据。

本DT没有GPU覆写。未来uhd5组合应在引入passthrough profile之后，应用其独立GPU选择片段，
关闭Panfrost节点、启用kbase；不能把两个含完整板级base的DTS直接相互包含。
组合后须重跑资源/互斥预检和完整匹配构建；此包仍为uhd4/Panfrost，不冒充uhd5。

VM加载vkms/vivid及查找v4l2loopback均因当前7.2.12 OrbStack内核缺模块失败；
没有虚拟设备可运行端到端测试，也没有替换VM内核或给7.2加载7.3模块。
日志在本worktree `logs/passthrough-73/{pt1-*,virtual-devices-r4,loopback-r4}.log`。
未来上板仍按[离线门禁清单](passthrough-73-offline.md#将来上板门禁当前禁止执行)，当前禁止执行。
