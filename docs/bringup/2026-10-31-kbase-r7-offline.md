# 2026-10-31：kbase默认调频对齐候选，等锁超时

结论：取消performance默认的离线代码已准备；**未构建、未上板、未提交/推送**。
不能将[r6的800MHz成绩](2026-10-31-kbase-r6-window.md)视为新默认策略通过。
当前入口见[候选状态](../gpu-kbase-7x.md)。

## 窗口与基线

UTC 07:19:44开始等待，约09:19:44排队取锁超时（lockf退出75）。
期间持锁者先后显示HDR_UHD4、HDR_R17、HDR_R18；未中断、删除或替换对方的锁。
曾观察到空闲瞬间，但未取得可用窗口；截止时仍由HDR_R18持有双锁。
没有SSH/串口访问板子，没有HID、声音、视频ptrace、PWM或电压写入、刷写或blob分发。
未替HDR停止服务或回退；板子当前状态由HDR会话管理，本轮没有5.15回退核验结果。

最后09:20:15重新fetch后，主仓origin/main仍为14cc2b2，sources.toml固定
f71b5c6289cb / 7.3.0-vim4kvm-uhd3+，不是预期的uhd4。
本轮没有改内核worktree；后续上板前必须重新核对正式revision/release/build ID。
若uhd4已合入，先更新构建锁定值与候选DTS，使用同次Image/完整模块集构建，不复用uhd3模块。

## 厂商策略的源码证据

固定厂商树80a07ad5406d，以下路径相对其根目录：

| 证据 | 含义与边界 |
|---|---|
| .config启用CONFIG_MALI_MIDGARD_DVFS，关闭CONFIG_MALI_DEVFREQ | 不是看到devfreq.c存在就认定实际运行simple_ondemand；待读板上运行态再次确认 |
| drivers/gpu/arm/midgard/platform/devicetree/meson_main2.c的平台metrics回调 | utilisation先取整数百分比，再乘255/100，传给厂商scaling |
| 同目录scaling.c的mali_decide_next_status | 每档up/down阈值，下降保持计数；中间负载刷新计数，改变档位后保持；def_clk条件下才有bst_gpu跳档 |
| common_drivers/arch/arm64/boot/dts/amlogic/meson-valhall.dtsi及mesont7(c).dtsi | 五种频率250/400/500/666/800MHz；阈值分别0/76、80/120、80/120、80/120、80/255；keep_count=5，基础def_clk=0；表尾重复800档 |
| mali_kbase_config_defaults.h及backend/gpu/mali_kbase_pm_metrics.c | 默认metrics周期100ms；GPU poweroff tick 400µs、shader计数2；实际可写属性仍待只读核对 |
| backend/gpu/mali_kbase_devfreq.c | 另一个编译分支为simple_ondemand，poll100ms、30/5；不能将它当成当前5.15策略 |
| platform/devicetree/mpgpu.c、platform_gx.c | mpgpucmd的手动preheat入口存在；没有据此认定产品自动发输入boost |

既有r6只读快照显示5.15使用/sys/class/mpgpu，空闲可达250MHz。
本轮没有取得实际governor/参数/DT覆盖和boost消费者的板上新证据，因此源码对齐候选仍需验证。

## 离线改动

0008将T7默认governor由performance改为vim4，其他平台仍simple_ondemand。
独立GPL模块dvfs/governor_vim4.c通过公开linux/devfreq-governor.h接入监测，
复现上述阈值、整数取整和保持计数；交由devfreq核心应用OPP及thermal QoS上限。
支持r44降序表和核心升序表。独立模块由devfreq的governor_vim4自动加载，随候选打包。
period_ms=100、keep_count=5及五档阈值为只读模块参数，加载时可指定；不新增私有电压接口。
未复刻手动preheat命令、shader核心伸缩或平台状态机，不能宣称已复刻全部厂商策略。
performance仍可显式写入governor作诊断，完成后恢复vim4，不能作为默认验收成绩。

0009将JM的destroy_kctx_work两处及gpu_clock_control_work改用schedule_work；
7.3公开实现选择system_percpu_wq，5.15选择原系统队列，不引入自建队列生命周期。
CSF未启用，未在本轮扩展其旧调用。还需编译后检查未定义符号和故障清理实际日志。

default-parity.py在两核使用同一脚本：5分钟无GPU查询的空闲、同heap-gfx、
固定顺序DMA/GLES/CL latency/SP、各七次、每项前相同2秒间隔；探针自带预热保持一致。
保存每次频率、各thermal zone温度/类型、5分钟空闲及负载后快照、原始输出和dmesg。
汇总中位数与nearest-rank P95；七样本的P95即最大值，置信度有限，不当作高精度尾延迟结论。
单项限时，整阶段570秒；不更改governor，不将trace样本与普通性能成绩混用。

## 剩余门禁的范围

现有board/vim4-kvm-run在5.15选择厂商GE2D/NV21编码路径，在7.3才选择Wave5。
检视gst-plugin-vfmcap、gst-plugin-venc、NanoKVM/One-KVM及ustreamer源码，未发现该编码路径使用GBM BO。
ustreamer另有可选DRM passthrough，使用捕获DMA fd或dumb buffer，并非GBM渲染BO。
这支持将GBM→Wave5视为新增互操作能力，但是否属于实际部署依赖，仍待读服务参数核对，不能仅凭搜索下结论。
blob NV12的INVALID modifier仍不能猜成LINEAR；真实scanout也不能用PRIME handle成功替代。

uhd3.config明确未配置CONFIG_THERMAL_EMULATION，不能写emul_temp；
若新release也未配置，只记录绑定及离线路径，不声称温控实际触发。
若新release配置了，仅对具名GPU zone写高于95°C passive trip的温度，确认对应GPU cooling状态/频率上限，
finally立即写0恢复并核对；不写PWM、不改变trip，不触碰其他zone。

default CMA的CL六类覆盖修正已准备在私有窗口脚本中，但未运行。
dma-coherent仍保留r5的删除状态；下一窗以非coherent默认候选对比恢复该属性的独立DT，
分别跑最小及大缓冲负载，首个fault停止该项，不能把r6最小通过说成所有压力场景等价。

## 检查与下次窗口（≤30分钟）

已做：全部九块series从固定厂商源码重新git apply成功；新增补丁strict checkpatch零提示；
governor源码strict checkpatch零提示、Python AST语法、文档八项检查与git diff --check通过。
新增governor宿主测试覆盖升/降序频率表、持续负载升档、
中间负载刷新保持及低负载退档，但**尚未运行**。
遵守对方采样期间不编译：W=1/Werror、modpost、宿主C模型、完整unittest均未运行；不推未验证代码。

| 分钟预算 | 操作与停止规则 |
|---|---|
| 窗口前 | 核对新正式基线；构建/ABI/宿主/完整unittest通过，备好完整一次性启动包及两种DT；默认启动保持5.15 |
| 0–1 | 双锁独占后确认5.15、服务/UDC，保存启动文件及助手哈希、只读实际调频与产品服务参数 |
| 1–9 | 5.15同脚本5分钟空闲＋七次默认策略配对，保存温度、频率、中位数/P95 |
| 9–12 | RAM候选启动，加载零WARN门禁；API/像素与六类VK/CL（含default CMA），拒绝软件设备 |
| 12–20 | 7.3相同空闲/预热/间隔配对；默认策略性能不足即记录，不切performance补成绩 |
| 20–22 | 有emulation配置才做具名GPU thermal验证并立即恢复0；GPU＋采集编码60fps并行 |
| 22–25 | 独立coherent DT最小/大缓冲二分；首fault停项并采日志，WARN/BUG/oops或hang不恢复立即回退 |
| 25–30 | 回5.15，核对服务/UDC/所有哈希及助手，下载证据并释放锁 |

若任何预算不足，优先回退和恢复核验，不挤占30分钟上限。
API、默认策略性能、零WARN/fault、温控、60fps门禁仍待本轮实测；不提交产品路径批准方案或合并默认配置。
