# 2026-11-02：uhd7 正式构建与 BCM43752 SDIO 部署

FullKvm 已正常重启到 `7.3.0-vim4kvm-uhd7+`，默认 kbase。无线独立中断、eMMC 读回、
HID/UDC 通过。HDMI 无输入，用户同意将画面和编码登记为未验证后安装。
[D2 对照](2026-11-02-wifi-sdio-host-path.md) 与本次正式安装分别测量。

## 来源与构建

fetch 后正式分支仍为 `923aa01fdd7d454076ea41b560afe267291b5618`，直接快进到
`52b95c8493264b195fe5fa10ccf07ad28670f16f`。顺序为 `246a89ec0c878`、`fb4583023d59a`、
`20c6098d25fea`、`3f3a03f9c00ef`、`52b95c8493264`。未重写提交，严格 checkpatch 沿用 D2 记录。

VM `vim4-build`，GCC 13.3.0，独立 `~/build/sdio-formal-52b95c849326/{out,stage,external}`。
`olddefconfig` 后与 uhd6 唯一配置差别为 LOCALVERSION。重建 Image、DT 和 2338 个树内模块，
运行 `packaging/kbase/build.py` 构建 mali_kbase、vim4_kbase_heaps、governor_vim4 并生成 FullKvm DT。
逐个解压核对完整 vermagic、GNU ID、BTF 节和文件 SHA，随后封存两种 GPU DT、Symvers、vmlinux BTF。
逐节点解析 DT、还原 phandle 引用，预约表和启动 CPU 相同；仅 wifi@1 新增
`interrupt-names = "host-wake"`、指向 GPIO 中断控制器 27 / level-high 的 `interrupts-extended`。

| 产物 | GNU ID 或 SHA256 |
|---|---|
| vmlinux GNU ID | `d6f9c685802759c85cba6bd92bce90396d1cf6ec` |
| Image | `10e3451d13bca87006bd93faa991c0290d0109df8a21f5bf0b4725f700f52354` |
| FullKvm DTB | `89c4bcf6b5523cee60a6f222f28675c99b5137767ec484d78d53b14899702071` |
| vmlinux BTF | `99f681a065c24ce09478be6ad52e728e77e44db32014d5776cec5e79bc2dcddc` |
| uhd7.tar.gz | `de593126c39108d3ed94a3e6ea54adca1173818d7d6615f431343e2603d67851` |
| uhd7-ram.tar | `b2a820e9c9f59f93de7e69833c28eac8b4541747676f3d32afb89ce39aea9e5e` |

[完整构建清单](../../packaging/kernel-edge/uhd7-manifest.json)、
[外部模块来源](../../packaging/kernel-edge/uhd7-external-manifest.json)、
[2341 个模块身份](../../packaging/kernel-edge/uhd7-module-inventory.json)。

## RAM 门禁与 HDMI 边界

一次 RAM 启动实际 GNU ID 匹配。40 秒单 TCP 反向流量中，10.002 秒计数窗
`brcmf_oob_intr` 增加 6762；同步实验的 250 ms 工作队列跟踪保留全部 7221 项，
`sdio_irq_work` 为零。固件为 .217 / `01-e47f9a86`。
对 eMMC 根分区 `/dev/mmcblk0p2` 的 `libLLVM.so.20.1`（138943216 字节）
分别在 uhd6/uhd7 逐出该文件缓存并读取两遍，四次 SHA 均为
`c716c4db8c44ec43b3c87d2a6245ae79b0cd65dff8895622ddc547576c18841c`。
四服务 active，UDC configured，键盘端点写入全释放报告。taint 4096（外部模块），
该次内核日志未见 Oops、panic、MMC I/O 错误。

H.264 WebRTC peer 已连接，但 60 秒内没有解码首帧。自动回到 uhd6 后核对原启动文件与身份。
uhd6 上 QUERY_DV_TIMINGS 返回 ENOLINK、0 Hz，一次 Ctrl 唤醒尝试也未恢复。
随后按用户新指示先请求 MCP 截图，返回 No video signal；服务只公布绝对坐标 mouse_move，
未发相对移动或再次按键。未取得 HDMI 锁定，按用户许可跳过画面/编码项，未再次 RAM 启动。
无源状态在两内核均可观察，尚无在有效信源上验证新内核采集/编码的证据。

## 持久安装与身份

由已安装的 uhd6 FullKvm 执行 `tools/kernel-install.sh --edge uhd7.tar.gz --keep-directory-symlink`。
该版本升级路径沿用已安装 r14e 插件与 One-KVM USB overlay，并复制已核对的 release 专用 .217 固件。
安装后没有创建回退副本，保留 /lib 符号链接。extlinux 字节不变，默认 FullKvm；
正常重启的 cmdline 无候选 init。两项内核登记的产物均逐文件校验。

七个 /boot/edge 文件、2354 个模块目录文件、11 个已加载模块身份和 One-KVM 进程 SHA 均匹配。
one-kvm、vim4-manager、vim4-kvm-hdmi、vim4-kvm-gadget active，UDC configured。
第一次安装核验扫描 /proc 时遇到没有 exe 的内核线程，改从服务 cgroup 核验，未重装或再次重启。
[安装收据](../../packaging/kernel-edge/uhd7-installed-proof.json) 保存逐项 boot 哈希与运行身份。

## 安装后无线测量

Mac 192.168.50.239:5217，板端使用已保存的 5 GHz 配置，从 wlan0 发起单 TCP 反向 iperf3，
间隔 1 秒；采样期间无跟踪。原始记录目录为 `build/sdio-formal/`。
首次频段预检测到 5200.0 MHz，整数解析失败，尚未启动 iperf；修正后重新采样。

接收端实际 600.001 秒、600 个一秒区间。总接收均值 **369.55 Mbit/s**；
p10 **337.64**、p50 **372.24**、p90 **398.46 Mbit/s**。分位口径沿用 D2 工具，
排序后 p10/p90 取下标 60/540，p50 取中位数。
[门禁收据和逐秒速率](../../packaging/kernel-edge/uhd7-validation.json) 固定此次结果与原始 JSON 摘要。
结束时 Wi-Fi disabled，默认路由经 eth0。board-queue 实际持板共 879.49 秒（14 分 39.49 秒），
含只读预检、唤醒、安装、重启和测量；构建和封包仅持 heavy 票。

驱动审查遗留仍见 [vim4-kvm issue #1](https://github.com/vim4-kvm/vim4-kvm/issues/1)。
