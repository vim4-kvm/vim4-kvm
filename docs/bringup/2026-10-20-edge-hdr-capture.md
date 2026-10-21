# 2026-10-20：7.x HDR10 采集与 HDR→SDR

已接通 Mac 的 3840×2160p60、BT.2020 / PQ、YCbCr420 10bit 输入，经 VDIN HDR2
映射为 8bit SDR NV12，再由 Wave5 编成 H.264/H.265，网页实测约 60fps，HDMI 音频正常。
支持现有白点/高光参数，播放中预览后可恢复。**HLG、其他 HDR 输入格式和长期稳定性
未验收**；H.265 一轮切换触发网页自动重连，不能宣称所有 HDR 切换保持同一 SSRC。
前期只有接收观测的版本见 [上一记录](2026-10-20-edge-hdr-observation.md)。
后续前端与曲线改进见 [高光与连接优化](2026-10-20-edge-hdr-optimization.md)；以下保留本版本结果。

## 版本与部署

- Linux `c4e982bf80cd0cc8b2f988fd2f6de34017a1838c`，
  tree `13236203800ab03db9ec863b20b8705db7a6123a`。
- 完整 2333 个匹配 BTF 模块包 SHA256
  `272fcfb8fd36a4e014f7b427a8aa959121032bfaaac09f32e180ecc9b318e3b1`。
  Image 字节不变，build ID `cd0b47762bd10b4c02dbf43b369b57ab182d1fb5`。
- 已加载 RX / VDIN build ID 分别为
  `d1f77a4554dd28cc5c031f687f5fb6c46dce553d` /
  `cfcab528dbbff129db7aad989fff99792543c7ce`。
- One-KVM 仍为 `97e810005ea6f8dde6a66a918dc44c7d323dbdc6`，应用、私有 GStreamer
  插件及 DTB 不变；对应摘要见 [源码锁](../../packaging/kernel-edge/sources.toml)。

独立 edge prepare 启用 `hdr_probe=1 hdr_capture=1`，内核选项自身仍默认关闭。
新增专用 [EDID](../../packaging/kernel-edge/uhd60-hdr10-audio-edid.hex)，SHA256
`d54359d8ebfd750684a6a97fc482791ff755b2acab29646773e6104d9c57a47b`：
保留 594MHz 首选时序与已测 LPCM，使用 420-only VIC97 及 10bit 能力，HDR 块只声明
SDR/PQ、静态元数据类型 1，不声明 HLG、HDR10+ 或 Dolby Vision。
普通 VDB 保留 FHD60。它是有限能力的实验配置，不能据 EDID 推断所有 HDR 时序均可采集。

初版 Y420 capability map 未让 Mac 提供 HDR 模式；声明 422 又让它选择未适配的
422 输入。最终 420-only 表已实测协商成功。Mac 关闭 HDR 后仍可能保持 420/10bit，
因此补齐 BT.709 limited SDR 420 路径，不能把“关闭 HDR”等同于“返回 RGB8”。
原厂 5.15 EDID 和原 SDR 固件文件保留。

## 驱动路径与所有权

RX 用 AVI 校验和、色域、VIC、量化范围及 GCP 深色码确认格式；DRM 要求版本 1、
长度 26、EOTF=PQ、descriptor=0，双读一致且在一秒内实际收到。COR `0x1120` bit4
选择每次 unrecognized packet 收包标志，避免默认仅内容变化时更新而错误过期。
只消费 DRM 的 W1C 位，不启用包 DMA，也不修改其他包的中断屏蔽；关闭 core 恢复原寄存器。
失锁清元数据，停止刷新或无效元数据拒绝 HDR 采集。
上板临时将 unrecognized packet 过滤类型改为 `0xff`，保持 PHY/PCS 锁定，
确认 HDR ready 清零、查询返回 ENOLINK、无采集 DMA；恢复 `0x87` 后新包自动恢复。
一秒超时边界另由离线受控时钟测试覆盖。

RX 输出映射器展开 420/deep-colour；计数器半宽 1920、总宽 2200 归一化为
3840、4400，水平同步宽度也加倍。源格式作为租约的一部分，RGB/YCbCr 或 HDR/SDR
变化，即使几何相同也令旧采集失效，待 DMA 停止后重建。RGB 与 420 切换重新资格检查
148.5/92.8125MHz 参考，更新 TMDS meter，供音频 N/CTS 校验。
原 AXI drain、DMA 隔离和 CMA 回收保护保留。

HDR2 配置有限 BT.2020 YCbCr→RGB、PQ EOTF、BT.2020→709、203/1000 尼特增益、
sRGB OETF、有限 BT.709 NV12 输出，沿用 [5.15 曲线](../hdr.md)。
SDR RGB 仍走原矩阵，SDR 420 绕过 HDR2，直接写 NV12；不将 PQ 原始值当作 SDR。
HDR/YCbCr 只允许 NV12，不向 RGB24 快照路径输出错误格式。

平台设备 `hdr_curve` 接受两行各 149 个 CSV 值的一次写入，校验完整性、范围、
单调性和编码端点后才整体替换。sysfs 仅提交待用表，IRQ 在帧完成、MIF 请求关闭后
重载，丢弃其后一帧，避免半帧使用不同 LUT。共享 `vim4-hdr-curve` 新增此入口；
5.15 原参数和 `reload_hdr` 路径保留，现有 helper 的 `hdr-preview` 无须改协议。
配置仍为 `HDR_SDR_WHITE=203`、`HDR_SDR_PEAK=1000`。

## 图像与网页实测

原厂 EDID 的首次 HDR 原生 NV12 快照均为 12,441,600 字节，三原色色块及运动标记
正确。同一 sRGB 灰阶图与 RGB SDR 基准的 16 级 Y 最大差 2 码。
最终版本网页 JPEG 为原生 3840×2160，每张三处 magic/checksum 帧号一致；
HDR 灰阶相对 sRGB 图值最大差 7 个 RGB 码，SDR 420 相对自身基准无漂移。
Mac 的 SDR YCbCr 与 HDR 桌面使用不同源端传递配置，不能直接把两个 JPEG 的
全部灰阶当作相同输入码值比较；没有通过放宽同值断言掩盖这点。

H.264/H.265 各两轮开/关 HDR，均在同一网页自动恢复，每阶段独立测 5 秒：

| 编码 | HDR fps | SDR fps | 音频峰值下限 | 连接 |
|---|---|---|---|---|
| H.264 | 59.962–59.966 | 59.966–60.159 | 0.1023 | 全程同一 SSRC |
| H.265 | 59.963–60.177 | 59.956–59.959 | 0.1015 | 第二轮 HDR 自动重连，后续恢复 |

播放中经原 helper 将白点 203→350→203，中灰 RGB 从 132→103→132，两种编码均通过。
结束后无需重启服务，DMA-buf 严格归零。早期要求每轮同 SSRC 的 H.265 测试失败，
保留原日志，没有计作同连接通过；最终验收记录自动重连，并重新验证实际解码和音频。

新版本另以临时 EDID 各复测一次 RGB8 FHD60↔420 SDR UHD60：
H.264 为 59.980/59.967fps，H.265 为 59.965/59.955fps，均同 SSRC；
截图尺寸、声音及关闭后的 DMA 归零通过。没有将前版五轮结果标成新版证据。

另用 Metal 16bit float、extended-linear-sRGB 表面输入名义 0–10000 尼特阶梯。
默认曲线采集 Y 为
`16,29,53,69,100,132,174,205,231,234,235,235,235,235,235,235`，单调且黑白范围正常。
初始报告 EDR headroom=1、potential=10，未做绝对亮度标定。沿用的 95% 白以下线性、
顶部 5% 肩部，在 8bit 输出中约 400 尼特以上已量化到同一码；1000/10000 峰值设置
在这张图上没有可辨码值差异，**不是完整高光细节保留的验收**。

12 组实际 C 提取回归与完整 Image/dtbs/modules 构建通过；主仓库离线 126 项，
121 通过、5 跳过。新增覆盖元数据过期、校验失败、HLG 拒绝、同几何租约切换、
HDR→SDR 矩阵复位、完整 LUT 写入和畸形曲线拒绝。尚未进行长时间 HDR 推流、
物理拔线、休眠恢复、HLG/动态 HDR 或其他位深/分辨率验收。

证据：`logs/kernel-edge/edge-hdr-capture*-*`、`edge-hdr-web-verified-*`、
`edge-hdr-highlights-*`。三轮完整模块备份为
`/var/backups/vim4-onekvm-edge-20261020/hdr-capture1/` 至 `hdr-capture3/`；
共享曲线工具旧版另保存在 `hdr-capture2/hdr-curve-before`。
默认 5.15 Image、应用和启动项保留，新增配置只由独立 edge 服务使用。
