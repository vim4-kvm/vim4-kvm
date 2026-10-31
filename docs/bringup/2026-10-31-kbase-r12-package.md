# 2026-10-31：uhd5封包、正常回退与推广阻塞

结论：已封存完整uhd5包，正常DT一次RAM启动→一次回默认5.15的SSH/DHCP/四服务/UDC/保护哈希
验证通过，没有串口补救。r11负向DT后网口残留的具体机制仍未定位；本轮NPU/HDR2与manager检查
也没有完整通过。按用户门禁**只推特性分支，不合main，不改sources.toml正式锁，不发布Release或改默认**。
原生HDR由既有hdr10会话独立执行，本会话没有操作其工作树或替它宣称验收通过。

## 回退证据与流程

r11串口：5.15内核确已运行，四服务active、carrier=1、MAC仍c8:63:14:74:70:0d，eth0没有IPv4。
NetworkManager日志显示真实DHCP事务反复超时，最终ip-config-unavailable；不是只有SSH探测过早，
也不是cmdline严格比对造成假失败。现有证据不能区分MAC/PHY/共享总线的具体残留机制。
较早[DDC记录](2026-10-19-hdmirx-ddc.md#恢复与限制)也见过carrier正常但无RX的回退故障，
不能据此就认定r11必为同一原因。没有重复故障DT、热解绑网卡或改用户网络配置。

board-window现在只发起一次正常返回重启，超时失败并保留UART/proof，不自动无限重启。
5.15就绪要求One-KVM、HDMI、gadget、manager和configured UDC；期望release明确传入就绪检查。
返回后的真实build ID、release和保护文件继续严格比较。
仅审阅reboot_mode=normal与watchdog_reboot之间的变化，分别记前后值；
未知reason只能原样保留，重复、新增、删除或其他cmdline token/顺序变化仍拒绝。
回归包含build ID/文件/release不匹配、init参数注入、重复及未知reason拒绝。
特性提交e4b4cbf、fa060d7；完整unittest359项通过，11项环境跳过。

本轮等待HDR10正常释放票据后才取得板子，不抢锁。正常候选窗口约15:43:32–15:48:37 UTC，
main版board-window走完整boot-candidate/collect/return-baseline，无人工串口、无额外重启。
返回NM状态connected，DHCP服务器192.168.50.1、地址192.168.50.210/24、有有效动态租约；
RX=1032、TX=1156、RX/TX错误均0。四服务active、UDC configured；八项启动/登记文件SHA、
原5.15真实build ID、五个临时助手恢复均通过。
reboot_mode由normal变watchdog_reboot已审计，其余cmdline参数完全一致。
本会话票据与临时进程释放后，hdr10取得下一票据，未再访问板子。

这一正常回退成功缩小了复现范围，但不能证明r11故障路径已修复，因此暂不正式推广。

## 完整包身份

新packaging/kbase/package.py只封存既有构建，不编Image、不安装或接触硬件。
核对干净生成源码HEAD为8bca939d6bbd3e4d91e9f23b812e920172c99b3d，绝不以文档提交冒称Image来源。
保留2338个基础模块+3个外部模块、完整depmod清单、2341个模块GNU build ID、vermagic及BTF；
另将每个基础模块build ID与原构建O=目录的未剥离模块逐项比对，全部一致。
后续审计重封档只在modules.tar.gz元数据上不同；模块逐文件SHA/build ID与原封存包完全一致，
不拿新封档代替已测试原封存身份。

| 项目 | 值 |
|---|---|
| release / build ID | 7.3.0-vim4kvm-uhd5+ / 90cc3dc2ddd1ad2562bf07e8de65f96eeb092a90 |
| Image SHA256 | 2cbe6ed9db6337d24468e5a73b17fbe78f769b5aa2490f0dcc17e08b94a93f66 |
| 原封存包SHA256 | 174cf528c8e12a4fa71c5adbf42c95bc39ba987e4ba6133db7b5912e2da85b0b |
| 原包manifest SHA256 | 4918334197a87f5ecd1e9e64e0e02041cb43d2f5ea46fe4f7932ef7e04bf3c10 |
| 独立vmlinux.btf SHA256 | 8afa7bcc52351993c3efebb2b5b42575c02bec5939cf6c9ac3f329a3b82087cc |

VM封存~/build/uhd5-final-r12.tar.gz，54862373字节；manifest在同名目录。
包含Image、kbase DT、独立Panfrost DT、config、Module.symvers、vmlinux.btf、modules.tar.gz、
runtime助手及外部构建manifest。RAM封套逐文件证明Image/DT/全部模块等同封存内容，额外PID1仅用于测试。
生成编译器GCC13.3.0（Ubuntu6ubuntu2~24.04.1）、binutils2.42、aarch64；
UTS_VERSION为#13 SMP PREEMPT Sat Oct31 21:26:55 +08 2026，原始头文件记录在build-environment.txt。
保留uhd4与Panfrost选项，只有kbase DT绑定私有compatible；按驱动选择ICD/EGL前缀。
包中没有libmali或外部固件，不覆盖Mesa、不生成GLVND假vendor；既有UK11.39/SHA校验沿用。

## 最终包回归范围

EGL1.5/GLES3.2像素正确、VK1.3.231、CL设备/C3.0及六类VK/CL内存通过，默认250MHz，
mpgpu忙闲检查通过。连续GLES与实际One-KVM网页并发35秒，全部帧3840×2160、约59.91fps；
候选日志无新增kernel WARN/BUG/oops/GPU fault。不重跑r11已审阅的七轮性能。

NPU脚本未找到预期目录中的可配对5.15报告/模型，没有执行三模型，不引用旧结果充当本轮通过。
随后HDR2 /api/vim4/video在3秒预算内超时，脚本报告未完整落盘；该子阶段失败并单列，
仍继续独立GPU网页并行及正常回退。故本轮没有完成HDR2专项验收，也不重复故障DT来补证据。
可选manager检查：现有网关status入口404、直接认证入口401，未建立可信API/mpgpu配对；
没有部署575538e、改UI或试图绕过认证。该分支的新debugfs fallback仍只保留原离线范围。

接下来仅处理这两项集成所必需的剩余门禁：明确故障后网络残留机制、定位既有NPU基准资产及
HDR2状态查询的有界路径；manager取数若仍无合法入口则维持未验证，不扩展应用功能。
不安排透传、独立解码、额外性能调优等新任务。

证据：logs/kbase-r12/（封包、编译环境、359项测试、原manifest及基础模块审计），
logs/kbase-r12-window/（UART、API、网页接收、NM租约/计数、returned-baseline-identity.json、final.json、失败子阶段）。
