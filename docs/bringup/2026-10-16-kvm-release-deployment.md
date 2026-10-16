# 2026-10-16：四套 KVM 正式包部署

## 发布与安装

源码固定于工作区 `769e0c0`，通过各应用的发布工作流构建 ARM64 正式包。
下载 GitHub Release 制品，核对全部 SHA256、`sources.json` 的版本、组件、源码提交，
并确认开发标记为 false、所有源码干净，再逐个执行 `board.py deploy --exclusive`。

| 应用 | 原安装版本末尾编号 | 新正式版 | 源码提交 | 发布任务 |
|---|---|---|---|---|
| NanoKVM | 110 | `2.5.1+vim4.20261016.1018` | `3834630` | [38926129382](https://github.com/vim4-kvm/NanoKVM/actions/runs/38926129382) |
| JetKVM | 110 | `2.5.1+vim4.20261016.1012` | `e68c52f` | [38926135617](https://github.com/vim4-kvm/kvm/actions/runs/38926135617) |
| PiKVM | 113 | `2.5.1+vim4.20261016.1010` | `b7a3042` | [38926147292](https://github.com/vim4-kvm/kvmd/actions/runs/38926147292) |
| One-KVM | 112 | `2.5.1+vim4.20261016.1016` | `00fff030` | [38926141069](https://github.com/vim4-kvm/One-KVM/actions/runs/38926141069) |

## 板上检查

- 部署前虚拟介质状态已知、没有插入或连接，活动应用为 One-KVM；安装锁空闲。
- 四个发布任务的构建、隔离验证和发布均成功；四个包分次部署成功。
- NanoKVM、JetKVM、PiKVM 依次切换后，所选服务运行并启用，其余应用停止并禁用。
  Chrome 经 SSH 隧道访问真实页面，HTTP 成功、页面有内容，没有页面脚本错误。
  PiKVM 检查到登录页面，没有登录或重置账户。检查后恢复 One-KVM。
  最后安装新版 One-KVM，同样通过服务、首页内容与无页面脚本错误检查，最终活动应用为 One-KVM。
- 四套 KVM 与管理器以 root 执行 `dpkg --verify` 无差异。系统 boot ID 保持
  `9ac9de0a-1b7f-44fe-934e-c9d8e40ed5d0`，未重启。
- 用户选择仅检查启动与页面；未验证视频解码、音频、HID、介质读写或延迟。
- 发布任务、部署、版本与页面检查证据及截图位于 `logs/kvm-release-deploy/`；
  管理器保持 `2.5.1+vim4.20261016.1022`。
