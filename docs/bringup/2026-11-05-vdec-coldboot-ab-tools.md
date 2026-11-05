# 2026-11-05：冷复位 A/B 工具与封包离线复审

**仅离线准备，没有排板、启动或部署。** [计划](2026-11-05-vdec-coldboot-ab-plan.md)
的二十次启动已获批准，但协调者要求本次工具复审后才排票。
两组已有内核产物未重编，未混入 HEVC 私有模块。

## 本轮修正

- UART 只匹配内核 WARN 格式、cut-here、行首/内核时间戳后的 BUG、Oops/panic；
  普通用户态 WARNING 和行内 BUG 不触发停止。保留 lockdep 的明确循环锁告警。
- 冷复位后的缓存按各原始收包 monotonic 时间戳回放；恢复 Linux 标识不因处理时间
  被推迟。同块余下字节和后续块都保留。
- reader 线程未退出时保留 fd，并报错；不在 finally 把仍由线程持有的 fd 关闭。
  最终恢复会先存原错误，随后永久禁止新实验，只允许正式 release。
- mountinfo 的 fsroot 比较保持安全失败；入场只读保存 mountinfo，并断言
  `/var/lib` 与 `/` 的 st_dev 一致。此项**尚未实板确认**，不满足即不启动实验。

## 新工具与边界

[批次编排器](../../packaging/kernel/coldboot-ab.py) 默认只校验锁定输入；execute
要求既有新鲜板票，不排票、不构建、不部署。固定交替顺序，无补样、无第三组。
全程 sampling，单实验时限包括自动恢复；末尾为正式恢复保留预算。
冷复位消耗当前实验序号，自动恢复另列记录；未进入所选 Linux、恢复失败或内核
告警直接收尾。恢复先清理本任务创建的固件副本，再正常启动、核验正式 proof、
验真实视频，随后清理已本地归档的私有 payload。失败保留结果和未完成列表。

两组都核验私有 init 与只读模块 bind，避免把 A 的正式自动回退误计作 RAM 对照。
固件仅复制配置中已锁定内容，已有文件只核 hash，不覆盖；只删除本任务创建且
hash 仍相等的副本。SSH 超时已收到的所有权记录仍保存供收尾。

[早期采集器](../../packaging/kernel/coldboot-collect.py) 由显式编译开关启用的静态
init 异步启动，不等待其完成，不主动加载模块或读取 debugfs/MMIO。
采集 cmdline、boot ID、uptime、release、模块参数及 modprobe/modules-load 配置；
每项保留 hash/错误，子进程超时留下部分输出。完整数据在私有 tmpfs，UART 只报
紧凑的 boot ID、解码模块存在与参数摘要。宿主取已完成/超时快照，并收 dmesg、
journal、失败服务列表；传输 SHA 核验后删除临时 tar。

初始快照不保证先于 systemd；早期冷复位可能丢失 RAM 数据。迟到采集标 skipped，
采证失败标未覆盖，不能借恢复启动补原启动的数据。观察到 60 秒后留短暂时间取
最终快照；这期间复位单列 post-observation，不并入 60 秒冷复位计数。

## 封包核验

完整输入、输出与 init SHA 见[机器记录](data/2026-11-05-vdec-coldboot-ab-package.json)。
本地目录 `build/hwdecode-parity/coldboot-ab/`，执行配置 `config.json`。

| 组 | RAM archive SHA-256 |
|---|---|
| A，正式 fd41fb5 | `c157ead74743b5d91918a07cfd65d7f8b1d719a23777e024f74c94c7add531c1` |
| B，既有 .28 / 9601323 | `440928af06544eeff52ecb314e566425ff22501fc4f4f2e35be3caeb29e81e7d` |

逐组核对输入归档、Image/DT hash、全部 2354 个模块/元数据文件。
B 从 r58 RAM 包重建 GNU 格式 modules tar；压缩归档 hash 改变，逐文件 hash 与原
manifest 完全一致。两组模块文件名集合相等，其中 2341 项内容 hash 不同，不能
把不同 release 的模块当作相同二进制。没有换用 c99c3ed 重建产物。

规范化私有 payload 路径后 extlinux 文本一致；采集器 SHA 相同。静态 init 使用
同一源码、编译器和开关，仅 release/TRIAL_ROOT/输出路径不同。
未启用采集开关时，与 4006ae8 的同名源码在相同参数下编译，静态 ELF **逐字节相同**。

两份 DT 用既有内核 dtc 反编译排序，差异仅 `video-codec@320000`：B 增加 HEVC
时钟/IRQ/电源域，status 由 disabled 改为 okay。未改 DT 或 binding；本轮不运行
dt_binding_check。差异原文 `dt.diff`，decompile 警告保存为 `A-dtc.log/B-dtc.log`。

## 已运行与未运行

- `package-3.log`：两组 static ARM64 init 编译（Wall/Wextra/Werror）及完整模块校验。
- `preflight-3.log`：正式批次离线入口通过；`verify-2.log`：封装规范化、默认 init
  逐字节一致、模块集合和 DT 差异核验通过。
- 首轮全套主仓库测试 `tests-1.log`：583 项，跳过 11 项；后续最终全套结果随提交报告。
  新增工具测试覆盖默认不排票、用户态 WARNING、原时间戳回放、reader 卡住、
  采集超时保留部分输出、失败后只恢复一次、不继续后续样本、冷复位不重试、
  自动恢复失败、单次截止时间不被采证异常处理吞掉。
- 首次 B 打包暴露 PAX 长路径覆盖 member.name，`package.log` 和
  `preflight-2.log` 保留失败；重包为 GNU 格式后清单全量校验通过，未改通用默认打包路径。
- 第一次默认 ELF 对比使用不同源文件 basename，符号表因此不同；改成同名源文件
  后逐字节相同，前次失败仍存 `verify.log`。
- UART 硬件连续读、异步采集对实际启动时序的扰动、二十次 A/B、正式恢复与视频，
  本次全部未运行。旧窗口不能替代这些验证。待 t48 复审后方可排板票。
