# 2026-10-30：MCP开启PQ与HDR2合并候选的编码协商阻断

用户授权One-KVM MCP操作M6；19:36–19:46 PDT独占板/heavy锁，RAM一次启动hdr2a1，最终恢复5.15与M6 HDR关闭。
**PQ识别、HDR2启用、同曲线shadow和局部像素对照通过；Wave5未通过；7.3切换/过渡帧、HLG未测。不能推广完整候选。**

## M6操作与恢复

先MCP截图，确认原有Finder/浏览器窗口；只通过苹果菜单打开System Settings→Displays。
界面显示外接显示器名称为RTK UHD HDR（旧文档写RTK-CONTROL），HDR初始关闭，刷新率60Hz。
默认1920×1080为macOS逻辑缩放，截图源和实际采集均3840×2160；未改变分辨率、刷新率或亮度。
仅点击High Dynamic Range开启；5.15随即读到HDR10-GAMMA_ST2084，VDIN1 hdr_sdr=1。
不type、不单按Shift、不碰文档、不关闭其他窗口；自然滚动仅在显示器设置内使用。

候选启动后网口MAC为02:ad:36:01:89:77，DHCP地址变成192.168.50.162；原MCP目标为192.168.50.210:8080。
串口登录确认后仅以新地址SSH测量，不改网络配置。One-KVM服务active，但MCP截图实际HTTP传输失败。
停止M6操作，正常回5.15并启动One-KVM后重新截图成功；只点击HDR关闭，板端读到SDR、VDIN1 hdr_sdr=0。
截图确认开关关闭后关闭本次打开的系统设置窗口，再截图确认原Finder/浏览器仍在。
未用SSH、脚本或其他方式向M6发送HID。截图保留于本次MCP会话，不将含用户界面的截图提交到仓库。

## 固定构建与启动

- 5.15：5.15.137-vim4kvm-hdrdual6，保留默认不变；native_hdr=1，基线从共享RX的VDIN1映射输出/video71取得。
- 7.3：vim4-hdr2-pq@58b7ecfeb6838，7.3.0-vim4kvm-uhd3-hdr2a1+，build ID 2c88ab69181672d3ca60f93ccded2fb74612aa8c。
- 使用[统一候选](../hdr2-unified-candidate.md)完整归档5dc67148…，同次Image/DTB/2338模块；本次选display-m0 DTB。
  静态PID1验证build ID及私有目录所有者后只读绑定模块与五个私有runtime助手，只为hdr2a1增加准入。
  根位于`/var/lib/vim4-kvm/hdr2-unified/2c88ab69181672d3ca60f93ccded2fb74612aa8c`；无saveenv、不替换默认启动文件或磁盘助手。

## PQ对照

| 项目 | 5.15产品配置 | hdr2a1 |
|---|---|---|
| 输入 | HDR10-GAMMA_ST2084，8bit | 有效DRM 87011a5c0200…，EOTF=2、hdr_input=1、depth code=0 |
| 输出 | NV21，3840×2160 | NV12，3840×2160，stride3840，size12441600 |
| 标签 | 既有Default/709/limited，未宣称实测HDR时逐字段重新读回 | Rec709 primaries、sRGB transfer、709 YCbCr、limited |
| HDR_CTRL | VDIN1 0xe05e | VDIN0 0xe05e，matrix_in/out=1 |
| gamut | 0x1b，T7 precise分支 | 0x18，既有PQ分支；不是逐寄存器相等 |
| gain配置CRC | 5868f499 | legacy203/1000后5868f499 |
| OETF端口样本CRC | 47745310（配置数组右移2） | configured及last_programmed均47745310 |
| PQ EOTF | 本轮未读取厂商LUT | 静态configured CRC 55057c14；不是LUT硬件读回 |

候选默认tables-edge的gain CRC为728d4d9e；第一次数据留存，随后停One-KVM、通过已有hdr_curve兼容口提交legacy203/1000，
在原有停流/AXI完成序列内加载。PQ profile_programmed=1，curve_pending=0，gain的last_programmed也为5868f499。
CRC为LE u32样本；shadow证明驱动执行过写入序列，不能代替硬件LUT数据端口读回。
仅读取已审阅的CTRL/矩阵/offset/gamut白名单，厂商VDIN1字索引为上轮VDIN0名单+0x100；不盲扫、不读取LUT自增端口。

两端各采3帧编码前原始数据，厂商每帧块含尾部padding，候选可见载荷12441600字节。
NV21的VU顺序规范化后比较；下表为首帧、同源桌面静态ROI，坐标均为4K源像素，端点不含右/下界：

| ROI（y范围，x范围） | Y p50/p99/max | U p50/p99/max | V p50/p99/max |
|---|---|---|---|
| 左侧静态文件列表，1000:1200，1000:1800 | 0/1/1 | 0/0/0 | 0/0/0 |
| 灰色背景，1800:1900，400:800 | 0/0/0 | 0/0/0 | 0/0/0 |
| 彩色窗口按钮，460:480，250:280 | 0/1/2 | 0/1/1 | 0/2/2 |

HDMI重连使显示器设置列表滚动位置复位；右侧窗口ROI Y p99=179/max184为内容变化，不能当作颜色误差。
上述ROI是在识别内容变化后选取的诊断区域，**不是预注册色彩门禁**；没有受控HDR测试图、输入码值ground truth，
因此不宣称整帧逐字节一致、绝对PQ色准或高光层次验收通过。gamut分支差异仍需饱和色/高亮固定图验证。

## Wave5与测量工具修正

先前工具把appsink→appsrc桥接caps写死bt709，会隐藏采集端sRGB transfer。
本轮修改`tools/hdmirx-encode-check.py`：桥接首帧保留实际capture caps并记入report；新增显式初始`--colorimetry`选项，默认bt709兼容SDR，
HDR复验使用2:3:7:1；不能以把标签改回709绕过信令门禁。

尝试3600帧/85秒有界4K60 H.265 DMA导入：

1. 输出私有目录root所有导致filesink无法启动；仅修正该临时目录所有者后重测，保留失败日志。
2. 实际capture caps为2:3:7:1；编码器probe公布列表含bt709、1:4:7:1等，未含2:3:7:1，随后not-negotiated。
   初次桥接caps缺少colorimetry也产生accept-caps警告，可能影响缓存；本轮未再次启动候选验证最终显式初始caps选项。

**没有3600帧成功报告、有效码流/VUI或4K60通过数据**。初判为GStreamer V4L2 encoder对混合色彩组合的协商/枚举问题，
不能仅凭该日志断言Wave5固件不能编码sRGB或硬件吞吐不足。下一步离线查probe/TRY_FMT的色彩枚举，再用显式初始caps最小复验，
随后检查SPS VUI的transfer=13及60秒吞吐；不临时写寄存器或伪造成功。

## 切换、HLG、错误与回退

5.15上实际完成SDR→PQ和最后PQ→SDR，hdr_sdr从0→1→0。
7.3期间MCP地址不可达，未操作HDR开关，所以7.3同分辨率切换、旧lease退休/过渡帧丢弃仍未测。
不能以5.15切换或已有宿主夹具代替七系硬件通过。
无HLG源；没有强制写HLG profile、没有伪造infoframe。
HLG只有此前宿主实际writer的LUT/寄存器端口字与切换夹具证据；本轮当前PQ寄存器读回不等于HLG硬件读回。

候选日志无新增WARNING/Oops/BUG或GPU/Wave5 timeout/fault；末次VDIN faulted=0、stream_error=0、invalid_frames=0。
一般启动日志含iwconfig弃用提示，未将包含“default/timeout”的普通日志误计为故障。
最终5.15、one-kvm/vim4-kvm-hdmi/vim4-manager均active、UDC configured，12项启动/助手SHA256全部OK；锁已释放。
不测声音、不ptrace、不写PWM/电压；测量未并行编译。应用本身的既有音频服务未作为测试负载。

原始日志/帧保存在主工作区`logs/hdr2-unified/`，准备脚本在`build/hdr2-window/`；不上传原始桌面帧。
本轮内核无新提交；主仓记录与测量工具修正经unittest后提交。正式main/内核基线不合入候选。
按“只推验证通过提交”的约束，主仓报告推特性分支；内核只推已验证PQ诊断前缀和此前已上板GPU系列。
HDR2合并/OETF提交的编码门禁未过、HLG未上板，相关内核提交继续留本地，不冒充完整验收通过。
推送目标：主仓gpu-hdr-prototype（本轮记录）、hdr2-hlg@15d0eab（已在远端，无新增）；
内核vim4-hdr2-pq仅到eb156b545c8a2，vim4-gpu-panfrost到此前已上板的52ad11da91f3c。
内核58b7ecfeb6838/c68407cb052be不新增推送，正式main及vim4-kvm-7.3不动。
主仓unittest：315项、跳过13项、无失败；文档/索引/体积与diff检查通过。
