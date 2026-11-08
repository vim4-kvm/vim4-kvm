# 2026-11-05：独立格式 Fluster 与 HEVC 启动顺序核对

`.25` 的 H.264 子集 1/2 通过，MPEG-2 子集 0/2 通过（1 失败、1 未运行），
均为像素对照失败而非超时。两个独立窗口首错退出，均恢复 `.3` 与 4K 视频。
清理已归档的本任务上传后释放约 295 MiB。HEVC 没有上板或改代码：找到草稿
无条件启用厂商 8K 专用解析模式的具体差异，仍是待验证假设。

## 窗口与身份

复用序号修复记录中的 `.25` Image、
配置与匹配私有模块，未重新构建或变更草稿。内核提交 `e7729c116550`，正式配置，
Image build ID `915bf903142f874b6f7836568eb89332d8d782be`。不打开 HEVC 节点；
stateless/JPEG compliance 使用上一窗口同一产物的记录，不重复计为本轮运行。

`build/hwdecode-parity/run38/validation-plan.json` 只选择 H.264，成功才继续 MPEG-2；
H.264 失败后先恢复并释放板锁，再用 `run39/validation-plan.json` 独立选择 MPEG-2。
沿用 `vdec-window.py fluster`、逐流 30 秒、manifest、watchdog 和恢复流程，
每个窗口持 FIFO 票，目标/租约 15 分钟；没有失败后现场重载或换 codec 继续。
CPU 保持 performance，未调整节能、音频、HID、MMC、DMA debug 或 PWM。

输入和 Fluster 版本沿用标准准备；
每个窗口实际执行 `list -c`，可用解码器分别为 `GStreamer-H.264-V4L2SL` 与
`GStreamer-MPEG2_VIDEO-V4L2SL`，MPEG-2 参考解码器也通过可用性检查。
板上没有下载码流。

## 实际结果

| 套件 | 本轮计划通过/总数 | 逐流结果 | 全套未运行 |
|---|---|---|---|
| JVT-AVC_V1 | 1/2 | AUD_MW_E：Success；BA1_FT_C：Fail | 133/135 |
| MPEG2_VIDEO-MAIN | 0/2 | att：Fail；mcp10ccett：Not run，首错停止 | 42/43 |
| JVT-FR-EXT High、MPEG-2 422、HEVC | 未运行 | 不在这两个独立窗口范围 | 全部 |

本轮没有 Timeout。H.264 `BA1_FT_C` 的标准摘要为
`4f2da01d1d1ae7b99bea3fe1fb9e8ef4`，实际为
`ee5cfa38a011aa6f9aa57eb78d43ed6c`；MPEG-2 `att` 在 ISO 参考像素比较中报告
23,959 个超出容差的位置。二者均正常进入结果比较，不能把进程完成写成像素正确。
根因仍待定位，当前不能区分驱动、插件控制/布局转换或固件差异。

原始 JSON、逐流日志、可用解码器列表与内核日志：

- `logs/hwdecode-parity-r38/validation-fluster-1793873128774762000/results/`。
- `logs/hwdecode-parity-r39/` 下的 `validation-fluster-*/results/`。

原始 `results.json` 保留整个套件的 Not run 状态，不将未执行项算失败或通过。
恢复后的 `.3` build ID 和基线证明匹配；r38 五秒新增 300 帧、59.99 fps，r39
新增 298 帧、59.58 fps，均为 3840×2160 H.265，新增丢帧/冻结/丢包均为零。
两轮 `WINDOW_FINISHED baseline restored=True`，恢复身份和视频原始输出位于各自
日志根目录。候选日志未发现 BUG/WARNING/KASAN/Call trace；生产配置不证明锁和
内存检查通过。

5.15 对照未运行：两次候选均触发首错停止，未链式切到厂商内核；另外尚无本轮
已核验的 `5.15.137-vim4kvm-hdrdual6` 一次性启动产物清单与运行身份 manifest，
`vendor-boot-plan.py` 仅能离线生成配置，不能替代这些门禁。不能据本轮认定
7.3 比 5.15 差的具体项目，更没有固件/私有 ABI 无法达到的结论。

## 本任务旧上传清理与 SQLite

r38 在候选启动前只读盘点 `/var/tmp/hwdecode-standard-r*`：r32 约 599 MiB，
r33/r34/r35/r37 合计约 14 MiB。保留 r32 在用的工具、码流与 manifest，只删除
其三个重复上传包；逐包与宿主 `run32/archives.json` 和实际归档 SHA-256 比较。
其余四个旧目录先流式归档到 Mac，再核对归档与远端逐文件 SHA-256，删除前重新
核对一次；不允许符号链接、特殊文件或挂载点。没有碰其他任务和应用数据。

可用空间从 420,339,712 增至 729,370,624 字节；新增候选日志会再占少量空间。
证据在 `build/hwdecode-parity/run38/cleanup.log`、`disk-before.log`、
`disk-after.log`，完整旧目录备份为 `archived-r{33,34,35,37}.tar` 和同名 JSON。

此前 r36 One-KVM 的 SQLite `disk I/O error` 原因仍未解释。本轮基线和恢复视频
正常，所收近期服务日志未再出现该错误，但不足以证明低余量就是原因或清理已修复。
登记为独立 issue；没有删除数据库、WAL/SHM 或修改应用配置。

## HEVC 离线差异表

厂商源码为 `common_drivers` 提交 `31619c527655514b4c89516ef609b6db1dd47db6`，
工作树干净。下表厂商路径以 `drivers/media_modules/frame_provider/decoder/` 为根；
也核对 `decoder_v4l/h265/vh265.c` 的相应 `run()`/`config_decode_mode()`。
主线路径以 `drivers/media/platform/amlogic/vdec/` 为根，基于 e7729c116550 加
原有未提交草稿。原始摘录带行号/源码哈希保存在 `run38/hevc-startup-source-evidence.log`
与 `hevc-hardware-source-evidence.log`，草稿未修改或提交。

| 阶段 | 厂商 5.15 | 当前草稿 | 判定 |
|---|---|---|---|
| reset / 输入 / 固件顺序 | `vh265.c:14098` reset → `vdec_prepare_input` → WAIT_FLAG → loadmc → prot_init | `aml_vdec_hw.c:1328` stop/reset/load → enable_irq → `hevc.c:1543` prot_init → feed | 输入指针在固件加载前后的位置不同；待验证，不能仅凭顺序判错 |
| 固件选择 | `vh265.c:12484,14211` 按固件版本与 enable_swap 选择 hevc_mmu_swap 或 h265_mmu，并缓存 swap 地址 | `aml_vdec_hw.c:1350` 固定 SMC format 17（HEVC_MMU），无 swap 分支 | 厂商存在非 swap 支持路径；需实际确认本板厂商选择，不能假定必须 swap |
| WAIT_FLAG | `vh265.c:14152` 新 AU 为 0，续传使用 invalid 字节数 | `hevc.c:412` 新 AU 为 0 | 与新 AU 分支相同；续传不在本轮首 AU 范围 |
| mailbox / Linux IRQ | `vh265.c:12325` 清 MBOX0、mask=1，启动前建立回调 | `aml_vdec_hw.c:1363` 先 mask/clear、安装回调并 enable_irq；`hevc.c:413` clear/mask=1 | 均在 MPSR 启动前完成；irq_status=0 不能单独证明 IRQ 路由有错 |
| DECODE_MODE | `vh265.c:12258` framebase=1，加 start_decoding_flag 与 MBX0 bit31，MODE2=rps_set_id | `hevc.c:390` 相同 | 首 AU 对应 0x80000001 |
| NAL_SEARCH_CTL bit21 | `vh265.c:11511,12262` 只有有效且超过 4K 的尺寸才设置 performance_profile；分配时 memset 为 0 | `hevc.c:396` 每次无条件置 bit21 | 明确差异：2560×1600 首 AU 不满足厂商条件，优先验证假设 |
| stream 指针 / padding | `utils/vdec.c:1983` END=base+size；WP 向下对齐 8 字节，padding=16 KiB | `hevc.c:430` 相同 END/对齐/padding，额外留一 FIFO 字空间 | 草稿已对齐这一协议；本轮未更改 |
| stream enable | `utils/vdec.c:2312` endian=7、FIFO bit29、CONTROL bit0 | `hevc.c:458` 同字段；在 prot_init 后写指针并启动 FIFO | 字段相同，输入与 prot_init 的先后不同 |
| 首个 ACTION 与 CPU 启动 | `vh265.c:14268` ACTION_DONE=0xff → SHIFT/DECODE_SIZE → `amhevc_start`；后者在 CPU reset 前后各读三次 reset 寄存器，然后 MPSR=1 | `hevc.c:1551` CPU reset → clear mailbox → ACTION_DONE → CPSR=0 → MPSR=1，没有读回 | 可独立核对的启动顺序差异，不与 bit21 一次混改 |
| DECODE_COUNT | 厂商仅 is_vcpu_clk_set 时写；T7 capability 未设置该标志 | 当前未写 | 不将其他 SoC 分支误当 T7 缺项 |

### 可验证假设与边界

优先假设：首 AU 错开 bit21 的微码多 slice 模式，改变头部处理/通知行为。
厂商 V4L2 路径也在 `decoder_v4l/h265/vh265.c:12107,12729` 施加相同尺寸条件，
不是单实例与 V4L2 两套驱动的偶然差别。下一次实验应只改变该模式条件，保持
输入、固件与其他寄存器顺序不变，以 SOURCE_CHANGE、第一条 IRQ/RPM 和标准流
像素结果验证；失败则保留原始状态，不能将此推断写成修复。

另一个候选假设是 ACTION/CPU reset 顺序与缺少 reset 读回；应在排除 bit21 后
独立验证，不能一起修改导致无法归因。固件选择则先从厂商运行日志确认是否
使用 swap，不能盲改 SMC 编号。

r37 `pc=0xa1e, irq/status=0` 没有对应微码符号，不能精确解释 PC。SHIFT=0x72
表明字节计数非零；宿主只读检查锁定输入首 AU 为 155,498 字节，含 VPS/SPS/PPS
和 type 19 slice，并非只有头部的空 AU。证据为 `run38/hevc-first-au.json`。
这支持继续查早期解析/握手，但不证明已经正确解析头部。没有在内核新增码流解析。

## 交付检查

最终主仓库离线回归实际运行 537 项、11 跳过，其余通过，日志为
`build/hwdecode-parity/run39/main-tests-final.log`；`git diff --check` 通过。
本轮只提交记录和 issue，不新增测试或改变驱动。窗口后再次核对 HEVC 草稿 diff
SHA-256 为 `158cde0d2ef95e16117f4b1e889ae0405af390e4b63ae8fe2b13e4131b3d3f12`，
与 `.25` 使用的草稿相同。
