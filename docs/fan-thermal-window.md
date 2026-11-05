# 风扇集成候选窗口准备

本页为窗口操作步骤；实际执行与未验边界见[上板记录](bringup/2026-11-05-fan-thermal-adaptive.md)。
只接收集成构建者给出的**生产 RAM 包**，
不使用fan-thermal工作树自建Image，也不重编集成内核。入口为
[fan-thermal-check.py](../tools/fan-thermal-check.py)，RAM链复用
[board-window](../tools/board-window)；锁与证明规则见[短窗口](board-window.md)。

## 外部输入与离线校验

协调者提供RAM_PACKAGE（candidate.tar）、RELEASE、SHA256；SHA256必须来自构建者的外部归档证明，
不能先给传输后的未知包现算摘要、再拿该摘要冒充来源校验。

```sh
python3 tools/fan-thermal-check.py prepare --ram-package "$RAM_PACKAGE" \
  --release "$RELEASE" --sha256 "$SHA256" --output build/fan-candidate-plan.json
```

prepare只读归档，复用board-window的完整inventory/逐文件摘要/RAM启动布局校验，
核release和既定恢复基线，再输出候选build ID、源SHA、归档路径和恢复身份。
归档格式不含内核配置，生产/调试身份须与构建者的生产构建收据对应，不能仅凭release名字判断。
包到手后才执行，不能用合成测试夹具充当候选。
板测各phase必须带此plan，运行release/build ID不符立即拒绝。
温度JSON记录plan、运行身份、角色、实际采样时长、六区温度、cpufreq cooling状态和频率/策略。

## manager来源、构建与临时安装

本轮已fetch origin/main并确认它是manager fan-thermal的祖先；分支仅多两个风扇提交。
实际SHA见任务结果。构建前再次fetch并做祖先校验；若main推进导致不再包含最新main，先离线整合并验证，
不能在板窗内rebase。构建须在板窗外完成。

协调者放开heavy后，通过队列构建Ubuntu ARM64组件（包含嵌入前端）：

```sh
tools/board-queue run --heavy --who fan-thermal --purpose manager-package -- \
  python3 tools/ubuntu-build.py package --component manager
```

保留输出目录的sources.json、builder身份、包SHA256；从实际输出的manager deb解包，
取`opt/vim4-manager/vim4-manager`与`usr/libexec/vim4-manager-helper`。
用file确认ELF为AArch64，记录二者SHA256和manager源SHA。
此处不安装deb、不升级NAS/服务单元/其他组件；本任务只改这两个运行文件和嵌入的UI。
配置、sudoers和unit仍用板上原件，必须在窗口预检其与新helper/命令接口兼容；不兼容则中止并离线准备。

窗口内先捕获原manager二进制/helper的真实文件哈希、服务unit/override、服务活动状态，
并保存独立的original-manager-proof，返回后逐项核验。外部RAM包可能已固定baseline_files；
不得为了追加manager路径改写包内清单或改变其来源SHA。board-window首次proof仍须完整匹配该清单。
记录原风扇L/M/H、配置是否存在及其内容。
不以origin/main的重编译产物冒充“原manager”，不备份无关凭据或整个应用数据目录。

候选RAM启动后上传新二进制/helper到私有临时目录并核SHA256，
仅临时bind覆盖（以下以`/run/fan-thermal-manager/`为例）：

```sh
sudo -n systemctl stop vim4-manager
sudo -n mount --bind /run/fan-thermal-manager/vim4-manager /opt/vim4-manager/vim4-manager
sudo -n mount --bind /run/fan-thermal-manager/vim4-manager-helper /usr/libexec/vim4-manager-helper
sudo -n systemctl start vim4-manager
```

核MainPID、`/proc/PID/exe`及helper摘要、新UI/API、六区统一锚点读回；只重启manager，
不重启HDMI、gadget或KVM后端。绑定前后保存服务InvocationID等证据。
stop或任一mount/start失败立刻清理已完成的bind、启动原manager并停止本次测量，不能继续温度验收。
同一窗口内临时回原manager时，执行以下逆序步骤并核原哈希；安装失败时只卸载已成功完成的bind：

```sh
sudo -n systemctl stop vim4-manager
sudo -n umount /usr/libexec/vim4-manager-helper
sudo -n umount /opt/vim4-manager/vim4-manager
sudo -n systemctl start vim4-manager
```

所有覆盖均为RAM mount，正常回到.3的重启会消除它们，不改磁盘上的原manager。

## 窗口顺序与相同负载

1. 在正式.3上捕获首次baseline-proof，确认默认启动仍是.3，release/build ID符合plan的baseline。
   board-window补齐正式内核/模块/启动文件证明；原manager二进制/helper另存证明并在返回后独立核验。
   同时保存原风扇配置（含不存在状态）、实际L/M/H、CPU governor/min/max和环境温度。
2. 固定一个常见负载：One-KVM、3840×2160@60Hz运动源、H.265、30Mbps请求，保持原音频状态，
   不做音频验收或HID操作。若现场不能维持该负载，先记录双方都能复现的替代参数，不能中途换codec/源。
   原manager+旧曲线和新manager+阶梯使用相同L/M/H，确认实际读回，不能一边用出厂值、一边用保存的自定义值。
3. receiver持续覆盖整个自适应预热和采样；两侧使用相同接收机、浏览器及参数。
   至少预热180秒后，每分钟检查最近连续五个完整分钟组，六区均温最大差均≤0.5°C即停止采样，
   使用首次达标的五分钟作为测量窗。最早第8分钟、第15分钟为最后一次检查；单侧总上限900秒。
   温度按monotonic时间分组，不把60条略慢于1Hz的记录直接当一分钟。
   完整早期记录保留，已声明的预热部分不计入两组最高温比较；不删除所选五分钟里的前段。
   receiver异常或单侧到上限仍未稳定立即停止整个测量。采样期间保持sampling独占。
   保存源/应用/编码参数和实际解码推进报告；无接收客户端的静态待机不能冒充常见推流负载。
4. 按顺序完成baseline采样、外部RAM启动、manager临时安装、同负载candidate采样。
   不重编/封装/修改外部内核包，不在板上重新生成SHA当信任来源。

本机未来调用RAM入口（所有调用在同一已授权板票与WINDOW内）：

```sh
tools/board-window --host "$HOST" --window "$WINDOW" boot-candidate "$RAM_PACKAGE" --sha256 "$SHA256"
```

复用同WINDOW已捕获、与外部包baseline_files一致的proof，并保留独立的原manager证明。
如果轮到本任务时已经在集成候选上，只有同日、同身份、同设置且含六区稳定温度的.3基线可复用；
其他任务的普通视频冒烟不是温度基线。没有合格温度基线则先回.3，额外启动成本须计入30分钟预算，不能省掉对照。

将脚本按`tools/fan-thermal-check.py`、`board/vim4fan.py`的相对目录上传到私有临时目录，
再上传fan-candidate-plan.json；无需永久安装板级Python模块。以下相对路径在该临时目录执行：

```sh
sudo -n python3 tools/fan-thermal-check.py sample --exclusive --candidate-plan fan-candidate-plan.json \
  --role baseline --ambient "$AMBIENT" --workload "$WORKLOAD" --output baseline.json
sudo -n python3 tools/fan-thermal-check.py sample --exclusive --candidate-plan fan-candidate-plan.json \
  --role candidate --ambient "$AMBIENT" --workload "$WORKLOAD" --output candidate.json
```

这两个命令分别在.3和集成生产候选上执行，不能在同一个启动上直接连续执行。
WORKLOAD是同一组公开源/参数/接收机/风扇锚点身份。环境温度差必须≤1°C。
script只采样，不负责启动视频；外层窗口必须同时监督receiver，任何一边失败就收尾。
JSON保留完整readings、每次检查checks、起始monotonic及最终measurement边界；比较端重算首次达标窗口，
不盲信stable字段。不能只看最后两分钟或不足五分钟的尾部，未稳定保留数据并判对照无效。
到15分钟没有达标则写出全部记录后失败，不能追加采样。基线和候选都执行完全相同的规则。

取回JSON后离线比较：

```sh
python3 tools/fan-thermal-check.py compare --baseline baseline.json --candidate candidate.json
```

判据保持：最高温相对基线增加≤3°C，常见负载两组CPU均<85°C，无新增降频。
脚本比较cpufreq cooling状态；同时审查采样中的实际频率、governor/min/max及journal热事件，
排除双方策略不同、负载未推进和热关机。设置/负载不一致的数据不能验收。

## 恢复.3与原manager

成功/失败都给恢复留预算。先清emul_temp、停止本任务receiver，恢复原风扇锚点和配置文件（含原先不存在的状态）。
panel phase有finally恢复，若实际网页也应用过设置，同样须读回原值及核配置内容。
然后只正常重启一次：

```sh
tools/board-window --host "$HOST" --window "$WINDOW" return-baseline --video-check "$VIDEO_CHECK"
```

VIDEO_CHECK是预先准备的原应用真实解码推进可执行脚本路径（不是包含空格的shell复合命令）。board-window按首次proof校完整原内核/模块/启动文件、
清单内文件哈希，并执行视频检查；不能用systemctl active代替真实推进。
原manager应在重启后自动启动，核原二进制/helper哈希、服务MainPID及页面/API、原L/M/H和配置文件，
确认无残留manager bind且实际release/build ID为plan baseline（当前为.3），保存returned-baseline-identity.json。
若正常返回或manager恢复失败，不循环重启/重绑，保存UART、proof及具体恢复交接，交协调者处理。

## 时长预算

| 阶段 | 预算 |
|---|---|
| .3身份/原manager/配置proof、负载参数核对 | 1.5–2分钟 |
| .3相同负载自适应预热、稳定五分钟测量窗 | 8–15分钟 |
| 外部RAM启动与服务/身份核对 | 1.5–2分钟 |
| manager临时bind安装、UI/API/锚点核对 | 0.5–1分钟 |
| 候选同负载自适应预热、稳定五分钟测量窗 | 8–15分钟 |
| 回.3、原manager/配置/视频恢复验证 | 2–3分钟 |
| 故障及收尾预留 | 2–3分钟 |
| 合计 | 约22–41分钟；本轮协调者明确批准整窗上限50分钟 |

完整温度对照本身不适合承诺15分钟。若基线/候选任一到15分钟未稳定、启动耗时超预算，
在剩余恢复预算不足前停止；不延长到50分钟以外、不把未稳定数据当通过。
本轮使用`board-queue run --max-min 50`，排在kunit-migration补测之后；默认板窗仍为30分钟，
不能据此次授权延长其他任务。收尾至少预留五分钟，不因额度尚未用完而首错重试。
逐trip仿真、面板交互、系统睡眠等现有phase保留，但不默认挤进本次温度窗口；需协调者选择范围并重排总预算。
构建、包校验、上传准备、恢复命令审阅均在占板前完成。
