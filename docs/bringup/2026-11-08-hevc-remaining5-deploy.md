# 2026-11-08：HEVC 剩余修复正式构建并设为默认

`34fbda5a776e` 正式构建为 `7.3.1-vim4-20261108.2`，第四张获批票验收通过后保留为 Mainline 默认。
前三次分别因证据回传权限、空间门禁及 PD API 目标错误停止或恢复，均未绕过门禁。
正式身份见 [sources.toml](../../packaging/kernel/sources.toml)、
[installed proof](../../packaging/kernel/releases/7.3.1-vim4-20261108.2/installed-proof.json)
及[新 2372 项基线](../../packaging/kernel/releases/7.3.1-vim4-20261108.2/baseline.json)。

## 改动

内核从 `3eab9050` 前进六个提交，仅改 `drivers/media/platform/amlogic/vdec/`：
处理可见格式未变时的内部重配、slice 长期参考完整 POC 匹配，并快速拒绝固件不能处理的 SPS LT、窄图 WPP。
修复根因和 `.44` 的 HEVC 129/132、JPEG 3/3、compliance 56/56 见[剩余五条记录](2026-11-08-hevc-remaining5.md)，不算本次重测。

使用 `build.sh` 在新的 VM 空输出目录构建 Image、DT、完整模块，再重建三个 kbase 外部模块，
以 `package-unified.py` 封包；重型步骤均持 heavy 租约。四次尝试使用同一包，没有重建。

- build ID：`f01ed7abb0dd9d3d4f15f238c2e089684d03192c`。
- 包 SHA256：`1947d1dbb48def575005f7fbc5efaebcf3db16bef234d2af22909763d5d672e3`。
- config 与旧正式相同；2341 个模块、2354 个模块树文件，集合零增删，运行时文件零变化。
- 沿用上次正式的同次 `vdec-test.dtb` → kbase 路径；最终 `vim4.dtb` 哈希与旧正式相同，解码节点为 `okay`。
- 普通构建 17 条警告均来自未改动 ADLA，vdec 无警告；本次未重跑 W=1、sparse 或 KUnit。

## 上板

四次各一张获批 40 分钟 FIFO 票；每张结束都释放，没有在失败后自行重试。
旧正式为 `7.3.1-vim4-20261108`（此前任务称 `.43`），完整回退包及历史证据保留。

### 前三次及根因

| 尝试 | 结果与处理 |
|---|---|
| 一 | 候选身份、59.78 fps 视频和六条解码通过；普通用户 scp 无权读 root 0600 的 GStreamer registry，门禁失败后恢复旧正式，完整 proof 和 59.75 fps 视频通过 |
| 二 | `aac047e` 将 registry 移出 results；plan-2 通过，但清理旧上传暂存后 root 仍只有 1927274496 B，低于预算 2133988236 B，候选目录删除前停止，零安装、零重启 |
| 三 | 按批准删除匹配且无引用的 `.2` 启动目录及模块；空间通过。安装身份、59.55 fps 视频、六条解码及回传通过，但 PD 状态请求向后端端口返回 404，恢复旧正式，proof 和 59.38 fps 视频通过 |

第一次 `/boot` 不足，确认 extlinux/kernels.json 无引用后退役 `20261107.2` 启动目录七文件，
保留其模块、包和证据。第二、四次分别将前次本任务暂存完整归档为
`attempt1-staging.tar`、`attempt3-staging.tar`，sudo tar 后 chown、回传核两端 SHA256，
另核逐文件清单，随后按明确授权清理暂存；归档、清单及哈希均保留在主检出日志和数据中。

第三次 PD 失败源于 `api.mjs` 固定访问 `18088`（板上 8081 后端），未使用管理器地址。
协调者 `821e277` 增加 `manager-status.mjs`，经 `MANAGER_URL=18080` → 板上 80 密码登录读取管理器状态。
第四窗前逐行审查尚未运行的成功路径及 publish，又确认 runtime 收据用 print 输出会多一个换行。
`99fa849` 改为原样输出，并在 publish 校验收据字节与新基线 SHA；提交前全套 607 项通过。
第三次真实失败日志在离线 publish replay 中正确拒绝；私有派生夹具只验证解析路径，不作硬件证明。
保守空间预算及空日志目录合同保持不变。

前三次 boot_id、逐流结果、恢复 proof、UART 和原始日志哈希均在[数据](data/2026-11-08-hevc-remaining5-deploy.json)。

### 第四次成功

最新提交上 plan-3 通过，门禁仅 decode-smoke、PD 及执行器的被动视频，无 retire、无 baseline overlay。
入场完整基线通过；候选启动七文件及模块树 2354 文件与包逐项一致，
extlinux、kernels.json 及现场 registered.json 快照均无引用，按批准删除这两个候选目录。

| 分区 | 删除前 B | 删除后 B | plan 要求 B |
|---|---:|---:|---:|
| root | 1935241216 | 2578116608 | 2133988236 |
| /boot | 46448640 | 104443904 | 57976087 |

先在旧正式默认上单独预演 PD，管理器登录、状态读取和固件 B 断言通过；预演日志另存后才 execute。
安装只切 Mainline LINUX/FDT，APPEND 逐字不变（含 `module_blacklist=fusb302`），
默认标签及其他启动项不变，未 saveenv。一次自然启动后：

- release、build ID、全部模块、config、启动文件哈希及已加载模块身份通过，fusb302 未加载。
- 视频前后各 298 帧，分别 59.5566、59.5526 fps。
- DOS debugfs 空闲全 X、编码器在位 busy open（K9）、独占 open/close 和解码后断电状态通过。
- HEVC WPP_A、DBLK_A、TILES_B 分别 48/30/100 帧，逐帧及发布者整流 MD5 相同，status 0。
  JPEG 三条各 16 帧，长度及 SHA 与参考相同；应用和两个编码器正常恢复。
- 安装后 PD B 通过：fusb302 未加载、无 Type-C port，服务成功跳过，管理器只报告固件 handoff，未进行 Linux 协商。
- runtime 收据更新成功，输出字节与板上哈希一致；新 2372 项基线采集、上传目录清理和成功退出均通过。

boot_id 为 `6f3856d0-ee91-4854-8380-a0343219950c`；UART 一个 U-Boot/Linux 启动，
reboot_mode 为 watchdog_reboot，未见额外冷复位，无回退。
连续 UART、候选启动 journal 和解码增量均无 WARNING/BUG/Oops/SError。
补充的跨重启 journal 游标失效、输出零行，不将其空结果记为通过，保留此取证边界。

离线 `formal-deploy.py publish` 完成，发行目录补齐与旧正式相同的 13 项收据；
来源锁推进到新正式，下一包递增至 build 3。VM 在目标 SHA 建本地 tag `v7.3.1-vim4-20261108.2`，未 push。
第四窗原始输出位于 `logs/deploy-hevc5/{preflight-4,pd-rehearsal-4,window-4}/`，所有尝试和构建原始输出均保留。

## 未验证

没有运行九类、全集解码、600 秒运动、HID 注入、EDID、音频、介质或 GPU；
`.44` 全集是历史证据，三条 HEVC 仍受限制。本次只验单子系统门禁。
补充跨重启 journal 游标无效；一次成功自然启动不能说明冷复位问题已修复。
