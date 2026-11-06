# 2026-11-06：HEVC 8bit全集逐帧参考核验

配套[.36全集计划](2026-11-06-vdec-integration36-full-plan.md)，仅离线采证，无板票。
发布者在Fluster套件中提供的是整流MD5，不是本次生成的逐帧表。离线软件参考整流
MD5与发布者相等后，才按实际显示帧布局拆出逐帧MD5；136/136现已全部匹配。
参考I420不进入仓库，逐帧表/日志留build，不把未匹配的软件输出当作发布者参考。

- 132条由VM FFmpeg 6.1.1-3ubuntu5常规输出匹配；另1条CONFWIN_A_Sony_1需
  `-flags +unaligned`精确裁剪后匹配，常规裁剪摘要不同，原始失败日志保留。
- SAODBLK_A/B_MainConcept_4使用Fluster hm.wrap锁定的HM
  `ae4c8d6d67572e929610a205eb574bd8dc00c043`（18.0）匹配。FFmpeg输出不匹配，
  不推断为驱动或发布者错误；两条逐帧参考来自HM。
- VPSSPSPPS_A_MainConcept_1的FFmpeg只输出2帧并报告参数集错误，HM完整输出6帧，
  依次176×144、320×240、352×288、640×480、704×576、1280×720，总2756736字节，
  MD5 `1ddf74263cb4953cfdfcf99c563d88ea`。HM输出函数仅加尺寸打印以分帧，
  与未修改HM的原始输出实际cmp相同；打印补丁、两份日志和二进制SHA均留存。

HM源码按Fluster既有锁获取，使用该锁内meson recipe构建，没有新增码流；初次CMake
因环境无cmake失败，随后Meson实际构建/解码通过，失败日志同样保留。未修改系统插件。
未修改HM二进制SHA256 `8e2c2c87444acb2820c43b92dc6ae675dda1be41eb513c74a720a7871b1c0b7b`。

136条参考共8297帧，其中四条超尺寸流40帧虽有软件参考，但不能作为当前硬件支持项。
可执行132条共8257帧。每条frames.json的SHA在[清单CSV](2026-11-06-hevc-full-vectors.csv)
锁定；完整执行/参考计划`build/hwdecode-parity/hevc-full/full-plan.json` SHA256为
`461db28ae4979b3ac1f2865816e2661122f6e0a238a77c3581bead85ecccbf0c`。

Mac证据在`build/hwdecode-parity/hevc-full/`：references-final.tar、evidence逐流
probe/FFmpeg/HM日志和frames.json、HM来源/构建/尺寸打印补丁及原版cmp，
full-plan.json、windows.json、plan.log。VM为`/home/deepdream/build/hevc-full/`。
原版HM与尺寸打印版输出比较日志为hm-original-crosscheck.log；源码和二进制仅本地保存。
