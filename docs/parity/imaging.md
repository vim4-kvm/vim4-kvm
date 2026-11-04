# MIPI、相机与其他显示接口

本页管对应能力差距与验证条件；当前身份见[主线入口](../kernel-mainline.md)。
先证明板上连线、扩展件与实际接口，不能从驱动名或 DT 节点推导本板支持。
导航：[能力与边界](#能力与边界)；[范围和依赖](README.md)；[固定来源](../archive/parity-sources.md)。

## 能力与边界

| ID / 厂商能力及来源 | 7.3 状态 | 差异与证据 | 路线、依赖与验证条件 |
|---|---|---|---|
| I01 MIPI DSI/LCD0、背光、local dimming | 缺失 | E基线M0只适配无MIPI的HDMI布局；没有本板DSI host/PHY/panel/背光验收；LCD1/2在厂商默认disabled | 重写DRM DSI host/bridge/panel/PHY/PWM backlight；D01/D03、P06资源归属，两版VIM4、准确面板型号/时序/电源序列、MIPI屏与示波器 |
| I02 CSI PHY/adapter/ISP | 缺失 | 厂商旧版多ISP子块、新版csiphy0/2→adapter→isp0路径不同；E只有C3 ISP参考，无T7完整media graph | 重写V4L2 subdev/media-controller、标准ISP params/stats、VB2/DMA/PM；P06/S04、厂商T7寄存器/固件；匹配CSI相机、转接排线、标定图/RAW源、在场复位 |
| I03 传感器、镜头AF、IQ/标定 | 缺失 | 新板amlsens sensor0@36与dw9714，旧板sensor/iq/lens独立。E无板级sensor/lens集成，enabled仍不证明插有相机 | 外围sensor/VCM可先厂商移植后整理标准V4L2 sensor/controls，ISP核心仍按I02；准确sensor/模式/标定，实际sensor/镜头、光学图卡、合法标定数据 |
| I04 eDP/LVDS/VbyOne/CVBS/其他vout | 缺失 | V6面板参数含多接口 | 选装DRM bridge/panel/PHY路线；先核对板图/厂商当前选中的接口，不为无布线输出承诺移植；调查2–4，确认后每接口对应转接板/面板、协议分析仪；不列当前必须追平前置 |
