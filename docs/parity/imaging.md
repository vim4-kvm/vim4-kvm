# MIPI、相机与其他显示接口

固定 [V/E 来源](sources.md)，回到 [总表](../vendor-parity.md)。本页 4 项。
厂商DT启用相机/面板候选不等于本板插有对应扩展件；不使用C3驱动名推导T7可用。
风险H/M，估计单位人日；核心显示和相机进入DRM/V4L2框架。

| ID / 厂商能力及来源 | 7.3 状态 | 差异与证据 | 路线、依赖 / 人日 / 风险 / 验证硬件 |
|---|---|---|---|
| I01 MIPI DSI/LCD0、背光、local dimming；V6:8,1090,1186，V1:1813 | 缺失 | E基线M0只适配无MIPI的HDMI布局；没有本板DSI host/PHY/panel/背光验收；LCD1/2在厂商默认disabled | 重写DRM DSI host/bridge/panel/PHY/PWM backlight；D01/D03、P06资源归属，20–40 / H / 两版VIM4、准确面板型号/时序/电源序列、MIPI屏与示波器 |
| I02 CSI PHY/adapter/ISP；V2:2203–2267，V0:1630，V1:1697 | 缺失 | 厂商旧版多ISP子块、新版csiphy0/2→adapter→isp0路径不同；E只有C3 ISP参考，无T7完整media graph | 重写V4L2 subdev/media-controller、标准ISP params/stats、VB2/DMA/PM；P06/S04、厂商T7寄存器/固件；30–60起 / H / 匹配CSI相机、转接排线、标定图/RAW源、在场复位 |
| I03 传感器、镜头AF、IQ/标定；V0:524–550/1430，V1:1472–1509 | 缺失 | 新板amlsens sensor0@36与dw9714，旧板sensor/iq/lens独立。E无板级sensor/lens集成，enabled仍不证明插有相机 | 外围sensor/VCM可先厂商移植后整理标准V4L2 sensor/controls，ISP核心仍按I02；准确sensor/模式/标定，8–15 / M / 实际sensor/镜头、光学图卡、合法标定数据 |
| I04 eDP/LVDS/VbyOne/CVBS/其他vout | 缺失 | V6面板参数含多接口；V1 lcd1/2与mesont7c_drm.dtsi:11的CVBS默认disabled，本板实际连接待查。HDMI-TX驱动不能代替这些PHY | 选装DRM bridge/panel/PHY路线；先核对板图/厂商当前选中的接口，不为无布线输出承诺移植；调查2–4，确认后每接口10–25 / H / 对应转接板/面板、协议分析仪；不列当前必须追平前置 |
