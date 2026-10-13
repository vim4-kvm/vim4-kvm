# 工作区

org 目录不是 Git 仓库。每个子目录对应一个仓库，公共文档和入口由 vim4-kvm 文档仓库管理。

| 目录 | 分支 | 归属 |
|---|---|---|
| vim4-kvm | main | 公共文档、板级服务与部署工具 |
| NanoKVM-Pro | vim4 | 当前应用，官方 Sipeed fork，服务 nanokvm |
| gst-plugin-venc | vim4 | 官方 Khadas 编码插件 fork |
| gst-plugin-vfmcap | main | VFM DMA-buf 采集插件 |
| common_drivers | vim4-kvm-5.15 | 官方 Khadas 驱动与设备树 fork |
| kvm | vim4 | 旧 JetKVM 回退，服务默认禁用 |

主内核是 vim4-kvm/linux 的 vim4-kvm-5.15 分支。macOS 大小写不敏感，
工作树放在 OrbStack vim4-build 的 ~/src/linux。MCU 风扇修改属于主内核。
构建见 [kernel.md](kernel.md)。

## 初始化入口

按上述布局克隆，在 org 目录运行：

```sh
sh vim4-kvm/tools/setup-workspace.sh
```

脚本在文档仓库父目录生成 AGENTS.md、CLAUDE.md、LESSONS.md 三个入口文件，以相对路径引用仓库文档。
不克隆仓库、不改 git 配置、不操作板子。已有相同内容会跳过，其他文件或链接
在写入前报冲突。先人工检查迁移内容，再移除已迁移入口并重跑。
整个 org 目录移动后引用仍有效；单独移动文档仓库需重新初始化。

各代码仓库保留简短路由。独立克隆时从
[公共文档仓库](https://github.com/vim4-kvm/vim4-kvm/tree/main) 阅读，
或将它克隆到相邻 vim4-kvm/。跨仓库相对链接按此布局解析。

## 文档维护

CLAUDE.md 仅引用 AGENTS.md 和 LESSONS.md；AGENTS.md 只做任务路由。
当前架构和操作方法归子系统文档，历史证据归上板记录。
错题本记录触发条件、原因、修复和验证入口；失效结论应更新或删除。
