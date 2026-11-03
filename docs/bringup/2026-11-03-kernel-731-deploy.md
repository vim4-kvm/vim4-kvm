# 2026-11-03：7.3.1 整包部署与 boot 清理

7.3.1 完整包已安装并留作默认 FullKvm/kbase，来源锁更新为 `25110086de2ef`。
九类按下表范围完成：音频只验服务/设备状态，UU只证明官方客户端RTP接收；没有原生UU渲染证明。
首次因MCP长文本损坏中止并回uhd7；随后按协调者要求在uhd7复现同一问题，才重新登记现有7.3.1
启动文件并继续验收。没有重新安装、复制内核文件或修改驱动；后续输入改用US输入源与逐键保持50ms。

## 输入与预检

部署工具来自已合入主线的 `3c199fd2d2133229008e94c76b483e7c7073d405` 工作树。
候选源码 `25110086de2ef6aa9564a31a7c694eca893fd423`，release 为
`7.3.1-vim4kvm-uhd7+`，完整包 `deploy-tools-731-final.tar.gz`，69,566,113 字节，
SHA256 `59a8343225da61a1cf81ec70a60603d451cb2d2611ce493f25f260bd83e869cc`。
上传的安装器 SHA256 为 `f5f986f027106a6bd099989f6548ea9aad6cf406467ab5d6eead1ef9818a3ffb`。

预检核对实际 uhd7 Image/DT、2341 模块及三个 `4111568841bd` overlay，
完整 proof 含2368个保护文件；六个 kbase/采集模块加载 ID 与正式锁一致。
串口 `/dev/cu.usbserial-1100`、921600 已登录并读取 uname/boot ID。
`fuser /dev/watchdog0` 确认 PID1/systemd 持有，RuntimeWatchdog=30s、RebootWatchdog=60s。
三次重启均开启串口日志；没有向开发 M4 发送 HID。

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
| HDMI 模式 | 通过限定范围：1080p60→4K60往返、清除EDID无信号及恢复，实际wire刷新均约59.999Hz；没有重跑19档矩阵 |
| H.264 | One-KVM指定H.264，3840×2160，首帧1232ms，约10秒新增600帧；丢帧/丢包/冻结增量均零 |
| H.265 | One-KVM指定H.265，3840×2160，首帧960ms，约10秒新增600帧；同上计数均零 |
| 4K60运动 | 通过：原生运动源，实际解码3840×2160，60秒3599帧、59.9814fps，丢帧/丢包/冻结增量零；另两段1080p或混合尺寸采样不计4K结果 |
| 音频 | 仅状态检查：HDMI与应用服务active，VIM4HDMIRX采集PCM及UAC2播放PCM存在；没有听音、播音或音频内容验收 |
| HID | 通过事件计数：M6收到20对按键、5对点击、4次绝对移动、4次正反滚轮；USB profile重连后收到5对按键与4次相对移动。长文本问题另记issue |
| 虚拟介质 | 通过：M6只读/可写挂载专用FAT夹具、读marker、写256KiB并核SHA；两次安全弹出均清空内核LUN，结束删除测试镜像并恢复配置 |
| GPU | kbase EGL1.5/GLES3.2，Mali-G52，像素179/128/128/255，gl_error=0；3.000688秒1964帧。模块身份通过；不作性能对比结论 |
| 管理页 | 认证、内核API及四应用接收通过，JetKVM第二浏览器接管关键帧通过；UU官方客户端连接并取得两次新鲜HEVC零丢包RR，只证明RTP接收 |

各应用均3840×2160、第一统计点已有1个关键帧，约10秒采样如下；
全部会话的丢帧、丢包、冻结增量均零，结束恢复原 One-KVM/H.265。

| 会话 | 首帧等待ms | 新增解码帧 |
|---|---:|---:|
| NanoKVM | 1841 | 601 |
| JetKVM首个浏览器 | 2106 | 601 |
| JetKVM第二浏览器接管 | 231 | 601 |
| PiKVM | 8830 | 601 |

PiKVM时间包含HTTP启动等待，不作首帧性能结论。JetKVM只证明第二浏览器接管，没有证明持续并播。

打开radio并等待保存连接自动激活：`NETGEAR_5G_Game`、5200MHz、wlan0地址192.168.50.156。
iperf3显式 `--bind-dev wlan0 -B 192.168.50.156 -R -t 30`：接收1437990912字节、30.001056秒，
383.4507Mbit/s；开发M4为有线iperf服务端。只证明本次下行，不重做5.15比较或长测。结束恢复Wi-Fi disabled。

## 首次中止与 uhd7 对照

M6终端（`deepdream@deepdremsMinim6`）下载命令的 `curl -fsS` 变为 `curl-fsS` 并报command not found。
当时按失败处理指令停止，手动将FullKvm指回 `/edge/Image`、`/edge/vim4.dtb`，用现有流程无备份重新登记。
正常重启到uhd7，boot ID `4c472e78-dc05-4c8c-8c96-f0f9be9f5838`；原Image/DT、2341模块及六个加载ID
通过旧正式锁，面板两项available、FullKvm selected，3秒接收4K约59.60fps。
boot可用46366720字节；保留7.3.1现场，未改驱动或宣称内核回归。
748/750/752三票累计968.138秒（约16分8秒），释放后收到继续验收指令。

uhd7以同一One-KVM MCP `type`调用输入完全相同长命令、不回车，截图再次出现缺空格、字符拼接和中文
输入法候选框。当前MCP源码按字符30ms间隔，按下与释放之间没有保持时长；本轮没有API调速参数。
登记MCP文本/输入法issue。切US输入源，MCP `hold_key`逐字保持50ms、间隔20ms；
短下载命令核对后执行，由HTTP传输现有Swift工具与调用脚本。

## 继续验收与最终状态

用安装器 `upgrade_registration` 读取已安装manifest与哈希，validate/sync后依次原子写kernels.json、extlinux。
没有重装或复制内核。确认PID1 watchdog，开启串口日志后正常重启：
最终boot ID `1959c0c4-4ac5-4505-a7cf-ec192209c4ab`，release/GNU ID与首次7.3.1完全一致。

HDMI使用现有 `hdmi-source-mode.swift` 和 `hdmi-mode-fixture.py`：仅切CoreGraphics模式仍可能是4K线缆
时序，因此用单时序EDID约束1080p60。接收端实测1920×1080@59.9988925、恢复后
3840×2160@59.9988926；浏览器分别收到1080p与4K。`--clear-edid 0`后hpd_request=0、
edid_bytes=0、link_ready=0；`vim4-edid restore`后恢复4K，3秒新增180解码帧、59.9442fps、零冻结。
源工具只有list/set，没有全档扫描入口；本轮验证1080p/4K往返。

M6使用现有 `input-target.swift` 的临时接收窗口记录事件。按键/绝对移动/点击/滚轮经MCP，
相对移动经One-KVM现有WebSocket HID协议（MCP仅提供绝对坐标接口）。专用USB夹具为K731TEST，
M6读到marker；写入262144字节SHA256为 `8a39d2abd3999ab73c34db2476849cddf303ce389b35826850f9a700589b4a90`，
弹出后在板侧从实际镜像再次读出核对一致。

恢复USB原配置时暴露应用生命周期问题：helper重建gadget，而HID配置值未变导致backend跳过重载，
后续MCP写入报endpoint shutdown。手工UDC检查错误地写入空字符串（没有真正解绑），再次绑定返回EBUSY，
这次无效检查不计为通过；没有把EBUSY归为内核故障。随后用既有API切full_no_consumer再恢复原profile，
日志确认backend成功重载，UDC configured，M6记录5对按键和4次相对移动。只登记该应用问题，没有改代码。

原生运动源两次各190秒，总运动时间380秒（低于10分钟）。第一段180秒浏览器采样受UU会话1080p输出影响，
第二段中途恢复输出，均不计作4K合格数据；显式设置2160p60后，在第二段源内独立采样60秒，得到表中4K结果。
结束恢复原output height=0/fps=0/hdr=false，最终3秒仍收到3840×2160、约60fps。

官方UU 4.42.0经CLI连接核对过device ID的 `m6-vim4-kvm`。两次HEVC RR age分别1245.8/186.1ms，
total_lost=0，RTT约3.92/5.84ms；只证明官方客户端RTP接收。macOS对可见原生UU窗口截图返回
`could not create image from window`，未取得官方解码/渲染证据，不把RR冒充该证明。
UU已断开；没有向M4发送HID，没有听音。UU之后再次恢复视频配置，并确认最终4K接收。

最终核对2354模块文件、2341模块库存、74个加载ID/BTF全部匹配新整包；taint保持4096。
无新增内核WARNING/Oops/BUG/Call trace/BTF错误；启动时iwconfig的wireless-extensions弃用提示单独保留，
不当作内核WARN堆栈。旧 `/edge` 与完整uhd7模块（含三overlay）共2361文件哈希不变。
FullKvm指向 `/kernels/7.3.1-vim4kvm-uhd7+/Image` 和同目录vim4.dtb；Default/hdrdual6保留，
内核面板登记SHA256为 `c3a6149c3ca13439d109923c65301d72e174aa302fc272de8821ca0a27321469`。
正式锁更新为实际7.3.1，旧三overlay仅留uhd7历史/基线证明，不再列入当前retained_runtime。

继续验收753/754/755分别持有344.289/1490.163/259.805秒，合计34分54秒；加上首次约51分2秒，
均主动释放。sampling、SSH转发、iperf和源HTTP服务器已关闭。
未并行编译、用子代理或push。原始数据在 `logs/kernel-731-deploy/`。

## 离线交付核对

正式锁的配置、清单、模块库存、运行时描述、验收和安装收据已入库；重复candidate-731锁删除。
build.sh与package-unified默认读取正式锁，后者的旧uhd6/uhd7固定源码分支删除，保留显式独立候选输入。
VM在heavy票据下验证干净25110086源码、olddefconfig哈希，并完整重新检查2341模块的vermagic/BTF/ID。
复核包位于VM `~/build/deploy-tools-formal.0GSLHV/package.tar.gz`，69566572字节，SHA256
`ca0f59fc9957e0276b50a6a0fa0f94006a38341959c0d75dd70a9b50ed1b8dc8`；它是离线工具复核产物，
没有上传或安装。内核/双DT/运行时/BTF/模块文件与已部署包相同，模块tar元数据不同；正式部署仍固定原包59a834…。
