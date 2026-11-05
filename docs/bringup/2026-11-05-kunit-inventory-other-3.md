# 2026-11-05：内核测试清单 other（3）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/tty/vt/gen_ucs_width_table.py`

类型：源码生成工具（上游，保留，不属于项目测试迁移）。

## `drivers/usb/gadget/function/test_hid_request_lifecycle.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise actual HID unbind across retained configfs function instances.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 39 | `C main` | V/B：保留 configfs function 的多次 bind/unbind 中 GET_REPORT request 和 worker 引用必须只回收一次；标准 USB 枚举/HID 与 KASAN/lockdep |

## `drivers/usb/gadget/function/test_uac2_controls.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Compile actual UAC2 GET_CUR handling; reject access to disabled runtimes.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 62 | `C main` | V/B：禁用 PCM runtime 不得读取其参数、GET_CUR 长度/方向和 buffer 尾边界；标准 USB Audio 描述符/控制请求与 ALSA，不能伪造 u_audio runtime |

## `drivers/usb/gadget/udc/crg/test_bus_suspend.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise actual CRG bus notifications without hardware or DMA emulation.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 35 | `C main` | V/B：configured bus suspend/resume 成对通知且保留配置/排队请求、VBUS 引用与重置/未配置不误通知；真实 USB 主机挂起和 gadget 回调 |

## `drivers/usb/gadget/udc/crg/test_probe_failures.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Compile actual CRG allocation/IRQ code with deterministic failure injection.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 97 | `C main` | B/V：EP0/status/ring 分配逐次失败、IRQ 错误及 gadget.irq 注册、pullup 断开先 halt/drain 再归还队列、timeout 保留 DMA；标准注入/USB 与 DMA 调试 |

## `drivers/usb/gadget/udc/crg/test_setup_events.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Compile the actual event dispatcher against a small EP0 lifecycle harness.  Run with an optional crg_udc.c path to check an older revision as a negative control. No hardware is accessed; MMIO and completion handlers are stubbed.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 60 | `C main` | V/B：SET_ADDRESS/status completion 与 setup 顺序、重连 port event、不活跃/解绑时不转交 setup但消费完成事件；标准 USB enumeration/control 与实际 IRQ |
