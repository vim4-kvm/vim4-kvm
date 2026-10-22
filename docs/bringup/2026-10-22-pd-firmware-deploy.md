# 2026-10-22：U-Boot PD 交接刷写与双内核验证

摘要：用户第二轮明确授权刷写并接受启动失败需现场 FUNCTION+RESET 进入 OOWOW
恢复的风险。新 U-Boot 已保留，默认 7.x、串口菜单 Stock 5.15、再回默认 7.x 三次
启动成功，固件属性与各次串口完全一致。三次固件均为 PD 超时回退、Rp 3A，未取得
成功固件合同，不能把本记录作为成功合同/完整 PDO 列表的实板验收。
5.15 Linux 后续协商 5V/3A，候选 API/页面优先显示 Linux；管理器验证后恢复 b1e49a8。
最后重启确认基线内核 build ID `52d5e46…`、manager active。双锁已释放。

## 版本与最终镜像

实现及离线测试见 [第一轮记录](2026-10-22-pd-firmware-handoff.md)。没有更改 PD 选择、
Request、I²C 操作与协商时序；本轮只重建已提交版本并验证部署。

- U-Boot：分支 `vim4-kvm-2019.01-edge-pd-handoff`，提交
  `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`，基于板上对应 `4317387a6a58`。
  VM 工作树 `/home/deepdream/src/u-boot-pd-handoff`，独立 O= 和 BL33Z BUILD_BASE。
- 管理器：分支 `pd-firmware-handoff`，提交 `6c3220c69fefbec91d39f1c1186ad5faa8ef24d7`。
  工作树 `build/pd-handoff/manager`，基于 b1e49a8；两个子仓库均未推送。
- 串口实际版本：`U-Boot 2019.01-00006-g0d5a3d7848 (Oct 22 2026 - 16:40:49 +0800)`。

最终完整镜像 3,248,640 字节：

```text
SHA256 3ddfc405d283e5cc645382c5c00b4e8ddc261361825e721f5e7e87492dd30bab
Mac build/pd-handoff/u-boot.bin.sd.bin.signed
VM  /home/deepdream/build/u-boot-pd-handoff-candidate/u-boot.bin.sd.bin.signed
```

重建受 `/usr/bin/lockf /tmp/vim4-heavy.lock` 保护，使用 VIM4.md 的 GCC 12 参数，
重打包命令为：

```sh
python3 tools/vim4-repack.py \
  /Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/build/kernel-edge/boot-input/u-boot.bin.sd.bin.signed \
  /home/deepdream/build/u-boot-pd-handoff-candidate --update-bl31
python3 tools/test-vim4-pd-handoff.py
```

固定 stock 输入 SHA256 `95547c4cd3624fab11ff118668bd15d1497aef8c8339049c714566bb63adadee`。
打包/签名完成，主机事件/FDT 测试通过；相对原 edge 镜像，大小、FIP 布局、FIP 前全部
字节一致，BL30/40/31/32 载荷逐字节未变，只有 FIP 元数据与 BL33 改变。
日志 `logs/pd-handoff/round2-build.log`，清单 `build/pd-handoff/image-verification.json`。

## 锁、备份与刷写

阻塞等待 HDMI 会话，不抢锁：

```sh
/usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/pd-handoff/window.py
```

首次获锁后的 SSH 查询超时，窗口未执行板上改动即退出。只读复查随后恢复可达，
重新取得双锁，解析 `/sys/kernel/notes` 得到基线 ID 后才继续；没有恢复 HDMI 候选。
刷写、管理器替换、串口菜单选择、全部重启与验证全程持双锁。
实际输出：

```text
LOCKED baseline_probe=52d5e46fb006230785110a1fa5ba0dd1383b732f
READY: both locks held; commands use JSON argv/log
```

布局确认根分区 `/dev/mmcblk0p2`、第一分区从 sector 32768（16MiB）开始、
eMMC 可写、虚拟介质未挂载。备份前 16MiB、独立原 FIP、管理器/helper、extlinux，
先 fsync，再从板上复制到 Mac，所有二进制逐哈希复核后才打开设备写入：

- 板上：`/var/backups/vim4-pd-handoff-20261022/`。
- Mac：`build/pd-handoff/round2-backup/`（仓库根目录下，忽略文件）。
- `emmc-prefix-before.bin`：`dc451cd70b6c40d5919183d7cd0c393e1bed6d98f7126864f367e4442072ad33`。
- `device-fip-before.bin`：`0bdd6f6925c7def039c7c9fa7abdfbf8a07b17cf7a687d7e4131cfd4b2b3edb5`。

临时脚本 `build/pd-handoff/board.py` 的 backup/flash 操作分别在基线下再核对布局。
flash 再确认整段前缀未被其他任务修改，只向 eMMC 偏移 672256（sector 1313）写入
2,576,384 字节（5032 sectors），不写 MBR、前级启动代码或分区表。
fsync 后读取完整前 16MiB，与原备份仅替换 FIP 后的期望值比较。
本地模拟的通过日志不算硬件证据；以下来自真正的板上写入：

```text
FLASH_VERIFIED {"imageSHA256":"3ddfc405d283e5cc645382c5c00b4e8ddc261361825e721f5e7e87492dd30bab",
 "fipSHA256":"751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0",
 "writtenOffset":672256,"writtenLength":2576384,
 "full16MiBReadback":true,"outsideFIPUnchanged":true}
```

见 `round2-backup.log`、`round2-mac-backup.log`、`round2-flash-mainline.log`，均在
`logs/pd-handoff/`。板上和 Mac 都保留 `device-fip-after.bin`；最终再次读取设备核对一致。

## 双内核与实际页面

使用 `tools/uart-run.py` 的 open_port，以 921600 打开 `/dev/cu.usbserial-100`，
从写入之前开始记录。每次只执行一次 `sudo systemctl reboot`；Stock 在检测到
`Enter choice:` 后发送菜单号 2，没有改 extlinux 默认项。命令与记录：

```sh
python3 build/pd-handoff/uart-reboot.py default logs/pd-handoff/round2-mainline-uart.log --flash
python3 build/pd-handoff/uart-reboot.py stock logs/pd-handoff/round2-stock-uart.log
python3 build/pd-handoff/uart-reboot.py default logs/pd-handoff/round2-final-uart.log
```

三个串口日志中都只有一组以下快照；无 Source PDO 行：

```text
fusb302_init: Device ID: 0x91
CC connected in 0 as UFP
PD boot: flags=d0 source=0000 request=0000 rdo=00000000 rp=3 policy=0mV/0mA
```

`d0` 表示 sink 已附着、超时、退出时没有确认的 PD；未记录硬复位、请求失败或
I²C 错误。Rp 3 是附着时 3A 档，不是 PD 合同或实际用电。
三次 `/proc/device-tree/chosen/khadas,usb-pd-boot` 均为 64 字节：

```text
[1,208,0,0,0,0,3,0,0,0,0,0,0,0,0,0]
```

比较器仅检验实际 UART 与属性是否一致，不要求或伪造 PS_RDY。三次结果均
`UART_FDT_MATCH / all16CellsEqual=true / psReady=false / typecFallback=true`。

| 启动 | 内核与证据 | 结果与限制 |
|---|---|---|
| 首次默认 | 7.3.0-rc7-vim4kvm-uhd1+，ID 52d5e46… | 属性/串口一致，基础健康检查通过 |
| 菜单 Stock | 5.15.137，ID a30469fc9777705734f513af53c0275447c8ce7f | 属性/串口一致；Linux PD 随后成功；完整 KVM 检查失败 |
| 最后默认 | 7.3.0-rc7-vim4kvm-uhd1+，ID 52d5e46… | 属性/串口一致，恢复后健康检查通过 |

Stock 的 `/lib/modules/5.15.137` 缺少 `vfm_cap`，HDMI 服务反复报 modprobe 失败，
One-KVM inactive；`tools/board.py check --kernel 5.15.137` 失败，未修模块或服务。
其内核 taint=8704，不能写作零 taint/完整健康通过。内核启动、SSH、manager、USB gadget
及 PD 初始化可用；这不是该内核无法启动，也不是完整双内核 KVM 验收。

候选 manager/helper 在首个 7.x 下临时替换，随后跨 Stock 验证；没有安装新 deb 或
修改包数据库。候选二进制 SHA256 `0426c96a6d72c0da318782a75777eb460d633241ed92d832df87b06b3af005e3`，
helper SHA256 `3713572c172c7e6dd13ced32e4cee52af259d55d781b01768cad31b78b8c18d9`。
真实登录后的 `/api/status` 和页面（非 mock）验证：

- 7.x：`bootContract=null`；固件超时回退、Rp 3A、合同 null、来源列表空；页面显示
  「Type-C · 无确认的 PD 合同」「启动固件 · Rp 3A」「初始化超时」。
- 5.15：Linux 日志包含 `PD bootstrap complete; USB-capable 5V contract established`、
  `PD contract at bootstrap: 5000mV 3000mA`、`PDO1 2e01912c`；API 的 Linux
  `bootContract={voltageV:5,currentA:3}`，页面主值「5 V / 3 A」「Linux 初始化」，
  展开仍可看固件未完成合同，来源能力 0 项，没有混用 Linux PDO 充当固件来源能力。
- 两种内核分别检查 1280px 和 390px，无横向溢出、无页面异常；截图人工复核。
  日志/API/截图为 `round2-mainline-*`、`round2-vendor-*`，在 `logs/pd-handoff/`。

## 恢复与保留

在 Stock 下将 manager/helper 原子替换回备份，哈希一致后才最终重启默认 7.x。
最后实际输出（`round2-final-proof.log`、`round2-final-status.json`）：

```text
FINAL_BASELINE_AND_FIP_VERIFIED
buildID: 52d5e46fb006230785110a1fa5ba0dd1383b732f
managerVersion: 2.5.1+vim4.20261018.44.dev.2.gb1e49a8
managerHashesMatch: true
manager / one-kvm / vim4-kvm-hdmi / vim4-kvm-gadget / vim4-kvm-pd: active
UDC: configured; taint: 0; failedUnits: empty; extlinuxUnchanged: true
```

manager 原 SHA256 `4494f89ce85ef8da13c6dd07b7aca0e9d397aba054b594357b920ab1107ffea7`，
helper 原 SHA256 `f64159d4b7a7a7e0627b8119cea32ac9ddd6b518144ea6a1dedee1117bcdb917`。
Image SHA256 `7b8607b2c24b7a1f41a2670770dea07a813a2773c36902e9527dcd4c131bc784`，
DTB SHA256 `e0ebe345dba968f811136de69412cc58846814775ce4d4f3ac440ee5d32961c5`，与指定基线相同。
最终 `tools/board.py check --kernel 7.3.0-rc7-vim4kvm-uhd1+` 通过；这是基础服务/设备/HTTP
检查，不含视频内容、音频、键鼠输入或性能。HDMI 无输入，dmesg 有 ASoC `-67`，不称日志无错误。
本轮不改内核、模块、EDID、启动项或 Wi-Fi/P2P。管理器现网仍是旧版，待用户合并部署。

新 U-Boot 已证明两条内核路径能启动，按授权保留。需在板子可启动 Linux 时回退，可按
下面的 FIP 恢复命令执行；本轮没有实际回刷旧固件。执行前仍须独占双锁、确认没有别人
的候选且运行指定基线 ID，并打开串口；读回失败不得重启。不要写完整镜像或前 16MiB：

```sh
# 仅在已有双锁持有窗口内执行这个恢复阶段片段
ssh vim4 'sudo sh -s' <<'SH'
set -eu
b=/var/backups/vim4-pd-handoff-20261022/device-fip-before.bin
old=0bdd6f6925c7def039c7c9fa7abdfbf8a07b17cf7a687d7e4131cfd4b2b3edb5
new=751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0
test "$(stat -c %s "$b")" = 2576384
test "$(sha256sum "$b" | cut -d ' ' -f 1)" = "$old"
test "$(dd if=/dev/mmcblk0 bs=512 skip=1313 count=5032 status=none | sha256sum | cut -d ' ' -f 1)" = "$new"
dd if="$b" of=/dev/mmcblk0 bs=512 seek=1313 count=5032 conv=notrunc,fsync status=progress
test "$(dd if=/dev/mmcblk0 bs=512 skip=1313 count=5032 status=none | sha256sum | cut -d ' ' -f 1)" = "$old"
sync
SH
```

随后仍在同一持锁窗口、保持串口记录执行一次重启并确认恢复版本。以上片段不负责获取
锁，不能从未持锁终端直接运行；外层锁须跨越基线核对、恢复、重启与恢复后确认。
若已无法启动 Linux，则 SSH 回退不可用，需现场 FUNCTION+RESET 进入 OOWOW；该失败
恢复路径本轮未实测。Mac 备份可供现场恢复核对，不能把其有副本等同于恢复已验证。

## 剩余验收

未取得固件成功 PS_RDY/Source PDO 的实板样本；成功合同、PDO 列表、其它 PDO 类型、
硬复位/失败分支目前只有第一轮主机/浏览器模拟测试。没有为获得合同而调整协商行为、
重置控制器或反复重启；没有冷启动、换充电器/线缆及长期/功耗验证。
Stock 缺模块的完整 KVM 故障未修；不扩大本任务修改范围。
主仓库最终 `python3 -m unittest discover -s tests -p 'test_*.py'`：147 项，5 skipped，OK；
日志 `logs/pd-handoff/round2-final-tests.log`。U-Boot host 测试也通过；管理器代码未再变动，
其完整单元测试与构建结果见第一轮记录，不把那些离线结果替代本页尚缺的实板成功合同。
