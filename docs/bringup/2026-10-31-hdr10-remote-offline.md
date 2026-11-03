# 2026-10-31：7.3 原生远程 HDR 离线调查

本轮无上板、无HID/声音/ptrace/重启/刷机；未改其他HDR2、GPU、kbase工作树。
结论：P0仍未完成。r1/r2为以下历史调查快照；r3已按用户确认实现AMLY→Vulkan→P010、
RX标准HDR10读取控件、用户态SEI与One-KVM能力探测，验证进度见文末。
设计、缺口、分阶段门禁和30分钟清单见[原生HDR10设计](../hdr10-remote-73.md)。

## 固定源码与缺口

内核起点是fetch得到的 `origin/vim4-hdr2-uhd4`：`ce6bc0cc5218a49ab49390d5008652ecf2cbb3dc`，
新分支 `vim4-hdr10-remote`，工作树 `/home/deepdream/src/linux-7.3-hdr10-remote`。
正式HDR2合入后再rebase，不合正式。
候选提交 [`6c7af142e52a7`](https://github.com/vim4-kvm/linux/commit/6c7af142e52a7)，
分支[vim4-hdr10-remote](https://github.com/vim4-kvm/linux/tree/vim4-hdr10-remote)。
以下行号针对调查时版本，主仓起点 `14cc2b2`；子仓均只读。

| 层 | 5.15证据 / 7.3缺口（file:line） |
|---|---|
| VDIN DMA | common_drivers `31619c527`：`drivers/media/vin/tvin/vdin/vdin_canvas.c:167`，full_pack按width×5/2，非full_pack另有布局；`:189`按canvas_align补行。`vdin_ctl.c:5055`设置MIF十位模式。不能只按bitdepth决定布局 |
| VFM发布 | 同版本 `drivers/media/vfm_cap/vfm_cap.c:503`区分AMLY与位深，`:598`发布色彩、`:1813`发布PQ与range。metadata_version=1在`:67`说明的是位深/色彩/stride合同，并非完整HDR SEI接口 |
| 解包 | gst-plugin-vfmcap `a4937400`：`src/amly.h:44`定义连续Cb/Y0/Cr/Y1十位槽，`:51`转P010并平均两行色度；`src/gstvfmcapsrc.c:176`将AMLY转换输出为P010，`:263`传PQ/BT.2020；`src/amly-gpu.c:488`使用实际输入/输出stride及尺寸 |
| 厂商编码 | gst-plugin-venc `b3b82a98`：`hdr/gstvim4hevc10.c:102`检测P010，`:131`传img_format/internal_bit_depth，`:138`设置VUI，`:279`扩展DMA API的pitch按字节；`hdr/p010-cpu-input.patch:20`修CPU字节交换。该插件未见mastering/CLL传入，不能据5.15网页PQ成功声称已逐值透传SEI |
| 7.3 VDIN | 起点 `drivers/media/platform/amlogic/t7-hdmirx/t7-vdin-test.c:529`固定WR_CTRL2八位配置，`:1120`仅枚举当前格式，`:1130`输出NV12/RGB24的SDR colorimetry；`:852`私有环完成后sync/copy/归还，适合作为标准格式归一化边界 |
| Wave5 | 起点 `drivers/media/platform/chips-media/wave5/wave5-vpu-enc.c:92`输入表无P010，`:1689`仅按hdiv/vdiv选420/422；`wave5-hw.c:2454`已有十位16/32-bit源格式寄存器分支；`:2541`清零prefix/suffix SEI；`wave5-vpuapi.c:1035`已有colorimetry→VUI DMA |
| 硬件/固件 | 同树 `wave5-hw.c:431`读取W521_FEATURE_HEVC10BIT_ENC，`:2814`拒绝无能力的十位编码；`:2184`按编码位深计算重建缓冲。已有通用寄存器API支持十位不等于当前转换固件接受P010/SEI，必须板上合成输入验证 |
| One-KVM | `3649a8c8`：`src/platform/vim4.rs:35`限定Vendor；`src/video/pipeline/shared/vim4/wave5.rs:62`固定Main，`:72`NV12/709，`:95`起只处理NV12 stride/plane views；`src/platform/vim4/wave5_caps.rs:1`已有不REQBUFS/STREAMON的能力探测模式 |
| UU | 同版本 `src/uu_remote/peer.rs:476`HDR依赖原生采集与协商；`:802`选择Main10能力，`:2189`处理HDR开关；不能仅改硬件可用判断。历史字段11 enable_hdr与feature6证据见[远程HDR](2026-10-26-remote-hdr-modes.md) |

5.15的[原生双路径](2026-10-25-native-hdr-dual-path.md)是VDIN0高位深本地输出加
VDIN1映射SDR，后续[远程HDR](2026-10-26-remote-hdr-modes.md)增加AMLY→P010→Main10；
该早期记录已明确像素错误被后续修复，不能只引用其吞吐。
[四应用缩放](2026-10-27-all-kvm-hdr-scale.md)证明公共源与浏览器PQ/2020短测，
不证明7.3或静态元数据逐值一致，也不证明Safari、HLG、光度或长稳。

## 上游核对（2026-10-31）

检查了[上游wave5编码器源码](https://raw.githubusercontent.com/torvalds/linux/master/drivers/media/platform/chips-media/wave5/wave5-vpu-enc.c)，
所取版本输入表仍无P010。搜索linux-media的wave5/P010/Main10，没有找到可直接采用的
Wave5十位编码补丁；搜索到的Wave515 Main10是**解码**，不能作为编码输入支持。
这是有限检索结果，不是“上游绝无讨论”的证明。

发现已有[media: v4l2-common: Fix P010 format info邮件](https://lists.openwall.net/linux-kernel/2026/09/04/534)：
修正P010的bpp和vdiv；[7.4 media合入摘要](https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/42e6549eafc66f3648319585680ba0c71c2461da)
也列出该修复。7.3起点仍是错误的bpp={2,2}/vdiv=1，本候选修为{2,4}/2，
使两分量stride相同、UV为半高。后续rebase至包含该补丁的基线应丢弃重复修复。
Wave6是不同IP，不能把其驱动支持直接视为Wave521C固件支持。

公开寄存器定义只有SEI地址和info寄存器，未确认本机匹配固件的info位域/输入单元；
本轮没有猜测长度移位或把完整NAL写入未知ABI，也没有推送任何vendor blob。

## 已实现与验证边界

候选新增P010格式、扩展格式表容量16→17；P010明确接16-bit左对齐420，要求HEVC与
十位内部编码配置。已有硬件能力位检查继续生效。通用P010描述修复同时保证正确容量。
新增 `wave5-hdr10.h`，接受标准V4L2两类compound结构，输出带emulation prevention的
Annex B prefix SEI；保留显式零CLL，不重新缩放标准control里的亮度。
**serializer尚未连接驱动、没有注册HDR10 controls，也没有新增VDIN十位格式。**
不能仅靠本候选启用7.3 HDR；这些缺口仍是下一阶段必要实现。

`test_hdr10.py`编译实际输入分支、读取实际P010格式表，验证容量和拒绝八位/AVC，
用FFmpeg独立解析实际C生成的SEI。新增CPU libx265红帧Main10/PQ/2020 fixture，
检查SPS profile2、Y/UV bit_depth_minus8=2、VUI 9/16/9、mastering亮度/白点与CLL。
CPU fixture只用于解析器，不能证明Wave521C的输出或像素精度。

Wave5目录12个 `test_*.py` 全部通过，包括既有SPS/SEI截断、DMA导入、清理、几何、
隔离、profile、reset、恢复和VUI测试。首次批量到reset时因稀疏树缺iopoll.h失败，
补齐只读源码后reset、VUI及HDR10重新通过；没有通过跳过失败修正计数。

Wave5模块编译通过：使用独立 `/home/deepdream/build/hdr10-remote` 输出、复制的UHD4
生成头与Module.symvers，基础头来自只读linux-7.3，KCFLAGS补候选include路径。
首次缺trace/events/wave5_buffers.h，补齐候选include后通过。
这是模块API编译，不是同提交的完整Image/模块发布构建；无vmlinux，BTF跳过，不可部署。
VM余量约1.8GiB，完整worktree创建失败自动回收后改用稀疏checkout，未清理他人数据。
完整Image、通用core对象构建、标准V4L2 compound验证和真实DMA/固件验收尚未运行。

strict checkpatch：0 errors、0 checks；1条新增文件是否更新MAINTAINERS的通用warning。
本次未新增独立维护者，沿用wave5目录现有归属。无One-KVM生产改动，未运行其全量构建。
原始离线输出在VM `build/hdr10-remote-module.log`、`build/hdr10-remote.diff`，不含板端记录。
主仓完整离线套件运行315项，302通过、13跳过；跳过不算通过。

## r2历史快照：当时未验证草稿

进一步解开同一固定SDK后，找到 `multiEnc/amvenc_lib/AML_MultiEncoder.c:1024`
确实选择 `FORMAT_420_P10_16BIT_LSB`；`:1040`起注明P010使用
`VDI_128BIT_LE_BYTE_SWAP`。`multiEnc/vpuapi/include/vdi.h:244`定义该枚举为17，
`multiEnc/vpuapi/vdi.c:1703`转换为低四位1，`enc_driver.c:1943`取反低四位，
最终源寄存器值为0xe。**r1硬编码0xf不满足这条legacy P010路径。**
内核独立树已写入限定legacy固件的修正与宿主回归，尚未编译、测试、提交或推送。

该SDK的 `multiEnc/vpuapi/enc_driver.c` 是VP5实现；其中没有找到prefix/suffix SEI
写入。此前搜索到的 `amvenc_265/.../wave4.c:850` 的size<<16接口属于Wave4，
不能当作Wave521C的ABI证据。未证明固件不支持，也未将未知位域写入固件。
可考虑在用户态已压缩HEVC AU中插入完整prefix SEI，避免像素复制和固件DMA生命周期
变化；需与静态元数据来源、重复SEI去重、随机访问和5.15产品码流合同一起验证。

VDIN厂商 `vdin_ctl.c:5050` 对V4L/NV21转换强制八位；`:2370`的full-pack路径
输出packed422，`vdin_canvas.h:29`的非full-pack十位路径为每像素3字节，仍非P010。
当前只证明私有AMLY→GPU→P010产品路径；没有找到直接写标准P010/Y210的证据。
不能只改fourcc或MIF十位位来宣称标准P010 DMA。GPU转换路径是否可作为本轮交付，
已向用户提出选择；暂未变更格式对外合同。

One-KVM已创建独立 `../One-KVM-hdr10-remote`、分支`hdr10-remote`（起点3649a8c8）。
草稿通过ENUM_FMT检查VDIN P010，通过私有无缓冲编码上下文协商HEVC/Main10/P010，
核对实际返回的格式、stride、容量与PQ/2020nc/limited；不以内核版本或profile枚举代替。
新增替代格式、短缓冲、profile拒绝等测试；仅执行rustfmt语法/格式检查，未编译测试。
`hdr_remote_available()`和管线保持原门禁，没有以探测草稿开放尚未实现的HDR链路。

本次检查时Mac双锁由HDR r18的lockf进程持有，子命令为sleep 10800。未删除、终止或
抢占锁，未访问板子/M6，也未启动编译。已询问采样是否结束；没有以持锁sleep推断可编译。
磁盘余量VM约1.2GiB、宿主约1.7GiB；VM约9.8GiB可用RAM，可进一步核算tmpfs构建，
尚未创建挂载、清理其他任务制品或声称完整归档可构建。尚无完整候选，未进入候选就绪后
最多120分钟等锁及30分钟上板窗口；本节不能作为r2验证通过记录。
