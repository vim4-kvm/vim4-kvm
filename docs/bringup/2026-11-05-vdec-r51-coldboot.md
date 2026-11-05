# 2026-11-05：r51 `.28` 启动冷复位

`.28` 在进入解码测试前发生非请求冷复位，自动回到正式 `.3`。候选启动身份
检查未通过，compliance、Fluster、Sharp 输出与 V4L2 跟踪全部未运行。此事件
计入已知 cold_boot 的候选记录，不作为解码功能失败或根因证据。

## 身份与阶段

内核 `7.3.1-vim4-20261105.28`，HEAD
`960132382e00864f4944aee077cd621927a97bb0`，Image build ID
`81bb2f999ffffb38d549afbf8b15fb3048184c0f`。生产配置 SHA-256
`7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`，
未使用调试片段或 HEVC 草稿。完整构建身份见[重放记录](2026-11-05-vdec-integrated-rebase.md)。

UART 确认实际进入 `.28`：Linux 启动后约 6 秒、NetworkManager/systemd-hostnamed
启动阶段，直接出现 NUL、`T7:BL:`、BL2 和 U-Boot；随后 `stick_reboot_flag=0x0`
并启动 `.3`。没有 panic/Oops 或正常关机尾部。冷复位前最后一条带内核时间的
日志为 **5.540308 秒**；本工具 UART 没有逐行主机时间戳，不能把这个末条日志时间
当作精确复位时刻，“约 6 秒”仅为启动阶段近似值。

前面可见 brcmfmac 固件加载和 Bluetooth 初始化，但未进入候选 ready，未启动
任何解码验收动作。UART 中后续登录提示属于 `.3`，不能据此判定 `.28` 完成启动。
`boot-candidate` 的 ready 检查要求 `.28`，而板子已回 `.3`，所以反复触发 release
断言，外层在 180 秒超时后执行正常恢复流程；没有绕过身份检查继续跑测试。

## 证据与恢复

- 连续 UART：`logs/hwdecode-parity-r51/uart-1793898813155997000.log`。
- 启动/自动收尾：`build/hwdecode-parity/run51/boot.log`、`window.log`。
- 正式身份：`logs/hwdecode-parity-r51/returned-baseline-identity.json`，release、
  build ID、正式文件哈希匹配 `.3`；启动默认配置未修改。
- 实际视频：`returned-video.log`，3840×2160 H.265，5 秒 299 帧、59.76 fps，
  dropped/freeze/lost 增量均为零。
- 515 个上传文件逐项归档、核对板端未变后删除；`run51/board-upload.tar`、
  `board-upload-files.json` 和 `upload-cleanup.log` 保留原始证据。

本次记入 [coldboot 统计表](data/2026-11-05-tcpm-coldboot-events.csv)。它是生产配置
候选启动，不加入此前正式 `.3` 的 20 次启动分母，也不由一次事件推断复位概率。
没有修改 MMC/PWM/ADLA 或猜改 PD。协调者批准同一 `.28`、同计划原样重试一次，
FIFO 排在正式部署后；届时须先按新正式基线重新生成和核对 proof。
