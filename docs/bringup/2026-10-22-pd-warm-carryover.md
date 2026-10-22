# 2026-10-22：PD 热重启历史合同卡片

第一轮真实热重启已呈现 S3，验证后恢复既有 manager/runtime；第二轮视觉修正已部署保留，
真实页面为无历史记录的 S4。两轮证据与各自回退入口见下文。
实现只保存合同历史和改变显示，不增加 PD 消息、不刷 U-Boot，不改内核或应用锁。
manager 在独立工作树 `build/pd-warm-carryover/manager`，分支 `pd-warm-carryover`，
提交 `31a54a8c5cf986e662a5f8851e6f34a8e0b50e55`，未推送。
主仓 `board/vim4pd.py`、`board/vim4-board-runtime`、`tests/test_pd_boot.py` 与文档保持未提交。

## 实现与离线验证

固件 PS_RDY 的 `fw.contract` 先保存；Linux bootstrap 成功完成后覆盖。
5.15 入口改由同一 Python 包装器执行原 `usb-pd-init`，7.3 保留原一次判断/修复条件。
协议工具与参数不变；Linux RDO 按现有 `request_5v()` 的固定标志和最终请求电流还原，
包括工具处理后续 Source_Capabilities 的情况。写入失败不重试协商、不覆盖旧记录。
历史文件使用同目录临时文件、fsync、rename；无本次确认不写、不删。
manager helper 复用板级解析器，只读取其他 bootId 的完整记录。
安装时先更新板级模块，再更新 helper；不重启 PD 服务。

UI 按 Linux、固件、本次超时/空 PDO/VBUS 历史、无历史、其他状态的顺序显示。
S3/S4 隐去「初始化超时/未完成 PD 合同」，保留独立错误与 footer；空 PDO 的 summary
统一为「来源能力 · 本次未收到」。时间保留记录中的板端时区，跨年显示年份。
主值单行截断，detail 的 title 保留全文。

离线通过：板端 10 项；manager `go test ./...`；helper 150 项（Mac 缺 Linux FAT
工具，12 项跳过）；锁文件前端构建；Playwright S1–S5 精确文案、独立错误、板端时区/
跨年和 390px 布局。Go 初次受环境 GOROOT/工具链混用影响失败，清除 GOROOT 后通过：

```sh
env -u GOROOT GOTOOLCHAIN=local go test ./...
env -u GOROOT GOTOOLCHAIN=local GOOS=linux GOARCH=arm64 CGO_ENABLED=0 \
  go build -trimpath -o ../vim4-manager-arm64 ./cmd/vim4-manager
```

主仓完整测试最终为 169 项、5 项跳过，其余通过，输出 `logs/pdcard/root-tests-final.log`。
板端专项输出为 `logs/pdcard/pd-python-tests.log`。

候选二进制 SHA256 `9a42532910a303fc3ccc4dbd30c3af9b495c2816449357d36d220bb6b0d30e8c`，
Go 元数据 vcs.modified=false。离线截图在 `logs/pdcard/`：`s3-390.png`、
`s3-previous-year-390.png`、`s4-390.png`、`s5-empty-pdo-390.png`。

## 上板窗口

首次窗口在上传时遇到 root 所有暂存目录权限错误，未安装候选、未重启。
finally 已恢复四个文件、核对基线与实际 HID；日志 `logs/pdcard/board-window-initial.log`。
第二次使用独立 run2 目录，修正暂存目录所有者，等待其他音频任务释放板锁：

```sh
/usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/pd-warm-carryover/window.py \
  > logs/pdcard/board-window.log 2>&1
```

第二次窗口完成一次热重启。备份为板上
`/var/backups/vim4-pd-warm-carryover-20261022-run2/files.tar`，本地为
`logs/pdcard/backup/files.tar`，两端 SHA256 均为
`4bbaa05d1fab9a663508732c58f26f81337b6b4e9f881f9042ab916b46399d54`。
备份包含 manager 二进制、helper、vim4pd.py、board-runtime，并单独记录历史文件是否存在。
上传后安装板级模块/runtime、helper、二进制，只重启 manager；未重启 PD 服务。

按本次明确授权，使用 `remember_contract()` 预置 5V/3A、RDO `1304b12c`、USB comm=true、
origin=linux 的记录，bootId 取当前启动，时间为板端写入时刻。数据对应此前实际 Linux
日志中的 Request（见 [热重启审查](2026-10-22-pd-warmboot-audit.md)），但本轮预置是
验证夹具，不是本次确认的新合同，也不声称测到 Mac 内部保存的合同。
写入后同次启动 `previous_contract()` 返回 None；重启后 API 才输出 `lastContract`。

实际输出（完整内容见 `logs/pdcard/board-window.log` 和 `live-s3-api.json`）：

```text
旧 bootId: 0511bd09-d820-4a8d-98ee-7d856fb38475
新 bootId: 590745c9-a1b3-4af3-b07a-1bc6a990e824
PD bootstrap skipped: firmware timeout or Type-C fallback
LIVE_S3_VERIFIED: vbusPresent=true, bootContract=null, flags=208,
  timedOut=true, contract=null, sourceCapabilities=[]
lastContract: 5V 3A, usbComm=true, rdo=1304b12c, origin=linux,
  bootId=0511bd09-d820-4a8d-98ee-7d856fb38475,
  establishedAt=2026-10-22T15:29:34+00:00
```

真实页面主值「沿用上次合同 · 5V 3A」、detail/title「本次未重新协商 · 上次 10-22 15:29」，
summary「来源能力 · 本次未收到」。展开后没有「初始化超时/未完成 PD 合同」，无 PDO
列表，footer 保留。浏览器设为 Honolulu，仍正确保留板端 UTC 时间。
1280px/390px 均无横向溢出，无 pageerror；完整截图为
`logs/pdcard/live-s3-desktop.png`、`live-s3-390.png`，卡片局部为
`live-s3-tile-desktop.png`、`live-s3-tile-390.png`。

## 恢复与边界

窗口 finally 已从备份恢复四个文件；原历史文件不存在，预置记录已删除。
不重启 PD 服务，不再次重启系统。恢复输出：

```text
HID_RESTORED_PASS
BASELINE_RESTORED 3ed254bfa838ab50732fdce1c5134400a1663fd5
```

`logs/pdcard/baseline-restored.json`：内核 `7.3.0-vim4kvm-uhd1+`、上述 build ID、
one-kvm/manager 均 active、UDC configured；四个恢复文件的哈希逐项等于窗口前。
manager SHA256 为 `ad7b8aa3e068cb4f5e4ef8e8c2fb6df623c791a1c4ed82949e616cd6fd01f67c`
（7a69ced），One-KVM 运行中二进制为
`72db30c07aa2351a27499e06d2ac28ccde3a74e1cb18d0927766a7ba35d37b0d`（382efb70）。
`hid-restored.log` 实际收到键按下/抬起各一次，绝对/相对鼠标、点击、滚轮均通过。
锁已随窗口退出释放。未改 U-Boot、内核、Wi-Fi/P2P 或持久部署锁。

需要再次回退候选时，Mac 持板锁恢复同一备份（不重启 PD）：

```sh
/usr/bin/lockf /tmp/vim4-board.lock ssh vim4 \
  'sudo systemctl stop vim4-manager && sudo tar -C / -xf /var/backups/vim4-pd-warm-carryover-20261022-run2/files.tar && sudo systemctl start vim4-manager && sudo sync'
```

本轮没有冷插拔、没有建立新合同；固件合同和 Linux 成功持久化分支由离线单测覆盖，
未在板上触发。S4/S5 的确切文案和截图使用 Playwright 夹具验证；真实板端只验 S3。
第一轮候选按当时约束未保留部署；第二轮用户明确覆盖此约束，以下版本已保留。

## 第二轮：视觉修正并保留部署

manager 分支仍为 `pd-warm-carryover`，新增提交
`4ea748426935f782cb2bc0a6e724a1e8075c741f`，未推送，工作树干净。
S3 主值改为「5V 3A · 沿用」，S4 主值为「仅 Type-C」，detail 为
「本次未重新协商 · Rp …」。详情、折叠区和 Rp 映射保持原规格。
为保留 S5 完整文案及单行显示，≤400px 时 PD 和开机时长分别占整行。
共用 TrendChart 在完全空白时只显示一条占位文案；「尚未采样」仅用于有实际数据的
图表中尚未覆盖的历史区域。功耗不可用只显示「暂无法估算」。

前端构建、Go 全套、helper 150 项（12 项因 Mac 无 Linux FAT 工具跳过）与
Playwright 通过。Playwright 对 S3/S4/S5 在 390/1280px 下逐一断言文字、主值元素
`scrollWidth <= clientWidth`，覆盖功耗不可用和六图全部空白的单一占位。
日志 `logs/pdcard/r2-browser-tests.log`；截图同目录：

| 内容 | 390px | 1280px |
|---|---|---|
| S3 | r2-s3-390.png | r2-s3-1280.png |
| S4 | r2-s4-390.png | r2-s4-1280.png |
| S5 空 PDO | r2-s5-empty-pdo-390.png | r2-s5-empty-pdo-1280.png |
| 功耗不可估算 | r2-power-empty-390.png | r2-power-empty-1280.png |
| 全部空图 | r2-empty-charts-390.png | r2-empty-charts-1280.png |
| 实际 S4 页面 | r2-live-390.png | r2-live-1280.png |

持锁安装命令：

```sh
/usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/pd-warm-carryover/r2-window.py \
  > logs/pdcard/r2-board-window.log 2>&1
```

安装 manager 二进制、helper、配套板级模块和 runtime；只重启 manager，不重启系统/PD。
脚本仅识别并删除第一轮的精确夹具，保留其他真实历史记录；实际发现文件原本已不存在，
输出 `LAST_CONTRACT_ABSENT`，部署后仍不存在，未预置任何数据。
实际 API 为 flags=208、空 PDO、VBUS=true、无 bootContract/lastContract，页面为 S4。
主值「仅 Type-C」在两宽度下 scrollWidth=clientWidth=83，无浏览器异常。
证据为 `r2-live-api.json`、`r2-retained.json` 与 `r2-hid.log`，实际键按下/抬起各一次、
绝对/相对鼠标、点击和滚轮均通过；One-KVM/manager active、UDC configured，内核仍为
build ID `3ed254bfa838ab50732fdce1c5134400a1663fd5`，One-KVM 运行哈希未变化。

运行中 manager SHA256 为
`3fc215e3de431d1c65e08e62b3179b6329e190d803ab77e89dae3c3d90728eb1`，
Go 元数据 vcs.modified=false。最终输出 `HID_PASS; DEPLOYMENT_RETAINED`。
旧四文件备份为板上 `/var/backups/vim4-pdcard-r2-20261022/files.tar`、本地
`logs/pdcard/r2-backup/files.tar`，SHA256 两端一致：
`4bbaa05d1fab9a663508732c58f26f81337b6b4e9f881f9042ab916b46399d54`。
回退到安装前版本（不重启 PD，不删除之后产生的真实合同记录）：

```sh
/usr/bin/lockf /tmp/vim4-board.lock ssh vim4 \
  'sudo systemctl stop vim4-manager && sudo tar -C / -xf /var/backups/vim4-pdcard-r2-20261022/files.tar && sudo systemctl start vim4-manager && sudo sync'
```

本轮未重启或重新协商；真实合同将在之后启动确认时自动写入。S3 用离线夹具验收，
没有在第二轮板端预置 S3。主仓改动未提交，未改变任何来源锁文件。
