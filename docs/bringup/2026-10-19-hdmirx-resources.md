# 2026-10-19：7.3 HDMI RX 资源与源端 5V 实测

结论：已接入 T7 HDMI RX 功能时钟、电源域和 TOP 资源，port 1 能读取到源端 5V。
三轮模块加载／卸载通过：旧 debugfs fd 在卸载后被拒绝访问，时钟引用归零，
HDMIRX 电源域回到 off。尚未初始化 EDID/HPD、PHY、接收中断或 VDIN，没有视频帧。

## 代码与构建

Linux `vim4-kvm-7.3` 新增三个提交，本次仅本地提交，尚未推送：

- `773cb14f60001`：时钟 ID 与接收器设备树绑定。
- `59cadc1261013`：CFG、METER、2M、5M、HDCP、ACR、AUD_PLL 七组时钟；沿用
  现有 CCF mux/div/gate 实现，父时钟和位域对照厂商定义，追加 ID，保留原编号。
- `281605e681846c685f00276591489260e3a23c81`：最小 `t7-hdmirx` 驱动和独立测试 DTB。
  普通 VIM4 DTB 中接收器 disabled；仅测试 DTB 启用 port 1 的 detect 引脚。

源码参照 common_drivers `4cfb128d3` 的 T7 时钟定义、HDMI TOP 映射与 5V 位域。
未引入 TVIN/VFM/codec_mm 或 HDCP 处理。驱动位于
`drivers/media/platform/amlogic/t7-hdmirx/`，目录 README 描述阶段边界。
debugfs status 是调试接口；`source_5v` 不代表 TMDS/PHY 锁定，
`hpd_request` 只表示寄存器请求，不证明引脚电平。

VM 输出目录 `~/build/kernel-edge-hdmirx-test` 为此前 CRG 构建的 reflink 副本，
独立 release `7.3.0-rc7-vim4kvm-hdmirx1+`。完整 `Image dtbs modules` 成功，无编译警告。
新驱动 checkpatch strict 无错误、警告；绑定 schema、示例、yamllint 和测试 DTB 检查通过。
工具使用 VM 独立虚拟环境，日志保留最初缺 Python 开发依赖的失败与修正后的结果。

- Image SHA-256：`829556bed849e9d1919ff7dc2450631782587d36da10e33dfbac259be5701d7d`。
- 加入本板 MAC 的 DTB：`9523b0c5d2379627bf6841ccebe8316aae05bd4f52acc167d4d4a1531f1140cd`。
- 未 strip 模块：`86dba63c4eca34eed2931b93508e289911e235be070b168e3899a47c1def9aa3`。
- 已加载模块 build-id note 与 VM 构建相同，SHA-256：
  `61dcb06acbfc0a88f60336c571084b6fc5f6d1e4672bc8ebd955e59bd8c9f9e3`。

配方已启用模块并记录测试 DTB；正式配方仍使用 `-vim4kvm-edge`，
上述独立测试 release 只在该实验输出目录设置。

## 上板与生命周期

开始前确认用户介质为空，没有其他测试占用。先将现有实验 Image、DTB、extlinux.conf
逐项校验备份到 `/var/backups/vim4-before-hdmirx-20261019/`；因 /boot 空间不足，
再替换 `/boot/edge/` 的实验文件，第三项 CrgTest 改为 HdmirxTest。
Default/Stock 和默认选择保持原值，固件、分区、生产内核未变。
模块安装到独立 release，保留 /lib 符号链接。

本次只经串口选择一次 HdmirxTest。KVM/HDMI/PD 服务被实验命令行屏蔽，
自动加载 t7_hdmirx 和 crg_udc 被禁用；SSH 就绪后设置本次启动的 15 分钟返回定时器，
再手动加载接收器。读数如下：

| 项目 | 读数 |
|---|---|
| port / source_5v | 1 / 1 |
| TOP_HPD_PWR5V | 0x00200010 |
| HPD 请求 | 0 |
| TOP_SW_RESET | 0x0000ffff，接收器核心仍在复位 |
| pclk | 166666664 Hz |
| CFG / METER / 2M / 5M | 50000000 / 24000000 / 2000000 / 5000000 Hz |

频率为 CCF 读数，未使用外部仪器测量。未做物理拔插对照，不能把单次 5V=1
当成所有线缆场景的验收。驱动没有写 HPD、EDID、IRQ 或 DMA 寄存器。

工具三轮分别加载模块、检查读数、保留已打开的 status fd，再卸载：
旧 fd 返回 I/O 错误；五个时钟 enable/prepare 引用均为 0。
最终 genpd 显示 `T7_HDMIRX off-0`，tainted=0，日志无 BUG、Oops、WARNING 或 panic。
结束后主动重启回到 `5.15.137-vim4kvm`，gadget configured，systemd 无失败服务，
`board.py check` 通过；未重跑音视频端到端测试。

```sh
scp tools/hdmirx-resource-check.py vim4:/var/tmp/
ssh vim4 'sudo python3 /var/tmp/hdmirx-resource-check.py --exclusive \
  --cycles 3 --expected-source-5v 1'
```

此命令仅用于已启动的专用测试内核、接收器初始未加载且已确认板子独占的情况。

## 后续接入顺序

1. 解除必要的 TOP 复位，初始化 DDC 滤波与 EDID RAM；准备好有效 EDID 后才拉高 HPD。
   在发送端读取 EDID，对照校验和，验证卸载与重连行为。
2. 接入 T7 PHY 供电、端口选择、PLL/均衡与锁定状态，再实现真实分辨率和时序检测。
   不能仅添加 compatible 就复用 rk3588 的 Synopsys 接收驱动。
3. 接入 VDIN 的 VPU/时钟/中断与连续 DMA 帧，先做固定 1080p SDR 的原始帧验证。
   明确完成中断、缓冲持有与归还，再扩充分辨率、热插拔和 DMA-buf 输出。

## 日志

`logs/kernel-edge/`：hdmirx-build.log、hdmirx-modules-install.log、
hdmirx-dt-binding-check.log、hdmirx-dt-binding-final.log、hdmirx-dtb-check.log、
hdmirx-install.log、hdmirx-firstboot-uart.log、hdmirx-resource-cycles.log、
hdmirx-loaded-note.bin、hdmirx-final-runtime.log、hdmirx-return-uart.log、hdmirx-return-check.log。
