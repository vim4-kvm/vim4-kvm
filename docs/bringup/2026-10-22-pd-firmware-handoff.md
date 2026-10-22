# 2026-10-22：U-Boot PD 交接与管理器候选

摘要：完成启动固件 PD 快照与管理器读取候选，独立工作树构建、协议/FDT 主机测试、
管理器单元测试及桌面/390px 浏览器测试通过。没有刷 U-Boot、部署管理器或切换内核。
现有记录没有证明无需 OOWOW 的 U-Boot 失败回退，按本轮限制停止硬件写入。
本记录不能作为 5.15/7.x 实板交接验收。

本页保留第一轮准备与停止原因。第二轮用户已授权刷写并接受现场 OOWOW 恢复风险；
实际刷写、双内核属性/页面验证与最终恢复见 [部署续记](2026-10-22-pd-firmware-deploy.md)。

## 版本与隔离

- 基线 U-Boot：`4317387a6a58f4d42186cbadc24cd3cc52675bc3`。
  从板上只读提取 device FIP，与 VM 历史候选同区间逐哈希吻合。
- U-Boot 分支：`vim4-kvm-2019.01-edge-pd-handoff`，提交
  `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`。
  VM 工作树 `/home/deepdream/src/u-boot-pd-handoff`；独立输出
  `/home/deepdream/build/u-boot-pd-handoff`、`u-boot-pd-handoff-stub`。
- 管理器分支：`pd-firmware-handoff`，提交
  `6c3220c69fefbec91d39f1c1186ad5faa8ef24d7`，基于已部署 `b1e49a8`。
  工作树为主仓库忽略目录 `build/pd-handoff/manager`，没有修改原管理器工作树。
- 两个子仓库提交均未推送；主仓库仅更新本记录、索引与供电文档，不提交。

## 固件交接

没有在 U-Boot 的 board/include/doc 中发现既有 Khadas PD 交接属性。使用私有属性
`/chosen/khadas,usb-pd-boot`，64 字节，16 个大端 u32：

| cell | 值 |
|---|---|
| 0 | 版本 1 |
| 1 | flags：bit0 PS_RDY 完成，1/2 收到/发送硬复位，3 Request 失败/Reject/Wait，4 超时，5 I²C/probe 错误，6 sink 已附着，7 退出时无确认 PD 的 Type-C 回退 |
| 2–4 | 原始 Source_Capabilities header、Request header、RDO |
| 5–6 | PDO 数量、附着时 BC_LVL/Rp：0 未知，1 默认，2 1.5A，3 3A |
| 7–8 | 原驱动策略目标 mV/mA，仅诊断，不当作实际请求 |
| 9–15 | 全部原始 Source PDO，未使用项为 0 |

在原有接收/发送/附着事件旁保存内存快照；没有增加 I²C 事务、轮询、延时或改变
PDO 选择、Request 报文。硬复位清除完成标记；未出现新 Request 时，残留 PS_RDY
不能重新标记完成。失败标志在本次初始化内保留，不用厂商 hardrst_count 冒充历史。
Rp 来自已有 CC 观测，不使用 sink 自身配置的 host Rp，不新增比较器测量。

`ft_board_setup()` 在 `image_setup_libfdt()` 创建 `/chosen` 后、收缩 FDT 前写入。
`bootm` 与 `booti` 都经过 ARM `boot_prep_linux()` / `image_setup_linux()`，
kvim4 配置已启用 `CONFIG_OF_BOARD_SETUP=y`。extlinux 按所选项加载
5.15 的 FDTDIR 或 7.x 的 `/edge/vim4.dtb`，fixup 操作 `images.ft_addr` 的最终 DTB。
并非修改 U-Boot 控制设备树，也不在 FDT fixup 中访问控制器。
写属性失败只打印错误，board fixup 返回成功，避免可选信息阻断启动。
这些是源码路径核对与主机测试，尚不是两种内核的启动实测。

原驱动有需要明确区分的现状：5V/3A PDO 的策略打印为 5000mV/3000mA，
但 Fixed RDO 将 PDO 电压单位放进工作电流位，实际可为 `0x1401912c`，
即工作请求 1A、最大请求 3A。本次按要求保留该行为；同时保存原始 RDO 和策略值，
不能只复制打印数值当作完整合同。完整格式与构建说明在 U-Boot 的
`doc/README.usb-pd-boot`、`VIM4.md`。

## 管理器

限定助手只读设备树属性，校验版本、长度、数量、header、所选位置与 RDO 额度。
仅已完成且可解析、无 I²C 错误/回退的电压与电流组合生成 `firmwarePD.contract`。
额度取 RDO 最大请求，工作请求单独列出，不把 Source PDO 额定值直接当合同。
Battery 按功率解析，Variable 保留电压范围，PPS 从其 RDO 解码；
没有可确认的 V/A 就不构造 V/A 合同，未知 APDO 保留原值。
Source 与 Request 的 revision 分开记录；header 不能区分 PD 3.0/3.1 的细分版本。

API `power.firmwarePD` 独立保留原始 header、RDO、全部 PDO 和失败标志；
原 `bootContract` 仍只表示本次 Linux 初始化日志。5.15 优先显示 Linux，
展开来源能力可并列看固件记录。7.x 显示如「PD 合同 · 5V 3A」及
「启动固件协商」，展开列出 PDO 类型、范围/额定值、原始十六进制与请求位置。
旧 U-Boot 缺属性时保持原文案；默认 Rp 不擅自换算成 500mA 或 3A。
它们都是历史协商，不是实时合同、电流、功耗或 USB-C/VIN 供电分担。

## 验证与命令

U-Boot 构建均在 Mac 以 `/usr/bin/lockf /tmp/vim4-heavy.lock` 包住 OrbStack 命令。
独立构建使用 `make O=/home/deepdream/build/u-boot-pd-handoff kvim4_defconfig`，
随后按 VIM4.md 的 GCC 12 参数构建 BL33；BL33Z 使用独立 `BUILD_BASE`。
保留厂商兼容告警参数；没有为了通过构建修改其他驱动。

BL33 `u-boot.bin` 为 2,550,800 字节，SHA-256
`1e382656e2c00efd862f81dcf4b804dc2cc7f0edd20b655f4e8fbcb86a540cfe`；
独立 BL33Z 的 SHA-256 为
`9e7fa056e558272fa822f946131bdfdbc400e334334f4823ccccbad0070b21b2`。
它们是提交前同内容工作树的构建（版本字符串可能带 dirty），不是可直接刷写镜像。
提交后的版本重建/重打包一直等待 HDMI 会话持有的 heavy 锁，最终取消本任务排队，
没有后台写板操作；最终签名 SD/eMMC 镜像及相对已部署固件的完整差异验证尚未生成。
后续须按 VIM4.md 重建，使用固定 stock 输入与 `--update-bl31` 重打包，并证明
相对现有 edge 固件 BL31 等前级载荷不变，再记录完整镜像哈希。
增量源码备份为 VM `~/build/u-boot-pd-handoff.bundle` 与本机
`build/pd-handoff/manager-pd-handoff.bundle`，均已 `git bundle verify`。

`python3 tools/test-vim4-pd-handoff.py` 编译实际驱动函数与 libfdt，控制器 I/O 为 mock。
实际输出包括：

```text
chip->pos_power = 1, chip->pd_output_vol=5000  chip->pd_output_cur=3000
PD boot: flags=c2 source=2061 request=1042 rdo=1401912c rp=3 policy=5000mV/3000mA
PASS: unchanged Request, PS_RDY gate, raw PDO retention, hard reset, vendor/mainline FDT, no fixup I/O
```

测试覆盖 Request 原字节、PS_RDY 完成门槛、接收缓冲复用后的 PDO 保存、硬复位、
复位后残留 PS_RDY、两种 FDT 外形、FDT 打包后属性保留、无空间与缺节点。
初次 host 测试误用内核头，以及 dtc 目录中未参与固件构建的旧 fdt_ro.c，均失败；
最终使用主机头与固件实际使用的 fdt_ro 实现，仅适配 include 前言，没有改其函数。

管理器：Linux VM 助手完整 148 项通过（无跳过）；Mac 148 项含 12 个环境跳过。
`go test ./...`、`go vet ./...`、Linux ARM64 后端构建与 `pnpm --dir web build` 通过。
初次本机 Go 检查受 GOROOT/工具版本混用影响失败，改用
`env -u GOROOT GOTOOLCHAIN=local` 后完成，没有修改全局配置。
浏览器使用本地前端与 mock API，验证旧固件文案、RDO/PDO 区别、Linux 优先、
硬复位/超时、能力列表及桌面/390px 无溢出、无页面异常；不是板上 API/页面验收。
截图和构建日志在 `logs/pd-handoff/`，浏览器回执在 `build/pd-handoff/browser.log`。
主仓库 `python3 -m unittest discover -s tests -p 'test_*.py'`：147 项通过，5 项环境跳过。

## 板上只读证据与停止原因

只读命令（不改变控制器、服务或启动项）：

```sh
ssh vim4 'sudo dd if=/dev/mmcblk0 bs=512 skip=1313 count=5032 status=none' > build/pd-handoff/board-device-fip.bin
shasum -a 256 build/pd-handoff/board-device-fip.bin
ssh vim4 'sudo cat /boot/extlinux/extlinux.conf; systemctl is-active vim4-manager; uname -r'
```

FIP 区间 `[672256, 3248640)` 的 SHA-256 为
`0bdd6f6925c7def039c7c9fa7abdfbf8a07b17cf7a687d7e4131cfd4b2b3edb5`，
与 VM `~/build/u-boot-edge-candidate/u-boot.bin.sd.bin.signed` 同区间一致。
所对应完整历史镜像 SHA-256 是
`be2a07fd0475deabc950af2e05b843cf8d1373844ed502fbe7af562c888ad0f5`。
板上当前属性不存在，manager 为 `active`；Linux 为 `7.3.0-rc7-vim4kvm-uhd1+`。
解析 `/sys/kernel/notes` 的 GNU Build ID 得到
`52d5e46fb006230785110a1fa5ba0dd1383b732f`。

末次只读核对时，HDMI 会话仍持 board/heavy 锁，运行 build ID 已为
`4086bbfe5035e5c3f318fb26107e4ad668fc70fe`，不是指定基线。
本任务没有恢复别人的候选、改启动项或重启。manager 仍 `active`，版本仍是
`2.5.1+vim4.20261018.44.dev.2.gb1e49a8`；固件交接属性仍不存在。
日志为 `logs/pd-handoff/board-final-readonly.log`。上面的 52d5e46 是较早只读窗口
证据，不能作为末次已恢复基线的证明；内核恢复由持锁的 HDMI 会话负责。

[旧风扇固件记录](2026-10-17-uboot-quiet-fan.md) 与
[edge 首次启动](2026-10-19-edge-firstboot.md) 都要求：布局/哈希核对后恢复 FIP 区间、
fsync、读回再重启；Ubuntu 无法启动时依赖 SPI OOWOW。
历史记录证明正常写入/启动，未记录这条失败回退路径的完整实测。
因此本轮没有执行 dd 写入、U-Boot 刷写、服务变更或重启，也没有动 HDMI 会话候选。
无需恢复本任务候选；没有执行一次本任务的“恢复后重启”，不能宣称该项验收完成。

待满足可验证回退条件后，仍需独占 board/heavy 双锁，核对指定基线，备份原 FIP 并读回
验证，再用串口对照两种内核的属性/日志、真实管理器 API 与页面；最后回到基线内核和管理器。
在完成这一步前，不把固件候选或管理器候选标为可正式部署。
