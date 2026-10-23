# 2026-10-22：Wave5 首轮部署采集停止复核

结论：失败发生在HDMI模式切换后的**采集／恢复路径**，观察器捕获了真实停流；
不是已证实的Wave5固件编码挂死，也不能凭浏览器曾出帧／快照成功把它判成假阳性。
同一已部署基线上有界重复检查第5轮复现相同失败，未重新部署或改检查门槛。
具体触发是源端失锁、RX测量资格检查还是应用恢复竞态，仍需区分，置信度分层见下文。

## 保存日志的时间线

来源：[部署记录](2026-10-22-edge-wave5-deploy.md)、
`logs/wave5-deploy/window/h265.log`、failure-board.log、video/browser-h265-events.jsonl。
浏览器文件名时间是Mac Unix毫秒，journal为板端UTC；下表的截图保存时间来自本地文件mtime，
只辅助排序，不作为精确延迟测量。

| UTC 2026-10-23 | 证据 |
|---|---|
| 02:35:24.372 | 应用从H.264切到H.265，共享管线重建 |
| 02:35:29.092–37.111 | 640×480通过：255解码帧、约60.10fps、snapshot=200、14个DMA对象 |
| 02:35:37.482 | 开始720×400 EDID切换 |
| 02:35:42.477、45.231、48.271、51.238 | pipeline45–48的GstV4l2Src反复报`gst_v4l2_object_poll: poll error 1` |
| 约02:35:51.318 | 保存720×400 JPEG；随后资源检查`Total 0 objects, 0 bytes`失败 |
| 失败捕获 | video width/height=0、paused=true、src=false；VDIN frames=102、dma_idle=1、faulted=0、stream_error=0 |
| 02:35:55.292之后 | finally恢复EDID／H.264并关闭会话；这是断言之后的清理，不能解释之前的零对象 |

`browser-modes.mjs:175`的断言在采集帧推进、颜色检查和快照之后，**在finally之前**。
出现零DMA对象时CMA已回到505168KiB，符合管线释放，不是仍占buffer的Wave5卡死形态。
保存的720×400截图只证明某时刻成功取帧；不能证明检查采样结束时采集仍活跃。
失败后的source-mode.log与RX状态已恢复到4K，不能拿它证明故障瞬间输入锁定。
source event日志只有sequence 0–5，没有时间戳，无法单独重建瞬态失锁。

`poll error ... (25)`来自GStreamer采集端；不能把随附errno文案直接认作“缺少某个ioctl”。
内核VDIN在取帧资格错误后可走`vb2_queue_error()`，vb2非streaming或error队列返回EPOLLERR；
One-KVM的`capture_vim4()`读取bus error后退出并释放管线，外层回报无信号并等待重试。
`faulted=0/stream_error=0`是该时刻驱动状态，不保证这段路径未返回RX资格错误。
这给出了可解释日志的代码路径，尚不能据日志确认每次具体返回码。

## 有界复现方法与边界

锁内在**保留的0196fe22…部署**上重复原浏览器检查器，目标为`0,1,1,0`，
即640×480→720×400→720×400→640×480，尺寸均合法，不触发非8对齐HEVC。
仅把输出路径转到独立目录，读取原模式资格输入，不覆盖原部署失败证据。
保留帧推进、颜色、快照、资源与fps断言；原断言fps>5与fullRate诊断也原样保留。
未重跑完整原始HDMI／18次H.264前序，不声称重复了10次完整部署事务。

```sh
python3 -u build/small-fixes/wave5-repeat.py
# 每轮内部：
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 build/small-fixes/wave5-repeat.py ROUND
```

每轮≤150秒，正常finally恢复原EDID与编码模式，释放双锁再开始下一轮。
第一组1–4轮通过；第5轮720×400重现同一`capture stopped during the browser sample`，
立即停止该组，保留日志而未部署／重启。第4轮有30.60／47.92fps的低帧率窗口，
原门槛通过不等于全程60fps。第5轮此前640×480约60.11fps，随后管线60–63连续poll错误，
失败时VDIN frames=29、dma_idle=1、零DMA对象，failed video同样src=false。
该轮health.log确认两服务active、UDC configured、EDID SHA256恢复为
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。

第一组日志 `logs/small-fixes/wave5-repeat.log`、`wave5-round-1/`至`wave5-round-5/`，
含原始check.log、快照、source events、journal和恢复后的health。
为了进一步区分输入锁定，后续最多补5轮，在原序列旁每200ms只读RX／VDIN debugfs，
保存带板端时间的receiver-trace.jsonl；观察开销与第一组不同，结果分开报告。

第二组6–10轮全部通过，日志为`wave5-repeat-traced.log`和`wave5-round-6/`至`wave5-round-10/`。
RX trace显示正常EDID切换时PLL／TMDS alignment下降，随后link_ready和采集恢复；
本组未捕捉到原失败，不能用其成功trace解释第5轮的具体根因。
两组合计9轮通过、1轮复现；增加观察器后0/5不能当成问题已消失或可靠的概率估计。
未重新安装Image、DTB、模块、应用；无Wi-Fi/P2P操作。

全部采样结束，再持板锁运行`build/small-fixes/final-health.py`。
`logs/small-fixes/final-health.json`、final-hid.log、final-window.log实际核对：

```text
buildId=3a61b75bccf8c46e9411dee92928999884bbfc7f
one-kvm=active, vim4-manager=active, UDC=configured, taint=0
keyboardDown=1, keyboardUp=1, absoluteMouse=true, click=true, wheel=true
relativeMouse: [0.699996,0.599989] -> [0.709904,0.611733]
FINAL_BASELINE_HID_PASS
```

两应用运行哈希仍为部署基线的72db30c0…与3fc215e3…；原EDID已恢复，
同一bootId `4c9f3ff2-a2a0-495c-9268-f7ef48bf2731`，没有为复现而重启。
最终释放全部锁；保留同轮[PD持久化修复](2026-10-22-pd-manual-contract.md)。

## 置信度与后续

- **高**：确实发生采集停流／重建间隙，资源断言反映真实状态；现象可在不改部署时重现。
- **高**：现存证据不支持“Wave5编码器固件挂死”的归因；本轮没有Wave5超时、内核挂死、
  新panic或需要RESET的证据。不据此排除所有潜在编码问题。
- **中**：720×400切换后的RX／采集恢复时序触发；重复poll错误、源模式切换和最终管线清理支持此方向。
- **未确定**：物理TMDS瞬态、RX测量读取／lease比较和应用重建各自的责任比例。
  若后续修复，应补齐失败瞬间RX／队列错误原因，而不是放宽资源断言或仅增加等待。

本任务不改部署、内核或应用恢复代码；本记录用于下轮定位，不把未证实的竞争点包装为修复完成。
