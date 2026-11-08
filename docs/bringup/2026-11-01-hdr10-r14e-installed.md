# 2026-11-01：r14e持久安装，交用户手测

后续按用户明确授权，六组件及主仓 HDR/r14e、MAC、音频修复已收尾合入，
见[合入清单](2026-11-01-p0-hdr-final-merge.md)。r14e 原封包身份不变，
当前 One-KVM 另由音频 overlay覆盖运行；
下文安装时的“暂不合入”与默认5.15等历史表述不替代最新授权和实际安装状态，未验边界不变。

后续MAC修复已复审并部署，当前管理页恢复为
**http://192.168.50.210**，MAC与5.15一致。下文192.168.50.162及MAC差异保留为初次安装历史，
不代表当前仍未修复；r14e与默认uhd6/kbase、未验范围不变。

用户明确授权持久安装r14e、改默认为7.3并正常重启。现已运行且默认
`7.3.0-vim4kvm-uhd6+`，kbase配置；**仅安装健全检查通过，不是第二阶段功能验收通过**。
本轮不操作M6，不运行HDR/尺寸/性能矩阵，不自动合主线或发布Release。

## 安装身份

- 内核正式提交 `f951e2d24d32d5df0e701e7c355b3db4c91eaf74`；真实GNU ID
  `48106f6f9fb09b12d1eaf6a5fe91953dba53d9cb`。已安装Image、双DT、BTF与全部2341模块逐文件匹配，复用而未重装。
- 正式内核归档SHA256 `7e68dc27e46bb270d561f4307bba1cd947152ee3813a0a926f817f11f8e9dfc6`。
- r14e原用户态归档SHA256 `9069fc083a8afe1a139e6d3e5eb725c608afafb4245ec3b155f873fd3f4a5b90`。
- 持久安装包 `build/p0-5/hdr10-r14e-persistent-r1.tar.gz`，SHA256
  `034ace4fb6a041029ec17a353e02d83e1bf89c183c6751c52b0bf263b84c4897`，40项程序/网页/插件/启动资源。

| 组件 | 固定来源 |
|---|---|
| gst-venc | `3a74cc9c0f074ff8bf980440e426438bba65d1db` |
| gst-vfmcap，含Pi NV12引用修复 | `5de382e36350fc37b43d9ff11f693fa3f2bb0323` |
| One-KVM | `50f0b4d433c0ebb8c83f806f49084622547afe99` |
| NanoKVM | `0525dea7d5d2417b3b5c5eee754f026d9ca4c671` |
| JetKVM | `166719c5b8acdfb1ab995c440aabc8a0e39ae08d` |
| uStreamer | `97eb951d10a0ccebd312d6951acc91624f5f0876` |

真实文件安装于`/opt/vim4-kvm/hdr10-r14e`；没有RAM目录bind。
`/usr/libexec/vim4-kvm-run`仅对uhd6选择该目录，继续使用既有kbase GPU包装器；
Panfrost DT和私有PanVK选择路径保留。5.15原程序、应用数据、配置及/lib→usr/lib符号链接保留。
Pi只在私有默认配置中将ustreamer指向新程序，保留原override设置；私有Janus插件与之配套。
NanoKVM网页资源与私有可执行程序位于同一真实目录，避免os.Executable查找失败。

安装收据`/etc/vim4-kvm/hdr10-r14e.json`标明user-manual-test-candidate和未验项；
`/etc/vim4-kvm/runtime-build.json`同步实际内核、默认、模块/配置摘要与组件来源，保留原包版本/管理器记录。
备份`/var/lib/vim4-kvm/before-hdr10-r14e-1793531523151928872`。

## 就绪核验与网络地址

安装后经现有kernel-select入口改默认FullKvm，正常重启；cmdline无私有init，非RAM候选启动。
当前入口 **http://192.168.50.162**。管理器、One-KVM、HDMI、gadget active，UDC configured；
80/8081 HTTP 200，8080未登录401符合鉴权行为。两内核均登记可用，7.3为默认。

旧地址192.168.50.210不可达使原等待脚本超时；串口确认系统已启动、NetworkManager取得
192.168.50.162，然后在新地址完成核验，没有为此再次重启或修改网络配置。
5.15留存MAC `c8:63:14:74:70:0d`；当前7.3为`02:ad:36:01:89:77`，与U-Boot sec_reg读数一致。
先前RAM窗口临时setenv沿用5.15 MAC，因此未显示此差异。
**同板跨内核MAC尚未统一是已知迁移缺口，不作为正常最终产品行为**；本安装不扩展处理网络配置。

9个关键实际加载模块的GNU ID和文件SHA匹配同次构建：mali_kbase、vim4_kbase_heaps、
governor_vim4、wave5、t7_hdmirx、t7_vdin_test、t7_jpeg、crg_udc、dwmac_meson8b。
taint=4096，仅kbase外部模块位；不把它写成taint零。
真实One-KVM子进程SHA256 `79678cbff6ab7885de3fb0aff6f3c9ec229ea63aa1f217e7ebafb12853d6162a`。
systemd MainPID为Python GPU包装器，按服务cgroup识别程序子进程，不误把包装器当应用。

四应用服务与程序已登记、可选择，未逐一启动验证。所有私有插件实际gst-inspect加载的
factory路径核对通过，包括硬件生成的v4l2h265enc/v4l2h264enc；私有目录逐文件SHA匹配。
未打开观看者，One-KVM进程没有常驻视频插件映射；这不是实际HDR接收或GPU转换验收。
日志中有ADLAK诊断WARN、iwconfig弃用提示等启动日志，完整保留，不宣称零日志警告。

交付前完整446项unittest通过、15跳过；含GPU包装器PID核验的3项定向回归通过。
依赖/factory在ARM64容器检查；容器缺少的libevent/libevent_pthreads/libspeexdsp均已确认板上现有。

## 证据与待手测

- 原安装/正常重启：`logs/hdr10-r14e-persistent-user-test/`，含串口、安装成功和旧地址超时日志。
- 实际系统身份/模块/程序/插件：`logs/hdr10-r14e-installed-sanity-r2/sanity.json`。
- 最终内核选择/HTTP/源状态/服务/UDC/dmesg：`logs/hdr10-r14e-install-final/`。
- M6未操作，读到源HDR=False；不复验原前台。所有票据和临时串口进程已退出。

保留[此前真实证据](2026-11-01-hdr10-phase2-uhd6.md)：One-KVM/Panfrost180秒和Nano/Jet八份码流。
Pi修复后有限VDIN池持续映射/JPEG/往返、kbase原生收发、UU真实客户端HDR及CMA仍待手测，
非零静态元数据/HLG/动态HDR无真实源未验。RR或官方窗口呈现不代表独立HDR渲染/解码帧率。
用户手测候选保持此边界，不自动合主线，不继续排自动测试。
