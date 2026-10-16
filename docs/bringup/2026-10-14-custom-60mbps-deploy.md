# 2026-10-14：三套 KVM 自定义 60 Mbps 部署

已部署完整组件包 `2.5.1+vim4.20261014.11`。NanoKVM、JetKVM、One-KVM
及 amlvenc 由固定提交重新构建；未改动的板级工具、采集插件和管理器二进制
复用 `.10` 验证包，sources.json 记录来源。工作区未提交的 EDID 等改动未打包。
三套应用自定义范围均为 1000–60000 kbps，JetKVM 新增自定义输入，原档位保留。

- 干净源码构建及包校验通过，包括 ELF/依赖、配置保留、损坏文件拒绝和真实升级流程。
  JetKVM 的副本 Git 对象路径在容器内不可用，最终构建使用 `-buildvcs=false`；
  源码版本由包清单记录，应用版本显式写入 `.11`。
- 逐套切换并实际保存 60 Mbps，拒绝越界请求，刷新后读取配置；Chrome 解码
  3840×2160：One-KVM 59.67fps、NanoKVM 60.07fps、JetKVM 59.98fps，
  每次采样 10 秒，无观测到的丢帧/丢包。这是功能回归，不是持续带宽压力测试。
- NanoKVM 第一次检查因共用 URL 的缓存页面超时；测试入口加应用参数后通过。
- 恢复原码率及 One-KVM 选择；NanoKVM/JetKVM 配置文件 SHA256 与测试前一致。
  切换时 NanoKVM 自动挂载的磁盘已先在 Mac 弹出、再卸载，恢复测试前未挂载状态。
- 所有组件版本为 `.11`，dpkg 文件校验/audit 通过，管理器图表功能保留。
  HDMI InvocationID 仍为 `5adb6d1c9b494584996befd0f64d2877`。

证据：`logs/encoder-high-bitrate/package-verify.log`、`deploy.log`、
`apps-60m.log`、`nano-60m.log`、`jet-60m.log`；安装包位于
`build/packages/2.5.1+vim4.20261014.11`。实验硬件极限仍见前一节，
未新增高运动长时压力、端到端延迟或画质结论。
