# 2026-10-22：SARADC channel 2 超时取证与离线候选

channel 2 是 Function 板载按键，不是温度或硬件版本检测。留存的23次启动中只找到
[pstore 第二次启动](2026-10-22-edge-pstore-deploy.md)那一条超时；本次2000次直接读取零错误。
确定发现一处采样延迟掩码错误，已修正为独立候选；**尚未证明它是该次超时的根因**。
没有部署内核、重启、驱动热重绑或物理按键测试，仍保留0196fe22…基线。

## 读取者与频率

7.3 `amlogic-t7-a311d2-khadas-vim4.dts:adc-keys`：`io-channels = <&saradc 2>`、
`poll-interval = <20>`，Function 映射 KEY_ENTER；厂商5.15 `kvim4n.dts:adc_keypad`
也取channel 2、名为function、code=28、名义ADC值90/1023。硬件版本不在该路径；
当前IIO设备名 `meson-g12a-saradc`，温控不由此channel提供。
上层 `drivers/input/keyboard/adc-keys.c:adc_keys_poll()` 调用
`iio_read_channel_processed()`；读取错误会释放原按键，不按坏数据报告按下。
20ms是配置的轮询间隔，实际还受输入设备打开状态和调度影响，未据此估算总转换次数。

只读查询：

```sh
python3 build/small-fixes/adc-history.py > logs/small-fixes/adc-history.json
ssh vim4 'cat /proc/bus/input/devices; sudo cat /sys/kernel/debug/clk/clk_summary'
/usr/bin/lockf /tmp/vim4-board.lock \
  python3 build/small-fixes/adc-window.py > logs/small-fixes/adc-sample.json
```

journal按bootId逐个读内核日志，23个条目均保留Linux version行；唯一命中为
boot `75e4d1aae85047a89e885b4cc1ad1050`：

```text
[6.509976] meson-saradc fe026000.adc: failed to read sample for channel 2: -110
reads=2000, errors=[], min=4093, max=4093, seconds=0.629354966
```

本次raw读取前后当前启动均无该警告。23次启动的内核、时长与负载不同，
1/23仅是留存历史的出现比例，不是同条件复现概率；本轮未专门重启抽样。
直接读取只检验ADC转换，未覆盖物理按键电阻阶梯和启动瞬间。

## 厂商对照与确定缺陷

对照VM `~/src/linux/common_drivers/drivers/iio/adc/meson_saradc.c`、
`meson_saradc_m8.c`、`arch/arm64/boot/dts/amlogic/mesont7.dtsi`：

- 厂商T7与7.3均用g12a兼容项，MMIO fe026000/0x48、SPI181上升沿IRQ，
  时钟为xtal/core/adc_clk/adc_sel；板端实读xtal父频24MHz、ADC **1.2MHz**，符合厂商参数。
- 厂商转换完成用有界BUSY轮询；7.3等待FIFO IRQ completion，超时返回-ETIMEDOUT。
  现存警告未保存当时REG0/FIFO与IRQ计数，不能区分漏中断与转换引擎未完成。
  不改变IRQ触发类型、不延长超时或增加重试来掩盖这个未确定问题。
- 两版初始化均声称样本间隔11µs，但第一条 `regmap_update_bits(DELAY, ...)`
  把`INPUT_DLY_CNT_MASK`（23:16）与`FIELD_PREP(SAMPLE_DLY_CNT_MASK,10)`（7:0）配对。
  掩码不相交，样本计数保留固件残值；后续正确写入的是输入延迟，不会补救样本计数。
  这是厂商代码也存在的确定缺陷，不能把照抄厂商等同于正确。

## 独立候选与边界

VM工作树 `/home/deepdream/src/linux-7.3-saradc-small`，分支 `fix/saradc-sample-delay`，
基于0196fe22ecf0104d96b7ef0fa497ca2317bd20bb；提交
`d0c36b0fab52f1179e7f42ffea2dbdc10bf31b64`，**未推送、未部署**。
只改 `drivers/iio/adc/meson_saradc.c` 一行，把写掩码改为SAMPLE_DLY_CNT_MASK。
输入延迟、时钟、IRQ、DT与重试策略均未改变。主内核工作树保持原分支与干净状态。

独立 `O=/home/deepdream/build/kernel-saradc-small`，复制uhd1.config，完成
olddefconfig、prepare/modules_prepare、`drivers/iio/adc/meson_saradc.o` 编译；
`git diff --check`通过，编译日志未发现warning/error：

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock orb -m vim4-build sh \
  /mnt/mac/Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/build/small-fixes/build-adc.sh
```

输出与日志：VM上述O=目录、`logs/small-fixes/adc-build.log`。未构建完整Image／模块包，
未运行候选硬件测试。VM当时仅余约1.5GiB，不复制11GiB的既有输出目录。
下次内核部署可审查合入此提交，完整重建并验启动与ADC；仍需单独捕捉超时现场才能关闭原问题。
基线与真实HID证据见同轮[PD窗口](2026-10-22-pd-manual-contract.md)及最终Wave5复核。
