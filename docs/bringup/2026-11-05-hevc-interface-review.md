# 2026-11-05：HEVC 接口与厂商固件参数模式核对

用户已决定继续标准 stateful HEVC；H.264/MPEG-2 使用 stateless，JPEG 独立节点。
每个节点遵守自己的 V4L2 模型，不添加私有用户态控制。stateful 节点不在内核
解析码流，只消费固件报告的信息并配置硬件、管理参考和显示缓冲。

已检查的 5.15 驱动呈现的是“压缩码流进入微码，解析参数经 RPM 回到主机”的
协议。**没有发现 T7 可用的、以主机提供完整解码参数替代微码头部解析的模式。**
这是公开源码接口范围内的结论，不证明二进制固件不存在未公开模式；没有新增
实板验证或逆向固件。VP9/AV1 后续接口选择据各自协议验证，不只依据共用 HEVC 核心。

## 源码证据

检查基于 common_drivers 的固定提交
`31619c527655514b4c89516ef609b6db1dd47db6`，工作树干净。
下表位置相对该仓库 `drivers/media_modules/frame_provider/decoder/`；行号用于
定位这次检查，维护时以函数/符号为准。

| 路径与位置 | 实际数据方向和含义 |
|---|---|
| `h265/vh265.c:12255`，`config_decode_mode()` | single、framebase、streambase、Dolby 双层模式；写入启动状态、mailbox 标志和 RPS set ID，没有完整主机参数注入模式 |
| `h265/vh265.c:11311`，`HEVC_SLICE_SEGMENT_DONE` 分支 | 从 `rpm_ptr` 读出 `hevc->param`，再配置图像；参数来自微码 |
| `h265/vh265.c:3081`，`get_rpm_param()` | `SEND_PARAM_WITH_REG` 分支读取 `RPM_CMD_REG`，等待有效位、取低位数据、写零确认；不是主机发送参数 |
| `vp9/vvp9.c:6967` 附近，`DECODE_MODE` 选择 | single、stream/framebase、low-latency、`NOHEAD`；未看到填入完整主机解析参数的接口 |
| `vp9/vvp9.c:9701`、`:9743`、`:9795` | 等 `VP9_HEAD_PARSER_DONE` 后读取 RPM 到 `vp9_param`；分阶段解码也是消费前端解析出的 RPM |
| `vav1/vav1.c:5487` 附近，`DECODE_MODE` 选择 | 和 VP9 类似的输入模式；不能凭 `NOHEAD` 名称认定绕过 OBU/frame header 解析 |
| `vav1/vav1.c:8562`，`load_param()` | 接受 sequence/frame header parser-done 状态，从 RPM 取参数；`:7044` 的寄存器调试方式也只是读回 |
| `utils/amvdec.c:497`，`optee_load_fw()` | 根据 codec/固件名称选择 HEVC/VP9/AV1 MMU 固件和执行核心；普通、swap、front/back 是加载路径，不是标准主机参数提交接口 |

secure 调用在 common_drivers 的 `drivers/tee/tee.c:624`，`tee_load_firmware()`
只传固件索引、核心与 swap 标志，没有每帧 SPS/PPS、DPB 或其他完整参数块地址。
固件类型见 `drivers/media_modules/common/firmware/firmware_type.c` 的对应枚举表。
HEVC 的 `h265_mmu` 加载分支保留默认核心选择；不能照搬其他 SoC 的加载参数。

`NOHEAD` 的全部微码语义无法仅凭主机源码证明；现有主机调用链没有因此改为写
RPM，也仍然等待解析完成事件。它不是已找到的 stateless 接口。
front/back 分离同样不能证明支持主机语法参数，后端接受前端产生的硬件状态与
接受标准用户态解码控制是两回事。

还核对了 `drivers/media_modules/amvdec_ports/decoder/`：
`vdec_hevc_if.c:278` 的 `parse_stream_ucode()` 直接投递码流，而 `:320` 的
`parse_stream_cpu()` 是厂商另一条获取流信息的路径；`:372`、`:384` 用
`param_sets_from_ucode` 选择它们。正常解码仍在 `:420`、`:499` 附近投递压缩
数据。该 CPU 解析选项不等于微码接受完整主机参数，7.3 stateful 不移植它。
VP9 的 `vdec_vp9_if.c:634` 和 AV1 的 `vdec_av1_if.c:986` 还有厂商前缀处理，
同样不能据此引入内核码流解析；如后续确认必须解析，会先报告。

## 当前实现与多格式草案

7.3 的 `hevc.c:h265_feed()` 复制输入并填充 DMA 缓冲，不解析输入语法；
NAL 类型来自固件 scratch 寄存器，几何、POC 和参考信息来自 RPM。
stateful 队列管理 SOURCE_CHANGE、参考图像、显示顺序和 EOS，符合
[stateful 接口的职责划分](https://docs.kernel.org/userspace-api/media/v4l/dev-decoder.html)。
采用这条路径的目的是匹配现有固件协议，并避免要求应用提供私有参考列表。

已保存并检查的
[多格式 HEVC 草案](https://lore.kernel.org/linux-media/20261025192507.210058-10-christian.koever-draxl@student.uibk.ac.at/)
采用 HEVC_SLICE，仍让微码解析码流；作者明确指出长参考处理所用的
`V4L2_CID_AML_HEVC_REFS` 不能作为可合入的用户态 ABI。其报告的长参考样例
也没有全部通过。这是该草案的限制，不能推导成所有 stateless 实现都需要私有控制，
也不能直接断言 T7 固件有相同缺陷。

可复用的是已审查的寄存器/RPM 定义、workspace/MMU、tile、scaling LUT、SAO、
参考图像配置及本分支的 T7 电源、时钟、IRQ 同步和有界停机。不能直接复用私有
控制、要求客户端改写码流的约定或将 Main10 舍入为八位的输出。

如果以后重新评估 stateless，必须实现标准 HEVC 控制与 Request 生命周期、
timestamp/DPB 到压缩参考图像的映射，以及固件输入适配，分别以 KUnit、带流
compliance 和标准码流验证。当前不进行这项重构。

## 验证与未完成项

EOS 修复 `8c94ee343220cebc8f208097daf2308fd5a04c76` 已提交并推送。
历史实板结果为三个节点接口 compliance 各 47/47、零警告；HEVC 首个码流超时，
输出零帧。因此只确认订阅接口修复，带流 EOS 尚未通过。固定版本、原始输出与
恢复情况见 [记录](2026-11-05-hevc-stateful.md)，不能用本次源码核对代替实板成功。

本次核对的原始检索输出保存到
`build/hwdecode-parity/vendor-hevc-parameter-search.log`，代码摘录另存同目录
`vendor-hevc-parameter-evidence.log`；文档检查输出为
`repo-tests-hevc-interface-review.log`。没有新增 KUnit、fluster 或固件模式实测。
首帧超时、多切片、长参考、Main10 和长期共存仍待验证。

后续先按任务顺序迁移驱动测试、完成静态检查与调试配置，再准备一致性和性能
验收。每个改动提交前明确验证方法，实际运行并保存原始输出才标记已验证。
Linux 规范用于实现与验证；短期不投稿，不准备投稿材料，不向外发送邮件或补丁。
