# 2026-11-06：AVC评审版与三格式集成窗口计划

仅离线准备，**待协调者批准，不排板票**。AVC评审版已审；合主线仍等待本窗口
H.264全集无回退，HEVC不随AVC合入。正式默认和系统GStreamer不改变。

## 系列与集成身份

AVC评审分支 `vdec-avc-residual-review` 保留两个独立提交：

| 原提交 | 评审版 | QEMU KUnit |
|---|---|---|
| dfd3af9 | dad4d7a8b59f45867d94593c8725bf2ca5ca23de | 26/26 |
| d444ab8 | 5dd4f646bcd8af7b9749bf1396c2a9a2ebf04e5f | 27/27 |

对应源码tree逐项相等，仅正文按75列换行（SoB不拆行），分别引用r63/r64实板边界。
每项strict format-patch checkpatch均0 errors/0 warnings/0 checks；宿主现存
Panfrost fixture 1/1；模块W=1及有效C=2 sparse、内建、头文件kernel-doc、
decoder binding和普通/vdec-test两份DTB检查完成。内建仍有树外vgetrandom既有
sparse缺声明告警；不称全树零告警。没有新增宿主mock测试。
原始日志及range-diff在 `build/hwdecode-parity/residual-review/01.*`、`02.*`。

独立 `vdec-integration-20261106` 从c99c3ed起，依次no-ff合AVC评审尖和
HEVC `5f7ed4f720237cfaf2a0de674e56a14e9257bebc`，无冲突，集成HEAD
`6346fd353fdc0405841ab0804b9239e604f9128f`。MPEG-2没有内核提交，只验证私有用户态库。
完整生产配置构建 `.31`，CONFIG_DYNAMIC_DEBUG=y；不混入私有内核草稿。
封包身份、双端哈希及protected_files逐项校验保存在
`build/hwdecode-parity/integration31/artifact-identity.json`、`offline-validation.log`。
完整封包已完成：build ID `89a8802c4a2c2a2e7a469a66ff422b64c324d157`，RAM包SHA256
`3201ca50da5724185c9105ccc18530a29524873e57c254c0231165648d9ab394`。
配置与正式逐字节一致，2372项protected_files由baseline生成并逐项核验通过。
集成尖W=1模块和27/27 QEMU KUnit通过。主仓库588项检查通过、11项跳过，
原始输出main-tests-final.log；首次漏加索引的两项失败已修复，日志保留。
VM未安装gst-inspect-1.0，宿主插件加载预检未完成（plugin-preflight.log）；
库哈希及软件参考已核验，板端实际加载路径/依赖采证仍为执行门禁，不冒充已运行。

## 顺序与预算

申请单张FIFO sampling票，上限30分钟，仅一次候选启动，不自动追加样本。

| 阶段 | 预算 |
|---|---:|
| 入场proof/视频、上传、启动 | 3分钟 |
| stateless compliance、H.264全集 | 7分钟 |
| MPEG-2两组及对照29次 | 8分钟 |
| HEVC启动清单 | 3分钟 |
| 正式恢复、归档清理、proof/视频 | 7分钟 |
| 余量 | 2分钟 |

历史H.264单条Fluster多数约1–3秒，r64带strace的10条解码合计35.868秒；
全集合批调用既有run_fluster，避免每条重复list/全包校验。预算含启动及日志开销，
不是性能保证。每条H.264限30秒，MPEG-2硬件与ISO参考分别限30秒；HEVC每动作
限30秒，compliance至多120秒。任何阶段耗尽预算则后续单列未运行，始终保留7分钟恢复。

1. 入场uptime至少300秒，连续UART覆盖proof/视频且boot_id不变；不额外等5分钟。
   当前正式baseline与2372项保护文件精确一致。空间门禁至少6GB；预估MPEG-2
   硬件输出605332224字节、参考同量，加输入/工具/完整候选/归档副本与日志留余量。
2. H.264使用官方parser私有前缀，原v4l2codecs不变。135条保留分母：130条运行，
   已确认FMO三条及SP两条按特性标Known unsupported，不重触发已知超时。
   MR3/4/5及两条Sharp保留完整输出、ioctl/队列trace；报告Success/Fail/Error/Timeout/
   Known unsupported/未运行，并与原58项及110项通过集合逐项比较。
   CVFC1仍按原套件像素判据，不将已知crop用户态限制改成套件Success。
3. MPEG-2遵循[29次清单](2026-11-06-mpeg2-visl.md)：六条矩阵问题旧/修正各一次，
   13条pending及四条通过对照用修正组。两组均固定Khadas parser和codecparsers；
   只更换私有v4l2codecs及codecs库，分进程、独立registry/LD_LIBRARY_PATH。
   保存gst-inspect实际路径、库解析及SHA，身份不符停止该比较。所有29次保留输出、
   请求控制及CAPTURE时间戳；strace包装使用65535字节和十六进制，避免控制数组截断。
   原Fluster ISO容差仍为主判据；FFmpeg逐帧/逐平面差异另列，不替换ISO或忽略缺帧。
   六条MPEG-1仅列格式不支持，不送MPEG-2接口。固定库SHA见工具manifest及原清单。
4. 最后按[HEVC启动清单](2026-11-05-hevc-start.md)启用hevc.c dynamic debug，保存IRQ起点，
   用既有256×256八位全I样本跑节点带流compliance，再捕获SOURCE_CHANGE及首帧。
   核before-reset/after-reset/after-start、命令读回、IRQ及停机；I420与同输入软件参考
   逐帧比较。全I正确才关闭debug复跑，再运行既有P/B样本并检查显示顺序及EOS/LAST。
   本轮不临时追加HEVC标准全集；首帧错误时不换流重试。

## 判停、恢复与证据边界

H.264/MPEG-2普通像素Fail继续收集；Timeout、BUG/WARN/Oops、设备不可用、DMA/停机
异常或恢复余量不足停止剩余执行并恢复。HEVC错误像素、加载/握手/SOURCE_CHANGE超时、
停机失败立即停止HEVC；不否定已完成的H.264/MPEG-2结果，不再开新HEVC流。
全局内核异常仍直接恢复。冷复位不重启候选，按r60经验最多观察两次自然恢复。

恢复正式baseline，核全部保护文件；清理前检查helper，不在则重传，解除候选挂载后
按owned manifest哈希删除任务固件副本，正式模块不动。逐文件归档Mac核哈希后删除
板端任务文件，最后验视频推进。不得saveenv、改默认启动项或系统插件。

软件参考与输入全部宿主准备并校验，板端不联网下载；29次MPEG-2清单、三组HEVC
输入/参考哈希和输出预算均在integration31目录。共享visl环境只读且保持不动。
S4、L1[0]占位限制、调试锁/内存、5.15对照与性能仍单列未验，不据本窗宣称完整parity。
