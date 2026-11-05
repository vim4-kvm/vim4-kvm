# 2026-11-05：manager 续窗登录传输失败，已回退

**本页保留验收前首次续窗的失败与恢复证据。后续已验收并保留新默认，见[正式部署](2026-11-05-integration-formal-deploy.md)。**
协调者批准额外一张 20 分钟 FIFO 票，测试第 13 分钟截止，恢复预留 7 分钟；
范围只补身份/风扇/新鲜视频和 manager，明确沿用同封存资产的八类结果，不操作 M6。

## 本票结果

票 `1ca2ceeeb7004339b7e401d102bed7b5`（FIFO 1244）实际 **235.073 秒**，已释放。
内核归档仍为 `a12069066760768a833803ad11e7e1fc212674e4ff09f40bdf2017cc1d55e204`，
GNU ID `bdbfa439f298e92b5bad092528d11119a974f262`；manager 仍为 dev.10.g85，
deb SHA `5b7490a8cb6b1e362ae08eb113f818e28e4aa658506538cf5c3688f9f5ec9002`。

- 七个启动文件、2354 个模块目录文件、共享运行器和固件再次核验后安装 manager，原子登记新 Mainline。
- 新默认一次正常启动；UART BL2 主机观测 19:11:25.172 UTC。实际内核与完整模块身份通过，
  manager 文件/实际进程 SHA 通过，ExecStartPre fan-restore 与六区 90 trip 通过。
- 新鲜 H.265 3840×2160 五秒推进 304 帧、60.7680 fps，丢帧/冻结/丢包增量零；health 通过。
- manager 正常登录的 POST 请求在 Playwright 报 `EHOSTUNREACH 192.168.50.210:80`，
  尚未写入风扇；立即按首错回退。没有把 SSH、API 或视频成功记作 manager 门禁通过。

最后结果 accepted=false / restored=true。恢复 `.3` 整包登记、原 manager 和原 runtime 元数据，
完整身份/模块/基线保护文件通过；回退 boot ID `d0f306ac-9c5c-428f-84c0-c1c273ed4732`，
H.265 4K 五秒推进 305 帧、60.9735 fps，三个异常计数增量零。
恢复 `.3` 启动发生一次非请求已知类复位，BL2 观测 19:12:47.609/19:13:05.592 UTC，
第二次身份正确。此为原基线恢复启动记录，不是候选复位。
本窗没有 M6 通道、MCP 调用或 HID，也没有挂载介质或改变 HDMI 模式。

原始输出：`logs/deploy-73/window-10/` 的 inputs.used、完整身份/模块、fan-persistence、
candidate-fresh4k-video、manager.log、result、returned-proof/video、完整 UART 和启动事件。

## 离线修正与收据预检

下一次浏览器入口改为 SSH 本地 18080 转到板端生产 80，仍调用正常 loginManager 并要求
vim4_session，不使用 localBackend 绕过认证；安装前先只读登录和核原内核。
这是传输路径修正，尚未实板运行，不能由此断言已定位 EHOSTUNREACH 的系统原因。
同样资产的下一次编排已封存 94 项哈希并通过语法/离线输入核验；尚未排新票。

封存外部模块来源清单有 **5 个 AppleDouble v2 侧文件**，来自 Mac tar，不是编译源码。
从本任务 VM recipe 取回原字节，格式头和 SHA 全部核对；原包和 manifest 没有改变。
来源检查对这些侧文件核归档原件、AppleDouble v2 头和 SHA，其余源码仍逐项匹配 Git 工作树。
候选完整来源/产物边界离线通过；主仓独立提交 `c6205e7`，全套 557 tests、14 skipped、
31.998 秒通过。元数据原件在 `build/deploy-73/build-input-metadata.json`，正式验收成功后才进新 release 收据。

当时协调者明确只批准“一张票”，释放后没有自行重排。后来另批最多两张15分钟票，
先在原系统完成只读登录再安装切换，第一张即通过并保留新默认；正式锁/收据/tag的最终状态见正式部署记录。
本页失败记录没有覆盖或改写为通过；无 push、无合并。
