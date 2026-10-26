# 2026-10-26：远程 HDR 花屏与 SDR 误走十位路径

用户报告 H.265 关闭 HDR 转 SDR 后花屏、帧率低。
此前[远程 Main10 HDR](2026-10-26-remote-hdr-modes.md)只验证了真实输入的色彩标签、
位深和吞吐，没有验证采集到网页的像素内容，不能作为 HDR 画面正确的证明。
本轮补测物理 HDMI 桌面的运动网格、三处带校验帧号与固定 RGB 色块。

## 根因与修改

1. VDIN0 的 `no_swap_en=1` 输出小端全打包十位 4:2:2，每五字节依次包含
   Cb、Y0、Cr、Y1 四个十位样本。原 AMLY 解包错误地反转 128 位字并按高位优先取样，
   原始 P010 已出现周期彩条，与网页花屏一致。修正标量与 NEON 解包，转换到 P010 时
   平均相邻两行色度。独立的实采黑白、红蓝字节夹具防止测试与错误打包实现自洽。
2. 开启 `output.hdr` 偏好时，SDR 源也被送入 CPU P010/Main10 链路。
   现在仅锁定的 PQ 输入使用该路径；SDR 保持 VDIN1/八位 DMA 编码。
   保留偏好，EOTF 改变重建采集；Main10 接收会话可继续接收兼容的 Main 码流。
   驱动 sysfs 将 PQ 拼作 `SMPTE_ST_2048`，判断使用实际 ABI；HLG 不冒充 PQ。
3. 源端 HDR→SDR 时复现 codec CMA 碎片：338 MiB 空闲但无法申请连续 200 MiB。
   VDIN0 十个独立帧分配穿插在旧编码工作区两侧。原生 HDR 模式在 probe 时改为整块
   分配主采集池，保留十个帧缓冲；分配和释放模式一致，不在线修改已分配池的标志。
   此项已部署候选，源端往返验收仍待完成。

## 已完成验证

Mac mini HDMI 3840×2160p60 → RX1，5.15.137-vim4kvm-hdrdual6，
H.265 原尺寸、自动帧率、30000 kbps；Chrome LAN UDP，HTTP 经 SSH 转发。
真实 PQ 输入，输出 HDR 转 SDR 开→关→开：

| 输出路径 | 网页色彩/吞吐 | 实际像素 |
|---|---|---|
| 转 SDR | BT.709，60fps | 20 个推进帧号，三处一致，RGB 顺序正确 |
| 保留 HDR | Main10/PQ/BT.2020，34–35fps | 同上 |
| 恢复 SDR | BT.709，60fps | 同上 |

以上像素验收在 CMA 修改前完成。CMA 修改后的 SDR 登录界面测试中，
HDR 偏好关→开→关均为 BT.709、60fps，开启时协商 profile 2 并正确接收兼容八位流。
这是静态画面的吞吐/协商验证，不能替代运动标记或源端 HDR 切换验收。
Mac 当前停在登录界面，需解锁原用户会话后继续绘制 HDMI 运动标记。
新 CMA 候选独立完成 120 帧主采集→P010→Main10 编码，退出后应用恢复；
此窗口输入为 SDR，含首次插件扫描，不能作为 PQ 性能或源端切换通过证明。

真实 4K HDR 仍未达到 60fps，不以 SDR 自动选择的提升替代 HDR 性能结论。
PQ 色块经 SDR canvas 映射后的数值不能当作 HDR 光度测量。
无 HDMI OUT 显示器，不验收本地透传；未运行音频或官方 UU 客户端。

解包测试：Linux ARM64 Meson 三项通过；Mac Clang NEON、强制标量夹具均通过。
One-KVM Rust 783 通过、3 忽略，release 构建通过。
驱动 HDR、同源采集、帧率/尺寸枚举八项在 Linux ARM64 通过，模块构建通过；
CMA 修改 strict checkpatch 无错误、警告或检查项。
主仓库离线测试 275 项通过、7 跳过。

## 部署、证据与回退

One-KVM `f379f446e895595ea625412dcc85c69a81ca3bb07d987f708243b948458c47e8`；
采集插件 `45687dae40c5de13100126b78fca056adf374461cd5782b7c4b8cf707f028ced`。
CMA 候选 aml_media `74fad91db48bec8d041086b39e77a7a7e3afd8ebe5aaf81e3dd30ea035ed12a0`，
加载 note `3397df5f1b3217c38c4ce6f403f54dd02e1f1235f0ab079674a97f53cc5ac57b`，
initrd `0a08965bb96605d8415405c5ba0a97885e6f52d94a4f04e1f295fa4fb84212f5`；
boot ID `5fe5df69-2ed0-4132-a8d9-cae997aa90a5`。initrd 解包核对内嵌模块，
资格表加入匹配 note。启动仍有既有 DRM vblank 告警，taint 12800。

板端 `/var/backups/vim4-hdr-remote-20261026` 保存
`libgstvfmcap-before-layout.so`、`one-kvm-before-display-fix`、`before-cma.tgz`。
内核回退恢复归档中的模块、initrd、资格表并 depmod、重启；插件/应用回退后重启应用。

忽略目录 `build/hdr-remote/` 保存 `corruption.amly`、`corruption-capture.png`，
`display-layout-corrected.log`、`display-pq-final.log`、`display-pq-hdr.png`，
`capture-layout-tests.log`、`onekvm-display-fix-build.log`、`kernel-cma-build.log`，
`cma-checkpatch.log`、`cma-install.log`、`transition-kernel-failure.log`、`static-sdr-cma.log`。
`display-sdr-final.log` 的实际输入为 PQ，误用 SDR 色彩断言而失败；显式 PQ 重跑通过。
首次 `input-transition.log` 在旧 CMA 方案下分配失败，恢复步骤又遇到手动停应用，不能计作通过。
