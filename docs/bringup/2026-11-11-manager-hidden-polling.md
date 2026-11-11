# 2026-11-11：管理器后台标签页暂停轮询与输入法回车修复

vim4-manager `1aac105`：各页轮询在标签页隐藏时停止、显示后立即刷新一次；
NAS 文件夹 U 盘新建文件夹时，确认输入法候选的回车不再提交。
后台标签页不再续期会话，远程访问的一小时空闲限制（`internal/auth/store.go` `Authenticate`）开始对留在后台的面板生效。

## 上板

组件包 `2.5.1+vim4.20261029.102.dev.12.g1aac105`（deb SHA256 `3c3a39fe…0c686`），容器 verify 通过；
board.py manager-only 部署，旧版 `dev.11.gf384b3d`。内核 `7.3.1-vim4-20261108.2` 未变，
boot_id `6f3856d0-ee91-4854-8380-a0343219950c` 未重启；deploy 与随后 check 均以实际运行内核通过。

| 项 | 安装前 | 安装后 |
|---|---|---|
| vim4-manager | dev.11.gf384b3d | dev.12.g1aac105 |
| 概览 3.5 秒内 `/api/status` 请求 | 2 | 2 |
| 隐藏 7 秒内请求 / 恢复显示 1.5 秒内 | — | 0 / 1 |
| PD 服务 InvocationID、活动应用、UDC | — | 不变 |

隐藏状态通过覆盖 `document.visibilityState` 并派发 `visibilitychange` 模拟，未切换真实浏览器标签页。
窗口脚本、截图和状态在 `logs/manager-visibility/run-20261111T155146Z/`。

## 未验证

输入法回车只有离线 Chrome 合成事件回归（`web/tests/nasdisk.mjs`），未在 Safari 真实拼音输入下上板试；
远程会话一小时空闲过期未实测；其他页面的暂停仅由离线页面测试覆盖。
