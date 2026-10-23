# 2026-10-22：手动 PD 协商合同持久化

修复已部署保留。Mac 2026-10-22 的窗口对应板端 UTC 2026-10-23 04:00；
手动运行 `/usr/sbin/usb-pd-init` 实际完成 5V/3A 合同并写入历史，随后真实 HID 通过。
没有预置合同、重启系统、刷写 U-Boot 或安装内核／应用；部署锁文件不变。

## 调用链与修复

原入口：`vim4-kvm-pd.service → vim4-board-runtime pd → vim4pd.py`。
7.3 按固件快照作一次判断，5.15 使用 `--vendor`；两者调用同一个 C 工具。
此前只有 Python 包装器解析 C stdout 并保存 Linux 合同，手动运行 C 工具绕过保存。

现在 C 工具成功完成有限协议服务后，将**最后实际请求的 RDO**交给
`/usr/bin/python3 /usr/lib/vim4-kvm/python/vim4pd.py --remember-linux RDO`。
后续 Source_Capabilities 改变电流时也使用最终值。Python 验证固定 5V 请求编码、
USB comm／No USB Suspend 标志和相等的工作／最大电流（0–3A，不含0），复用原写入器。
开机包装器保留退出状态和日志转发，删除重复保存逻辑；firmware 确认路径继续复用原写入器。

写入为同目录私有临时文件、flush/fsync、`os.replace`；旧记录在失败时保留。
历史字段沿用[原约定](2026-10-22-pd-warm-carryover.md)：voltageV、currentA、usbComm、
rdo、origin、bootId、带板端时区的 establishedAt。没有本次确认或 `--status` 时不写。
记录器失败不改变已成功的 PD 退出状态、不重新协商；I2C fd 不传给 exec 后的记录器。

离线 Python 专项11项通过，覆盖固件与 Linux 优先级、跨启动可见性、1.5A最终值、
非法RDO拒绝、失败原子替换保留旧历史与不重试。Linux C `-Wall -Wextra -Werror`
编译及边界测试通过，覆盖记录器 exec 实际参数、记录器失败／缺失后正常返回。
日志：`logs/small-fixes/pd-c-tests.log`；主仓完整测试见同目录 root-tests.log。

## 持锁部署与真实证据

```sh
/usr/bin/lockf /tmp/vim4-board.lock \
  python3 -u build/small-fixes/pd-window.py \
  > logs/small-fixes/pd-window.log 2>&1
```

只按 `board/install.sh` 的既有编译参数与安装目标更新 C 二进制和 Python 模块，
`install` 到同目录 `.new` 后 rename；未运行会重启 HDMI／gadget 的整个安装脚本，
也未重启 PD 服务。备份为板上 `/var/backups/vim4-small-fixes-pd-20261022/files.tar`，
本地 `logs/small-fixes/pd-backup.tar`；候选编译位于 VM，未重型构建或同时采样。

锁内实际运行 `ssh vim4 'sudo /usr/sbin/usb-pd-init'`，输出：

```text
Request rdo 1304b12c: tx 0
42 rx hdr 0d66 ctrl 6 n 0
PD bootstrap complete; USB-capable 5V contract established
PD contract at bootstrap: 5000mV 3000mA
PDO1 2e01912c type 0 5000mV 3000mA usbcomm drswap
```

真实文件 `/var/lib/vim4-kvm/pd-last-contract.json`：

```json
{"voltageV":5,"currentA":3.0,"usbComm":true,"rdo":"1304b12c","origin":"linux","bootId":"4c9f3ff2-a2a0-495c-9268-f7ef48bf2731","establishedAt":"2026-10-23T04:00:49+00:00"}
```

写入后核对记录 bootId 等于运行中 bootId；UDC `configured`。
`tools/one-kvm-usb-check.mjs --exclusive --hid-only` 的 Mac 原生窗口实际收到
键盘按下／抬起各1次，绝对／相对鼠标、点击、滚轮通过，输出 `HID_PASS`。
证据：pd-manual.log、pd-hid.log、pd-before.json、pd-retained.json、pd-window.log。

窗口结束：内核 `7.3.0-vim4kvm-uhd1+`，build ID
`3a61b75bccf8c46e9411dee92928999884bbfc7f`，taint=0；one-kvm／vim4-manager active，
运行二进制 SHA256 分别仍为 `72db30c07aa2351a27499e06d2ac28ccde3a74e1cb18d0927766a7ba35d37b0d`、
`3fc215e3de431d1c65e08e62b3179b6329e190d803ab77e89dae3c3d90728eb1`。
输出 `PD_RUNTIME_RETAINED` 后释放板锁。5.15 未切换上板，走同一 C 成功入口由离线验证覆盖。

需要回退这两个运行时文件时持板锁执行以下命令；保留之后产生的真实合同，不重启 PD：

```sh
/usr/bin/lockf /tmp/vim4-board.lock ssh vim4 \
  'sudo tar -C / -xf /var/backups/vim4-small-fixes-pd-20261022/files.tar && sudo sync'
```
