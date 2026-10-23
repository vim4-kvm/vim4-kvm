# 2026-10-23：Wave5 隔离正式窗口复验

状态：十次注入验收通过；首次正式窗口 8/9 类通过、manager 失败并恢复基线。
修正构建资产后，第二次完整正式窗口 9/9 类通过并正式保留，已推送内核和 manager 部署分支。
驱动设计、内存保留边界、十轮逐项数据和临时窗口实际 HID 恢复证据见
[隔离验收](2026-10-23-wave5-isolation.md)。不实现运行时硬件复位或固件重载。

## 第一次正式窗口：前端产物错误，已回退

入口为 final-window.py，stage 使用 --wave5-monitor、--framebuffer-console 和
--require-all-checks；全程持 board/heavy 双锁。板端备份
`/var/backups/vim4-wave5-isolation-final`，Mac 日志
`logs/wave5-isolation/formal-window.log`、`formal-window/`。

HDMI 19 模式、H.264 18 个正反向采样、H.265 16 个正反向采样、4K60、音频、
真实 HID、虚拟介质、GPU 均通过。最后 manager 的 kernel API 检查通过，但浏览器等待
`.kernel-panel` 内“正式版”超时 30 秒，结果 manager=false。自动 restore/reboot 后输出
`BASELINE_RESTORED f483ea42fee88be39ea67c43478638be67334d6e`；没有保留失败候选。

原因是第一次 manager 编译复用了主工作树旧 web/dist；该产物没有当前固定源码已经具有的
正式内核标记。不能把源码工作树干净等同于被嵌入的忽略目录产物正确。改用独立 manager
worktree、同一提交 `9b141c5833c06a1cc876f9979ff21523c8af0558` 完整构建：

```sh
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
git restore web/tsconfig.tsbuildinfo
env -u GOROOT go test ./...
env -u GOROOT GOOS=linux GOARCH=arm64 CGO_ENABLED=0 \
  go build -trimpath -o ../wave5-isolation/vim4-manager-front-complete ./cmd/vim4-manager
```

tsbuildinfo 是构建修改的跟踪缓存，恢复它避免元数据误报源码修改；保留新 dist。
新二进制 go version -m 为上述 revision、vcs.modified=false。前端源码没有修改；
没有新增隔离告警 UI，仅后端 encoder API。Go 测试与前端构建均通过，日志
`logs/wave5-isolation/manager-rebuild-tests.log`、`manager-rebuild-provenance.log`。

## 第二次正式窗口

重新准备 formal-regression-2（全部九类、无 Wi-Fi/P2P 操作），使用完整 2334 模块的包，
新 bundle formal-complete-2.bundle；没有沿用第一次窗口的通过结果。

```sh
/usr/bin/lockf /tmp/vim4-heavy.lock /usr/bin/lockf -t 0 /tmp/vim4-board.lock \
  python3 -u build/vim4-main-wave5-isolation/packaging/kernel-edge/final-window.py window \
  --bundle build/wave5-isolation/formal-complete-2.bundle \
  --backup /var/backups/vim4-wave5-isolation-final2 \
  --logs logs/wave5-isolation/formal-window-2 \
  --archive-remote-to /var/tmp/vim4-pre-wave5-isolation-final2 --execute --locked
```

日志为 `logs/wave5-isolation/formal-window-2.log`、`formal-window-2/` 和
`formal-regression-2/`。本窗口已执行完成，结果：

| 类别 | 实际结果 |
|---|---|
| HDMI 模式 | 19/19，动态标记与三原色检查通过 |
| H.264 | 18 个正反向切换采样通过 |
| H.265 | 16 个安全尺寸正反向切换采样通过 |
| 4K60 | H.264/H.265 WebRTC 检查通过 |
| 音频 | 连续性检查通过，AUDIO_RESTORED_48000 |
| HID | 实际键盘按下/释放、绝对/相对鼠标、点击、滚轮通过 |
| 虚拟介质 | 实际主机传输检查通过 |
| GPU | 原有受限配置检查通过，没有加电压 |
| manager | 正式版/运行中标记、PD 卡、390px 布局、无 pageerror 通过 |

最终 health 所有字段 passed=true，NEW_WARNINGS []、taint=0；精确 Image/模块/服务核验通过。
finalize 输出：

```text
CRITICAL_HEALTH_VERIFIED 7b8372b894c98ffae12e636a325c86f2b6c85e00
UBOOT_UNCHANGED 751490703dc2f8ccee199ffe083b2ba5937cc598ec0e9e718f36c863a164e9e0
DEPLOYMENT_RETAINED {kernel: aa2f875..., onekvm: 382efb70..., manager: 9b141c5...}
SUCCESS: final deployment retained; no baseline reboot
```

满足本轮“十次注入 + 全部门禁通过才正式部署”条件，因此最后保留新版本。
临时注入窗口已先恢复过 f483ea42…并完成实际 HID，首次正式窗口失败也自动回退过；
不能把最终保留解释成跳过基线恢复要求。未重跑专门的 pstore 重启标记检查。

## 发布与产物锁

- 内核 `vim4-wave5-recovery` 和远端 `vim4-kvm-7.3`：
  `aa2f875bec2fc7c9a4952fccb9dcaa6fbfc4aa64`，tree `9b736ca14e1cb3f5536b6526c5dfac4dd110a91f`。
- manager `wave5-isolation-api` 和远端 main：`9b141c5833c06a1cc876f9979ff21523c8af0558`。
  One-KVM 保持 `382efb70e7ebb5e7fb8c9b13f1e6da5a161c84d1`，未推送或修改其分支。
- Image SHA256 `9fca5c6fc2a7c8943b5802198977df97857d89717f8da0041329bc070061c41a`；
  modules `770213bb108478a263be61f2b1b59031813ad639fd53232ed51f3b5393479cb1`，2334 模块、有 BTF。
- DTB M0 SHA256 `a635f8947ee77f67a43714aaa87276aff70edc0952bf40188d46853e055ce652`；
  Wave5 模块 SHA256 `39ae88c3ce5e9225b094ade9fd950c45cd86173b51884721a967cfda27df7844`，
  build ID `52f71181453475bd188db808c4da04fde8b419b4`。
- manager SHA256 `d7a15868e4b0b2a9fcf7342e1ffb69ed63db9b983d7b55aeedb99b0faaa59901`。
  完整锁、11 个已加载模块 build ID、manifest/runtime-proof SHA 写入 sources.toml；
  workspace.toml 只推进 manager revision，5.15 与其他应用的源锁不变。

保留板端 `/var/backups/vim4-wave5-isolation-final2` 与 Mac 的 baseline 六件套，
可用本窗口 bundle 和 final-window.py rollback 做受控回退。自动重启默认关闭；
开启后也只认“全部 KVM 服务 inactive 且虚拟介质为空”的可证明空闲状态。
运行中但无浏览器客户端的 One-KVM 不据此触发重启。前端隔离告警由后续 UI 设计。
真实挂死、热重启后的真实挂死恢复、运行时硬件复位/固件重载仍未验证或实现。
