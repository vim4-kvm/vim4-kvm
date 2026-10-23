# 2026-10-23：HDMI RX 音频 ENOLINK 基线对照

本条单独跟踪 ASoC `hw_params -67`，用于区分显示 M0 与既有音源重协商问题。
前三轮背景及回退见 [M0 音频复核](2026-10-23-display-m0-deploy.md)。
基线已在失锁时重开标准 ALSA PCM，复现完全相同的 ASoC hw_params -67。
这条错误路径不需要 M0；自然 One-KVM 竞态的发生概率仍未证明相同。

## 匹配源码与可达路径

基线 `0196fe22ecf0104d96b7ef0fa497ca2317bd20bb`，运行 build ID
`3a61b75bccf8c46e9411dee92928999884bbfc7f`；One-KVM `382efb70e7ebb`，
manager `4ea748426935`。M0 候选 `47878a0c611d` 只新增独立 DTS 与 Makefile 一项，
没有改变以下音频实现；这不足以单独排除时序影响，须以上板对照为准。

内核 `drivers/media/platform/amlogic/t7-hdmirx/t7-hdmirx.c`：

- `t7_hdmirx_audio_hw_params_locked()` 传播 `t7_hdmirx_read_audio()` 的错误，
  并在实读格式与已资格确认的 `rx->audio_format` 不同时返回 `-ENOLINK`。
- read_audio 在 core/link 未 ready 或 AIF header 无效时返回 ENOLINK；
  两次 AIF/包属性不一致、校验和错误、ACR 计算的采样率未稳定则返回 EAGAIN。
- `t7_hdmirx_validate_audio()` 对零 TMDS/N/CTS 返回 ENOLINK，但 read_audio 将
  validate 结果折成 pcm 布尔值，不能把这一路直接认作 hw_params 的 -67 来源。

One-KVM `src/audio/capture_linux.rs` 在打开 PCM 前查询 ALSA 控件 snapshot，若未 ready
直接退出；若 ready，使用源端 native rate 打开 PCM。运行中 generation/format 改变会退出，
由 recovery 串行重开。`src/audio/recovery.rs` 未 ready 时每250ms查询，不打开 PCM；
ready 后先经历退避、枚举和线程启动。capture 的 snapshot 与内核 hw_params 之间
不是原子事务，源端仍可能再次失锁/改格式；这解释了可达竞态，不证明本次具体返回分支。

定位方向：同时保留 source generation/state、AIF、ACR、link_ready 与 PCM 重开时间；
核对 ready 到 hw_params 之间是否换代。后续可在 hw_params 返回ENOLINK/EAGAIN后
重查generation/state、有界等待重新资格；保留驱动拒绝失锁的保护，不启动旧native rate。

## 第四轮测试方法

Mac board/heavy 双锁覆盖全部操作。先用 verify-restore 核对完整基线身份，原计划三轮：
原 4k60 fixture 的 EDID18→H.264/H.265→original 恢复，接着启动440Hz源，
新 AudioData 工具测 48→44.1→32→48 kHz，每段15秒、前5秒按工具设计留作稳定期。
由格式变化触发 One-KVM 旧 PCM 关闭及重开，不手工写音频/时钟寄存器。
最后先恢复48k并确认RX，再停止音源。未做物理扬声器录音。

监督脚本 `build/display-m0-r4/baseline-audio.py` 脱离会话持双锁，标准流写文件；
日志 `logs/display/m0-r4/baseline-window.log`，逐轮 `baseline/round-N-{4k60,audio}.log`。
另以200ms只读采样 RX 状态，完整保留 dmesg 前后与 journal；不使用 strace。

## 实际结果与判定边界

首轮4K60及四段 AudioData 全通过，窗口101–102/端点，无失败或观察器错误。
第二轮4K60通过，接着 CoreAudio 尚未重新枚举 `RTK UHD HDR`，工具退出7，
音频测量未开始；该次不能算连续性失败。给 final-regression 音源入口加最多30秒
只读枚举等待，未出现则不打开音源、不改采样率；离线测试覆盖迟到与缺失。

接着让音源与观看者持续存在，八轮 EDID18↔original，每个 EDID 内快速切换
48→44.1→32→48 kHz；实际设备名分别为 `VIM4-UHD-60` / `RTK UHD HDR`。
前两次压力尝试因设备名选择不完整中止，已恢复 original，不计通过；修正后的
`baseline-burst-3` 八轮完整执行，One-KVM 多次 format changed / 自动重开，
**未自然触发同样的内核 -67**。之后7段、每段20秒的 AudioData 严格稳态检查通过，
端点各151–152窗、无失败或观察器错误，最后确认恢复48k。

为单独检验“失锁后 PCM 重开”的返回路径，临时停止 One-KVM 避免占用，重复三轮
原有 `fixture.py original loss`（HPD低5秒）；在该窗口用标准 ALSA 请求：

```sh
sudo timeout 3 arecord -D hw:0,0 -f S16_LE -r 48000 -c 2 \
  --period-size=960 --buffer-size=4800 -d 1 -t raw /dev/null
```

基线产生与上一轮逐字相同的两行 ASoC -67；前两轮分别在启动后1038.007/1045.610秒，
证明未配置 M0 reserved-memory、显示时钟引用或 tty0 时，普通失锁重开已经可达该诊断。
这是有意失锁的组件复现，不能写成“三轮常规 One-KVM 回归都自然复现”，也不能反推
此前05:36:55的具体驱动分支或调度影响已定位。暂不修改驱动/应用，不宣称问题修复。
诊断的 errno 应继续保护硬件，不应让 PCM 在无有效链路时启动。

证据根目录 `logs/display/m0-r4/`：`baseline-window.log`、`burst-window-3.log`、
`baseline-burst-3/steady-audio.log`、`baseline-pcm/{arecord-*.log,reproduction.json,journal.txt}`。
组件复现后已恢复 original EDID、One-KVM，重测48/44.1/32/48k、每段20秒：两端点
各151–152窗、零失败、无观察器错误，确认48k后停音；真实键盘/鼠标/点击/滚轮通过。
One-KVM与manager均active，UDC configured，基线状态passed。
正式显示窗口见 [M0 第四轮](2026-10-23-display-m0-r4.md)。
