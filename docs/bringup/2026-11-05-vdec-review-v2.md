# 2026-11-05：hwdecode-parity-v2 内部评审系列

这是已提交解码系列的离线整理，供合入评审，不是上游投递材料，也不是部署许可。
旧 56 个提交压缩为 16 个独立构建的逻辑提交，保留原作者；未包含私有 HEVC 草稿。
原 `hwdecode-parity` 保持 `960132382e00864f4944aee077cd621927a97bb0` 不动。
基点为正式源码 `fd41fb5950b9da1fb336ce00d5137d27ee9755fa`。

## 系列与来源

VM 工作树 `/home/deepdream/src/linux-7.3-hwdecode-parity-v2`，分支
`hwdecode-parity-v2`，HEAD `f604008cda7e5d426311824f9a26683b7c5c57b4`，
tree `e0cfeece4a38ca8b8568993e30b92e2258fcccb5`。
逐提交 SHA、源码树、实测构建身份与结果见
[配套清单](data/2026-11-05-vdec-review-v2.csv)。
所有提交有整理者自己的 Signed-off-by；MPEG-2、JPEG、HEVC 保留
Christian Stefan Kövér-Draxl 原作者，正文列原仓库提交链接及后续集成改动。

| 序号 | 一句话说明 | 原系列归并范围 | QEMU KUnit |
|---|---|---|---:|
| 01 | 修正 T7 H.264 参数表、原生头部、canvas 和共享固件选择，加入真实函数 KUnit | 1–7、10–11、39–40、44–45；13 的共享基础部分提前 | 8 |
| 02 | 接入 stateless MPEG-2 请求、DMA 生命周期、codec reset 与首场状态 | 12–16、43；13 剩余部分 | 10 |
| 03 | 独立 stateful JPEG 节点、compose、字节序、DMA 与头部 KUnit | 17–22、41 | 12 |
| 04 | 先定义 HEVC domain、前后端时钟和 IRQ binding | 23、29、32 | 12 |
| 05 | 接入 stateful HEVC 队列、资源生命周期、EOS 和参数 KUnit | 24、26–28、30、33、35–38、42；44 的 HEVC 成员注释 | 17 |
| 06 | 再为 T7 DTS 接入上述 HEVC 资源 | 25、31、34 | 17 |
| 07 | 每队列 sequence、首次 CAPTURE 编号、HOLD 和错误回收 | 46、52 | 17 |
| 08 | 多 slice 共用同一 picture 的 canvas/MV 生命周期 | 47 | 17 |
| 09 | map-unit 尺寸先展开再做 frame 对齐 | 48 | 18 |
| 10 | 保存场参考元数据和 frame/top/bottom POC | 49 | 19 |
| 11 | 当前 picture 同样使用 stateless builder 的 POC | 50 | 20 |
| 12 | 按 frame/MBAFF/field 结构计算 colocated MV 地址 | 51 | 22 |
| 13 | canvas/MV 存储改用 timestamp 身份，保留 held IDR 首场槽位 | 53 | 23 |
| 14 | 逐参考项填充地址，组合原始布局与场视图 | 54 | 24 |
| 15 | 场 PicNum/LongTermPicNum 按奇偶与 wrap 处理 | 55 | 25 |
| 16 | 最后开放 field/MBAFF 入口及独立参考列表容量 | 56 | 25 |

原 8/9 是 scaling 参数改动及其完整 revert，净效果为空，删除这段演进历史。
资源探测、修复和接口转换合入相应最终实现，不保留临时中间态作为单独提交。
最终源码已有的实验门禁、诊断接口仍保留，未把“整理历史”误写成“生产就绪”。
驱动树没有 `test_*.py`；纯逻辑由实际 KUnit 覆盖，V4L2 与硬件生命周期仍依赖
compliance、实流和错误恢复记录，不重新引入 mock。

## 与旧最终树的有意差异

最终 `git diff 9601323 hwdecode-parity-v2` **不是空**，仅以下四个文件：

- `hevc.c`：去掉 `h265_config_pic_list()` 结束前的一行空白，清除合并补丁新暴露的
  strict checkpatch 提示。
- `aml_vdec_drv.h`：补格式/codec/queue 枚举及 JPEG/HEVC 节点、compose、
  HEVC CAPTURE 等待/锁成员的 kernel-doc，随各成员首次出现的提交一起加入。
- `aml_vdec_platform.h`：补 `num_fmts`、`has_internal_canvas` 描述。
- `h264.h`：将 `sps_flags2` 错名改为实际 `SPS_FLAGS2` 宏的 kernel-doc 标题。

没有代码逻辑、寄存器值、DT、Kconfig 或 UAPI 差异。逐文件补丁和词法比较
输出保存在 `build/hwdecode-parity/v2/intentional-tree-diff.patch`、
`tree-proof.json`；后者保留字符串/字符常量，去掉注释与空白后逐 token 相等。
这是辅助审查证据，不能代替构建或实板验证。

## 验证方法与例外

全部离线构建通过 `board-queue --heavy`，使用原任务 O= 目录，没有板票。
每个最终源码树重新执行模块和内建 `W=1 C=2`、有效 sparse，以及 arm64 QEMU
的实际 `amlogic-*` KUnit。各次完整输出在 `build/hwdecode-parity/v2/finalNN.*`；
配置、源码 commit/tree 对应于 `.identity`，QEMU 原文和 JSON 都保留。
提交正文修订只改 metadata，最终评审 commit 与实际构建 commit 逐树相等。

模块与 vdec 内建改动范围内没有新增编译/sparse 告警。内建构建都会带出范围外
`arch/arm64/kernel/vdso/vgetrandom.c` 的 `__kernel_getrandom` 未声明 sparse
告警，完整保留，不能宣称整个内核零告警。工具路径为
`/home/deepdream/build/hwdecode-parity-tools/sparse/sparse`，固定源码
`84ec0658c81db4ccc4aabc420d3dc118c2c6a310`；smatch 未安装，未运行。

逐提交对改动头文件实际跑 `scripts/kernel-doc -none`。首次发现的旧注释告警
保存在 `before-kernel-doc-fix/` 和 `kernel-doc-final-before.log`，补注释后全系列
重新构建/运行，不将旧结果冒充最终树验证。

`git format-patch` 输出逐项跑 `scripts/checkpatch.pl --strict`，原始结果保留。
**不宣称 checkpatch 全过**：02/03/05 缺原作者 Signed-off-by，保留 nominal-author
错误，不代签、不改作者。其原提交分别为 `b1bdea695746b`、`37b50c957b4b1`、
`0204da89aa08d`，上游前阻断项已登记 [issues](../issues.md)。
新增/删除文件的 `FILE_PATH_CHANGES` 提醒按既有
[人工路径审核规则](2026-11-05-vdec-kunit-results.md) 单独记录：MAINTAINERS 已覆盖
`drivers/media/platform/amlogic/vdec/` 与 T7 binding，不加重复条目。
另保存仅忽略该提醒的结果；其余 style error/warning/check 必须为零。

原始 strict 结果：12 个提交为 0/0/0；01 有一条已人工审核的路径提醒；
02/03/05 各有一条路径提醒和一条原作者 SoB 错误。仅排除路径提醒后，
13 个提交为 0/0/0，以下三个仍各有一个 error：

- 02 MPEG-2：`5952c3b3ab7f3`。
- 03 JPEG：`a01f357260a89`。
- 05 HEVC：`f11d9b5771141`。

最终再次执行 targeted `dt_binding_check`，并通过内核 `CHECK_DTBS=y` 的
同一 schema 校验路径重建/验证普通 VIM4 和 `vim4-vdec-test` 两个 DTB。
过滤项为 `media/amlogic,t7-vcodec-dec.yaml`，没有该 binding 的告警或错误；
不是全仓库所有板子的 schema 验收。原始命令在 `dtb-check.sh`，结果在
`final-dtb.log`；04 binding 中间提交也单独保存 `04-binding.log`。

逐提交头文件检查最终均无输出，原始日志为 `review-NN-kernel-doc.log`；
补丁与两种 checkpatch 原文为 `review-NN.patch`、
`review-NN-checkpatch-{raw,paths-audited}.log`。全系列所有 16 个源码树的
模块/内建构建及 QEMU 执行均已实际完成；最终 suite 为 25/25。

## 功能证据与未验边界

沿用 [H.264 全集原始记录](2026-11-05-vdec-avc-final.md) 的准确口径：
110/135 Success、20 Fail、5 Known unsupported，旧 58 条通过流无回退。
不把离线 KUnit 数相加当成独立硬件用例；中间提交没有重新上板。
三条已定位用户态限制是 CVFC1 crop 和 Sharp 两条尾 slice 未提交；Sharp 的
HOLD 有 STREAMOFF 收尾证据，没有实际 DECODER_CMD FLUSH 验证。

MPEG-2 未全过；HEVC 固件启动握手/出帧未解决；5.15 对照因厂商启动 hard-lockup
未完成。高阶格式、性能、KVM 共存与零告警调试内核验收未完成，不能宣称 5.15
parity。不能据生产配置像素证据声称锁/内存检查通过。
`.28` 冷复位仍待排除，见 [离线启动分析](2026-11-05-vdec-boot-diff.md)。
本轮没有部署、没有运行区分实验、没有对外发邮件或补丁。
