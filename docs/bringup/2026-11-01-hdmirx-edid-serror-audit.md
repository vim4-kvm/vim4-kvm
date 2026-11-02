# 2026-11-01：HDMI-RX EDID 撤回 SError 离线审计与 COR 复位竞争修复

结论：N 窗 SError 的触发条件已由 f951 消除，具体异步 MMIO 事务离线无法定位，**不安排专门分离窗口**。
审计另发现 PCS 与 PCM 对同一 COR_POWER_RESET 的读改写竞争，已在候选分支修复，**未上板、未进正式分支**。
全程仅开发机与 VM，无板端访问。前情见 [EDID 修复门禁](2026-10-31-uhd6-edid-review.md)。

## 根因边界

- 运行期零块撤回误用退出清理 `t7_hdmirx_ddc_stop()`，在 link/audio 工作队列仍运行时恢复探测前
  TOP_PORT_SEL / TOP_SW_RESET；f951 改为只降 HPD、置长度零，保留 DDC 归属。
- pstore 的 pc 位于 `t7_hdmirx_video_status_reason+0x38` 函数序言，只能定位异常送达上下文；
  无法区分 PORT_SEL 与 SW_RESET 的作用。区分需要各一次的上板单变量实验，对产品无直接收益，不排。
- 厂商 common_drivers `31619c527655` 只在已初始化硬件上执行具名 HPD/EDID 复位并在复位释放后写 RAM；
  未证明 EDID 复位或 HPD 期间任意 COR/PHY/FRHDMIRX 访问安全或必然出错。
- 1080p24/25 撤回后立即发布未锁定属于重锁边界，与 SError 分开，见 [uhd6 正式记录](2026-10-31-uhd6-formal.md)。

## 修复候选

`vim4-kvm/linux` 分支 `fix/hdmirx-cor-reset-lock` = `f2e8424261af`（父 f951e2d24d32），3 文件 +35/−2。
`t7_hdmirx_reset_pcs()` 用既有 `audio_lock` 覆盖 COR_POWER_RESET bit 4 的完整读改写脉冲；
PCM prepare/free 已在同锁内更新 bit 1。唯一调用者 link_work 在调用前已释放 audio_lock，
嵌套顺序保持 link → audio，无反向获取；回调与工作队列均为可睡眠上下文。

| 验证 | 结果 |
|---|---|
| 新 `test_audio.py` 夹具配父提交驱动 | 稳定失败于 bit 1 保留断言 |
| 驱动目录全部 20 个宿主测试 | 通过 |
| `checkpatch.pl --strict -g HEAD` | 0 errors / 0 warnings / 0 checks |
| t7-hdmirx.ko 按 uhd6 输出树编译 | 通过，vermagic `7.3.0-vim4kvm-uhd6+` |
| 独立 review（gpt-6-astra medium） | 未发现乘积 ≥5 的问题 |

上板前不快进正式分支；随下一次 7.3 候选窗口验证 RX 重锁与音频启停交错后再合入。

## 登记 issue（不修）

非零 EDID 读回失败后丢失退出清理责任：先撤回再发布非零 EDID，若 RAM 读回不匹配，
`ddc_start()` 内调用 `ddc_stop()` 清 `ddc_active`；`previous_size=0` 时不重发，解绑时最终
`ddc_stop()` 提前返回，不恢复探测前快照。原 EDID 非空但回滚也失败时同样可达。
频率 1 × 严重度 3 = 3，依据 f951 `t7-hdmirx.c:374–386,398–420,1950–1965`。
