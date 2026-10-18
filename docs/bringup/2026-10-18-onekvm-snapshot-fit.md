# 2026-10-18：One-KVM MCP Fit 截图提前“超时”

结论：厂商 amlvconv 的帧率缓存取到未初始化值，随机丢掉单帧转换的唯一输入，
随后 EOS 被截图服务误归类为 Timeout。修复单帧 caps 协商和错误分类，
不改变共享采集、编码器或视频设置。

## 版本与根因证据

- 旧版：`8add2c49`，包 `2.5.1+vim4.20261018.32.dev.1.g8add2c4`。
- 最终代码：One-KVM `mcp-web` 的 `04bce8c8`、`c95b4099`，已快进合入
  `mcp-integration`；包 `2.5.1+vim4.20261018.32.dev.4.gc95b409`。
- 板上 3840×2160 NV21，H.264 共享管线，30000 kbps；保持用户当前 HDMI 桌面。
- 旧版 8 次试拍有 5 次失败（其中稳态失败为 27–43 ms）。失败帧的插件日志为
  `divisor > 1`、`remainder=1`、`drop frame`；成功帧的随机比值小于 1。
- `gst_aml_vconv_transform_caps` 未检查 `gst_structure_get_fraction` 的返回值，
  无固定帧率的模板查询会把栈值写入缓存；0/1 又不覆盖这些缓存。
  Appsrc 通常直接推送 CAPS，不先做初始化输出帧率所需的反向查询。

仅设置输入和输出 capsfilter 的帧率仍不足以修复：首次候选上板虽然试拍成功，
输出帧率缓存仍是随机值，未作为验收版本。最终版复制单帧输入 caps 并设为 1/1，
约束 GE2D 输出同为 1/1，在提交唯一输入帧前显式查询下游 caps。
板上应用日志确认两端均为 1/1、比值为 1、余数为 0。

`try_pull_sample` 的 None 不只表示超时；现在提前 EOS 和 bus error 返回
Unavailable，等待期间每 10 ms 检查 bus，期限耗尽才返回 Timeout。
MCP `serverInfo.version` 使用构建环境 PACKAGE_VERSION，无此变量则回退 Cargo 版本。
最终板上 initialize 响应与已安装包版本一致。

## 截图验收

移除临时 GST_DEBUG systemd 配置并重启正常服务后，从 Mac 经局域网 HTTP MCP
顺序调用；计时包含请求、转换、JPEG、传输与 JSON 解码。成功样本使用 nearest-rank
P50/P95；无重试。Fit 输出 1280×720，Region 调用 zoom `[0,0,320,180]`。

| 调用 | 成功 | P50 ms | P95 ms |
|---|---:|---:|---:|
| Fit，返回后间隔 0.3 s | 50/50 | 142.90 | 158.42 |
| Fit，无间隔 | 50/50 | 108.25 | 140.09 |
| Region，无间隔 | 30/30 | 266.91 | 283.78 |

## 对 H.264 推流的影响

使用 `tools/one-kvm-smoke.mjs --exclusive --mode=h264 --seconds=120 --warmup=15`，
网页账户通过环境变量传入，Mac Chrome 155.0.8059.80 无界面运行。
两轮均为 3840×2160 H.264、30000 kbps，每轮 15 秒预热、120 秒采样。
截图轮每 0.5 秒发起一次 Fit，覆盖整个测量窗口，含窗口外预热/收尾共 253/253 成功，
截图 P50/P95 为 140.22/156.17 ms。

| 指标 | 不截图 | 每 0.5 s 截图 |
|---|---:|---:|
| 解码 fps | 59.997 | 60.006 |
| 呈现 fps | 60.000 | 59.998 |
| 呈现间隔 P50 ms | 16.7 | 16.7 |
| P95 ms | 18.1 | 20.4 |
| P99 ms | 21.0 | 33.6 |
| 最大 ms | 33.6 | 37.9 |
| >50 / >100 / >250 ms 次数 | 0 / 0 / 0 | 0 / 0 / 0 |
| 回调漏采 | 6 | 286 |
| 丢帧 / 丢包 / freeze 增量 | 0 / 0 / 0 | 0 / 0 / 0 |

平均 fps 保持，但呈现 P95/P99 分别增加 2.3/12.6 ms，最大增加 4.3 ms。
回调漏采不能直接等同视频丢帧。这是当前用户桌面负载下的浏览器回调测量，
没有启动固定运动标记，不是光学显示或端到端延迟验证。

第一次基线期间用户 UU 会话接入，把共享编码器从 H.264 切到 H.265，脚本
以 `Video stream changed during measurement` 拒绝结果；该窗口已保留并剔除。
日志确认 UU 会话随后关闭、管线释放后，重新进行了上述两轮有效 H.264 对照。
脚本每轮结束恢复进入测试前的编码模式；最终服务未保留 GST_DEBUG 配置。

## 构建与测试

`vim4-kvm-builder:ubuntu24.04`，使用 `onekvm-mcp-cargo` / `onekvm-mcp-target`
卷执行 `cargo test --locked --features vim4 --lib`：706 passed，0 failed，1 ignored。
新增测试覆盖未知/分数采集帧率、原始 caps 不变、单帧前必须完成固定 caps 查询，
以及丢帧 EOS、管线错误和期限到期三类结果。临时副本移除查询后的负向测试按预期
失败为 `conversion ended without producing a frame`；正式源码保持修复。

正式 package 流程再次通过相同库测试、前端 typecheck/build、release 构建及
77 项工作区测试（1 项跳过）、20 项 One-KVM 部署测试。verify 通过校验和、ARM64 ELF、动态库、
sudoers、配置保留、更新 feed、升级与认证更新 API 验证；board deploy/check 通过。
未调用键鼠 MCP 工具，未删除 VPU mutex，未更改 USB、EDID、HDR 设置。

原始证据和复测脚本：`logs/onekvm-mcp/snapshot-fit-fix/`，包含旧版/最终版
GStreamer 日志、逐次截图数据、initialize、库测试、负向测试、打包、验证和部署日志。
