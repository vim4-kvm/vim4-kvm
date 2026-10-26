# 1080p120 候选准备

2026-10-26。已准备可回退的输入声明、5.15 RX 映射和 One-KVM 候选，
尚未部署、重启或加载新 EDID。当前板子仍为 `5.15.137-vim4kvm-hdrdual6`、
`RTK-CONTROL`；不能把本记录当作120帧采集、编码或显示已通过。
完整阶段与验收矩阵见[专项审查](1080p120-audit.md)。

## EDID

[原始 RTK 表](../board/edid/rtk-uhd-hdr.bin)没有 CTA VIC63/64（1080p120/100），
基础块垂直扫描范围为40–61Hz，两个1080p/1440p详细时序均约60Hz。
因此现有名称“RTK UHD HDR”不能证明支持1080p120。

[独立派生表](../board/edid/rtk-uhd-hdr-1080p120.bin)仅改5字节：在既有保留
SVD位置 `0x8c/0x8d` 加入63/64，`0x72`垂直范围上限改120，重算两块校验和。
保持SVD顺序/长度，避免错移Y420能力位图；首选4K60、原有详细时序、HDR、深色、
音频与厂商块全部保留。FreeSync范围仍40–61Hz；固定120与VRR120是独立能力。
原表既有的其他保留VIC/能力字段未清理，未声称整表协议符合性。

新增 `RTK-1080P120` 实验预设，经共享助手读取平台包的数据文件，
manager与One-KVM可选择；原始 `RTK-CONTROL` 数据/名称不变。
部署必须同时包括平台EDID文件、NanoKVM包提供的共享助手以及所需应用。
选择预设后源端仍需主动选1080p120；首选4K60不会自动改成120Hz。
首轮限定SDR8，HDR120和本地OUT120不由EDID字段继承为已验证。

## RX 与应用

5.15 `hdmirx_hw_get_fmt()` 已把1080p100/120 VIC归入1080p分支，但之前仅处理
24/25/30/50Hz，其余落到60Hz。本候选增加100/120映射，复用已有TVIN时序表；
不改RDMA、完整帧交付、VDIN0/1隔离或TX准入。
主机C测试编译真实 `get_fps_index()` 和 `hdmirx_hw_get_fmt()`，覆盖119.88/120、
100与原24–60行为，以及4K回退，避免只测声明字符串。

One-KVM输出上限接受5–120，H26x实际预算仅在Vendor后端、原生1920×1080时
放至120。4K/1440p即使缩小输出仍60，Wave5保留60，MJPEG上限不变；
用户60上限和低帧率源仍生效。UU请求不再在入口截成60，最终由同一预算约束；
这不代表官方UU客户端已请求、解码或呈现120。
界面增加100/120选项与独立EDID；候选状态未提升成已验功能。

## 构建与后续窗口

候选模块从VM干净 `linux-native-hdr-5.15`、common_drivers `8648a716b` 加上述4行
RX补丁构建；独立保存在本地 `build/1080p120/aml_media.ko`，不覆盖板端模块。
板上压缩Image解压后SHA256与该VM树的Image一致：
`6123de38fa741667b1f6c906d5a06ae7a4aa7ba4a16d7fc29e13ca406afaa780`。
模块vermagic为 `5.15.137-vim4kvm-hdrdual6`，仍需实际加载验证。
候选模块SHA256 `19eb3f474bb31344602595ba2a7ee8f2fd9c68c25f357bb85fae69490b33790c`，
build ID `6802376f07c793d9e5cdca045d22d13f2cb0d95d`。
One-KVM候选ARM64 release二进制已构建，SHA256为
`7f9d168c24a893bae5ade473c7b2645fdb04aa5ba449d9383455aaf20ec61570`。
源码提交：common_drivers `52f9e8431`、NanoKVM `9f72f71`、manager `5829d86`、
One-KVM `1ce65ba7`；尚未推送。它们是已离线验证的候选，不是实板交付记录。
VM候选基线与Mac正式common_drivers的运行C代码一致，后者只多两处测试补充；
已撤回VM原生HDR树的临时RX改动并重建基线模块；未改VM主 `~/src/linux` 的既有
未提交VDIN改动。候选模块独立保存在本地，不能拿基线重建后的VM模块替代它。
编译日志、离线测试与制品清单位于本地忽略目录 `logs/1080p120/`、`build/1080p120/`。

已通过：RX主机C回归；EDID语义/校验和检查；共享EDID助手12项；manager部署助手
212项（跳过12）；One-KVM Linux助手35项、Rust库775项（忽略2）、网页构建与9项网页测试。
主仓全套265项（跳过7）。Swift测试源已编译，音频代码有既有macOS弃用警告。
Mac网页构建因现有node_modules缺少Darwin Rollup可选依赖失败，改在隔离Linux构建器
按锁文件 `npm ci --ignore-scripts` 后通过；未修改锁文件。One-KVM助手在Mac因USB状态
目录的Linux约束失败，Linux构建器同套35项通过。全仓 `cargo fmt --check` 有既有格式
差异；未对无关源码批量格式化。模块编译通过不代替真实加载、显示或编解码验收。

上板须按[工具目录](tools.md)协调双锁；模块在 `aml_media` 内，需要更新启动时
加载的模块/initramfs并重启，不能热卸载正在工作的显示/采集栈。
重启前备份原模块和initramfs，保留原EDID与应用二进制；失败恢复同一基线。
新窗口先确认运行模块build ID，再按原始采集→裸编码→LAN浏览器→UU验证。
测试源新增可选 `--display-link`，使用所选屏幕的
[NSScreen displayLink](https://developer.apple.com/documentation/appkit/nsscreen/displaylink(target:selector:))
回调替代固定60Hz Timer，保留默认路径并输出回调/目标时刻；已编译，尚未验证120Hz运行。
绘制/回调计数不能证明物理呈现，仍须实际采集三处帧号验证独立120帧。
60Hz接收屏只能验证解码吞吐，不能证明每秒120次实际显示。
