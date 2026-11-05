# 2026-11-05：解码缓冲序号修复与复验

修复 r34 带流 compliance 在第二个 OUTPUT buffer 发现的序号不递增问题。
独立提交已完成离线检查；`.25` 实板复验 stateless、JPEG 各 60/60，原序号错误
消失。HEVC 等待 SOURCE_CHANGE 失败，Fluster 未启动；已恢复 `.3` 与视频。生产配置结果
只用于接口、功能和像素，不能替代调试内核的锁、DMA 与内存验收。

## 根因与实现

失败证据见[生产配置窗口](2026-11-05-vdec-production-validation.md#实板结果)。
锁定 `v4l2-test-buffers.cpp:415` 检查每个已出队缓冲的 sequence 递增，ERROR
缓冲也不豁免。通用完成路径原来直接返回缓冲而未设置 sequence。

读源码核对同一内核树的上游 Hantro 模式：`verisilicon/hantro_drv.c` 的
`hantro_job_finish_no_pm()` 在完成前递增 OUTPUT/CAPTURE 各自计数；
`hantro_v4l2.c` 的 `hantro_start_streaming()` 按队列清零，`hantro_buf_queue()`
为空 LAST 缓冲编号。摘录保存于 `build/hwdecode-parity/sequence-fix/upstream-pattern.log`。

`hwdecode-parity` 提交 `e7729c116550210c002c8ebf5de330df550dba0d`：

- `aml_vdec_drv.h` 给每个 m2m 上下文保存两队列计数；`aml_vdec.c` 对应队列
  STREAMON 清零，通过共同完成函数在 DONE/ERROR 前为源和目标缓冲编号。
- JPEG 复用共同完成函数，空 LAST 缓冲也使用 CAPTURE 计数。
- HEVC OUTPUT 在真正完成源缓冲时递增，保留 source-change AU 时不提前递增。
  CAPTURE 继续使用原有显示顺序的 `h->sequence`，补上空 LAST 缓冲编号；
  从 QBUF 返回空 LAST 时沿用 `hevc_lock` 保护同一个计数，没有新建一套 HEVC
  CAPTURE 序号。

HEVC 握手草稿先单独 stash，提交后恢复；四个提交文件中 `hevc.c` 只有序号相关
改动，草稿 hunk 与 r34 完全一致，仅基准 blob ID 改变。原 stash
`64a7b5c598b8f1844050737bf87a42667acab16a` 及差异留作本地证据。
提交正文说明根因、修法、已运行的离线验证和待跑的带流 compliance，并带
Signed-off-by。没有改写既有提交，也没有新增 KUnit、Python 或 mock 测试。

## 离线验证与候选

原始日志目录 `build/hwdecode-parity/sequence-fix/`：

| 检查 | 结果 |
|---|---|
| `git format-patch -1` → strict checkpatch | `commit-style.log`：0 error/warning/check；检查包含正文与签名 |
| W=1/C=1 模块 | `module.log`：实际 CHECK 修改文件，生成 `.ko`，vdec 无诊断 |
| W=1/C=1 内建 | `builtin.log`：实际 CHECK 修改文件，生成 built-in.a，vdec 无诊断；前置 arm64 vgetrandom 仍有既有 sparse 声明警告 |
| kernel-doc | `api.log` 无输出；`before.log`/`after.log` 的既有成员/枚举文档警告相同，新增计数字段没有新警告；不声称整个头文件零诊断 |
| 草稿隔离 | `isolation.log`、`restore-draft.log`、`hevc-handshake.diff`；提交后仅 HEVC 握手草稿保持未提交 |

未安装 smatch，未运行。未改 DT binding/DTS，不新增 schema 检查。此修复是
V4L2 缓冲生命周期语义，离线构建不证明实际出队顺序；以相同带流 compliance
复验为硬件证据。

候选独立树 `vdec-sequence`，源码为上述提交，tree
`dff51679830b739f3683d3fa0a2caf6a052e9a0d`。私有锁
`build/hwdecode-parity/sources-vdec-sequence.toml` 固定正式配置 SHA-256
`7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`。
完整包从干净树生成，再应用原 HEVC 草稿构建匹配私有模块。按 r34 相同顺序和
输入检查三个节点，再运行首条 HEVC，成功后才继续同一子集；首错停止，恢复 `.3`。

构建、封包、私有模块 W=1/C=1 sparse 及 RAM 包全量校验已完成，日志为
`build/hwdecode-parity/sequence-build.log`、`sequence-package.log`，以及
`run35/prepare.log`、`run35/artifact-sha256.json`。配置与正式文件逐字节一致。

| 产物 | 身份 |
|---|---|
| release | `7.3.1-vim4-20261105.25` |
| Image build ID | `915bf903142f874b6f7836568eb89332d8d782be` |
| Image SHA-256 | `85e7e76ab0c5283cdbab57a43413780b194c0b8b90af704be93d5f2b53435f10` |
| 完整包 SHA-256 | `b40e86719570b782f33f29eba8de5b18c6832999ae90890b42c6a8d1ab5d5947` |
| RAM 包 SHA-256 | `628951ac4a4e73857afc7fce778e5ac7609822f52937d74584c4f6fff79ba791` |
| manifest SHA-256 | `7bce2b7e1e1fd120ec55f20c9774964822944089cad55e30f02b21d6614ad744` |
| 私有模块 build ID | `4c47a41e143ef0d8dac8524365c863b15fb5a525` |
| 私有模块 SHA-256 | `85a83e1fe278e1d09cb3cb5371ce32f956e4d76051379b4880092a6025458b7c` |
| 草稿 diff SHA-256 | `158cde0d2ef95e16117f4b1e889ae0405af390e4b63ae8fe2b13e4131b3d3f12` |

## 实板结果

首轮 r35 已结束并恢复 `.3`，原 `v4l2-test-buffers.cpp:415` 序号错误消失。
原命令 `-d /dev/video1 -s 17 -m /dev/media0` 实际先检查 media，再遍历其全部
视频节点：media 8/8，stateless `/dev/video1` 60/60，JPEG `/dev/video2` 60/60，
均零失败、零警告，包含多轮 REQBUFS/CREATE_BUFS、no poll/select/epoll 的缓冲
往返。它们不是有效像素证明：此时没有传入 JPEG 文件，stateless 也有缺 codec
controls 后返回 ERROR 缓冲的日志。

随后工具提前到达 HEVC `/dev/video3`，还没有设置 HEVC 文件输入，等待
SOURCE_CHANGE 一秒超时，报 `v4l2-test-buffers.cpp:1738: ret == 0`。
不能把这一项当作 `AMP_A_Samsung_7` 解码失败。最外层工具将整条命令记为
stateless 项失败；原始逐设备总结保留在
`logs/hwdecode-parity-r35/validation-fluster-1793871321535554000/results/compliance/stateless-compliance.log`。
Fluster 未启动。

离线核对锁定 v4l-utils 的参数处理与 `testNode()`：`-m` 改变主设备并递归访问
其他节点；`-M` 只做 media 测试；`-d` 使用 video 的 bus info 自动打开 Request
API 所需 media fd。已将工具改为独立 media-only 命令与逐视频节点带流命令，并
要求每条命令恰好返回所请求设备的一个总结。工具离线回归 537 项、11 跳过，见
`build/hwdecode-parity/run35/tool-fix-tests.log`。不修改测试工具源码或放宽失败判定。

r35 恢复后 `.3` build ID 与 2,370 个证明文件一致，3840×2160 H.265 约五秒
增加 299 帧、59.76 fps，新增丢帧/冻结/丢包均为零。最后候选内核日志没有
BUG/WARNING/KASAN/Call trace，但生产配置不证明锁/内存检查通过。
`returned-baseline-identity.json`、`returned-video.log` 及完整候选 UART 均在
`logs/hwdecode-parity-r35/`。已释放板锁，没有失败后重载或现场重试。

### r36 基线门禁与 r37 有效复验

r36 在候选启动前因基线应用身份不匹配退出，没有切换内核。只读检查发现
One-KVM 启动曾报 SQLite `disk I/O error`；根分区余量约 404 MB，未发现
文件系统或 MMC I/O 错误。没有删除数据库/WAL、修改配置或重启服务，后续观察
服务自行恢复 active；原因未确定。原始检查保存在 `build/hwdecode-parity/run36/`
的 `application-state.log`、`disk-state.log`、`sqlite-*.log`。

r37 重新通过完整基线证明与实际视频门禁，按 FIFO 复用逐文件校验的同一 `.25`
RAM 包。修正后的独立命令实际结果：

| 项目 | 结果 |
|---|---|
| media-only | 8/8，零失败、零警告 |
| stateless | 60/60，零失败、零警告；ERROR 缓冲往返证明序号语义，不证明标准流像素 |
| JPEG | 配置已有 MJPEG 输入，60/60，零失败、零警告；未做独立像素校验 |
| HEVC | 已配置 AMP_A_Samsung_7 输入，等待 SOURCE_CHANGE 一秒超时，`v4l2-test-buffers.cpp:1738`；进程退出 1，无最终总结 |
| Fluster HEVC/H.264/MPEG-2 子集 | 全部未运行；compliance 首错停止 |

HEVC 内核日志同时记录 `timeout, irq_status 00 status 00 pc 00000a1e shift
00000072`。与 r35 不同，这次输入配置和设备调用顺序正确；但尚不能归因为固件
能力限制，握手/启动路径仍需离线定位，HEVC 序号改动尚未获得实际出队验证。
原始记录在 `logs/hwdecode-parity-r37/validation-fluster-1793872378975281000/`，
包含各节点 compliance 日志、逐项 `results.json`、内核日志与窗口状态；完整 UART
及恢复证明位于 `logs/hwdecode-parity-r37/`。

结束后 `.3` 身份与基线文件校验通过，浏览器 3840×2160 H.265 五秒约 60.38 fps，
新增丢帧、冻结、丢包均为零。`WINDOW_FINISHED baseline restored=True`，板锁已释放。
没有失败后重载/重试。生产配置日志不替代未来零告警调试内核的锁与内存验收；
5.15 同板标准流对照、完整一致性与性能验收仍未运行。

最终主仓库离线回归实际运行 537 项，11 项跳过，其余通过；原始输出为
`build/hwdecode-parity/run37/main-tests-final.log`。`git diff --check` 通过。
