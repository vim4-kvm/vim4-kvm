# 2026-11-05：7.3 集成内核与新 manager 正式部署

**已通过协调者批准范围，保留新内核与 manager 为正式默认。**
Mainline 运行 `7.3.1-vim4-20261105`，manager 为 dev.10.g85ef0b1；原 `.3` 整包留作回退。
同封存资产的八类结果与最后 manager 续窗合并验收；19 档 HDMI 矩阵未重跑、不记通过，音频仅状态检查。
当前身份及哈希以[正式锁](../../packaging/kernel/sources.toml)和[收据](../../packaging/kernel/releases/7.3.1-vim4-20261105/validation.json)为准。

## 最终身份与续窗

内核源码 `fd41fb5950b9da1fb336ce00d5137d27ee9755fa`，GNU build ID
`bdbfa439f298e92b5bad092528d11119a974f262`；归档 SHA256
`a12069066760768a833803ad11e7e1fc212674e4ff09f40bdf2017cc1d55e204`。
UTC 打包日按 release.py 查空闲序号，build 1 不带 `.1`；源码分支为 vim4-kvm-7.3。
manager 源码 `85ef0b1287c2dd428003b609e575ce33cbc4f99a`，版本
`2.5.1+vim4.20261029.102.dev.10.g85ef0b1`，deb SHA256
`5b7490a8cb6b1e362ae08eb113f818e28e4aa658506538cf5c3688f9f5ec9002`。

最终 FIFO 1245，票 `cd5dede2c94f4c9ba0c6e0952df210c1`，**167.967 秒**，已释放。
协调者批准最多两张票、每张 15 分钟（测试 8/恢复 7）；仅使用第一张，未取第二张。
先在原 `.3`/原 manager 上，经 SSH 18080→板端正式 80 完成只读 loginManager 登录、
取得正常会话并核原内核，之后才安装 manager、重核完整候选并原子切 Mainline、重启。
没有使用 localBackend 绕过认证，本窗没有 M6 通道、MCP、HID 或介质/HDMI 操作。

最终 boot ID `c81a3c7b-2247-4052-9904-f78120781b74`；UART 观察一次正常启动，
BL2 主机时刻 19:34:32.092 UTC，无就绪后复位。
完整七个启动文件、2341 模块/2354 模块目录文件、已加载模块身份及 BTF 通过，既有 taint 4096。
manager 安装文件与实际进程 SHA 一致；Mainline available/selected、Vendor available、默认及运行身份通过。
新鲜 H.265 3840×2160 五秒推进 **299 帧、59.7650 fps**，丢帧/冻结/丢包增量零。
最终 health、默认指针及 `.3` 的 **2361 个受保护文件**通过后，最后原子写 accepted runtime 元数据。
`window-11/result.json` 为 accepted=true / manager_passed=true / retained_default=true。

## 九类验收范围

前八类来自窗口 9 同一封存内核/manager；协调者明确认可续窗复用，最后只补 manager 和身份/风扇/新鲜视频。

| 类别 | 结果与边界 |
|---|---|
| HDMI 模式 | 1080p60→4K60、清 EDID 无信号及恢复通过；各次浏览器推进299/298/303帧；**19档矩阵未重跑，不记通过** |
| H.264 | 实际3840×2160，约10秒597帧、59.6927fps，丢帧/冻结/丢包增量零 |
| H.265 | 实际3840×2160，约10秒602帧、60.1854fps，同上计数增量零 |
| 4K60运动 | 同一正式包窗口5实测600.003秒、36000帧、59.9997fps，三个异常计数增量零；后续核原始凭证并新boot另做5秒，未重跑600秒 |
| 音频 | 服务active、HDMI采集和UAC2播放PCM存在；仅状态检查，无听音/内容验收 |
| HID | M6原生5对按键、2对点击、7移动、2滚轮事件，含WebSocket正反相对移动；USB profile恢复后重复得到同样计数 |
| 虚拟介质 | 专用16MiB FAT，M6 RO/RW读marker、写1MiB核SHA、安全弹出/LUN清空、板侧从实际镜像读回SHA通过；结束删除测试镜像 |
| GPU | Mali-G52/EGL1.5/GLES3.2，3.001485秒1952帧，像素179/128/128/255，gl_error=0；不作性能对照结论 |
| 管理页 | 最终窗口认证、面板fan保存/刷新读回/恢复、内核available/default与Vendor、实时TCPM5V3A、15点fan与移动布局均通过，无pageerror/横向溢出 |

介质写入 1048576 字节 SHA256：
`bd8a5183fdafb052402b7f52480145004a781b927f0d376e4fbd922da44f6926`。
USB 恢复沿用先例，经 API 切换 profile 再恢复，未手写 UDC；结论取 M6 原生事件/实际镜像，不以 API 成功代替。
窗口 9 先截图、明确选 U.S.、hold_key 逐字保持引导，下载六项工具逐项核 SHA；结束恢复 mode88/US，
关闭本任务两个终端并补拍 TestUFO 前台，没有操作其他 Chrome 标签页。

### 风扇持久化与面板保存

入场有保存的60/80/100°C锚点；新 manager 启动 ExecStartPre fan-restore exited/status=0，
journal 无恢复失败，六区共90个trip逐项符合保存锚点。
面板实际改为65/85/100°C并应用，刷新页面读回三输入值；API与六区90trip及小数温度逐项一致。
再经面板恢复60/80/100°C，恢复原保存文件的字节、模式和存在性，完整对比通过；之后再次运行
fan-persistence 核90trip和ExecStartPre。最终原锚点对应15点为
45/47.5/50/52.5/55/57.5/60/65/70/75/80/85/90/95/100°C。
面板保留启动固件历史快照；实时状态独立显示内核TCPM ready、5V/3A，未把固件历史fallback当当前合同。

## 构建、封包与来源验证

新 VM 目录 `/home/deepdream/build/deploy-73-20261105-fd41fb5950b9/` 使用独立源码副本和空 O=。
所有构建/隔离verify均走heavy队列；构建后只删本任务*.o，保留vmlinux、模块和封包产物。
生产.config字节一致，实际auto.conf全部4623项值一致，vmlinux无kasan_report。
首次27个字符串的引号表示差异误报保留；按Kconfig字符串值严格比较后通过，没有豁免选项。
外层24个文件、内层2354个模块目录文件完整集合/SHA、2341模块的vermagic/BTF/build ID通过。
manager初包dev9.g85在dpkg排序低于原dev9.g710；首错恢复后改为dev10重建，来源源码未改，版本排序通过。
其他应用及共享运行器保持原部署字节，不因本次切内核而重编或替换。

Mac tar 的 **5个AppleDouble v2侧文件**只在VM recipe及来源归档中；封存包外层32成员、
模块归档2791成员、2354模块文件及10运行时文件均无._或__MACOSX，七文件启动清单亦无。
原manifest保留这些侧文件的来源SHA，原件另存build-input-metadata.json；来源检查核格式头与原始SHA，
真实源码仍逐项匹配Git工作树。原包及原manifest未改，构建时hardware_validated/boardTested标志保持原值；
硬件验收由独立validation/installed-proof/manager/fan/regressions收据表述。

正式锁已更新tested_build/retained_runtime及下一包输入（20261105 build2），workspace仅推进manager85。
VM本任务source上本地轻量tag **v7.3.1-vim4-20261105**精确指向fd41fb5；未改git身份或配置，未push/发布。
收据包含完整模块库存、生产配置/封包核验、实板身份、manager面板/PD、fan前后、600秒及新鲜视频、
前八类引用、原始部署输入、旧.2授权清理及`.3`保留证明。
提交前`python3 -m unittest discover -s tests -p 'test_*.py'`：557项、跳过14项、无失败；
原始输出`logs/deploy-73/formal-accepted-tests-final.log`，Git差异空白检查通过。

## 已授权的旧启动目录清理

t48 **依据用户“部署所有东西”的授权批准**仅删未引用的
`/boot/kernels/7.3.1-vim4-20261104.2`。窗口4内再次核extlinux/kernels.json无引用，
目录七文件SHA逐项匹配收据后才删除；实际释放58040320字节，/boot可用46362624→104402944。
`.2`模块/固件、`.3`整包和Vendor保留；Mac原`.2`归档SHA
`f40370e057e40376f2687dceb7875568b34e85615fecef1459eddd301e6c73ba`，可整包重装。
`.3`回退归档SHA `dda222dfc7038485cbf657ad4a4dce2e82f16c0ad4f4befd5b1130eb950202f1`，
原manager dev9.g710包SHA `26c06134e146c488c54d8cde37c2da7633e77c6b99b29799f00661a95c62c87b`。

## 前期停止与保留证据

首阶段十票共2373.657秒（含恢复），遵守累计38分钟停新测试、45分钟含恢复的授权；
八类通过后因manager180秒上限无法满足剩余测试时间，回退并请批续窗。
随后额外20分钟票1244登录传输失败，用235.073秒首错恢复，详见[续窗历史](2026-11-05-integration-manager-continuation.md)。
协调者再批最多两张15分钟票，1245完成验收，用167.967秒；未重置或隐去各阶段历史预算。

保留的主要失败：入场实际manager710与历史workspace1400不符；截图比较子进程缺浏览器环境；
完整包安装前boot空间不足；重启后旧SSH转发失效导致恢复视频Failed to fetch，另票重建转发补核验；
窗口5诊断表达式忽略边界/大小写，误把ramoops/iwconfig warning判为splat而回退；
两个截图审核等待超时及一次终端启动截图不符均按失败停止。原failed result与日志不覆盖。
诊断脚本离线修为Linux诊断前缀边界，真实BUG/Oops/WARNING/Call trace/KASAN/panic/Wave5超时仍阻断，
两个回放测试通过；600秒凭证引用明确记重分类，没有把窗口5整体改为成功。
原`.3`恢复启动两次出现一次已知类复位，UART阶段/偏移保留；最终候选无此复位。

原始命令与输出在`build/deploy-73/`和`logs/deploy-73/window*`、`recovery-proof/`；
最终是window-11，`board-budget.json`保留逐票started/release mtime与耗时。
失败不归因为已证实内核回归；本次不扩展为19档矩阵、音频内容、端到端延迟或睡眠验收。
无子代理、无push、无合并。
