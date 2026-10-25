# 2026-10-25：原生 HDR↔SDR 采集颜色跟随与独立曲线

## 范围与已复现根因

接续[原生部署](2026-10-25-native-hdr-production.md)。用户提供UU截图：白色窗口基本正常、
菜单栏蓝色、壁纸青绿/过饱和。开始时实际运行/default为hdrdual2，manager支持/running，
RX仍为4K60 YUV422/PQ。截图中的“不支持”属于旧部署阶段，当前页面未再复现。

持board/heavy双锁，保留同一网页/编码会话自动切Mac HDR，无需用户操作：
hdrdual2收到真正SDR YUV444后，**活动中的VDIN1 hdr_sdr仍为1**。
混合色块约(56,116,184)被错误输出成(0,85,255)，反向色块约(183,116,56)
被输出成(255,1,0)，灰白仍可正常。启动新SDR采集后色相恢复，排除了持续Cb/Cr交换。

VDIN1借用主RX时不再创建第二套接收状态机，厂商V4L2中断却没有普通VDIN中断的动态
颜色/HDR更新，因此运行中一直使用启动时的格式、矩阵和HDR配置。
修复`c98bcf5cb`在VDIN1帧边界读取同源RX属性；变化时重配输入格式、矩阵、HDR核、
位深和MIF，丢弃过渡帧；主RX停止时不发布无效输入。覆盖PQ↔SDR、HLG EOTF、范围、
位深及显式曲线重载，不重开/关闭RX，不触碰One-KVM编码代码。

另复现一次切换后HDR白色252→187、灰色127→92。源端探针仍约199nits PQ，
不是源端停止发HDR：VPP的`hdr10_tm`把共享`oo_y_lut_hdr_sdr`从3153改回1600，
即用户203nits参考白被厂商400nits曲线覆盖。
修复`b4bbf3d42`增加VDIN专用完整149点增益，VPP保留自己的动态表；未写完整时兼容旧表。
`vim4-hdr-curve`同时写专用表并在原生模式请求VDIN1重载，不再让主VDIN0旁路吞掉预览请求。

第三处精度问题：厂商2020→709色域矩阵仅8位小数，三行系数和均为257而非256，
会把接近零的颜色通道抬起。修复`7f85242d4`在T7 VDIN的标准HDR→SDR矩阵使用已有
11位小数系数（行和2048）与匹配的gamut shift，保留浮点EOTF模式；不改VPP、
SDR旁路、非T7或自定义色域矩阵。标量寄存器对照实验中，同源HDR色块的最大通道残差
由14.11降至3.43码，平均1.94降至0.73；随后恢复原驱动设置，未留下临时寄存器配置。
此改动不是针对某几个色块加黑位截断，不牺牲暗部层次来遮盖残差。

## 取证方法与参考域

不使用采集卡。Mac自动显示16色块，网页canvas读取解码帧；同一时段用已审阅的
VDIN0 `prob_mat_sel/prob_pre_post/prob_xy/prob_rgb`读取**HDR/矩阵前**10-bit Y/Cb/Cr，
仅取两颗已上电HDR核的CTRL标量(0x1280/0x1380)，不扫regmap或LUT。
探针最终恢复默认选择与坐标。SDR白/黑/红验证分量顺序及limited量程：
白(940,512,512)、黑(64,512,512)、红(252,408,960)，没有Cb/Cr倒置。

不能把AppKit sRGB绘图常数直接当作HDMI线上的码值：例如源端0.5灰实际探针Y=464，
按limited709解码应为116.44，而非128。工具`tools/hdmi-color-check.py`据实测源值计算
709参考，或PQ EOTF→BT.2020/709线性色域转换→用户203/1000曲线→sRGB参考；
报告包含10-bit探针量化、矩阵/LUT和编码误差，不证明显示器的光学色差。

首次尝试仅撤销EDID HDR声明：成功得到真实4K60 SDR；恢复RTK-CONTROL后Mac未自动
重新启用HDR，所以未把该阶段误当HDR验证。随后通过本机SDK列出的CoreDisplay HDR
开关自动执行，逐次以RX实际EOTF/颜色空间确认，最终恢复原RTK-CONTROL与HDR开启。
不操作UU客户端、不修改音频；声音仅只读检查服务active。

## 48fps窗口

历史04:41:45五秒窗口capture/encoder/UU同时48.35fps；04:41:43 RX颜色2→0、
TMDS invalid、READY→WAIT_CLK_STABLE，04:41:44恢复PQ。UU最大发送间隔765.8ms，
之前同路约60fps且编码队列很短。对应源/RX重新协商造成约一秒供帧缺口，不是持续编码器
吞吐下降，也不能用sequence_gaps=0声称这段没有源帧缺失。

## 候选及验收

中间候选hdrdual4，包SHA256：
`d03b1945e55fbb150074ebf0e37c2278e467b8a6b7f5fb889761564ab7bd9489`，
aml_media note SHA256：`4e9c809f06ec4f9cd3fc780c4a94ca5f70e25a7eed9a2512f8888d48ee8a6557`。
hdrdual4已验证活动会话SDR映射关闭、HDR重新映射，且VPP共享增益被改回1600时，
独立VDIN表仍为3153、白色维持约250而非187。SDR16色块参考最大2.23码、平均0.34。
增加精密矩阵后的最终候选hdrdual5，完整包SHA256：
`48968b9cb49e7b4a76b468e2f6829e8e3ef31e579f1c6b8d50175bf09c30d61e`，
运行模块note SHA256：`062f2416ff75e0dde506fef3b10e1fe7fd814d999297399ccb140cf5ab9878dc`。
一次性启动后，同一活动网页会话HDR→SDR→HDR四阶段，16色块48个通道的参考误差：

| 阶段 | 最大绝对误差 | 平均绝对误差 |
|---|---:|---:|
| HDR初始 | 3.43 | 0.65 |
| SDR切入 | 2.07 | 0.46 |
| HDR恢复 | 3.43 | 0.73 |
| HDR继续 | 3.43 | 0.73 |

SDR期间VDIN1 CTRL=0x1c040、hdr_sdr=0，HDR期间CTRL=0xe05e、hdr_sdr=1；
VDIN0始终bypass，HDR输出仍为2160p60、422 12-bit、PQ/BT.2020。
采集增益3153保持不变，即使VPP表改为1600也不再变暗。
common_drivers已合入推送`a7ca8b05c`，One-KVM仍为`24d35af8`、manager仍为`01a24cf`，
两者本轮无源码/前端改动。经标准promote登记hdrdual5为默认并正常重启，
仅删除无启动项引用的hdrdual1旧boot产物腾空间，不新增备份、回退项或脚本。

UU在`peer.rs`直接订阅`subscribe_encoded_frames()`并发送同一帧数据，未二次转换颜色；
本轮自动验收读取网页解码帧，不冒称重新目视了远端UU客户端。
正式默认重启后再次维持同一活动网页会话自动HDR→SDR→HDR：
最大误差HDR 3.43、SDR 2.23、恢复HDR 3.43；平均分别0.65/0.52/0.73。
随后物理16色块及动态帧号、各独占60秒：H.264 3840×2160 **59.9947fps**，
H.265 **59.9926fps**，drop/lost/freeze/PLI增量均0；呈现p95均17.5ms，
最大33.0/33.5ms，无>50ms间隔。两种编码各三帧的HDR最大残差均3.43、平均0.73码。
HDR gamut读回CTRL=0x1b、系数3401/-1204/-149、-255/2320/-17、-37/-206/2291，
与11位小数配方一致，不再是8位小数配置。
One-KVM/manager/透传/声音服务active，UDC configured；管理器实际页面支持、开关勾选，
显示“透传中”，输出hdrToSdr=false。原RTK-CONTROL EDID及Mac HDR已恢复，测试源退出恢复桌面。

主仓254项通过、7跳过；驱动针对性C fixture及完整Image/DTB/模块构建通过，
checkpatch 0错误、1警告（新增Python fixture未加SPDX头）。Swift图案构建通过，
仅有原同步音频代码的macOS弃用告警，本轮没有调用声音功能。
新增工具误差是对**RX实际码值的软件转换参考**，不是保证Mac绘图API原常数或显示器光子
也只差几个码；源端PQ/YUV编码本身的量化已在探针里，不能误算成KVM新引入的偏色。
驱动C fixture覆盖同一活动采集的HDR/SDR、范围/位深跟随，以及VPP不能覆盖采集增益。
本机忽略证据：`logs/passthrough-hdr/color-cycle-*`、`color-old-48fps.log`及color4构建/启动记录。
