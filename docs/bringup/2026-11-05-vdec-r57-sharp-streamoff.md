# 2026-11-05：r57 Sharp STREAMOFF 与 AVC 续跑

`.28` 正常启动，stateless media/video compliance **8/0、60/0**。
index 95–126 为 **24 Success / 6 Fail / 1 Error / 1 Timeout**。
FM2_SVA_C 为 FMO 码流 Error，SP1_BT_A 为内核 Timeout；后者立即停止窗口并恢复。
合并 r54/r56 的唯一输入后 **103 Success / 21 Fail / 1 Error / 2 Timeout / 8 Not run**，
未运行仅 index 127–134，不把旧基线结果补进分母。

## Sharp ioctl 结论及边界

`logs/hwdecode-parity-r57/validation-fluster-1793911981661817000/results/` 保存
`vector-0120-ioctl.log`、`vector-0123-ioctl.log` 与各自 V4L2 trace/stats。
两条流的 OUTPUT/CAPTURE **VIDIOC_STREAMOFF 均返回 0**，没有 VIDIOC_DECODER_CMD。
V4L2 trace 的各 CPU overrun、commit overrun、dropped events 均为零。
之后同次启动继续通过 Sharp_MP_Field_2_B、Sharp_MP_Field_3_B 等码流，未出现
Sharp 拆流后设备不可用。用户态缺失末 slice 的结论同 [r54](2026-11-05-vdec-r54-sharp-trace.md)。

此证据覆盖用户态实际采用的 STREAMOFF 收尾；**没有执行 FLUSH，因此不把
HOLD+FLUSH 路径列为已验**。PAFF 的 Q/DQ 不对称仍按原始跟踪报告，不据返回 0
补造没有观察到的 CAPTURE DQBUF。驱动正确性结论限于已提交请求与已输出帧。

## 恢复与后续

新正式默认 release/build ID、2372 个保护文件全部相等；实际 H.265 4K
298 帧、59.57 fps，零新增 dropped/freeze/lost。635 个上传文件逐项归档、复核后删除。
证据在本轮 `returned-baseline-identity.json`、`returned-video.log` 和
`build/hwdecode-parity/run57/upload-cleanup.log`。
本轮候选及恢复均未冷复位；`.28` 累计 **7 次/2 次**，新正式下界 **12 次/0 次**。

协调者的新 known-unsupported 指令到达时本窗已执行，不中途修改载入计划。
后续明确把已核实 FMO 的 FM1_BT_B、FM1_FT_E、FM2_SVA_C 标为 Known unsupported，
保留之前实际 Fail/Error/Timeout 历史，不能改写成 Pass。ASO 仅在已核实不支持时列入，
不按文件名猜测；SVA_FM1_E 的 num_slice_groups_minus1=0，不误判成 FMO。

r58 使用最后一个获批启动额度：先 index 128–134，预先标记的 FMO 只输出跳过原因，
最后跑有历史超时的 sp2_bt_b（index 127）；其余 Timeout/内核错误停止条件不变。
已取得 Sharp ioctl 证据，不为重复采证占用剩余预算。
