# 2026-10-18：NAS 网络存储与 NAS 文件夹 U 盘

## 部署来源

管理器 `vim4-manager` 从 `38e6986` 起到 `fdb828d`，最终安装 `2.5.1+vim4.20261017.28.dev.22.gfdb828d.dirty`
（dirty 仅为主仓库文档改动）。最终全量包 `dev.24`/`dev.25`（含 One-KVM）。
测试 NAS：Mac 上的 Samba 容器 `vim4-smbtest`（445 端口，含中文共享名）与 OrbStack VM `vim4-build` 的 NFS 导出 `/srv/nfs`
（OrbStack 自动把 2049 转发到 Mac）。被控电脑为同一台 Mac。

## 平台事实

- CIFS、NFS 为模块；`CONFIG_NLS_DEFAULT=iso8859-1`，SMB 必须加 `iocharset=utf8`，否则中文共享名报 error(2)；挂载单元 `What=` 里的空格直接写，不能写 `\x20`。
- 测试挂载带 `nofail` 时 mount 返回 0，错误被吞掉；测试挂载只用基本参数，开机单元才加 `nofail,_netdev,x-systemd.mount-timeout=30`。
- NFSv4/TCP 在静默丢包时 I/O 不受 timeo/retrans 限制（超过 300 秒）；应用必须自己限时（管理器 2–3 秒工作进程，One-KVM 1.5 秒）。
- 板子同时做 NFS 服务器并 loopback 挂载自己时整机卡死，需 RESET，日志未保留。服务器移到 VM 后未复现。
- 厂商内核在 FUSE 挂载上执行 inotify_add_watch 时发非标准 `FUSE_CANONICAL_PATH=2016`（fs/fuse/dir.c）。go-fuse v2.8.0 解析失败不回复，
  请求永久挂起：会话卡在 attaching，SIGQUIT 后进程成僵尸，需写 `/sys/fs/fuse/connections/N/abort`。v2.12.0 回复 ENOSYS，inotify 得到错误，其余正常。
  回空成功会让内核写 `path[-1]`，不可用。
- 本内核 f_mass_storage 没有 `forced_eject`；模拟拔线用 UDC 解绑→清空 LUN→重新绑定。
- 主机 SCSI 命令超时（约 30 秒）后 Mac 复位整个 USB 设备，之后不再识别存储接口，直到 UDC 重新枚举。LUN 后端 I/O 现限 8 秒返回 EIO。
- 冻结写入时 Mac 的 msdos 驱动无限重试，dd 停在不可中断状态；NAS 恢复后写入完成。

## 实板验证

- 存储：SMB 保存/挂载/目录/卸载/删除、中文共享、访客、错误文案、会话期间拒绝卸载（「挂载点正被进程或 USB 虚拟介质使用」）、
  NAS 冻结时列表有界、复位后开机自动挂载、`storage-migrate` 对已最新单元无改动；NFS 各版本对 VM 服务器挂载、冻结时板子保持响应。
- U 盘（SMB，可写）：Mac 3 秒内出现 NASTEST 卷，50 MiB 文件 md5 一致；新建、修改、改名、删除、多级目录、20 MiB 新文件弹出后自动写回，
  内容与 md5 一致，旧版本进入 `.vim4-nasdisk/trash`，会话目录删除；只读文件不再被误判改写，改名识别为 rename。
  主机与 NAS 同时修改 → 冲突副本 `保留 (冲突 …).txt`，主机删除被 NAS 改过的文件 → 保留 NAS 版本。
  修改时间：Mac（+08）看到 NAS 的本地时间，主机写入的文件回写为正确 UTC。
- 拔线：needs-decision（FAT 脏标志，中文原因），重新挂载后全部文件可读，安全弹出后写回；「写回能识别的内容」路径也验证。
- 只读模式：Mac 以只读挂载，写入被拒，弹出结果 unchanged。
- NAS 冻结（`docker pause`）：只读读取 32 秒后 Mac 得到 I/O 错误、设备不复位、恢复后同一文件可读，状态接口 3.0 秒并显示 `nasStalled`；
  可写写入 → 弹出 needs-decision「NAS 在 U 盘写入期间暂时无响应」→ 重新挂载 → 弹出 → 写回，md5 一致。
- NFS 可写：写回的目录 0755、文件 0644（服务 UMask=0077 曾让文件变成 0600）。
- 网页：新建文件夹（同名、私有目录名被拒）、清空回收目录。

## 上板发现并已修复

go-fuse 未回复 opcode 2016；FAT 数据区未按 4 KiB 对齐导致相邻文件被标脏（16812032 字节起点）；源文件一次属性不符即永久 EIO（加 1.1 秒复核与日志）；
FAT 时间按 UTC（改用浏览器偏移）；NAS 卡死使主机复位 USB；写超时后重新挂载仍要求决定；回写文件权限；失败会话无操作按钮；旧挂载单元缺 iocharset。

## One-KVM 录屏保存到 NAS

One-KVM `cf50f7ed`、界面重做 `34873606`、文件夹历史与估算 `622a2b51`、`9bd71c1a`。账户 admin/admin（此前登录失败发生在部署重启期间）。
- 位置列表含本机、两个 NAS、未连接的共享（not_mounted）；选择即生效，非法文件夹（`../x`）在输入框下报错且不保存。
- SMB 录 20 秒：4K H.264 + Opus，20.1 秒；NFS 录 12 秒正常。
- 录制中冻结 SMB（docker pause）约 12 秒后停止，NFS（VM 内 nft 丢 2049）约 5 秒后停止，原因 storage_unavailable；冻结期间状态接口 1.5 秒，RSS 约 110 MB，无 D 状态线程残留；
  已录部分留作可播放的 `.mkv.part`（9 秒、120 秒）。横幅「录屏已在 08:29 自动停止」写明 NAS 与已录时长，恢复后追加「已恢复，可以重新开始」。
- 改文件夹后旧录像仍列出（按位置记住最近 8 个文件夹），按 folder 下载 200、未知 folder 400。
- 只在已连接 NAS 无响应时提示「其中的录像未列出」，主动断开的共享不再常驻警告。

## 界面重做

管理面板网络存储页改为以 NAS 列表为主体：U 盘只从 NAS 行进入，选择面板内联展开（已选择栏、新建文件夹、卷标默认收起、LUN 占用/USB 未连接预检），
会话、未写回修改与上次结果收进顶部活动卡；行操作收进「⋯」。实板经网页完成一次挂载与弹出写回。非 ASCII 文件夹名默认卷标改为 NAS（「U盘测试」曾得到「U」）。

## 未验证

- Windows/Linux 主机；超大文件夹扫描耗时；VM 无 Samba，源文件瞬时属性不符的确切原因未复现（现有日志会记录）。
