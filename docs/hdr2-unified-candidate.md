# HDR2 PQ/HLG完整候选与统一验收

**当前离线修复与下一窗口以[HDR2a3清单](hdr2a3-offline.md)为准**：默认恢复产品709视频合同、增加Wave5 VUI、精确gamut/预偏移及逐buffer退休证明。
以下设计、完整构建及窗口表保留a1历史；transfer13门禁和等待用户物理切换的前置已被后续决定替代。

最新[a2窗口](bringup/2026-10-30-hdr2a2-window.md)已恢复MCP并完成4K60 DMA编码；SPS无VUI、固定图色差及零告警门禁仍阻断正式合入。

用户已于2026-10-30确认VDIN HDR2硬件主路径。此次仅离线，不访问板子、不push。
后续[真实PQ窗口](bringup/2026-10-30-hdr2-unified-window.md)：PQ路径与局部像素通过，Wave5 caps协商阻断；
7.3切换及HLG仍未测，不推广候选。用户已另授权MCP准备M6及推送通过验证的特性分支。
独立VM工作树`~/src/linux-7.3-hdr2-pq`、分支`vim4-hdr2-pq`，基于正式`f71b5c6289cb`；
HLG原提交`c68407cb052be`已整合为`bbf9ff89b284d`，主仓`15d0eab`已整合为`f7b2f84`。
保留PQ诊断`eb156b545c8a2`与CRC依赖`11f3239b7c849`，输出合同修正`58b7ecfeb6838`。
独立release **7.3.0-vim4kvm-uhd3-hdr2a1+**，完整输出`~/build/hdr2-combined`，不覆盖uhd3或hlg1。
[邮件补丁](../packaging/hdr2-pq/README.md)四份顺序应用；HLG原worktree、NPU文件、正式配置均未修改。

## OETF与标签的明确取舍（a1历史）

**以5.15产品运行时配置的sRGB OETF为数值目标，PQ与HLG共用该表；映射后NV12报告709原色、sRGB transfer、709 YCbCr、limited。**
没有把sRGB表改名为数学BT.709 OETF，也不将已映射SDR标成PQ/HLG。SDR旁路NV12维持既有709/709/709/limited。
RGB24维持sRGB/full；现有准入仍拒绝YUV HDR到RGB24，不新增格式承诺。

证据与边界：

- V为`~/src/linux-native-hdr-5.15/common_drivers@8648a716befda5ec2837a7764cd61b8493db8d99`。
  `drivers/media/enhancement/amvecm/set_hdr2_v0.c:336–350`默认`oe_y_lut_sdr`可运行时覆盖；
  `:3295–3312`的PQ和`:3388–3407`普通HLG都选择同一个可变数组，`:2580–2598`在10bit口径右移2打包。
- 产品`tools/hdr-curve.sh:55–57, 107–113`生成sRGB OETF，apply会写同一个厂商数组。
  [上轮实际读回](bringup/2026-10-30-hdr2-pq-window.md)配置CRC为539ffb54，右移2的端口样本CRC为47745310，与七系PQ相同。
  这是**真实配置读回**；源当时是SDR，尚不能证明HDR时已应用，更不能当作PQ像素通过。
- 原独立HLG候选保留的是厂商源码默认gamma表，其SHA为f6259903…；现在改为引用PQ的`t7_hdr_srgb`，
  LE int32 SHA256=`bcb715148098dffe8c2d1fbf867ae1e80e5dc7f7fb03b401100ee40ca0739099`。
  HLG EOTF/gain/gamut/cgain和写入顺序不变，只有输出OETF对齐当前产品配置。
- 5.15上轮V4L2为colorspace/xfer DEFAULT、YCbCr709/limited，并未显式表达sRGB。
  新候选选择准确的V4L2 transfer，而非复制含糊DEFAULT。原色与传递函数分开，sRGB transfer不意味着全范围或RGB像素格式。
- `t7-vdin-test.c:t7_vdin_fill_fmt`按已准入源/活动lease选择输出transfer；
  新`t7_hdmirx_capture_is_hdr`持link锁，活动流使用不可变lease，未ready不读MMIO。
  source-change/drain/reopen后再协商；应用不能缓存SDR时的caps后继续把HDR映射帧标709。

**编码端仍是验收门禁**：现有`gst-plugin-venc/wave5/gstvim4wave5enc.c`未显式将输入transfer写入VUI；
内核`drivers/media/platform/chips-media/wave5/wave5-vpu-enc.c:645`保存输入colorspace不等于已验证比特流VUI。
下一窗口必须记录采集caps与H.264/H.265 VUI transfer（sRGB应为IEC 61966-2-1代码13），缺失/变成709则判信令项未通过，
保留原始NV12数值结果，另修用户态/编码接口，不能以改回错误V4L2标签掩盖。
浏览器若拒绝混合709原色+sRGB transfer，也要据实记录，不能据此宣称端到端颜色已闭合。
旧hdr_curve兼容口仍存在；任意替换OETF不在此次固定sRGB候选的正确性范围，white/peak调节生成的sRGB表不变。

## 离线验证与复现

私有配置由`~/build/uhd3/.config`复制，只改LOCALVERSION为`-vim4kvm-uhd3-hdr2a1`，不改主仓配置。
构建前只清理本会话旧GPU O目录可重建的`.o`，Image/DTB/模块/日志均保留；未清理HLG/NPU/正式构建。

```sh
cd ~/src/linux-7.3-hdr2-pq
mkdir -p "$HOME/build/hdr2-combined"
cp "$HOME/build/uhd3/.config" "$HOME/build/hdr2-combined/.config"
scripts/config --file "$HOME/build/hdr2-combined/.config" \
  --set-str LOCALVERSION '-vim4kvm-uhd3-hdr2a1'
make O="$HOME/build/hdr2-combined" ARCH=arm64 olddefconfig
make O="$HOME/build/hdr2-combined" ARCH=arm64 W=1 -j8 Image dtbs modules
python3 drivers/media/platform/amlogic/t7-hdmirx/test_hdr_crc.py
python3 drivers/media/platform/amlogic/t7-hdmirx/test_color.py
python3 drivers/media/platform/amlogic/t7-hdmirx/test_hlg.py \
  "$HOME/src/linux-native-hdr-5.15/common_drivers/drivers/media/enhancement/amvecm/set_hdr2_v0.c"
```

`test_color.py`按实际HDR2节点与sRGB数学定义核对149样本，执行真实输入分类/format函数，
覆盖未ready无MMIO、活动lease不受新输入扰动、映射NV12标签/stride、SDR旁路与RGB/full。
HLG writer端口字夹具改为共享sRGB期望；其余厂商表逐值对照及实际DRM/lease/过渡帧回归保留。
这些能证明表/写序列和标签选择，不证明硬件插值、色度采样或显示光度准确。
产物记录见下节；不能将原独立HLG完整构建或之前PQ目录模块构建冒充本轮完整构建。

## 构建产物

完整构建日志`~/build/hdr2-combined-build.log`，sparse日志`~/build/hdr2-combined-sparse.log`。
工具链为Ubuntu GCC 13.3.0-6ubuntu2、GNU ld 2.42；UTS为`#1 SMP PREEMPT Sat Oct 31 10:30:39 +08 2026`，
build user/host为deepdream/vim4-build。重建可显式固定KBUILD_BUILD_TIMESTAMP/USER/HOST/VERSION；不声称不同工具链可生成逐字节相同产物。
无DTS改动，完整dtbs编译，不另声称dtbs_check通过。

完整Image/dtbs/modules退出0，2338模块；全树W=1保留1174条其他代码的warning（含重复诊断），
修改的RX/VDIN目录无warning/error。目录C=2 sparse两个C文件均有CHECK且无诊断；
strict checkpatch为0 error/warning/check（744行，仅忽略FILE_PATH_CHANGES）。
CRC、颜色合同、HLG writer/解析/lease/过渡帧夹具全部通过；四份邮件补丁对干净f71应用后与最终源码一致。
主仓全量unittest：315项、跳过13项、无失败。

私有归档`~/build/hdr2-combined-stage.tar.gz`由[封装脚本](../packaging/hdr2-pq/package.py)生成，
带所有文件SHA256 manifest，同次完整模块集strip后保留BTF；vmlinux留在O目录。
归档内2470个文件逐项重新计算SHA256全部匹配，2338模块；VDIN vermagic与独立release一致。
这不是自动安装包，下一窗口仍需为独立release准备匹配的私有runtime助手和RAM启动器，禁止默认助手未准入时强行继续采集。

| 产物 | SHA256或build ID |
|---|---|
| 归档 | `5dc671488035a21da7cb7db90d283f8831dd7885fc034d1f529111f653729387` |
| Image | `9226eef40ff9643081b248fac776ac331e57f3b900c4592f369212e2256af97f` |
| display-m0 DTB | `6e69635a251ff9e2163384cd757d1d204e492d8e2b0fd68a9dbc1c992d1d62eb` |
| 临时.config | `a0181de232c82181c0f34fca9dd6202277c490c092ccb70aeee564ec91472718` |
| vmlinux build ID | `2c88ab69181672d3ca60f93ccded2fb74612aa8c` |

## 统一上板窗口：总计≤30分钟（a1历史）

前置：用户按[M6操作说明](m6-enable-hdr.md)物理开启HDR并确认；源固定3840×2160/60Hz。
先准备同一稳定灰阶/饱和色/高光测试画面，记录原始文件SHA、播放器及呈现设置。
普通桌面只能做功能观察，不能替代受控色块。若用户/素材未就绪，不启动窗口、不发HID补救。
板锁与heavy锁独占；所有单项timeout≤10分钟，测量不编译、不音频、不ptrace、不PWM/电压。

| 预算 | 执行与门禁 |
|---|---|
| 0–4分钟 | 5.15默认、锁/服务/UDC/启动与助手哈希；只读确认有效PQ EOTF=2、BT.2020、range/实际位深。确认VDIN1确为共享RX且hdr_sdr=1，不能取VDIN0原生HDR冒充SDR对照。保存固定图3帧与当前gain/OETF配置、native标志、CUVA参数 |
| 4–7分钟 | 同构建Image/DTB/全模块和私有runtime助手，只用U-Boot RAM选择hdr2a1，无saveenv、不改默认5.15；核对release/build ID/BTF加载、服务、UDC |
| 7–12分钟 | PQ采集3帧：去尾padding、NV21→NV12色度规范化，同源固定图ROI/全帧差异；相同white/peak及gain，禁止tables与tables-edge混比。候选先用既有工具生成legacy203/1000以配厂商gain；记录两端CRC而非默认猜测。受限HDR_CTRL/矩阵/offset/gamut只读快照、PQ shadow configured/last_programmed CRC；禁读LUT自增数据端口 |
| 12–17分钟 | 用户物理关闭/开启HDR一轮，均在同分辨率；记录source-change、lease错误、最后旧buffer/首个新buffer的sequence/PTS，验证过渡帧discard、不把错误/旧profile帧交编码。每次重开核对xfer与shadow；失锁/恢复或错误不能自动沿用旧HDR分类 |
| 17–22分钟 | 真实PQ→NV12→Wave5 4K60至少60秒，采集/编码帧数、PTS p99、丢帧、CPU/CMA、timeout/fault；读取码流VUI与caps，sRGB transfer及709原色/矩阵/limited一致。颜色门禁失败则停止性能推广，但保留故障证据 |
| 22–24分钟 | 有真实HLG源才执行HLG识别/受限状态；无源仅封存host writer测试与现有SDR/PQ寄存器基线，HLG信号/切换/像素/吞吐明确未测，不强制伪造EOTF或写入HLG profile |
| 24–30分钟 | 有界停流，正常回5.15；核对12项受保护哈希、三个服务active、UDC configured、日志无新增fault/WARN，释放锁；预留异常回退时间，前项超时则跳过可选项 |

像素门禁：固定图同栈3帧先估计静态抖动；若不稳定，固定ROI/图源后重测，不能不断放宽容差。
预注册工程阈值为黑白码差≤1、灰阶Y绝对误差p99≤2/最大≤4、非色度边缘UV p99≤3/最大≤6（8bit码值）；
边缘ROI单列报告，不据此宣称标准色准。超阈值先查LUT、矩阵、range/采样相位及呈现一致性，不自动通过。
无法锁定输入码值时只报告5.15相对差异；没有输入ground truth就不宣称PQ绝对EOTF准确。
GPU/VDIN/Wave5 timeout/fault零增量为硬门禁；树外模块O taint与WARN位必须分开。

### 没有HLG信号时的替代证明

本轮没有证据表明M6的系统HDR开关能强制HLG EOTF；播放HLG视频也不保证HDMI原样输出HLG，必须看真实infoframe。
本轮可完成的是宿主实际HLG writer的寄存器端口字、LUT样本和启用顺序测试，不能称作HLG硬件读回。
SDR/PQ运行时受限寄存器读回只证明当前profile；不以旧值或PQ shadow替代HLG状态。
HLG完整验收需要能原生输出HLG的信号发生器/相机/播放器或明确支持该输出的外部设备，接入须另获用户安排；不伪造信号、不扩充EDID来假装已验收。
