# 2026-10-20：驱动原生基准、AVC profile 与采集内存

摘要：新增 C/GStreamer 的纯采集及硬编码基准，排除 Python、解析、文件输出和
网络。独立解码发现旧 Wave5 驱动请求 H.264 High 却实际输出 High 10；修正 T7
固件命令的 profile 编号，并取消直接 DMA 模式不用的三个私有复制环分配。
同条件纯采集运行中的可用 CMA 从 421,168 增至 457,624 KiB，释放 35.6 MiB。
H.264/HEVC 各 240 帧全部解码通过，实际 profile 为 High/Main。整机 CPU 三轮
中位数约 0.13/0.28/0.32%（纯采集/H.264/HEVC）。本轮保持 7.x，未重新启动
5.15，因此没有声称完成同一新入口的跨内核性能对齐。

## 基准与旧驱动证据

用法、编译与测量边界见 [驱动基准](../driver-benchmark.md)。板上原生 cc/GStreamer
1.24.2，固定物理 HDMI 4K60 RGB8 运动源、20 Mbps、GOP 60、关闭逐行刷新。
CPU governor 为 performance，A73/A53 最大 2208/2016 MHz，Wave A/B/C 约
666.7 MHz；无应用客户端或其他编码任务。每轮先排除 120 帧，再测 1800 帧。
三个 backend case 各三轮串行运行；整机 CPU 为八核平均，进程值按单核计。

旧内核 `1762175bf43d`、uname build `Tue Oct 20 13:37:27 UTC 2026`：

| 负载 | 整机 CPU 三轮中位数 | 编码 sink→src p50 / p99 三轮中位数 |
|---|---:|---:|
| 纯采集 | 0.145% | 不适用 |
| 采集＋H.264（实际 High 10） | 0.349% | 11.184 / 12.422 ms |
| 采集＋HEVC Main | 0.325% | 12.371 / 15.226 ms |

源到编码 sink 的桥接中位数约 0.034–0.040 ms；码流平均约 20.1–20.3 Mbps。
这是默认 no-payload-read 管线结果，包含原生测试进程、内核及系统背景；不是纯
硬件耗时，更不是完整 One-KVM 的 CPU 或光学延迟。CPU 接近系统背景负载，
不得把不同轮次的小波动当成驱动优化收益。

旧三轮报告为 `logs/kernel-edge/vim4-driver-native-{capture,h264,h265}-{1,2,3}.json`。
三轮用工具源码 SHA `dbf3b1005309032c95af70586b4284f74a2abb350180bc1bc84315c039bf8072`，
二进制 SHA `7d718edc5f65fe89204259ca536e17ff836320c3e453439d68b071ae5593915a`。
随后补报告元数据、验证文件输出和设备检查，默认采集/编码计算路径未改；最终
工具源码 SHA `082652fee7fdd7819900a5a67215c7e974d4a497c05b06b631404578e8384cc8`，
二进制 SHA `696f2f87b067ea06cca92b4b9d74a4ac8ac7d8ab069e96717103f5c5822c43d4`。
旧内核又用最终入口各测一轮，结果为 `vim4-driver-native-final-*.json`：
纯采集/H.264/HEVC 整机 CPU 0.109/0.326/0.333%，编码 p50 11.181/12.370 ms。
早期二进制和源文件保留在板上 `/var/tmp/vim4-native-baseline-evidence`。

## 实际 profile 的回归

另开带文件输出的正确性窗口，各编码 240 帧，**不使用该窗口的 CPU 作比较**。
在构建 VM 解码，H.264/HEVC 的全部 480 帧均通过三处运动标记、推进和颜色检查。
但 ffprobe 显示 H.264 为 **High 10、8-bit yuv420p、Level 5.2**，与 caps 的
High 不一致；HEVC 为 Main、Level 5.0。成功解码不能掩盖 profile 不匹配。
旧原始文件为 `vim4-driver-native-check.h264` / `.h265`，结果为
`driver-native-verify-h264.json` / `driver-native-verify-h265.json`。

源码核对：当前 Wave5 的 AVC Extended/High/High10 编号为 3/4/5，而匹配 T7
旧固件没有 Extended，其 High/High10 为 3/4。内核 `f6e848f2ed481` 在 SPS
命令边界翻译编号，保持 V4L2/API 参数不变；T7 的菜单拒绝不支持的 Extended、
High422、High444，其他固件路径不变。同时清除切离 constrained-baseline 后
遗留的 constraint_set1，防止同一实例切 profile 时残留约束。

新增 `test_profiles.py` 编译实际翻译函数和控制分支，检查 High/High10 命令、
非 legacy/HEVC 不变以及 constrained-baseline→High/Baseline 的约束清除。
验证工具新增 `--expect-profile`：旧 High 10 文件在期望 High 时实际拒绝，
负对照 `driver-native-high-negative.stderr`；离线单元测试也覆盖先拒绝再解码。

## 内存变更与部署

`46f8489461869fedc8e7bc33d4d5412e082b5515`，tree
`b03cccda3f83ba6241b23820e942e95985885147`，在 direct_dma 下不分配复制环。
三组 slot 状态及独立快照分配保留；复制模式仍分配旧环。
test_stream.py 的直接路径现在将私有 slot 地址和指针置空，验证不会访问旧环。
Linux ASan/UBSan 的所有权、耗尽、在途停流、busy/missing IRQ 隔离通过；另通过
VDIN 时序/快照测试、Wave5 导入边界及 32 个分配/关闭失败用例。

完整 Image/dtbs/modules 构建成功，未发现 warning:/error:，2333 个匹配模块。
Image SHA `b3c36c97efc04310dfd33d950fba539ce547d4c8020b3dad7686e2ca4bd93aec`；
模块归档 SHA `470beb359079f5b54c21f09ed39d40bda863bc61562c85719f90ea2aede3daad`。
安装前确认串口可用，停止 Mac 源窗口，备份旧实验 Image 和完整模块集到
`/var/backups/vim4-onekvm-edge-20261020/profile-memory-46f8489`，单次选择 OneKvmTest。
新 uname build 为 `Tue Oct 20 14:45:52 UTC 2026`；默认启动仍为 5.15。
原应用、兼容分配器、服务、默认 Image 和 extlinux SHA 均保持不变；固件、DTB、
私有 GStreamer 插件也未改。

原生工具的四个 C 回归包含预热/PTS 边界、拒绝不匹配及漏帧、父缓冲 lease，
在 Linux ARM64 常规编译和 ASan/UBSan 下通过。模拟 fd 仅证明所有权。
与实际驱动性能、物理 DMA 一致性分别核对，不把软件测试冒充上板验收。

## 新内核复测

相同最终工具、固定 4K60 RGB8 运动、20 Mbps、GOP 60、120 帧预热＋1800 帧，
各三轮，CPU/编码器频率与旧轮一致。全部报告 success=true：

| 负载 | 整机 CPU 三轮中位数 | 编码 sink→src p50 / p99 三轮中位数 |
|---|---:|---:|
| 纯采集 | 0.133% | 不适用 |
| 采集＋H.264 High | 0.275% | 11.174 / 12.337 ms |
| 采集＋HEVC Main | 0.315% | 12.380 / 15.186 ms |

三组均约 59.998 fps，码流约 20.1–20.3 Mbps。旧 H.264 实际 High 10，而新为
High，因此不是相同 profile 的 CPU A/B；不能将数字下降归功于取消空闲分配。
HEVC 同配置的小 CPU 波动也不构成优化收益。明确收益是内存与 profile 正确性。
报告在 `logs/kernel-edge/profile-memory/{capture,h264,h265}-{1,2,3}.json`。

纯采集三轮的 streaming CMA 均为 457,624 KiB，旧三轮均为 421,168 KiB；
差 36,456 KiB，即 35.60 MiB，与三个 page-aligned 4K NV12 私有分配一致。
关闭编码后的立即 CMA 会受延迟释放影响，最终原生测试完成后恢复 506,232 KiB，
DMA-buf=0、taint=0、faulted=0、dma_idle=1、stream_error=0、stream_copy_bytes=0。
记录 `profile-memory-post-native-status.log`，没有把 transient 差值当成泄漏。

独立录像 `profile-memory/check.h264` / `.h265`，严格 `--expect-profile=High/Main`
均通过：各 240 帧、3840×2160、全部运动标记/推进/颜色正确。H.264 实际 High、
Level 5.2；HEVC Main、Level 5.0（ffprobe level=150）。旧 High 10 负对照拒绝，
修正后的 High 正对照通过，证明核对的是码流而不是 GStreamer caps。

原生采集检查又完成 600 帧×3 轮，1800 帧的三处帧号及颜色均通过；每轮持有
全部四缓冲期间内容不变、耗尽后恢复。REQBUFS(0) 旧导出重映射和活动 close
通过；序号≥8 的稳定段各约 59.998 fps。总 span 包括完整缓冲哈希及人为耗尽，
不拿该平均数代替稳定帧率。本轮未再次做保留导出跨模块卸载或真实 DMA 故障注入。
证据为 `profile-memory/stream.jsonl`；六个原始快照保留在板上测试目录的 frames。

主仓库离线测试 105 项：100 通过、5 明确跳过（Mac 缺 GStreamer 开发库等）；
相应原生 C 回归已在 Linux ARM64 常规编译及 ASan/UBSan 单独通过。
恢复实验应用后 Chrome 155 的 H.264/HEVC 各测 20 秒（另预热 8 秒），均为
3840×2160、约 59.99 fps，增量零 dropped/lost/freeze，记录
`profile-memory/restored-h264.json` / `restored-h265.json`。这是恢复后的功能检查，
未将其当成光学延迟或长期稳定性证明。结束恢复 H.264/30 Mbps、关闭 Mac 源，
实验服务 active，板子保持新 7.x；最终 DMA-buf=0、taint=0，保护文件 SHA 未变，
见 `profile-memory-final-status.log`。本轮未运行 5.15 厂商编码路径；7.x 中其共享锁
文件不存在，没有手动创建、重建或删除它。
新内核仍为固定 RGB8 4K60 实验版本；动态 HDMI、音频、完整 USB、runtime PM
功耗和长时间推流均没有由这轮测试验收。5.15 的同一新工具基线仍待补测，
历史带 Python/parser/文件输出的结果不能直接充当它。
