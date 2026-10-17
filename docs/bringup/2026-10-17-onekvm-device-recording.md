# 2026-10-17：One-KVM 设备端带声音录屏

One-KVM `f42af7e7` 新增设备录屏，`3e97ca23` 将入口放到所有控制台布局的公共顶部。
复用现有 H.264/H.265 与 Opus 编码，保存 MKV；支持开始、停止、下载、删除、状态恢复，
不因网页关闭或播放静音而结束。原厂 GLKVM 的录屏功能仅作为需求参考。

## 软件验证

- ARM64 Ubuntu：626 项 Rust 单元测试、18 项部署助手测试通过，前端 typecheck/build 通过。
- 真实软件编码、MKV 封装和解码测试覆盖 H.264/H.265、非静音 Opus；另测序号断裂、
  文件路径保护与停止请求被取消时的资源归属。
- 主仓库离线测试 77 项，跳过 1 项，其余通过。
- 非 VIM4 的 ARM64 `cargo check --locked` 在原有 hwcodec RKMPP 分支失败：Ubuntu
  FFmpeg 没有 `AV_HWDEVICE_TYPE_RKMPP`。未修改该平台依赖，也未声称此目标通过。

## 候选版本实板验证

先用已验证的候选包独立实例（18081、临时账户和数据目录）验证，保留正常应用账户。
候选二进制来自 `f42af7e7`，网页覆盖目录使用 `3e97ca23` 的构建结果。
三个布局均实际打开录屏弹窗；浮动布局先折叠原有工具栏。
使用 Mac 的 RTK UHD HDR HDMI 输出，3840×2160@60 Hz、真实运动图案和定向 440 Hz 音频。

| 输出 | 时长 | 解码视频帧 | 音频 | 文件大小 |
|---|---:|---:|---|---:|
| H.264 MKV | 12.700 s | 762 | Opus、48 kHz、双声道 | 7,508,860 bytes |
| H.265 MKV | 12.660 s | 760 | Opus、48 kHz、双声道 | 6,360,345 bytes |

每次录制期间关闭全部观看页面约 12 秒，再重新打开停止和下载。FFmpeg 严格解码无错误；
每秒取样得到的 13 张画面均不同，排除重复静止画面。解码音频第 1–6 秒 RMS 分别为
0.07063/0.07108，零交叉测得 440 Hz；不是仅凭音轨存在判断有声音。

认证拒绝、重复开始、录制中文件禁止下载/删除、停止后下载删除、音频停止触发收尾、
恢复音频后重新录制均通过。临时目录的 128 MiB tmpfs 验证空间不足拒绝启动；
扩大到 320 MiB 后开始录制，再分配 80 MiB，使可用空间低于 256 MiB，验证自动停止且
已有文件完成封装。该测试未填满 eMMC。

正常停止测试服务时，约 3.23 秒的录像完成封装，重新启动同数据目录后可列出该文件。
临时实例和测试账户清理后恢复原 One-KVM 与管理器；HDMI 服务 InvocationID 保持
`595934a7c8294fdeaa4679b35292629b`，未更改 EDID、HPD 或原有账户配置。

证据：`logs/one-kvm-recording/` 的 `hardware-candidate.log`、`boundaries.log`、
`media-summary.json`、两份 MKV、解码 PCM、画面 MD5 和截图。复测入口为
`tools/one-kvm-recording-check.mjs --exclusive`，环境变量与其他 One-KVM 测试一致；
`HDMI_TONE` 可指定定向测试音程序，`RECORDING_OUTPUT` 指定下载目录。

## 最终安装与回归

正式安装包 `2.5.1+vim4.20261017.2` 从干净的 One-KVM `3e97ca23` 构建，包校验、
ARM64 依赖检查、配置保留及升级验证通过。通过 `board.py deploy --exclusive` 安装后，
使用已安装的 `/opt/vim4-onekvm/one-kvm` 和内嵌网页，在临时账户实例重跑三个布局与
完整录屏流程，未使用网页覆盖目录。新增验证观看页面在录制前后均能播放视频，
以及录制中切换编码会终止并报告原因。

最终 H.264 文件 13.320 秒、7,816,940 bytes；H.265 文件 13.300 秒、6,706,734 bytes。
两者均为 3840×2160 视频和 48 kHz 双声道 Opus，FFmpeg 严格解码通过。最终证据保存在
`logs/one-kvm-recording/final/`，测试日志为 `hardware-final.log`。

清理临时实例后，原 One-KVM 与 vim4-manager 均恢复 active，健康检查返回 ok；
dpkg 确认已安装上述版本，`dpkg --audit` 与 `dpkg -V vim4-onekvm` 无异常。
原应用账户及数据目录保留。部署日志在 `logs/one-kvm-recording/deploy/`。

不把短测推广为长时间口型同步、所有播放器兼容、突然掉电可恢复或慢盘性能保证。
