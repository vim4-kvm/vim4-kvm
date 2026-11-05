# 2026-11-05：r52 基线计划不一致，解码前停止

`.28` 正常启动并通过候选身份检查；测试计划仍带旧正式 `.3` 的保护文件哈希，
在 `/boot/extlinux/extlinux.conf` 检查处被拒绝。compliance、Sharp 跟踪和
全部 Fluster **未运行**。这是准备脚本错误，不是解码失败，也不是 r51 冷复位复现。

## 身份与原因

内核源码、配置和模块仍为[已逐提交验证的 `.28`](2026-11-05-vdec-integrated-rebase.md)，
没有 HEVC 私有草稿。RAM 包仅重新生成恢复入口，绑定新正式默认，包 SHA-256 为
`1ff9d5241ae352abf2acc18f6a3c8aaeff7353f24f1dd7395c6a27fb08f77870`。
`build/hwdecode-parity/run52/repack-identity.json` 保存重新封包身份；原内核产物未变。

准备流程更新了 `baseline.json` 和 RAM 恢复入口，却从 r51 复制了
`validation-plan.json` 中的 `protected_files`。原始计划保留不改。
远端运行身份与 watchdog 检查通过，保护文件检查失败，尚未创建结果目录；
后续 tar 的目录不存在错误是未进入验证的结果，不能替代首个失败原因。

后续计划从当前 baseline 的 files 生成保护清单，排票前离线要求逐项完全相等；
执行入口也与恢复 proof 核对。旧哈希、缺项、多项及空清单均拒绝，不放宽板端检查。
跟踪功能仍没有实际运行证据，不能声称 Sharp 尾帧已定位。

## 原始证据与恢复

- `logs/hwdecode-parity-r52/validation-fluster-1793909129398391000/window.log`：
  `Protected baseline changed: /boot/extlinux/extlinux.conf`。
- 同目录保存实际上传的计划、内核 manifest 和 runner SHA；
  `build/hwdecode-parity/run52/boot.log` 保存候选启动，`window.log` 保存自动收尾。
- `logs/hwdecode-parity-r52/returned-baseline-identity.json`：恢复
  `7.3.1-vim4-20261105`，build ID `bdbfa439f298e92b5bad092528d11119a974f262`，
  全部 2372 个保护文件与新 proof 相等，包含 manager 二进制。
- `returned-video.log`：3840×2160 H.265，59.96 fps，无新增 dropped/freeze/lost。
- 518 个上传文件归档、逐项校验并复核板端未变后删除；原始包与校验清单留在
  `build/hwdecode-parity/run52/board-upload.tar`、`board-upload-files.json`，
  `upload-cleanup.log` 确认删除。

协调者批准 r53 使用同 `.28`、同测试顺序按 FIFO 重试；恢复目标仍为新正式默认。
