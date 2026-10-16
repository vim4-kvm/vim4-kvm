# 2026-10-15：管理器侧边栏、风扇曲线调节与 EDID 界面

管理器改为侧边栏分页：概览、KVM 界面、视频输入（EDID + HDR）、散热、网络、底层服务。
风扇曲线复用 khadas-mcu 现有 trigger_temp_low/mid/high 接口，不改内核；助手先放宽
两端再写中值，保证每一步都满足驱动 low < mid < high 校验，并跳过未变化的写入（每次
写入都会触发一次 5% 调速）。保存值由 vim4-manager.service 的 ExecStartPre 恢复。
EDID 由下拉框改为预设卡片，显示已保存、本次开机加载与 JetKVM 同步状态，切换前确认。

管理器 `.45` 本机 Go 交叉编译，在 vim4-kvm-builder:ubuntu24.04 中调用 package.py 的
manager() 组包，经 board.py 单组件路径安装。实板：非法曲线 60/62/100 返回 400 且未写入；
50/70/90 写入后 sysfs、mode=1 与 /etc/default/vim4-kvm-fan 一致；手工把 sysfs 改回
60/80/100 后重启管理器，曲线恢复为 50/70/90；最后应用 60/80/100 出厂值。全程 One-KVM、
tvserver、HDMI 服务 InvocationID 不变。未重启整板验证开机恢复，未测量风扇实际噪声与温度。
Go/Python/前端构建、主仓库离线测试及 Wi-Fi 浏览器测试通过；风扇拖动、键盘与应用请求
在模拟 API 上验证，桌面/手机宽度与浅色/深色截图无溢出。
证据：logs/manager-fan-sidebar/（部署日志、风扇 API 记录与实板截图）。

界面随后重新设计为“数据表”风格：去掉卡片阴影与胶囊徽标，内容直接排在页面上以细线分隔；
状态改为小指示灯加文字，主按钮用墨色，KVM 界面与底层服务改为列表/表格，数值等宽数字，
删减重复说明文字；wifi.css 合并进 styles.css。以 `.46` 经单组件路径部署，One-KVM、
tvserver、HDMI 服务 InvocationID 不变；风扇拖动与 Wi-Fi 浏览器回归通过，桌面浅/深色与
390px 手机宽度无横向溢出。截图：logs/manager-fan-sidebar/restyle-*.png。

概览随后增加网络吞吐趋势（发送/接收，与其他趋势共用时间轴）、网卡链路与地址、系统盘用量、
vim4-* 组件版本和最近事件。事件只在管理服务内存中保留，来源为 5 秒轮询的状态比较与面板
操作结果。`.49` 部署后 One-KVM、tvserver、HDMI 服务 InvocationID 不变；实板 API 返回 eth0
1 Gbps 与地址、两块未连接的 Wi-Fi、系统盘 28.1 GiB、8 个组件版本，应用风扇曲线后事件
列表出现对应记录。HDMI 掉线、USB 断开与过热事件只经单元测试，未在实板上制造。
截图：logs/manager-fan-sidebar/overview-*.png。
