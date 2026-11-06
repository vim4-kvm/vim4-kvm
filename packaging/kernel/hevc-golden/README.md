# HEVC golden trace：离线工具

[资产证据与窗口方案](../../../docs/bringup/2026-11-05-hevc-golden-plan.md)。没有连接板子、排票、
安装或重启入口。patch只用于experiment；trace_printk有时序开销，不是生产修改。

## 补丁和格式

`vendor-trace.patch`对应common_drivers `31619c527655514b4c89516ef609b6db1dd47db6`，
输入文件SHA在vendor-source.json。原厂商源码未修改，补丁仅在独立副本apply-check。
寄存器层编进media_clock，加载/电源/input编进decoder_common，HEVC编进amvdec_h265，
因此不是只重建amvdec_h265一个模块。此源码尚未证明对应板上hdrdual6。

`mainline-trace.patch`对应实验分支experiment/hevc-golden-trace的
`562ec48e8fd719ebdbad92b647e7f0dbb2fc7b9c`，基于自动NAL的f065c6712f7e，
不带857b5a2e手动NAL候选。默认关闭，开关分别为模块参数
media_clock.hevc_golden_trace和aml_vdec_drv.hevc_golden_trace，须在首次power请求前开启。

两侧记录 `HGT p=5 op=W reg=3301 val=00000001`。地址/值为十六进制，地址为DOS word index。
E=相位，L=secure固件索引/核心选择，F=加载返回值，I=ISR的DEC_STATUS，R/W=寄存器访问。
相位：1电源请求、9核心reset、2固件、3协议初始化、4输入、5启动/运行、7首个DECPIC_DONE、8停机。
I保留运行相位；phase7只是固件完成事件，仍需用户态像素证明。

覆盖DOS 3000..3eff及3f33..3f35。厂商在实际低层read/write后记录，包含compat路径。
7.3的wr/read_dos_reg输出同格式，但**完整录制还须原生regmap_reg_read/write**，
覆盖prepare/stop/update_bits/poll等直接regmap调用。normalize的regmap模式只保留
原生R/W及HGT的E/L/F/I，去除重复HGT R/W；设备名固定fe320000.video-codec，byte offset除4。

不新增MMIO读、IRQ注入或fallback；不新增逐笔printk。CPU可见访问不等于TEE/BL31内部
写入、固件自行改寄存器或CCF/genpd provider原始MMIO。power/clock trace事件可辅助边界，
不能冒充provider内部每笔写入。跨CPU事件排序是录制顺序，不能反证严格硬件事务总序。

## 使用与可信度

冻结trace后保存完整文本和所有CPU的per_cpu/cpu*/stats（带CPU标识）。
任何LOST、overrun或entries覆盖都拒绝比较，缺少计数也拒绝；capture必须包含power相位，
golden还必须到达首帧完成相位，不能用失败前缀充当成功基准。

```sh
python3 packaging/kernel/hevc-golden/align.py normalize vendor.trace vendor.jsonl \
  --source custom --stats vendor.stats --address-map vendor-map.json
python3 packaging/kernel/hevc-golden/align.py normalize mainline.trace mainline.jsonl \
  --source regmap --stats mainline.stats --address-map mainline-map.json
python3 packaging/kernel/hevc-golden/align.py compare vendor.jsonl mainline.jsonl > comparison.json
```

退出0=选定事件一致，1=分歧，2=输入不足/不可信。默认比较写入、固件选择/返回和IRQ，
全部读回保留，`--reads`可比较读；不同采样时刻的PC/轮询不默认判成写入缺口。
报告每相位首个值/次序分歧、原始行号及相位顺序差异，归一化截在首个phase7。
首个分歧只是审核入口，自检/合法架构顺序/内存布局等均可能不同，不自动据此改代码。

地址映射必须来自该次分配/配置证据，示例：

```json
{"address_registers":["0x3102","0x3103","0x3104","0x3105"],
 "endpoint_registers":["0x3103"],
 "regions":[{"name":"stream","start":"0xb72e0000","size":"0x10000"}]}
```

只对声明的寄存器且落入region的值归一成name+offset；one-past需显式endpoint。
workspace/RPM/LMEM/MMU/参考缓冲应逐项声明同名region，不能整体屏蔽地址寄存器。
长度、偏移、end=size-1/size和位字段保留；重叠匹配拒绝。不提供map时地址原样保留，
不能把分配地址差异当配置错误。

r69/r70 journal可用 `--source snapshot` 做格式自测，op=S、metadata标记snapshot，
compare拒绝使用；不能补造缺失写入。没有真实golden或板上两侧比较结果。

## 验证

厂商patch仅apply-check，未编译/加载：缺hdrdual6匹配源码/Module.symvers。
7.3实际启用TRACING/FUNCTION_TRACER后，heavy队列W=1模块和arm64 QEMU 25/25通过，
五个既有KUnit MODULE_DESCRIPTION警告。脚本测试覆盖DMA/offset、写次序、缺相位、
regmap去重、丢事件拒绝、首帧截断和snapshot拒绝。原始输出见窗口方案。
