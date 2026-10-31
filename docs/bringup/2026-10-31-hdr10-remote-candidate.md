# 2026-10-31：原生HDR10 r3离线候选

AMLY→Vulkan→P010→Wave5 Main10与用户态prefix SEI已实现并离线构建。
尚未上板，P0未完成；原生并行SDR截图和其他三应用仍未接入。
最新窗口只运行了5.15准备与收尾，MCP开HDR失败，未启动7.3候选；详见末节。
当前首选归档为特性worktree的 `build/hdr10r3-uhd4-final-ram.tar.gz`，SHA256：
`8b50ff26219f13b6945cbf154b37bc003d6f53c3cffccd863eeb7f2435c83652`。
最终完整离线制品包 `build/vim4-hdr10r3-uhd4-final.tar.gz`，SHA256：
`4e1d8a438d21c830aebb481960a2c968cad84f94e88f9f80e725d57a762a31d8`。
合同、缺口和30分钟清单见[设计](../hdr10-remote-73.md)，历史调查见
[r1/r2证据](2026-10-31-hdr10-remote-offline.md)。

## 提交与产物

| 仓库 | 特性分支 / 提交 |
|---|---|
| linux | vim4-hdr10-remote / dc220366a1222a03423d5b5987fab3f027ec1d7a |
| gst-plugin-vfmcap | hdr10-remote / b43e564595407b0b637a23f49a3cb390d4a6cbfa |
| One-KVM | hdr10-remote / 77b2cd10a6c6a41d0e30019bff5d6cc33b60f8a2 |

初版起点为origin/vim4-hdr2-uhd4的ce6bc0cc5218a；本轮已rebase到正式uhd4，详见末节。
不修改HDR2/kbase/manager工作树，原生HDR特性不合正式。

以下保留初版归档证据：本特性worktree `build/vim4-hdr10r3-20261031-offline.tar.gz`，SHA256：
`f8f9c80c56a86bfb5e7bb3a81cc11cc2f258d35b935c62dd2787fd630794a4b9`。
包含唯一release `7.3.0-vim4kvm-hdr10r3+` 的Image、DTB、完整模块、runtime-proof，
私有采集/V4L2 GStreamer、One-KVM、启动入口和逐文件candidate.json；不含vendor固件。
另已生成 `build/hdr10r3-ram.tar.gz`，SHA256：
`f8f74c397b7884602004c3b3dd1477670320fcbab2d1c98ffba625ee367dc057`。
该RAM payload包含静态ARM64 PID1、私有runtime/extlinux和完整模块；启动模板取自
只读HDR2 r18 payload，仍是唯一hdr10r3 release，不伪装为HDR2。
特性分支已补充新工具的hdr10rN识别与私有模块/基线回归；main工具尚需同步兼容修正。
PID1仅在RAM候选期间只读绑定runtime和模块，不改默认启动项；启动器需私有PanVK ICD。

Image SHA256 `fb5496a2a197bf1f63d0538cff0ee4bbeb034ef725bec29f1df7acde0d7c2f53`；
模块包 `5746d5bc2b9cdee6dfb6e4cd7596fe12de559c59cf436e97c7d5bf9449c89c1c`；
DTB `0c795e920aff8319c85346048c5c2423e9bf18bab65a3c3e9d04ec8cc7d5fc5a`。
私有V4L2插件 `7bb6551536645f5bc44db94e51f02a2abe7cdf8bf83b7f310dcb69636ee4a45a`；
采集插件 `8cf5655b9b1e3ccbb1f29feb8f848b4127b80c0843c2fe40e7336da13c681395`。

## 验证与中断恢复

- VDIN19项视频宿主脚本、Wave5目录12项脚本通过；AMLY尺寸/预算、原生准入与LUT保留、
  HDMI缺包/过期/零值及单位、P010 profile/容量、legacy endian均有实际C函数回归。
- 编码器Main10/PQ CPU fixture及实际C/Rust SEI输出由独立解析器检查；不是硬件精度证明。
- Vulkan三着色器与采集插件编译，Meson六项通过，含真实source PAUSED→NULL与12个失败回收点。
- 私有V4L2插件重建及三项既有协商回归通过，P010添加格式映射与可见尺寸支持。
- One-KVM：库测试820通过、4忽略；部署助手37通过；网页39通过、typecheck/build通过；
  release完成。通用cargo check被既有RKMPP C++/FFmpeg构建错误阻断，未改上游其他平台代码。
- 主仓首次315项运行、302通过、13跳过；同步main的新队列工具并补hdr10rN后，
  完整334项通过、10项跳过；strict checkpatch零错误/警告/check。
- 内核完整Image/dtbs/modules与BTF完成；NPU基线有既有编译warning，未见新增视频文件warning。

迁移前会话在完成构建后被用户停止，完整源码树HEAD仍为6c7af142e52a7，但工作内容已是
e883b52333a78。新队列heavy票据中核对所有内容、对齐干净提交；增量make确认无须重建，
未重做完整构建。One-KVM最终链接也在新队列中补齐并记录Finished release。
打包通过实际模块清单、build ID及runtime-proof检查。首次手工commit参数抄错被断言拒绝，
随后由git rev-parse读取实际完整提交重跑，未生成混合清单。

## 尚未运行的门禁

初版归档时没有板锁窗口、M6 HDR操作、5.15新鲜GPU占用基线或7.3真实DMA/码流/网页/UU证据。
随后用户明确限定授权M6 MCP，最新窗口结果如下。
不因静态能力探测/CPU fixture通过宣称4K60或SEI与当前产品逐值一致。
预计硬件精度/性能1–2工程日；并行截图、四应用与UU恢复补齐约3–5工程日。

## 正式uhd4 rebase与窗口结果

纯工具修正 `07ed1e5` 在独立worktree通过335项全量测试（13跳过）后合入main并push：
接受安全的任意7.3.0-vim4kvm-tag+，保留全部哈希/manifest/静态PID1清单门禁；
stage记录自己新建模块空目录的device/inode，回原5.15后仅删除仍属于它的空目录，
保留已有、替换、非空或挂载中的目录。新工具后续正式修正也同步进本特性分支。

排队遵守kbase→HDR(uhd4)→本会话，所有编译/打包使用新heavy入口，无旧lockf。
首次启动前发现正式分支已更新，未接触M6即释放票据；rebase到
`8bca939d6bbd3e4d91e9f23b812e920172c99b3d`，候选新头
`dc220366a1222a03423d5b5987fab3f027ec1d7a`，已带旧头lease校验推送。
差异只有HDMI RX/VDIN恢复同步及测试；31项视频宿主回归通过，只增量编译两模块/BTF，
重建并核对2338模块清单。Image/DTB和其余模块保持原产物，Image SHA仍为fb5496a2…。
因此保留原r3内核release/ABI，以独立归档名和新模块build ID标识此模块修订。
私有V4L2插件另纳入正式uhd4的sRGB探测/编码尺寸修正后重建，SHA256为
`3a7ab39049af1a3ee41b3d2168cdcbe0050daa2f1beb992c3536fef70f2e6589`。

窗口记录在main的 `logs/hdr10r3/`、`logs/hdr10r3-restore/`：

- M6截图1920×1080、源3840×2160，空闲变化率0.003%，初始EOTF=SDR。
- 新鲜5.15网页接收3840×2160，59.98 fps，零丢帧；实际codec=H.264。
  这不是AMLY→GPU→P010原生HDR性能基线，不据此宣称HDR 4K60或GPU对齐。
- MCP内置序列未进入显示设置，down-seven滚动落在Chrome网页，15秒内源未到PQ，
  报 `M6 HDR toggle did not reach the requested source EOTF`。随后停止，不重放开关序列。
- 本轮没有启动7.3候选，真十位DMA、Main10/VUI/SEI、HDR接收和模式往返门禁均未运行。
- 收尾独立票据只执行逆向up-seven恢复原Chrome页面，并截图确认；前后EOTF均SDR，
  最后为5.15.137-vim4kvm-hdrdual6，三项受查服务active、UDC configured，票据释放。
  没有发送裸Shift、输入文本、其他HID，也没有声音/ptrace/刷机。

首次脚本读root启动清单漏sudo时已在HDR操作前停止，随后修正为sudo -n；
源码/归档没有混用该失败结果。原生SDR截图与另外三应用的缺口按本轮授权继续留待后续。

最终再次核对5.15身份及18项启动/登记/程序/插件哈希，全部未变，HDR=SDR；
服务active、UDC configured。最终原窗口截图为main的
`logs/hdr10r3-restore/screenshot-1793450888993512000.jpg`。
最终RAM归档由main通用入口离线验证2364项文件哈希，保留2338个模块，静态ARM64 PID1通过。
模块流式写入tar以保留Mac上大小写不同的模块名；复用已校验的同release PID1，未重复编译。
合并最新main后完整运行347项，334通过、13跳过。首次文档合并超14KB已压缩入口并重新通过。
VM上的r3完整源码临时worktree、O=输出、重复展开payload/template已清理，保留候选归档；
主机另从Image恢复了内嵌config，SHA与manifest相符。默认Mac工作目录映射阻塞时，
改用显式Linux工作目录恢复VM命令，没有重启VM或干预其他会话构建。
