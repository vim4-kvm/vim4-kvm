# T7 HDR2普通HLG离线候选

后续[统一候选](hdr2-unified-candidate.md)把HLG输出OETF改为5.15产品运行时的sRGB表，
并为映射NV12显式报告sRGB transfer；下文独立候选表hash及709标签描述为原始交付快照。

集成状态：PQ会话已将本候选合并为`vim4-hdr2-pq@bbf9ff89b284d`，保留PQ-only shadow语义，
合并后宿主夹具及W=1/sparse模块构建通过；未上板、未替换正式模块。
[PQ窗口记录](bringup/2026-10-30-hdr2-pq-window.md)及[集成邮件补丁](../packaging/hdr2-pq/README.md)说明当前边界。
以下原始HLG完整构建产物属于独立候选，不能当作合并后的完整构建。

用户已于2026-10-30批准VDIN HDR2硬件路径。本轮仅HLG，不访问板子、不push、不修改PQ会话的worktree。
主仓分支`hdr2-hlg`从main@14cc2b2建立，持久目录`../vim4-kvm-hdr2-hlg`；
内核独立`~/src/linux-7.3-hdr2-hlg`、分支`vim4-hdr2-hlg`从f71b5c6289cb建立。
内核提交`c68407cb052be`；[邮件补丁与应用说明](../packaging/hdr2-hlg/README.md)已保存在主仓，不对外发送。
完整构建使用独立`~/build/hdr2-hlg`与临时uhd3配置副本，release `7.3.0-vim4kvm-uhd3-hlg1+`；未改正式配置。

## 实现边界与与PQ合并

- HDMI DRM infoframe双读、checksum、version/length/descriptor验证沿用现有实现，新增EOTF=3；不从EDID猜HLG。
  仅dynamic_modes、limited BT.2020 YCbCr输入，保留AVI/GCP、包超时和失锁检查；不启用RGB、CUVA或全范围HLG。
- 记录有效包EOTF与当前stream lease的EOTF；PQ↔HLG即使时序/色域没变也返回lease-encoding错误。
  现有capture worker在交buffer前再次检查，标记错误并停止投递，需要drain/重开流；不在活动DMA中途重编整套HDR2。
  重开后的首帧沿用ring_discard；AXI未完成的帧不能交付，停止中的frame仍由旧生命周期退休。
- 新`t7-vdin-hlg.h`独立普通HLG配置：143点EOTF、149点OOTF gain/OETF、65点cgain、T7 precise gamut、亮度主导adaptive scaler。
  使用固定厂商整数表，不以PQ/CUVA表替代，不用浮点公式近似生成厂商编码EOTF。
- 仅NV12路径调用HLG writer，既有YUV→RGB24不支持准入保持；停止MIF、清旧状态后编程，最后enable。
  新writer不使用PQ的hdr_gain/hdr_oetf；已有PQ hdr_curve pending在HLG期间保留，回到PQ后才应用，避免UI请求覆盖HLG表。
- 不新增厂商私有sysfs/ioctl/module参数。输出继续用V4L2 REC709/709/limited、NV12→现有Wave5；不把源HLG标签带到已映射SDR buffer。
  f71的V4L2 xfer enum没有HLG项，内部采用CTA EOTF码，不虚构V4L2控制或借WDR选择HLG。

**输出OETF信令须与PQ工作统一审查**：厂商oe_y_lut_sdr是已有厂商曲线，不是本轮数学推导的BT.709 OETF。
本候选逐项保留厂商表和既有V4L2标签，未声称两者精确一致；最终推广以PQ会话的像素/信令合同为门禁。
不能在合并时仅改709标签、保留错误曲线便宣称色彩一致，也不能直接把PQ会话用户sRGB表写给HLG。

合并接触点为`t7-hdmirx.c/h`的包解析/lease分类和`t7-vdin-test.c`的profile选择/重载。
优先将HLG独立表及writer合入PQ的profile接口，若PQ已使用EOTF枚举就复用该枚举，不保留重复bool＋状态字段。
`t7-hlg-state.h`为本候选纯准入/lease比较助手，可整合进共同状态机；需保留PQ→HLG、HLG→PQ、HLG→无包的实际函数回归。
不要将本分支的旧PQ header覆盖PQ修正，不合并任何EDID能力扩大；统一完成色彩门禁后再声明HLG支持。

## 固定证据与寄存器值来源

V为VM `~/src/linux-native-hdr-5.15/common_drivers@8648a716befda5ec2837a7764cd61b8493db8d99`。
该快照工作树干净；S文件SHA256为`0a708842d2feddf8ea3a811ef8cec7cb74848a522d2de37dd09cd8e17ad1981c`。
下列`S`均为`drivers/media/enhancement/amvecm/set_hdr2_v0.c`；`R`为同目录`arch/vpp_hdr_regs.h`。
原版权/许可证保留；提交信息不添加移植来源叙述。没有读板上寄存器，也没有猜测寄存器值。

| 内容 | 来源file:line与选择 |
|---|---|
| T7位宽模式 | S:3208–3227，T7走eo_gmt_bit_mode=true，VDIN bit_depth=10；普通HLG的cuva_static_hlg_en固定0，禁止套用CUVA分支 |
| EOTF | S:229–246 `eo_y_lut_hlg`143项；S:3388–3407普通HLG选择该表，不选hlg_23 |
| OOTF gain | S:649–666 `oo_y_lut_hlg_sdr`149项，末项512；不选PQ hdr_sdr_gain或cuva_oo_y_lut |
| SDR OETF | S:336–349 `oe_y_lut_sdr`149项；S:2580–2598中10bit每值右移2、两项合并16bit半字、末项单写，无四舍五入 |
| cgain | S:74–83 `cgain_lut1`65项，每项减1（S:3400–3401）；S:2675–2706选y-dominant、coef1高位0x400、两项16bit打包，末项独立 |
| 输入/输出矩阵 | S:1011起ycbcr2rgb_ncl2020、S:949起rgb2ycbcr_709；S:3940–3949选普通HLG的input/709 output/cgain，S:1987–2012的input位/offset写出；本候选限定limited YUV，pre-offset -64/-512/-512，post 64/512/512 |
| gamut | S:1269–1277、2020–2025的T7 VDIN precise override，S:816–818 `ncl_2020_709`，模式BIT(4)\|11；不复用PQ旧8bit矩阵425… |
| adaptive | S:2032–2068普通HLG mode=0（Ys），ys_coef={269,694,61}见S:904，x/y shift=10见S:785–790；S:2113–2126归一化shift=OO_NOR-log2(2^OO_NOR/512)=9。S:2249–2292打包ALPHA1=(10<<24)\|(9<<20)\|(10<<16)\|1024，alpha0=0x04000400，beta全0 |
| 色度系数/使能 | S:2243–2248以709首行{186,627,63}左移2；S:2675–2694设置cgain开、y-dominant。S:1943、1982–1987、2313、2414、2490、2578对应HDR总开、矩阵、EOTF/OOTF/OETF开位；本候选CTRL与PQ不同之处包括cgain开 |
| 地址银行 | R:502–555确定VDIN0 0x1280控制、0x1282/128e矩阵、0x129e/9f EOTF、0x12a0/a1 OETF、0x12a2/a3 cgain、0x12a6/a7 gain、0x12a8–af adaptive、0x12b0–b5 gamut。沿用P设备资源映射，仅写审阅清单，不做MMIO扫描 |

LUT的实际节点分布和硬件浮点插值尚未建立bit-exact像素模拟器；本轮验证的是**表和寄存器端口字**逐项一致，不是HLG光度或像素全域误差通过。
省略histogram配置：本路径无自适应直方图消费者；不因此宣称与厂商所有动态策略相同。profile只针对固定普通HLG，不复制全局module参数策略。

## 宿主验证与复现

内核目录`drivers/media/platform/amlogic/t7-hdmirx/test_hlg.py [V/S路径]`：

1. 去除厂商注释后提取确定十进制/十六进制数组，逐值比对；无厂商树也按固定LE int32 SHA256检查。cgain先减1后hash。
2. 编译实际HLG writer为宿主C夹具，截取写序列，与原始表逐项比较EOTF、OETF截断/打包、gain/cgain端口字、gamut和adaptive/cgain系数及最终enable次序。
3. 编译实际HDMI DRM/AVI处理函数，以模拟COR/TOP测试EOTF=3、checksum错误、撕裂双读、descriptor错误、无新包过期、失锁、全范围及legacy准入拒绝。
4. 编译真实lease选择助手，枚举SDR/PQ/HLG变化；编译真实ring_done函数，覆盖首帧丢弃、正常发布、stop期间不交付、AXI失败不交付。

表SHA256（LE int32）：

| 表 | SHA256 |
|---|---|
| EOTF | `887e6841dfeb378230a0be770dc646801e6758310c4e72333872e41bebaf2150` |
| gain | `84f874e72b917f4fc32032bc8f6a1bdc44b9a91553d7eea841e0533accc38ca1` |
| OETF | `f6259903a90039c4f82535382c60654941861dc21e5aba8db00af87aed992db7` |
| cgain减1 | `7b23b31657f2ac921ce26347da579deefe4b9543050772b090dddb357454431c` |
| precise gamut | `4650784da5a8632231c0a332aed110705c4c884928c366259c9e782f68005267` |

本轮未安装任何板端工具，不占用PQ板锁。宿主夹具全部通过，其中实际writer加UBSAN检查。
strict checkpatch为0 error/warning/check；仅忽略新增文件通用FILE_PATH_CHANGES提示。
驱动目录W=1通过；系统sparse 0.6.4被内核拒绝后，复制已有新版工具至本任务私有目录再跑C=2，
两个驱动C文件均有CHECK且无诊断；准备阶段既有vdso `__kernel_getrandom`声明警告保留。
主仓全量unittest：315项、跳过13项、无失败；无DTS改动，未运行dtbs_check。
完整Image/dtbs/modules与最终提交的增量核对均退出0，2338模块；完整树保留18条未修改ADLA代码的编译告警，RX/VDIN目录无诊断。
邮件补丁对干净f71文件`git apply --check`通过；不把离线构建/表一致当作HLG硬件验收。

| 最终产物 | SHA256 / ID |
|---|---|
| vmlinux build ID | `144d89b672ef484afbddf5e08bc700718bd7025c` |
| Image | `906603fe76f01001bc07b4de52f1a0af005a09ad079a03c85e672e4c33829fdd` |
| t7-hdmirx.ko | `8cd949c01b6a77fb2fd4c39a211e7904c931be82e49da447ae5307e1e3d9c4fe` |
| t7-vdin-test.ko | `1aa1f7c3bb0898b4150ccb9d7833afd434577f3a2e00f1ad3ef7fd4dee0c440d` |

日志在VM `~/build/hdr2-hlg-{build,final,sparse-final}.log`及主机`build/hlg/`。
完整验证后因VM空间紧张仅删除本任务O目录的可重建`.o`缓存；Image/DTB/全模块、vmlinux、配置和日志保留，最终三项SHA再次确认不变。
未生成安装归档；合并PQ后必须重新完整构建，不把上述模块混进uhd3或PQ候选。

## PQ会话统一上板清单（本轮不执行）

- 仅使用合并后同构建Image/DTB/全模块的RAM候选，5.15默认不变。HLG EDID必须在统一窗口显式安排，不能偷偷替换PQ正在使用的EDID。
- 源端已有HLG图/录像或预先设置的HDMI信号；不发HID、不测声音、不ptrace视频进程。先确认EOTF=3、BT.2020、limited、实际深色码，缺HLG源则记未测。
- 受限只读具名CTRL/matrix/gamut/adaptive读回与写profile一致；LUT看shadow CRC，不扫自增data port。
- 同源5.15普通HLG非CUVA的raw NV12与7.3编码前NV12比较，黑白、近黑、灰阶、肤色、饱和色与高光。容差由PQ会话统一预注册，不能用host表一致代替像素通过。
- 同分辨率PQ↔HLG、HLG↔SDR、invalid/超时DRM恢复：旧lease错误、过渡帧不交付、重开后首帧丢弃、无旧profile污染；PQ用户曲线在HLG期间不得改写HLG gain/OETF。
- 每单项≤10分钟带timeout；有效HLG 4K60→NV12→Wave5至少60秒，PTS/计帧/错误/CMA/服务，分别记录吞吐与尾延迟；失败停止验收。
- 正常回5.15、服务/UDC/启动哈希一致。未经此窗口，不推广HLG、不宣称颜色或4K60已通过。
