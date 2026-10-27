# 2026-10-27：UU HDR 降分辨率的 GPU 缩放

接续[UU HDR 能力与首帧修复](2026-10-27-uu-hdr.md)。用户确认原尺寸4K约60fps，
降分辨率约5fps。真实PQ输入下，生产UU的3022×1700编码输出约4.3fps，
每帧发送约1–2ms、无序号缺口；等待在发送之前。原尺寸4K60不能证明缩放路径性能。

## 实现

原路径在AMLY→P010 GPU转换后使用CPU `videoscale`，其系统内存输出还会走
SDK的CPU上传。One-KVM改用 `vfmcapsrc height=1700`，源插件按输入比例计算偶数宽，
4K得到3022×1700；缩放后的P010直接从既有双槽codecmm池交给Main10编码器。
SDR继续使用VDIN1/GE2D，原尺寸HDR保留既有GPU转换与启动时CPU回退。
缩放明确要求Mali与连续DMA输出；缺失时报错，不静默回到慢速CPU缩放。

缩放分两次GPU dispatch：先把打包的Cb/Y0/Cr/Y1解到固定R16F/RG16F纹理，
再用纹理双线性插值缩放并输出P010。Binary16能精确表示0–1023全部整数，
UV保留4:2:2直到缩放时转4:2:0；不做色调映射或传递函数转换。
两张输入尺寸纹理随GPU实例释放、尺寸变化重建；不增加CMA输出槽数。
采集fd与输出fd仍等GPU完成、释放临时导入后才交还，编码器输入退休规则不变。

直接在buffer计算shader中逐样本插值的第一版，冷态单帧约51ms，
连续优化版仍约17–19ms；共享tile候选更慢，均未部署。
最终纹理路径同一4K→3022×1700连续120次均值约14.42ms，包含导入、dispatch、
fence与销毁；未固定GPU频率，首帧/升频峰值约68.91ms。

## 已测边界

内核仍为`5.15.137-vim4kvm-hdrdual6`，输入3840×2160p60 PQ HDR。
独占实际HDMI→缩放→Main10链路输出1200帧，执行20.280秒，计入启动约59.17fps。
GPU累计均值：import0.491ms、dispatch0.071ms、wait13.190ms、free/idle0.256ms；
编码均值8.261ms，DMA输入1200、CPU输入0，pending峰值1、结束0。
文件实际声明3022×1700、Main10、yuv420p10le、PQ/BT.2020。
部署后生产Chrome网页在15秒内解码900帧，3022×1700约59.97fps；
原尺寸3840×2160同样15秒解码901帧，约60.04fps，二者均实际报告PQ/BT.2020。
测完恢复原输出限制`height=0,fps=0`，未写HDR设置。
这些数据是编码吞吐，不是端到端显示延迟或MacBook光度验收。

真实Mali同帧像素套件17组通过：原尺寸12种几何逐字节相等；
五种缩放覆盖2×2、非块对齐、1080p、1700高和超宽。
缩放与独立double双线性参考最大差6个十位码值（极端随机输入），
反映纹理插值的有限小数精度；P010低六位始终零、行/尾填充未修改。
首尾dispatch均检查；中间迭代不扫CPU映射，避免验证本身阻止GPU持续升频。

优化构建的UU硬件协议回归21.97秒通过：4K的SDR→HDR→SDR→HDR各接收240个
完整RTP帧，用时3.97–3.99秒；1700高的HDR→SDR→HDR各接收30帧，
同一Peer保持连接，接管和断开恢复全局默认通过。该测试检查控制、SPS与连续RTP，
不替代官方MacBook客户端的实际显示验收。
调试构建在板上同时收发加密4K视频时仅约8fps，首次240帧检查超时；
未放宽断言，改用优化构建后通过。第一版管线的相邻caps拼接错误也由该回归捕获并修复。
Rust调试和优化构建全套均789通过、3忽略；Meson四项及三份SPIR-V校验通过。

## 部署与记录

候选仅替换One-KVM和公共采集插件，未修改内核、EDID、源端HDR偏好或全局默认。
部署来源：One-KVM `9f8a3c34`，采集插件`d0bf013`。
部署前版本备份在板端`/var/backups/vim4-uu-hdr-scale-20261027/`，
回退需停止One-KVM、恢复其中应用与`libgstvfmcap.so`，再启动服务。
One-KVM的HDR缩放要求配套支持`height`属性的采集插件，须成对交付。

部署SHA256：

```text
One-KVM d80acf240dd7a5053028f63bc2f8a1353aa7c938811cd29bd3f37fd0732311b7
libgstvfmcap.so c7f646c6efcb4a22ad1d82034648187963bc95e308afe28ae01d42a88ae547fb
```

忽略目录`build/uu-hdr-scale/`保存构建、像素参考、实验shader基准、
`gpu-texture-suite.log`、`texture-scaled-pipeline.log`和`board-uu-regression.log`。
网页结果为`web-scaled-hdr.log`、`web-native-hdr.log`；调试测试超时与早期解析失败
分别保存在`board-uu-debug-timeout.log`、`board-uu-parse-failed.log`。
