# 2026-10-31：MCP与ICE定位，uhd4 PQ通过及恢复速度余项

承接[uhd4门禁](2026-10-31-hdr2-uhd4-gate.md)。本轮不改内核、One-KVM源码或M4个人网络设置。
**仅推特性分支，不合main/vim4-kvm-7.3：PQ→SDR恢复仍比5.15慢，尚未满足速度门禁。**
HLG保持“已实现、无真实源未验”。用户已于2026-10-30确认VDIN HDR2主路径。

## 接收与MCP

M4的板子IPv4路由和mDNS组播路由均经en0，LAN地址192.168.50.239，板子仍为192.168.50.210。
utun0–3只有IPv6链路本地地址；Tailscale显示Disconnected，系统HTTP/HTTPS/SOCKS代理未启用，
应用防火墙disabled。保留原设置；没有证据证明个人VPN/TUN接管了这次IPv4流量。

同一5.15、同一接收器做默认/关闭本次Chrome的mDNS candidate/恢复默认A/B/A：
默认两次均20秒无视频，offer为随机`.local` host candidate；
板端反复`pingAllCandidates called with no candidate pairs`，关闭时记录mDNS解析失败。
接收器加`--disable-features=WebRtcHideLocalIpsWithMdns`后使用192.168.50.239 host candidate，
ICE/DTLS connected，60秒段59.9924fps、3840×2160，丢帧/丢包/冻结均0。
实际选中LAN candidate pair；不把getStats中pair的瞬时in-progress字段误判成未连接。
由此定位到mDNS host candidate依赖，排除“一切UDP都被拦截”；**未证明是哪项历史网络变化导致**。
23:19的旧日志无SDP/网卡快照，不能追认变化时间。接收工具新增显式选项，默认行为保持原样。

本次Codex工具列表没有原生One-KVM工具，先以同协议只读screenshot探测，没有先发输入。
Python urllib直连报`OSError 65 No route to host`；同机curl initialize/tools/list/screenshot均200，
约0.04/0.04/0.42秒。新工具每次RPC新建curl连接并initialize，密钥只在内存/stdin，不入参数或日志。
5.15和uhd4下均截图成功，uhd4切换瞬间的`No video signal`与服务重启时502均有正常状态解释。
此前原生客户端具体错误为发送`http://192.168.50.210:8080/api/mcp`的transport错误，无HTTP响应。
One-KVM `src/mcp/server.rs`为无状态JSON HTTP接口，不维护MCP会话；
现有证据支持客户端/进程路径差异，**不能定论旧会话失效，也不能定论TCC/VPN**。

## M6空闲与恢复

00:49:21、00:51:25两次截图相隔124秒，Chrome窗口、URL、标签与滚动位置相同。
起初下方“终端”有变化，先退出设置、等待10分钟；只读网页脚本确认是固定STORY与60ms定时重绘的动画，
01:01复查仍同窗口、同指针位置，遂判断未观察到用户操作，开始窗口。
网页脚本仅作只读取证，没有执行页面展示的安装命令。

窗口01:02:11–01:30:17 PDT，共28分06秒。只打开显示器设置及一个本次data:固定渐变/色条标签页；
输入ASCII前先截图确认U.S.输入法。通过MCP切HDR，5.15状态确认PQ/ST2084；
结束关闭HDR、关闭本次标签页与设置窗口、恢复微信输入法和原Chrome页面，分别截图确认。
未单按Shift、未触碰文档、未测试声音；接收器仅video transceiver，无音频或HID通道。

## PQ、DMA与编码

内核仍ce6bc0cc5218a，release 7.3.0-vim4kvm-uhd4+，两次RAM一次性启动，5.15默认文件不变。
完整包/程序/插件哈希沿用[前轮清单](2026-10-31-hdr2-uhd4-gate.md)，本轮不编译，不访问kbase工作树。
色准使用已审阅legacy曲线，gain/OETF/PQ EOTF shadow CRC分别5868f499/47745310/55057c14，
19个具名寄存器白名单只读；shadow CRC不等于硬件LUT RAM读回。重新启动恢复管理器既有曲线。

| 门禁 | 本轮结果 |
|---|---|
| 干净启动/CMA | taint=0，无内核WARNING/BUG/Oops/CMA分配失败；独立编码后CmaFree恢复505208KiB |
| 5.15 vs uhd4 PQ | 三对完整3840×2160帧，NV21/NV12按各自UV顺序/尾部padding解析，Y/U/V p99全部0 |
| 输出/VUI | NV12 Rec.709/709/709/limited；实际HEVC SPS present、1/1/1/0，与5.15产品基准一致 |
| 逐代退休 | 5代、8954 ticket、8949编码提交、4次source change；最终未退休0、过时代提交0、trace丢失0 |
| 产品DMA | 两向切换后direct_dma=1、stream_copy_bytes=0，无严格DMA类型报错；浏览器恢复原连接 |
| 独立PQ Wave5 | DMA-buf，3600/3600帧，59.998327fps；最大采集间隔16.677708ms，pad→AU p50/p99=12.609/26.339ms |
| ADLA | 三模型各3次，共15个完整输出SHA与5.15基准相同 |
| Panfrost | Mali-G52 r1 MC4、Mesa26.2.6，正确像素、gl_error=0，GPU fault/timeout零增量 |
| MCP | 5.15、uhd4均能截图和切HDR，最终HDR关闭截图已取得 |

GStreamer扫描仍有既有libMali/无关插件缺失与GObject提示，不称全栈零告警。
110秒浏览器段后部被本次第二次独立抓帧主动停服务打断，不能把其全段平均当稳定吞吐；
稳定吞吐以上述独立3600帧编码和未受干扰的浏览器段为准。

## 固定图自身噪声与局部最大差

5.15两次采集间隔187秒，uhd4间隔126.5秒，每次3帧，保持同一固定图，不伪称桌面所有像素静止。

| 对照 | 完整帧max Y/U/V | 去顶部64行max Y/U/V | 完整帧p99 |
|---|---|---|---|
| 5.15自身 | 201/23/21 | 201/23/21 | 0/0/0 |
| uhd4自身 | 146/23/18 | 0/0/0 | 0/0/0 |
| 跨内核 | 201/24/21 | 201/23/21 | 0/0/0 |

5.15自身Y峰值的85个点在(3532–3552,175–196)浏览器工具栏区域，非顶部菜单栏；
uhd4自身峰值在菜单栏，去64行后完全一致。进一步去浏览器工具栏232行，跨内核max为35/2/3，
5.15自身仍45/2/7。该裁剪只作定位，不替代整帧p99门禁。
因此局部大差已有同内核内容变化噪声底；**旧a5首行212仍不能精确断言就是菜单栏时钟**，
需要保留原画面对应的源端时间/区域证据。不能把本次max都称硬件颜色转换误差。

## 切换速度：继续阻断正式推广

同一接收器每250ms读取framesDecoded，停顿定义为最后一次推进到恢复推进的间隔，含采样误差。
它衡量浏览器解码推进，不等于点击到HDMI锁定的物理时间，也不保证每帧均是新桌面内容。

| 方向 | 5.15 | uhd4，trace开 | uhd4补测，trace关、切换后不立即截图 |
|---|---|---|---|
| PQ→SDR | 1.012秒；回退补测1.269秒 | 1.776秒 | 1.778秒 |
| SDR→PQ | 回退补测2.281秒 | 2.031秒 | 1.777秒 |

原5.15首轮的ON点击晚于接收器结束，明确不用于恢复时间；后面专门补齐。
uhd4的OFF方向持续多约0.5–0.77秒，补测排除即时截图与trace开销，尚不能判“不明显差于5.15”。
ON方向没有变慢；不再沿用旧约6秒作为本轮数据。

trace将OFF分成SOURCE_CHANGE→END约0.521秒，END→下一BEGIN约0.979秒；
该短代又在约100ms触发source change，约171ms后最终新代开始。ON也有一次短代重建。
源码`drivers/media/platform/amlogic/t7-hdmirx/t7-vdin-test.c:1062–1100`每250ms监测锁定/时序，
`One-KVM/src/video/pipeline/shared/vim4.rs:285–328,444–483`每100ms观察/拉帧，错误有1秒退避。
日志未出现对应硬件错误退避，不能仅凭约1秒间隔认定走了该分支。
停止路径`t7-vdin-test.c:730`允许等帧边界最多1秒；目前没有入/出点trace，不能把0.521秒全归给它。
下一项应只加状态查询、管线置NULL/销毁、STREAMOFF与重新STREAMON分阶段时间戳，
查明短代的二次信号变化及旧池排空等待，再修有证据的恢复开销；不放宽退休或DMA合同。

## 交还与推送

最终5.15、输入SDR、one-kvm/vim4-manager/vim4-kvm-hdmi均active、UDC configured；16项受保护文件SHA一致。
证据保存在本会话`vim4-kvm-gpu-hdr/logs/hdr2-r17`，原始屏幕/帧不公开入Git。
板上本会话目录已完整封存43项至`board-evidence.tar.gz`并检查成员与gzip完整性，SHA256为
`260011df443654f14d506f54fa1bed2895258f9196a5d9383d17b5d5442985e6`，随后仅删除`/var/tmp/hdr2-r17`。
主仓unittest 325项、13跳过，其余通过；接收器node语法检查和git diff --check通过。
上板测量期间无并行编译；宿主测试在采样/恢复结束后、仍持有双锁时执行，随后释放双锁。
只推`hdr2-uhd4-integration`和内核`vim4-hdr2-uhd4`；正式main/内核分支不动。
One-KVM正式vim4仍未推进，db848a52保持候选；kbase仍以uhd3为基线，未来推广uhd4后需要rebase。
