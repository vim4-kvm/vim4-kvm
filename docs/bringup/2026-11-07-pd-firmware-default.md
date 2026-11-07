# 2026-11-07：正式默认保留固件 PD 状态

**用户决定采用A/B的B状态，正式默认已追加 `module_blacklist=fusb302`，不由Linux接管PD。**
一次自然默认重启通过，未冷复位。仍是正式fd41fb5 / `7.3.1-vim4-20261105`，
build ID `bdbfa439f298e92b5bad092528d11119a974f262`，Image/FDT/模块均未改变。
这是一项持续观察的运行策略，不是已证明冷复位根因或永久解决。[A/B结果及统计边界](2026-11-07-pd-takeover-ab.md)保留。
取消的15次B补测未执行；后续冷复位继续记入tcpm-coldboot-events.csv。

## 唯一参数变更与登记同步

FIFO **1629**、15分钟sampling票，按用户批准备份后原子替换：

- `/boot/extlinux/extlinux.conf`仅Mainline APPEND末尾追加同一黑名单，`${eth_mac}`原样保留。
- `/etc/vim4-kvm/kernels.json`只同步Mainline.boot.APPEND中的同一追加项，JSON其余文本/字段不变。
  否则vim4boot的逐字段登记校验会判该启动项不可用。Vendor记录未改。

板端备份为 `/var/lib/vim4-kvm/pd-no-takeover/adopt-1629/`；主机
`logs/pd-ab/adopt-1629/`保存两文件前后副本及逐字diff。没有saveenv、改FIP、Image、FDT、模块、
服务配置、无线、EDID或Mac输入；未安装新内核或修改正式release。

| 文件 | 变更前SHA256 | 变更后SHA256 |
|---|---|---|
| extlinux.conf | `1f7c7d75ae26faa06f71ac9db2c71f992d0cfe8f0f4246b24fbc8e1f2361b819` | `d2c2b9ac406b871c36dfeb5184ea5728b1b6970ab9eef24fd6489588c87e1ee5` |
| kernels.json | `2fe69efbc75e2393ceca542f18ff4aadf6e85b1b3b979fee45d4ceae5a7c0c9f` | `1ff35302d22081bb555dd4e7cd598bfdb439dc8c166d3f59b1416d919cfe5fa8` |

## 自然启动与新正式 proof

重启前已发BOOT通知，随后只执行一次正常reboot、不打断U-Boot；实际1次Linux启动/0复位。
**87.47秒**完成稳定运行≥60秒及验收，420秒内自然恢复门禁通过：

- `/proc/cmdline`逐字等于原正式参数加黑名单；fusb302未加载，Type-C没有端口。
- `vim4-kvm-pd.service`打印 `PD bootstrap skipped: controller reserved for kernel TCPM`，没有原始I²C回退。
- 以太网SSH、原服务、configured UDC、One-KVM OTG HID backend正常；未发HID。
- 被动3840×2160 **59.56fps**、帧6→304通过。
- 2372保护文件中仅上述2个批准的元文件hash改变，**其余2370逐项相同**；loaded模块身份及DT属性不变。

从本次起，正式基线proof是新的B版本，后续窗口不能拿旧A清单放宽比较。
新旧完整2372清单均入库保留：

- [变更前清单](../../packaging/kernel/releases/7.3.1-vim4-20261105/pd-before-baseline.json)：
  SHA256 `fe7aba419a1a17795f8793a2fcb589ebf16ab0f1d142ef6937deffc17585acd9`。
- [当前正式清单](../../packaging/kernel/releases/7.3.1-vim4-20261105/pd-baseline.json)：
  SHA256 `0514bdab3aac0a0c9f0d9fa63be8df94d50aff533c7890a1608d23bcc9333126`。
- [新登记receipt](../../packaging/kernel/releases/7.3.1-vim4-20261105/pd-installed-proof.json)及
  [sources.toml的retained_runtime](../../packaging/kernel/sources.toml)指向新清单；原installed-proof.json不追改。

原始连续UART、主机时戳分块、runtime.json、video.json、baseline-before/expected/after.json、
written.json与complete.json均在上述主机证据目录。票已释放；本次仍没有物理VBUS观测。

## 部署与候选策略

`register-runtime.py`在Mainline新登记和完整包升级时加入该策略，并同步生成APPEND与登记元数据；
已有模块黑名单合并到一个参数，保留其他模块，避免重复参数覆盖。只识别工具的历史标准profile迁移，
其他管理员自定义参数仍拒绝替换。`promote.py`仅处理Vendor5.15，不改Vendor策略，保留Mainline项。

普通RAM候选由 `display-once.py`加入fusb302黑名单；无线屏蔽变体使用同一工具的合并函数，
保留fusb302和无线模块，避免两个module_blacklist参数互相覆盖。显式ram_baseline_control实验仍复现
其捕获基准，当前正式基准已含黑名单。基线文件清单及其cmdline保留原样记录，不伪造为旧A清单。
历史已封包的候选需另建参数/基线元数据变体并锁新SHA，不能静默覆盖旧证据或直接沿用旧保护清单。

策略验证包括Mainline生成幂等/无线黑名单保留、升级时登记与配置一致且Vendor不变、候选真实tar里的参数、
无线变体合并，以及旧profile和自定义参数拒绝路径；原始离线日志在 `build/pd-ab/`。
616项全套测试通过（17跳过），最终输出 `policy-full-tests-final.log`；新正式proof及receipt引用也核SHA一致。
