# RTP 逐包发送优化审查

本次先区分加密、RTP/interceptor、UDP 交付三个成本，再决定实现方案。离线基准必须复现正式构建的 Cargo features、ARM cfg、包长和帧内包数；单项 HMAC 或 Context 加密结果不能直接当作屏幕显示延迟。本文记录源码审查和复现方法，性能结论以对应原始日志为准。

后续已将单一 HMAC 后端接入 VIM4 构建，见[正式接入与验证](bringup/2026-10-25-srtp-openssl-hmac.md)。下文的上游实现与实验限制保留为该决策的审查依据；批量 UDP 和 GCM 策略仍未变更。

## 正式路径与构建条件

[One-KVM Cargo.toml](../One-KVM/Cargo.toml) 锁定的 WebRTC 系列为 0.17.2，启用 `webrtc/vendored-openssl`。实际 `cargo tree` 已确认它经 `srtp/vendored-openssl` 激活 `srtp/openssl`；不能只根据 feature 名称推断 `cfg(feature="openssl")` 未开启。证据为 `logs/rtp-bench-cargo-features.txt`；[10 月 15 日记录](bringup/2026-10-15-uu-h265-picture-send-stalls.md) 也核实过正式程序的 OpenSSL 后端。本次未读取现有板端二进制或其构建 fingerprint，不能声称重新证明了当前运行制品的全部构建参数。

SRTP 的 OpenSSL 分支只替换 AES 运算，AES-CM 的认证仍经过共同的 RustCrypto `Hmac<Sha1>`。因此“OpenSSL AES 已启用”和“SHA1 仍为软件实现”可以同时成立。源码：[SRTP feature 定义](https://docs.rs/crate/webrtc-srtp/0.17.2/source/Cargo.toml)、[AES-CM 公共认证](https://docs.rs/crate/webrtc-srtp/0.17.2/source/src/cipher/cipher_aes_cm_hmac_sha1/mod.rs)、[OpenSSL cipher](https://docs.rs/crate/webrtc-srtp/0.17.2/source/src/cipher/cipher_aes_cm_hmac_sha1/opensslcipher.rs)。

[One-KVM/.cargo/config.toml](../One-KVM/.cargo/config.toml) 为 AArch64 设置 `aes_armv8`、`polyval_armv8`；RustCrypto AES/Polyval 后端运行时检查 CPU 特性并保留软件回退。这些 cfg 不能加速共同的 SHA1。本次板端 `/proc/cpuinfo` 核0为 Cortex-A73，实际暴露 `aes pmull sha1 sha2`，见 `logs/rtp-board-baseline.txt`；未取得反汇编证据，不能仅从 CPU 型号推断特定库已执行这些指令。

标准 VIM4 构建使用 release（opt-level 3、LTO、codegen-units 1），不是 release-static 的体积优先设置。独立基准要从 `One-KVM` 或其子目录执行 Cargo，确保载入该仓库 `.cargo/config.toml`；仅从其他目录传 `--manifest-path` 不保证载入它，环境变量 `RUSTFLAGS` 也可能覆盖配置。重现时保存以下内容：

```sh
cd One-KVM
cargo tree --locked --features vim4 -e features -i webrtc-srtp
cargo tree --locked --features vim4 -e features -i sha1
```

还需保存 rustc 版本、目标架构、完整构建命令和实际 rustflags。10 月 15 日的 RustCrypto-only 初版基准曾与正式 OpenSSL features 不一致，其性能变化不能归因给正式程序。

## 每包做了什么

| 层级 | 源码行为及归因边界 |
| --- | --- |
| 应用 RTP | [video_track.rs](../One-KVM/src/webrtc/video_track.rs) 完成 H.264/H.265 分包后，按帧内顺序逐包 await `write_rtp_with_extensions`。H.264 状态锁覆盖该帧发送；不能在未测锁竞争前把持锁时间全部算作锁开销。 |
| Track | [TrackLocalStaticRTP](https://docs.rs/crate/webrtc/0.17.2/source/src/track/track_local/track_local_static_rtp.rs) 创建 Attributes、复制包结构及绑定 Arc 列表，逐绑定调用 writer。`Bytes` clone 通常共享载荷，不等于每层深拷贝整个视频包；空 HashMap 也不等于一定分配堆内存。 |
| Interceptor | [默认注册](https://docs.rs/crate/webrtc/0.17.2/source/src/api/interceptor_registry/mod.rs) 包括 NACK、RTCP report 和 TWCC 接收端。NACK 缓存及 report 计数涉及锁/包结构 clone；默认没有 TWCC 发送端，不能把其发包扩展成本列为当前瓶颈。 |
| SRTP 入口 | [SrtpWriterFuture](https://docs.rs/crate/webrtc/0.17.2/source/src/rtp_transceiver/srtp_writer_future.rs) 取得 session 并维护序号变换；[Session](https://docs.rs/crate/webrtc-srtp/0.17.2/source/src/session/mod.rs) marshal RTP、锁定 context、加密，再调用底层 send。 |
| 认证和发送 | [Context](https://docs.rs/crate/webrtc-srtp/0.17.2/source/src/context/srtp.rs) 再解析已 marshal 的 RTP 头；cipher 生成认证后的输出，经 ICE/UDP 发出。这里有输出缓冲、加密/认证、锁和每包系统调用成本，不能只靠源码给出各自百分比。 |

建议保留真实分包和 interceptor 的基准，以同样的包流比较：Context-only、真实 SRTP+loopback、完整双 peer。固定主/次核、协议和运行顺序，交错重复 A/B，记录帧内首包到尾包及 p50/p95/p99；接收端还要检查序号、marker、解密和 payload 一致。loopback 完成表示软件链路交付，不表示网卡出线、浏览器解码或显示完成。

## SHA1：已有状态复用，候选是后端

`CipherInner::new` 为 RTP/RTCP 各创建一次带密钥 HMAC；每包 clone 已初始化状态，输入认证包和大端 ROC，再 finalize。`hmac 0.12.1` 已预计算 ipad/opad 的压缩状态，clone 复制摘要状态，不为每包重新处理密钥，也不为 clone 分配堆内存。见 [HmacCore](https://docs.rs/crate/hmac/0.12.1/source/src/optim.rs)。因此再次“预初始化 HMAC”没有新的算法收益；`finalize_reset` 可作小范围 A/B，但不能预设有显著收益，其 feature 还会改变状态大小。

锁定的 `sha1 0.10.7` 在 AArch64 使用 soft 压缩路径；该版本 `asm` feature 为空，开启它不会得到 ARM SHA1 加速。见 [压缩实现选择](https://docs.rs/crate/sha1/0.10.7/source/src/compress.rs)、[feature 定义](https://docs.rs/crate/sha1/0.10.7/source/Cargo.toml)、[移除 sha1-asm 的上游说明](https://github.com/RustCrypto/hashes/pull/897)。不建议为恢复旧 asm 依赖而降级。

最小归因实验是比较同一个 key、同一段 `packet || ROC`：现有 RustCrypto clone、OpenSSL SHA1 的预计算 inner/outer 状态、OpenSSL EVP 新建 Signer。后者必须包括逐包初始化/分配成本。OpenSSL 低层 SHA1 clone 可以避免堆分配，但其 API 依赖 deprecated SHA_CTX 接口可用；只适合作为先证明收益的实验，不能在无测量时直接替换生产 SRTP，或为了一个调用建立新的长期依赖 fork。

## HMAC 离线实验复现

单项代码位于忽略目录 `logs/srtp-hmac-bench/`，不是生产依赖；已在 Linux AArch64 VM 验证 RFC2202、包与ROC的跨后端标签等价并运行。结果及完整 SRTP 候选见 [实测记录](bringup/2026-10-25-rtp-send-benchmark.md)，不能与主发送基准同时抢 CPU。该 crate 不在 One-KVM 下，也不依赖 AES/Polyval；它测的是 SHA1/HMAC，所以不会自动继承上述 ARM cfg。本次显式使用相同 cfg 以复用构建缓存，不把它们当作 SHA1 优化。

```sh
cd logs/srtp-hmac-bench
cargo generate-lockfile
cargo build --locked --release
cp target/release/srtp-hmac-bench ../srtp-hmac-baseline
cargo build --locked --release --features reset
cp target/release/srtp-hmac-bench ../srtp-hmac-reset
../srtp-hmac-baseline 1000 > ../srtp-hmac-baseline.jsonl
../srtp-hmac-reset 1000 > ../srtp-hmac-reset.jsonl
```

首次生成 lock 后保留它和构建日志，后续使用 `--locked`。输入覆盖 128/512/1200 字节、每帧 38/48/180/220 包，预热 100 帧，输出帧内 HMAC 总耗时及尾部百分位。开始计时前校验 RFC 2202 向量，以及不同 key 长度、SHA1 块边界、ROC 值的完整 20 字节标签逐字节相同；SRTP 的 10 字节截断也因此一致。reset 构建会同时测 clone 和 reset，比较时还需保留无 reset 的正式基线。

这项实验不包括 AES、RTP marshal、interceptor、socket、接收端或画面，只能判断 SHA1 后端是否值得继续。即使 HMAC 提速，也必须在真实 SRTP/完整 sender 复测，才能估计逐包尾部改善；不能把结果直接加减到端到端延迟。

## GCM 协商与 UU 约束

WebRTC 默认 profile 顺序已经是 GCM128、GCM256、AES-CM/SHA1-80、AES-CM/SHA1-32，见 [dtls_transport](https://docs.rs/crate/webrtc/0.17.2/source/src/dtls_transport/mod.rs)。本项目 DTLS fork 的 [find_matching_srtp_profile](../One-KVM/libs/dtls/src/lib.rs) 按第一个参数顺序寻找交集；仅两个调用者：[flight0](../One-KVM/libs/dtls/src/flight/flight0.rs) 服务端读取 ClientHello，以及 [flight3](../One-KVM/libs/dtls/src/flight/flight3.rs) 客户端读取 ServerHello。flight0 当前先传远端列表，所以服务端按客户端优先级选。仅重排本地列表或强制 answering Server 都不保证最终使用 GCM，必须核对实际协商 cipher。

[RFC 5764 §4.1.1](https://www.rfc-editor.org/rfc/rfc5764.html#section-4.1.1) 要求服务器选出的唯一 profile 来自客户端提供的集合，没有要求必须选择客户端最高优先级。因此服务端采用本地优先级有协议依据，但仍需对端兼容测试。客户端 flight3 的校验不应随之改变。[现有测试](../One-KVM/libs/dtls/src/conn/conn_test.rs) 的 `Multiple Suites, Client Chooses` 明确断言客户端优先；修改策略必须更新这一行为约定，并覆盖 GCM/CM 反序、CM-only 回退、无交集和两端选择一致。

尤其 [UU peer.rs](../One-KVM/src/uu_remote/peer.rs) 使用 `SettingEngine::default()`、强制回答 Server，没有显式 `set_srtp_protection_profiles`：它继承同一组默认 profiles，并不是 AESCM-only。全局修改 flight0 可能改变 UU 在同时提供 GCM/CM 的对端上的选择。没有当前 UU 兼容和性能回归，不能称这种修改无风险或只影响网页会话。

离线先测以下组合并打印实际 negotiated profile：默认角色/默认列表；Server/默认列表；Server/GCM128-only；Server/GCM128+CM80。最后一种在当前算法下仍可能选 CM80，不能误记为 GCM。若 GCM 在当前硬件/正式 features 下明显胜出，再考虑仅对 VIM4 网页会话生效的可配置选择策略；共享 DTLS fork 的全局策略变更需要额外 UU 验收。

NanoKVM 的 [Pion 配置](../NanoKVM/server/service/stream/webrtc/h264.go) 使用 Server 与 GCM 优先，但不能把 Pion 的服务端选择行为直接套用到本项目 Rust fork。[10 月 14 日记录](bringup/2026-10-14-webrtc-segmentation-offload.md) 的收益同时包含 GCM 和 UDP_SEGMENT；没有隔离两者，也不是 One-KVM 的当前基准。历史 `logs/uu-remote/srtp-probe-openssl-board.log` 中 GCM 还曾慢于 CM，因此必须重新测量，不能承诺切换即提速。

## 采纳顺序

1. 先完成生产等价的 Context/完整 sender 基线和 HMAC 后端实验，确认耗时主要落在哪里；保留内容及序号一致性校验。
2. 若 HMAC 后端有稳定、可观收益，优先研究现有 SRTP 上游可维护入口；reset 只作为小改动候选，避免复制已有状态复用逻辑。
3. 若真实 GCM 胜出，再验证实际协商和局部配置；保留 AESCM fallback，先解决共享 DTLS 对 UU 的影响。
4. 若 syscall 占主要尾部，再评估 Linux 发送批处理。要保留帧内顺序、ICE 选路、每包 SRTP、错误返回和音频/HID 调度；不能靠取消认证、随意增大 MTU 或并行乱序发包获取虚假收益。

所有候选最终都要回到相同运动负载的真实接收端，比较完整帧到达、解码、显示及丢包/重传。平均吞吐或离线 p99 改善只是进入该验证的依据。
