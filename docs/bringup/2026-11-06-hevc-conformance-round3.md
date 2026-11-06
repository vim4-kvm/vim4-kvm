# 2026-11-06：HEVC 第三轮裁剪与序列结束

离线候选，尚未上板。基于 `hevc-conformance-fixes` 的
`d177f0dc1ca40a33dadee38f95c08fa332236f69`，追加两项修复，尖端
`ab07ae47f79db163676b9a7a9b81d4db871964cb`。不修改其它失败流的推断规则。
架构规则已读取主 checkout 的 `docs/vdec-architecture.md`；本工作树尚无此文件。
本轮不提交主仓库、不 push、不合并、不占板。

## 已确认的两处差异

厂商路径均为只读 `common_drivers/drivers/media_modules/frame_provider/decoder_v4l/h265/vh265.c`。
对照增量见 [CSV](2026-11-06-hevc-conformance-round3.csv)。
基线步骤统计：相同 2、不同 1、缺失 2、待证 0；此统计不表示板上像素已验证。

| 提交 | 改动及依据 |
|---|---|
| `b54ff9b766e3efd851262c39085dad6198e7633a` | 无效 RPM 裁剪回退整幅；厂商 :5785–5815 的正常解码路径，区别于 :2155–2200 的 CSD 校验。 |
| `ab07ae47f79db163676b9a7a9b81d4db871964cb` | EOS 冲刷待输出图、使旧 POC/参考失效并重启随机访问；厂商 :11681–11708、:3878–3887。 |

SLIST_B/D 的实测 crop 为 `1:1/24576/0/120`、`1:1/57344/0/120`，
而 SPS 实际无裁剪。移除参数校验中的裁剪拒绝；尺寸、色度、位深及其它校验保留。
新 `hevc_dpb.c:h265_display_crop()` 统一计算可见区域，有效裁剪继续生效，
任何一维被裁空则四边全部回退。格式协商缓存同一结果到 `h->crop` 和 `ctx->compose`，
selection 读取缓存；coded CAPTURE 的对齐尺寸不受可见区域裁剪影响。

EOS 的新 `h265_end_sequence()` 是纯 DPB 操作，不访问 MMIO 或调用 vb2。
它先为待输出图保存显示 POC、标记无条件 bump，再清除所有旧参考 POC、ST/LT 标记，
复位当前 POC 和随机访问门限。重复 EOS 不覆盖已保存的显示 POC。
IRQ 仅调用该函数并继续原握手；待硬件停止后，原有工作线程按 epoch/显示 POC 输出。
输出完成清除 flush 标记，槽位仍按原有 output/reference 所有权复用。
码流 EOS 不新增 V4L2 EOS 事件或 LAST；drain、SOURCE_CHANGE 和缓冲完成顺序未改。

没有 EOS 时 flush 标记始终为 false，输出仍按原 epoch/POC 与逐图 reorder_limit 选择。
RPS 构造、LT 解析、连续 CRA、RASL 判定均未改；已有连续 CRA/RPS_B 用例继续通过。
这证明相应纯逻辑回归通过，不能代替 RPS_B/RPS_E 的板上像素复验。

## 离线门禁

- heavy 正式 FIFO **1527**，票 `7e730cd36a134a67a8c14309d02389f7` 已 released；
  固定上述尖端，源码与 index 干净，复用自有 O= 的 `kunit/`、`module/`。
- arm64 QEMU KUnit **44/44 PASS**：原 39 项及新增 5 项全部通过。
  新用例直接链接驱动，不添加新的测试符号导出。
- W=1 模块构建成功；五个既存 KUnit 模块缺 `MODULE_DESCRIPTION()` 的 modpost 告警仍在，
  无新增编译告警。模块 SHA256：
  `59f224ad00045bf9202d8e41eca86627432e2191f35dcda4effbc042d4776f94`。
- 逐提交完整 patch 的 strict checkpatch：裁剪提交 **0 errors / 1 warning / 0 checks**，
  EOS 提交 **0/0/0**。唯一提醒为新增文件是否需更新 MAINTAINERS；
  `MAINTAINERS:1503–1511` 的既有 `F: drivers/media/platform/amlogic/vdec/` 已覆盖新文件，
  不添加重复规则、不屏蔽原始提醒。正文按 75 列换行，既有完整 SoB 不拆；diff --check 通过。
- 主仓库全套测试本轮 **607 项 OK，14 项跳过**，原始输出
  `logs/hevc-conformance-round3/repo-tests.log`；主仓库 diff --check 通过。

KUnit 覆盖有效裁剪、两份实测无效偏移与裁空边界、旧 ST/LT 不再匹配、
重排门限之下仍全部有序输出、重复 EOS、新 CRA 的 POC 复用及 RASL_N/R 跳过。
新纯逻辑与测试位于 `hevc_dpb.c`、`hevc_dpb_kunit.c`，未做全驱动重构或核心 codec 分支修改。

复现入口：VM `/home/deepdream/build/hevc-conformance-fixes/round3/validate.sh`，
固定尖端后执行 arm64 QEMU KUnit 与 W=1 模块构建。
Mac 的 `build/hevc-conformance-round3/` 保存脚本、两份 patch、strict 原始输出/退出码、
validated-head、source.sha256、QEMU/JSON、构建日志、模块哈希及票据；
`logs/hevc-conformance-round3/` 保存 heavy 与主仓库测试输出。

## 给 integration 的定向判据

1. SLIST_B/D：不再因裁剪偏移报 invalid RPM；selection 为完整 832×480，
   保持 CAPTURE coded 对齐容量；输出帧数、逐帧 MD5 与原参考相同。
2. RAP_B：EOS 前待输出图按序全部交付；EOS 后旧 POC 不再匹配，
   新 CRA 所需跳过的 RASL 不触发 invalid reference lists；整流逐帧 MD5 匹配。
3. 回归 .38 已通过的 RPS_B、RPS_E 及原六条代表流、全 I、三条 P/B 短流；
   逐帧 MD5 不变、零 ERROR、EOS status 0；compliance 保持 56/56。
4. 任一逐帧错位、重复/丢图、invalid RPM/reference、超时、ERROR、EOS 非零或 compliance 下降判失败；
   保留逐流 kernel.log、ioctl/事件时序、帧数与 MD5 对照，不扩大板窗或现场猜改寄存器。

未运行板验与 compliance；不宣称两条 SLIST 或 RAP_B 已修复出像素。
VPSSPSPPS、输出标志/bumping、两条 timeout 均未改，等协调者后续任务。
