# 2026-11-01：跨内核原厂MAC传递修复与部署

现状：固定217c9e4经独立复审通过，按用户明确部署/正常重启授权完成45.468秒短窗。
r14e/uhd6/kbase运行且默认，MAC与本板5.15既有证据一致，管理页恢复为
**http://192.168.50.210**。没有硬编码MAC/IP，没有改M6或运行HDR矩阵。

## 来源证据

厂商U-Boot基线`b60ff51ece0fb05456261b1aabb043db6bd923d5`源码：

- `cmd/kbi.c:get_mac()`执行`efuse mac`，取环境变量`eth_mac`。
- `cmd/efuse.c`将读取的每板MAC格式化并`env_set("eth_mac", mac_addr)`，不是产品代码常量。
- `board/khadas/configs/kvim4.h:cmdline_keys`执行`kbi ethmac noprint`后，把`mac=${eth_mac}`加入厂商bootargs。
- `net/eth-uclass.c`另一路`ethaddr`在没有有效ROM MAC时可生成sec_reg/chipid本地地址。

对应同板实测：安装前保存的
`logs/hdr10-r14e-persistent-user-test/before.json`中5.15实际cmdline含
`mac=c8:63:14:74:70:0d`；先前RAM启动串口沿用同一地址。
7.3正常启动串口打印`MACADDR:02:ad:36:01:89:77(from sec_reg)`，运行DT的
`ethernet@fdc00000/local-mac-address`和eth0均为该值；addr_assign_type=0，NM无cloned MAC配置。
因此是两条身份来源没有统一，不是DHCP修改MAC。

以上是部署前旧厂商参数的展开证据；新7.3参数的实际展开已由下方短窗补齐。
源码经VM中的固定git对象只读核对，不读取猜测的寄存器、不刷改U-Boot。

## 最小实现及边界

- 完整7.3的FullKvm profile增加动态参数`vim4.eth_mac=${eth_mac}`；不写入此板的MAC或IP。
- board组件安装`vim4-ethernet-generator`到systemd system-generators目录。
- PID1 generator从当前cmdline解析每板地址，在udev和NetworkManager启动前生成
  `/run/systemd/network/10-vim4-ethernet.link`，只匹配实际确认的`Path=platform-fdc00000.ethernet`。
  不按易变网卡名匹配，不影响USB/Wi-Fi，不修改NetworkManager连接或用户网络配置。
- 只接受唯一、格式正确、非零单播MAC；缺失、空值、未展开变量、重复或非法地址报错，
  不生成猜测地址。MACAddressPolicy=none让udev使用传入地址；源仍来自每板eFuse。
- 5.15没有vim4.full_kvm标记，generator不介入。内核/DT/2341模块、r14e应用与GPU文件不变。

安装路径通过board/install.sh及Ubuntu board包接入；register-runtime只允许从原精确FullKvm
profile增加此参数，其他标签、默认项和管理员自定义参数仍保留/拒绝覆盖。

## 前置时序证据与离线测试

板上systemd255自带systemd.generator(7)明确：generators在启动/重载时、**unit files loaded之前**执行，
并以三个输出目录参数调用。因此此位置先于udev coldplug及NetworkManager服务启动。
当前FullKvm没有INITRD项，不存在initrd内先启动另一套网络的路径。

`tests/test_ethernet_identity.py`执行实际generator主入口（只重定向/proc与/run文件位置），
传入systemd三个目录参数，确认主进程返回前.link已完整可读；程序没有后台任务。
这验证generator同步完成合同，不宣称已测板上udev/NM的真实时间线。
另覆盖两块不同身份的动态生成、空/缺失/未展开/重复/非单播拒绝、5.15不写入、
旧精确profile迁移时保留其他标签和默认值。实际网卡ID_PATH已只读核对。

交付前全量451项通过、15环境跳过；MAC/注册定向13项通过。
复审前未取板票、未部署；独立报告`/tmp/herdr-workers/review-mac-handoff.result.md`
未发现确认缺陷，13项定向回归通过。随后收到明确部署及必要正常重启授权，才进入下述窗口。

## 实板部署结果

唯一窗口`logs/mac-handoff-217c9e4-r1/`，FIFO持票45.468秒，正常重启一次。
安装generator并经register-runtime只升级精确旧FullKvm参数/登记清单；保留默认FullKvm、
其他启动标签、NetworkManager连接配置、r14e程序、Image/双DT/2341模块和/lib符号链接。
备份`/var/lib/vim4-kvm/before-mac-handoff-1793534466005449573`。

| 核验 | 实际证据 |
|---|---|
| 动态展开 | 串口读出的运行cmdline为`vim4.eth_mac=c8:63:14:74:70:0d`；磁盘配置仍是`${eth_mac}`变量 |
| 跨5.15身份 | 最终eth0=`c8:63:14:74:70:0d`，与既有5.15记录逐字相同；未重新启动5.15 |
| 精确网卡/配置选择 | ID_PATH=`platform-fdc00000.ethernet`，ID_NET_LINK_FILE=`/run/systemd/network/10-vim4-ethernet.link` |
| udev/NM顺序 | udev USEC_INITIALIZED=3789136；NM首次发现该网口=6865509微秒；NM激活后MAC仍相同 |
| DHCP地址 | 由串口`ip`和NM租约日志读取192.168.50.210，不按预设IP判通过 |
| 启动身份 | 7.3.0-vim4kvm-uhd6+，GNU ID仍48106f6f9fb09b12d1eaf6a5fe91953dba53d9cb，FullKvm默认，kbase配置保留 |
| 用户态/就绪 | 真实r14e One-KVM SHA仍79678cbff6ab7885de3fb0aff6f3c9ec229ea63aa1f217e7ebafb12853d6162a；manager/One-KVM/HDMI/gadget active，UDC configured，HTTP200 |

原始证据：`serial-network.json`、`udev-nm.txt`、`udev-nm-order.json`、`kernel-status.json`、
`identity.json`、`r14e-sanity.json`、`result.json`及正常重启串口日志。
generator SHA256 `ceff3267730cec55ec30cf86326bf76daff567477dc67fc1d39311d53f4ea62c`。
文件由generator在unit加载前生成，实际MAC由udev应用；不把“生成文件”说成已在udev执行前改过网卡。

本窗无失败、未写U-Boot环境/引导区，未写死IP/MAC或改动NM用户连接。票据与串口已释放。
Pi/kbase/UU/CMA及HDR未验边界保持[安装记录](2026-11-01-hdr10-r14e-installed.md)所述，交用户手测后停止。

## 用户指令来源

本worker当前会话的直接User消息，在MAC根因解释之后依次为：

1. `yes 这个要修一下`
2. `不能硬编码`

它们直接授权修复跨内核MAC且不得硬编码，最初未将其改写成单独明确的重启授权。
此后收到新的明确指令：“部署上去我再测”，且说明“包含本MAC修复部署及必要正常重启”；
复审返回后又明确要求现在部署并正常重启，才执行本次唯一短窗。
