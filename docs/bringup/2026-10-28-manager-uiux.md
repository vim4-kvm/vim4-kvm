# 2026-10-28：管理器界面体验整理

参照 impeccable 的操作型界面准则复核 12 个页面后整理管理器前端：删除重复读数和概览快捷操作，
散热改为单条温度读数，HDMI 输出删去重复的信号格式卡并为未接显示器给出说明，
网络存储删去三张低信息数字卡，连接失败行提供「查看原因」（以已保存配置调用
`/api/storage/test`，就地显示 NAS 返回原因）；助手的失败文案改为「连接失败」。
数据盘默认隐藏 `.` 开头的 macOS 索引文件并修正窄屏标题断词，登录设备默认显示最近 5 台，
回环来源显示为「经板上代理」，更新页区分「高于最新发布版」。原生复选框与下拉框换为
shadcn Checkbox 与样式化 NativeSelect，行内链接统一使用 `--link` 蓝色，选项组选中态与页签一致。

源码：vim4-manager `31b4f5f`（部署的程序由提交前的同一工作树构建，内容一致）。
验证：TypeScript/Vite 构建、Go 测试（随包构建）与 helper 214 项（Mac 跳过 12 项）通过。
针对本次行为的离线 Playwright 检查 20 项在 1280/390px 通过，无页面错误和横向溢出。
`web/tests` 中 auth、disks、motion、overview、passthrough、power、theme、updates、wifi
与 `ui-pages.mjs` 在未修改的 `2bb2c92` 上以相同首个断言失败，属既有过期断言，未据此判定。
注意：本机 `127.0.0.1:5188` 曾被旧 `vim4-manager-ui` 工作树的 Vite 进程占用，默认 TEST_URL
会测到旧代码；本次改用独立端口。

部署：开发包基线标签 `20261018.44` 低于板上登记的 `2.5.1+vim4.20261026.2`，安装器会拒绝降级，
因此沿用 [GPU 趋势](2026-10-27-manager-gpu-trends.md) 的做法，只替换
`/opt/vim4-manager/vim4-manager`（SHA256 前缀 `765589c07b61`）与 `/usr/libexec/vim4-manager-helper`
（`65826338de7d`），保留包登记版本，重启管理器。原文件备份在 `/var/backups/vim4-manager-uiux-20261028/`。
被替换的程序为 `894216f` 的脏构建（02:41 UTC），其内嵌板卡照片资源与 `93f49a5` 相同，
未丢失线上功能；板上 helper、透传脚本与 EDID 文件在部署前已与 `2bb2c92` 一致。
重启前后 HDMI 采集 PID 1097 未变，管理器 active，网页无浏览器异常。
板上截图与离线检查截图保存在本地 `build/uiux-manager/`。

回退：将备份目录中的两个文件装回原路径并重启 `vim4-manager`。
