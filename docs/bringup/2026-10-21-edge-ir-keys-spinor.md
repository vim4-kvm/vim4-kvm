# 2026-10-21：7.3 IR、板载按键与 SPI NOR 节点

IR raw receiver、ADC 功能键和 GPIO 电源键已在 7.3 注册，ir-keytable 可加载 Khadas
键表并启用 NEC。没有物理遥控器或按键动作，不能据此声称按键、解码或唤醒通过。
SPIFC/NOR 补入默认禁用节点：与当前 8-bit eMMC 根盘共用引脚，本轮未启用、未读
JEDEC/dump，更未擦写。候选在 Mac 共享锁内试启，完成后恢复原启动文件并重启。

## 源码、配置与硬件依据

- VM 工作树 `/home/deepdream/src/linux-7.3-dtnodes`，分支 `vim4-ir-keys-spinor`；
  基于 `ffdadae5b3f85`，提交 `4c582adea35e9`。只改
  `arch/arm64/boot/dts/amlogic/amlogic-t7.dtsi` 与
  `arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4.dts`。
  未修改、切换或构建主工作树；独立输出为 `/home/deepdream/build/kernel-dtnodes`。
- 厂商依据：VM `~/src/linux` 的 `80a07ad5406d5`、其中 common_drivers 的
  `4cfb128d36f85`；后者 `arch/arm64/boot/dts/amlogic/mesont7.dtsi`、`kvim4n.dts`
  的控制器和 keypad 节点，以及对应 IR、ADC、SPIFC、pinctrl 驱动。
- 对照 [V13A 原理图](https://dl.khadas.com/products/vim4/schematics/vim4-sch-v13a.pdf)
  的 Sheet 2、4、10，以及
  [新 VIM4 规格](https://dl.khadas.com/products/vim4/specs/new-vim4-specs.pdf)。
  规格称 SPI Flash 为 32MB；原理图仅标 SPIFLASH，未查明本板具体型号和 JEDEC ID。
- 板子运行 `7.3.0-rc7-vim4kvm-uhd1+ #12`。新板厂商文件名为 `kvim4n.dtb`，但
  实际 extlinux 默认 `FullKvm` 显式使用 `/edge/Image` 和 `/edge/vim4.dtb`；
  `/boot/Image`、`/boot/dtb`、`/boot/dtb.img` 仍指向 5.15，不是本轮替换目标。

| 功能 | 厂商连接与资源 | 7.3 处理 |
|---|---|---|
| IR | 多协议接收器 `0xfe084040/0xa4`，SPI IRQ 22，上升沿；GPIOD_5 `remote_in`，40-pin 接口引出 | 对应 REG0/1/2 布局的 `amlogic,meson-gxbb-ir`，raw 接收；未启用旧接收器窗口 `0xfe084000/0x20` 或发射器 |
| 功能键 | SAR ADC `0xfe026000/0x48`，SPI IRQ 181，上升沿；ADC2，厂商 10-bit 标称 90、容差 40，1.8V 量程 | 厂商同样使用 G12A ADC；四个时钟为 xtal、SYS_SAR_ADC、SARADC、SARADC_SEL，板级 vref 为 VDDAO_1V8；`adc-keys` KEY_ENTER，标称 158000µV、空闲标称 1800000µV，20ms 轮询 |
| 电源键 | SOC_PWR_KEY 接 GPIOD_4；厂商驱动实际把低电平报按下 | `gpio-keys-polled`、GPIO_ACTIVE_LOW、KEY_POWER，20ms 轮询；不依赖当前未提供 GPIO IRQ 的 T7 GPIO 控制器 |
| Reset | 原理图接复位/MCU 信号 | 保持硬件复位，不注册 Linux input 键 |
| SPI NOR | SPIFC `0xfe056000/0x80`，CS0，厂商上限 16MHz，SYS gate；不是扩展口 SPICC | 7.3 旧 SPIFC 驱动与厂商使用的寄存器布局一致，采用现有 GXBB compatible；控制器 disabled，子设备 `jedec,spi-nor`，不猜型号/容量 |

标准 adc-keys 按最近电压点分类，不能精确重现厂商 90±40 的窄容差窗口；本轮只验证
注册和空闲采样，实际按下电压、消抖、误触发仍需物理验收。按键也接 MCU，其电源/
升级快捷键行为没有改动；未验证 Linux 挂起唤醒。

NOR 的 `nor_hold/d/q/c/wp/cs` 分别是 GPIOB_3/4/5/6/7/12，B3..7 与 eMMC DAT3..7
共线。板上 `mmc0/ios` 确认 8 bits、HS200、约 200MHz、1.8V。不能同时申请两组
pinmux，不能抢占正在提供根文件系统的 eMMC 引脚。板级禁用状态和注释保留此限制；
尚未验证 SPIFC 的实际传输、时钟及识别。flash 级的 read-only 属性并不在此内核
中实现写保护，因此最终节点没有使用该无效属性，也没有编造固定分区。

`edge.config` 已启用 IR_MESON=y、KEYBOARD_ADC=m、KEYBOARD_GPIO_POLLED=m、
SPI_MESON_SPIFC=y、MTD_SPI_NOR=y；MESON_SARADC 由 ARCH_MESON 默认 y。
`uhd1.config` 和本次 olddefconfig 输出也启用上述选项，未改主仓库配置。
以上为首轮配置；第二轮把接收器改为模块并验证开机自动加载，见
[IR 自动键表记录](2026-10-21-edge-ir-autoload.md)。

## 构建与候选

复用已部署驱动，没有替换 Image/模块；本次构建范围为 DTB。配置取自已有
`~/build/kernel-edge-uhd1-test/.config`，olddefconfig 后 SHA-256 为
`610ff17daf5bb40085ca657f40a7436c1ff257c57aabb65367fb2aa3a4709ae9`。

```sh
cd /home/deepdream/src/linux-7.3-dtnodes
make O=/home/deepdream/build/kernel-dtnodes ARCH=arm64 olddefconfig
make O=/home/deepdream/build/kernel-dtnodes ARCH=arm64 -j8 dtbs
```

dtbs 成功，日志没有 warning/error。对 IR、SAR ADC、adc-keys、gpio-keys、旧 SPIFC、
JEDEC NOR 六项 binding 做限定 schema 检查；另复制仅供离线检查的 DTB，把 SPIFC
设为 okay，避免 disabled 节点被检查器跳过，该副本未部署，检查输出为空。
未做整板全部 binding 验收或 Image/modules 全量构建。

```sh
~/build/dt-schema-venv/bin/dt-validate \
  -s ~/build/kernel-dtnodes/Documentation/devicetree/bindings/processed-schema.json \
  -l 'amlogic,meson6-ir:amlogic,meson-saradc:adc-keys:gpio-keys:amlogic,meson6-spifc:jedec,spi-nor' \
  ~/build/dtnodes-schema-enabled.dtb
```

部署前对比旧 audio-test DTB 与板上现用 DTB，反编译差异仅有以太网固定 MAC。
从新 audio-test DTB 生成候选，保留原 `c8:63:14:74:70:0d` 的 mac-address 和
local-mac-address，保留现有 USB/HDMI 音视频配置。最终候选 SHA-256：
`fd75a4fad4383974c46d7eb0c1b9684b74fd696f55278d72fb62aad7cff5cd09`。

## 上板命令与实际输出

Mac 命令覆盖备份、安装、重启、检查及恢复全窗口：

```sh
/usr/bin/lockf -t 600 /tmp/vim4-board.lock \
  python3 -u build/kernel-edge/dtnodes/board-window.py
```

首次及最终窗口分别备份至板上 `/var/backups/vim4-dtnodes-20261021` 和
`/var/backups/vim4-dtnodes-20261021-final`，含 Image、DTB、extlinux.conf、完整模块 tar
及逐文件 SHA-256。仅通过临时文件加 rename 替换 `/boot/edge/vim4.dtb`；未向系统
根目录解包、未替换 `/lib` 链接，未停 manager 或操作 Wi-Fi/P2P 服务。
`ir-keytable` 从 Ubuntu arm64 包 `1.26.1-4build3` 提取到临时目录运行，板上未安装包；
`evtest` 使用现有工具。

执行 `cat /proc/bus/input/devices`、`ir-keytable`、dmesg 和 ADC sysfs，得到：

```text
Name="meson-ir"
Name="adc-keys"
Name="polled-keys"
Found /sys/class/rc/rc0/ with:
    Name: meson-ir
    Driver: meson-ir
    Default keymap: rc-empty
    Input device: /dev/input/event0
    LIRC device: /dev/lirc0
    Enabled kernel protocols: lirc
meson-ir fe084040.ir-receiver: receiver initialized
meson-g12a-saradc
4095
0.439453125
```

最后三个值为 IIO name、in_voltage2_raw 和 in_voltage_scale，空闲约 1.8V。
每个 event 执行 `sudo timeout 3 stdbuf -oL evtest /dev/input/eventN`，均进入
`Testing ...`；adc-keys 列出 `Event code 28 (KEY_ENTER)`，polled-keys 列出
`Event code 116 (KEY_POWER)`。两次启动的 event1/2 分配顺序不同，按设备名判断。
没有物理按下，未产生按下/释放证据。

meson-ir 内建而 rc-khadas 为模块，早期注册时找不到键表，实际回落 rc-empty；不能
把 DTS 的 linux,rc-map-name 当作已装载证明。最终窗口执行：

```sh
sudo /var/tmp/vim4-dtnodes-ir-keytable -c -w /var/tmp/vim4-dtnodes-khadas.toml -p nec
sudo /var/tmp/vim4-dtnodes-ir-keytable -r
```

```text
Read khadas table
Old keytable cleared
Wrote 12 keycode(s) to driver
Protocols changed to nec
Enabled kernel protocols: lirc nec
scancode 0x0014 = KEY_POWER (0x74)
```

只是配置加载和读回，不是收到遥控信号的证明；首轮键表加载没有持久化。
该早期注册问题已在[第二轮](2026-10-21-edge-ir-autoload.md)通过模块化接收器及
匹配的 Image/完整模块包修复，重启后自动使用 rc-khadas 和 NEC；候选验证后仍恢复基线。

`/proc/mtd` 始终只有标题，SPI devices 为空。这是保留引脚限制的结果，不是 NOR
验收通过。没有 NOR dump 或厂商/5.15 内容比较；实装型号、容量均未确认。
后续需不依赖这些 eMMC 数据引脚的启动环境，再分别建立 5.15、7.3 只读基准。
缩窄 eMMC 总线也需单独审查时序/pinmux 和存储回归，不能仅改 bus-width。
尚无证据要求新 SPI 驱动；本轮未编写任何控制器驱动。

## 恢复与证据

恢复原 DTB 后再次正常重启，校验全部启动文件及模块：

```text
/boot/edge/Image: OK
/boot/edge/vim4.dtb: OK
/boot/extlinux/extlinux.conf: OK
systemctl is-active vim4-manager
active
```

原 Image SHA-256 为 `25241ef8c402619e6917e6826129ba301c4b4dfacc4665db365620e9489faa48`，
原 DTB 为 `471fc2881ed6c83726ac1db85277aaeadbb63eb6b608d821f2e0bc177d96a567`，
extlinux 为 `84e8ff8ed405c6f2f45d959b6e17295ae37f20590ce036bad8d2ebf69fd47c0e`。
恢复后 rc/input 注册消失；默认 FullKvm、5.15 Default/Stock 启动项保留。
最终候选启动 boot_id 为 `a5d7dbbb-f516-4be5-9f72-b28bde658342`，恢复重启后为
`210a3f43-8d83-4a12-a24d-e0f0c5616a30`，运行版本仍为原来的 uhd1+。

主仓库执行 `python3 -m unittest discover -s tests -p 'test_*.py'`：
`Ran 147 tests`、`OK (skipped=5)`。未提交主仓库，保留并行 GPU 任务的文件和索引行。

Mac 原始日志在 `logs/kernel-edge/dtnodes/board-window{,-final}.log`，构建和 schema
日志在同目录；临时脚本、最终候选及原理图在 `build/kernel-edge/dtnodes/`。
VM 保留 `~/build/dtnodes-{build,schema,candidate-schema}.log`。
主仓库只新增本记录、索引及子系统链接，不提交主仓库。
