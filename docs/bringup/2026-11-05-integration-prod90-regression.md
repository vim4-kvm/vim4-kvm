# 2026-11-05：生产 .90 首窗与单项接收补测

**窗口整体未通过；已恢复正式 `.3` 并验证真实视频解码推进。**
这是首窗结论；随后获批的单项补测已通过，见[补测记录](#获批单项补测通过)。
其他未验项保持原状态，未因接收补测通过而扩大验收结论。
`.90` 启动及下列采集/编码短轮通过，应用重启后的接收检查遇到8081拒绝连接，
按首错即停采证/恢复，没有重试或再占板。接收脚本缺少重启应用后的API就绪等待，
不能区分尚未就绪或实际启动失败，**不能据此归因内核，也不能记候选端到端通过**。

## 身份、票据与命令

候选来自[集成构建记录](2026-11-05-integration-build-results.md)，源码
`fd41fb5950b9da1fb336ce00d5137d27ee9755fa`，release `7.3.1-vim4-20261105.90`，
GNU build ID `6c5ebf0605c190d7670374fb6ea880958f54cba1`。启动后验证内核身份，
运行模块notes全部属于当次完整模块清单；没有替换正式Image/DTB/模块或默认项。

FIFO票 `405b5a6372b544bf800fcfab8735e14e`，19分钟租约、sampling独占。
窗口起止Unix时间 `1793885903.89988` / `1793886056.158679`，实际 **152.259秒**。
正常结束释放板票后，下一位fan-thermal按FIFO接续；本worker未再访问板子。

取板前已有C工具在VM持heavy票按Werror编译，浏览器离线启动检查通过。
执行的是既有工具及一次性编排，没有新增驱动诊断接口、没有持板编译。
实际入口和资产哈希保存在本工作树
`build/kunit-migration/integration-73/board-assets/`：

```sh
tools/board-queue run --who kunit-migration \
  --purpose 'production .90 migrated-driver checklist, first-error stop, restore .3 and decoded video' \
  --max-min 19 -- python3 build/kunit-migration/integration-73/board-assets/window.py
```

编排复用board-window的boot-candidate/return-baseline、完整proof、ready与接收器，
UART为既有 `/dev/cu.usbserial-1100`。按[回归清单](2026-11-05-integration-regression-plan.md)
只运行条件已满足的项目，其他项保留未验。板端benchmark沿用实际One-KVM进程的
GStreamer环境，使用现有skip-debug-clocks选项，不盲扫CCF/MMIO；未作性能比较。

## 实测通过的局部范围

各轮10帧预热、30帧测量，报告原始/输出均40帧，PTS前进、正常EOS/退出。
以下通过仅指这些命令/断言及离线解码范围，不能覆盖后述未验项。

| 项目 | 实测 | 判定范围 |
|---|---|---|
| HDMI RX | NV12 1920×1080，40/40，测量capture IRQ +30 | 真实采集、交付和短轮退出；未验证运动标记/像素、全部MMAP/持导出路径 |
| T7 JPEG | 3840×2160/q80、1920×1080/q50、再次3840×2160/q80各40/40；测量JPEG IRQ各+30 | 真实DMA编码、尺寸/质量切换、关闭重开；三份码流各软件解码40帧、尺寸正确 |
| Wave5 | H.264/H.265各两轮1920×1080，每轮40/40；测量VPU IRQ各+31 | 正常编码/EOS/退出/再开；四份码流各软件解码40帧、尺寸正确；不等于挂死/隔离恢复通过 |
| 资源与诊断 | 各轮CMA退出差值最大8KiB；taint恒为4096（既有OOT）；增量日志无BUG/WARNING/Oops/KASAN/panic、未见Wave5 timeout/isolation/fail特征 | 短轮未观察到新增诊断/CMA滞留；不能替代长压/故障注入 |
| brcmfmac能力 | iw phy/dev命令成功，声明P2P-client/P2P-GO/P2P-device，存在managed wlan0 | 基本能力/接口查询完成；未进行P2P协商/传输 |
| ALSA | arecord/aplay枚举命令成功 | 只有接口枚举，音频数据与AED/速率行为未验 |
| CRG/TCPM | UDC configured，Type-C sink/device、usb_power_delivery；online=1，5,000,000µV / 3,000,000µA | 本次运行时只读状态；不证明热插拔、控制异常、重置或唤醒 |

七份码流离线用标准ffprobe显式mjpeg/h264/hevc demuxer解码计帧，均40帧，
codec/尺寸匹配，stderr无error。原始输出是board-results/offline-decode.json及每份
ffprobe JSON/stderr。最初自动识别`.jpeg`按单图只报告1帧，不是驱动丢帧结论；
保留offline-decode-autodetect.json及日志，显式选择实际串接MJPEG格式后7/7通过。
没有标准像素金值或运动源，不声称内容/色彩正确性通过。

## 首错、脚本修正与恢复

板端各轮结束后 `systemctl start one-kvm` 返回成功。接收脚本立即建立SSH转发并
offer，SSH报 `connect failed: Connection refused`，浏览器 `Failed to fetch`。
这次编排没有在应用重启后复用既有ready检查，违反了[就绪合同](../board-window.md#候选链与恢复)。
没有采到可区分启动尚未完成与启动失败的候选服务日志，原因未定位；这里登记
测试前提缺失，不将其写成已证明的内核回归或简单宣称只是等待不足。

首错后只回收证据、正常重启回 `.3`，没有再次offer或重跑候选。
恢复核对完整保护文件、原模块notes、DT/应用和cmdline；真实接收5秒解码推进299帧，
约59.789fps。入窗前推进297帧，约59.369fps；只作视频推进证据，不作性能结论。

离线保留实际执行的video-check-first-attempt.py，给后续video-check.py补一行
现有 `bw.ready('vim4', timeout=60)`，Python字节编译通过。
首窗收尾时修正尚未在板上复测、未申请第二票；后续协调者明确批准的补测另记于末节。

## 未验项与原因

| 项目 | 未验范围与本次前提缺口 |
|---|---|
| HDMI RX/F类 | 无已准备的运动checksum源，hdmirx-stream-check的标记/MMAP/持导出轮未运行；无标准像素样本比对 |
| DRM/显示 | 板上modetest未安装；未建立活动输出/CRTC及空闲master前提，未运行scanout/IGT；不强制modeset |
| ASoC | 既有入口存在，但没有已准备的受控HDMI音源、接收及速率恢复夹具；音频数据、AED、全速率未验 |
| brcmfmac | 无当前连接的已保存SAE profile，P2P/STA并发、真实对端协商与传输未验 |
| ADLA | 没有暂存的锁定模型/probe/输入/金值，未捕获utilization属性；7e35e3b公式所需同次频率/MACC/耗时未取得，**显示行为仍需实板回归** |
| CEC | 未建立合格CEC对端，未运行compliance或TX/RX路由验证 |
| secure genpd | 只保存一次框架summary；无合格SMC失败注入，不强制断共享域；供断电/错误路径未验 |
| HID/UAC2 | M6测试USB主机和受控UAC音频前提未确认，未重绑、未发HID、未录音 |
| CRG/FUSB302/TCPM | 只有只读状态，无主机枚举/异常控制夹具；未reset/睡眠/唤醒/热插拔，未拔单线供电 |
| Wave5/B类 | 短正常编码不能代替挂死/隔离/复位/恢复；生产配置不注入，仍按独立故障注入方案待调试窗 |
| 候选应用接收 | 首窗失败保留；后续仅此项获批补测通过，见末节 |

## 原始输出与验证

`logs/kunit-migration-prod90/` 保存window-result.json、preflight-baseline.json、
baseline-proof.json、完整候选启动collect/dmesg、两次UART、regression.log、
candidate-video.log、returned-baseline-identity.json、returned-video.log和return-baseline.log。
board-results.tar.gz为75,924,100字节，解包目录
`board-results/kunit-migration-prod90/`含各轮JSON/码流、results.json、状态及dmesg。
编排输出 `build/kunit-migration/integration-73/board-window-wrapper.log`，离线解码输出
offline-board-decode.log与初次autodetect日志均保留。没有push、合并或修改内核源码。

## 获批单项补测通过

协调者确认首窗8081错误不归因内核，明确批准一次FIFO补测、上限15分钟，
只验证`.90`应用重启后的端到端WebRTC接收。没有重跑采集/JPEG/Wave5等已过项目，
没有补测其他缺入口或前提的项；前述未验清单保持不变。

补测前在UTC `2026-11-05T14:05:41.262885+00:00` 完成两脚本的py_compile检查，
均PASS；时间、路径及SHA256保存于
`build/kunit-migration/integration-73/retest-pycompile.log`。
video-check.py SHA256为 `f0d3308dd915ac3066040d3198a85b4ca4e3a05d5cb1fdee779a7722959fe3bb`，
retest-window.py为 `a14fb3a4ab49e582cd3c300a6b558b4ae30d26c164339e32c22587bd496c4c68`。

等待复用 `bw.ready(timeout=60)`，另设65秒SIGALRM墙钟硬限；整个候选接收步骤
150秒上限，失败即停并采one-kvm journal、systemctl状态和8081监听状态，再恢复。
超时分支已准备但本次未触发，不声称做过故障注入。

```sh
tools/board-queue run --who kunit-migration \
  --purpose 'approved .90 application restart WebRTC retest only; bounded API wait; restore .3 video' \
  --max-min 15 -- python3 build/kunit-migration/integration-73/board-assets/retest-window.py
```

票 `2770606356514a3cbaef27f4fa8365d6`，Unix起止
`1793887541.7127051` / `1793887723.5995898`，共 **181.887秒**（含等既有heavy结束），
未超15分钟，sampling独占，结束已释放。两次窗口合计约5分34秒。

| 补测步骤 | 实际结果 |
|---|---|
| 启动/重启应用 | 同一`.90` RAM包启动成功；systemctl restart one-kvm成功 |
| API就绪 | 2.097秒；等待期间的暂态stderr原样保留，最终ready通过 |
| 端到端接收 | H.265 3840×2160，5.0019秒解码推进304帧；接收后复核仍为`.90`及build ID `6c5ebf0605c190d7670374fb6ea880958f54cba1` |
| 服务采证 | 成功时也保存candidate-service-state.log，含one-kvm journal/状态及8081监听 |
| 恢复正式基线 | 正常重启回`.3`，完整保护文件、原模块notes、DT/应用/cmdline核对通过 |
| 恢复视频 | H.265 3840×2160，5.0031秒推进298帧；API等待0.510秒 |

**应用重启后的接收补测PASS，`.3`恢复及视频推进PASS。** 这只关闭首窗遗漏的
单项验证，不抹掉首窗失败，不作性能、长期稳定性或像素正确性结论。

原始输出 `logs/kunit-migration-prod90-retest/`：window-result.json、
preflight/baseline proof、candidate-video.log、candidate-service-state.log、
post-receive-identity.json、两次UART、returned-baseline-identity.json、
returned-video.log、return-baseline.log。API等待暂态stderr与最终接收JSON同文件，
JSON在末行。实际脚本为board-assets/retest-window.py和video-check.py，完整执行输出
`build/kunit-migration/integration-73/retest-board-window-wrapper.log`。
本次没有内核源码/默认项变更，没有push或合并。
