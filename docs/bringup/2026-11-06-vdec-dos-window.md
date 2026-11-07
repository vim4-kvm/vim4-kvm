# 2026-11-06：T7 DOS 窗口注册共存与 probe 资源审计（K10）

r109 自然启动时 Wave5 和 t7-jpeg 均绑定，解码器在申请
`0xfe320000–0xfe32ffff` 时 -EBUSY，未注册节点。K9 已解决 probe 租约竞争，
这次阻塞来自同一 DOS 窗口的 request_mem_region。
原始证据只读：`vim4-kvm-integration41/build/hwdecode-parity/run109/archive/results/k9/before/`，
其中 bindings.json 显示编码器已绑定、解码器模块加载但没有绑定设备；kernel.log:442–443 为申请失败。

## 修改与系列

仅改解码器 aml_vdec_hw.c:1394 的资源映射。T7 has_dbus_ctrl 路径用 devm_ioremap，
不申请独占区域，NULL 返回 -ENOMEM；非 T7 继续 devm_ioremap_resource 和原错误指针处理。
注释说明与 JPEG 共用 DOS 窗口，以及硬件访问受 runtime 独占租约保护。
没有新增寄存器访问、时钟/电源动作或软件解析逻辑。

K10 插在 K9 之后、K1 去门之前，去门时同时具备租约寿命与映射修复。
基于 0ae8beaa 的十提交如下，K2/K9 原 SHA 不变，后七提交无冲突重放：

| 项 | SHA | 摘要 |
|---|---|---|
| K2 | `2ec22a40b8b99987a8e7fca77477c1c019c8f565` | 删除原始 DOS 实验。 |
| K9 | `dd87f5ed0913b8f7e4058620abbebbf33aa5e4f6` | DOS 租约随 runtime PM。 |
| K10 | `5f9a4be44b1d9a92bbdb4707d0aefecef292a975` | T7 映射共享窗口，不 request 区域。 |
| K1 | `1f1408420569056085bb8d6b0b1fa561c0e32fc3` | 去门，保留 K9/K10。 |
| K3 | `65720ac4ccf786ab342abc5d78b97b0ab63184ad` | 每图 RPS。 |
| K4 | `b0ccf75cc56042bd5b058b72e6a937e1ced80478` | 裁剪回退。 |
| K5 | `d1d6879d98605b32bc2acdedde95dec8507603da` | 最小头解析及 reviewB 规则。 |
| K6 | `3910ca58ba4297012a101b9eb452689eb96a9b6c` | stateful discard。 |
| K7 | `2ae35cc5c5086bfb98b6afcb1f688c79a02c7df5` | C.5.2 输出过程。 |
| K8 | `3facfaa37284f7193508c2a16fbf5162c6242616` | 单 AU 隔离。 |

相对已审 f41a9bfd 只有 aml_vdec_hw.c 的13行增加、4行删除；HEVC、DPB 和共享协议源码不变。
作者及旧提交说明/签署保留。完整补丁及 range-diff 在 `build/vdec-fixes/k10/`。
此次是简单映射调整，不新增模拟映射的测试；沿真实 KUnit 与构建门禁验证，注册共存需实板。

## 实际 DTB 与三方资源审计

从 r109 candidate.tar 只提取 vim4.dtb，SHA256 与封存 manifest 一致：
`fbef1ddaecdc7924de841c9fe36885bcb8c36b18cd4b97804a74af44f2588b90`。
文件在 `build/vdec-fixes/k10/audit/r109-vim4.dtb`，反编译结果及原始诊断分别保留在同目录和 logs。
核对真实封包而非只看 dtsi：三节点均无 resets、memory-region、sram 属性；解码器无 assigned-clocks。
审计表 `build/vdec-fixes/k10/probe-resources.csv` 共15行，原始源码摘录在 `audit/probe-source.log`。

| 资源 | 解码器 | JPEG / Wave5 | 判断及依据 |
|---|---|---|---|
| MMIO | DOS 0xfe320000，64KiB | JPEG 同窗；Wave 0xfe310000，64KiB | 唯一发现的申请冲突，K10 消除解码器的 request。 |
| IRQ | GIC SPI92 与 HEVC SPI91，均 NO_AUTOEN | JPEG SPI93；Wave SPI94 | 四条不同，数字为 SPI，不是 Linux 动态虚拟 IRQ。见 amlogic-t7.dtsi:2167、hdmirx-test.dts:35/49。 |
| reset | 无 reset_control 获取 | JPEG 无；Wave optional exclusive array | 实际 T7 DT 没有 resets，Wave 无可争用 reset handle。wave5-vpu.c:468/498。 |
| 时钟获取 | 普通 clk_get/bulk_get，只取句柄 | JPEG bulk_get；Wave bulk_get 后 enable | 无 exclusive/rate-exclusive 请求；SYS_DOS三方共享，VAPB由两编码器共享，CCF引用计数。 |
| assigned-clocks | 无 | JPEG HCODEC→HCODEC_0、666666666；Wave A/B/C各666666666 | 不改解码器功能时钟，也不 assigned 共享 SYS_DOS/VAPB。实际 DTB 与 hdmirx-test.dts:40/58。 |
| 共享时钟寄存器 | VDEC 下半 mux/div/gate | HCODEC 上半；Wave 独立 WAVE521 寄存器 | 字段不重合，clk-regmap.c:61/162/205 均按 mask 更新。t7-peripherals.c:985/1013/1039。 |
| genpd | VDEC4、HEVC3，另 attach NIC3 | HCODEC2、WAVE5 | 不同子域共享 NIC3 父域，不是独占 attach；域 flags无 SINGLE_DEV。meson-secure-pwrc.c:416–425。 |
| DMA/CMA | probe 无 codec DMA 分配 | JPEG open 才分配；Wave probe 分配普通 coherent common buffer | 无专属 pool 或保留区争用。Wave 用普通 DMA allocator；T7 sram_size为0且DT无sram。 |

没有发现第二处 probe 独占资源冲突。这个结论覆盖上述代码及封存 DTB，不能替代下一窗的双加载顺序验证。
Wave 本身 probe 会启动其硬件，仍由共享编码器租约排斥解码器 active；本项不允许同时解编。

K9 的 DOS 访问边界不变：T7 probe 安装禁用 IRQ、映射 regmap、attach 域并 get 时钟，
不执行 DOS MMIO；T7 domain link 不带 DL_FLAG_PM_RUNTIME，初始 runtime suspended。
唯一上电路径仍在取得独占租约后的 vdec_enable / HEVC job；系统查询只做 read-only SMC。
映射成功不触发读写，regmap_init_mmio 默认无寄存器访问。

## 门禁与上板交接

十提交 strict 预检零 errors/checks，K2/K9/K5/K7各一条 MAINTAINERS 通用提示；K10为0/0/0。
正式 heavy **FIFO1624**（票 d14cf9c61e564efb8c72a27255d52d7f，已 released）完成新八提交
逐提交 W=1完整模块和 arm64 QEMU。按表顺序 KUnit 为 **46/49/49/49/51/53/58/60/64/67** 全过；
前两个未改 SHA 的 K2/K9沿用其已审原始证据，新八个 SHA 均为本轮实际运行。
汇总 `build/vdec-fixes/k10/gates.json` 标明证据来源，尖端测试配置模块SHA256
`7b281eacd3555855d9bd54c2210facd2725ae25094f5d0047bf2270200cb397b`。

尖端 DEBUG_FS=n/y、CONFIG_KUNIT=n 两配置完整内核链接和 W=1模块通过；
两配置 decoder 模块SHA256相同：`018fe28e7bbfecebeecd59dba1959c5a53db20572f2d71ba1374d457d8ea3199`。
模块/内建有效 sparse 实际 CHECK包括 t7-dos.c、aml_vdec_hw.c，驱动零诊断。
保留既存 VDSO __kernel_getrandom提醒、四个 KUnit模块缺MODULE_DESCRIPTION提醒，以及
kernel-doc的node/diag_started缺注释提醒；smatch未安装。未改DT/binding，不新增schema门禁。
源码目录含ignored状态为空，所有旧作者、AuthorDate及完整说明/签署比对不变，diff --check通过。
主仓库全套 **608项OK、14跳过**，`logs/vdec-fixes/k10/repo-tests.log`。

脚本 `build/vdec-fixes/validate.sh` 转入固定新尖的 `k10/validate.sh`，VM 路径同原构建根。
默认跑全部十提交 strict、W=1模块、arm64 QEMU，以及尖端 DEBUG_FS=n/y、有效 sparse 和 kernel-doc。
独立 O= module/kunit 保持；失败/跳过和原始输出保存在 `logs/vdec-fixes/k10/`、`reports/<SHA>/`。

由协调者/t3k 在通过门禁后批量验：

1. 自然加载、编码器先加载：三方 platform binding 和解码节点全部存在；无 region/IRQ/reset/clk -EBUSY。
   编码器保持加载时，解码 open 的 -EBUSY 是 K9 预期，不能误报 probe 失败。
2. 解码器先加载且 idle，再加载 JPEG/Wave：三方均可绑定；解码 runtime 保持 suspended，编码器可工作。
   同时检查 IRQ 条目与编码视频，不以模块 loaded 代替设备已 bound。
3. 卸载编码器后，原 decoder 节点无需重载即可 open/close、解码及 compliance；close 后 suspended。
   decoder active 时编码器 probe -EBUSY仍是互斥设计；下一次 close 后允许加载。
4. 沿既有 integration 清单回归 HEVC/其它 codec，窗末恢复并验证真实 KVM 推流。
   任一新 probe 错误、WARN/fault、租约泄漏或旧 Success 退步即停并保存证据。

未改 JPEG、Wave5、DT 或仲裁策略；未碰板、不push、不合并、不提交主仓库。
父节点/syscon 建模由协调者另记 issues，本轮未扩展。注册共存和实板像素仍待板窗。
