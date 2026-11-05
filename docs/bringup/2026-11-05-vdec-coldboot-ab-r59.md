# 2026-11-05：冷复位 A/B r59 入场失败，零启动

**串口设备路径不存在，工具在打开 UART 时退出；A/B 各 0 次启动，20 项全部未运行。**
没有 SSH、上传、固件操作或 reboot；正式默认未被修改，本次也未实测恢复或视频。
不把这次工具入场失败计入冷复位统计。

## 输入与证据

- 使用已审 `d87c83c` 的编排器与
  `build/hwdecode-parity/coldboot-ab/config.json`，两组封包不变，见
  [离线核验记录](2026-11-05-vdec-coldboot-ab-tools.md)。
- FIFO 票 `d3bf95ed466443fb929a8e4c9436ae7a`，order 1318，上限 50 分钟；
  进入 sampling 后 UART open 失败，finally 取消 sampling，票已释放。
- 原始异常：`build/hwdecode-parity/coldboot-ab/r59-window.log`。
  新目录 `logs/vdec-coldboot-ab-r59/` 在失败时只有复制的 `baseline-proof.json`，
  归档时另保存 `ticket.json` 与 `window.log`；
  UART 尚未打开，无 raw/chunk、entry identity 或 samples 结果。

## 原因与下一步边界

调用遗漏了 `--device`，采用工具默认 `/dev/cu.usbserial-100`，宿主不存在该节点。
现有节点是 `/dev/cu.usbserial-1100` 和 `/dev/cu.usbserial-1101`；
r58 已归档 validation-plan 的 `serial_device` 为前者。
这是宿主枚举号与默认值不一致；board-window/uart-run 的默认值保持不改。
失败位置在 continuous_uart 的 open_port，早于任何板端命令，因此没有必要发起
所谓恢复 reboot；本次不能宣称重新核验过正式基线。

协调者随后批准一张替代票：零启动不占样本额度。保持原配置和二十次固定顺序，
显式传 `--device /dev/cu.usbserial-1100`，先在既有波特率确认 VIM4 控制台，再执行；
使用新输出目录，失败记录先提交。此记录本身不代表替代窗口已经运行。
本次分区 st_dev 门禁尚未执行；后续若失败仍直接停止，不放宽门禁。

## 局限

本次没有任何 A/B 硬件结果，无法推断冷复位概率。后续实验中的 Python 早期采集器
本身占用启动早期 CPU，可能改变调度、probe 时序及复位概率；两组同版同策略只能
控制组间探针差异，不能证明与未插桩生产启动完全等价。
