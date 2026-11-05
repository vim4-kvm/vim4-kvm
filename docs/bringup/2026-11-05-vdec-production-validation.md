# 2026-11-05：生产配置解码功能验收

调试 `.23` 遇启动锁错误与冷复位后，按协调者批准另走正式配置的功能验证。
本轮只证明实际运行到的接口、出帧与像素结果；不能替代以后零告警调试内核的
锁、DMA 和内存验收。不修改 MMC、dma-debug 或 PWM，窗口结束恢复 `.3`。

## 候选准备

独立 `vdec-production` 工作树基于 `hwdecode-parity` 已提交 HEAD
`e6f9f06b06d3765148ae6a271c64d8482a175531`，tree
`c2642863a77ac3d8b1cdf5b1f6b99ad847629159`，不包含调试修复分支。
使用正式 `packaging/kernel/kernel.config`，SHA-256 为
`7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`，
不合入调试片段。完整包从干净树生成后才应用未提交的 HEVC 握手草稿，构建
匹配 Image/BTF 的私有模块；草稿与[联合窗口](2026-11-05-vdec-joint-debug.md)
相同。正式源码锁和默认启动不修改。

私有构建锁 `build/hwdecode-parity/sources-vdec-production.toml`；完整构建、
封包和私有模块日志保存在同目录。窗口输入与身份记录在 `run34/`。
构建、封包、私有模块 W=1/C=1 sparse 与 RAM 包离线校验已完成；原始输出为
`production-build.log`、`production-package.log`、`run34/prepare.log`、
`run34/artifact-sha256.json`。生成配置与正式配置逐字节一致。

| 产物 | 身份 |
|---|---|
| release | `7.3.1-vim4-20261105.24` |
| Image build ID | `fb4954fb39169d9bbfbf160394d5249d95faf3b0` |
| Image SHA-256 | `2a88e99b02054be36646552184f92fbba68026197ce271d53c19286b376c815f` |
| 完整包 SHA-256 | `31f2d4dd3522316da400b7c877a97558f054a7e7745acc841394153c3df321b4` |
| RAM 包 SHA-256 | `530ab5d6d0afdfb84805e74b0ba557bedd853c43047394daa4155af327afbf6b` |
| manifest SHA-256 | `b5f57a8b942f830c9dd1199a2b4c9644c157c5ff74bcc57ea4607cef3c2e878f` |
| 私有模块 build ID | `2899fb8f415f763269c2ad336e2fd18b7900899e` |
| 私有模块 SHA-256 | `a329e94bfc02da392724cb7836491a94f393a6d24f48620e9bd2dec5e932d90d` |
| HEVC 草稿 SHA-256 | `9d081f4235dd70bf184ecb33c749adb951683b64c6145fbc6d2710efb7482909` |

## 验证顺序与边界

沿用 `vdec-window.py --validation-plan`，同一窗口先检查三个节点的 compliance：
stateless 带 media/Request，JPEG 使用既有 640×368 的 16 帧 MJPEG，HEVC
使用 `AMP_A_Samsung_7` 的 17 个访问单元。JPEG/HEVC 只加工具帧头，没有重新
编码或改变原码流。JPEG 没有 Fluster 标准套件，因此这部分仍为补充样本。
工具若跳过 stateless 出帧，必须按实际结果记跳过，不能算流测试通过。

随后先运行 HEVC `AMP_A_Samsung_7`；只有通过才依次尝试 H.264
`AUD_MW_E`、`BA1_FT_C`，MPEG-2 `att`、`mcp10ccett`，以及 HEVC
`AMP_B_Samsung_7`、`AMP_D_Hisilicon_3`。测试集、解码器和输入沿用锁定且已校验
的 Fluster bundle，每组实际运行 `list -c`。所有组共用截止时间，首次失败即停止，
保留逐码流原始 JSON、摘要与未运行状态；不能因分成子集重新获得时间预算。

本轮计划不包含完整矩阵、5.15 对照、性能和长期共存。每次启动仍要求完整包身份、
运行配置哈希、只读模块挂载、看门狗、正式文件与 performance CPU 策略匹配。
生产配置未开启锁/内存检测，故没有告警也不能据此推断这些检查通过。

## 实板结果

窗口 `hwdecode-parity-r34` 已执行并结束，正式 `.3` 和视频已恢复。`.24` 正常
启动并通过就绪、正式文件、performance 策略、运行配置哈希和私有模块身份检查；
MDEC/HEVC 电源与固件预检完成。未复现 `.23` 的启动冷复位，但这是不同配置、
不同源码候选，不能据此归因或宣布 `.23` 问题已解决。

首个 stateless 节点在带流 compliance 的第二个 OUTPUT buffer 失败：

```
Video Output Multiplanar: Frame #002
fail: v4l2-test-buffers.cpp(415): (int)g_sequence() < seq.last_seq + 1
```

锁定工具的该检查也适用于带 ERROR 标志的已出队缓冲，并非遇缺少 codec controls
就跳过所有流测试。内核日志有 `not ctrl ref for h264 decoder`，随后归还错误缓冲。
离线核对候选 `drivers/media/platform/amlogic/vdec/aml_vdec.c` 的
`m2mops_vdec_device_run()`：DONE/ERROR 两条路径均调用
`v4l2_m2m_buf_done_and_job_finish()`，通用路径没有为输出/捕获缓冲赋递增 sequence，
`vb2ops_vdec_start_streaming()` 也没有相应序号复位。该问题应按 V4L2 缓冲生命周期
修复并用同一带流 compliance 复验，不能把它归入 Fluster 或固件限制。
本轮只定位，尚未修改驱动；HEVC 草稿也未提交。

| 项目 | 结果 |
|---|---|
| media `/dev/media0` | 8/8，零失败、零警告 |
| stateless `/dev/video1` | 流测试前 50 项返回 OK（含 Not Supported）；第二个 OUTPUT buffer 序号检查失败，首错退出，无最终 video 总结 |
| JPEG、HEVC compliance | 未运行，按首错即停规则退出 |
| HEVC `AMP_A_Samsung_7` | 未运行，不能计为解码超时 |
| HEVC 全集 | 本轮 0/147 已验证通过，147/147 未运行 |
| H.264、MPEG-2 子集 | 全部未运行，后续子集调度分支未获实板验证 |
| 内核日志 | 本次保存日志未见 BUG/WARNING/KASAN/Call trace；生产配置不提供锁/内存检查结论 |
| 正式基线恢复 | `.3` / `e595ad243d663f6c33b92678a4de6e0b78ec16d5`，2,370 个证明文件一致，服务/UDC 就绪 |
| 恢复视频 | 3840×2160 H.265，约 5 秒增加 298 帧，59.56 fps，新增丢帧/冻结/丢包均为 0 |

没有在失败后重载或重试驱动，恢复后删除本次临时 Wi-Fi 固件副本并释放板锁。
完整标准矩阵、5.15 对照、性能、长期共存及调试内核验收均仍未完成。

原始记录在 `logs/hwdecode-parity-r34/`：候选串口
`uart-1793867879685102000.log`、启动采集 `dmesg-1793867881599338000.log`、
`returned-baseline-identity.json` 和 `returned-video.log`。验证目录
`validation-fluster-1793867881762408000/results/` 保存最终 `kernel.log`、
`window-status.json` 及 `compliance/stateless-compliance.log`、`compliance/results.json`。
主机 `build/hwdecode-parity/run34/window.log` 保存首错与恢复成功状态。
v4l-utils 为 `1.33.0-1` / `d2e89246cefcb6371425361b12c4ca2a36a662d2`。
主仓库离线检查 `run34/main-tests-preflight.log`：537 项、11 跳过；没有新增 Python
或 mock 测试，也没有修改 MMC/dma-debug/PWM。
