# 2026-11-08：HEVC 剩余修复正式部署尝试与门禁阻塞

`34fbda5a776e` 已构建为 `7.3.1-vim4-20261108.2` 并自然启动，身份和解码冒烟通过，
但 `formal-gates.py` 回传 root 私有 GStreamer registry 缓存失败，执行器按失败路径恢复旧正式包。
修工具后的第二张获批票在安装前因根分区空间门禁停止，没有再安装或重启。
**本次没有保留新默认**；当前默认仍见 [sources.toml](../../packaging/kernel/sources.toml)
和[上次正式部署](2026-11-08-vdec-dos-regmap-deploy.md)。

## 改动

内核从 `3eab9050` 前进六个提交，仅改 `drivers/media/platform/amlogic/vdec/`。
修复和 `.44` 的全集验收见[剩余五条记录](2026-11-08-hevc-remaining5.md)，不算本次重测。
本次用 `build.sh` 在新的 VM 空输出目录构建 Image、DT 和完整模块，再用 kbase 构建三个外部模块，
通过 `package-unified.py` 封包；所有重型步骤持 heavy 租约。

- build ID：`f01ed7abb0dd9d3d4f15f238c2e089684d03192c`。
- 包 SHA256：`1947d1dbb48def575005f7fbc5efaebcf3db16bef234d2af22909763d5d672e3`。
- config 与旧正式相同；2341 个模块、2354 个模块树文件，集合零增删，运行时文件零变化。
- 沿用上次正式构建的同次 `vdec-test.dtb` → kbase 路径；最终 `vim4.dtb` 与旧正式哈希相同，
  `video-codec@320000` 为 `okay`，没有在部署时替换 DT。
- 普通构建有 17 条未改动 ADLA 代码警告，vdec 无警告。本次未重跑 W=1、sparse、KUnit。

## 上板

离线 plan 通过，无 baseline overlay，选择 decode-smoke、PD B 和执行器自带的被动视频。
一张 40 分钟 FIFO 票，失败恢复后释放；没有另开窗口。

- 入场完整基线通过。启动文件需要 57976087 B，`/boot` 只有 46448640 B；
  确认 extlinux/kernels.json 无引用后退役 `20261107.2` 启动目录七文件，哈希存入数据。
  退役后可用 104443904 B；保留其模块、包及历史证据。
- 安装只切 Mainline LINUX/FDT，APPEND（含 fusb302 黑名单）、默认标签及其他启动项未变，未 saveenv。
  新 release、build ID、完整模块、config、启动文件哈希及已加载模块 build ID 均通过，fusb302 未加载。
- 候选 boot_id 为 `c90782cb-07e8-4bd0-9e9e-3ece43b93b48`；被动视频 299 帧、59.78 fps。
- DOS debugfs 空闲全 X、K9 busy open、独占 open/close 状态通过。HEVC WPP_A、DBLK_A、TILES_B
  分别 48/30/100 帧，逐帧及发布者整流 MD5 相同，status 0；JPEG 三条各 16 帧，长度及 SHA 符合参考。
  `decode_passed=true`，`kernel_faults=[]`，编码器及 one-kvm 已恢复。

失败发生在上述解码完成后的证据回传：[formal-gates.py](../../packaging/kernel/formal-gates.py)
以普通用户 `scp -r` 下载 root 执行产生的结果目录，六个私有 `*.registry` 无读取权限。
`finally` 中的 `check=True` 将 scp exit 1 作为门禁失败抛出，执行器开始恢复。
上次手工部署也遇到缓存回传失败，本次封装将其升级为部署阻塞；需先修工具，再另行安排部署。

执行器确认恢复 `7.3.1-vim4-20261108`，完整基线 proof 一致，视频 299 帧、59.75 fps。
恢复 boot_id 为 `20e783cd-c0d9-44ec-8637-4c5897320645`。
UART 候选及恢复各一个 U-Boot/Linux 启动，未见额外冷复位；两次 reboot_mode 均为 watchdog_reboot。
候选启动日志及解码增量日志无 WARNING/BUG/Oops/SError。

逐流状态、MD5、空间、恢复结果及原始日志 SHA 见[数据](data/2026-11-08-hevc-remaining5-deploy.json)。
原始输出保存在主检出 `logs/deploy-hevc5/`，构建包保存在 Mac/VM 的任务私有目录。

## 第二次窗口：空间门禁停止

协调者提交 `aac047e`，将 `GST_REGISTRY` 从 `results/` 移到 smoke 根目录，
并批准第二张 40 分钟票。不重建包；在该提交上重跑 plan，通过，无 retire、无 overlay，
仍选 decode-smoke、PD。协调者另明确批准先归档并清理第一次留下的本任务上传暂存。

第二窗入场完整基线通过。`.2` 候选的七个启动文件和 2354 个模块树文件均与包逐文件相同，
extlinux/kernels.json 无引用。安装器明确拒绝已有启动目录；准备按批准只删除该候选启动目录、复用模块。

先以 sudo 将旧 `/var/tmp/vim4-formal-deploy/` 打成 tar、chown 给登录用户并回传，
板端和本机 SHA256 均为 `2ceada6b990473cebe95a86f12380d4bdf19b61fe711f0ff93eae265a858c41e`。
归档 1361428480 B，保存在主检出 `logs/deploy-hevc5/attempt1-staging.tar`，
清单为同目录 `attempt1-staging.list.txt`；归档内容还与板端逐文件清单一致。
根分区紧张，板端临时 tar 使用 `/dev/shm`，回传核验后清理本任务上传目录及临时 tar。

清理后根分区可用 **1927274496 B**，小于 plan 的 **2133988236 B**，缺 206713740 B。
预检立即停止，未删除候选启动目录或模块，未调用 execute，未安装或重启，未再动其他启动目录。
默认仍为入场核对通过的旧正式包；第二张票已释放。遵照失败后不再重试的约束，未申请第三张票。

## 未验证

PD B、候选冒烟后视频及全窗末尾增量日志采集未执行，原因是前序门禁回传失败。
九类、全集解码、运动、HID、EDID、音频、介质及 GPU 不在本次门禁范围。
未 publish、未打 release tag、未推进正式来源锁或默认部署链接；新包安装目录及失败证据保留。
第二窗没有运行硬件门禁；缓存路径修复尚未通过真实 execute 验收，空间不足仍阻塞正式部署。
一次候选和一次恢复没有额外冷复位，不证明冷复位问题已修复。
