# 2026-11-01：跨内核原厂MAC传递修复（离线，待复审/重启授权核实）

现状：r14e已持久安装，7.3/kbase运行且默认，地址仍为192.168.50.162。
本修复尚未部署、未重启，不将离线时序测试当作实板成功。

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

以上证明旧厂商参数的实际展开；**新7.3参数`vim4.eth_mac=${eth_mac}`尚未重启验证实际展开**。
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
复审与授权核实前不取板票、不重启；后续只需一次正常启动核对动态参数、MAC、DHCP、
SSH/管理器/One-KVM/HDMI/UDC，默认继续7.3，不跑HDR/性能矩阵或操作M6。

## 用户指令来源

本worker当前会话的直接User消息，在MAC根因解释之后依次为：

1. `yes 这个要修一下`
2. `不能硬编码`

它们直接授权修复跨内核MAC且不得硬编码。没有把它们改写成“已单独明确授权本次重启”；
按协调者新增门禁，先提交/只读复审，重启前由协调者核实授权范围。
