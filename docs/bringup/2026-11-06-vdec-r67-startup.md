# 2026-11-06：r67 UART 启动识别失败与 SSH 身份修复

同一`.31`实际启动一次，旧连续UART路径因版本行残缺，45秒后误报
`No selected Linux boot`。未进入remote.py，compliance、剩余10条H.264、
29次MPEG-2与HEVC全部未运行，不能据此关闭AVC合入门禁。正式默认已恢复，未部署。
候选源码和封包沿[r65](2026-11-06-vdec-r65-joint.md)，计划沿[r66](2026-11-06-vdec-r66-plan.md)。

## 实际窗口与恢复

FIFO1393，连续UART记录191.360秒。一次请求候选启动、一次请求正式恢复，
没有非请求冷复位。候选`Booting Linux`所在接收块monotonic为676326676646708；
其后的版本文本丢失，原始字节直接拼接到编译身份。后续UART含候选init路径、
完整cmdline及USB Manufacturer的`.31`版本。旧代码只认`Linux version`，
因此没有进入SSH就绪检查；本轮没有候选SSH build ID/boot_id实测，不能补称已采到。

入场视频脚本已从run52复制到run67并核对SHA256：
`253d055bcbb6f921c6362e1909eb2ca9ea3b8ed35c254a90baff743254153e10`。
路径门禁与私有Playwright导入冒烟通过，未重现r66的旧运行目录问题。

最终正式7.3.1-vim4-20261105，2372项保护文件一致；视频推进298帧、59.563fps，
丢帧/冻结/丢包无新增。765项任务文件归档Mac逐项核对后删除板端上传目录；
候选及owned固件按归属/哈希清理，正式模块未动。没有追加启动或票。
正式eMMC累计下界从r66的≥24/4变为**≥25次/4冷复位**；正式RAM仍2/1，
`.28`仍9/2；`.31`三次/0非请求复位，不据此宣称稳定。

## 离线修复与验证

只修改显式启用的连续UART启动路径，历史默认boot路径不变。
UART接受`Booting Linux`或`Linux version`，同次启动的两行合并计数；
重复启动标记或Linux之后返回T7 ROM仍触发复位处理，WARN/BUG检测保留。
UART版本只作证据，不再单独裁定候选身份。

连续路径在既有120秒就绪上限内等待SSH身份：release、GNU build ID、完整cmdline，
以及不同于请求重启前的boot_id。cmdline与候选extlinux的APPEND逐项相等，
先核对extlinux文件哈希与封包清单一致。仍要求实际发出候选选择命令。
服务就绪之后再次核身份，boot_id变化则拒绝。身份不符立即失败；SSH未就绪
等到截止时间才恢复。成功事件保存SSH身份及UART缺失标记，不凭SSH伪造UART起点。
正式恢复仍由后续完整baseline proof验收。

回放覆盖r67从请求启动至恢复前的全部1755个rx块，使用原始monotonic时间戳；
SSH响应是受控测试输入，不是本轮板端证据。正确身份通过，错误build ID拒绝。
提交的214字节fixture为原始UART的`[26852:27066]`切片，保留损坏行；
单元测试另覆盖错误release/cmdline/封包配置哈希、旧boot_id、无启动标记且无SSH、
双启动标记去重及重复启动停止。完整UART SHA256：
`5ae8323927179091fc143d9efe9a3fe6af815cd892c8155ef09627d3109830e1`。

原始证据：`logs/hwdecode-parity-r67/`含UART/chunks、execution-error、
returned-baseline-identity、returned-video和complete；`build/hwdecode-parity/run67/`
含上传归档/哈希清单、video-identity、browser-smoke，以及replay-startup.py/log、
uart-tests.log（10项）、window-tests.log（35项）与main-tests-startup.log
（全套595项通过，11项跳过）。
工具修复尚未上板；提交交协调者审核push后，才申请r68，同`.31`与r66计划。
