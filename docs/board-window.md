# 单板 FIFO 与短窗口

编译先完成，持板不超过30分钟；同批候选链式 RAM 启动，最后回5.15。工具本轮只做
离线验证，尚未用新入口上板。所有会话必须在同一协调主机共享 `/tmp/vim4-board-queue`；
不同主机的 `/tmp` 不互通。Python入口无第三方依赖；浏览器接收/像素比较复用项目已有
Node、Playwright与Chrome，配置见 [工具目录](tools.md)。

## 排队、采样与迁移

```sh
tools/board-queue status
tools/board-queue run --heavy --who HDR --purpose build --max-min 30 -- make -j8
tools/board-queue run --who HDR --purpose r18 --max-min 30 -- sh window.sh
```

`run`把 `BOARD_TICKET`、`BOARD_QUEUE_ROOT`传给命令，结束（包括失败、SIGINT/SIGTERM）
释放。直接管理窗口：`export BOARD_TICKET=$(tools/board-queue acquire --who HDR --purpose r18)`，
然后 `tools/board-queue release`；独立keeper在命令返回后保管内核锁。
`sampling on/off`仅允许当前板票据，on等现有heavy退出后返回；申请期间已阻塞新的heavy，
heavy之间共享。板窗口平时持旧heavy共享锁，采样时升级独占锁。
不要在heavy命令中再取板锁，或在板窗口中等heavy；先释放再排另一类票据。

票据序号在flock下递增，keeper持有旧 `/tmp/vim4-board.lock` 和
`/tmp/vim4-heavy.lock`（macOS BSD flock，Linux另外兼容POSIX lockf）。票据原子替换，
历史在 `history.jsonl`，每个票据有keeper日志。释放再申请只能排到尾部；过期票据永不续期。
超时写 `.notice`、keeper日志、原终端（存在时）；run也向stderr打印。status显示告警。
超时释放租约和旧锁，后继可接管并记录；**不会终止原命令或远程操作**，原会话应立即收尾，
不能继续启动新操作。不要据此推断硬件已经空闲。SIGKILL无finally，keeper会检测run父进程消失；
keeper自身死亡由后继/status剔除。主机睡眠期间不提供准时唤醒保证。

正在运行的旧会话先完成原窗口、原样退出旧lockf，不嵌套新队列、不删活跃锁文件。
已在旧lockf等待的会话应在下一轮改用新入口；旧waiter不具备新票据FIFO资格。
仍需短期用旧入口时使用 `lockf -k` 保留锁文件。旧lockf默认退出删除文件，不能保证
其未修改的旧waiter之间FIFO；迁移完成后仅使用新队列，禁止手工unlink两个锁文件。
本轮不会打断旧持有者或旧waiter，也未给其他会话发送消息。

## 候选链与恢复

新候选可在manifest同时指定`namespace`和`payload_id`，各为1–64位小写字母、数字、
下划线或连字符，首位为字母或数字。目录为
`/var/lib/vim4-kvm/ram-candidates/<namespace>/<payload_id>/<真实kernel build_id>/`。
payload_id是独立构建身份，修改DT或模块必须换ID；相同ID已存在也拒绝覆盖。
Image/build_id不必变化。`display-once.py prepare`可传`--namespace kbase --payload-id trial1`。
编译静态init时用`-DTRIAL_ROOT='"/var/lib/vim4-kvm/ram-candidates/kbase/trial1/"'`，
prepare/stage验证ELF中的根目录合同，sysboot/extlinux采用同一路径。
最后一级仍为真实GNU build ID，PID1继续核对运行内核notes；不能把payload_id当作内核ID。
省略两字段时，原display-m1/HDR2 build-ID目录、原静态init与cleanup合同保持不变。

使用 `display-once.py prepare` 生成的目录（包含candidate.tar）或candidate.tar归档。
也接受r18的HDR2 `manifest.json` RAM payload目录或归档（Image/DTB/init/modules/runtime/extlinux），
首轮需 `--baseline-files` 显式列出5.15恢复文件；普通boot/lib内核安装包不能直接传入。
目录内有candidate.tar时SHA指归档；松散payload目录的SHA指manifest.json，逐文件再验证。
原有prepare的release/静态ARM64 PID1/完整模块清单门禁继续有效。
归档外部SHA必须来自构建记录，不能以传输后重算的哈希代替来源证明。

```sh
# 在同一个run窗口的window.sh里；串口设备按现场指定
tools/board-window --window hdr-batch --device /dev/cu.usbserial-1100 boot-candidate build/candidate-a --sha256 "$SHA_A"
tools/board-window --window hdr-batch receiver --local-ip 192.168.50.239 --seconds 10
tools/board-window --window hdr-batch --device /dev/cu.usbserial-1100 boot-candidate build/candidate-b --sha256 "$SHA_B"
tools/board-window --window hdr-batch --device /dev/cu.usbserial-1100 return-baseline
```

首候选前必须运行5.15；记录release、GNU build ID、cmdline与trial.json全部baseline_files。
HDR2的 `--baseline-files` 是持久恢复证明，只列原5.15启动文件和运行时登记配置；
不要把候选PID1临时bind覆盖的runtime程序路径放进该证明，否则候选期间读到的是私有版本，
链式校验会拒绝。后文baseline测量的 `--files` 则须包括程序/插件，用于性能缓存失效。
归档逐文件核哈希，stage复用display-once.py的安全解包/静态ELF/fsync/原子发布。
新增显式 `stage --retained-baseline proof.json` 在链式窗口核对原5.15证明与归档一致，
两次验证磁盘文件不变；不要求当前候选的release/cmdline等于原基线。原stage默认门禁不变。
HDR2新release只创建空的 `/lib/modules/<release>` bind挂载点，完整模块仍留在私有payload，
不向基线模块目录安装文件。接受任意安全的 `7.3.0-vim4kvm-<tag>+` 候选名；
release名称不代表能力或验证结果，仍校验manifest全部文件、归档SHA、静态PID1和模块清单。
stage只记录自己新建空模块目录的设备/inode；return-baseline验证回到原5.15后清理。
已有目录、被替换的目录、非空或仍挂载的目录保留，清理异常报告失败，不递归删除。
串口在autoboot提示后打断，仅发送原有sysboot RAM命令，不写saveenv或默认配置。
立即读UART而不阻塞等SSH退出；从基线读取MAC并仅在RAM setenv ethaddr，保持DHCP身份。
等待新的boot ID、预期release/build ID、SSH、逐服务active、UDC configured与API响应。
snapshot只读缓存，无查看器时503不代表采集故障；receiver创建offer后另验真实解码推进。
任一步失败停止，不自动重试或选择另一个候选；查看UART证据再决定恢复。
SSH使用开发环境免密 `sudo -n`，脚本通过 `python3 -c`，没有密码/heredoc混用。

`return-baseline`重启而不打断autoboot，再验证原5.15身份/所有证明文件、服务、UDC与视频。
无原始proof时拒绝恢复。默认启动必须事先确认为5.15；本工具不修改默认项来修正错误配置。
批次脚本应在EXIT trap中安排恢复，并为恢复预留时间；不能靠finally保证硬锁恢复。

## 基线与证据

`baseline --files /boot/... /opt/...` 必须列出当前5.15 Image、One-KVM程序、插件、
所有默认启动/DTB/initrd与运行时登记文件（按当前部署清单选，不能只给uname）。
例如受保护配置含 `/boot/extlinux/extlinux.conf`、`/etc/vim4-kvm/kernels.json`、
`/etc/vim4-kvm/runtime-build.json`；内核/应用具体路径从当前登记清单读取。
缓存键还含host、运行内核GNU build ID、cmdline、接收URL/时长/接收LAN IP；
当天相同键返回 `reused: true` 和 `source_time`，变化/跨日才测；失败不缓存。
测量后再次核身份，避免将变化中结果写缓存。缓存位于共享队列目录，不随worktree分裂。
更换信源、编码设置、浏览器或接收机器时应清理对应缓存，或使用独立 `BOARD_QUEUE_ROOT`，
后者所有排队会话必须同时迁移，不能创建互不相通的板锁队列。

`collect --readonly`只执行已审阅状态读取：dmesg、服务、UDC、/proc计数与One-KVM info，
不访问regmap/MMIO/HID/采集节点，不停启服务。其余子命令要求未过期板票据。
证据写主工具所在仓库 `logs/<window>/`，含原始dmesg、WARN/BUG/oops/CMA筛选、JSON、
UART和 `evidence-*.tar.gz`。失败保留已有证据，不删除现场。

## MCP 与接收

MCP只在显式调用时创建客户端：先通过SSH转发One-KVM 8081到本机18081，
从板上凭据安全读取 `ONEKVM_MCP_KEY` 环境变量（不写命令参数/日志）。
`mcp screenshot`保存JPEG；`mcp idle --menu-pixels 60`相隔2秒比较截图并忽略顶部菜单栏，
每通道变化>20的像素比例<0.1%认为视觉静止，这不是“无人操作”的证明。
每次工具动作先initialize并发送initialized通知（当前无状态服务不暴露重启代次），
因此One-KVM在HDR步骤之间重启也会重新初始化；HTTP会话失效/断线后重建，截图等只读调用重试一次，HID结果
不明时不自动重放。现有One-KVM是无状态JSON MCP，另支持返回session header的版本。

`mcp hdr --profile reviewed.json --exec <测量命令>`封装apply→截图→命令→finally恢复→截图。
profile使用明确的原状态恢复序列，格式如下；坐标/显示排列必须来自现场已验证记录，
本工具不提供未经核实的固定坐标，不能只用一次toggle假定恢复成功。

```json
{"verified_source":"已验证操作记录路径及截图尺寸", "apply":[
  {"name":"left_click","arguments":{"coordinate":[100,100]}}, {"wait":1}
], "restore":[{"name":"key","arguments":{"text":"Escape"}}]}
```

上述仅为自定义profile结构示例；restore必须填写实际恢复HDR原状态的完整操作。
HDR命令涉及HID，只有得到对应窗口的HID授权才调用。本轮仅mock，不发送任何HID。
内置 `mcp hdr --m6-hdr on --exec <测量命令>` 复用r17/r18已经执行的M6序列：
Apple菜单(27,13)→Settings(108,83)→Displays(1092,647)→向下滚动7格→HDR(1704,540)。
强制截图1920×1080、English Settings与RTK UHD HDR布局，先检查视觉空闲；从
One-KVM `/api/vim4/video` 的源端EOTF记录原状态，每次切换等待实际PQ/SDR，再关闭设置窗口。
finally按源端原状态恢复并截图；不依赖toggle次数推断。初始未知EOTF、尺寸不符、画面活动均停止；
切换中暂时UNKNOWN有界等待15秒，恢复前同样等待可判定状态，不把UNKNOWN当SDR。
来源为gpu-hdr工作树只读的 `build/hdr2-r17-control.py`、`hdr2-r18-*-control.py` 与
`logs/hdr2-r17/window-1793433768.jpg`、`window-1793435376.jpg`；需保持现场窗口布局，
本轮未重新进行硬件验收。截图不能证明显示器实际光度。

receiver复用r17 `packaging/hdr2-pq/video-recovery.mjs` 的独立视频页面与offer/close流程，
另复用manager-login/getStats；不加载产品页面输入脚本，不请求声音或数据通道。
发offer前由SSH确认服务与管线出帧，
实际framesDecoded>0才开始计时，每50ms采样，保留原始时间戳与SSRC/codec；流更换、倒退、
未推进或未解码均失败。按r17结论在自有测试Chrome进程关闭WebRtcHideLocalIpsWithMdns，
优先发送literal host candidates；仍遇mDNS时才用显式 `--local-ip` 的接收机LAN地址替换，
不能误用板IP；不修改生产ICE配置。50ms是目标采样间隔，JSON保留实际耗时，不宣称硬实时。
接收与baseline自动开启/关闭sampling；不测声音，不发键鼠。
