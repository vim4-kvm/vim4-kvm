# 2026-10-30：uhd3 GPU候选与HDR离屏窗口A

执行[HDR规格](../gpu-hdr-pipeline.md)。用户已于2026-10-30确认上游Panfrost＋Mesa为准，libmali仅临时后备。
本轮未push、未测试窗口B，不发HID、不测声音、不ptrace视频进程，不写PWM/电压、不盲读寄存器。

## 分支、构建与入场

原型分支675cbd8完整保存在Git，worktree已移到持久目录`/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm-gpu-hdr`，
rebase至main@14cc2b2，原型提交变为6babfc3；文件未丢失。
GPU分支`vim4-gpu-panfrost@52ad11da91f3c`基于正式f71b5c6289cb，保留012c8fa cooling、4c53dfe 10ms、24628b6 QoS及等价workqueue修正。
快轮询不在新候选历史中；旧分支归档仅供追溯，未加入运行载荷。
只用临时配置副本派生release **7.3.0-vim4kvm-uhd3-gpu1+**，未覆盖uhd3文件或改正式配置。

完整Image/dtbs/modules成功，2338模块；Panfrost W=1/C=2、PM/boost夹具与strict checkpatch通过。
新Image build ID `1e87e8644e9827d67592bdc6a8d4e3758f6b8f58`；使用同构建display-m0 DTB与完整模块。
内核暂存tar SHA256 `81090e44e35f6df7dac5a9b25e3b8dd107836104fc32557a517d98a23f245d53`，板端Image/DTB/init/runtime清单逐项校验通过。
GBM原型ELF SHA256 `149f3d097438fc5d26bf2737eedb56d52a77742035d435f82182c619da78834b`；shader仍为规格中的06506ca6…版本。
候选PID1验证release/build ID后只读挂载私有模块，并只读bind五个只增加候选release准入的runtime副本。
不替换磁盘上的正式helper；重启自动撤销。候选目录为`/var/lib/vim4-kvm/display-m1/1e87e8644e9827d67592bdc6a8d4e3758f6b8f58`。

board→heavy独占锁覆盖上板；入场5.15.137-vim4kvm-hdrdual6，三服务active、UDC configured。
所有本轮编译在首项测量前结束；窗口内不编译。U-Boot RAM sysboot启动，没有saveenv。
候选通过DHCP获得192.168.50.162，固定SSH别名仍指.210；串口确认身份/服务后以原host key显式连接.162。
未修改网络配置或热解绑网卡；串口首次在login提示符发送shell命令未执行，登录后才读取地址。

## 同负载门禁与吞吐

两端使用同一ARM64程序、同一GLES310 compute、同一seed生成的P010输入，GPU_HDR_RENDER_NODE指定renderD128。
5.15逐进程libmali；7.3逐进程GCM Mesa26.2.6（ES3.1），没有使用完整编译器系列或软件renderer。
SSBO一次上传，三次预热后每轮30次dispatch＋glFinish，回读不计时；三轮配对，单项90秒超时。
**这不是采集→GPU→编码端到端，也不是零拷贝；不包含上传和CPU回读成本。**

两端五个固定小帧对CPU双精度参考均最大1码，未超过既定2码容差；
4K白帧NV12全帧与Y235/UV128参考逐字节一致。GPU timeout/fault零增量后才执行吞吐项。
离线比较两端最后一轮随机输出：4K的12,441,600字节中120字节不同，1080p的3,110,400字节中19字节不同，最大差均为1码。
随机4K吞吐输出未生成完整CPU逐像素oracle，不能把白帧通过扩展成所有真实HDR画面已验收。

| dispatch＋wait ms，三轮 | 5.15 libmali GLES | 7.3 GCM GLES |
|---|---:|---:|
| P010 4K→NV12 4K | 46.763 / 46.818 / 46.903 | 78.490 / 78.518 / 78.493 |
| 均值 / 吞吐 | 46.828 / 21.35fps | 78.500 / 12.74fps |
| 三轮最大单帧 | 47.586 | 79.005 |
| P010 4K→NV12 1080p | 16.011 / 15.908 / 15.918 | 18.326 / 18.267 / 18.345 |
| 均值 / 吞吐 | 15.946 / 62.71fps | 18.313 / 54.61fps |
| 三轮最大单帧 | 16.374 | 18.758 |

7.3耗时为厂商约1.68倍/1.15倍；4K在两端都失败，1080p七系也不足60fps，更未达到GPU p99≤8ms工程目标。
不能把厂商现有Vulkan AMLY→P010保真缩放当作相同tone-map基线：它不包含PQ解码、色域和肩部映射，输出也不同。
本轮没有相同负载的厂商Vulkan计时；提供的是相同shader的厂商GLES对照，不使用历史7ms保真结果相除。
下一优先级应是产品shader的LUT、工作划分、寄存器/带宽优化；不恢复编译器试验来掩盖算法本身的成本。

## 离线接口候选及尚缺部分

独立内核worktree `~/src/linux-7.3-gpu-raw`、分支`vim4-gpu-raw-capture@8f66386161f42`基于f71b5c6289cb。
新增`t7_hdmirx_get_stream_color`在stream lease锁下复制depth/space/colorimetry/range/PQ分类；
无lease返回ENODATA、legacy不完整分类返回EOPNOTSUPP，不猜10位默认值。
驱动目录W=1编译、实际函数准入/快照夹具、strict checkpatch零诊断。**没有上板，也没有启用十位写出。**
该快照只含现有接收器分类，仍缺完整extended colorimetry、chroma site和HDR静态元数据，不能冒充完整帧描述符。

源码证据：f71的`t7-vdin-test.c:1049–1069、1578`只输出NV12/RGB24；
厂商`common_drivers/drivers/media/vin/tvin/vdin/vdin_ctl.c:2351–2361、2413、5033–5043`使用full-packed422和10bit mode，
`vdin_regs.h:297`描述WR_CTRL2 bit19，`vdin_ctl.h:135`的full-pack枚举为3。
但这些不证明当前T7接收前级、double-write和内存字节序已满足同一合同；厂商V4L路径还会强制八位。
因此未临时打开这些位或将AMLY标成P010/Y210。

采集实现方案：先证明源位深在前级没有被截断，旁路HDR2并保留帧级PQ/range；
full-packed422按每两像素5字节、16字节行对齐导出一个dma-buf，原始排列必须显式声明。
正式标准格式优先Y210/P010，需硬件或GPU重排；不能用私有AMLY字节排列冒充标准fourcc。
目前这个原始写出接口尚未实现，是窗口B的硬阻塞。

[hdr-dmabuf.c/h](../../packaging/gpu/hdr-dmabuf.c)为外部可写buffer候选：检查实际fd容量、VkBuffer requirements及memoryType交集，
dup后导入、失败回收未提交对象，显式EXTERNAL queue ownership；借用原fd并保留上游lease，不做CPU映射。
retire遇未完成fence或device lost拒绝释放，夹具覆盖这三种结果；ARM64 Werror编译通过，真实导入尚未执行。
该候选要求支持对应Vulkan外部内存API，不能因为G52已有uint导入探针就宣称完整新路径通过。
[hdr-vulkan.py](../../packaging/gpu/hdr-vulkan.py)由唯一颜色shader生成push-constant版本，SPIR-V编译/校验通过，未运行新Vulkan调度器。

Wave5交接方案复用`gst-plugin-venc/wave5/nv12-planes.c:9–52`：GPU输出fd保留GstBuffer parent lease，
visible NV12的UV物理偏移仍是width×height；额外tail容量按编码器16行对齐预留。
两段GstMemory拼接的VideoMeta偏移不是把物理UV移到对齐高度；不要混淆二者。
GPU fence完成后才能交编码，编码DQBUF/退休后才能归还池；输入只在GPU完成后QBUF。
新DMA池、实际GPU调度与插件接入未实现，不能仅凭导入助手宣布Wave5交接完成；HLG仍未实现。

## 并发与回退

停止One-KVM独占编码器，无GPU/有GPU各60秒、3840×2160 NV12→H.264、预热120＋测3600帧。
有GPU组用本原型两次500帧4K tone-map负载，总约79秒，两次之间含一次重新上传/上下文创建；不是新零拷贝后端。

| 指标 | 无GPU | HDR文件GPU负载并发 |
|---|---:|---:|
| FPS | 60.010381 | 60.003116 |
| source→encoded p99 ms | 19.489 | 19.496 |
| 整机CPU% | 2.585 | 2.670 |
| 收尾CMA KiB | 505200 | 505200 |

两组各3720输入/输出帧、success=true；GPU后台两次正常退出，最终taint=0、GPU timeout/fault零增量。
该视频工具no-payload-read，不验证运动像素/码流；并发只是离屏GPU与真实NV12采集编码并存，不是HDR真实帧交接。
退出候选min/max=250/800MHz、polling=10ms、PM auto，未改变频率上下限。单项10/90秒等超时、并发批次240秒，测量未超20分钟。

最终5.15.137-vim4kvm-hdrdual6，boot ID `6f178472-62c7-4836-b31e-e810c90f36a1`；
One-KVM/HDMI/manager active、UDC configured。七文件SHA全部OK，临时runtime绑定随重启撤销，板锁已释放。
窗口B未执行，须另经用户决定；raw10写出、实际GPU调度/池及Wave5接入是其阻塞。
剩余估计8–14工程日，色彩/HLG另2–3日；首轮数据未达4K60，需先验证LUT/工作划分优化，再承诺性能。
主仓全量unittest：315项、跳过13项、无失败；候选未合入main，未push。
原始JSON、固定帧、串口、状态在`logs/gpu-hdr-A/`，脚本/内核归档在`build/gpu-hdr-A/`。
