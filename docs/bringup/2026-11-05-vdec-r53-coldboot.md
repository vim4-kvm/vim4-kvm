# 2026-11-05：r53 `.28` 再次启动冷复位

保护清单已从新正式 baseline 生成，排票前离线相等检查通过；`.28` 在解码前
再次直接回 BL1，未完成候选 ready。compliance、Sharp 跟踪、Fluster 全部未运行。
没有修改 MMC/PWM/ADLA，也没有把启动失败算成解码像素失败。

## 原始事件

`logs/hwdecode-parity-r53/uart-1793909541958771000.log`：
`.28` Linux 启动后，NetworkManager/hostnamed、TEE preload 和 cpufreq 服务启动
阶段出现 NUL、`T7:BL:`；后续 `stick_reboot_flag=0x0`、`cold_boot`，启动新正式默认。
此前没有 panic/Oops 或正常关机尾部。末条内核时间 **5.331471 秒**只是复位时间下界；
没有逐行主机时间戳，不能给出精确的 Linux→ROM 间隔。

内核仍为源码 `960132382e00864f4944aee077cd621927a97bb0` 的 `.28`，生产配置
SHA-256 `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`。
RAM 包与 [r52](2026-11-05-vdec-r52-baseline-guard.md) 相同，payload 为
`/var/lib/vim4-kvm/ram-candidates/hwdecode/rebase28-formal/81bb2f999ffffb38d549afbf8b15fb3048184c0f`。
没有 HEVC 草稿。r51、r52、r53 三次 `.28` 启动中两次冷复位，样本不足以归因。

## 恢复与清理

`returned-baseline-identity.json` 核对新正式 `7.3.1-vim4-20261105`、build ID
`bdbfa439f298e92b5bad092528d11119a974f262` 和全部 2372 个保护文件与 proof 相等。
`returned-video.log` 实际 H.265 3840×2160，299 帧、59.77 fps，零新增 dropped/freeze/lost。

复制的收尾脚本误留归档参数 52，旧目录不存在检查拒绝，未删除任何错误目录。
另排只做归档的短 FIFO 票，逐项核对并删除 r53 的 515 个上传文件；证据为
`build/hwdecode-parity/run53/board-upload.tar`、`board-upload-files.json` 和
`upload-cleanup-retry.log`。原始失败日志保留，不覆盖。

协调者批准再最多两次同 `.28` 同计划；若再出现一次复位且同期正式默认没有复位，
停止重试，离线比较 `.27` 与 `.28` 启动路径并提出区分实验，不自行修改公共驱动。

## 当日跨内核启动统计（截至 r53 收尾）

分母是实际 Linux 启动，自动恢复启动也计入其实际内核；重复 collect/dmesg 不重复计数。
日志不覆盖整日，以下是已核实覆盖范围，带 ≥ 的数字是下界，不能据此计算全天故障率。
只凭 journal 缺 shutdown 不判复位；复位分子要求 UART 从运行内核直接回 ROM 的证据。

| 内核 | 已证实启动数 | 非请求冷复位 | 覆盖依据 |
|---|---:|---:|---|
| `.3` | ≥38 | ≥6 | 两次 journal 采样按 boot ID 去重补身份；a83、e1、prod90、deploy window-3/9/10 的 UART 各一次 |
| `20261105` 正式 | ≥8 | 0（已覆盖窗口） | deploy window-5/8/9/10/11 各一次；r52 恢复一次，r53 自动恢复与显式恢复各一次 |
| `.27` | 3 | 0 | r48、r49、r50 |
| `.28` | 3 | 2 | r51、r52、r53；r51/r53 复位 |
| `.90` | 3 | 0 | prod90、prod90-retest、paired90 |
| `.92` 调试 | 1 | 1 | pd-fifo-92 |
| `.93` 误带调试配置 | 1 | 1 | pd-fifo-93；不能合并到生产包统计 |
| `.93` 正确生产配置 | 2 | 0 | pd-fifo-93-corrected、pd-fifo-93-throughput |

原始 journal：`build/debug-splat-fixes/pd-audit/journal-summary.json` 与
`build/hwdecode-parity/boot-audit-complete.jsonl`，旧 34 boot 与新 36 boot 按 ID 去重。
新采样中 5 条无 Linux version，3 条由 deploy returned-boot-id 对应 `.3`，
1 条由 pd-fifo-93-corrected 身份对应 `.93`，剩余一条不强行归类。
`.3` 得到 38 个已确认 ID；新正式 journal 只确认 7 个，UART 覆盖 8 次，因此报告下界。
UART 同目录的 candidate-uart 是摘录，不另计；`.93` 两种配置必须拆开。
当日更早已滚出 journal 且不在上述窗口的启动未覆盖。

`.3` 的六次证据多于此前只读采样中的两次：新增 prod90 和三个部署窗口，不能沿用
旧 2/20 分母。部署阶段本身也有三次（window-3/9/10），不是两次；每处原始 UART
都保留 NUL→BL1，末条内核时间分别 5.214711、6.173414、5.447081 秒。
