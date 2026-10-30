# ADLA 离线候选

本轮工作在 VM `~/src/linux-7.3-npu`、分支 `vim4-npu-adla`，基于
`213f271505411`。正式部署锁不变。驱动在 `drivers/misc/adla`：其接口是
下游闭源 SDK 字符设备兼容接口，本轮不声明 DRM accel 支持。

## 兼容合同

保持 `/dev/adla0`、magic X 的 ioctl、packed 外层结构、嵌套 task/fixup、
QUERYCAP 的 NULL 查询长度、ioctl 内映射和 UID mmap。
`/sys/class/adla/adla0/device/debug/{hw_info,clk_core,dpm_period}` 的路径及
hw_info 文本标签属于兼容合同，不以 debugfs 取代。
保留 KMD 1.4.0.3 标识不意味着已完成硬件验收。

5.15 本板只读启动日志确认 `nn_adj_vol=0, package=1, efuse=2`，设置
890000 µV；原日志的 `mv` 标签错误，代码单位是 µV。候选不引入多频 OPP。
DT 计算时钟设 800 MHz，实际工作频率需下轮基线记录，不能当作本轮实测。

## 模型和工具

固定 Khadas 提交与六个文件的 SHA256 在 `tools/npu-models.json`。
不提交模型二进制。检测模型选 YOLOv8n，尚未在本板执行，不能称为已验证。

```sh
python3 tools/npu-validate.py prepare build/npu-models
cc -O2 -Wall -Wextra tools/npu-probe.c -lnnsdk -lm -o build/npu-probe-bin
python3 tools/npu-validate.py run --help
python3 tools/npu-validate.py compare baseline/result.json candidate/result.json
```

prepare 在开发机执行，需要 Pillow；生成 BGR HWC 或灰度 float32，记录 Pillow
版本与输入哈希。两内核必须使用同一份输入文件，不能各自重新生成。
run 要求显式模型/输入 SHA，输出目录必须不存在。101轮包含一次预热；逐轮保存
全部张量，比较时每个文件大小和 SHA 必须一致，再检查平均退化不超过5%，
同时报告 P50/P99/最大值。输出差异直接失败；分析差异不自动放宽标准。
本工具不证明采样环境可比，需窗口负责人控制频率、温度、视频负载并重复配对。

超时先 TERM 后 KILL，均有界；D态进程不能靠用户态清理保证消失，必须报告，
不能继续复用硬件。工具不删除旧目录，不发 HID、不测声音、不 ptrace 视频进程。

## 下一轮上板顺序

1. 先在5.15持板锁和媒体锁，记录SDK/模型/输入/内核哈希、实际频率和电压。
   用同一工具采集三模型逐轮完整输出与计时，外部物理地址导入和profiling另测。
2. 离线门禁全部完成后才准备7.3一次性启动；保留5.15默认，不覆盖正式源码锁。
   Image/DTB/modules须来自同次完整构建。
3. 三模型输出字节一致、配对平均退化≤5%；性能不通过就不登记为追平。
4. 计数器证明提交/中断推进、空闲门控及再唤醒；区分温度计持域与计算时钟。
5. 受控超时、取消、进程退出、软复位恢复与失败状态；不盲写寄存器注入。
6. 与HDMI/Wave5固定运动负载并行，检查帧推进、错误、超时和NPU尾延迟。

每项≤10分钟，只用脚本和计数器；不发HID（被控机为Mac mini M6），不测声音。
整机挂起另需平台PM资格，不能用设备clock-gating替代。
