# 2026-11-05：r61 官方/Khadas parser 同窗像素对照

同一 `.28`、同一私有 v4l2codecs，仅切换 h264parse：**官方组14 Success/3 Fail，
Khadas组17 Fail**。13条隔行流和CAWP5在官方parser下帧数完整、逐帧MD5全部匹配参考；
这些旧Fail的原因是Khadas用户态parser，不是本轮确认的内核像素缺陷。
MR3/MR4/MR5两组输出相同且都Fail，继续定位驱动LTR/MMCO路径。

原环境的全集结论仍为110/135，不能把混用官方parser的结果改写为原环境通过数。
本轮只报告官方parser子集14/17；没有重跑全集，没有部署或替换系统包。
Sharp_MP_Field_1_B、Sharp_MP_PAFF_1r2预计同类，**本轮未运行、官方parser效果未验证**；
本轮实际运行的Sharp_MP_PAFF_2r不可与它们混淆。CVFC1裁剪问题未运行。

## 窗口、恢复与身份

协调者批准[计划](2026-11-05-vdec-parser-ab-plan.md)，额外要求入场连续运行至少5分钟。
FIFO 1346，sampling，全窗约19分钟；只启动一次`.28`，没有候选重试。
入场连续UART观察300秒，uptime2725.97→3026.43秒，boot ID相同、未观察到新启动。
正式proof和4K视频通过后才上传。两组YUV保守上界452666880字节，入场要求4GB可用空间。

候选源码`960132382e00864f4944aee077cd621927a97bb0`，build ID
`81bb2f999ffffb38d549afbf8b15fb3048184c0f`，既有`.28`包未重建。
parser与私有插件身份沿用[visl记录](2026-11-05-vdec-visl-controls.md)，每组实际
gst-inspect Filename/SHA对应私有官方或系统Khadas库，依赖路径与哈希一并归档。
正式默认仍是`7.3.1-vim4-20261105`，build ID `bdbfa439f298e92b5bad092528d11119a974f262`。

stateless streaming compliance **60/60**，media compliance **8/8**；34次解码全部运行，
无Timeout、无窗口级内核异常、无冷复位。正式恢复及2372个保护文件核验通过，4K H.265
视频推进298帧，59.5646fps。正常恢复启动一次；本轮无自然恢复启动。
清理helper重新上传至独立cleanup目录后执行，任务候选/固件副本已清理；正式模块目录不动。
1005个任务文件逐项哈希比对归档后删除，FIFO已释放。
执行器先正常重启退出只读模块bind，再清空候选挂载目标；未额外启动一次“清理后重启”。

证据：`logs/hwdecode-parity-r61/` 的连续UART/主机时戳、entry-uptime、baseline proof、
returned-baseline-identity、returned-video和complete；
`build/hwdecode-parity/run61/board-upload.tar`及`board-upload-files.json`为完整归档/哈希。
展开后的`archive/results/<vector>-<group>/`包含Fluster原始JSON、完整YUV、ioctl和队列trace。
`execution.log`、`window.log`、`output-budget.json`保留执行与预算记录。

## 逐帧比较及首错定位

宿主FFmpeg单线程解码同一SHA输入，passthrough输出yuv420p，ffprobe保存尺寸和每帧信息。
全部输出长度均为完整帧大小整数倍；本批格式/尺寸一致，无需crop变换。
一次性`run61/compare.py`、`*.reference.log`、`*.frames.json`、`pixel-comparison.json`
保存命令结果和每帧MD5，不引入仓库Python驱动测试。
[逐流尺寸/帧数/整文件MD5/首错](data/2026-11-05-vdec-r61-pixels.csv) 可独立复核。

14条Khadas输出不是全部等于参考的前N−1帧：

- CABREF3、CAMA3、CAMANL3、CAPAMA3、CAWP5少最后一帧，已有帧完全正确。
- CAMA1、CAMANL1/2、CAPA1、CVMA1、CVMANL1/2、CVPA1少显示索引88，
  原索引89仍输出；Sharp_MP_PAFF_2r少索引13，原索引14仍输出。

逐流删除上述唯一参考帧后，**剩余帧MD5序列与Khadas输出完全相等**；不是尾部错误像素。
解码顺序末slice缺失与显示重排使缺失位置不同，不能据前N−1直接比较出现的最后一帧差异
误判驱动。官方组恢复完整序列，14条每帧都与软件参考相等，Fluster总MD5同时Success。

| 流 | 两组帧数 | 首个错误显示索引（0起） | 错误帧数 | 首错帧类型 |
|---|---:|---:|---:|---|
| MR3_TANDBERG_B | 300 | 10 | 263 | P、逐行 |
| MR4_TANDBERG_C | 300 | 16 | 264 | P、逐行 |
| MR5_TANDBERG_C | 300 | 16 | 264 | P、逐行 |

两parser在三条MR上整文件MD5相同，排除本次parser尾部缺失影响；结合visl请求完整及
控制采证，下一步重点是驱动参考列表、微码重排握手、长期参考标志及MMCO后身份。
不能把ffprobe coded_picture_number直接当请求序号；完整MMCO/POC重演和寄存器根因仍待查。
之前per-field LTR位差异不影响这些逐行代表，不据此提交猜测修复。
