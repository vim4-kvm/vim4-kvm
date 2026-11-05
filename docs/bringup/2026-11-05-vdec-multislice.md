# 2026-11-05：T7 H.264 多 slice 的 picture 生命周期

独立内核提交 `adadb95ff898ef7ef08d2e77e7947dcb3e61708f` 修正 T7 后续 slice
被显式拒绝的问题。生产配置 `.26` 实板复验：19 条多 slice 中 11 条转为通过、
7 条仍 Fail、1 条仍内核超时；3 条已通过的单 slice 对照全部通过。已恢复 `.3`
及视频并清理上传。隔行支持按[已审设计](2026-11-05-vdec-interlaced-design.md)后续拆分。

## 根因与修改

原 `.25` 对 `first_mb_in_slice != 0` 直接报错。简单删除检查会进入旧路径，
在 slice 之间释放 canvas、重新分配当前 picture 和 colocated MV。这会破坏
同一 picture 的 DMA 所有权。

`drivers/media/platform/amlogic/vdec/h264.c` 现在仅在首个 slice 分配当前 picture，
后续 slice 保留其 canvas/MV。每个 slice 从同一 request DPB 重建参考列表，
采用固件报告的 slice type 和重排命令；`h264_priv.h` 的 job bitmap 保证每个
内部 LUT 槽只编程一次，直到 worker 确认 DMA 停止后再释放。

正常完成和错误退出仍走现有停机路径，不新增私有 ABI、码流解析器或 mock 测试。
提交没有触碰 `hevc.c`；原 HEVC 草稿已恢复，diff SHA 仍为
`158cde0d2ef95e16117f4b1e889ae0405af390e4b63ae8fe2b13e4131b3d3f12`。

## 离线验证

原始输出目录为 `build/hwdecode-parity/multislice/`：

- `module.log`、`builtin.log`：W=1、C=1，有实际 `CHECK h264.c`；vdec 无诊断。
  内建前置 `arch/arm64/kernel/vdso/vgetrandom.c` 有 `__kernel_getrandom` 未声明的
  sparse 警告，不隐去也不算 vdec 的新回归。
- `kernel-doc.log`：修改头文件检查无诊断；smatch 未安装，未运行。
- `commit.patch`、`commit-checkpatch.log`：对 format-patch 运行 strict checkpatch，
  0 errors / 0 warnings / 0 checks。未改变 DT binding，无相关 schema 检查。

硬件生命周期没有用 Python/mock 伪造通过；以同批标准流、单 slice 对照和内核
日志证明。生产配置只证明功能/像素，不能代替零告警调试内核的锁/内存验收。

## 候选身份

复用 `vdec-sequence/kernel` 的 O=，候选工作树为已提交的上述 HEAD，没有 HEVC
草稿或调试片段。`candidate-build.log` 保存完整构建/封包输出，
`run47/artifact-identity.json` 与 `copy-artifacts.log` 保存 VM 原产物和 Mac 副本
的双端核验；传输后 fsync，再比较来源 SHA，不使用副本自身哈希冒充来源证明。

| 项目 | 实际值 |
|---|---|
| release | `7.3.1-vim4-20261105.26` |
| build ID | `cfef47ada4c4e84b5c3f81c57c38078ff700cdcc` |
| 正式配置 SHA-256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA-256 | `569241dd93533b2c3867b44f9bdad243a02d0e7055e524c44fef13704f6d3901` |
| manifest SHA-256 | `592e447b9bb27dd0ffa58a1d5ca7e972ba7bd179d85c58ec23a88394ef99dd07` |
| RAM archive SHA-256 | `8c96c00e59f996a15a2a14a9984825da553cc6c7ef0e0547c000247e74b86d07` |
| 完整包 SHA-256 | `2d1647d85ad89b875da879bec94ebd83da0717e5d7a4a27877abedcf52afd36a` |

实板使用整包中的原生模块。HEVC ACTION/reset 读回实验仅准备了独立差异文件，
没有纳入这个包，也没有据此提交或声称验证。

## 复验范围

从[原逐流 CSV](data/2026-11-05-vdec-conformance.csv)选择全部 19 条多 slice 输入。
先运行此前 18 条 Fail，再运行已通过的 AUD_MW_E、BA1_Sony_D、BA2_Sony_F，
最后运行此前发生内核超时的 FM1_FT_E。任意 Timeout/内核异常立即恢复；像素
Fail/普通 Error 逐流保留并继续。

其中 CAMASL3_Sony_B、CVFI1_Sony_D、CVFI2_Sony_H、CVNLFI1_Sony_C、CVNLFI2_Sony_H
同时带隔行 SPS，本次未开放隔行入口，不能承诺修复它们。FMO 与 cropping/长期
参考交叉项也按实际结果判定，不用多 slice 标签掩盖其他缺口。

`run47/selection.json` 保存顺序和旧结果；输入由宿主归档重新校验上传，不依赖
已清理的 r32 板端目录。窗口结束恢复 `.3`、核身份和视频，再归档清理本轮上传。

## r47 实板结果

[逐流 CSV](data/2026-11-05-vdec-multislice.csv) 保留旧结果、新结果、特性与原始
JSON 路径。本轮 22/22 均运行，合计 14 Success / 7 Fail / 1 Timeout，没有
Not run。3 条对照通过只能说明所选对照无回归，不能代替完整 135 条重新验收。
也不能把跨 `.25`/`.26` 的结果相加，称为 `.26` 全套通过数。

| 分类 | 数量 | 码流 |
|---|---:|---|
| 原 Fail → Success | 11 | BA1_FT_C、BASQP1_Sony_C、CABACI3_Sony_B、CABAST3_Sony_E、CABASTBR3_Sony_B、CI1_FT_B、MR1_BT_A、SL1_SVA_B、SVA_Base_B、SVA_CL1_E、SVA_FM1_E |
| 隔行交叉项仍 Fail | 5 | CAMASL3_Sony_B、CVFI1_Sony_D、CVFI2_Sony_H、CVNLFI1_Sony_C、CVNLFI2_Sony_H |
| cropping 交叉项仍 Fail | 1 | CVFC1_Sony_C |
| FMO 交叉项仍 Fail | 1 | FM1_BT_B |
| 仍内核超时 | 1 | FM1_FT_E |
| 原 Success → Success | 3 | AUD_MW_E、BA1_Sony_D、BA2_Sony_F |

最后的 FM1_FT_E 原始 Fluster JSON 仍是 Error，但内核在 12:46:07 报
`dec timeout=500`。新门禁立即记录 Timeout、终止窗口并恢复，没有继续解码。
`window-status.json` 正确为 `success=false`、`recovery_required=true`，不是整窗
通过；此前已完成的逐流结果保留。内核日志没有新增 BUG/WARNING/KASAN 特征，
但这是生产配置，不能据此声称做过 KASAN/lockdep 验收。

原始结果在 `logs/hwdecode-parity-r47/validation-fluster-1793882467351467000/results/`，
每个 followup 都保留 `results.json`、Fluster JSON、日志、逐流内核日志。主目录
保存候选身份、启动 UART、恢复身份及 `returned-video.log`。

本轮没有重跑带流 compliance，也没有运行 MPEG-2、HEVC 或其余 AVC 向量；
`.25` compliance 的历史结果不记作 `.26` 新通过。后续受影响的接口验证仍需补齐。
5.15 对照继续暂停，不能将未解决项归为厂商固件不支持。

恢复证明为 `WINDOW_FINISHED baseline restored=True`；五秒 3840×2160 H.265
视频新增 303 帧，约 60.57 fps，丢帧/冻结/丢包增量均零。666 个上传文件已在
Mac 归档、逐文件哈希核验、远端再次核验后删除。板票已释放；清理本任务 O=
及模块目录的对象文件，保留 Image、模块、归档和日志，见 `run47/object-cleanup.json`。
