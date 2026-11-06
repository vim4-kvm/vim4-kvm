# 7.3 解码驱动架构方向

协调者把关，worker 实现。适用于 `drivers/media/platform/amlogic/vdec/`。
依据：主线 `3cbab82167a1`／第二轮 `d177f0dc1ca4` 源码，2026-11-06 审查。

## 现状问题

1. **stateful 用标志嫁接在 stateless 核心上。** `aml_vdec.c` 有 31 处
   `is_hevc`/`is_jpeg` 分支，覆盖控件、格式、事件订阅、vb2 回调、m2m 回调、request 支持。
   每加一个 stateful 编解码器，核心文件就要多一批分支。
2. **通用上下文混入 HEVC 私有状态。** `struct aml_vdec_ctx` 里的 `hevc_lock`、
   `hevc_wait_capture`、`hevc_min_capture` 只有 HEVC 使用。
3. **任务模型只描述 stateless 单帧任务。** `aml_codec_ops` 的 init/exit/prepare/run/finish
   对应一次请求一帧。HEVC 在 `device_run` 开头直接跳到 `aml_hevc_device_run`，
   没有走核心的硬件占有、缓冲 pin、故障处理路径，而是自己另写一套。
4. **`hevc.c` 2000 多行，混着三层逻辑。** V4L2 stateful 协议（drain、EOS、
   SOURCE_CHANGE、LAST）、DPB 逻辑（POC、RPS、长期参考、随机访问、参考列表、输出选择）、
   硬件编程（寄存器、固件命令握手、IRQ 线程）都在同一个文件里。
   KUnit 只能靠 `VISIBLE_IF_KUNIT` 逐个导出函数来测。
5. **硬件结构按编解码器堆字段。** `struct aml_vdec_hw` 里 HEVC 的时钟、电源、IRQ、
   固件 swap 字段和 VDEC1 的字段并列，没有按硬件核心分开。
6. **生产驱动里留着 bring-up 钩子。** `hevc_test`、`hevc_core_test` 两个 sysfs 属性。

## 目标结构

- **按节点类型分接口层。**
  - `aml_vdec_stateless.c`：H.264、MPEG-2，走 request。
  - `aml_vdec_stateful.c`：HEVC、JPEG。
  - 每类节点各有自己的 ioctl/vb2/m2m ops 和控件、格式表，`open` 时按节点选用。
  - `aml_vdec.c` 只保留共享部分：格式查找、缓冲 pin、硬件占有。
  - 核心代码里不再出现编解码器名字的分支。
- **stateful 协议只实现一次。**
  - drain、EOS、LAST、SOURCE_CHANGE 的发布顺序放在 stateful 层（54b6ba1b 的顺序是基准）。
  - 编解码器只通过回调接入：送入一个 OUTPUT、取一张可显示帧、冲刷、格式变化。
  - HEVC 和 JPEG 共用这一层。
- **上下文分层。** 通用 ctx 只放 V4L2 和队列状态。
  编解码器私有状态全部放进 `codec_priv` 指向的结构，锁也随私有状态走。
- **硬件占有只走一条路径。** 拿 pin、置 `curr_ctx`、开时钟、复位、加载固件、
  停止/故障、放 pin，合成一组 acquire/release。stateless 和 stateful 都调用它。
- **HEVC 拆成三个文件。**
  - `hevc_dpb.c`：纯逻辑，无 MMIO、无 vb2。KUnit 直接链接测试，不用逐个导出。
  - `hevc_hw.c`：寄存器、固件命令、IRQ。
  - `hevc.c`：对接 stateful 层的胶水。
- **硬件按核心组织。** 每个硬件核心（VDEC1、HEVC 前后端）一个结构，
  各自持有时钟、电源、IRQ、固件状态。
- **bring-up 钩子移出生产路径。** 改为 debugfs，或者直接删除。

## 规则

- **新代码放进对的层。**
  - 不在核心加 `is_<codec>` 分支。
  - DPB 逻辑不碰 MMIO。
  - 协议顺序只改 stateful 层，不在单个编解码器里绕过。
- **重构不改行为，并且要单独可验证。**
  - 不和功能修复混在同一个提交里，每步都能单独二分。
  - 验收看同一套输入：
    - HEVC 132 条的逐帧 MD5 和重构前完全相同；
    - H.264、MPEG-2、JPEG 已有的一致性结果相同；
    - KUnit 和 v4l2-compliance 不退步。
- **时机。**
  - 重构排在 .38 合入主线并部署之后，不打乱正在跑的验收。
  - 剩下的 HEVC 失败等重构完成后，在新结构上修。
- **审查。** worker 的系列除了查正确性，还要过结构审查。
  需要结构性修复的问题，用特例绕过的补丁一律退回。
