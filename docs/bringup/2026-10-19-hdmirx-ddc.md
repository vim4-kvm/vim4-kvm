# 2026-10-19：7.3 HDMI RX EDID 与源端 DDC 读回

结论：T7 接收器已能发布经过校验的 EDID，Mac HDMI 发送端依次精确读回
两份不同的 128 字节 EDID 和一份 256 字节 EDID。尚未接入 PHY 锁定、
时序检测、接收中断或 VDIN DMA，没有视频帧，不能替代生产 5.15 内核。
测试跨至次日；最终回到 5.15 后需要用户重插 USB-C 才恢复主机枚举。

## 源码与行为

Linux `vim4-kvm-7.3` 在上一轮资源版本之后新增三个本地提交，尚未推送：

- `e48ddac54f3ea`：追加 SYS_HDMIRX 时钟 ID，接收器绑定扩为六路时钟。
- `99c8bf7b2e83a`：CCF 管理 SYS_CLK_EN0_REG2 bit 9；bit 8 为已有 pclk。
- `00b37117883df95b707334996cc2b92f97c9feb5`：EDID 校验、DDC 发布与测试。
  tree 为 `8dc5232c937bbc5585ce5b43642ad122e80ab9f3`。

驱动在 `drivers/media/platform/amlogic/t7-hdmirx/`，不带参数仍仅监测资源。
只读模块参数 `edid_firmware=目录/文件.bin` 从固件目录加载测试 EDID；
要求 128..512 字节、完整块、正确头部、扩展数量和逐块校验和。
先保持 HPD 请求低 120ms，再写并验证选定端口完整 512 字节 RAM，尾部清零，
全部成功后才请求 HPD 高。卸载或失败时撤销 HPD，恢复 TOP 端口／复位状态，
再回收时钟和电源。debugfs `edid` 保存验证过的有效字节。

port 1 的 RAM 起点为字节地址 0x1200；测试 DTB 加入 HDMI B 的 detect、HPD、
SDA、SCK 引脚。普通 VIM4 DTB 仍禁用接收器。初始仅解除部分复位时虽能读回 RAM，
发送端读不到 EDID；对照厂商和 U-Boot 初始化，解除完整 TOP 复位并设置
TOP_PORT_SEL bit 4 后才读回成功。未加入 HDCP 或厂商 TVIN/VFM 接口。

## 构建与离线验证

VM `vim4-build`，源码 `~/src/linux-7.3`，输出 `~/build/kernel-edge-hdmirx-test`，
release `7.3.0-rc7-vim4kvm-hdmirx1+`，GCC 13.3。最终完整 Image/dtbs/modules
构建成功，无编译警告；schema／示例／yamllint、专用 DTB 校验通过。
驱动 strict checkpatch 为 0 errors、0 warnings、0 checks。
实际 C 函数的 fake MMIO 回归通过，覆盖输入校验、HPD 顺序、端口隔离、
读回故障及重复清理；1..4 块覆盖是离线证据，硬件只测了 1、2 块。
主仓库离线测试共 83 项，无失败、4 项跳过；新工具 Python 语法检查通过。

| 产物 | SHA-256 |
|---|---|
| Image | `73ff43cf3d3dd499a9c5a066f4b72158ef03ee8c79ab82e3af6260a569d506c6` |
| 写入本板 MAC 的测试 DTB | `fff51aac1c5a0708c59c0ed04f61255ecd68a0aa37b32156c6962f538fa9a1d0` |
| 完整匹配模块归档 | `3b40ca45e8d2b3b9c68738b8846a506618ff92ea7df09b6b294bff40488d6b56` |
| 已加载接收模块 build-id note，与 VM 相同 | `e50fa3d0279bebbda453cb7b6e4f226195999894ca11a5a1073150edeacafd68` |

构建报告和 bundle 保存在主仓库忽略的 `build/kernel-edge/`，不进入发布镜像。
配方仍使用 `-vim4kvm-edge`；独立实验 release 仅在本次输出目录设置。

## 上板证据与复现

保留 Default/Stock 和默认 5.15，串口仅单次选择第三项 HdmirxTest。
实验命令行屏蔽生产 KVM/HDMI/PD 服务，禁止接收器及 CRG UDC 自动加载；
SSH 就绪后设置本次启动的 15 分钟返回定时器。本轮没有修改 BL31/U-Boot 或分区。

最终匹配构建中，无效校验和及不存在固件均 probe 失败、没有驱动绑定，六路时钟引用归零。
随后三轮无参数加载／卸载通过：source_5v=1，旧 debugfs fd 被拒绝，
六路时钟引用归零。发送端测试又依次加载以下三份 EDID，每次 RAM 与 Mac 端逐字节相同：

| EDID | 字节 | SHA-256 |
|---|---|---|
| VIM4-DDC-A | 128 | `e57fa72ff13200fd4606fbe214139b8397fa64ea07136f559052a975096e7ac3` |
| VIM4-DDC-B | 128 | `2871b6d0eee28a5726fbe100b1eeb1b30c47abe546dc3c02fb333a5b975ff371` |
| 现有 RTK UHD HDR | 256 | `32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d` |

```sh
mkdir -p build/kernel-edge/ddc-fixtures
xxd -r -p tests/fixtures/hdmirx-edid-a.hex > build/kernel-edge/ddc-fixtures/edid-0.bin
xxd -r -p tests/fixtures/hdmirx-edid-b.hex > build/kernel-edge/ddc-fixtures/edid-1.bin
```

先在独占的专用内核安装匹配的完整模块，将这两份二进制及
`board/edid/rtk-uhd-hdr.bin` 放到板子 `/usr/lib/firmware/vim4-hdmirx-ddc-test/`，
保持各文件 basename 不变，接收器初始未加载。Mac 的 HDMI 口直连 VIM4 HDMI 输入，再运行：

```sh
python3 tools/hdmirx-ddc-host-check.py --exclusive \
  --log-dir logs/kernel-edge/hdmirx-ddc-host-new \
  build/kernel-edge/ddc-fixtures/edid-0.bin \
  build/kernel-edge/ddc-fixtures/edid-1.bin board/edid/rtk-uhd-hdr.bin
```

发布 256 字节时 port=1、hpd_request=1、TOP_SW_RESET=0、TOP_PORT_SEL=0x10，
TOP_HPD_PWR5V=0x00200032，pclk/sys 约 166.7MHz，CFG/METER/2M/5M 为
50/24/2/5MHz。TOP_EDID_GEN_STAT 仍为 0，不能作为传输成功计数。
最终卸载后 HDMIRX off，tainted=0，最终 7.3 运行日志无 BUG/Oops/WARNING/panic。

## 恢复与限制

- 首次只更新 Image/DTB/接收模块，旧网口模块的 split BTF 引用了旧 vmlinux 类型 ID，
  即使 release/vermagic 相同仍报 BPF Invalid name，无法 SSH。经串口返回 5.15，
  安装同次构建的完整模块集后，最终 7.3 网口恢复；没有关闭 BTF。
- 这次失败启动返回 5.15 时曾出现 carrier 正常而 RX=0、DHCP 不通。
  NetworkManager 重连无效；尝试网口平台驱动热重绑触发厂商 5.15 Oops 并重启。
  正常重启后网络恢复。此热重绑路径未修复，后续禁止将其作为常规恢复手段。
- 最后正常返回 5.15 时 PD 5V/3A、网络和服务正常，但 UDC not attached，Mac 无键鼠枚举；
  软件 UDC 解绑／重绑未恢复。用户重插单线供电 USB-C 后，内核为 5.15.137-vim4kvm，
  UDC configured，Mac 再次枚举序列号 60846dc05990 的 USB 组合设备，systemd 无失败服务，
  `board.py check` 通过。本轮未重跑视频、音频、实际键鼠输入的端到端验证。
- Mac IORegistry 在卸载后仍保留 Active/High 和上一份 EDID，不能证明物理 HPD 波形或
  断开完成；本轮以不同 EDID 的精确变化证明 DDC 读取。RTK 数据传输通过不代表 HDR、
  音频或各个宣告时序可用。暂无 V4L2 EDID API，变化需重新加载模块。

下一步接入 T7 PHY 的供电、PLL／均衡、锁定与时序检测，再做固定 1080p SDR 的
VDIN 连续 DMA 帧验证；之后才接编码、音频和应用。

## 日志

`logs/kernel-edge/`：hdmirx-ddc-final-build.log、hdmirx-ddc-final-modules-install.log、
hdmirx-ddc-binding-check.log、hdmirx-ddc-binding-final.log、hdmirx-ddc-final-dtb-check.log、
hdmirx-ddc-matched-resources.log、hdmirx-ddc-host-matched.log 及同名目录、
hdmirx-ddc-matched-note.bin、hdmirx-ddc-final-runtime.log、
hdmirx-ddc-return-network.log、hdmirx-ddc-network-retry.log、
hdmirx-ddc-ethernet-reprobe.log（含 5.15 Oops）、hdmirx-ddc-network-panic-return.log、
hdmirx-ddc-return-usb-rebind.log、hdmirx-ddc-final-return-uart.log、hdmirx-ddc-return-check.log、
hdmirx-ddc-return-usb-ioreg.log、hdmirx-ddc-offline-tests.log、hdmirx-ddc-bundle.log。
