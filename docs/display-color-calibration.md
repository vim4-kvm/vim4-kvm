# HDMI OUT 自环颜色校准

工具为 [display-color.py](../tools/display-color.py) 与 [display-color.c](../tools/display-color.c)。
仅 `chart`、`analyze`、`diff` 可离线运行；`run` 独占 KMS/采集，`snapshot` 读取上电后的
寄存器。调用者持有 Mac board→heavy 双锁、停止视频消费者、保留 watchdog/panic，
候选使用 display-once.py。工具不管理默认启动项或自动停启应用。

```sh
cc -O2 -Wall -Wextra -Werror tools/display-color.c -o /tmp/display-color \
  $(pkg-config --cflags --libs libdrm)
python3 tools/display-color.py chart --width 1920 --height 1080 --output /tmp/chart
# 以下在已独占、已自环的候选板上运行；card/video 使用现场枚举结果。
sudo python3 tools/display-color.py run --exclusive --binary /tmp/display-color \
  --card /dev/dri/card1 --video /dev/video0 --output /var/tmp/color-matrix
```

图案包含黑白、RGBCMY、256级灰阶、75% SMPTE 顺序色条、近黑/近白电平。
TX 创建线性 XRGB8888 dumb buffer，使用 EDID 中精确整数 Hz 的 progressive timing，
通过标准 color format、max bpc=8、Broadcast RGB 属性作 TEST_ONLY 再提交。
持有 framebuffer 至接到SIGTERM，再 atomic disable、RMFB、销毁dumb，保存退出状态。
`display-color probe CARD` 通过标准 GetConnector 刷新 modes/EDID；`run` 在读取 sink
能力前调用它，避免把 sysfs 缓存中的旧显示器 EDID 当作当前 sink。

RX 使用现有动态模式 NV12 VDIN 驱动，必须保持原始可见分辨率、不缩放、不经过编码器。
工具申请4个MMAP buffer，丢弃8个预热帧，再保存3个完整帧的sequence/timestamp/raw。
`run --warmup 0` 可记录资格确认后的前三帧，用于分离颜色和后续流故障；
预热数量写入 capture.json，坏帧、缺帧、序列回退仍拒绝。短窗口颜色通过不能替代
默认8帧预热窗口或持续采集稳定性，失败窗口必须与短窗口一起报告。
保存实际stride、allocation height对应的UV offset及V4L2色彩元数据。
当前UV偏移合同是 T7 VDIN 的 `stride * height`，有效payload为其3/2；
`sizeimage` 按 ALIGN(height,16) 分配的额外空间在尾部，不能当作平面间padding。
采集工具核对驱动名，只对这个已核对的布局生效，不推断任意V4L2设备的布局。
开始DMA前要求连续2秒原生时序匹配，资格确认上限40秒，之后仍丢弃8个预热帧。
服务关闭、模块参数和输入EDID由窗口控制器保存与恢复，不由工具隐式改动。

## 判定和证据边界

主测量域是 VDIN 声明的 BT.709 limited 8bit Y/Cb/Cr。YCbCr输出期望值由已知源RGB
按709 limited换算，RGB输出先按TX/RX声明的full/limited量化，再换算到同一采集域。
每块保存源RGB、期望wire值、期望NV12、三个观测值和最大误差；取色块内部完整色度对，
并检查采样区域所有值，避免中位数掩盖单帧/空间异常。每块每次误差≤2且黑白电平正确
才通过。三个原始帧保存SHA256，可在Mac重跑 `analyze DIRECTORY`。

NV12测量包含RX/VDIN的RGB→YUV转换和420采样，不能将通过结论扩大为每个RGB总线
分量的直接探针精度。若要分离TX和RX误差，用同一自环、同一图案取得厂商5.15原始
采集作参考，或增加已验证的无CSC原生采样；不能通过放宽≤2阈值抵消观察器误差。
色块边缘不参与精度判定，420色度损失不靠大色块证明不存在。

每档前后读回TX AVI packet bank、CSC/位深/通道mapping，以及RX收到的完整AVI；
校验checksum、BT.709、格式/量化范围、TX/RX一致和无taint。只读明确列出的VPU控制及
矩阵，不读LUT自增端口，不改VDIN矩阵。输出register snapshot中同时保存sink EDID，
跨内核差分拒绝不同EDID。420只跑CTA有效映射支持的模式；越界map直接报错，不猜能力。

`matrix.json` 中 pass/fail 是数值判定；error 是提交/取证/采集错误；not-applicable
表示EDID未声明该VIC的420。未取得完整样本不计颜色通过。

## 厂商差分

[厂商源码链路与系数](display-color-vendor.md) 固定了对照revision。5.15使用同一dumb
图案和atomic KMS，但颜色属性是厂商已有的 `color_space`、`color_depth`；这是测量
工具适配，不引入7.3内核。范围使用native并记录真实AVI，不伪造Broadcast RGB能力。

```sh
sudo python3 tools/display-color.py run --exclusive --vendor --binary /tmp/display-color \
  --card /dev/dri/card0 --output /var/tmp/vendor-color-registers
python3 tools/display-color.py diff vendor-before.json candidate-before.json --output diff.json
```

vendor模式只取得寄存器参考，不把它标成数值颜色通过。TX寄存器经厂商debug接口的
`rh`单地址读命令，AVI用厂商已有packet getter读回并解码；完整RX AVI单独保存。
5.15 没有 `/dev/mem` 时，VPU 控制字经 `aml_reg/paddr` 的选址后读接口取得，
RX COR 经 `rhd` 字节读两次并核对。不能用 32bit 物理读替代 COR 字节访问；其结果会
复制同一个字节到四条 lane。debug 回读只接受本次命令之后的新 dmesg 时间戳。
`diff`逐项输出VPU、TX控制与AVI语义，包含相同项；差异原因在bringup记录逐组说明，
工具不自动豁免差异。

校准 sink 使用 [SDR EDID](../packaging/kernel-edge/display-color-sdr-edid.hex)：
1080p60、4K30、4K60，8bpc、709、600MHz/SCDC、可选量化范围，420 仅声明 VIC97。
运行时加载后必须逐字节比对 TX 读回的 EDID；不能只检查显示器名字。厂商 repeater
自环需临时设置 `rpt_edid_selection 1`，避免 TX 插入回调改写本板 RX 的 EDID。
5.15 正在运行的 RX FSM 可能与 EDID 写入交错，需 `pause1`，调用现有 helper 的
runtime `load`，再执行 `reset40` 同步刷新，最后在 finally 中 `pause0`。
不调用 helper 的 persist/apply，不替换用户保存的 EDID；重启恢复原服务加载流程。

结束后按need-user文件协议恢复PC输入，再重启回正式eeddb005，核对受保护文件哈希、
服务active、UDC configured、HID和H.265冒烟。第二阶段仅有[设计草案](hdmi-passthrough-design.md)。
