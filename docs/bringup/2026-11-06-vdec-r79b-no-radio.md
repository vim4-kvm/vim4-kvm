# 2026-11-06：r79b无线初始化屏蔽通过，HEVC身份门禁误停

**无线屏蔽.36一次启动成功、无冷复位；stateless compliance 60/60、media 8/8，
DOS step=0。HEVC在解码前因编排器错误的插件路径判据停止，全部未运行。**
未重试、未运行全集第1批，正式fd41fb5恢复、2372 proof及视频通过。
FIFO1496已释放，788项上传归档校验后删除，没有部署或改正式默认。

## 拓扑、入场和无线证据

本窗延续[无线变体计划](2026-11-06-vdec-integration36-no-radio-plan.md)的RAM SHA
`5d6e262cf6044e1cee23b65fd37dff6fb7ad82aba9ea2fb01dfa0d1065de3c6d`，同.36内核/模块，
build ID `355061dc85a2fd695429b501c0c2b87078cf1f89`。仅追加三项cmdline屏蔽。
前一次[入场停止](2026-11-06-vdec-r79-entry-stop.md)零上传/零启动，不计冷复位。

拓扑为Mac→用户USB-C功率计（型号待补）→板子，同时供电与HID。
插拔导致一次未计入既有统计的正式断电启动。用户确认Mac仍识别HID；报告表显供电
能力15W、平时约3W、本次候选启动显示最高约5W。未确认峰值保持，无同步电压/电流波形，
不能据显示值排除短时瞬态或确认功耗归因。

替代票先排空UART一次并保存字节/SHA：实际0字节，SHA为
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
随后正式boot_id `7be4d8b5-c0f1-4b95-8704-8925d7da60ba`不变，uptime
475.45→484.27秒，观测8.925515917秒。UDC `fdd00000.usb`为configured，kvm gadget
绑定，hid.keyboard、hid.mouse_abs、hid.mouse_rel存在；没有向Mac注入输入。

入场保存systemd服务/ExecStart、modules-load.d、modprobe.d、本地udev规则；另读
fenix-hardware-optimization、sysfs.conf、camera setup。未找到独立无线GPIO上电动作；
bluetooth-khadas及rc-local已mask，bluetoothd由本候选新增mask覆盖。
NetworkManager/wpa_supplicant保留，不能对不存在的SDIO/HCI设备初始化固件。

候选boot_id `88fde45c-9dab-4a3e-b98d-5c0b2aa04e50`；SSH核release/build ID及全部
cmdline，ready采证uptime15.47秒：

- brcmfmac、hci_uart、btbcm均未加载，rfkill列表为空，无无线接口/HCI/SDIO设备。
- dmesg明确记录`initcall mmc_pwrseq_simple_driver_init blacklisted`及btbcm拒绝加载。
  pwrseq_simple驱动目录不存在，devices_deferred为
  `fe088000.mmc platform: supplier sdio-pwrseq not ready`，无无线固件初始化日志。
- bluetooth.service为LoadState=masked、ActiveState=inactive、masked-runtime。
- eth0地址192.168.50.210、SSH可用，UDC仍configured，HID gadget绑定不变。

证明Linux无线初始化被阻断，不证明共享电源轨物理断电或U-Boot遗留GPIO为低。
这是新拓扑下的一次变体成功启动；原.36为6次/4复位，新变体单列1次/0复位。
不把两组混算成稳定性结论。

## 解码结果与离线修正

stateless带流compliance 60/60，media 8/8，零failed/warnings，DOS step=0。
HEVC身份检查在全I compliance之前抛出AssertionError：编排误将stateful
v4l2h265dec的文件期待为私有libgstv4l2codecs.so。
实际gst-inspect的Plugin Details为video4linux2，文件
`/usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstvideo4linux2.so`，1.24.2，gst-plugins-good。
stateless v4l2slh264dec则确实来自私有v4l2codecs；官方h265parse来自私有前缀的
videoparsersbad。三份实际输出完整保留。

因此全I、cip_B_NEC_3及全集18条都是Not run，不能将phases.json中粗粒度all_i=Failed
理解为硬件/像素失败。没有HEVC码流提交证据或捕获帧，未修改驱动。

离线修正只在编排器：读取Plugin Details的Name/Filename/Version，严格区分stateful
video4linux2与stateless v4l2codecs，不以日志任意位置包含路径为通过条件。
私有parser/stateless插件继续核封存SHA；系统stateful插件在下一窗入场记录SHA并冻结
到计划，HEVC执行前再核一致（这是同窗身份锁，不冒称独立发行包签名验证）。
`run79/replay-plugin.log`用本窗真实三份输出通过正例，错family/路径及外部伪路径均拒绝，
旧的HEVC错误期待明确拒绝。新的编排位于run79c；不改共享工具默认行为。

## 恢复、证据与下一窗边界

这是正常请求恢复，不是冷复位。正式boot_id
`4516d0d5-4d71-45bf-9281-a857160bf516`，build ID
`bdbfa439f298e92b5bad092528d11119a974f262`，2372保护文件全同；无线三模块、
hci0及两SDIO设备恢复，新增cmdline屏蔽消失；HID configured。
视频298帧、59.566984fps，零新增丢帧/冻结/丢包。只清理本任务哈希核对的固件与暂存，
清理helper先重新上传；未触碰正式模块。正式eMMC累计至少42次/8次复位，不包括
用户插拔功率计的断电启动。

原始目录`logs/hwdecode-parity-r79b/`含连续UART、SSH身份、无线前后快照、服务脚本、
returned-baseline-identity.json、returned-video.log及complete.restored=true。
UART 242.477423667秒，SHA256
`2e1299f6c092d1fa321db8f5f5f972a12d148c22035212c76d35994d50fdc938`。
`build/hwdecode-parity/run79/`含board-upload.tar/788项哈希清单、archive/results、
离线失败路径、插件回放和功率计口述记录；全套主仓库607项OK、11项跳过，
检查日志main-tests.log，跳过不计通过。

协调者条件授权r79c：记录/修正/回放/全套测试完成并报SHA后，一张替代票、同变体一次
启动、冷复位不重试；全I加一条P/B全过且剩余≥630+420秒才跑全集第1批。
功率计保留在线，按用户最新指示不再逐次发送“即将启动候选”提醒。
全集结束再由协调者另派主线部署计划，本窗不部署。
