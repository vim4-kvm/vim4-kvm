# HDR 输入映射

EDID 预设声明 HDR10/HLG，主机开启 HDR 时发送 PQ/HLG 10bit 信号。采集为 8bit，
未处理时画面发白。T7 的 vdin0 有独立 HDR2 核，内核在 HDMI 输入为
HDR10/HDR10+/HLG 时将其映射到 SDR，SDR 输入直通（`dmesg` 中
`vdin_set_hdr vdin0 fmt:N`，0=SDR、1=HDR10）。切换由驱动的信号变化处理完成，
不重启服务。vframe 的 signal_type 仍描述源信号；将来 HDMI 环出需要原样输出 HDR 时，
在 vdin0 上设置 `vdin1_bypass_hdr 1` 关闭入口映射，网页另走 vdin1 回写。
Dolby Vision 未支持，EDID 也不声明。

映射表由 `vim4-hdr-curve`（tools/hdr-curve.sh）生成：增益曲线 `oo_y_lut_hdr_sdr`
和 SDR 编码曲线 `oe_y_lut_sdr`。厂商增益曲线相当于 400 尼特映射为 SDR 白，
厂商编码为 gamma 2.2，macOS HDR 桌面会整体偏暗、暗部偏亮。
参数 `HDR_SDR_WHITE`（主机 SDR 白，默认 203 尼特，即 BT.2408 参考白；macOS HDR
灰阶实测 199）和 `HDR_SDR_PEAK`（高光保留到的亮度，默认 1000）保存在
`/etc/default/vim4-kvm-hdr`，与 NanoKVM 改写的 `/etc/default/vim4-kvm-hdmi` 分开。
SDR 白以下 95% 线性，其上用扩展 Reinhard 曲线压入顶部 5%；编码为 sRGB。
增益寄存器为 12 位（上限 4095），SDR 白低于 157 尼特会溢出反而变暗，故下限 160。

hdmi-setup.sh 在打开输入前写入；运行中由 vdin0 attr 的 `reload_hdr` 请求采集中断在帧边界重载，
不重启采集。vim4-manager 的“HDR 转 SDR”滑动条拖动时实时预览，松开后保存。
`oe_y_lut_sdr` 与 VPP/OSD 的 HDR→SDR 共用，将来接 HDMI 输出时同样生效。
HLG 输入仍用厂商 HLG 曲线。
