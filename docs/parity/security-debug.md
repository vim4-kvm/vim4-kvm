# 安全、固件与调试

本页管对应能力差距与验证条件；当前身份见[主线入口](../kernel-mainline.md)。
授权、可信固件和协议缺口限定当前交付条件，不把缺源码一概当作硬件不可用。
导航：[能力与边界](#能力与边界)；[范围和依赖](README.md)。

## 能力与边界

| ID / 厂商能力及来源 | 7.3 状态 | 差异与证据 | 路线、依赖与验证条件 |
|---|---|---|---|
| Q01 TEE/OP-TEE、SMC安全加载 | 部分对齐 | E2:25/29已用T7 OP-TEE控制加载JPEG固件；不表示厂商全部TA/session/RPC/安全媒体服务可用。[JPEG/TEE](../bringup/2026-10-21-edge-scaling-jpeg.md) | 核心用Linux TEE框架、已核对的厂商SMC后端；逐服务核对参数/缓存共享与错误回收，5–10＋资料等待 / H / 匹配BL31/BL32、合法固件/TA、串口；不改板上可信固件 |
| Q02 运行时hwrng | 完全对齐 | E1:535使用meson-s4-rng握手，运行hwrng/CRNG已验。[RNG](../bringup/2026-10-22-edge-diag.md)。仅随机设备功能对齐，不是熵源安全认证，亦不包含KASLR | 保持hwrng框架；固定规模跨温度/冷启动统计另需VIM4、可控供电/温度；不因偶发rngtest失败擅改quality |
| Q03 efuse读取/nvmem | 缺失 | E配置有NVMEM_MESON_EFUSE，但E1无本板对应启用/验收证据；通用compatible不证明T7 SMC布局正确 | 外围厂商读取后端先移植后整理nvmem provider/cells，Q01、厂商layout/权限；有已知只读字段的测试板、厂商映射；不读出敏感密钥、不烧写 |
| Q04 secure boot签名/烧录/反回滚 | 无法做到 | V2 provisionkey/secmon与厂商镜像签名格式存在，不证明本板已熔丝锁定；没有OEM私钥/烧录政策/反回滚合同，不能承诺自建内核等价安全启动 | 当前不做烧录或替代私钥；取得OEM支持后先离线签名链/可恢复开发板核对，不能在共享板验证不可逆状态。调查3–7，交付专用可牺牲样板、OEM密钥流程与恢复设备 |
| Q05 KASLR与启动早期随机种子；B bootm.c:449，V RNG路径 | 部分对齐 | CONFIG_RANDOMIZE_BASE有而固件缺种子，晚期hwrng无补救作用；固定地址/启动日志已复现。合并种子候选曾早期失败，未正式完成。[KASLR](../bringup/2026-10-22-p2-kaslr.md)、[SD方案](../bringup/2026-10-22-uboot-sd-recovery.md) | 厂商U-Boot移植后整理到标准FDT种子合同；有界真实RNG握手/BE64/独立rng-seed，先microSD再现场批准升级，串口、SD恢复、在场RESET/OOWOW；本轮禁刷引导区 |
| Q06 AES/SHA/TDES DMA硬件加速 | 缺失 | E无本板等效Crypto DMA链验收；ARM CE指令能算SHA/AES不代表厂商DMA模块已移植 | 外围厂商实现后整理Crypto API/crypto_engine，DMA mapping/超时/算法自测；Q01/P06、已知向量、scatterlist/并发压力；不必旧私有ioctl兼容 |
| Q07 NPU闭源编译器/SDK、模型格式兼容 | 部分对齐 | ADLA兼容驱动已合入，现有SDK三模型输出已与5.15核验，见[运行合同](../npu-adla.md)。官方vim4_npu_sdk提供转换器/编译器，不能继续记成SDK不可获得；完整转换链、版本适配与再分发条件尚未验收 | 复用已验SDK与模型，按[候选输入说明](../../packaging/security-media/README.md)追踪上游工具；补模型转换、匹配运行库与参考输出，再评估通用accel；闭源工具不作自行重写承诺 |
| Q08 unifykey/defendkey/provision/密钥梯与安全服务 | 无法做到 | 缺TA/安全固件实现、密钥provision合同；不能用普通文件替代安全存储即宣称等效。只读公开efuse另见Q03 | 当前不做私有安全服务替代；取得文档/授权后Linux TEE/keyring/nvmem边界明确、私有ABI按消费者评估。确认3–7，实施专用测试密钥/样板与厂商TA |
| Q09 pstore/ramoops/重启诊断 | 部分对齐 | E0:ramoops已保留1MiB，正常重启标记读回、console已部署；未用真实panic覆盖整条掉电/崩溃链。[部署](../bringup/2026-10-22-edge-pstore-deploy.md)、[M0](../bringup/2026-10-23-display-m0-r4.md) | 主线pstore/ramoops＋persistent journal；补受控crash、跨启动/保留区冲突验证，串口、现场RESET；不能为本表主动触发panic |
| Q10 厂商reg-access/iotrace/page/slab trace/DDR debug/JTAG | 部分对齐 | 主线tracefs/ftrace/perf/dynamic_debug/pstore可承担部分诊断；厂商iotrace、DMC故障观测与JTAG路由未等效，CONFIG打开不代表有可用接口 | 外围确有消费者的监控先移植后整理perf/tracepoints/debugfs；S05/Q09，调试探头、串口、受控负载；裸MMIO调试ABI不作产品稳定接口 |
| Q11 厂商fake SMMU/安全DMA隔离 | 部分对齐 | E使用DMA API、restricted PCIe pool、TEE保留区；没有已证明等效的T7硬件IOMMU。厂商aml_smmu名称不是完整硬件隔离能力证明 | 先逐消费者核对fake-SMMU实际地址转换/权限；核心DMA API/genpd与安全服务边界，P05/N01/S04/Q01；厂商驱动契约、可现场恢复的DMA故障验证。无硬件隔离时不能伪造IOMMU能力 |

旧私有用户态ABI本身是兼容政策（D12），不是硬件不可实现结论；闭源应用若不愿迁移，
应标记该应用无法在当前标准接口上运行，不能把整块硬件能力一并标成“无法做到”。
