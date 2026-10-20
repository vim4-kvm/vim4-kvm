# 2026-10-19：7.3 CRG 真实 HID 与只读虚拟盘

结论：三种 HID（键盘、绝对鼠标、相对鼠标）＋只读 mass storage 的三轮组合测试通过。
Mac 收到实际按键与鼠标移动，读取测试文件哈希一致；每轮安全弹出后重新绑定，
上一轮 HID fd/epoll 保持至下一轮传输成功。尚未完成完整 KVM 或长期 USB 稳定性验收。

## 版本与边界

- Linux 固定提交 `9610500b6fee8f094ac68d6802dd7c6f7bb19df2`，源码工作树干净。
- 使用现有独立构建目录 `~/build/kernel-edge-crg-test`，重新执行完整
  `make ... Image dtbs modules` 成功；控制端点与初始化失败回收回归均通过。
- release `7.3.0-rc7-vim4kvm-crg1+`；Image 与上次产物一致，SHA-256 为
  `5318e5e5112324b8c17b257b575b5c3cee3ee1d9a0e4e9dff3f173f589ab79e8`。
- 本板 DTB 为 `7d8d1798bec7737413e4a8d44475f1440de1bf17baa471853e8fe2e11572c674`。
- 已加载 CRG 模块 build-id note SHA-256 为
  `3462ef3a210bee374e07210a5047f1a53b68c9aae722859ec82704db613ba7db`，与 VM 修复版一致。
- 启动前确认没有其他测试占用，现有虚拟介质为空。串口只选择一次 CrgTest，
  默认启动项仍为 5.15；未更新固件、分区或现有生产内核。
- 实验内核屏蔽 KVM、HDMI 和 PD 服务，手动加载 CRG；设置本次启动的 15 分钟返回定时器。
  测试结束主动返回默认内核。

## 方法与结果

专用 FAT16 镜像位于板上 `/var/tmp/crg-composite-7319/test.img`，32 MiB，卷标 CRG7319。
包含固定 marker.txt 和 16 MiB 随机 payload.bin。通过只读 LUN 暴露，不使用现有用户镜像。
镜像 SHA-256 在测试前后均为
`dfb8208d73df91a60b33f464491709745928bfdeb1f5f9b2dca1e18d6fa26013`。

三轮分别完成：

1. 三种 HID＋存储枚举，Mac 挂载测试卷，确认总线为 USB、`WritableMedia=false`。
2. 临时原生窗口取得前台，验证 Shift 按下/释放状态，窗口收到右方向键一按一放（keyCode 124）。
   避开上次 IOHIDManager 原始报告监听的权限限制；本次证据来自实际 OS 输入事件。
3. 绝对鼠标定位到屏幕 25%/25%、70%/60%，主机坐标误差小于 2%；
   相对鼠标报告 X=24/Y=16，主机坐标沿预期方向变化。
4. HID 验证期间，另一个线程四次读取 payload.bin，以 F_NOCACHE 请求绕过文件缓存，
   每次 SHA-256 都为 `8d14b51131e3853ddcf9f62015aeaa02d0dbd181b3b09274d34e2389fa248f33`。
   这不是 USB 吞吐率或存储性能测试，也不能证明各次读取的每个字节都经过物理总线。
5. 主机 `diskutil eject`；板端确认 LUN file 已被 SCSI eject 清空后才解绑。
   上一轮 relative HID fd/epoll 保持到下一轮枚举与连续中性报告提交成功后再关闭。

三轮均通过。测试 gadget 已清理，模块卸载/重新加载通过，tainted=0，
本次日志未见 BUG、Oops、WARNING 或 panic。
返回后确认 `5.15.137-vim4kvm`、gadget configured、systemd 无失败服务；
管理器完成启动后 `board.py check` 通过。未重跑音视频端到端验收。

首轮工具在重启后因 /tmp 脚本被清理而退出；重新上传后，两次因错误使用
`ReadOnlyMedia` 字段而退出。macOS 实际字段是 `WritableMedia=false`，修正后正式三轮通过。
失败日志保留，不能将所有日志统称为成功。

## 复测入口

先按[首次实测](2026-10-19-crg-udc.md)进入实验内核，准备 configfs、libcomposite 与 CRG UDC，
确保没有其他 gadget。启动后再上传脚本，因为 /tmp 会在重启时清理。
制作新的专用 FAT 测试镜像，放入上述 marker 和 payload，并记录实际哈希；不要复用用户介质。

```sh
swiftc tools/input-target.swift -o /tmp/vim4-input-target
scp tools/crg-udc-check.py vim4:/tmp/crg-udc-check.py
python3 tools/crg-composite-host-check.py --exclusive \
  --image /var/tmp/crg-composite-7319/test.img \
  --payload-sha256 8d14b51131e3853ddcf9f62015aeaa02d0dbd181b3b09274d34e2389fa248f33 \
  --cycles 3
```

此工具要求 Mac 单显示器、修饰键已释放；测试期间不要操作键鼠。
临时窗口结束后恢复原前台应用与指针。只读盘必须安全弹出才允许进入下一轮。

未覆盖鼠标点击/滚轮、键盘 LED 输出、可写盘、UAC2、网卡、主机主动 USB reset、
主机休眠恢复及长时间负载。固定 peripheral 模式和拒绝板子系统休眠的限制仍存在。
下一项核心开发是 HDMI RX/VDIN 的独立输入采集。

## 日志

`logs/kernel-edge/`：crg-composite-build.log、crg-composite-image.log、
crg-composite-boot-uart.log、crg-composite-host.log、crg-composite-host-run2.log、
crg-composite-host-run3.log、crg-composite-host-run4.log（正式三轮）、
crg-composite-loaded-note.bin、crg-composite-final-runtime.log、
crg-composite-return-uart.log、crg-composite-return-check.log。
