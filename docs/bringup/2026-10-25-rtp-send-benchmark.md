# 2026-10-25：RTP 发送离线基准与板端 CPU 回放

本次研究逐包发送的大帧尾延迟及编码入口到输出的优化空间。生产程序、采集、编码、
时钟与协议配置保持原样；新增独立基准和实验补丁，不能把软件回放结果称为画面延迟改善。

## 方法与复现

[One-KVM 独立基准](../../One-KVM/test/rtp-bench/README.md) 直接编译生产分包器、
video track、WebRTC 0.17.2、默认 interceptor、私有 DTLS fork 及 vendored OpenSSL。
使用 release opt3/LTO/codegen-units1 和生产 AArch64 cfg，保存实际 feature 树、
源码/制品哈希、每帧原始时长及失败状态。输入来自前次 4K60/30Mbps 真实采集码流。
选择接近 38/48/180/220 包的四个 AU；H.264 为 38/48/180/220，H.265 最后为224包。
每 case 预热10帧；报告实际包数，不能把224记作220。

分别测 packetize、track_mock、interceptors_mock、真实 srtp_context、srtp_udp、完整双 peer。
mock 包含计数校验开销，跨层中位数不能直接相减作精确归因。Context/UDP 每个密文都在
计时外解密并比对完整 RTP；固定 key、salt、序号、时间戳还生成密文 transcript SHA256，
供后端候选逐字节等价验证。计时包含帧内工作，读取文件、解密、排空接收队列不计入。

UDP 系统调用单项使用 [rtp-udp-bench.c](../../tools/rtp-udp-bench.c)：

```sh
cc -O2 -Wall -Wextra -Werror -pthread tools/rtp-udp-bench.c -o /tmp/rtp-udp-bench
/tmp/rtp-udp-bench 300 30 > logs/rtp-udp-new.json
```

Linux only；每帧1200字节包，38/48/180/220包，三组轮换 sendto/sendmmsg 8/32/64，
逐帧 barrier、核对全部内容/序号/marker/来源/多余包。计时包括 batch 描述符准备，
不等待后续帧凑批。仅请求私有 SO_RCVBUF，不改系统默认值。

## ARM64 VM 结果

原始分层结果 `logs/rtp-bench-layers.json`：三组、每 case100帧，全部有效。
完整 peer 初始失败保留在 `logs/rtp-bench-peer-pilot*.json`；最终 pilot5 确认缺包数
逐组等于 Linux UDP RcvbufErrors 增量。仅给基准接收端私有 socket 请求4MiB、实际8MiB
后，四组完整 peer 均无缺包/重复/内核drop。该结果不能据此修改生产接收缓冲或推断
Chrome 有相同问题。失败阶段不进入性能比较；发送端未改。

Chrome 真实互通对照使用独立浏览器和文件信令，H.264 四种组合均4K、约60fps，
20秒窗口零丢包/丢帧/freeze、控制 DataChannel open：默认、Server/default、
Server/GCM-only、Server/GCM+CM fallback。只有 GCM-only 实际协商 GCM，其余仍 AES-CM。
单轮30秒发送窗口 GCM 帧内发送均值2.209ms、P99 8.730ms；AES-CM默认1.754ms、
P99 7.010ms。这是互通诊断，非多组性能验收，足以否定“只换角色必然GCM”及当前
“直接强制GCM一定更快”的假设。原始记录 `logs/rtp-chrome-*-h264/`。

三组完整包校验通过的 UDP 单项 `logs/rtp-udp-bench-vm.json` 共15840帧。
220包时 sendto P50为162–165µs、P99为250–252µs；batch32 为111–115µs、
P99 129–141µs。48包时 P50由35–39降至25µs，P99由55–60降至31–32µs。
batch64 相对32收益很小，batch32可作为首个集成候选。此处只测 socket，未含 SRTP/ICE。
最初窗口误与HMAC编译重叠，`logs/rtp-udp-bench-vm-interfered.json` 保留但排除性能结论。

独立 HMAC 实验 `logs/srtp-hmac-vm-round1.jsonl`：RFC2202与跨后端完整标签比较通过。
1200字节×220包，RustCrypto P50/P99=192/217µs，OpenSSL预计算SHA1状态=86/101µs；
每包新建EVP Signer反而357/393µs。现有HMAC已预计算ipad/opad，收益来自SHA1后端，
不能再声称是新加状态复用。首次EVP空key测试被provider拒绝，原失败stderr保留；
空key仍由Rust与低层SHA1互比，实际SRTP的20字节key另完整覆盖。

## 板端回放与候选

板端5.15.137-vim4kvm-hdrdual6，CPU0/1 Cortex-A73，实际CPU特性含aes/pmull/sha1/sha2。
两个测试进程均只设置自身亲和性0,1；既有performance governor、2.208GHz保持不变。
温度约50℃，One-KVM PID83724、HDMI PID1094全程保持运行。源码/制品和上传哈希见
`logs/rtp-board-upload-sha256.{json,txt}`；独立测试文件放私有 `/var/tmp/vim4-rtp-bench.*`。

首次全分层 A/B/A 中，基线两轮 H.264 srtp_udp 缺包使报告失败；接收socket实际仅458752字节，
而非VM的8MiB。`logs/rtp-board-{a1,b,a2}.json`保留作诊断，不纳入性能比较。
C UDP原始窗口也出现220包突发队列溢出，保留 `logs/rtp-udp-bench-board.json`，不采纳其耗时。
没有改系统rmem或生产socket。新工具允许显式 `force-private-buffer`，仅给本测试socket使用
SO_RCVBUFFORCE，需CAP_NET_ADMIN；不足权限直接失败，不自动改设置。它不是生产优化。

为独立验证计算段，原制品用同一组4个真实AU，单独跑Context-only A→B→A；
每窗口三组、每case100帧，三个报告全部complete/valid、failed_stages=0。
四组codec/profile的整个密文transcript跨三个窗口完全一致，覆盖序号回绕；每包解密完整比较通过。
baseline与candidate制品SHA256分别为
`77e02dc4dbfbade5d5fcd2d85842d6bddf75105525f36690805831ffc41121e6`、
`af218b4734c99a63e52934ca788bb88a5e7f71647481c3992d42fbd464924b1d`。
原始文件 `logs/rtp-board-context-{a1,b,a2}.json`，分析 `logs/rtp-board-context-summary.json`。

表中P50/P99单位ms；每项为同一窗口三组共300帧合并的分位数，短窗口P99仅供离线对照：

| Context真实SRTP | 原实现A1 P50/P99 | 候选B P50/P99 | 原实现A2 P50/P99 |
|---|---:|---:|---:|
| H.264 48包 | 0.280 / 0.540 | 0.116 / 0.173 | 0.280 / 0.542 |
| H.264 220包 | 1.341 / 1.683 | 0.565 / 0.908 | 1.347 / 1.733 |
| H.265 48包 | 0.294 / 0.555 | 0.121 / 0.148 | 0.294 / 0.307 |
| H.265 224包 | 1.378 / 1.719 | 0.576 / 0.939 | 1.362 / 1.435 |

GCM为未修改的控制路径，H.264 220包P50依次1.757/1.763/1.761ms，H.265224包
1.777/1.758/1.734ms。候选只改变现有openssl feature下SHA1计算后端；协议、密钥派生、
认证长度/验证不变。补丁保存在
[独立基准](../../One-KVM/test/rtp-bench/README.md#isolated-openssl-hmac-experiment)，
未接入正式依赖；候选上游40项单测通过，含RFC2202及RTP/ROC/SRTCP边界与Rust参考相等。
低层OpenSSL SHA_CTX API有弃用约束，正式采纳应向上游提交可维护实现。

UDP单项在私有socket申请4MiB、实际8MiB后重新测，三组全部15840帧内容与顺序校验通过，
无缺包、重复或错误。`logs/rtp-udp-bench-board-private-buffer.{json,err}`；例：

```sh
sudo taskset -c 0,1 /private/path/rtp-udp-bench 300 30 4194304 force-private-buffer
```

| 板端UDP单项 | sendto P50 / P99 ms | sendmmsg batch32 P50 / P99 ms |
|---|---:|---:|
| 48包，三组范围 | 0.802–0.834 / 0.824–1.202 | 0.403–0.438 / 0.428–0.812 |
| 220包，三组范围 | 3.674–3.866 / 3.714–4.300 | 1.781–1.998 / 1.869–2.670 |

220包逐组P50减少46–54%，P99减少34–51%。batch64有些组更快，有些更慢；32作为首个
集成候选可限制一次提交的工作量。这里含loopback接收端与内核成本，不能加上Context收益
来预测生产发送或端到端延迟。没有进行本轮生产整链路A/B、网卡出线、光学显示或UU验收。

建议先做单一SRTP HMAC后端补丁的正式sender A/B，再引入帧内最多32包的批量UDP接口。
后者要在SRTP认证后、实际ICE选路的socket上提交，保留默认interceptor/NACK、顺序和错误；
只批当前视频帧，尾包立即flush，不等待下一帧。STUN/DTLS/RTCP、音频和HID仍需公平调度。
简单并发write、取消认证、增大MTU或绕过ICE不能替代该实现。两项分别验证后再做组合，
不能从单项基准宣称已消除前次约8–10ms的真实大帧尾部。

## 编码结论

[编码审查](../encoder-fast-packing-audit.md) 核实每帧只等一次完成中断，无固定重试睡眠。
原实测编码入口→输出约12.5/13.3ms，厂商WAIT约12.1/12.9ms，其他API CPU工作约0.27ms。
WAIT包含硬件与IRQ/调度，现有探针不足以继续拆分。库将 lowLatencyMode 设0；可研究
只开bit0的fast packing，但bit1中断会进入当前wrapper不支持分支，不能直接启用。
旧日志的字节数相关性不构成fast packing收益证据；真实收益与画质须匹配库/固件、
固定输入0→1→0→1硬件A/B。本次没有启用该模式或修改编码器。

## 验证与清理

独立基准release构建和23项生产模块测试通过；HMAC候选上游40项测试通过。
C工具以-Wall/-Wextra/-Werror编译，通过默认小样本、非法参数及无权限强制缓冲失败检查。
主仓库259项测试通过（7项按环境跳过）。未推送或部署本轮实验。

UDP超时报告已修正，保留部分raw、失败帧/迭代、实际buffer和内核计数，整轮仍返回失败。
用仅注入本次测试进程的LD_PRELOAD故意丢一个1210字节包，实际验证退出1、failed_stages=1、
warmup失败case的n=0及完整失败记录，见 `logs/rtp-board-failure-injected-all-check.{json,log}`。
此前只拦sendto及仅缩小buffer的试验没有触发丢包，日志保留，未当作失败分支覆盖。
最终测试通过后删除板端私有目录，核对两个生产PID与服务均未变化。
