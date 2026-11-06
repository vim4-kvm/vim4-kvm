# 2026-11-05：MR3/4/5 缺口参考与 ERROR 缓冲定位

离线定位到 frame_num gap 的无缓冲 DPB 项使驱动提前返回 ERROR；不是只凭整文件
MD5 推测 LTR 寄存器错误。topic `vdec-avc-residual` 在 `c99c3ed` 上的独立修复为
`0096602bed208f6da17e46fb6b84c5a26f953186`。构建/KUnit/静态检查已运行，
**修复后像素未上板验证**；不修改 [r61](2026-11-05-vdec-r61-parser-ab.md) 的 Fail。

## 首错与 MMCO

索引均从零起。JM 19.0 在 init_slice、DPB MMCO、write_picture 和两条单向运动补偿
路径只增加日志；三条流均只有 I/P slice。各300帧与 FFmpeg 参考完整逐字节相等。
输入沿用 visl/r61 的已锁定码流。证据在 `build/hwdecode-parity/ltr/`：
`jm19.0.zip`、`jm-audit.patch`、`audit-sha256.json`、各流 `jm.log`/`decoded.yuv`、
`jm-mc-build.log`、`jm-mc-run.log`、`audit-summary.json`。JM 来自
`https://iphome.hhi.de/suehring/tml/download/jm19.0.zip`；旧源码链接需 `-fcommon`，
首次失败保留在 `jm-build.log`，不算通过。

| 流 | 首错显示索引 → 解码索引 / frame_num / POC | 首个 CAPTURE ERROR 解码索引 / frame_num / POC | ERROR 总数 |
|---|---|---|---:|
| MR3 | 10 → 10 / 17 / 34 | 10 / 17 / 34 | 221 |
| MR4 | 16 → 26 / 17 / 2 | 24 / 15 / 21 | 156 |
| MR5 | 16 → 26 / 17 / 2 | 24 / 15 / 21 | 156 |

ERROR 是 r61 官方组 ioctl 原始日志的 `VIDIOC_DQBUF` flags，不是新跑板结果。
MR4/5 显示16所对应的解码26引用解码25、24；后二者已先返回 ERROR，因此不能
把显示16或 ffprobe coded_picture_number 当作首个错误请求。

- MR3：decode3 的 MMCO4(maxplus1=1)、MMCO3(diff=1,idx=0) 后，decode4
  MMCO2 删除 LT0；decode7 重建 LT0/1；decode8 MMCO4(maxplus1=3) 与
  MMCO3(diff=5,idx=2) 将 fn2 设为 LT2。decode9 为非IDR I，fn8→16，
  产生 fn9..15 缺口，再以 MMCO4(maxplus1=4)、MMCO3(diff=9,idx=3) 将 fn6
  设为 LT3。首错前 max_long_term_frame_idx=3。decode10 的最终 L0 前八项为
  fn3、fn5(LT0)、fn16、fn7、fn8、fn2(LT2)、fn6(LT3)、fn4(LT1)，其后为缺口项。
- MR4/5：decode9/12/13 用 MMCO4/3 设置、清除、重建 LT0；decode14 MMCO5
  重置 frame_num/POC。decode19 MMCO4(maxplus1=1)、MMCO3(diff=3,idx=0)，
  decode20 MMCO4(maxplus1=0) 再清空长期参考。decode23 非IDR I 从 fn8 跳到14；
  首错 decode24 的 max_long_term_frame_idx=-1，最终 L0 为真实 fn14 与缺口
  fn13/12/10。此时无 LTR，不能把本次首错归因于 LTR 位或 MMCO5 本身。
- 三条首错之前均未出现 MMCO6；首个 IDR 的 long_term_reference_flag=0。
  完整逐操作参数（包含后续 MMCO）保留在 JM 日志，不用会覆盖重复字段的字典重演。

JM 实际单向预测调用分别为 44402、55951、55951 次，non_existing 引用均 **0**。
active 列表保留占位项是合法的；宏块实际引用和“出现在列表中”是两种计数。

## 与厂商及主线的差异

厂商源码锁为 common_drivers `31619c527655514b4c89516ef609b6db1dd47db6`，
以下文件均在 `drivers/media_modules/frame_provider/decoder/h264_multi/`：

| 路径 | 厂商 5.15 | 本驱动及结论 |
|---|---|---|
| MMCO / gap DPB | `h264_dpb.c:860` 的 fill_frame_num_gap 将 non_existing 的 buf_spec/colocated index 设为-1；该函数在本树未找到调用者，不能据它声称厂商实测支持 | stateless 由用户态提供 DPB；visl 确认缺口项 VALID/ACTIVE、timestamp=0，无对应解码请求 |
| LTR 寄存器 | `vmh264.c:4546` 和 get_long_term_flag_by_buf_spec_num 按场设置 info0[4:5] | 逐行参考设置两位，三条流无场差异；本修复不改这些位 |
| 列表下发 | `vmh264.c:4612` 起按 listX 次序写 canvas_pos 与 frame/field bits；错误检查可能拒绝无 buf_spec 项 | 本驱动重排前对整个初始列表强制绑定 buffer，缺口项使其提前返回-EINVAL；必须保留位置，不能压缩列表 |
| 缺失缓冲 | 主线 `verisilicon/hantro_h264.c:hantro_h264_get_ref_buf` 使用当前 dst 地址回退 | 本修复采用相同策略；缺口不分配 canvas/MV，不参与旧槽保留或真实 POC/MV 选择 |

固件不能看到尚未成功配置的参考列表，不能把 ERROR 之后的像素错误描述成已证明的
固件 LTR 算法缺陷。厂商实际像素对照仍未运行。

## 修复与验证边界

每个请求用实际 `vb2_find_buffer` 结果形成缺失 DPB 位图，绝不以 timestamp==0
判断缺口。prune 和 canvas 元数据查询排除这些项；重排仍保留 DPB 身份、PicNum、位置。
占位项借当前输出 canvas，不配置/释放独立 canvas，也不分配 MV。若 L1[0] 为占位项，
在读取其 POC/MV 前 dev_dbg 并返回错误。日志分开记录占位列表项与 colocated 选择；
宏块 ref_idx 的计数来自 JM，不冒充板端固件内部跟踪。

`check.module.log`、`check.builtin.log`：模块/内建 W=1、C=2 有效 sparse CHECK 已运行；
改动目录无告警。内建日志有树外既有 vdso/vgetrandom 缺声明 sparse 告警，不说全树零告警。
`check.kunit.json`/`check.qemu.log`：26/26，通过的新增用例覆盖 timestamp 0 的真实
槽位、缺失缓冲的槽位释放、占位地址与重排身份。KUnit 在纯逻辑边界输入查找结果位图，
不模拟 vb2；实际硬件队列查找留给实板。`check.format-patch.log`：strict checkpatch
0 errors/0 warnings/0 checks；header kernel-doc 无输出。构建后仅调整函数续行缩进。
无 DT/binding 修改，不适用 dt_binding_check。
主仓库全套离线检查588项完成、11项跳过，输出保存在 `ltr/main-tests.log`。

修复后另用已有 FRAME/ANNEXB visl 镜像复跑三条，目录
`build/hwdecode-parity/avc-residual/visl/mr-gap-recheck/`：每条300请求、进程0、
trace零丢失，全部控制内容与之前官方 Ubuntu 组相同。插件哈希已保存；visl 镜像没有
重建，也不执行 Amlogic 硬件路径，此项只复核输入序列，不证明修复正确。

下一步仅提交 [实板计划](2026-11-05-vdec-gap-validation-plan.md) 待批准，不排票、不部署。
