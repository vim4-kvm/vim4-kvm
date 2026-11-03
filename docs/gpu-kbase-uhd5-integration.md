# uhd5 kbase产品路径：正式集成清单

[r12完整包与回退](bringup/2026-10-31-kbase-r12-package.md)已验证正常候选一次回5.15的DHCP/SSH/服务/UDC/哈希。
用户批准据此最小GPU烟测正式合入，准确锁定产物，未验范围明确保留；
最终来源与验收范围见[正式合入记录](bringup/2026-10-31-uhd5-main-integration.md)。

[r11](bringup/2026-10-31-kbase-r11-policy.md)的默认策略性能、API、六类内存、mpgpu、温控和
One-KVM 4K60并行达到本轮门槛。负向dma-coherent DT不可用；5.15回退曾需额外正常重启恢复DHCP。
正式sources.toml登记uhd5，保留旧uhd4/Panfrost；5.15仍默认，不宣称所有故障回退已修复。

## 合入范围

主仓gpu-kbase-7x：ca6a1cb整理r7/r9外部模块及uhd4基线，9503496修正governor前置依赖，
1f8c2d9补实际厂商策略与24240组合差分回归；9b7419f及本轮记录说明验收边界。
7df8fa4仅同步已在main的be81255工具，不再维护分叉工具。e4b4cbf/fa060d7补充有界回退及
严格cmdline比较，1865953记录正式封包烟测。独立worktree从最新main合并，
不启用中间候选的坏DT或旧performance默认。

内核feature分支已保存aed3edb3a7eed（uhd4基线）及9e1726aeb4b3f（r10记录），本轮补充验收记录。
它没有将DDK放进内核树。当前已测Image精确基于8bca939d6bbd3，生成器从正式display-m0 DT副本
产生GPU候选；因此可保持正式kernel.revision=8bca939d6bbd3，不必为启用kbase合入新的内核C代码。
如要合入内核分支中的独立DTS审阅副本，需另列其生成提交；不能把现有Image冒称由后续doc/DT提交构建。

## 正式锁定产物

保留原uhd4的源码/产物证据，新增明确uhd5记录；不能仅改release字段而沿用uhd4模块。
Image与完整基础2338模块来自r10同次构建，加入三个匹配外部模块，生成完整depmod/BTF清单。
完整封包与2341个模块GNU build ID已登记；清单中的包内ID不冒称全部模块都实际加载。

| 固定项 | 值 |
|---|---|
| kernel源码 | 8bca939d6bbd3e4d91e9f23b812e920172c99b3d |
| 外部模块源码（主仓） | 1f8c2d9dc105aa94efc6fa0885a9aed2b7605ee5 |
| 完整包SHA256 | 174cf528c8e12a4fa71c5adbf42c95bc39ba987e4ba6133db7b5912e2da85b0b |
| release / build ID | 7.3.0-vim4kvm-uhd5+ / 90cc3dc2ddd1ad2562bf07e8de65f96eeb092a90 |
| Image SHA256 | 2cbe6ed9db6337d24468e5a73b17fbe78f769b5aa2490f0dcc17e08b94a93f66 |
| config SHA256 | 9dd8d44d56a68600fa9a9f2b5bed4a8b0fd3b1b727077bd4c12f683975216289 |
| candidate DTB SHA256 | 0247cd50be9690d3925a4ea7c95dabb18f4ed045b9d5c1dda17b85abdabeddda |
| mali_kbase.ko SHA256 | ace22d7c966cbe4bacb3608ffa63fcc9d2cdb0bbd8e5c818f8bc22a7367aa8d3 |
| vim4_kbase_heaps.ko SHA256 | 4fea6f5fc709dbc50dbfa077069daccc47a73aaeecbca5dd2da3aae003a8da58 |
| governor_vim4.ko SHA256 | dfc0e243f39c7117ce00bce5291a6c3034a957fcefcdbcdfc1ad24ff5b97b0be |
| 外部构建manifest SHA256 | 4ceb6bd0a632c9c1da665a3812f9c4a860c5b021751024438fdcd5de7dd2101a |
| libmali SHA256 / UK | 536ee80c17dc5c54e7c6ff029ca43270da8efc3fdc5b3aeb263f364419368494 / 11.39 |

[sources.toml](../packaging/kernel-edge/sources.toml)锁定完整uhd5.config、Module.symvers/BTF摘要、
完整模块清单、外部模块源提交与manifest、两套DT及runtime helper清单。
[runtime登记](../packaging/kbase/uhd5-runtime.json)固定用户态UK/SHA与驱动选择。
保持现有One-KVM/GStreamer正式pin，不借此改变HDR2、NPU、USB或信源。

## DT、用户态与分发

保留Panfrost/Mesa路径。两个独立DT按启动项选择：kbase DT使用专用compatible，保持system-coherency=0、
删除dma-coherent、持有T7电源域，加入独立WC heaps和GPU cooling map；Panfrost DT保持原状。
同一GPU节点只能由一个驱动绑定，kbase启动项另加panfrost黑名单，不能写全局黑名单影响Mesa启动项。
继续使用vim4默认五档100ms策略与softdep，不将performance设为默认；thermal QoS始终约束目标频率。

按实际绑定驱动选择用户态：kbase使用固定UK11.39 blob，Panfrost使用Mesa。
Vulkan/OpenCL采用逐进程ICD目录和loader变量；GLES进程使用同blob的私有EGL/GLES/GBM前缀。
此blob无__egl_Main，不能注册为GLVND EGL vendor，不覆盖系统Mesa/alternatives，不做假JSON或shim。
既有provision/探针校验libdrm/Wayland依赖闭包，禁止同进程混入两个GBM实现；本次不运行安装器。

可分发GPL模块、完整对应源码与补丁/配置/构建说明；libmali及专有固件不随Git或公开包推送。
沿用私有provision流程核授权来源/许可证和固定SHA，设备已有合法blob才激活；缺失或UK不匹配应明确拒绝。
不将未来r4x/r5x DDK与当前blob混用，升级仍须逐字节UAPI和同板回归。

## 回退和剩余范围

保留5.15及uhd4/Panfrost启动项，当前仅RAM一次性验证，未持久安装或切换新内核。
正常候选一次回退已通过，无串口补救；负向故障DT后的DHCP残留机制未定位，不声称所有故障回退可靠。
strict cmdline只允许已审的normal/watchdog_reboot差异，其他参数及保护哈希/build ID检查保持严格。
NPU资产缺失、HDR2查询超时、manager认证响应本轮未验，按用户批准范围不作为GPU合入前置。
温控emulation已清0；未测仪器功耗、长时间稳定性、系统suspend或CTS。
实际GBM scanout/GBM→Wave5布局合同仍为额外能力，不是现有5.15产品路径的替代验收。

小版本维护按API兼容层→T7平台→DVFS/thermal→候选DT逐主题重放，保持blob/UK绑定。
重跑差分状态机、ABI、W=1/Werror、完整unittest，再上板同协议配对/六类内存/温控/服务并行/回退。
只改外部模块时沿用准确匹配的Image/BTF；跨内核构建则必须重新固定完整模块集。
