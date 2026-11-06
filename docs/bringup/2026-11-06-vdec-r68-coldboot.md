# 2026-11-06：r68 候选冷复位与被动恢复

获批的同`.31`、同[r66计划](2026-11-06-vdec-r66-plan.md)窗口已结束。
候选在启动阶段冷复位，尚未进入解码流程；随后正式默认的第一次自然恢复也冷复位，
第二次自然恢复成功。没有重试候选、主动循环重启或部署，队列已释放。
compliance、剩余10条H.264、29次MPEG-2与HEVC全部**未运行**，AVC合入门禁仍未关闭。

## 入场与身份边界

FIFO1396，单张30分钟sampling票。入场uptime1210.47秒，采证结束1219.38秒，
boot_id一致，连续UART无复位；正式baseline核验通过，空间满足计划。
封包SHA与[r65](2026-11-06-vdec-r65-joint.md)相同，protected_files逐项一致，
所有运行路径重定向到r68。video.py真实存在且与run52参考哈希相同。
私有Playwright/Chromium及receiver离线冒烟通过；启动冒烟时必须在Node导入前
设置PLAYWRIGHT_BROWSERS_PATH，脚本内部后设环境变量不影响已导入的Playwright。

使用b8b9524的连续启动路径。UART两种启动banner均完整且正确去重，随后T7 ROM
标记触发停止。未出现`ssh-boot-identity`成功事件，没有保存候选SSH身份通过证据；
本窗不能宣称新SSH成功路径已实板验证。没有execution.log，也未启动remote.py。
UART保留完整`.31`版本与候选init路径，候选Linux启动计数为1，不是零启动。

## 逐启动时间线

间隔使用连续UART的主机monotonic时间，从Booting Linux所在接收块到T7 ROM块。
不是末条内核时间戳，也不是电气RESET边沿。

| 顺序 | 内核/路径 | 结果 | 距Linux起点至ROM | 复位前末条内核日志 |
|---|---|---|---|---|
| 1 | .31 RAM候选，唯一请求启动 | 冷复位 | 8.219290875秒 | `[5.986979] warning: iwconfig uses wireless extensions…` |
| 2 | 正式20261105 eMMC，自然恢复1 | 冷复位 | 7.251297500秒 | `[4.734777] brcmf_c_preinit_dcmds` Wi-Fi固件身份 |
| 3 | 正式20261105 eMMC，自然恢复2 | SSH/proof/视频通过 | 无观察到的复位 | 正式恢复成功，Linux起点677748089217000ns |

前两次未观察到panic，末条日志不构成归因。候选随后正式包在同一窗口连续复位，
仍不能归因于解码系列；验收流程未执行节点加载，未改MMC/PWM/ADLA/PD。
相对[r67统计](2026-11-06-vdec-r67-startup.md)，正式eMMC新增2次启动/1复位，
已覆盖下界**≥27次/5复位**；`.31`累计4次/1复位。正式RAM仍2/1，`.28`仍9/2。
物理区分沿既有RESET/VBUS/PD采样方向。

## r65–r68 全部启动对照

统一用`Booting Linux`首字节所在接收块至下一个T7 ROM首字节所在块计时。
r66旧记录使用Linux version行，r67回放记录使用完整行收齐时间，因串口分块有
不到3毫秒的口径差异；以下从原始UART/chunks重新计算，不改变冷复位分类。
“未观察到”仅覆盖该窗的连续UART时间，不把下一窗入场前的无日志区间算入。

| 窗口/启动序号 | 内核/启动方式 | Linux起点→下个ROM（秒） | 分类 |
|---|---|---:|---|
| r65/1 | .31 RAM候选 | 1169.426725 | 请求的正常reboot恢复，非冷复位 |
| r65/2 | 正式eMMC，请求恢复 | — | 窗口内未观察到复位 |
| r66/1 | .31 RAM候选 | 26.073674 | 请求的正常reboot恢复，非冷复位 |
| r66/2 | 正式eMMC，请求恢复 | 7.239996 | 冷复位 |
| r66/3 | 正式eMMC，自然恢复1 | 7.258330 | 冷复位 |
| r66/4 | 正式eMMC，自然恢复2 | — | 窗口内未观察到复位 |
| r67/1 | .31 RAM候选 | 42.405953 | 请求的正常reboot恢复，非冷复位 |
| r67/2 | 正式eMMC，请求恢复 | — | 窗口内未观察到复位 |
| r68/1 | .31 RAM候选 | 8.219291 | 冷复位 |
| r68/2 | 正式eMMC，自然恢复1 | 7.251298 | 冷复位 |
| r68/3 | 正式eMMC，自然恢复2 | — | 窗口内未观察到复位 |

精确纳秒起点与间隔保存在本轮`r65-r68-boot-timeline.json`，来源为各轮
`logs/hwdecode-parity-r*/uart.raw`与`uart-chunks.jsonl`。此表不计入入场前已经
运行的基线启动，避免重复分母。r69同包同计划的单张30分钟票，须本记录经协调者
审核并push后才生效；当前尚未排票。

## 恢复、清理与证据

第二次自然恢复后正式release/build ID及2372项保护文件一致。清理前重传helper，
按哈希删除本任务创建的固件副本、清理候选及其模块挂载，正式模块目录未动。
4K视频推进305帧、60.969fps，丢帧/冻结/丢包无新增。765项任务文件归档Mac逐项
核对后删除板端`/var/tmp/hwdecode-standard-r68`；complete记录restored=true。

`logs/hwdecode-parity-r68/`保留连续UART和分块时间戳、execution-error、
passive-recovered、returned-baseline-identity、returned-video、complete。
UART SHA256为`8755caabad7f8b2055f938b512f2d17085c7ed8cd4a255412d56ab8247712757`。
`build/hwdecode-parity/run68/`保留封包身份、计划、video-identity、browser-smoke、
window.log、board-upload.tar及文件清单；boot-timeline.json含逐启动原始起点和间隔。
本次只补记录与r67的UART去重盲区说明，没有修改工具或内核。
提交前全套595项检查通过、11项跳过，原始输出为本轮main-tests.log。
