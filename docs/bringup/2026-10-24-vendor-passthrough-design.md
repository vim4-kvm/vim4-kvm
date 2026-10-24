# 2026-10-24：厂商 5.15 HDMI 透传离线设计

本页保存 [5.15 透传交付](2026-10-24-vendor-passthrough.md) 的第一阶段源码分析。
最初核对 VM `~/src/linux/common_drivers@4cfb128d3`，构建前同步基线 `563cff9da`；
候选分支 `vim4-5.15-passthrough`，manager 从 `passthrough-ui` 建 `passthrough-5.15`。

## 原生链与启动

RX port 1 → VDIN0 → VFM tvpath → amvideo → VPP VD1 → hdmitx21。
`drivers/media/common/vfm/vfm.c:vfm_init()` 原始 tvpath 包含 deinterlace，可含 ppmgr；
板级 `tools/hdmi-setup.sh` 将其替换为 `vdin0 vfm_cap` 并运行 `hdmiin-demo`。
tvserver 管理 RX 打开、信号事件与 VDIN 解码；`vdin_drv.c` 的
`TVIN_IOC_OPEN/START_DEC/STOP_DEC/CLOSE` 是底层接口，不增加第二个 VDIN0 所有者。

## 共享采集选择

VFM 本身不是广播：`vf_get_receiver_name()` / `vf_get_provider_name()` 返回首个匹配端点。
给 vdin0 加两个 map 不会获得两份有独立归还语义的帧。`vfm_cap.c` 已有真正的 TEE：
注册上游 receiver、下游 provider，显示/V4L2 token/DMA-buf 分别持引用，最后归还才 vf_put。
选 `vdin0 vfm_cap amvideo`，逐行输入绕开 deinterlace/ppmgr。
VDIN 8-bit NV21、3840×2160、completed-frame game_mode=3 和 KVM 编码设置均不降低。
完整帧保护保留，不增加 CPU 拷贝或第二次 VDIN 写入。

UHD60 NV21 每次整帧读写约 746.5 MB/s，直接 TEE 新增主要是 VD1 读约 746.5 MB/s；
FHD60 约 186.6 MB/s。它们是理论有效载荷，不是 DDR 实测或零丢帧承诺。
显示持帧占用共享 VDIN 缓冲；ready_list 未限长、源重置强制回收的生命周期需重点验证。
不能为了显示关闭完整帧保护、降低码率/尺寸/帧率或开启同缓冲读写 game-mode bit2。

VDIN1/2 确有多个实例及 `start_tvin_service()`，但 RX frontend/时钟/端口控制共享；
不能凭实例数推断双实例同 RX 的 4K60 能力，额外至少增加约 746.5 MB/s 写入与 CMA。
amvideo 后经 VDIN1 的 VIU writeback 可取 VD1/VPP，但受输出缩放、OUT 热插拔和显示时钟影响，
增加读写与整帧等待，会把 KVM 质量绑定显示器，拒绝作为默认。
video_composer 是提交/合成层而非 VFM 自动广播，首轮不引入。

## 颜色与音频

输出选 [厂商对照](../display-color-vendor.md) 已验证的 SDR YCbCr444 8-bit limited，
420 仅在 sink 实际允许且验证后使用；不用已测原色误差最高 23 的 RGB。
首轮真实 2160p60，不重命名刷新率或降低采集尺寸制造成功。
后续取输入真实时序与 sink 交集；用户态不改 RX EDID、不脉冲 PC HPD。
厂商内核自身可能在 TX 热插拔时联动 RX，见 [HPD 记录](2026-10-24-vendor-passthrough-hpd.md)。

`sound/soc/amlogic/auge/card.c` 的 `HDMITX Audio Source Select` 仅列
Spdif/Spdif_b/Tdm_A/B/C，不含直接 RX；RX 由 `extn.c/frhdmirx_hw.c` 进入采集。
不能把 SPDIF→RX ARC 当作 RX→TX。tvserver/audio HAL 的共存路由待核对；
不并发独占打开 KVM 同一 RX PCM，不承诺音频已支持。

## 接入边界

双锁内暂停 KVM，备份输出/map/服务，干净停源后接入 TEE；启用 VD1、隐藏 OSD，先目视。
之后恢复 KVM，分别核对输入/显示/编码推进与丢帧，不把写入成功当验收。
manager 维持既有 API/前端；探测真实 sysfs、TEE 路由及运行模块资格，不只看 5.15 版本。
开关优先只控制显示可见性，保持采集所有者；输入/sink/output/scaled/no-signal 来自读回。
关闭导致队列积压时必须先修引用/有界队列，不能牺牲采集质量。
新内核部署单独确认，manager 验证后备份部署；用户最后取消部分测试不等于通过。
