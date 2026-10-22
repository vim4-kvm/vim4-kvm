# 2026-10-21：7.x Wi-Fi Direct 创建、扫描与并发建组

摘要：撤销 BCM43752 固件的 P2P 能力屏蔽，修正 discovery BSS 生命周期、P2P 扫描
请求版本、并发组的 ARP/ND 控制接口，并启用固件发送信用流控。真实板上完成扫描、监听、2.4/5GHz GO
建组与删除，并与原 WPA3-SAE 客户端并发通信。当前没有第二台可控制的 Wi-Fi Direct
设备，未验收对端发现、协商、客户端关联和组内传输，不能标为完整端到端通过。
本地日期为 10 月 21 日，板上测试时钟为 10 月 22 日 UTC。

## 原因与修正

此前直接清除 P2P 能力只绕过初始化失败，没有适配固件协议。本轮撤销该处理。

1. BCM43752 FWID `01-16e134aa` 的 discovery 是主控制接口上的独立 BSS，
   `p2p_disc=1` 后通过 `p2p_dev` 返回 BSS 索引，不发创建／删除接口事件。
   5.15 的 `wl_cfgp2p_init_discovery` 已按此处理。7.x 现在为该固件标记协议 quirk，
   查询索引、检查范围及占用，再创建 non-netdev discovery 对象，共用主接口控制索引，
   保留主接口的数据映射；删除不等待不存在的 IF_DEL。P2P GO/client 仍使用真实 IF 事件。
2. P2P 扫描原来只发送 v1 参数，而本固件已声明 SCAN_V2，请求反复被拒绝（-52）。
   现在与普通扫描使用同一能力选择，生成 v2 参数，旧固件复用转换函数保留 v1。
   扫描状态设置失败直接返回，固件未接受请求时不标记 BUSY。-52 是通用固件拒绝映射，
   不单凭这个 Linux 错误码推断原始固件错误类型。
3. 首次 GO 测试触发固件 trap，驱动自动恢复 STA。只追踪命令号与长度的 kprobe 发现，
   新接口的 multicast worker 在 ARP 设置后发送 `ndoe`，立即超时并触发 trap。
   5.15 的 `dhd_ndo_enable`、`dhd_arp_offload_set/enable` 都经主接口发送全局模式／开关。
   7.x 为已核实的固件添加 ARP_ND_PRIMARY，三个控制都改经主接口；地址表仍保留各自的
   BSS 索引。没有禁用 IPv6、ARP/ND 或 P2P。
4. discovery 重新创建前查询 APSTA，已有配置时不再 DOWN/UP 主链路；配置错误向上传递，
   失败设置 APSTA 后仍尝试恢复 UP。删除时清理 ENABLED，避免下一次跳过初始化。
5. 单独修正控制接口后，仍间歇出现跨频段 GO 期间 STA 保持 COMPLETED 却无法 ping 网关。
   5.15 的并发策略启用固件发送信用流控，7.x 的 fcmode 默认 0 绕过队列。该固件声明
   `proptxstatus`，实测 `fcmode=2` 后六轮并发通过。现在默认参数为 auto，只有
   BCM43752 + FWID `01-16e134aa` + `proptxstatus` 自动选择 explicit credit；显式
   `fcmode=0/1/2` 优先，其他芯片／固件继续原来的默认行为。
6. 复核出现 IPv6 `add nd ip err -52`，通过只读 vendor dcmd 查询确认 `nd_hostip`
   协议版本为 1。该已验证固件改用带 version/operation/length 的地址请求，先以
   DEL_UC 清理自己的单播表，再逐项 ADD；不删除固件 anycast 表。旧固件保留原始
   clear/add 请求。实际连续三轮加删测试地址，固件表从 5 项变 6 项再回 5 项，
   每次与 Linux 当前 IPv6 单播地址集合一致；重启后再做三轮也通过，不只是检查命令返回。

固件、NVRAM、地区、SAE 认证实现均未替换。历史上其他固件崩溃仍不能全部归因于这次的
ND 控制错误；保留私有转储和自动恢复，不宣称已消除所有崩溃。

## 实板验证

内核 `7.3.0-rc7-vim4kvm-uhd1+`，BCM43752/2 SDIO，原固件 SHA-256
`af7310c6c44da2690ea9f666eea8477a48e906810a1246a5fa207d3788fdf309`。

- 正常启动由系统 supplicant 创建 `p2p-dev-wlan0`，P2P、SAE、SAE_EXT 均保留。
  没有 discovery IF_ADD/IF_DEL 等待超时。最终重启后自动恢复原 WPA3-only 网络，
  SAE/H2E、group 19、PMF required、DHCP `192.168.50.156/24`。
- `iw` 创建／删除 P2P-client 接口成功。此项只覆盖接口生命周期，不包含客户端关联。
- NetworkManager 会清理由它管理、却非它发起的临时 P2P 组；不将直接 `wpa_cli` 下
  瞬时出现的 GO 当作持续出网成功。独立测试临时释放 wlan0，启动私有 supplicant，
  使用已保存的 SAE 设置，完成测试后恢复原 NetworkManager 连接。
- 自动流控候选重启前后各六轮通过；补齐 ND 地址协议的最终版本，重启前后各四轮、共八轮通过。
  每轮覆盖社会信道扫描、2 秒监听、建组、维持、无线 STA 网关 ping、删除。
  GO 频率在 5200、2412MHz 间交替，均确认实际 GO 频率与删除完成，
  每轮在 GO 存在时通过 wlan0 ping 网关 3 次，原 STA 保持 COMPLETED。
  测试期间复用原板有效 DHCP 租约，不将此并发检查写成新 DHCP 验收。
- 标量追踪显示 15 次 P2P escan 返回 0、17 次 discover_listen 返回 0；同期 escan
  回调有 17 次成功完成及 66 次 partial，其中也包含普通 STA 扫描，不冒充全部为 P2P。
  没有可控制对端，P2P-DEVICE-FOUND 为 0。
- 正常重启后 WPA2 热点进入 AP、2462MHz，地址 10.42.0.1/24，DHCP 端口已监听；
  关闭后恢复原 WPA3 连接，网关 ping 5/5，绑定 wlan0 的 HTTPS 请求返回 200。
  未要求手机关联热点，不将 AP 启动当作热点客户端传输验收。
- 最终启动后系统失败服务为零，kernel taint=0；One-KVM 和 manager active，USB configured。
  流控候选首次重启后 `pkt2bus=113`、`txs_indicate=113`，TLV 解析、descriptor update、
  队列溢出计数均为 0；启停循环后 mac_update_fails 有少量增加，TLV 错误及队列溢出仍为 0。
  没有真实 peer 流量，不能以这些计数代替组内吞吐／重传验收。`txs_discard` 也不是简单的
  网络丢包数：驱动将正常完成和部分丢弃状态合在该计数，保留原始 stats 供后续比较。
  循环期间仍见短 vendor IE 提示和停组后 chanspec 查询返回 -52，未隐藏这些日志。
- 最终热点往返后出现一次普通 escan timeout，保留为后续定位项；之后以 root 发起
  主动扫描正常完成，返回 15 个 AP，频率覆盖 2.4/5GHz，SAE 保持连接。
  普通用户直接请求扫描曾被权限拒绝，不将它误报为驱动失败或扫描通过。
- 最终模块重启前后八轮期间没有新增固件 trap，私有目录仍为此前两份失败候选转储。
  这不代替真实 peer 流量或长期运行验收。
- 无并行无线测试时，通过 8080 管理器网关登录 One-KVM，H.264 3840×2160 解码，
  2 秒预热后的 8 秒窗口约 59.96fps，新增 freeze/drop/lost 均为 0；只作功能回归，
  不作无线 4K 吞吐或新的延迟结论。测试结束恢复原编码选择并关闭测试浏览器和 SSH 转发。
  首次把网关当回环后端访问得到 401，随后误用 80 管理页得到 API 非 JSON；均非通过记录，
  按正常网关登录后重测成功，没有关闭认证。

板端测试入口（会短暂切断无线、有线保持）：

```sh
sudo python3 check-wifi-p2p.py --exclusive --cycles 4
```

源码为 `packaging/kernel-edge/check-wifi-p2p.py`。仅限已有正常 SAE 配置的 7.x VIM4，
有线 carrier 必须为 1，并获取独占锁。凭据与详细 supplicant 日志只写 root 私有的 /run
临时目录，结束清除；公开输出仅为角色、频率、事件计数与结果。不改保存的连接配置。

## 构建、失败记录与回退

- Linux 提交 `ffdadae5b3f8593f10707d70aa0391de79b7823f`，tree
  `c0bee61e51dd5ff99e375679fa472bb483e098e6`；包含前序协议修正 `bffaeb294822`、流控 `b784909fb1d7`。
- Image 没变，SHA-256 `25241ef8c402619e6917e6826129ba301c4b4dfacc4665db365620e9489faa48`。
  使用匹配 vmlinux 的完整 in-tree modules 构建、modpost、split BTF 和安装阶段。
  模块归档 `/home/deepdream/build/p2p-ndo-modules.tar.gz`（vim4-build VM），2334 个模块，
  SHA-256 `8ae5d70abae83bbf390e20a93f7317029db93a090ad570e869902c051b716794`。
  完整构建证明为板端 `/etc/vim4-kvm/kernel-p2p-build.json`，双内核清单已重新核验。
  本轮范围明确的结果另存 `/etc/vim4-kvm/runtime-wifi-p2p-20261022.json`（root 0600），
  不覆盖旧的完整系统验收记录。Linux 与主仓库本轮提交暂只保存在本地，未推送。
- 首次单独替换两个模块被完整证明校验拦下：头文件变更还影响 BCA 模块。
  已回退并恢复 STA，随后按完整构建中的四个 brcmfmac 模块一起安装，校验通过。
  没有跳过校验、关闭 BTF 或改变受保护的 5.15 Image。
- 早期 ND-only 候选曾连续四轮通过，但重启后的重复测试再次出现断流、固件 trap，
  NM 无法恢复；有线 SSH 保持可用，重新加载无线模块后恢复原 SAE 连接。
  trap PC 与第一次 ND 命令触发的不同，不把它们合并成已经完全证实的单一根因。
- 后续 ARP/ND 控制候选也有四轮通过及另一次第二轮断流：只能说明间歇问题仍存在。
  启用 TX credit 后才重新进行完整测试。保留这些失败日志，不用此前通过结果覆盖失败。
- 第一轮脚本退出恢复曾与 NM 自动连接竞争并覆盖原始失败；现等待原连接恢复，异常时
  先在私有 supplicant 仍存活时删除自己创建的组，然后结束进程，最后交还 NM。
- 首次扫描追踪因函数名被编译器加 constprop 后缀而未安装探针，没有更改无线状态；
  修正符号后重跑。测试结束移除自己的探针及 trace instance，不触碰其他 tracing 设置。
- 备份为 `/var/backups/vim4-wifi-p2p-20261022*`，包含各轮模块、原内核清单和原连接 UUID。
  最终备份的前一轮模块仍启用 P2P；最早一轮保存本轮开始时的版本。回退时用对应完整
  构建证明重新登记，不能只恢复单个模块或旧 manifest。
- 驱动旁 `test_p2p.py` 编译真实函数，ASan/UBSan 验证 v1/v2 序列化、1–64 个信道、
  分配失败与固件拒绝、已有 STA 的 APSTA 设置、删除状态清理及 ARP/ND 的接口选择；
  同时验证自动流控的芯片／固件／能力边界、显式参数优先及用户禁用 SAE 的优先权。
  ND 地址测试覆盖 0–8 项、请求长度与字节布局、地址内容、padding 及 clear 失败不继续写入。
  Mac、ARM64 Linux 均通过；内核 checkpatch 为 0 error/warning/check。

原始日志在忽略的 `logs/wifi-p2p/`：安装与回退、失败候选、最终并发循环、标量扫描／监听
追踪、正常重启、热点往返和完整模块证明。固件转储保持板端 root 私有，不发布内容。
