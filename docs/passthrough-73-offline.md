# 7.3透传：离线移植合同与验证

后续进度及当前测试边界见[r4](passthrough-73-r4.md)与[pt1封存](passthrough-73-pt1.md)。

2026-10-31用户调整：本轮及后续另行通知前，禁止上板、板票据、候选启动与MCP。
只用共用队列heavy票据编译/重负载；不依赖sink，不遍历VM的Mac挂载目录。
此前[r2现场记录](bringup/2026-10-31-passthrough73-r2.md)保留历史，不代表本轮进行了硬件测试。
架构决定仍按[计划](passthrough-73-plan.md#r2-架构决定独立常驻采集与分发服务)。

## 组件边界

- 内核：基于uhd4的独立`passthrough-73`分支增加明确的passthrough DT profile，
  引用既有M3-video定义，避免复制46组资源和TX声卡路由。保持M0/default锁不变。
  VD1 reader fence/额外扫描周期退休、ASoC TX/hdmi-codec ELD、HDR2 split VCBUS均复用现有源码。
  不通过新私有ioctl/sysfs做自动路由，不引入vendor blob。
- 独立broker：唯一V4L2抓帧所有者；池仅分配一次、EXPBUF一次，完整DQBUF后分发。
  KMS提交和应用退订均不构成可QBUF证明，必须等真实读者退休。
- IPC：Unix seqpacket携JSON版本/代号/布局，SCM_RIGHTS传DMA fd；应用回报仅表示不再使用，
  服务仍须检查DMA reader fence。断连保留在途租约，不能立即复用物理页。
- One-KVM：独立子worktree基于`db848a52`；显式`VIM4_BROKER_SOCKET`才启用AppSrc接入。
  DMA GstMemory的最终释放回报租约，Wave5 plane view仍保留父缓冲。
  第一版仅原尺寸NV12/709 limited；缩放/HDR原生路径须后续专项接入，不能回退抢开VDIN。
- 音频：RX唯一PCM所有者向TX及远程Opus分发，短时无源保持TX静音连续；
  ALSA EPIPE/ESTRPIPE原句柄recover，播放端不能因RX xrun重新prepare。
- manager：7.3使用broker状态/偏好控制，5.15沿用原provider；GET只读，hdr是偏好，
  output.hdrToSdr必须来自实际处理状态。UI不变。

## 后续应用接入顺序

1. One-KVM原尺寸Wave5输入先接；确认Appsink/ParentBufferMeta/encoder引用全释放后才ACK。
2. NanoKVM与JetKVM：共用GStreamer source协议，替换7.3 V4L2输入，不动5.15。
3. PiKVM/uStreamer：C客户端接相同seqpacket协议，编码结束回报lease；停推流仅退订。
4. 各应用音频输入改接音频所有者；本地TX不随远程音频客户端退出。

## 将来上板门禁（当前禁止执行）

- RAM身份/模块匹配、native probe、无sink disconnected与TX声卡枚举；5.15默认保护与回退。
- H.265真实4K60、原始ERROR buffer与三高度帧号、CPU/CMA/taint/oops增量，区别平均fps和帧节奏。
- 有sink后再验颜色、60fps地址锁存、READ退休/fault pin、源变化及HPD；不靠OUT_FENCE锁存事件QBUF。
- 四应用/零远程客户端/应用切换保持本地帧号推进；慢客户端不耗尽采集工作槽。
- HDR偏好与像素域/InfoFrame一致，RX/TX同时RUNNING、xrun不重启TX；不做听感测试。
- 性能与同条件5.15对比，光学延迟无设备时保留未验；每段稳定性≤10分钟。

## r3验证与保留边界

- 主仓最终370项测试，16项按宿主环境跳过，其余通过。
  Linux容器25项透传测试全部通过：含实际seqpacket/SCM_RIGHTS、受控ioctl执行生产C函数、
  ERROR buffer不自动归还、失败STREAMOFF保留运行状态及跨代租约。
- devices.c以Linux ARM64 `-Wall -Wextra -Werror` 构建共享库通过。
  内核新profile独立cpp/dtc编译、7个已有fixture通过；checkpatch 0 error，
  1条新增文件的MAINTAINERS提醒，未掩盖为零warning。没有内核C改动，未重建Image/模块；KUnit未运行。
- manager前端构建（源码/UI未改）、Python全套、Go全套与vet通过。7.3仅连接control.sock，
  不进入厂商watch/prepare/audio-watch；请求与实际状态保持分离。
  Python为226项、12跳过；独立子分支`passthrough-73@2e1a168`已推送。
- One-KVM前端构建、Rust编译与新GstMemory最终引用释放测试通过；首轮全套815通过、
  4忽略、2失败，失败为容器缺ffmpeg与avenc_aac。补依赖的网络更新未完成，已终止该临时容器，
  不改测试来绕过失败。原日志保留于`logs/passthrough-73/onekvm-r3-tests.log`。
  定向Wave5/采集测试14通过、1忽略，独立子分支`passthrough-73@1a9b3a76`已推送。
  内核分支`passthrough-73@a62fa298a57e8`已推送，
  [profile补丁](../packaging/kernel-edge/passthrough-profile.patch)随主仓保存。
- 未运行v4l2loopback/vkms设备集成或真DMA/GPU；没有上板、板票据、候选启动和MCP。

服务已拼接唯一采集、IPC、原子平面提交与reader fence轮询，但尚未完成自动热插拔/源变化、
完整HDR偏好执行/映射事实读回、ALSA设备适配及其余三款应用接入。manager保持unsupported，
不会把这些离线成果描述成P0通过或可直接部署的产品。下一步先补这些适配与设备集成测试；
未来上板仍须另行授权。
