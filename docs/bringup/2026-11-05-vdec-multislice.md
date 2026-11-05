# 2026-11-05：T7 H.264 多 slice 的 picture 生命周期

独立内核提交 `adadb95ff898ef7ef08d2e77e7947dcb3e61708f` 修正 T7 后续 slice
被显式拒绝的问题。离线检查和生产配置 `.26` 封包已完成；本记录暂不声称
实板像素通过。隔行支持按[已审设计](2026-11-05-vdec-interlaced-design.md)后续拆分。

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
