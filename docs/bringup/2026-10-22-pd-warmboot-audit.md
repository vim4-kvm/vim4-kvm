# 2026-10-22：PD 热重启原因与主动查询风险审查

摘要：第三轮确认 Linux 工具主动 Get_Source_Cap，U-Boot 本地复位后只被动等待。
这支持热重启后源不再主动广播能力的解释，但未读取 Mac 的 PD 策略状态，不能确定其
保存的合同。主机复现发现现有固件的接收、恢复和限压缺口；只补主动查询不能满足单线
供电安全边界。按用户「风险不可接受就不要实现，改为只在记录里解释」的条件停止，
不增加主动协商、不刷写、不部署管理器、不重启。本轮没有申请新的刷写授权。

## 版本与代码对照

U-Boot 工作树 `/home/deepdream/src/u-boot-pd-handoff`，分支
`vim4-kvm-2019.01-edge-pd-handoff`，提交 `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`，
与[第二轮已刷版本](2026-10-22-pd-firmware-deploy.md)一致且干净。本轮未创建固件提交。
原 `u-boot-edge` 工作树未修改。管理器仍是独立工作树 `build/pd-handoff/manager`、分支
`pd-firmware-handoff`、提交 `6c3220c69fefbec91d39f1c1186ad5faa8ef24d7`，本轮未修改。
没有推送，主仓库仅更新本文、索引和供电文档，不提交。

| 路径 | 能力获取与恢复 |
|---|---|
| `tools/usb-pd-init.c:main()` | 沿用固件 sink/UFP/PD2 PHY，先有限排空 RX；主动 Get_Source_Cap，ID 0–7 有界尝试并等待能力，未得到就退出；初始化不发 Soft_Reset 或 Hard_Reset |
| `usb-pd-init.c:serve()` | 合同后继续 20 秒；回复 Get_Sink_Cap、接收 Soft_Reset 后 TX ID 置 0 并回复 Accept、重新请求固定 5V、处理已知 VDM；收到硬复位报错退出 |
| U-Boot `tcpm_init()` | 写 SW_RESET 恢复 FUSB302 本地寄存器默认值，再写 PD_RESET 复位本地 PD 收发逻辑；启用有限包重试，未启用 AUTO_SOFTRESET/AUTO_HARDRESET |
| U-Boot `snk_startup()` / `snk_wait_caps()` | 本地 TX ID 清零；使能 RX 后只在 EVENT_RX 的 Source_Capabilities 到来时进入评估，没有 Get_Source_Cap 发送 |
| U-Boot `fusb302_init()` | 循环从 100 递减、每轮约 2ms 加控制器开销；不是完整 PD 定时器。看到 ready 立即返回，没有合同后 20 秒服务或 Linux 7.x 协议接管 |

器件行为以厂商代码与[onsemi FUSB302B 数据手册](https://www.onsemi.com/pdf/datasheet/fusb302b-d.pdf)
表 25、28 核对：SW_RESET/PD_RESET 是本地复位，不是向对端发送 USB PD Soft_Reset/
Hard_Reset。不能从这两次寄存器写推断对端也丢失合同，或保证 Mac 重新广播能力。
Linux 工具 `request_5v()` 则明确校验首个 PDO 为 Fixed/5000mV/非零电流并限在 3A，
其成功不能倒推出旧 U-Boot 被动等待或完整状态机也正确。

## 串口与 Linux 证据

第二轮三次重启均执行 `systemctl reboot`，没有拔 USB-C 或现场断电操作。
`logs/pd-handoff/round2-mainline-uart.log`、`round2-stock-uart.log`、
`round2-final-uart.log` 都是：

```text
fusb302_init: Device ID: 0x91
CC connected in 0 as UFP
PD boot: flags=d0 source=0000 request=0000 rdo=00000000 rp=3 policy=0mV/0mA
```

`d0` 是附着、超时、无确认合同；Source header/PDO count/RDO 为零，没有评估打印或
PS_RDY 完成记录。它只证明固件没有观察并完成合同，不能证明 VBUS 已物理降回默认档，
也不能证明 Mac 一定保留某份旧合同；Rp 是 CC 档位。

历史 `logs/kernel-edge/firmware-5.15-uart.log`、`edge-firstboot-uart.log`、
`return-5.15-uart.log` 都有识别与 UFP 附着，没有 `chip->pos_power` 或 sink ready。
进一步搜索该目录 `*uart*.log` 的固件标记，加第二轮三份日志，得到 78 份含初始化的日志、
80 次初始化、0 次能力评估、0 次 ready 打印。清单是 `logs/pd-handoff/round3-history-audit.json`。
旧固件没有新快照，不能把没有打印扩大为“总线上绝对没有任何 caps”，但也没有历史
证据证明固件曾评估并请求过 PDO。

第二轮 Stock Linux 真实输出（`round2-stock-journal.log`）：

```text
rx type 1 n 0 id 0
rx type 1 n 1 id 4
Request rdo 1304b12c: tx 0
6 rx hdr 0b63 ctrl 3 n 0
42 rx hdr 0d66 ctrl 6 n 0
PD bootstrap complete; USB-capable 5V contract established
PD contract at bootstrap: 5000mV 3000mA
PDO1 2e01912c type 0 5000mV 3000mA usbcomm drswap
```

`main()` 先发 Get_Source_Cap，才进入产生上述打印的接收循环；该次成功属于主动路径。
没有协议分析仪或 Mac 端状态记录。“持续供电、旧源状态与新接收端不同步”与证据一致，
但不写作已经测到 Mac 合同缓存；冷启动也未验证。

## 供电风险与停止决定

Get_Source_Cap 是正常能力查询，本身不请求改变电压，也不要求复位 VBUS。但查询会
引出后续协议响应，本地有界重试/返回失败，不能使对端也承诺保持供电。
[USB PD 3.0 v1.1 原规范（TI 托管副本）](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/138/USB_5F00_PD_5F00_R3_5F00_0-V1.1-20170112.pdf)
§6.4.1.1、§8.3.3.2.3、§8.3.3.4.1.1 说明能力响应、收到 GoodCRC 后等待 Request、
源发起 Soft_Reset 后等待 Accept 的流程；相应超时可进入源硬复位，电源恢复经过
vSafe0V。对仅靠 VBUS 供电的板子，这可能就是断电。没有证据说当前 Mac 已走过该失败
路径，下面是协议允许且现有软件不能处理的风险，不是断电实测。

实际 U-Boot 函数存在以下缺口：

1. **旧限压不是 5V。** `CHARGE_INPUT_DEFAULT_VOL=12000`，`evaluate_caps()` 初步选 5V
   后又调用 `fusb302_set_pos_power_by_charge_ic()` 覆盖结果。5V+9V/3A 的能力会选
   PDO2、9000mV 并生成请求；这是既有行为，本轮未用于实板。
2. **能力报文可能被吞。** `tcpc_alert()` 在 TXSENT 时无条件读掉一个 FIFO 帧，主循环
   再按 EVENT_RX 读一个。若先报 GCRCSENT、后报 TXSENT，先将 GoodCRC 当普通控制
   消息读掉，后将 caps 当待清的 GoodCRC 读掉，最终不发 Request。
   VM 厂商 5.15 `drivers/usb/typec/tcpm/fusb302.c:fusb302_pd_read_message()` 已明确注释
   两类事件可能乱序，并按实际报文类型区分完成/接收，并非假设中断永远同批。
3. **Soft_Reset 没有恢复。** 主循环收到消息后进入 `policy_snk_send_softrst`，switch
   只打印，不发 Accept 或返回能力获取。禁用本端自动硬复位不会阻止源的恢复超时。
4. **合同后无人服务。** ready 分支只打印，Get_Sink_Cap 无回复，init 随即返回。
   即使补了查询/Request，加载内核期间与 Linux 7.x 下仍有协议无人接管的空窗。

这不是“必须完整 TCPM 才能查询”的断言。有限引导协商也可以设计，但需要先修复按
报文类型分派的接收、严格固定 5V/电流边界、对端控制消息恢复与有界失败，并明确引导后
的协议责任，不能将“失败就返回”当作维持旧 VBUS 的保证。在当前单线供电、不能远程
验证冷启动的条件下，我判断只补 Get_Source_Cap 风险不可接受，采用用户明确允许的
“记录解释，不实现”分支。串口/OOWOW 回退授权不等于供电风险已消除。

## 离线复现

本机 `build/pd-handoff/round3/audit.py` 从未修改的驱动文本提取实际选择器、Request、
接收、IRQ 和主状态机函数，头文件来自同一提交。I²C/FIFO/IRQ 是受控 mock，未经过的
CC/附着函数设为断言失败，避免替身悄悄改变状态。运行：

```sh
python3 build/pd-handoff/round3/audit.py
```

真实输出节选，完整日志 `logs/pd-handoff/round3-risk-audit.log`：

```text
chip->pos_power = 2, chip->pd_output_vol=9000  chip->pd_output_cur=3000
AUDIT: existing selector requests PDO2 at 9000mV when 5V+9V are offered
AUDIT: received Soft_Reset stays in print-only state; no Accept transmitted
AUDIT: received Get_Sink_Cap in ready has no Sink_Capabilities response
CONTROL: simultaneous TXSENT/GCRCSENT processes caps and sends Request
AUDIT: GCRCSENT before TXSENT consumes both frames but sends no Request
PASS: actual unmodified driver functions reproduced four safety gaps; I/O and peer frames are mocked
```

乱序用例注入完整 GoodCRC/caps 两帧，分两轮先报 GCRCSENT、再报 TXSENT；帧被耗尽、
boot PDO count 仍为 0、发送次数为 0。控制用例保持相同 FIFO 顺序，同轮报两个事件，
实际评估并 Request 成功。没有把错误测试桩或恒定失败当证据。它只证明驱动对这些输入
的行为，不证明当前 Mac 真出现过中断乱序、硬复位或断电。源码副本及脚本保留在忽略的
build 目录；没有修改产品代码，也不将这次审查测试当作主动查询实现已通过。

## 板上状态与边界

本轮只有只读 SSH 查询，没有 FUSB302 寄存器访问、发包、模块/服务变更、写盘或重启，
按共同约束不需锁。HDMI 会话持 board/heavy 双锁使用候选；本轮没有申请写板窗口、
打开其串口或抢锁。后续若实施仍须阻塞取得双锁，获锁后先核对指定基线；下列读数
不能代替该前置检查。

2026-10-22 09:07:40 UTC 实际输出（`logs/pd-handoff/round3-board-readonly.json`）：

```text
kernel: 7.3.0-rc7-vim4kvm-uhd1+
buildID: 4086bbfe5035e5c3f318fb26107e4ad668fc70fe
managerVersion: 2.5.1+vim4.20261018.44.dev.2.gb1e49a8
manager / one-kvm / vim4-kvm-hdmi / vim4-kvm-gadget / vim4-kvm-pd: active
deviceFIPSHA256: 751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0
pdCells: [1,208,0,0,0,0,3,0,0,0,0,0,0,0,0,0]
```

当前 ID 是 HDMI 候选，不是指定 `52d5e46fb006230785110a1fa5ba0dd1383b732f`，不能擅自
恢复或宣称本轮最终回到基线。未执行本轮“恢复后重启”，内核恢复由持锁 HDMI 会话负责。
manager/hash `4494f89ce85ef8da13c6dd07b7aca0e9d397aba054b594357b920ab1107ffea7`、
helper/hash `f64159d4b7a7a7e0627b8119cea32ac9ddd6b518144ea6a1dedee1117bcdb917`，
与第二轮恢复后的 b1e49a8 完全一致，无本轮管理器候选需要恢复。

固件仍是第二轮镜像 SHA256 `3ddfc405d283e5cc645382c5c00b4e8ddc261361825e721f5e7e87492dd30bab`
对应的 FIP。原备份和回退命令见第二轮记录，本轮无新镜像/备份/回退操作。
成功固件合同、真实固件 PDO 列表、主动查询下的 7.x/5.15、冷启动均未验证。
主仓库 `python3 -m unittest discover -s tests -p 'test_*.py'`：147 项、5 skipped、OK；
完整日志为 `logs/pd-handoff/round3-repo-tests.log`。本轮没有固件构建或新的上板验收通过项。
