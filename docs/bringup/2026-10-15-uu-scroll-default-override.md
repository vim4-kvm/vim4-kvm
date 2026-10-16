# 2026-10-15：UU 滚轮方向默认值与手动覆盖

One-KVM `45de8abb` 增加独立的 UU 反转滚动配置。切换到 Mac 默认反转，
Windows 默认不反转；同一身份下手动覆盖保存后，刷新与重启保留。
旧配置缺少该字段时按系统取默认值，现有 Mac 用户无需重新切换身份。
改变方向会关闭旧 UU 会话并释放输入状态，重新连接后生效；仅影响 UU 的纵向滚轮，
不修改公共 HID 或其他客户端。细小滚动量先反转再累积，断开时清除余量。

599 项 Rust 测试、前端类型检查与构建、ARM64 release、完整包验证通过。
独立 Chrome 实例验证系统切换默认值、手动关闭、刷新、应用重启持久化及 API
只切换系统时的默认值。容器重启遇到本机端口转发失效，改用容器内监督应用重启，
等待 PID 变化及配置载入完成后复测通过；测试实例已删除。
实际 UU 客户端滚动体感仍待用户确认，不将浏览器配置测试算作端到端滚轮验收。

单应用包 `2.5.1+vim4.20261015.6` 已部署，服务 active、HTTP 200、dpkg -V
无差异并恢复 UU host online。SHA256：
`0063e59f587518f38086b1aed1fd240bc0e8d005b197be6adcd59279f813871b`。
证据：`logs/uu-remote/scroll-{tests,frontend,release,browser,package-verify,deploy,after-deploy}.log`。
