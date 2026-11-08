# 2026-11-08：fusb302 屏蔽时管理器显示固件 PD 交接

正式默认以 `module_blacklist=fusb302` 保留 U-Boot PD 合同后，设备树仍声明控制器，
`vim4pd.kernel_power` 一直返回 `kernelPD unavailable/contract null`，概览只显示“状态不可读”，
固件交接详情被隐藏。现已改为 cmdline 屏蔽 fusb302 时内核状态让出；
helper 因控制器仍被声明而直接返回，不运行 `usb-pd-init --status`、不读历史合同。
PD 服务仍按“controller reserved”跳过，没有引入 Linux 协商或原始 I²C 回退。

## 改动

- 主仓库 [vim4pd.py](../../board/vim4pd.py) `kernel_pd_blacklisted`/`kernel_power`；
  `modprobe.blacklist` 只禁自动加载，不算让出。离线用例见 tests/test_pd_boot.py。
- vim4-manager `f384b3d` 的 helper `power_status`，组件包 `2.5.1+vim4.20261029.102.dev.11.gf384b3d`，
  容器 verify 通过。
- [部署检查](../../packaging/kernel/final-manager-pd.mjs)改为要求无 `kernelPD`；
  [B 状态期望](../../packaging/kernel/pd-b-state.json)换成本次实测，board 字段与旧基线逐项相同，
  power 仅少 `kernelPD`，固件字段相同。

## 上板

板上 .42 默认内核不变，boot_id `8ad0825f-cb9c-4bea-98a0-19b37be62793`，未重启。
单票内先存安装前 API 和概览截图，再以 root 0644 安装新 vim4pd.py
（SHA256 `9cdfde80…6cb4`，旧版 `f7fdac85…53b0` 即 `10ab4e5~1`），随后 board.py 组件部署 manager。
deploy 末尾的 check 因默认 `--kernel 5.15.137-vim4kvm` 不符失败（安装已完成、版本正确）；
按文档用 `--kernel 7.3.1-vim4-20261107.2` 另跑 check 通过，没有重装。

| 项 | 安装前 | 安装后 |
|---|---|---|
| `/api/status` power 键 | bootContract、firmwarePD、kernelPD、vbusPresent | bootContract、firmwarePD、vbusPresent |
| 概览 PD 协商 | 状态不可读 · 内核实时 PD 合同 | Type-C · 无确认的 PD 合同 · 启动固件 · Rp 3A，可展开固件详情 |
| PD 服务 InvocationID/结果 | 不变 | 不变，未重启、未协商 |
| fusb302 / Type-C 端口 / UDC | 未加载 / 无 / configured | 相同 |

管理器重启使“最近事件”从新进程开始，这是既有行为。
概览截图和原始日志在 `logs/manager-pd/run-20261108T031009Z/`，摘要及 SHA 见
[数据](data/2026-11-08-manager-pd-firmware-display.json)。

## 未验证

只看了中文桌面概览；手机布局和连接图未截图。连接图 `powerConnection` 在无合同、
`vbusPresent=null` 时仍显示“未知”，未改。只验证当前 B 状态；TCPM 接管（A 状态）下行为
由离线用例覆盖，本次没有上板。
