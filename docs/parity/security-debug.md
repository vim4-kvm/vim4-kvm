# 安全、固件与调试

固定 [V/E 来源](sources.md)，[总表](README.md)。本页 11 项。
“无法做到”仅表示现有授权/资料/可信世界条件下无法交付，不把所有闭源固件都认作不可用。
可合法使用且协议匹配的固件应接入标准框架；风险H/M，估计为人日。

| ID / 厂商能力及来源 | 7.3 状态 | 差异与证据 | 路线、依赖 / 人日 / 风险 / 验证硬件 |
|---|---|---|---|
| Q01 TEE/OP-TEE、SMC安全加载；V2:330–350，V1:secmon/secure保留区 | 部分对齐 | E2:25/29已用T7 OP-TEE控制加载JPEG固件；不表示厂商全部TA/session/RPC/安全媒体服务可用。[JPEG/TEE](../bringup/2026-10-21-edge-scaling-jpeg.md) | 核心用Linux TEE框架、已核对的厂商SMC后端；逐服务核对参数/缓存共享与错误回收，5–10＋资料等待 / H / 匹配BL31/BL32、合法固件/TA、串口；不改板上可信固件 |
| Q02 运行时hwrng；V2:2501，C char/hw_random/meson-rng.c | 完全对齐 | E1:535使用meson-s4-rng握手，运行hwrng/CRNG已验。[RNG](../bringup/2026-10-22-edge-diag.md)。仅随机设备功能对齐，不是熵源安全认证，亦不包含KASLR | 保持hwrng框架；固定规模跨温度/冷启动统计另需2–4 / M / VIM4、可控供电/温度；不因偶发rngtest失败擅改quality |
| Q03 efuse读取/nvmem；V2:3317，V1:357 unifykey | 缺失 | E配置有NVMEM_MESON_EFUSE，但E1无本板对应启用/验收证据；通用compatible不证明T7 SMC布局正确 | 外围厂商读取后端先移植后整理nvmem provider/cells，Q01、厂商layout/权限；3–6 / H / 有已知只读字段的测试板、厂商映射；不读出敏感密钥、不烧写 |
| Q04 secure boot签名/烧录/反回滚 | 无法做到 | V2 provisionkey/secmon与厂商镜像签名格式存在，不证明本板已熔丝锁定；没有OEM私钥/烧录政策/反回滚合同，不能承诺自建内核等价安全启动 | 当前不做烧录或替代私钥；取得OEM支持后先离线签名链/可恢复开发板核对，不能在共享板验证不可逆状态。调查3–7，交付不可估 / H / 专用可牺牲样板、OEM密钥流程与恢复设备 |
| Q05 KASLR与启动早期随机种子；B bootm.c:449，V RNG路径 | 部分对齐 | CONFIG_RANDOMIZE_BASE有而固件缺种子，晚期hwrng无补救作用；固定地址/启动日志已复现。合并种子候选曾早期失败，未正式完成。[KASLR](../bringup/2026-10-22-p2-kaslr.md)、[SD方案](../bringup/2026-10-22-uboot-sd-recovery.md) | 厂商U-Boot移植后整理到标准FDT种子合同；有界真实RNG握手/BE64/独立rng-seed，先microSD再现场批准升级，3–6 / H / 串口、SD恢复、在场RESET/OOWOW；本轮禁刷引导区 |
| Q06 AES/SHA/TDES DMA硬件加速；V2:2474–2499 | 缺失 | E无本板等效Crypto DMA链验收；ARM CE指令能算SHA/AES不代表厂商DMA模块已移植 | 外围厂商实现后整理Crypto API/crypto_engine，DMA mapping/超时/算法自测；Q01/P06、4–8 / M / 已知向量、scatterlist/并发压力；不必旧私有ioctl兼容 |
| Q07 NPU闭源编译器/SDK、模型格式兼容；V7/P05 | 无法做到 | 当前未取得与kvim4n ADLA准确匹配且可交付的SDK/运行库/模型格式与授权证据。开源KMD或另一个Vivante SDK不等价于推理交付；不宣称SDK永远拿不到 | 当前不做闭源工具重写承诺；先确认可获得SDK/授权、ABI与模型转换，随后P05驱动可移植、评估通用accel。确认2–5，完整SDK替代不可估 / H / 厂商SDK/模型、相同IP板型、参考输出 |
| Q08 unifykey/defendkey/provision/密钥梯与安全服务；V1:357–531，V2:aml_mkl/aml_kt | 无法做到 | 缺TA/安全固件实现、密钥provision合同；不能用普通文件替代安全存储即宣称等效。只读公开efuse另见Q03 | 当前不做私有安全服务替代；取得文档/授权后Linux TEE/keyring/nvmem边界明确、私有ABI按消费者评估。确认3–7，实施不可估 / H / 专用测试密钥/样板与厂商TA |
| Q09 pstore/ramoops/重启诊断；V1:74，V2:ram-dump | 部分对齐 | E0:ramoops已保留1MiB，正常重启标记读回、console已部署；未用真实panic覆盖整条掉电/崩溃链。[部署](../bringup/2026-10-22-edge-pstore-deploy.md)、[M0](../bringup/2026-10-23-display-m0-r4.md) | 主线pstore/ramoops＋persistent journal；补受控crash、跨启动/保留区冲突验证，2–4 / H / 串口、现场RESET；不能为本表主动触发panic |
| Q10 厂商reg-access/iotrace/page/slab trace/DDR debug/JTAG；V2:jtag，V1:88，C memory_debug | 部分对齐 | 主线tracefs/ftrace/perf/dynamic_debug/pstore可承担部分诊断；厂商iotrace、DMC故障观测与JTAG路由未等效，CONFIG打开不代表有可用接口 | 外围确有消费者的监控先移植后整理perf/tracepoints/debugfs；S05/Q09，4–10 / H / 调试探头、串口、受控负载；裸MMIO调试ABI不作产品稳定接口 |
| Q11 厂商fake SMMU/安全DMA隔离；V1:277 smmu，V2:adla smmu属性 | 部分对齐 | E使用DMA API、restricted PCIe pool、TEE保留区；没有已证明等效的T7硬件IOMMU。厂商aml_smmu名称不是完整硬件隔离能力证明 | 先逐消费者核对fake-SMMU实际地址转换/权限；核心DMA API/genpd与安全服务边界，P05/N01/S04/Q01；5–10 / H / 厂商驱动契约、可现场恢复的DMA故障验证。无硬件隔离时不能伪造IOMMU能力 |

旧私有用户态ABI本身是兼容政策（D12），不是硬件不可实现结论；闭源应用若不愿迁移，
应标记该应用无法在当前标准接口上运行，不能把整块硬件能力一并标成“无法做到”。
