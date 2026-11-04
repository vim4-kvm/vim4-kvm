# USB 与供电

按任务读[PD](../usb-pd.md)、[接线](../hardware.md)、[应用集成](application.md)、[输入延迟、长按和Mac滚轮](../input-latency.md)。
重枚举panic/控制端点故障直读[HID重绑](../kernel.md#hid-重新绑定)、[CRG](../kernel.md#crg-usb-控制端点重连)。

板级gadget拥有configfs、PD负责有限开机协商；应用用现有HID，不重建gadget或部署上游设备USB脚本。
One-KVM限定助手可临时改描述符/功能链接、增多媒体键/网络实例，不删原HID；停用后恢复原配置，若有介质则保留当前组合至主机弹出。
端点预算、映射及恢复顺序按[One-KVM HID配置](../../One-KVM/VIM4.md#hid-功能配置)，端点不足先调USB功能，已有自定义组合保持不变。
早期独立入口边界见[内核证据](../kernel-mainline.md#相关记录)。

## 共享虚拟介质

挂载归板级共享LUN，不随当前KVM名称；介质存在时禁改USB配置/替换介质。
管理器介质页显示实际文件、读写状态和USB连接，KVM界面页仅显示摘要。
切换涉及PiKVM且有介质，可等待被控机安全弹出后由当前页提交，助手再核对；
取消、离开页面、状态未知、断连、应用改变或超时都会终止等待，期限按管理器实现。
不强制弹出：卸载卷≠SCSI eject；管理器弹出前确认主机停用/安全卸载，遵守防弹出锁，不解绑USB强移，结束保留空存储接口。
NanoKVM不按旧enabled标记自动重连数据盘，文件保留、用户主动连接。

管理器汇总各应用镜像/共享数据盘；ISO与JetKVM限定只读。
查询/变更读真实LUN，PiKVM显示外部镜像；JetKVM/One-KVM外部介质只显示，禁应用内替换/弹出，先主机安全弹出再管理器弹出。
四应用列表按来源分组显示全部共享盘/其他应用镜像；其他目录镜像只读、禁止当前应用删除。
数据盘NanoKVM/One-KVM可写，JetKVM/PiKVM只读；Nano旧虚拟磁盘开关仍对应原盘。
主机弹出光盘使内核清LUN，应用随之清记录。

## 共享数据盘

管理器提供FAT32多盘、卷标、文件操作、扩容、整镜像下载和快照恢复，接口与边界见[API](../../vim4-manager/README.md#共享数据盘-api)。
挂载中禁编辑、状态未知拒写；只读浏览不保证主机缓存一致；用mtools，单文件受FAT32限制。
旧盘不自动格式化/改卷标。
助手统一用[vim4media](../../board/vim4media.py)校验目录及共享锁；长操作仅持数据盘锁、防同盘挂载，不全程占全局锁。
先装提供介质API、mtools和dosfstools的板级包，再更新应用和管理器；能力依赖按[打包实现](../../packaging/ubuntu/package.py)，防旧平台版本满足却缺模块。
网页更新不能代装平台依赖，旧板先更平台。

PD并非完整TCPM，单线拔线即断电；启动枚举通过不证明睡眠唤醒、运行中重置或NCM通信通过。
改描述符/协商先测边界，再验主机枚举/真实输入，不扰他人。

## 错题

| 触发 | 做法 | 验证 |
|---|---|---|
| 认为USB-C供电必须加VIN才可HID | 已验开机协商后单线供电/HID，不代表所有供电/热插拔 | [PD](../usb-pd.md) |
| 卸卷仍不能弹PiKVM镜像 | unmount不清防弹锁，须host eject；厂商eject不发configfs inotify，现有轮询须核LUN file | kvmd/kvmd/plugins/msd/otg/__init__.py |
| 管理器挂介质后应用状态失真/覆盖外盘 | 查询/变更读真实LUN，外部仅显示不覆盖，助手共享锁内再核；四应用逐一网页验，不能只看管理器 | logs/media-crossapp/、kvm/internal/vim4media、One-KVM/src/msd/controller.rs |
| NAS卡住使USB主机超时、复位后不认存储 | 后端I/O须早于主机SCSI超时返回错误；本内核无forced_eject，模拟拔线用UDC解绑，故障后需重枚举 | [超时预算/实测](../bringup/2026-10-18-nas-storage-usb-disk.md) |
| 合成FAT32写入层将只读文件判改写 | 块跨簇；FAT/数据起点按簇及写入层块对齐，FAT无时区时间按挂载浏览器偏移换算 | vim4-manager/internal/vfat |
