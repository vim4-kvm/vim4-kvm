# r4离线移植与验证

本轮无上板、板票据、候选启动或MCP；所有编译/重负载经Mac共享队列heavy执行，
kbase sampling期间等待。没有修改其它会话工作树或VM内核，不推送二进制/blob。

## 已完成

- [pt1完整候选](passthrough-73-pt1.md)：新release、Image/DT/2338模块与SHA清单封存，
  基于uhd4源码，默认锁不变。只打包不部署；GPU选择可在该profile之后单独覆写。
- 自动跟随入口：V4L2 SOURCE_CHANGE订阅/DQEVENT，DRM uevent、连接/EDID指纹去重，
  旧generation停止分发，等待实际reader退休才重开采集池。重复相同sink事件不触发blank。
  新输入通过QUERY_DV_TIMINGS/S_FMT取真实尺寸；约500ms采样率进入7次中值、±0.005Hz滞回、
  2秒稳定资格，与5.15黑屏修复规则一致。输出选择实际sink模式，先TEST_ONLY再提交；
  故障不每轮重设TX，只在新事件后重试。未完成真实设备端到端验证。
- HDR：偏好与实际像素域分离。现有HDR2→709 NV12不能重新贴PQ标签。
  新可选RX status/VDIN hdr_status读回检查活动lease、pending、硬件HDR ctrl与重复RX快照，
  资格满足才给出output.hdrToSdr。它不是LUT内容/光学验证，也不是原生HDR输出实现。
  诊断文件依赖是临时适配，后续应收敛到逐帧V4L2元数据；manager继续unsupported。
- ALSA：AlsaPump实际调用ASoC PCM打开、配置、读取/写入，复用5.15已审阅的通用PCM类，
  不调用厂商mixer。仅RX句柄recover，TX继续静音/forward，不因RX xrun重prepare。
  `null`→`null`真实libasound测试通过，无物理音频播放。远程Opus分发队列已存在，
  远程音频IPC/应用输入与ELD/动态速率协调尚未接通；不能与应用重复独占RX。
- 共享GStreamer `vim4brokersrc`：仅开broker socket；SCM_RIGHTS导入DMA fd，
  GstMemory最终引用释放才ACK，保留generation，停止源时在途内存仍持socket。
  输入率经control.sock读取，未知返回0，不猜60。仅原尺寸SDR NV12；不静默回退另开VDIN。
- NanoKVM与uStreamer独立`passthrough-73`分支开始接入：显式设置VIM4_BROKER_SOCKET才选新source，
  5.15不变。NanoKVM common Go测试通过；uStreamer VIM4核心构建通过。
  已推送NanoKVM `0ec2754`、uStreamer `6af1a66`，均为独立passthrough-73分支。
  JetKVM未开始；三款应用完整音频/模式恢复及硬件编码共存仍待验证。

## 测试证据与边界

原始日志均在本worktree忽略目录`logs/passthrough-73/`：

- `pt1-build.log`、`pt1-seal.log`、`pt1-fixtures-final.log`：完整构建与7个host C fixture。
  strict源差分检查忽略通用FILE_PATH_CHANGES提醒后0 error/warning/check；历史提交正文提醒保留。
  无QEMU，KUnit未运行。
- `compile-fixture-r4-final.log`：设备/GStreamer共享库ARM64 `-Wall -Wextra -Werror`通过；
  真GStreamer + 真Unix seqpacket/SCM_RIGHTS + 最终内存释放ACK及输入率查询通过。
  图像内存来自普通文件，不是VDIN DMA，也没有KMS硬件退休。
- `unittest-r4-final.log`：主仓377项、16跳过，其余通过；`linux-r4-final.log`：
  Linux透传32项、1跳过，其余通过，另有上述GStreamer真实传输测试通过。
  `alsa-null-r4.log`：libasound null端点采播/Opus待取队列通过，不输出到硬件。
- `nanokvm-r4-final.log`：`go test -tags vim4 ./common`通过。
  `ustreamer-r4-validated.log`：干净构建WITH_VIM4=1、无Janus/可选Python扩展通过。
  完整组合尝试缺Python3.14与Janus SDK头文件，未称完整PiKVM打包通过。
- `onekvm-r4-full.log`：换用已含ffmpeg/avenc_aac的现有package-builder环境，
  原两项集成失败已消除；全套817通过、4忽略，没有改测试绕过。
- `virtual-devices-r4.log`、`loopback-r4.log`：VM当前7.2.12 OrbStack没有vkms、vivid或v4l2loopback模块，
  加载/查询失败，没有video/DRM虚拟节点；未能运行采集→IPC→KMS→退休设备端到端。
  7.3候选模块不能加载到该7.2内核，故没有通过混装模块绕过。

虚拟设备集成仍需要具备匹配vkms与vivid/loopback的测试内核或独立QEMU环境；
它也只能验证软件队列/IOCTL/IPC/通用KMS边界，不能证明T7的额外扫描周期reader fence、
VCBUS/时钟/CMA、真实HDR2与声卡时钟共存。当前阻塞是测试环境，不是sink。

后续优先补虚拟设备端到端、远程音频接口、HDR/ELD协调与JetKVM；
真实帧节奏/颜色/退休与四应用切换继续保留在[未来上板门禁](passthrough-73-offline.md#将来上板门禁当前禁止执行)。
本轮不宣称P0通过或可部署。
