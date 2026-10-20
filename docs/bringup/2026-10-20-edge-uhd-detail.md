# 2026-10-20：7.x UHD 清晰度与 Mac 渲染分辨率

摘要：用户反馈当前 7.x 的 4K 画面像 1080p。板端输入/采集与网页解码均报告
3840×2160，但 Mac 当前是 1920×1080、1 倍渲染。保持相同内核、应用、H.265
和 30 Mbps，只切换 Mac 的低分辨率/HiDPI 模式，对照确认单像素细节随输入端
模式丢失或恢复。最终保留逻辑 1920×1080、实际 3840×2160 的 HiDPI 模式。
没有因此宣称完成与 5.15 的复杂运动画质对齐。

## 原始状态与对照

内核 `46f8489461869`，One-KVM `9f457566ad78`，应用 output.height/fps 均为 0，
未设置缩放。H.265、Custom 30000 kbps；RX 状态为 3840×2160、TMDS 约 594 MHz。
VDIN 缩放寄存器关闭；网页实际解码为 3840×2160。测试浏览器的 CSS 视频框约
1687×949、DPR 1：缩小的网页框不应拿来代替原生帧检查。

Mac 的 `CGDisplayCopyDisplayMode` 最初为 mode 17：width/height 和
pixelWidth/pixelHeight 都是 1920×1080，NSScreen.backingScaleFactor=1。
提供的 mode 16 则是逻辑 1920×1080、pixelWidth/pixelHeight=3840×2160，scale=2。
选择 HiDPI 保持桌面逻辑大小，而提高渲染栅格；当前不是通过降低帧率或增加码率修正。

使用 [原生测试图](../../tools/hdmi-resolution-source.swift) 显示横向/纵向的
1、2、4、8 像素黑白条纹。工具要求启动时的渲染栅格为 3840×2160，禁止静默把
1080p 测试图当作原生 UHD；缓存本窗口的原生 PNG 作为参考。
网页按 videoWidth/videoHeight 创建 canvas 并读回解码帧，不用 CSS 截图。
同一个窗口保持显示，依次切换源模式做高/低/高对照。

| 源模式 | 网页解码尺寸 | 1 px 横/纵条纹标准差（0–255） | 与参考的灰度 MAE |
|---|---|---|---|
| 4K HiDPI | 3840×2160 | 127.5 / 127.5 | 0 / 0 |
| 1080p 低分辨率负对照 | 3840×2160 | 0 / 0 | 127.5 / 127.5 |
| 恢复 4K HiDPI | 3840×2160 | 127.5 / 127.5 | 0 / 0 |

原生 HiDPI 首轮的全部八个条纹内部区域与参考灰度逐像素一致。这证明本次 H.265
链路能传递 UHD 单像素亮度细节，排除了该链路固定先降到 1080p 再放大的假设。
低分辨率负对照仍有 4K 解码尺寸，却无法保留单像素条纹，复现了本次清晰度风险。
这项静态亮度测试不证明色度 4:4:4、运动纹理、光学观感或压缩画质全面等同 5.15。

## 复测与工具

```sh
swiftc tools/hdmi-resolution-source.swift -o /tmp/hdmi-resolution-source
VIM4_HDMI_DISPLAY=VIM4-UHD-60 /tmp/hdmi-resolution-source 120 /tmp/NEW-reference.png
python3 tools/hdmi-resolution-check.py /tmp/NEW-reference.png /tmp/NEW-decoded.png
```

测试窗口临时覆盖选中的物理 HDMI 桌面，不注入输入、不改变分辨率，结束恢复原画面。
默认拒绝覆盖参考文件。应先在 Mac 选择 HiDPI 或原生 UHD 渲染模式，避免按界面的
“1920×1080”标签判断实际栅格；检查 pixelWidth、pixelHeight 和 backingScaleFactor。
本轮通过 CoreGraphics 配置事务以 `forSession` 完成切换；单独调用
CGDisplaySetDisplayMode 后立即退出的早期尝试没有保持目标模式，日志保留。
跨重新接线/重启是否保持 HiDPI 未验证，不能依靠本次 session 设置保证。

离线检查依赖 Pillow，拒绝 CSS 缩小截图和无有效条纹的参考；输出对比度、相关性、
灰度 MAE，以两个方向的单像素细节决定退出码。相关性取绝对值，允许一像素的
相位反转；它是空间分辨率诊断，不是通用图像质量分数。测试包含 1080p 下采样后
放回 4K 的真实退化负例，以及灰度范围变化的正常输入。

证据在 `logs/kernel-edge/quality-*`：display-modes-before、control-low-mode、
display-mode-final 日志，chart-reference.png、chart-browser-7-h265.png、
chart-low-source-control.png、chart-hidpi-restored.png 及对应原生尺寸 JSON，
chart-{native,low,restored}-check.json。负对照的检查按预期失败。
最终已停止测试窗口，恢复桌面和 H.265；HID online/configured，内核 taint=0。
原先的 HID/音频适配工作继续，尚未完成的音频不会被此项结果覆盖。
