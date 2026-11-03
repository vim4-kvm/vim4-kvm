# 2026-11-03：7.3.1 整包试装、boot 清理与 uhd7 恢复

7.3.1 已完成整包安装并一次正常启动，编码、四应用接收和 kbase 像素检查通过；
M6 经 One-KVM MCP 输入长命令时文本不一致，HID 门禁未通过，按本轮失败处理要求停止其余验收，
一次正常重启回 uhd7。**未推广正式源码/部署来源锁，最终仍默认 FullKvm/uhd7。**
没有证据将输入问题归因于 7.3.1；没有重试候选、修改驱动或在恢复后重复该输入试验。

## 输入与预检

部署工具来自已合入主线的 `3c199fd2d2133229008e94c76b483e7c7073d405` 工作树。
候选源码 `25110086de2ef6aa9564a31a7c694eca893fd423`，release 为
`7.3.1-vim4kvm-uhd7+`，完整包 `deploy-tools-731-final.tar.gz`，69,566,113 字节，
SHA256 `59a8343225da61a1cf81ec70a60603d451cb2d2611ce493f25f260bd83e869cc`。
上传的安装器 SHA256 为 `f5f986f027106a6bd099989f6548ea9aad6cf406467ab5d6eead1ef9818a3ffb`。

预检核对实际 uhd7 Image/DT、2341 模块及三个 `4111568841bd` overlay，
完整 proof 含2368个保护文件；六个 kbase/采集模块加载 ID 与正式锁一致。
串口 `/dev/cu.usbserial-1100`、921600 已登录并读取 uname/boot ID；初次在登录提示符直接发送
shell 命令没有完成，确认登录提示符后正常登录，才执行后续命令。
`fuser /dev/watchdog0` 确认 PID1/systemd 持有，RuntimeWatchdog=30s、RebootWatchdog=60s。
两次重启均开启串口日志；没有向开发 M4 发送 HID。

## 经授权的 /boot 清理

初始 `df -B1`：boot 总容量219004928、已用189083648、可用19861504字节；
根分区可用14434893824字节。新候选七个 boot 文件合计58015723字节，连同目录/原子写入
余量需58060779字节，无法直接并存，因此在取得删除授权前没有安装或重启。

用户随后授权淘汰 Stock、VendorVapb1。清理前逐项核对 extlinux 全部 LABEL、kernels.json、
vim4boot/面板、uEnv.txt、顶层 Image/initrd.img/dtb/dtb.img 链接；实际登记只有
Default/hdrdual6 和 FullKvm/uhd7，未登记 Stock/VendorVapb1，无需删登记记录。
Default/hdrdual6、FullKvm、/edge、顶层活动链接及共享 overlays 均保留。

先原子删除两个 LABEL，保留夹在原 Stock 段后的全局 default/timeout；再删除两版本独占的
vmlinuz、initrd、config、dtb 目录及 System.map 链接，以及无 LABEL 引用的 hdrdual5 dtb 目录
和 System.map 链接。只删除链接本身，未遍历其指向的根分区文件。

| 删除的主要文件 | 字节 | SHA256 |
|---|---:|---|
| vmlinuz-5.15.137 | 15257557 | `4b81c4c909a65410236fb1330375c411d4d0676ab4273edc0479b8f4e2328fe5` |
| initrd.img-5.15.137 | 27907590 | `a40f23581631334e3096cdd446065bb1d49a37dd60e46217b6623599c83ecd5e` |
| vmlinuz-5.15.137-vim4kvm-vapb1 | 15332424 | `db1a3640041978d7ad32630fac731bec1ee1e3697667be9162aa2d52ecc9c949` |
| initrd.img-5.15.137-vim4kvm-vapb1 | 24203084 | `956a7f93d799391e2b40452cd7cae000ac81205b5cf7fae87908151c5add120b` |

完整删除清单在日志中记录逐文件 SHA 和链接目标：15个普通文件共84478997字节。
sync 后实际释放84545536字节，boot 可用104407040字节；前后所有登记产物逐文件验证通过，
面板两项均 available，默认仍为 FullKvm。没有创建备份。

## 安装与启动身份

使用本工作树安装器 `install`，完成包清单、模块、空间校验后，将七个启动文件写入
`/boot/kernels/7.3.1-vim4kvm-uhd7+`，兼容运行时入口原子替换，最后原子切换 FullKvm。
旧 `/boot/edge`、旧模块及三个 overlay 未改动；BCM43752 .217 固件按新 release 准备。

正常重启后：

- uname：`7.3.1-vim4kvm-uhd7+`；boot ID：`91613d13-d426-4267-bd55-d9a6d4699943`。
- GNU build ID：`58d9b0f4148da5c2275fac40f4e177a0d0cb301b`。
- 2354个模块目录文件哈希与整包精确匹配，2341模块的字节等同于打包时全量 BTF/ID 核验结果。
  74个实际加载模块的 GNU ID 与新 manifest 一致，其 `/sys/kernel/btf` 条目均存在。
- PID1 持有 watchdog，四个板级/应用服务 active、UDC configured；taint=4096（外部模块）。
- 新内核日志未见 WARNING/Oops/BUG/Call trace/panic；没有 BTF 加载错误。

## 九类门禁及额外检查

| 类别 | 本轮结果与边界 |
|---|---|
| HDMI 模式 | 未完成。原输入3840×2160可采集；M6模式工具的下载命令因输入文本损坏未执行，没有做1080p/4K往返或无信号恢复 |
| H.264 | One-KVM指定H.264，3840×2160，首帧1232ms，约10秒新增600帧；丢帧/丢包/冻结增量均零 |
| H.265 | One-KVM指定H.265，3840×2160，首帧960ms，约10秒新增600帧；同上计数均零 |
| 4K60运动 | 未执行。上述短接收为低运动桌面，不能替代运动验收；原生运动源没有启动 |
| 音频 | 仅状态检查：HDMI与应用服务active，VIM4HDMIRX采集PCM及UAC2播放PCM存在；没有听音、播音或音频内容验收 |
| HID | 未通过。MCP快捷键和输入Terminal曾打开M6终端；长命令出现缺失空格，详见下节；没有向M4发送输入 |
| 虚拟介质 | 未执行，没有挂载或改动用户介质 |
| GPU | kbase EGL1.5/GLES3.2，Mali-G52，像素179/128/128/255，gl_error=0；3.000688秒1964帧。模块身份通过；不作性能对比结论 |
| 管理页 | 认证、内核API及四应用接收通过，JetKVM第二浏览器接管关键帧通过；UU官方接收未执行，整项未完成 |

各应用均3840×2160、第一统计点已有1个关键帧，约10秒采样如下；
全部会话的丢帧、丢包、冻结增量均零，结束恢复原 One-KVM/H.265。

| 会话 | 首帧等待ms | 新增解码帧 |
|---|---:|---:|
| NanoKVM | 1841 | 601 |
| JetKVM首个浏览器 | 2106 | 601 |
| JetKVM第二浏览器接管 | 231 | 601 |
| PiKVM | 8830 | 601 |

PiKVM时间包含HTTP启动等待，未拆段作首帧性能结论。JetKVM只证明第二浏览器接管，
没有证明两个浏览器持续并播。测试复用已修正的有界HTTP就绪轮询；MCP查询恰逢切到其他应用时
返回403，该轮不是One-KVM服务的有效截图验收，不记成内核故障。

额外无线检查：打开radio后立即显式激活保存连接时返回“device is not available”；
随后只读观察已由NetworkManager自动连接 `NETGEAR_5G_Game`，5200MHz。
没有再次激活连接；因整体验收停止，iperf吞吐未启动，不能记吞吐通过。结束恢复Wi-Fi disabled。

## HID 阻塞与收尾

MCP截图确认被控终端为M6（标题 `deepdream@deepdremsMinim6`）。输入用于下载既有模式工具的
长命令后，截图显示预期的 `curl -fsS` 变为 `curl-fsS`，并报 `zsh: command not found: curl-fsS`；
其余若干空格位置也不一致，没有取得模式列表。保留截图和MCP响应；未据此区分MCP文本工具、
USB输入或源端因素，未宣称7.3.1回归。按“验收失败回到uhd7，不反复试”的要求停止后续验收，
未修改生产代码或尝试另一轮候选。

关闭本次打开的M6终端窗口，恢复Wi-Fi disabled；将FullKvm LINUX/FDT手动指回
`/edge/Image`、`/edge/vim4.dtb`，用现有inventory/register流程重新登记当前完整uhd7模块，
明确 `--no-backup`。没有新写回退工具或保存备份。

一次正常重启后：`7.3.0-vim4kvm-uhd7+`，boot ID `4c472e78-dc05-4c8c-8c96-f0f9be9f5838`，
原Image/DT、2341模块及六个加载身份重新通过正式来源锁检查。
保护文件与最初proof的差异仅为经授权清理后的extlinux和四个兼容运行时入口；
旧edge/模块及kernels.json均匹配。面板Default/hdrdual6与mainline/uhd7均available，FullKvm selected。
恢复后3秒WebRTC接收3840×2160、约59.60fps，四服务active、UDC configured，内核日志无上述故障。
安装后的boot可用46366720字节；未选择的7.3.1文件保留为失败现场材料，未再启动。

三张板票748/750/752分别持有193.136/0.718/774.284秒，累计968.138秒（约16分8秒），
全部已释放；sampling、SSH转发、本次iperf及源工具HTTP服务器均已关闭。采样期间没有并行编译。
原始数据位于本工作树 `logs/kernel-731-deploy/`，含清理清单、安装/两次串口启动日志、
installed-proof、六次浏览器JSON/PNG、M6输入截图、无线状态、恢复proof和最终接收数据。
