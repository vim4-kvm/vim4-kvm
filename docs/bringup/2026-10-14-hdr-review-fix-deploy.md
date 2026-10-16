# 2026-10-14：HDR 审查修复与部署

主仓库 `c84939d` 修复 systemd 重复 EnvironmentFile 导致音频包校验器抛出
DuplicateOptionError；曲线工具严格拒绝非十进制参数，不再吞掉重载写入失败。
新增曲线硬件边界测试，验证 149 点、12 位范围、单调性和无效参数不输出半张表。
管理器清单改为 `hdr-curve` 分支的 `d44cb95`，干净源码可构建文档描述的 HDR 控件。

common_drivers `305ab27e9` 将 sysfs `reload_hdr` 改为提交待处理标记，由采集中断
在 isr_lock 下消费。VDIN0 的 HDR 寄存器实际直接写入，不是旧注释描述的 vsync
RDMA 排队；从 sysfs 直接调用会与信号切换中断共用 LUT 缓冲区。停止采集时请求
保留，恢复帧后处理；重复请求合并。主内核保持 `b86c7e5bd`。

独立目录按清单检出，locked 检查、42 项主仓库 Python 测试、30 项 NanoKVM
部署测试、10 项管理器助手测试、16 项 JetKVM 部署测试通过；完整用户态构建、
VIM4/默认 Go 目标测试与构建、前端和 sudoers 检查通过。六组件包
`2.5.1+vim4.20261014.1` 的隔离校验通过，包括音频启动顺序、ARM64 ELF、动态库、
配置保留、旧助手清理和损坏文件拒绝。内核 modules 构建通过。

板上其他应用包含独立任务改动，因此仅更新 vim4-kvm-board 包与 aml_media.ko，
不使用会覆盖全部组件的 deploy 入口。安装前模拟 APT，实际仅升级板级包；更新
initramfs、sync 后重启。旧模块、initramfs 和板级脚本备份在
`/var/lib/vim4-kvm/hdr-review-20261014.1/`。加载模块 build ID 为
`71e455238d105f4d2d9eff1da7a34b85db2efca9`，与产物一致。
NanoKVM、JetKVM、管理器二进制哈希均保持不变；管理器原有手工部署的 HDR 控件
继续工作。JetKVM 仍为 enabled/active，NanoKVM disabled。

重启后信源初始为 SDR，用户重新开启 HDR 后报告 HDR10-GAMMA_ST2084。
真实 Chrome 页面连续四轮预览 SDR 白 400→160→203、高光 1000：64×36 缩小画面
的平均 RGB 码值约 168.5→236.0→227.9，确认曲线确实影响解码像素，不是只更新配置。
这是桌面抽样，不是色度校准或 HDR 视频高光质量结论。预览不改保存值，保存恢复
203/1000；运行中增益和 sRGB 两张 LUT 与工具生成值逐项一致。

HDR 测试窗口约 12.56 秒，4K 解码 714 帧，浏览器 dropped/lost 均为 0；采集端
frames_dropped=0。HDMI InvocationID 在预览与保存前后保持不变。SDR 冒烟同样
零丢帧/丢包。board.py check 通过，无 failed units，dpkg audit 无输出，本次启动
日志未见 Oops/BUG/panic。未测 HLG、HDR10+、RGB/4:4:4、长期稳定性或端到端延迟。
日志、构建记录和界面截图在 `logs/hdr-review/`；产物及部署脚本在 `build/hdr-review/`。
