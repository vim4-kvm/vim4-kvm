# 2026-11-04：运行时省电与 USB 总线挂起审查

最终状态：USB修复已随完整 `7.3.1-vim4-20261104.2` 部署并保留为默认 Mainline，
五分钟4K H.265冒烟通过。用户取消节能方向，两簇保持performance，不启用深idle、
不改电源域或PD策略。真实主机睡眠/唤醒仍未测试，不能据正常启动宣称该场景通过。
下文保留初始审查、短时调频观察和部署工具中止经过。

## 源码与候选

基于 fetch 后正式 `37483692243f9aff9a9e7737f3fde74e97a14908`，独立 VM 工作树
`/home/deepdream/src/linux-7.3-pm-typec-parity`、分支 `pm-typec-parity`。
候选提交 `ac47cb60d4848`，没有更改正式来源锁。

`drivers/usb/gadget/udc/crg/crg_udc.c:crg_handle_port_status` 原先在 PLC 的
PLS=3 分支调用 gadget disconnect；Resume/U0 没有相应 resume 通知。
厂商 common_drivers 同一函数也保留该行为，不能照搬作正确性基准。
正常总线挂起应保留配置和排队请求；候选通知 suspend/resume，抑制重复事件，
解绑禁回调和总线 reset 后清理挂起标记，保留已有 resume 链路寄存器处理。
参考同树 `drivers/usb/dwc3/gadget.c` 的标准 gadget 回调使用方式。

这不是设备端 remote wake 实现；现有 `crg_gadget_wakeup` 仍为空成功返回。
也不解除 CRG 的系统睡眠拒绝，不改 PD 报文、供电角色或 U-Boot。

## 离线验证

- 新增实际 C 函数夹具 `test_bus_suspend.py`：Mac Clang、VM GCC 通过，覆盖
  通知配对/重复、配置和请求保留、解绑禁回调、未枚举及可选回调缺失。
- 既有 `test_setup_events.py`、`test_probe_failures.py` 通过。
- 驱动差异 strict checkpatch 无 error/warning/check；git diff --check 通过。
- 使用已保留 `kernel-release-20261104/kernel` 构建接口，私有工作树 M= 目录
  编译 CRG 模块、modpost、链接及 BTF 通过。W=1 有五处未改代码的 unused 警告。
  这不是完整新内核构建，也不授权混装模块。

## 板端与后续

只读查询时运行 `7.3.1-vim4-20261104`；两簇 governor 为 performance，
当前频率分别为 2208000/2016000 kHz，UDC configured。
短时 governor 观察脚本与原始输出保存在忽略目录 `build/pm-typec-parity/`；
该观察不替代实际视频负载配对、功率测量或十分钟稳定性验收。
独占窗口每组30秒、每秒读一次，performance → schedutil → performance 的
两簇平均频率依次为 2208000/2016000、1605733/720933、2208000/2016000 kHz。
未控制观看者或视频负载，因此只证明调频可工作，不作节电幅度或性能结论；
脚本 finally 已恢复两簇原 performance，未持久化任何配置。

真实主机睡眠验收须确认板子供电条件，再准备同次完整候选及独占窗口，检查
挂起/恢复回调、HID/介质重用和主机主动复位路径；当前没有硬件通过结论。
原计划的默认调频与深idle候选已按用户后续决定取消。

## 部署准备与串口阻断

用户随后取消节能方向，要求保持 KVM 延迟优先，并授权部署 USB 修复。
没有调整正式 governor、深 idle 或电源域配置。候选以同一配置完整重建为
`7.3.1-vim4-20261104.2`，Image、DT、2338基础模块及3外部模块通过构建和
封包身份检查；配置与两份DT哈希保持不变。
整包SHA256为 `f40370e057e40376f2687dceb7875568b34e85615fecef1459eddd301e6c73ba`，
manifest SHA256为 `d58f889feb160b46142224dbc8415c55cb76ff51d2b061bae744b92cb754a361`。
VM产物在 `~/build/pm-typec-parity/`，主机日志及窗口脚本在 `build/pm-typec-parity/`。

两个短窗口都在安装前停止：第一次旧接收脚本经管理入口收到405，串口初始化也失败；
第二次增加串口启动检查后，在同一串口错误处退出。视频入口改为SSH转发真实8081后端。
修正入口后的独占5秒基线为3840×2160 H.264、60.58fps、丢帧增量0；未改变编码偏好。
macOS `/dev/cu.usbserial-1100` 的 tcsetattr 返回 EINVAL，系统Python与stty设置标准
波特率也失败，lsof未发现占用。尝试标准速率预置未解决，相关实验代码已撤回。
已请求重新插拔调试串口适配器；不能拔唯一供电USB-C。

整包已上传 `/var/tmp/usb-suspend-deploy/kernel.tar.gz` 并核对哈希，但未调用安装器、
未改启动指针、未重启。最后查询仍运行 build 1，四服务active、UDC configured。
旧内核完整模块和加载身份已核对；正式来源锁不提前更新。离线主仓519项通过、10项跳过。

## 串口恢复后的安装与最终验收

用户重新插拔调试串口后，同一工具能够设置921600并记录启动。首次安装完整包并重启后，
新内核身份、完整模块、四服务及UDC均通过，但视频脚本仍使用重启前的SSH转发，
连接失效导致验收中止；脚本恢复旧Mainline并正常重启，核对旧身份和服务恢复。
这次失败没有证明内核回归。

随后修正为每次重启后重建转发，重新逐文件核对已安装候选的启动文件和完整模块，
登记Mainline并正常重启，没有覆盖已封存包或重新安装同release。

| 项目 | 最终结果 |
|---|---|
| release / 默认 | `7.3.1-vim4-20261104.2` / Mainline |
| GNU build ID | `7a12c5177a686e955d352d65d9dd90fd17a05bd5` |
| 已加载CRG build ID | `c2eb5073ffb38e0fb4d7346cb5e8b63791476d47`，与本次完整模块一致 |
| 模块 | 2341个，完整目录逐文件哈希及已加载notes/BTF通过 |
| 服务 / USB | 四服务active、UDC configured、三个hidg字符设备存在 |
| CPU | 两簇均performance，配置和两份DT哈希与build 1一致 |
| 视频 | 3840×2160 H.265，300秒平均59.989fps，丢帧/冻结增量0 |
| 日志 | 无BUG/Oops/WARNING/Call trace，taint与原基线相同 |

保持原应用和编码偏好，没有发送HID、挂载虚拟介质、测音频或让被控主机睡眠。
正常枚举和节点存在不等同于实际键鼠或睡眠恢复验收，也未测端到端延迟。
旧build 1的启动文件、模块、固件保留，未删除；Vendor不变。
板端runtime-build记录与主仓来源锁、[收据](../../packaging/kernel/releases/7.3.1-vim4-20261104.2)
更新为实际保留状态。源码仍在本地 `pm-typec-parity` 分支，未推送、未发布Release。
`deploy-r3.log`、`attempt3/`保留失败恢复，`deploy-r4.log`和`final-proof.json`保留最终结果。
收据及来源锁更新后主仓519项检查通过、10项跳过，git diff --check通过；本地已建对应release tag，未推送。
