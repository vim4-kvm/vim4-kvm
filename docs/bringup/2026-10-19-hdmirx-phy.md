# 2026-10-19：7.3 HDMI RX 固定频率 PHY PLL 实测

结论：在独立 `7.3.0-rc7-vim4kvm-hdmirx2+` 中，固定 148.5 MHz 模拟前端／PLL
实验路径三轮锁定，SQO=1，cable/TMDS 时钟均约 148.5 MHz。约 10 秒的 40 次持续
采样也通过。TMDS 对齐始终为 0，没有图像尺寸、帧率或视频帧，不能作为 HDMI 接收完成。

## 源码与实验范围

Linux 分支 `vim4-kvm-7.3` 新增两个本地提交，尚未推送：

- `80d85a912f13e`：绑定／设备树增加独立 PHY MMIO 窗口，0xfe39c000、0x50 字节。
- `c9cd7fdf21415d6b47f0122182ba4bad99b82298`：固定频率 PLL、状态和错误回归。
  tree `2693415b9cbaa865b6f767f7701a2206fd4d26d7`。

驱动仍在 `drivers/media/platform/amlogic/t7-hdmirx/`；默认不启用 PHY。
模块参数 `phy_test=1` 要求同时提供 EDID 固件。为避免 HDMI 2.0 的 1:40 分频把
594 MHz 流呈现为 148.5 MHz cable clock，本阶段只接受无扩展块的数字 EDID，
首个详细时序的像素时钟必须为 148.5 MHz。此约束不等于读取了真实输入分辨率。
原有不带 PHY 参数的 DDC 路径继续支持 128..512 字节有效 EDID。

初始化依次配置 TOP 端口／通道、meter 与固定 PHY_BW_2 模拟参数，保留有效的
启动终端 trim；清除旧 meter 状态，等待至少四个相近的输入时钟样本，再配置
PLL_BW_2 的 M=40、N=1、TMDS 除 8。时钟等待约 3 秒、PLL 最多尝试 3 次。
成功后解除 CDR/EQ 复位、启用 DFE 与锁定检测。未实现自动重试或任意线缆均衡。

卸载或失败先撤销 HPD、关 PLL 和数据通道，再恢复实验写过的 TOP 配置，
之后由既有 DDC 清理恢复端口／复位，最后释放时钟和电源。debugfs 仅在资源有效时读取。
对照厂商 `common_drivers` 的 `hdmi_rx_hw_t7.c` 初始化、PLL 和关闭流程；
保留 Amlogic 版权，没有引入厂商全局状态、线程、TVIN 或 DMA 接口。

## 构建与验证

VM `vim4-build` 输出 `~/build/kernel-edge-phy-test`，独立 release 与旧 hdmirx1 并存。
GCC 13.3，完整 Image/dtbs/modules 构建及匹配模块暂存成功，最终构建无编译警告。
绑定／示例／yamllint、专用 DTB、strict checkpatch 通过。
实际 C 函数 fake MMIO 回归覆盖 EDID 限制、meter 有效位与溢出、时钟抖动／不支持频率、
5V 消失、PLL 有界失败、终端 trim、端口选择、TOP 恢复及重复清理；原 DDC 回归通过。
主仓库离线测试共 83 项，无失败、4 项跳过；Python 语法检查通过。

| 最终产物 | SHA-256 |
|---|---|
| Image | `fb7122a673028e4bb2914f23e417e7065a163f4a7a4834051d9185262d61dcc6` |
| 加本板 MAC 的测试 DTB | `2a8dd259897c1bea0c094e356a0a9ce4dd89eb2fb4fac88094ba45253b03fa3a` |
| 最终完整模块归档 | `624754902d36a5004c885673b71b0cced33b88913c269f460f5eeb3fb50d78ef` |
| 已加载模块 build-id note，与 VM 相同 | `23e85baaf24480f3b1671ad868b704c7bb785f2b44a3acd568cff3976a6daf47` |

先安装独立 release 的完整模块集及实验 Image/DTB，保留 /lib 符号链接，
旧实验文件备份到 `/var/backups/vim4-before-phy-20261020/`。
Default/Stock 及默认 5.15 保持不变；串口单次选择 HdmirxTest，生产服务被实验命令行屏蔽。
设置本次启动的 15 分钟返回定时器，结束时主动停止定时器并返回。
本轮未修改 BL31/U-Boot、分区或生产内核。

首次三轮 PLL 通过后补充 EDID 范围校验；重新完整 make 并确认 Image 字节未变，
安装最终匹配模块集，核对加载模块 build-id，再进行以下最终测试。

## 上板读数与复现

Mac HDMI 口直连 VIM4 输入 port 1。测试 EDID 使用
`tests/fixtures/hdmirx-edid-a.hex` 解码得到的 edid-0.bin，安装位置和解码命令见
[DDC 实测](2026-10-19-hdmirx-ddc.md#上板证据与复现)。确认独占且接收模块未加载后：

```sh
scp tools/hdmirx-resource-check.py vim4:/var/tmp/
ssh vim4 'sudo -n python3 /var/tmp/hdmirx-resource-check.py --exclusive \
  --cycles 3 --expected-source-5v 1 \
  --phy-firmware vim4-hdmirx-ddc-test/edid-0.bin \
  --reject-firmware vim4-hdmirx-ddc-test/rtk-uhd-hdr.bin \
  --reject-firmware vim4-hdmirx-ddc-test/invalid.bin \
  --reject-firmware vim4-hdmirx-ddc-test/absent.bin'
```

reject 项分别需要预先安装已有 256 字节 RTK、坏校验和文件，并保持 absent.bin 不存在。
无 EDID 的 PHY 请求、扩展 EDID、坏校验和与缺文件均拒绝绑定；后三项验证六路时钟归零。
三轮有效 PHY 加载后的典型读数如下，卸载后旧 debugfs fd 被拒绝、六路时钟引用归零：

| 字段 | 读数 |
|---|---|
| port / source_5v / HPD 请求 | 1 / 1 / 1 |
| TOP_PORT_SEL / TOP_SW_RESET | 0x12 / 0 |
| cable_meter / tmds_meter | 0x8000c5ff 或 0x8000c600 |
| cable_hz / tmds_hz | 148497070 或 148500000 Hz |
| phy_pll_locked / phy_sqo | 1 / 1 |
| tmds_aligned | 0 |

meter 由实际参考时钟乘计数再除 8192 换算，频率是硬件计数推导，未做外部仪器测量。
随后单次加载连续采样 40 次，间隔 250ms、末次约 9.765 秒，PLL/SQO 与时钟范围均通过，
对齐仍为 0。Mac 同时报告 128 字节 VIM4-DDC-A、Active/HPD High；
这不证明卸载后的物理 HPD 波形。最终 HDMIRX off、tainted=0，无 BUG/Oops/WARNING/panic。

## 后续缺口

下一阶段需接入 0xfe3a0000 的 COR 字节寄存器窗口，审查厂商 `cor_init()` 的
AON/PWD 复位、隔离、TMDS 通道映射与 PHYCK 门控，再实现对齐与 DE／总时序读取。
必须用稳定多次的实际时序确认 1920×1080；本轮的 148.5 MHz 读数不能替代该证明。
随后才能接 VDIN 连续 DMA；HDR、HDCP、输入音频、编码和应用未在此路径接入。

本次 7.3 启动另有 brcmfmac HT Avail timeout，未在本轮修复或验收 Wi-Fi。
不能据 PLL 测试通过推断其他驱动正常。

主动重启后已回到 `5.15.137-vim4kvm`，有线网络可达、UDC configured、systemd 无失败服务，
`board.py check` 通过，Mac 重新枚举序列号 60846dc05990 的 USB 设备；本次没有物理重插。
未重跑实际键鼠输入、音视频或延迟的端到端测试。

## 日志

`logs/kernel-edge/`：hdmirx-phy-build.log（首次编译失败）、hdmirx-phy-build-final.log、
hdmirx-phy-build-matched.log、hdmirx-phy-final-module-build.log、
hdmirx-phy-binding-check.log、hdmirx-phy-dtb-check.log、hdmirx-phy-regressions-final.log、
hdmirx-phy-install.log、hdmirx-phy-firstboot-uart.log、hdmirx-phy-no-edid.log、
hdmirx-phy-final-cycles.log、hdmirx-phy-loaded-note.bin、hdmirx-phy-steady-state.log、
hdmirx-phy-source-ports.plist、hdmirx-phy-final-runtime.log、hdmirx-phy-return-uart.log、
hdmirx-phy-return-check.log、hdmirx-phy-return-usb-ioreg.log、hdmirx-phy-offline-tests.log。
