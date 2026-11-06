# 2026-11-06：MR3 旧 timestamp 命中与 picture 槽归属

离线核对支持 [r63](2026-11-06-vdec-r63-gap.md) 的剩余首错假设：CAPTURE缓冲的
copied timestamp可以比驱动picture槽活得更久。topic `vdec-avc-residual` 的独立提交
`d444ab83f7fab8044eea48902b17310763bb7a04` 在dfd3af9之上补充槽位检查和诊断。
离线验证已完成，**未上板、未部署，不将MR3的历史Fail改成Success**。

## 时间线与证据层次

控制来自同组官方parser/private v4l2codecs的既有visl FRAME采证；缓冲时间线来自r63
真实ioctl日志。一次性 `build/hwdecode-parity/mr3-storage/timeline.py` 只提取原始记录，
`timeline.json`保存输入SHA、每请求ts0 DPB项、CAPTURE事件及行号，不模拟驱动。

| 时点 | 实际证据 | 对存储归属的含义 |
|---|---|---|
| decode0 | CAPTURE index0首次QBUF在ioctl行741，DQBUF行751返回ts=0 | 首图的真实timestamp0必须仍可正常使用 |
| decode1/2 | visl DPB含真实frame_num0、ts0的VALID/ACTIVE项 | picture槽仍被DPB引用 |
| decode3..8 | visl不再有ACTIVE ts0项 | 按驱动实际prune函数，该槽应回收；这一步没有板端函数trace |
| decode9/10 | visl有7个ts0占位项，frame_num9..15、POC0、VALID/ACTIVE | 它们不是原IDR，也没有对应解码请求/独立图像存储 |
| decode10、12..22 | r63两队列返回12对ERROR | 与原IDR缓冲尚未重新使用的时间段吻合 |
| decode23 | index0第二次QBUF行982，随后DQBUF行994返回ts=23µs | 此前index0没有重新排队；复用后不再出现本组ERROR |

visl reference_ts单位为ns，ioctl显示µs；编号n对应n×1000ns，两种表示不能直接混比。
decode9为I片，虽已有缺口DPB，尚不建立P参考列表，因此首个ERROR是decode10。

源码核对（本topic树）：`videobuf2-v4l2.c:vb2_find_buffer` 只检查copied_timestamp
与timestamp，不要求缓冲仍在驱动队列中。`videobuf2-core.c:__vb2_dqbuf`及其
`__init_vb2_v4l2_buffer`回调不清copied_timestamp/timestamp；后者只重置request_fd。
因此出队后尚未复用的index0仍可被ts0查找命中。新的KUnit直接调用实际prune与查找
逻辑，证明槽位回收后“buffer存在”不足以证明该picture仍拥有存储。

以上串起了控制值、缓冲生命周期和源码行为；**没有捕获r63时vb2_find_buffer的实际
返回指针或h264_config_decode_spec的失败出口**。诊断确认仍留到下一窗口，不把推导
写成已经观察到的函数返回值。

## 修改及可观察性

VALID DPB项满足“vb2不存在 **或** timestamp不在已占用canvas表中”即标为无存储，
在prune/当前图分配之前完成判定。真实ts0有槽位时仍是正常参考；槽位被其他timestamp
复用不能恢复旧picture的身份。沿用上个提交的占位列表位置、当前dst canvas、无独立
MV/canvas分配、无独立释放策略。

V4L2 DPB没有non-existing标志，不能准确区分所有合法缺口和驱动意外丢槽。
每次回退都dev_dbg记录DPB索引、timestamp、vb2是否命中、canvas查询结果、DPB flags
和SPS是否允许gap。即使不是缺口，也不会从诊断中隐藏；不对用户可控DPB触发WARN_ONCE。
`h264_config_decode_spec`当前图槽分配、参考槽解析、最终vb2查找三个失败出口分别记录
timestamp、队列内参考位置和返回码，不改变原错误返回。
L1[0]占位直接拒绝的已知限制保持不变，详见r63。

## 已运行验证

- `check.module.log`、`check.builtin.log`：模块/内建W=1及C=2有效sparse CHECK；
  驱动目录无告警。内建树外vdso/vgetrandom既有缺声明告警仍单列，不称全树零告警。
- `check.kunit.json`、`check.qemu.log`：27/27 arm64 QEMU KUnit通过。
  新例retired_picture_timestamp覆盖真实ts0、槽回收但成功buffer查找、槽复用及
  有槽但buffer缺失。buffer_present是纯逻辑输入，不构造mock vb2，不冒充实际查找测试。
- `check.format-patch.log`：strict checkpatch 0 errors/0 warnings/0 checks；
  `check.kernel-doc.log`无输出。未修改DT/binding，不适用dt_binding_check。
- PATH未找到smatch，未运行；本次无新板端记录，未运行compliance或像素复测。
- 主仓库全套检查588项完成、11项跳过，原始输出为 `main-tests.log`。

上述原始输出均在 `build/hwdecode-parity/mr3-storage/`。
后续按[存储归属验证计划](2026-11-06-vdec-mr3-storage-plan.md)完成
[r64](2026-11-06-vdec-r64-storage.md)：MR3/4/5各300帧逐字节正确，10条全部通过；
真实buffer命中但canvas缺失的路径已捕获，正式默认恢复，未部署。
