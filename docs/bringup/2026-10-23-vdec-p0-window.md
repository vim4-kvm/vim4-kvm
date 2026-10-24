# 2026-10-23：T7 VDEC p0 一次性验证窗口

本轮显式 p0 候选通过外部快照、第九步 GCLK 读取、写后回读、MDEC 单读及下电，
无 SError；compliance 45 项中 3 项失败，首错停止，未运行 640×368/1080p 解码。
前轮对照见[寄存器全量差分](2026-10-23-vdec-register-diff.md)。
原始证据在本机 `logs/vdec-p0-window/`。

## 候选与边界

`vim4-vdec`：`9c5687a94c9bc09999535ce15f4caab094976c01`；
kernel build ID `ddaaa01a6d7c0c02e2d8981d59fd612908232648`，
vdec 模块 build ID `a25a2242205f01d56d08adf6ad499e5b967c5b17`。
Image 与上轮快照候选相同，DTB/模块已变化，入口核验 manifest 的 source 与逐文件哈希。
使用 `build/vdec-register-diff/fixed-bundle`；RAM `sysboot mmc 1:2` 一次性启动，
私有完整模块只读 bind，不改五个受保护基线文件及默认启动项。

窗口全程持 heavy→board 双锁；入口核对 PID 1 持有 watchdog、Runtime=30s、Reboot=60s。
入口 baseline 实际 panic=20/on_oops=0，候选 `oops=panic` 后核验 on_oops=1；
回退恢复入口实际值，不将候选设置当基线。失败不卸载不明 DMA 状态模块，不重试；
最多等三分钟回基线。

实际窗口入口（脚本及 `vdec-window.py` 当次副本已归档到证据目录的 `scripts/`）：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/vdec-p0-window/field.py
```

窗口进程因 compliance 退出 1；finally 恢复、冒烟及清理成功，不将进程退出码当恢复失败。
主仓提交前全量测试 234 项、6 项按条件跳过，无失败；文档链接与体积检查通过。

## 各步实际结果

2026-10-24 UTC 00:27:47 取得双锁（Mac 仍为 10 月 23 日）；
00:28:36 开始 probe，00:28:56 compliance 失败后请求正常重启。

| 阶段 | 实际证据与结果 |
|---|---|
| 无上电 probe | `/dev/video1` open：`OPEN_BLOCKED_EPERM`；VDEC off、runtime suspended |
| power | `passed=1 DOS_SW_RESET0=0x0`；结束 VDEC off、runtime suspended |
| 第八步快照 | 2144 字全部读完；p0 enabled=1、p1 enabled=0；最终 VDEC 799,999,987Hz；DOS/两路 APB 166,666,664Hz |
| p0 字段核对 | `fe000140=02000100`、`fe000148=00000000`；低半字分别为厂商 `0100/0000`，高半字 HCODEC 属独立消费者，不照抄 |
| 外部访问前提 | SYS=`07f89ff2`、APB=`ff99ffd0`；DOS RESET0/EN0/MEM_PD=`0/3ff/0`；SMC VDEC[4]/NIC3[39] 均 on |
| 第 9 步 | `read offset=0x260c value=0x0 complete`，即 `0xfe32260c`，无 SError |
| 第 10–11 步 | GCLK 写 `0x3ff`、回读 `0x3ff` |
| 第 12 步 | `MDEC_TEST passed=1 MDEC_PIC_DC_CTRL=0x2a100` |
| 第 13 步 | VDEC[4]=1（off）、runtime suspended；模块正常卸载、编码器恢复 |
| compliance | `/dev/video1`，Detected Stateless Decoder；45 项：42 成功、3 失败、0 warnings，退出 1 |
| 640×368、1080p | 因上一阶段失败，均未执行；没有正确帧或解码性能结论 |

阶段收据为 `passed=[probe,power,snapshot,mdec], failed=compliance`。
证据分别在 `p0-verification.json`、`snapshot.log`、`mdec.log`、`compliance.log`、
`stage-receipts.json` 和 921600 波特率 `stages-uart.log`；候选模块文件哈希与 manifest 相符。

本次在与前轮相同 Image 下，p0 修正后 GCLK/MDEC 访问不再复现异常，
支持将此前访问失败归因到 p0/p1 时钟路径。这个结论限于本次时序及单次窗口，
不等于固件加载、DMA 或解码正确性已通过。

### compliance 失败归类

```text
test second /dev/video1 open: FAIL
test for unlimited opens: FAIL
fail: v4l2-test-buffers.cpp(554): node->node2 == nullptr
test VIDIOC_REQBUFS/CREATE_BUFS/QUERYBUF: FAIL
Total ...: 45, Succeeded: 42, Failed: 3, Warnings: 0
```

候选 `aml_vdec_drv.c:178–181` 在已有 `dec_ctx` 时返回 `-EBUSY`，
与第二次 open 失败相符。第三项依赖第二个 fd，不据此另判 MMAP 本身损坏；
EXPBUF/Requests 的后续输出也不是这些功能已完整验收。首次 open 和格式/控件查询可完成，
未见新增 panic/oops/SError。脚本保守保留失败模块状态，正常重启而非强卸载；未重试或跳过门禁。

## 合入范围与下次工作

fork `vim4-kvm-7.3` 已有 `4e3418b038587` 和 `323350fc77dff` 的 VDEC 时钟
ID/provider，以及 `1d80e6ccc3641` 的 Wave5 只读报告；窗口前远端为 `323350fc77dff`，
结束核对时另一个任务已推进到 `9d33f6ad27898`，祖先检查确认仍包含上述时钟提交。
这些独立基础已合入，不重复合并，也不覆盖本地主工作树。
p0 选择代码依赖尚未通过 compliance 的 T7 解码前端；本轮不将整条实验分支合入正式内核，
不正式部署。下次先离线处理多 fd 与单个硬件实例的所有权合同，并保留 DOS/JPEG 互斥、
故障隔离与 open 门禁；重新构建候选后另约窗口，从 compliance 再进入 H.264 正确帧。

## 回基线、冒烟与清理

00:29:34 UTC 已读回基线，00:34:53 清理完成并释放双锁，未用看门狗复位或人工 RESET。
`restoration-comparison.json` 核对入口与结束的 build、五文件、cmdline、原 Wave5、服务、
UDC、taint、panic 设置、模块挂载与实验模块列表全部相同：

- build `eeddb005df059a850853876d52ef603aa1af192b`；taint=0。
- 原 Wave5 文件 SHA `e88df353c730e5d82bbef8335788a28d5f71cfc7a4e1b8b5854ef00046d4b667`，
  加载 ID `8e2dedd2579d126adb8ba710eec2082ec1753b05`。
- One-KVM、manager、Wave5 monitor active，UDC configured；未运行 usb-pd-init。
- 300 秒运动画面 4K H.265：18,307 帧，59.9992648fps；freezes/drop/lost/PLI 全零，
  最大呈现间隔 38.6ms。键盘 down/up、绝对/相对鼠标、点击、滚轮均通过。
- 临时 payload、一次性 boot 目录、测试输出和本候选阶段收据已清理；无私有模块挂载、无实验模块。
  Mac 启动归档已清理，当前 p0 bundle 与 VM 精确 debug 资料继续保留。

前后 pstore 均已抓取：旧 `dmesg-ramoops-0` 哈希不变；console-ramoops 更新为正常
`reboot: Restarting system`，并非新 panic。候选与恢复基线未新增 oops/SError；
UART/previous-kernel-journal 可核对正常重启路径。

本轮 VDIN status 前后及 RX 中途/末段采样、baseline journal 另存日志。
300 秒内 journal 没有 `readiness revoked`、`tmds-invalid` 或 capture bus stop；
VDIN 摘录如下（after 在浏览器关闭及 HID 检查后，不能拿帧序号跨流作差）：

```text
before: stream_stops: 0; invalid_frames: 0; last_stop_error: 0; last_stop_reason: none
late:   stream_stops: 0; invalid_frames: 8675; stream_frames: 17650
after:  stream_stops: 0; invalid_frames: 9035; last_stop_error: 0; last_stop_reason: none
```

`invalid_frames` 在该候选对应的 `t7-vdin-test.c:795–810` 对 RX 检查返回 `-EAGAIN`
递增，并把该缓冲标为 ERROR，但该分支不停止流。这是明显的资格检查异常计数，
不能写成 RX 零错误，也不能仅凭此认定像素损坏或计算实际丢帧比例。
本轮浏览器无冻结、stream_stops 为零，仍不抹去这个计数；因上轮无计数快照，
无法据此判断新增回归。RX 源码、服务和策略均未在本任务修改。

## 上轮 1.647 秒停顿：RX 证据与归类

固定启动 ID `73c49e73-8d74-438f-84be-c5611613e6c5`，正式 baseline
`eeddb005df059a850853876d52ef603aa1af192b`。本轮只读取回其完整持久 journal，
保存为 `prior-baseline-journal.log`；不是拿当前启动的计数器替代历史数据。

`journalctl -b 73c49e738d74438f84bec5611613e6c5 -o short-monotonic` 摘录：

```text
[43.179277] VIM4 capture progress raw=Some((897, 897)) encoded=897 last_frame_ms=0
[45.394716] kernel: t7-hdmirx link readiness revoked: reason=5v-or-align error=-67 retries=0 users=1 configured=1
[44.900526] VIM4 capture bus stop raw=Some((976, 976)) encoded=976 last_frame_ms=403 signal=None
[44.909146] TRY_FMT failed for NV12 @ 3840x2160: Link has been severed
[45.918051] VIM4 capture started source=(Resolution { width: 3840, height: 2160 }, 60) codec=H265
[46.728755] Audio device lost: hw:VIM4HDMIRX,0
[47.937330] Audio recovered after 1 retries
```

以上内核与应用 journal 接收/显示次序不同，不据此计算亚秒级因果延迟。
同一采样窗口浏览器 `freezes=1`、最大呈现间隔 1646.9ms，drop/lost/PLI 均零。

- `tmds-invalid`：该启动保存的 journal 未出现该字符串；实际失就绪原因是 `5v-or-align`。
  候选同基线实现 `t7-hdmirx.c:1086–1094` 在 HPD 5V 或 TMDS alignment 检查失败时
  先返回 `-ENOLINK`，尚未到后续 TMDS qualification 分支。不能把它改记为 tmds-invalid。
- `stream_stops`：上轮没有采集 VDIN debugfs status，journal 也未记录此计数，无法追溯数值。
  `t7-vdin-test.c:838,1365` 的计数在内存中，后续重启清零；不伪造历史计数增量。
- **归类**：有 RX 失就绪→采集停止/重建并伴音频恢复的证据，归入 RX/采集链路瞬断，
  不是仅凭浏览器 freeze 推断网络或解码器问题。发生时已回正式基线；没有对照证明
  它是本轮 VDEC 引入或新的 RX 版本回归。发送端瞬态与接收端判定问题仍不能区分。
  本任务仅记录，不修改 RX；本轮恢复冒烟额外保存 VDIN 前后、RX 中途/末段 status 及完整 journal。
