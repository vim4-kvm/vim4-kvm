# 2026-11-06：integration41 的 K9 自然共存门禁停止

**r109 在 K9 自然 probe 门禁失败后停止，未执行 busy-open、编码统计或任何解码。**
Wave5、t7-jpeg 均绑定，decoder 模块加载但因重叠 DOS MMIO 的排他申请而 probe `-EBUSY`。
其余接口/格式/HEVC132条全 **Not run**，没有像素修复或不回退结论；未部署、合并或 push。
已恢复正式fd41fb5，2372 proof及被动4K视频通过；本任务2次Linux启动、冷复位0。
协调者确认根因，K10交另一worker修复；后续integration42沿本轮计划，仅换源码/release，当前不再取板票。

## 源码与跨日封包

| 项 | 实际身份 |
|---|---|
| 内核 | `f41a9bfd20c09220978f0e348385ad8aaa164048`，重排后9提交 |
| tree | `fcbbdb1444373d723a09619643c0a6331ed4d966` |
| K9 | `dd87f5ed0913b8f7e4058620abbebbf33aa5e4f6`，独占DOS租约移到runtime PM |
| release | **`7.3.1-vim4-20261107`**，integration41任务对应的新UTC日期首包 |
| GNU build ID | `3facecf3c626ad5a254b66cfbe8636287e5e7ee2` |
| 生产配置 SHA256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| 普通RAM SHA256 | `7fc2e46084b579f2889a229afe13ee4a9fa7f13bec11aea07273bd7834b6d0a3` |
| 无线屏蔽RAM SHA256 | `12e84f70a07cbf2567877ef190292cb38923ab9321961adc03565892d51e5ab3` |
| manifest SHA256 | `b73709fc7bb3a32c5c584420e65a76c231112f58503105f9aea48e93420beff6` |
| 统一组件包 SHA256 | `f74a5a466b2b423c31dc53095ccc529a530bd133c1d5524120892722e6691679` |

与bc651815最终树差异仅7文件，为DOS租约及相关KUnit，编解码逻辑未改。
按协调者要求复用登记的VM源码路径 `linux-7.3-vdec-integration40` 和
`/home/deepdream/build/vdec-integration40/kernel` O=；名字仍含40，**实际HEAD已是f41a9bfd**。
旧bc651815留在 `vdec-integration40-before41`，旧构建配置/生成头/命令/symvers等单独封存。
先make clean卸除O=端旧链接，再重编，避免改写与旧bundle/debug硬链接的vmlinux/ko。
构建后 .40 bundle 的 **3083个文件/链接摘要全相同**，r108证据未被复用O=覆盖。

第一轮全量W=1已完成，随后因漏建封包父目录而停止，未产出旧日期包；原始失败日志保留。
UTC已跨到11月7日，按协调者预授权及release.py首包规则改用新日期build=1（不加`.1`），
同SHA/同配置重新生成UTS release及受影响Image/模块/vermagic/BTF，再统一封包；不是重命名旧包。
全量加跨日增量W=1日志共1168条既存告警，与.40集合零新增、VDEC零；实际auto.conf逐项匹配。
保存15份真实额外告警编译命令，生产未混入KUnit/KASAN等片段。
复用本任务已有kunit O=后，arm64 QEMU **67/67**，无跳过/崩溃；协调者的逐提交结果仅引用原证据，
不当成本轮重跑。统一封包核2341模块的集合/BTF/vermagic/build ID/depmod及native来源。
无DT/binding变更，本轮不重复无关schema检查。

无线变体仅extlinux.conf/trial.json改动，2357文件不变，追加原有模块/initcall黑名单和Bluetooth mask。
正式cmdline、默认启动和sources.toml正式锁均未改。窗口实际用无线变体，SSH已确认release/build ID/
boot_id与包一致；原始cmdline及启动描述在[逐启动汇总](data/2026-11-06-vdec-integration41-summary.json)。

离线证据根 `build/hwdecode-parity/integration41/`：
`build41-pre-midnight-no-package.log`、`build41.log`、`offline-production.json`、
`tip.kunit.json`、`tip.qemu.log`、`retained40/`、`bundle40-unchanged.log`、
`artifact-identity.json`、`identity.json`。两个heavy票均已释放，未与sampling重叠。

## 工具及离线拒绝路径

工具提交 `e2ff0eb` 新增显式 `preserve_decoder_probe`：仅卸载编码器，保留已绑定decoder，
实际加载build ID与整包module_build_ids相同后才做metadata open。默认准备路径保持原行为，
未绑定、vendor、私有模块或混合coexistence请求在停止应用前拒绝。
33项vdec-window测试、610项全套测试通过，17项跳过；原始日志 `preserve-probe-tests.log`、
`tool-full-tests.log`，均在上述证据根。主仓提交前最终全套输出另存 `final-tests.log`。

K9分阶段沿用同一manifest/保护清单/watchdog/UART及恢复预算：自然绑定和busy-open →
保留decoder卸载encoder后解码 → encoder重载和板端编码统计。
离线拒绝路径包括正确EBUSY/错误errno/成功open、已加载却未绑定、错误节点minor/OUTPUT事件过滤、
无编码活动/ERROR/过短突发拒绝，以及正式无信号与无关视频失败的区分。
实际r109上传脚本/依赖/输入逐项SHA、2372保护清单、旧计划字段和历史ioctl/genpd回放均通过。
仅标准tracefs软件事件和只读被动流消费，不发HID、不切EDID、不盲读MMIO。
这些是工具门禁，不能代替下面未运行的硬件busy-open/队列统计。

## r109：重叠MMIO请求拦住decoder probe

FIFO **1623**，sampling，30分钟票；入场正式uptime≥300秒，2372 proof与被动3840×2160
**59.35fps**通过，原服务/以太网/UDC状态有效。候选仅启动一次，强身份核验成功，无cold_boot。
随后K9门禁采到：

| 模块 | loaded | 平台绑定 |
|---|---|---|
| wave5 | true | `platform:vdec` → `fe310000.video-codec` |
| t7_jpeg | true | `platform:t7-jpeg` → `fe320000.jpeg-encoder` |
| aml_vdec_drv | true | `platform:aml-vdec-drv` → **空** |

“模块存在”不等于probe成功。原始UART及候选kernel journal均记录：

```text
[    4.977056] aml-vdec-drv fe320000.video-codec: error -EBUSY: can't request region for resource [mem 0xfe320000-0xfe32ffff]
[    4.984221] aml-vdec-drv fe320000.video-codec: probe with driver aml-vdec-drv failed with error -16
```

协调者确认：DT的jpeg-encoder与decoder dos指向同一个64K窗口，两边probe都申请独占区域，
后加载方得`-EBUSY`。源码位置：

- `drivers/media/platform/amlogic/t7-jpeg/t7-jpeg.c:jpeg_probe()`，702行的
  `devm_platform_ioremap_resource(pdev, 0)`；DT在hdmirx-test.dts:32–34列出同一64K寄存器范围。
- `drivers/media/platform/amlogic/vdec/aml_vdec_hw.c:dev_request_hw_resources()`，1394行的
  `devm_ioremap_resource()`，在T7路径只处理DOS窗口。

此前窗口先卸载encoder再probe decoder，掩盖了资源排他冲突；.40 r105先被probe期DOS租约拦住。
K9移走租约后，MMIO请求仍使自然共存失败。不能将本次归为旧opt-in参数、固件限制或像素回退。
修复交t4r的K10（T7用devm_ioremap并审计IRQ/reset/clk等probe期资源）；本worker未修改驱动/DT，
未现场卸载JPEG绕过门禁、未重试求通过。

原始证据：`run109/archive/results/k9/before/{bindings-before.json,bindings.json,kernel.log}`、
kernel journal及`run109/before.log`；实际上传归档清单也保留其SHA。路径均相对本工作树的
`build/hwdecode-parity/`。连续UART位于 `logs/hwdecode-parity-r109/uart.raw`，SHA256
`d177a3a6e9e6fca8fe6648162bb1de0b0956d33c315cc3746ea29834633de596`。

## 恢复、未运行与结论边界

K9自然共存判 **Fail**；busy-open/板端编码统计、原绑定上的PM与解码、encoder重载均Not run。
stateless/media/JPEG/HEVC streaming compliance、全I首帧、三条HEVC短流、H.264三流、
MPEG-2四流、JPEG三样本，以及HEVC十条目标/独立132条均 **Not run**。
原120条Success覆盖0，不能称零回退，也不能从模块probe失败推断码流Fail。

[132行总表](data/2026-11-06-vdec-integration41-full.csv)全部Not run；Success/Fail/Error/Timeout均0。
CSV SHA256 `4530244ad887c8113472a0ff9378e3564a0a9497511ae39af19e15407a25b1ce`。
两次启动、K9绑定与正式恢复摘要见[JSON](data/2026-11-06-vdec-integration41-summary.json)。

正常请求一次正式fd41fb5恢复，2372 protected_files全过；被动3840×2160、**59.58fps**、
帧9→307，无新增掉帧/冻结/丢包。无线服务/模块恢复与入场一致，原One-KVM及UDC正常。
清理前重传必要helper，按marker/归属/SHA清本任务固件副本、RAM候选及上传；
归档782文件逐项核SHA后才清板端，未删除其他文件或更改/boot登记项。

本任务候选1/0、正式恢复1/0（启动数/冷复位数），两侧均有SSH身份；旧.40的两次复位不带入新预算。
跨任务正式eMMC由至少75/14变为至少76/14。Mac→USB-C功率计→板子拓扑不变，无新功率读数，
本次零复位不证明供电/PD问题解决。当前板停在正式 `7.3.1-vim4-20261105` / build ID
`bdbfa439f298e92b5bad092528d11119a974f262`；不部署、saveenv、变更默认或操作Mac输入/显示。
因K9失败硬停，不再排票；integration42待协调者通知，不另写新计划。
