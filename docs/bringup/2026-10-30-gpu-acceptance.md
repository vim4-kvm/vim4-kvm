# 2026-10-30：GPU 三栈上板验收

结论：未达到厂商5.15的功能与性能目标。7.3私有Mesa补齐了可运行的实验PanVK和
Rusticl，但设备Vulkan仅1.0、GLES仅3.1，固定GLES负载约为厂商的37.5%；
CL完整基准在map阶段超时。GPU默认cooling绑定、五档调频、runtime恢复和
HDMI/Wave5并行窗口通过其各自限定检查。最终已正常回5.15，六个受保护启动文件哈希不变。
后续[离线测量复核](../gpu-performance-diagnosis.md)限定旧数值解释：GLES未预热且分母含末次回读，
Vulkan为冷提交主机等待时间；clpeak120秒是全程序预算，不能称为map单次等待120秒。

方针**用户已于 2026-10-30 确认**：以5.15功能与性能为目标，通过Panfrost＋Mesa上游方式实现；
kbase/libmali仅作必要时临时后备。本记录不将建议当作用户已确认的长期产品决策。

## 版本、锁和负载

- Mac持久shell按board→heavy顺序取得`/tmp/vim4-board.lock`、`/tmp/vim4-heavy.lock`，覆盖所有板端操作，收尾后释放。
- 5.15：`5.15.137-vim4kvm-hdrdual6`，kbase r44p0，私有libmali SHA256
  `536ee80c17dc5c54e7c6ff029ca43270da8efc3fdc5b3aeb263f364419368494`。
- 7.3：沿用登记的`213f271505411`、build ID `7a473adf9353013fd1ab01908d20bbf503a063fb`及同次完整模块。
  `d2cd4c6c981e9`仅改DT，所以不替换Image/模块：在保留DTB的副本中新增GPU和95°C trip的phandle及cooling-map；
  反编译diff证明没有其他属性变更。保留HDMI/USB/MAC配置，候选DT只被临时`/boot/gpu-once.conf`引用。
- RAM命令：`sysboot mmc 1:1 any ${pxefile_addr_r} /gpu-once.conf; reset`；没有saveenv、修改默认项或持久选核。
  第一次脚本匹配错autoboot提示，自动回5.15；改为匹配`Hit SPACE`并发送空格后成功进入候选。
- 系统Mesa25.2.8；私有Mesa26.2.6归档与[离线记录](2026-10-30-gpu-runtime.md)一致。
  API/基准使用同一[gpu-compare.py](../../tools/gpu-compare.py)，vendor三轮后，7.3按system/private交替三轮。
- 原探针surfaceless+pbuffer在厂商库初始化失败。厂商库扩展明确支持GBM，补充探针改用GBM＋512×512 RGBA FBO、
  相同128次片元循环、glFinish和像素回读，三栈各三轮×10秒。GBM配置没有pbuffer能力，故不能只换display而保留pbuffer。
  七系先测试，回5.15后补厂商三轮；CPU governor为performance。其间没有编译与板上测量重叠。
  NPU任务在VM独立离线编译，不使用板子；没有操作其工作树。

## 三列实测对照

所有能力均来自真实Mali设备，无llvmpipe/lavapipe样本。GLES数值为补充GBM/FBO探针，
不与原surfaceless结果混算。版本/扩展的完整原文保留在每轮result.json中。

| 项目 | 5.15 libmali | 7.3 Mesa25.2.8 | 7.3 Mesa26.2.6 |
|---|---|---|---|
| GPU | Mali-G52 r1p0，4核 | Mali-G52 r1，4核 | Mali-G52 r1 MC4 |
| EGL / GLES | EGL1.5 / GLES3.2（GBM上下文） | EGL1.5 / GLES3.1 | EGL1.5 / GLES3.1 |
| Vulkan设备API | 1.3.231 | 无ICD，vkCreateInstance=-9 | 1.0.354，实验、非conformant |
| OpenCL设备 / OpenCL C | 3.0 / 3.0 | 无CL平台 | 3.0 / 1.2；平台标称3.1，不等于设备3.1 |
| GLES FPS三轮 | 619.174 / 624.750 / 624.052 | 232.097 / 231.932 / 231.114 | 233.470 / 233.427 / 234.294 |
| GLES平均FPS | 622.659 | 231.714 | 233.730 |
| Vulkan DMA compute，ms三轮 | 1.881 / 1.893 / 2.678 | 三轮创建instance失败 | 8.228 / 8.038 / 8.000 |
| vkmark三轮 | 均SIGSEGV（-11） | 均失败，无ICD | 103 / 103 / 104，退出0 |
| clpeak完整运行 | 三轮退出0 | 无平台，不能算通过 | 三轮均120秒超时，停在enqueueMapBuffer阶段 |
| clpeak float带宽，GB/s | 11.22 / 11.19 / 11.30 | 不适用 | 10.72 / 10.72 / 10.72（部分结果） |
| clpeak float算力，GFLOPS | 101.66 / 101.69 / 101.70 | 不适用 | 94.94 / 94.96 / 94.81（部分结果） |

私有Mesa的GLES吞吐比厂商低约62.5%，两版Mesa仅相差约0.9%，不能归因于升级显著改善。
私有CL已完成部分的带宽低约4.6%、单精度低约6.7%，完整运行仍未通过。
DMA compute三轮中位数为厂商1.893ms、私有8.038ms，私有约4.25倍耗时。
首次冷测厂商为3.957ms，单列保留，不混入回5.15后的三轮；DVFS/预热也会影响此类短提交测量。

DMA探针用同一shader，逐字校验24,883,200字节、6,220,800个uint。
厂商用`heap-codecmm`，7.3用已有连续CMA heap `default_cma_region`；
[探针](../../tools/mali-dma-probe.c)新增可选heap路径并打印实际路径，不创建误导性的设备别名。
全部成功样本均校验通过，但尚未证明GPU输出可直接送Wave5或HDR转换链性能。

厂商没有注册全局CL ICD：vendor子进程显式预加载同一libmali，并用测试目录中的临时ICD指向它；
实际查询到了Mali-G52的CL3.0平台/设备/扩展，未依据strings推断版本。
私有PanVK实验开关仅对子进程设置；没有改系统EGL/GLES、全局ICD或alternatives。

## DVFS、thermal 与 runtime PM

7.3内核日志：ID0x7402，shader_present=0xf、l2_present=0x1、L2 features=0x07120206，taint=0。
userspace governor下按250→400→500→666.7→800→666.7→500→400→250MHz，
每档3秒真实渲染、每0.5秒采样，所有请求均读回对应devfreq频率，所有渲染退出0。
这证明调频和负载驻留，不是独立仪器对时钟/电压的测量；未写PWM或regulator。
结束已恢复simple_ondemand。

GPU thermal zone的cdev0实际指向`devfreq-fe400000.gpu`，max_state=4；
passive trip为95°C、5°C hysteresis，critical为115°C。测量观察约49–54°C，
没有人为加热、写emul_temp或触发真实thermal降频，故只验收绑定，真实过温控制继续未验。

空闲→渲染→空闲→渲染→空闲窗口中，30个空闲样本28个suspended、2个active；
两次恢复渲染均退出0且像素正确，autosuspend_delay_ms=50、power/control=auto。
suspended时cur_freq为缓存，不证明外部时钟关闭或电压归零；未测仪器功耗。

## HDMI＋Wave5干扰对照

暂停One-KVM以避免第二采集/编码消费者，使用同一原生驱动基准，结束恢复服务。
4K60 NV12→H.264、20Mbps、GOP60、预热120帧、测1800帧；并发GPU窗口使用45秒固定GLES负载。
不ptrace、不做截图/声音/HID测试、不改变源Mac mini M6的输入状态。

| 窗口 | 输出FPS | 整机CPU% | source→encoded p99 ms | 输出帧数 |
|---|---:|---:|---:|---:|
| 无GPU前 | 59.998005 | 4.024 | 19.185 | 1800 |
| 系统Mesa并发 | 59.998010 | 4.596 | 19.197 | 1800 |
| 私有Mesa并发 | 59.998011 | 4.559 | 19.178 | 1800 |
| 无GPU后 | 59.998008 | 4.017 | 19.188 | 1800 |

四窗均success=true、无PTS丢失，CMA收尾均505200KiB；候选内核taint始终0，
收尾未检出GPU timeout/MMU fault/Oops。此基准不读取码流或像素帧号，
不能代替运动画面质量、HDR/GPU零拷贝、网络/浏览器延迟或长期稳定性验收。
插件扫描有既有nvcodec缺libMali和GObject属性warning，实际VDIN/Wave5基准完成。

## 失败初判与后续上游排序

1. G52 GLES3.2、Vulkan1.3设备能力与着色器性能是主要缺口；新版Mesa并未自动补齐。
   固定shader场景约62.5%吞吐差距，应先分析Bifrost编译输出/指令和GPU计数器，不能仅凭本测归因于频率或带宽。
2. CL map阶段三轮超时，但后续GLES、PM恢复和视频均正常，不足以断言GPU整机死锁。
   下一步用最小map/wait/unmap复现，区分Rusticl同步与clpeak校准/循环行为，先解决正确性再评性能。
3. 厂商vkmark崩溃不等于厂商Vulkan不可用，同库DMA compute通过。
   两栈均有vkmark apiVersion=0警告，不能仅凭该警告认定崩溃原因；需单独定位该基准与厂商WSI的兼容。
4. 系统Mesa缺Vulkan/CL来自未装ICD，不据此认定Panfrost内核缺计算能力。
   私有Mesa可作为上游实验运行时，但当前不能取代已验收的厂商GPU产品链。

## 收尾、证据与验证

正常重启回`5.15.137-vim4kvm-hdrdual6`，boot ID `5c5dfa4a-022d-43a0-9401-808b745ca0d2`。
One-KVM、HDMI、manager均active，UDC configured，无基准进程遗留，根分区11G/29G、剩余18G。
删除本轮两个临时boot文件和上传的归档；私有`/opt/vim4-mesa-26.2.6`和板上测量目录保留，未被默认服务选用。
六文件SHA256与入场逐项一致：extlinux.conf、uEnv.txt、原edge Image/DTB、5.15 hdrdual6 Image/initrd。
未更改其他启动文件，未执行saveenv、push、键鼠/HID报告、PWM/电压写入或声音测试。

原始证据在忽略目录`logs/gpu-board-20261030/`：九轮result.json保留API扩展全文、GBM三栈数据、
DMA compute、pm-dvfs、四窗视频JSON、串口启动/返回日志、DT diff、before/final哈希。
scp仅对不可读的GStreamer registry缓存报Permission denied；所有结果JSON及文本日志已取回，缓存不是测量证据。
补充探针SHA256：`20efbc206a9f51267ba5a0897a7e38f2d5f2e89e078d0b784615124b7a2be078`；
DMA探针SHA256：`2448e9e26b3ae353430b56732a9f2c35095355442f0b8820b744b390f9a78c8f`。
两者均在板上测量间隙以ARM64容器Werror编译，没有与测量重叠；原Mesa归档未重打包。
补充GBM可用`gpu-compare.py MODE --probe NEW_PROBE --gbm-device /dev/dri/renderD128 --output NEW_DIR`复现。
主仓离线unittest：305项、7项跳过、无失败。两份探针Werror编译通过；新增GBM/FBO路径已在三栈真实上板运行。
