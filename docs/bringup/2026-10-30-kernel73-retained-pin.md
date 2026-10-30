# 2026-10-30：7.3 保留运行时与发布锁同步

按用户授权将保留锁从 b1300eb 更新至正式 `vim4-kvm-7.3@213f271505411845eecb3c6ef10df7565b895ebc`，
使用此前已上板的 ACM 配置构建，build ID `7a473adf9353013fd1ab01908d20bbf503a063fb`。
已替换板上完整 Image/DTB/modules、重新登记 FullKvm；默认始终为 5.15 Default。
没有保留旧 7.x 模块副本、生成新回退备份、刷 U-Boot 或发布外部产物，也未 push 主仓。

## 字段来源

原始构建在 VM `~/build/73-gap-20261030`，原始 payload 在 `~/build/73-gap-payload`；
最终保留格式在 `~/build/73-pin-retained`。本轮原始证据在主工作区忽略目录
`logs/73-pin-20261030/`，板端保留包在 `/home/khadas/73-gap/pin-retained/`。
字段均由清单或板上文件读取，不用历史摘要推算新哈希。

| 锁字段 | 数据来源与含义 |
|---|---|
| kernel revision/tree | 原始 build.json、manifest.json；tree `9b70de878174c786b5a5d1cf4f2d446598fe8f61`；远端正式分支实查同 revision |
| release/localversion/config_path/config_sha256 | 原始 `.config`、kernel.release、构建清单及板上 `/proc/config.gz`；release `7.3.0-vim4kvm-uhd1+`，配置哈希 `4f8f254d60a37b7cdd7842a1ea7e40f0b036491185efa056179de15628e8dfa6` |
| build_id | 原构建 vmlinux notes 与两次板上 `/sys/kernel/notes` 一致 |
| module_btf/framebuffer_console | 原配置明确启用 DEBUG_INFO_BTF_MODULES、FRAMEBUFFER_CONSOLE；FullKvm APPEND 保留 tty0 |
| Image/DTB/modules/manifest | 最终 payload 实际文件哈希，DTB 为带本板 MAC 的 display-m0；modules 归档沿用原构建 |
| module_count/wave5_module_sha256 | manifest 完整清单实数 **2337** 个模块；Wave5 为清单内压缩模块文件哈希，不与 ELF build ID 混用 |
| loaded_module_build_ids | 11 个具名模块的板上 `/sys/module/*/notes/.note.gnu.build-id`，逐项与原始 manifest 对照成功；未加载的 IR/JPEG 等具名模块仅显式 modprobe，不发送输入或播放声音 |
| runtime_proof_sha256 | register-runtime.py inventory 实际扫描安装 Image/完整模块生成的 `board-runtime-proof.json`，内容与最终 payload 的 runtime-proof.json 相同；它是安装清单，不是功能验收报告 |
| live_proof_sha256 | 板上 GNU notes、运行配置、服务、版本、应用/插件文件哈希组成的 `live-proof.json`；同时写入 `/etc/vim4-kvm/runtime-build.json`，不沿用旧失真的运行摘要 |
| onekvm/integrated_runtime | 实装 One-KVM `3649a8c8`、manager `81c6cc5`、Wave5 插件 `b3b82a9` 的文件哈希及 dpkg-query；平台包仍为 20261027.3.dev.12，PiKVM 包仍为 20261025.13，不能冒充全部组件同版本 |
| gstreamer/jpeg | 实装私有 V4L2 插件哈希 a80d41…，JPEG 用户态插件仍为 bc21e6…；JPEG 内核模块哈希改取同次构建清单。visible-crop 补丁正式进入 gstreamer.patches，构建器仅按该列表应用一次 |

配套应用完整版本及哈希见 sources.toml。三个子仓的指定远端分支已实查与本地一致，
workspace.toml 的“未推送”注释已据此更正。gst-plugin-venc 本地没有 origin，使用清单中的
公开仓库 URL 查询 vim4，未修改其 remote 配置。

## 最终 Image 格式

启动分区仅余约 13 MiB，原始 Image 为约 54 MiB，不能直接覆盖后共存。
沿用板上已使用的 gzip Image 形式，对同一个原始 Image 执行 gzip level=9、mtime=0；
最终为 18,469,326 字节，未重新编译或改变 build ID。

- 最终安装 Image：`61dda2420c55623baf7c1f5f5d2a4af1a79c7f528dceb24f3462e373e93eca9d`。
- 原始 Image：`3171ff8eda8e45b149fef1fb92dbfeddfd20dccdf2db78fdaa626fdf03af003b`，
  记录在 uncompressed_image_sha256。
- 原始 manifest：`bf7a7652508f84c9ee58e9d61a2905a8b18b7758b20c0cc9a7c521e5069fcbb7`，
  记录在 source_manifest_sha256。
- 最终 manifest：`09cbe93b9a5659fcab40994a5650ea4fb16c6ad4ffe4a6e933989f21a48feb14`。
- 模块归档：`3f08147903a15cd211db0276e0b8c209d20c731b0bb8e0dcc6392123edae1875`。
- M0 DTB：`893ea6c8990860f1ee0d8c1910fc210e39728e941128d52f465618a5f0c3958d`。
- 安装 proof：`b5342302d05513a14bc3d05550060bae61ef649771b06ef8fc56943166a70f42`。
- 实测 live proof：`de7678426e1a5c510a722a83a70d6548259a9af6e8530e8a58cad63927c97d21`。

因此 tested_build.image_sha256、manifest_sha256 和 runtime_proof_sha256 对应最终安装格式，
不是把旧原始清单的 Image 哈希直接用于 gzip 文件。

## 安装、启动及校验

5.15 下先校验归档、逐文件比对完整模块清单，再替换旧 7.x 模块和 /boot/edge 两文件；
保留 /lib 符号链接和 Default/Stock。register-runtime.py register --framebuffer-console
重新校验安装清单并登记 2352 个 mainline artifacts，确认 default=Default。
工具原有 extlinux.conf.before-full-runtime 已存在，本轮没有再生成备份。

第一次 RAM sysboot 采集已有私有候选的运行 notes；第二次 RAM sysboot 直接加载最终
gzip Image、M0 DTB及持久 `/lib/modules`，不带私有 init。`persistent-modules.txt`
确认模块来自根 ext4，而非候选 bind；两次内核/模块 build ID 匹配，taint=0，核心服务 active。
视频专用空白页客户端仅接收视频，不加载产品页面/HID通道或音轨。
日志：`install-register.log`、`boot-uart.log`、`retained-boot-uart.log`、
`retained-live-proof.log`、`persistent-modules.txt`、`video.log`。

build.sh 新增第四参数 --validate-only：复用严格 revision、干净工作树、新外部空目录检查，
执行 olddefconfig 后退出。本轮在实际 VM 正式源码上通过，生成配置哈希与已验构建相同；
非空输出、错误 revision 均实测拒绝。没有删除或放宽版本保护。
未重新完整编译 Image/modules，也未承诺不同构建输出目录可以逐字节复现旧 GNU build ID。

## 边界与发布

此前功能验证见[批量窗口](2026-10-30-kernel73-gap-validation.md)及
[第三/四轮记录](2026-10-30-kernel73-gap-r3.md)。本轮补齐安装/运行身份与登记证据，
没有重跑九类全量、HID、声音或 UU/SRT 并发；GPU真实sudo CPU预算仍有第三轮记录中的缺口。
不能将更新锁解释为全部7.3功能验收通过。

流程不要求先发布 GitHub Release，故没有发布或上传。若需向外部交付二进制，应发布匹配的
gzip Image、M0 DTB、完整 modules.tar.gz、最终配置、manifest.json、runtime-proof.json，
附源码提交、原始 Image/manifest 哈希及功能验证记录；现有开发版应用包也须明确版本和来源，
不能冒充正式 Release。仓库中的哈希本身不会提供这些未上传产物的下载。

收尾恢复 5.15 默认启动、清除临时 HID 隔离并确认服务正常；最终检查与主仓 unittest
见本轮 `final-state.txt`、`main-tests.log`。本轮没有保留 b1300eb 作为板上 7.x 回退项。
