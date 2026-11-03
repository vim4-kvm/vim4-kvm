# 2026-10-31：uhd5 GPU正式来源锁与最小烟测合入

用户审阅r11/r12后批准按已通过的GPU最小烟测合入主线，不扩大板测范围。本次仅登记正式源码、
配置、完整包与运行时选择合同；不部署、不发布GitHub Release、不改变5.15默认启动。
原生HDR由并行会话处理，其未通过候选未进入本次GPU锁。r11/r12原始记录保留，不覆盖历史失败。

## 正式身份

- [sources.toml](../../packaging/kernel-edge/sources.toml)的tested_build为7.3.0-vim4kvm-uhd5+。
  Image源码仍为正式内核8bca939d6bbd3e4d91e9f23b812e920172c99b3d；内核正式分支无需新增代码，
  不把后续文档或独立DTS审阅提交冒称Image来源。
- build ID：90cc3dc2ddd1ad2562bf07e8de65f96eeb092a90；外部模块源码为主仓
  1f8c2d9dc105aa94efc6fa0885a9aed2b7605ee5，补丁及governor/heaps源码摘要另有逐文件校验。
- 已烟测封包uhd5-final-r12.tar.gz，SHA256：
  174cf528c8e12a4fa71c5adbf42c95bc39ba987e4ba6133db7b5912e2da85b0b。
  包含Image、互斥的kbase/Panfrost DT、2338基础模块和三个外部模块、depmod、BTF与构建清单。
- [完整清单](../../packaging/kbase/uhd5-manifest.json)锁定2341个模块的摘要和GNU build ID；
  [外部清单](../../packaging/kbase/uhd5-external-manifest.json)、
  [运行时文件清单](../../packaging/kbase/uhd5-runtime-files.json)、
  [完整配置](../../packaging/kernel-edge/uhd5.config)随仓库保存。
  包与二进制不随本次Git推送；已封存包保留在构建VM的/home/deepdream/build/uhd5-final-r12.tar.gz。

## 已验范围

[r11同协议七轮](2026-10-31-kbase-r11-policy.md)复用匹配5.15基线，默认250MHz、厂商等价100ms五档策略：

| 项目，中位数 / P95 | 5.15 libmali | uhd5 kbase/libmali |
|---|---|---|
| DMA submit_wait，ms | 1.692 / 3.618 | 1.535 / 3.570 |
| GLES，FPS | 616.361 / 617.773 | 646.280 / 648.065 |
| CL latency，µs | 78.32 / 79.14 | 53.19 / 56.54 |
| CL SP，GFLOPS | 101.69 / 101.71 | 101.74 / 101.76 |

[r12正式封包烟测](2026-10-31-kbase-r12-package.md)通过API/像素、六类内存、mpgpu、连续GPU负载与
实际网页3840×2160并行（35秒59.91fps）、零新增WARN/fault；正常候选一次回5.15后DHCP/SSH、
四服务、UDC、八项保护哈希及临时助手恢复核验通过，无串口补救。
API为EGL1.5、GLES3.2、Vulkan1.3.231、OpenCL设备/C3.0；不代表CTS。
五档调频和thermal emulation限频/恢复见r11，未用performance governor替代默认策略。

## 运行时与边界

[运行时登记](../../packaging/kbase/uhd5-runtime.json)明确installed=false、default_boot=5.15。
uhd4/Panfrost旧锁完整保留；uhd5也附独立Panfrost DT。kbase DT关闭Panfrost，仅该启动配置使用
Panfrost黑名单，现有启动项不变。助手按实际绑定驱动选择私有Vulkan/OpenCL ICD与EGL/GLES/GBM前缀；
系统Mesa保留，blob无__egl_Main，不注册假GLVND vendor或shim。
libmali/专有固件沿用既有合法provision，固定SHA、UK11.39与依赖闭包，不进Git或公开包。

r12 NPU资产缺失未测、HDR2查询超时、manager认证响应未验证；它们是本轮未验边界，
按用户批准范围不作为此次GPU合入前置。实际GBM scanout/GBM→Wave5、系统suspend、功耗和长稳也未验。
r11负向dma-coherent DT故障后5.15曾需第二次正常重启恢复DHCP，残留机制仍未定位；
正常候选回退通过不能证明所有故障回退已修复。本轮不重复故障DT，不改网络配置或热解绑网卡。
回退保持有界就绪等待、真实build ID和保护文件严格检查；cmdline只单独允许已审正常/看门狗reboot_mode差异。

此次独立集成worktree合并已验证GPU功能与必要工具修复，完整离线unittest另核配置、完整模块集、
外部源码与产物锁一致性。没有新增板窗或扩大性能验收；合入与推送后停止本会话工作。
