# 2026-10-31：uhd4正式构建准备，旧heavy锁阻塞（未上板）

用户已审阅[r18](2026-10-31-hdr2-recovery.md)：两向恢复中位数与5.15持平，
两栈都有长尾，三次样本内不构成退步，批准正式集成。
停止完成至下次STREAMON约0.5秒的长尾分解改为不阻塞后续项。

准备基于同一clean源码`8bca939d6bbd3e4d91e9f23b812e920172c99b3d`、
tree `0ce3bf8d9a1e57a97bdbaffa67610eceaddba579`生成正式命名
`7.3.0-vim4kvm-uhd4+`的Image/DTB/完整模块包，未添加新源码补丁。
正式内核远端仍f71b5c6289cb；One-KVM db848a52仅比vim4主线多一个已审阅提交。
独立集成工作树已合入主仓最新main的board-queue/board-window，未切主工作树分支。

## 排队观察

本轮只申请heavy票据，不申请板票据。04:13–04:29 PDT，HDR build票据始终queued，
前面的kbase build票据也始终queued；两者都被旧`/tmp/vim4-heavy.lock`独占持有者阻塞。
观察时持有者为lockf PID 23841，其子进程zsh PID 3979；未结束它们，也未删除锁文件。
VM观察时无make/cc1进程，但这不能证明其它会话已经不需要该锁。
新队列尊重旧锁属于预期兼容行为，尚未发现可确认的工具缺陷。

构建日志为空，未执行make、未改变构建release、未生成正式uhd4归档。
不是本轮磁盘满导致构建失败；VM可用59GiB。r18原构建已完整成功。
已请求旧会话自行释放或迁移；取消本轮尚未获批票据后，run/keeper正常结束，未留后台排队任务。
未访问板子、未调用MCP或改变M6设置，未重测5.15基线。

## 保留的准备与准入

本地`build/uhd4-build.sh`只通过heavy票据运行，完整构建后封存新formal-stage与RAM payload，
不覆盖旧实验uhd4封存档；`build/uhd4-seal.py`已与VM副本逐字节核对。
`build/uhd4-window.py`通过board-window完成boot-candidate、collect、return-baseline、receiver、mcp，
带截图审核停点和退出恢复；待构建完成后填入来源哈希，不能直接运行未封存候选。
这些为未执行的本地准备，不声称已通过烟测。

续跑顺序：旧heavy持有者自行释放→heavy构建→在kbase之后排板票据→≤15分钟烟测，
使用当天r18基线；干净启动、真实One-KVM 4K60解码、PQ/SDR各一次、ADLA/Panfrost、服务/UDC全部通过，
结束回5.15、HDR关闭截图及启动文件核验后，才推正式内核、One-KVM与主仓main及新sources锁。
kbase、hdr10-remote届时需rebase到uhd4并自行回归，当前不要求rebase到未完成的release。
HLG仍为已实现、无真实源未验。

旧HDR输出清理清单已核对，实际清理留待正式包封存后；保留正式构建和封存归档，
不触碰kbase/hdr10工作树。文档测试8项通过；主仓全量测试尚未重跑，因其包含编译宿主fixture，需heavy票据。
