# 2026-10-16：开发版本规则与管理器正式版部署

- 工作区 `8ca8e5c` 将本地默认打包改为自动生成 `.dev.N.g<提交号>[.dirty]`；指定正式版时要求源码干净，CI 发布再次核对版本和源码记录。同日新编号超过已有正式 tag，保留旧版本的升级顺序。
- 已推送管理器 `5975c05`、One-KVM `00fff030`、NanoKVM `3834630`、JetKVM `e68c52f` 及工作区版本锁定。管理器显示开发版标识，One-KVM 支持解析已安装开发版，NanoKVM 的更新提示比较包构建编号，JetKVM 增加开发版排序回归。
- 管理器 [CI 发布任务](https://github.com/vim4-kvm/vim4-manager/actions/runs/38924362383) 成功，正式版 [2.5.1+vim4.20261016.1022](https://github.com/vim4-kvm/vim4-manager/releases/tag/2.5.1%2Bvim4.20261016.1022) 成为 Latest。下载发布制品后逐项验证 SHA256；`sources.json` 的开发标记为 false、所有源码干净，管理器提交与预期一致。
- 用 `board.py deploy --exclusive` 的 manager 单组件路径从 `.116` 升至 `.1022`；`dpkg --verify vim4-manager` 无差异。One-KVM、HDMI、USB 服务的 MainPID 和启动时间与部署前相同，boot ID 仍为 `9ac9de0a-1b7f-44fe-934e-c9d8e40ed5d0`，活动应用和介质状态保持一致。
- 无头浏览器经 SSH 隧道访问板上真实页面（浏览器直连局域网返回地址不可达）：1920 宽更新页显示 `.1022`、已是最新，正式版没有开发标识；390 宽无水平溢出，无页面脚本错误。此轮未验证音视频、HID 或延迟。
- 发布、部署、前后状态及服务进程记录、页面截图与浏览器日志：`logs/versioning-release/`。构建工具与版本排序的离线证据见 `logs/versioning/`。
