# 2026-11-06：HEVC 主线整理系列

九个提交基于含 quiet-power 的 `32624d39cab888ef2428efdac64fa0bacc2954e6`，
位于 VM `/home/deepdream/src/linux-7.3-vdec-hevc-port` 的 `vdec-hevc-mainline`。
尖端 `f7b59cb34cd63d6c4b5469bde747a628abdd413f`；未 push、合并或上板。
旧 `experiment/hevc-vendor-port` 保留在 `d593d7a4`。

基线已包含 HEVC 核心、stateful 节点、绑定、DTS 和 KUnit，其中
`bafe82e461f49` 保留 Christian Stefan Kövér-Draxl 作者字段，不重复导入。
本系列仅重组未合入的启动及出帧修复；新提交保留原修改作者及整理者自己的签署。
原作者缺 SoB、整理者非真实姓名的问题仍按 [issue](../issues.md) 保留，
不能据本轮 checkpatch 通过称整个祖先历史已满足上游 DCO。

## 系列及旧提交映射

| 新提交 | 内容 | 原提交 |
|---|---|---|
| `98bf1bb469fb4f3e433c8b6781c61872846343cb` | T7 workspace/CFG3 尺寸 | f21dfc47 |
| `652ae4d38766c92e292b93d0687c4d333d647880` | 输入环 END/WP 及 FIFO 顺序 | 452a8cc8 |
| `3994a4cc88ead936906aa71e5d2640082e3aaf39` | 输入、协议、命令与 CPU 启动顺序 | 5f7ed4f7、f065c671、6c8560da，含 857 的复位读回 |
| `884dd59ffeb9568d20520e9955d9595993390a95` | picture table 后恢复压缩头/MMU 配置 | 8823d08b |
| `11261479d7f7c81b00d7cf74cc87458a05cd364c` | T7 SAO/DBLK 控制 | 82b68a02 |
| `b91b408272408f84ff3052c31744d7c60ff1297a` | SEI 应答及参数错误终止 | aadc70fb |
| `b1100e079815ef6f5f48fccd09b0f104d4a7bac8` | secure swap 固件选择与 SCRATCH8 生命周期 | 2a622cf6，日志移至末提交 |
| `dfdc1c8055ccc4fc790b40d8aed2931c498c7476` | HEVC DYN_RESOLUTION 能力声明 | d593d7a4 |
| `f7b59cb34cd63d6c4b5469bde747a628abdd413f` | 独立保留启动/超时、输入、IRQ 及固件诊断 | 5f7ed4f7、857b5a2e、2a622cf6 的诊断部分 |

857b5a2e 的手动 NAL 与 d9c85c7e 的自动模式恢复不作为往返提交保留；
最终始终使用自动搜索。运行顺序相关的 WAIT_FLAG、ACTION_DONE、复位读回放在同一提交，
没有为整理而新增状态机或硬件行为。每个行为提交写明动机、厂商 file:line 和 r72/r73
证据边界；厂商路径明确区分实际 `decoder_v4l/h265` 与对照 `decoder/h265`。
提交正文按 75 列换行，既有完整 Signed-off-by 行不拆行。

## 与已验收源码的限定比较

比较脚本与输出位于 `build/vdec-hevc-port/mainline/compare.py`、`equivalence.json`。
参照为 r73/.35 `67f95220173d8efc84866f4dc1d2c5c344ecbb1e`。
检查 `drivers/media/platform/amlogic/vdec/` 下八个路径：

- `aml_vdec.c`、`aml_vdec_hw.h`、`hevc.h`、`hevc_regs.h`、`hevc_priv.h`、
  `hevc_kunit.c`：逐字节相同。
- `hevc.c`：仅删 `before-reset`、`after-reset`、`header-reply` 三次完整诊断快照。
  复位前后三次功能性读回均保留；after-start、timeout 快照仍在。
- `aml_vdec_hw.c`：仅三条 secure load/fallback/overlay 信息改为 dev_dbg，
  及相应参数缩进。SMC 参数、返回值处理、地址保存恢复不变。

比较不是空白忽略后泛化判断，而是显式允许上述六处诊断变化后逐字节比对；结果通过。
原始 `vs-r73.diff`、`vs-d593.diff` 保存在同一目录。
相对 d593d7a4，shared 文件另含基线 quiet-power 的日志降级及失败时上下文补充；
.35 同样包含它们。基线到本系列只改六个上述驱动文件，未重写 AVC/MPEG-2。

## 验证与交付边界

九个完整 format-patch 逐提交运行 `checkpatch.pl --strict`，全部返回 0，
各为 0 errors / 0 warnings / 0 checks；`git diff --check` 通过。
原始 patch、日志、`checkpatch-status.tsv`、`series.txt` 位于
`build/vdec-hevc-port/mainline/`，VM 同名报告目录在构建根下。

实际 GStreamer 1.24.2 C 消费路径的 [EOS 离线 fixture](../../packaging/kernel/test_gstreamer_hevc_eos.py)
对新尖端通过：初始 SOURCE_CHANGE 在 CAPTURE 前消费，最终 LAST 终止；
运行中 DRC 重建后仍能正常 EOS。它不模拟 DMA，也不替代整条 pipeline 上板。

VM `/home/deepdream/build/vdec-hevc-port/validate.sh` 已固定上述尖端并检查工作树干净，
先跑 EOS fixture，再沿用独立 `kunit`、`module` O= 目录跑 arm64 QEMU `amlogic-*`
和 W=1 模块构建。Mac 副本为 `build/vdec-hevc-port/validate.sh`，语法检查通过。
协调者已经队列代跑 heavy，输出在构建根 `mainline/`：fixture PASS、QEMU KUnit 29/29、
W=1 模块无新增诊断（仅既有五个 KUnit 模块缺 MODULE_DESCRIPTION 的 modpost 警告），
模块 SHA256 `a95a511465af9f58d5808368d10644d9952eb05d3a9913c24b2ca332ad0ba17d`。
随后协调者把 `f7b59cb34cd63` 快进为内核主线 `origin/vim4-kvm-7.3`，未部署。

硬件依据是历史 r72/r73：全 I 样本首 AU 98304 字节，整帧和 Y/U/V 与参考逐字节相同；
r73 streaming 56/56，Captured 1 frames; status 0，初始事件先于 CAPTURE，
CAPTURE 只 STREAMON 一次。原记录为主仓库提交 `74833db` 的
`docs/bringup/2026-11-06-vdec-r73-eos.md`；本轮没有重新运行板验，
不能把这些历史结果称为重组尖端已验收。未扩展多实例、DV、10bit、secure 视频或长流能力。
