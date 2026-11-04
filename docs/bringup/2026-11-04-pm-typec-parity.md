# 2026-11-04：运行时省电与 USB 总线挂起审查

结论：CRG 将总线 suspend 错报 disconnect，候选改为标准 suspend/resume 通知；
离线回归和模块构建通过，未部署、未验真实主机睡眠。CPU 两簇运行 performance，
schedutil 可用；默认策略尚未改变。不扩展完整 TCPM 或整机睡眠。

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
CPU 默认策略应在真实视频吞吐/延迟门禁通过后再调整，CPU 深 idle 另作单变量候选。
