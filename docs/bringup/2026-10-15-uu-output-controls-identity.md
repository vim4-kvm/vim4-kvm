# 2026-10-15：UU 网页输出控制、名称与系统身份

One-KVM `.4` 开发包已部署。第三方访问页面 UU 卡片增加视频设置入口，复用现有
VIM4 控件，输出高度增加 900p/1440p，帧率增加 5/24fps，并保留客户端产生的
自定义档位。刷新读取实际运行设置；网页保存的视频上限、码率仍走现有持久化接口。
网页调整 H.264/H.265 输出与码率时保留共享管线订阅，UU 也同步外部码率变化。
底层网页控制改动提交 One-KVM `5a948313`，其余 UU 源码仍在用户原有未提交工作树中。

设备名称默认 `vim4-kvm`，支持网页修改；注册摘要的 name 不会覆盖已绑定设备的
alias，必须另外 PUT `/api/v1/device/{id}`，body 为 alias。现有 Windows 设备的
实际请求返回成功、设备 ID 不变且 alias 匹配默认名。网页允许 Windows/macOS，
选择影响注册接口、签名平台头及设备资料，不能只改 os 字符串。
官方本机 Mac 客户端静态检查确认 `/api/v1/device/macos/init` 与平台 4，Mac
资料使用 system_name/system_version/model_identifier/resolution 等字段及 video 数组。
IDA MCP 不可用，使用本机 otool/字符串与字段元数据核对；没有修改官方程序。

云端实测 Mac 注册成功并返回平台 4，但分配的设备 ID 与 Windows 不同；复用
Windows 令牌创建 Mac 房间返回 1120。因此分别保留 Windows credentials.json 与
Mac credentials-macos.json；首次切换系统需扫码，切换停止旧连接、取消旧二维码，
切回恢复该平台原有登录。不是把 Windows 令牌写到 Mac 文件后声称兼容。
部署后保留 Windows 身份与登录，UU online/ready，当前尚未扫码验证 Mac 观看端。

验证：595 项 Rust 测试、release、前端类型检查/构建、Linux 的 15 项部署测试通过；
部署测试在 macOS 上因 Linux 路径约束失败，不作为通过结果。隔离空白实例的 Chrome
回归通过真实网页保存、非法名称/系统拒绝、重启后保存与系统切换；视频控件入口已检查，
该实例无采集硬件，未将它算作网页调整后实际编码的板端验收。
工具：`tools/one-kvm-uu-ui-check.mjs`。完整包验证含真实 dpkg/认证在线更新通过。
板上 One-KVM active、首页 HTTP 200、dpkg -V 无差异，未改变其他组件版本。

制品：`build/packages/2.5.1+vim4.20261015.4/`，deb SHA256 为
`c17316c0906f32450cb1b2f5d3cf35288681d256bdc144768d4faa281fdc4da9`。
证据：`logs/uu-remote/web-identity-{final-tests,final-release,frontend,browser,package-verify,after-deploy}.log`。
仍保留上一轮缩放 60fps 吞吐限制；未进行全新镜像刷机或长期 UU 观看验收。
