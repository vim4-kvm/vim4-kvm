# 2026-11-07：按用户决定将 .42 设为正式默认

已将同一份 `.42` 整包安装为 Mainline 默认；最终自然启动的身份、完整模块、正式 APPEND、
fusb302 未加载及被动 4K 视频通过。正式身份和逐文件收据见
[sources.toml](../../packaging/kernel/sources.toml)、
[installed proof](../../packaging/kernel/releases/7.3.1-vim4-20261107.2/installed-proof.json) 和
[新 2372 基线](../../packaging/kernel/releases/7.3.1-vim4-20261107.2/baseline.json)。

**用户取消本次部署门禁及执行器适配：未跑九类、K9、解码冒烟或任何测试矩阵。**
不把此前 integration42 的成绩当成本次正式无线环境的完整验收。
未发 HID、切 EDID、操作源 Mac、改服务/持久模块配置或 saveenv。
`packaging/kernel/deploy42/` 半成品保持未跟踪，未修改或提交。

## 安装与两张 FIFO 票

复用[准备记录](2026-11-07-deploy42-preparation.md)的封存产品，没有重编或改包：
release `7.3.1-vim4-20261107.2`、源码 `3facfaa37284f7193508c2a16fbf5162c6242616`、
build ID `fa5a9fa53dc3f84802722702f18623730ab81d83`，整包 SHA256
`8fb7c55fce771a1ef076a4aa0014b35c5c76c596b78b09067632965f38842fa8`。
manifest 的原始 `hardware_validated=false` 不追改；本次有限范围另记
[validation](../../packaging/kernel/releases/7.3.1-vim4-20261107.2/validation.json)。

| 票 | 实际动作与结果 |
|---|---|
| 1640 | 入场 fd41fb5 的 2372 proof 相同；`/boot` 可用 104448000 B，大于整包启动文件加 20% 的 69625254 B。原字节保存 extlinux、kernels、runtime 登记。首次上传因暂存目录归 root 被拒，零安装/重启；同票换本任务目录后 SHA 核对通过，现有 register-runtime.py install 完成。 |
| 1640 | .42 自然启动，完整 2354 文件/2341 模块、已加载模块 build ID、运行 config、启动文件及 APPEND 均相符，fusb302 未加载。但 60 秒内 receiver 没收到可解码帧；内核 11.940810 秒有 `hdmirx link readiness revoked`（cable=0x0）。停止并复原三份登记原字节及旧共享运行器，自然回 fd41fb5，2372 proof 相同，4K H265 被动视频 300 帧/约 5 秒、59.973249fps。未追加候选启动，释放票。 |
| 1641 | t48 要求先离线分析历史，再授权一次重启及 240 秒被动观察。重新核 fd41 proof，核已安装 .42 的全部启动文件/模块；只恢复已验证的 Mainline 登记，没有重装或重编。自然启动 .42 一次；49 次采样后 receiver 通过，保留新默认并写收据，释放票。 |

两票均保留 Vendor 项和 default=Mainline；APPEND 与准备记录逐字相同，展开后的
`/proc/cmdline` 也逐字相同，包括 `module_blacklist=fusb302`，无线保持开启。
extlinux 只切 Mainline 的 LINUX/FDT。fd41fb5 的启动目录、完整模块及 Mac/VM 回退包保留，
旧文件逐项核对未变。仅清掉第一次票中本任务的 `/var/tmp/deploy42-direct-*` 上传目录。

## 历史时序与本次被动观察

先只读分析 r111–r115 的原始 kernel journal、UART 和 receiver/trace，派生
[时序表](data/2026-11-07-deploy42-hdmi-history.csv)及
[来源文件与 SHA](data/2026-11-07-deploy42-hdmi-history.json)。
这些候选是同一 .42 二进制的无线屏蔽 RAM 启动，不能直接代表正式启动参数。

| r111–r115 | 候选最早实际采到的 Wave5 CAPTURE DQ（启动后秒） | 候选最早观测到的解码帧（秒） | fd41 恢复最早观测到的解码帧（秒） |
|---|---:|---:|---:|
| r111 | 23.086568 | 20.341845 | 22.096871 |
| r112 | 21.080078 | 18.304098 | 22.137629 |
| r113 | 21.102741 | 18.292802 | 21.662780 |
| r114 | 21.107423 | 18.267422 | 23.210082 |
| r115 | 20.952205 | 18.346745 | 22.075821 |

这些是采证开始后的观测上界，**不是从启动起第一个编码完成的精确时间**。
五次候选日志及五次恢复 UART 均无成对 revoked→stable 事件，不能补算重锁延迟；
恢复侧也未封存完整内核 journal/编码 trace。TMDS measurement ready 独立列出，不当作 stable。

1641 首次 SSH 可达时 uptime 14.82 秒，boot_id 为
`8ad0825f-cb9c-4bea-98a0-19b37be62793`。从 uptime 15.20 秒起按 5 秒间隔采
增量 kernel journal、one-kvm journal、stream/status 及标准只读 QUERY_DV_TIMINGS，
持续 240.000098 秒，共 49 样本。49 次均有 3840×2160、约 59.999Hz 信号，boot_id 不变。
随后的 receiver 收到 **298 帧/约 5 秒，59.541206fps，3840×2160 H265**。
最终 UDC configured、fusb302 未加载，应用状态 streaming；收据和保护文件已封存。

观察期间没有 viewer，应用状态为 device_busy/fps=0；起 receiver 后能实际推进。
补充只读采样从 uptime 164.91 秒才开始，共 19 次，前段缺项不补造：
Wave5/t7_jpeg 在位，decoder suspended、Wave5 active，fuser 无 video 打开者；
video0/1/2 为三个 decoder，video3=VDIN、video4=Wave5。
`/dev/video_cap` 不存在，日志配置显示该路径，但没有 device_busy 对应的实际打开路径。
封存 One-KVM 源码 `2cf9ef4` 的 `wave5_device()` 按 sysfs name 找 VDIN，不能仅凭这个配置名
推断选错节点或 DOS 租约冲突。本次未定位第一次无帧的原因，也未以重启通过声称修复。

补充采样的 `dmesg --time-format=raw` 被本系统拒绝，错误原样保留；逐样本 kernel journal 正常，
另用普通 dmesg 在 `actual-device-paths.json` 和 `final-state.json` 补证。
r113 的 bindings-before 证明 K9 开始前 Wave5/JPEG/decoder 均已绑定，缺模块时的脚本 modprobe
分支没有执行；包内应用启动准备器 `vim4-mainline-prepare` 本身显式 modprobe wave5/t7_jpeg。

## 证据和未验证范围

[结果摘要及日志 SHA](data/2026-11-07-deploy42-default.json)覆盖两票；原始文件在
`logs/deploy-42/direct-{1,2,3}/`，其中 direct-1 是零安装的上传失败。
两次 .42 启动及中间一次 fd41 恢复均无观察到的冷复位，三次启动分别计数，不能据此宣布冷复位已修复。
VBUS 仍经 Mac→用户功率计→板子，本轮没有物理 VBUS/峰值电流观测。

此前 [.42 独立全集](2026-11-07-vdec-integration42-pd-results.md)仍为 127 Success / 3 Error /
2 内核 Timeout；没有完整 5.15 parity 结论。这次没有重跑 HEVC12/compliance、H264/MPEG2/JPEG、
K9、九类或 600 秒运动，也没有 GPU、音频、介质、HID 验收；全部记未运行。
19 档 HDMI 和 9/11 编码夹具缺口仍在 issues，不因本次安装而关闭。

收据同步更新 sources.toml 的正式身份、新基线和下一次构建序号；旧 release 收据不改。
离线仓库全套测试的实际输出保存在 `build/deploy-42/deployed-full-tests.log`。
