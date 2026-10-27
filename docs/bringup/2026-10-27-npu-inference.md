# 2026-10-27：NPU 真实推理与分类、文字识别验证

当前 VIM4 的 NPU 已实际完成模型推理。内核 `5.15.137-vim4kvm-hdrdual6`，
ADLA KMD `1.4.0.3`、用户态输出版本 `1.4.0.2`，系统包 `libadla 0.6-202409`。
未更新驱动、运行库、系统包或 KVM 应用，未重启服务或板子。

## 模型与方法

模型及样例来自 [Khadas 官方仓库](https://github.com/khadas/vim4_npu_applications/tree/3e87c7d2832b7cbd4dc727a325c4a89146e7a952)，
固定提交 `3e87c7d2832b7cbd4dc727a325c4a89146e7a952`；下载后按 Git blob SHA 校验。
VGG16 为 32×32 CIFAR-10 分类，DenseNet CTC 为 280×32 单通道文字识别。
两份模型 SHA256 分别为：

```text
vgg16_int8.adla       07520d099d5377d1acd39c6f30bdbdd97490dc7adb3767ac49e7d46b3953572b
densenet_ctc_int8.adla f70943193e429ea08195b422931e205f86e43f2a48fa37148f1454d6aae9c6e9
```

独立 C 程序用板上头文件与 `libnnsdk` 编译，显式选择 `AML_HW_NPU`、`NN_ADLA_FILE`。
图片在 Mac 上用 Pillow 双线性缩放并转 float32/255；分类按官方样例使用 BGR，文字使用灰度。
与官方 OpenCV 插值不保证逐像素一致。输入文件通过 `BINARY_RAW_DATA` 提交，结果以 float32 获取。
本机持 `logs/board.lock`，板上持 `/run/lock/vim4-media.lock`，每个进程有 20–25 秒超时。

先单独跟踪测试进程的设备调用，确认打开 `/dev/adla0`，INVOKE 与 WAIT_UNTIL_FINISH 均成功。
另一次 5 轮跟踪得到 5 次 INVOKE 和 5 次 WAIT，排除只返回缓存结果；不跟踪 One-KVM。
耗时测量另外运行，不带 strace。每份输入同一上下文执行 101 轮，首轮后统计 100 轮。

## 结果与边界

| 样例 | 首轮识别结果 | 100 轮平均输入提交＋推理＋结果获取 | 最小／最大 |
|---|---|---|---|
| VGG16 飞机 | airplane，0.5625 | 0.582ms | 0.529／0.933ms |
| VGG16 鹿 | deer，0.9961 | 0.591ms | 0.527／1.932ms |
| DenseNet CTC 文字 | KhadasTeam | 1.965ms | 1.883／2.596ms |

每轮检查输出存在且全部数值有限；首轮分类与文字结果单独解码核对。
耗时不含图片解码、缩放、模型加载及后处理，不是 4K 全屏 OCR、模型精度套件、
长期稳定性或 3.2 TOPS 峰值验收。原 KVM 服务保持运行，未控制其观看负载。
One-KVM PID 105379、HDMI PID 1081 保持；内核 taint 12800 未增加，
没有新增 ADLA fault/timeout，测试后驱动自动回到 clock-gating/suspended。

原始程序、下载清单、输入、输出和日志位于本机忽略目录 `build/npu-probe/`，
板上工作目录为 `/var/tmp/vim4-npu-probe-20261027/`。复测示例（khadas 用户）：

```sh
cd /var/tmp/vim4-npu-probe-20261027/airplane
../probe ../vgg16_int8.adla ../airplane.f32 101
```

当前验证限于厂商 5.15 与上述两份模型；7.3 和其他模型未验收。
