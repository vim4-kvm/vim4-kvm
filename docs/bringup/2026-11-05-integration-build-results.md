# 2026-11-05：集成候选构建与 KUnit 复验

集成源码固定为 `fd41fb5950b9da1fb336ce00d5137d27ee9755fa`，工作树
`/home/deepdream/src/linux-7.3-integration-73`，由协调者通过 tools/vm 登记。
所有编译、封包和运行验证走 board-queue heavy，不访问板子、不排板窗。
两套构建及独立完整 RAM 复读通过；同 SHA 的 QEMU 组合复验尚待完成。

## 输入与构建过程

复用唯一 `O=/home/deepdream/build/integration-73`。生产从入库 kernel.config
生成并逐字节核对，调试合入 vdec-debug.config；两个配置均关闭 KUnit 和函数错误
注入，调试配置实际保留 KASAN/PROVE_LOCKING/DMA-API/kmemleak/atomic-sleep 检查。
日期和构建号按协调者指定；不更新正式来源锁、不创建 tag、不改变默认启动项。

正式 `.3` 完整 proof 从原主仓库 `build/hwdecode-parity/run30/baseline.json`
只读取得，复制到本工作树 `build/kunit-migration/integration-73/baseline.json`。
SHA-256 为 `6133ef90e9c89ca84c9d871925ab29be1ba4417c84c7249d1d496fa9be1e325d`；
2370 个保护文件中的 Image/DTB 与入库发行收据一致，build ID 为
`e595ad243d663f6c33b92678a4de6e0b78ec16d5`。MAC 取同 proof 的
`vim4.eth_mac=c8:63:14:74:70:0d`，没有为取输入连接板子。

[构建入口](../../packaging/kernel/build-integration.py)调用过程：

1. 原双配置调用在生产对象编译期间主动停止：发现静态 init 漏传 RELEASE/TRIAL_ROOT。
   主仓库 `a113d86` 修正，之后在 heavy 下实际编译 ARM64 静态 init，ELF、release、
   namespace 检查通过。确认并终止自己遗留在 VM 的 make 及子进程后才继续，没有无锁编译。
2. 再次调用完成生产 Image/dtbs/modules 和三个外部模块构建，但封包门禁返回失败：
   此内核 modules.order 是 `.o` 路径，工具未转换 `.ko`；两侧实际各有 2338 项。
   `931bdf2` 修正归一化，并提供单配置分票及仅续封包入口；保留原失败输出。
3. 使用相同 SHA、O=、生产构建号调用 `--profile production --package-only`，先核
   保留构建/外部模块/DTB 哈希，再安装并核对完整模块、生成 RAM 包。该次 exit 0。
4. 新 heavy 票调用 `--profile debug`，仍传生产起始构建号，由入口选择调试号。
   两套候选封存后才运行独立 RAM 全量校验；同一 SHA 的组合 QEMU 排在其后。

前三个阶段不是三次都通过。首次中断和第二次封包失败不能被后续成功覆盖。
生产实际编译输出在候选根目录 production.log，续封包追加在同文件；wrapper
traceback 在本工作树 build-wrapper2.log。原始命令参数以以下实际脚本/日志为准：

- `build/kunit-migration/integration-73/build-wrapper.log`、`build-wrapper2.log`：初次中断与封包失败。
- `production-resume-wrapper.log`：生产续封包命令的退出结果。
- `debug-wrapper.log`：调试调用与后续独立全量 RAM 校验输出。
- `verify-ram.py`、`run-kunit.sh`：独立校验和完整组合运行的实际脚本。
- `main-tests-init-fix.log`、`main-tests-seal-fix.log`：工具两次修正的主仓全测，均543项、14 skipped、OK。

上述文件均在本工作树的 `build/kunit-migration/integration-73/`。
原中断生产编译另保留在 VM `/home/deepdream/build/integration-73-candidates-init-fix-interrupted/`。

## 候选身份与 RAM 门禁

VM 候选根目录为 `/home/deepdream/build/integration-73-candidates`。
每套 RAM 包路径是 `<profile>/ram/candidate.tar`，配套 trial.json、identity.json、
module-identities.json、payload/manifest.json 和完整配置随该候选保存。
DTB 由本次源码的 display-m0 DTB 经原 kbase 入口生成，保留集成温控内容；
三个外部模块按当次 vmlinux/Module.symvers 重建，不混入正式 `.3` 的模块。

| profile | release | Image SHA-256 | GNU build ID |
|---|---|---|---|
| production | `7.3.1-vim4-20261105.90` | `5d9111aa91b95b8df92815399d0f8510ce6e95b09c2255bf95bd20ce4df6ec91` | `6c5ebf0605c190d7670374fb6ea880958f54cba1` |
| debug | `7.3.1-vim4-20261105.91` | `2b1ee80670214b16b6615c529c773c5683487804f5b0aef00678a90f7652e7d2` | `e4ff1425d7fcc6f2ea2dba81f385faef0ff81a3b` |

生产配置 SHA-256 为 `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c`，
RAM 包 SHA-256 为 `83d87c9014e0a7a4160adc84e1e3b19b2548bad566486a28e067c500e04145ad`。
生产封包时已验证 2338 个基础模块与 3 个外部模块的 vermagic、BTF、build ID。
调试配置 SHA-256 为 `16e40afca3bc9019d1c7379268ea23ea36dfbc781444abf45f9cab16b4be47bc`，
RAM 包 SHA-256 为 `1e4fc21fa090869873b25c47f0cdf1987648237e28085ac9e4c83599c7ee879e`。
两套源码 tree 均为 `679a19977b7a877f944d1466a57c6b1e51f17d85`，DTB SHA-256 均为
`7d0cec981171634b44324d152d2850dec3a1b32a36422737b8e1d6b400336ad7`。

独立校验 **PASS**：复读每个归档文件、逐模块解压核身份、比较完整模块集合，
核 Image 内 GNU note、static init、namespace、基线恢复清单和所有 SHA-256。
每套2341模块、2354模块文件、2358个RAM清单文件，完整结果是候选根目录的
ram-validation.json。两套封包后已删除自身10878个`.o`；Image/.ko、包和日志保留。

## 组合 KUnit

当前 SHA 的风扇改动删除了旧策略及其 KUnit（含 drivers/thermal/.kunitconfig），
不恢复已经删除的策略测试。原十一套中当前保留十套驱动测试；增加相关上游
DMA-BUF fence/chain/unwrap/reservation 套件，单列其结果，避免用旧数量假装覆盖仍在。
ADLA 必须实际运行新增 `adla_mutex_roles_test`，不能只验证旧四项。

运行继续复用同一 O=，九份当前配置是 wave5、hdmirx、jpeg、meson DRM、Meson ASoC、
DMA-BUF、ADLA、brcmfmac、PWM。使用 arm64 QEMU，无 suite filter；运行 profile
沿用明确记录的 WERROR=n、generic KASAN 和 PROVE_LOCKING，不改生产配置或提交的
各目录配置。完整命令在 run-kunit.sh，结果仍待执行；不将过去44/44移植为本次通过。

首次单 vCPU、300秒运行超时：解析器报告46项中33 passed、12 crashed、1 skipped，
13 errors。原始KTAP确认 ADLA 五项含锁类用例通过，接着 DMA-BUF fence-chain 未完成；
qemu被工具超时SIGTERM终止，crashed是截断输出的解析标签，不能代替实际Oops证据，
也不能把其余未执行驱动套件记通过。完整失败产物在候选 `kunit/failed-single-cpu/`，
实际脚本另存 `run-kunit-single-cpu.sh`，完整编译/运行输出 `kunit-wrapper.log`。
源码确认竞争测试至少需要两颗在线CPU（首次因此跳过），chain压力4096节点。
随后改为 `--qemu_args '-smp 2' --timeout 900` 重跑相同完整配置，仍待完成；
复用已构建的同SHA测试Image，不改源码、不减少用例。两套RAM包不受此执行超时影响。

## 验证边界

W=1 的全树原始诊断保留，编译退出成功不等于零告警。旧 ADLA/CRG/TCPM 静态失败
按[迁移记录](2026-11-05-kunit-review-rework.md)保留，本轮不冒充重新通过 sparse。
没有驱动源码修改，集成 SHA 不改写；没有做板上标准接口/实流/像素、故障注入或
真实模块加载。ADLA 利用率显示仍需实板回归，PWM 同控制器 ABBA 仍按既有记录保留。
板窗按[生产回归清单](2026-11-05-integration-regression-plan.md)等待协调者通知，
首错即停，结束恢复正式 `.3` 并核对实际视频推进。
离线核对发现旧 edge-jpeg-check 要求 taint 恒为0，正式外置GPU模块已有 OOT taint；
清单已标明该入口限制，改用现有 driver-bench JPEG 路径与资源/数据检查，不放宽旧断言。
