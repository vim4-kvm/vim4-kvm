# HDR2采集池与跨代DMA所有权合同

2026-10-30，承接[a3余项](bringup/2026-10-30-hdr2a3-window.md)。
用户已确认VDIN HDR2主路径；本轮实现及[a5上板](bringup/2026-10-30-hdr2a5-window.md)不改正式配置或默认启动。

## 产品报错属于a3回归

正式uhd3[回归](bringup/2026-10-30-uhd3-formal-regression.md)的One-KVM真实接收3552帧/59.182秒，约60.018fps。
One-KVM `src/video/pipeline/shared/vim4/wave5.rs:121–124`只接受`DmaBufMemory`；
`io-mode=dmabuf`要求V4L2 MMAP池经EXPBUF导出，不能保证下游最终一定收到该类型。

锁定GStreamer 1.24.2源码`sys/v4l2/gstv4l2object.c:5587–5600`：下游没有明确pool提案时，
按设备最小数量加两个工作缓冲并开启`copy_at_threshold`；
`gstv4l2bufferpool.c:1954–1973`在低水位且追加缓冲失败时深拷贝、提前回收采集缓冲。
这正好解释“只出数帧、类型变system memory、严格桥接拒绝、不断重建”。
a3固定累计6个的限制低于产品实际持有量，CREATE_BUFS也不能补足；
HDR2矩阵不改变内存类型，GStreamer编码大小修复改变的是编码CAPTURE池，不是这项原始采集合同。

两层修正，保留严格类型判定：

- 内核`5f420235fff62`：`t7-vdin-test.c:923–942`以192MiB/单缓冲字节数限制REQBUFS及CREATE_BUFS累计。
  4K NV12可容16个，不是无限追加；故障队列仍拒绝再分配，给codec工作/参考帧留CMA。
- One-KVM独立分支`hdr2-dma-contract@db848a5288019f0d651bc429e01d6f727720154b`：
  `wave5.rs:281–288`声明12个下游lease预算：queue3、appsrc2、bridge1、snapshot2、encoder4；
  v4l2src再留2个采集工作缓冲。上板实际取得14个，关闭不确定pool的copy阈值。
  宿主回归重建PQ/SDR/PQ桥接，验证输出仍为DMA-buf且父buffer lease正确归还；不是伪造HDR输入测试。

独立工作树为`../One-KVM-hdr2-dma`，未改kbase或其它应用源码。
构建沿用`vim4-kvm-builder:ubuntu24.04`及锁定Cargo依赖、`--release --offline --locked --features vim4`。
全量测试816通过、4忽略；首次无网络容器的5个本地WebRTC测试超时，开启本地网络后五项及全量重跑通过。
新程序SHA256见上板记录；正式`packaging/kernel-edge/sources.toml`仍锁原3649a8c8，未偷改正式依赖。

## 稳定identity与真正退休

内核`7551908e3116b`改用`(allocator identity, normalized physical address)`双键。
`videobuf2-dma-contig.c:499–525`每次get_dmabuf创建新文件/inode，但`exp_info.priv`相同；
新宿主测试直接执行此函数两次，验证不同inode、相同allocator及引用数3。
Wave5仅对`videobuf2_dma_contig`解释priv，并与VDIN分别经各自device的`dma_to_phys()`归一化。
`device_iommu_mapped()`时输出0，检查器拒绝，不能把未知IOVA当同一物理地址。
本板VDIN `ff000000.video-capture`、Wave5 `fe310000.video-codec`均无iommu_group；实际trace双键逐帧相等且physical非零。

a4取证另发现a3布局错误：`t7-vdin-test.c:106–119`把generation/ticket插在vb2成员之前。
`videobuf2-core.c:500–519`从分配起始地址初始化vb，而回调container_of减去成员偏移，
同一buffer的ARM与DONE/QBUF因而访问不同对象，出现DONE gen=0/ticket=0，并可能访问对象前内存。
立即中止a4、回5.15并关HDR；其数据不计通过。
`851153f2f529f`恢复vb2首成员，增加static_assert；宿主模拟真实分配基址写入，旧布局必须编译失败。

退休检查区分QBUF复用与buf_cleanup释放引用：

- QBUF/重新ARM时编码器仍持有，立即失败。
- buf_cleanup只释放VDIN引用。vb2独立export及Wave5导入仍保留allocator：
  `videobuf2-dma-contig.c:167–188,421–425,523`和`videobuf2-core.c:1392`给出实际引用寿命。
  检查器保持该ticket未退休，直到真实编码完成/取消；不补造完成、不丢弃提交。
- 新代BEGIN仍要求旧代所有ticket退休、全部编码job结束；切点后旧代新提交、保留故障、trace丢失均失败。

a5出现一次合法尾帧：208.240568提交、208.243423切点、208.250112采集cleanup、208.252349编码完成，
下一代208.321857才开始。原检查器把cleanup直接当最终退休，误报提前回收；
新宿主回归覆盖引用先释放的合法完成，以及缺完成、提前新代、重用和重复提交的失败。
这不是通过忽略旧帧来修改门禁。

## 已批准的正式集成方案（门禁执行中）

用户已批准PQ合同集成；必须全部新release门禁通过才能推广。
[uhd4后续PQ窗口](bringup/2026-10-31-hdr2-mcp-ice-pq.md)已补齐MCP、接收、色准与逐代退休，
但PQ→SDR恢复仍较5.15慢约0.5–0.77秒，当前不合并、不推正式分支。

1. 内核以正式f71b5c6289cb为基线，整理为`vim4-hdr2-topics@ce6bc0cc5218a`的六个主题；旧13份仅保留历史证据。
   [补丁目录](../packaging/hdr2-pq/README.md)重放tree与候选均为`6fdb600add9ca1f0ed8bf12266bee9fee8d6debf`。
   合入时生成新的正式release和完整模块包，不能替换同名uhd3或拼旧模块。
2. One-KVM先审阅并合入db848a52；主仓再锁这个提交、私有GStreamer两补丁、真实程序/插件路径及新release准入。
   最后才调整正式sources/runtime/config锁；本轮这些文件未改。
3. 主仓合入`gpu-hdr-prototype`中HDR2文档、打包/工具和本轮修复，保留GPU原型为后备，不启动GPU tone map。
4. 正式候选再做干净启动、PQ/SDR双向DMA/退休、MCP、4K60、CMA、服务/UDC/hash回归。
   本轮未测声音；正式发布若要求声音，另开明确授权窗口。

风险：HLG无真实源，不能宣称色彩/切换已验；最大局部像素差仍有边界成因未完全分离；
HDMI重协商有秒级黑屏，不是无缝切换。建议批准PQ产品合同集成，HLG维持显式未验状态，外部发布另审。
