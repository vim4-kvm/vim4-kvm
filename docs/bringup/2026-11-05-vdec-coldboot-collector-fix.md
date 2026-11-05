# 2026-11-05：空环境下冷启动采集器离线修复

**已离线复现并修复，未上板、未重封 r60 候选、未补样。**
[r60](2026-11-05-vdec-coldboot-ab-r60.md) 的早期/ready/end 模块参数与 lsmod
仍然全部未覆盖；本次修复不能追改该结论。

## 机制与修改

在 Ubuntu ARM64 VM 中，以空环境和 `executable=/usr/bin/python3`、
argv[0]=`python3` 启动，Python 返回空 `sys.executable`，使用它启动子进程会得到
与板端相同的 `PermissionError: [Errno 13] Permission denied: ''`。
绝对 argv[0] 或有效 PATH 都能消除空值；板端完整环境未取得，但代码路径、空目标
异常和此机制一致。原始输出 `build/hwdecode-parity/coldboot-ab/python-executable-repro.log`。

静态 init 的 execl 使用绝对 argv[0] `/usr/bin/python3`；collector 的 snapshot
子进程也固定该路径，不依赖 sys.executable。进程创建的 OSError 写入快照和
status=error，不再让采集器无状态退出。默认不启用采集的静态 init 行为不变。

批次编排器在 ready 后另外通过 SSH 读取 boot ID、uptime、/proc/modules、lsmod
及 `/sys/module/aml_vdec_drv` 的存在与实际参数，保存独立 ready-runtime.json。
该路径不依赖早期采集器；错误与超时保留为未覆盖，不终止实验，也不跳过原归档。
既有单次/总预算保持生效，不通过额外等待改变观察分母。

## 已运行验证与边界

新增测试以空环境、裸 argv[0] 真正启动解释器并调用采集器，snapshot 子进程实际
执行并写出 fixture boot ID/status=complete；没有 mock 子进程创建。
在 Mac 和 Ubuntu ARM64 VM 均通过。另测 ready SSH 采证失败会明确标缺失，仍保存
ready/end 归档，不把样本截止时间误吞掉。

`collector-fix-host.log`、`collector-fix-linux.log`：两端工具测试各12项通过。
VM 的默认与显式 COLDBOOT_CAPTURE init 均以 static、O2、Wall/Wextra/Werror 编译；
默认 ELF 与修改前逐字节相同。主仓库全套结果随提交报告，原文另存 collector-fix-all.log。

没有访问板子。真实 PID1 启动、Python CPU 扰动、ready SSH 参数采集尚未实板验证；
任何未来窗口需重新批准、重新封包并记录新探针身份，不能复用 r60 的旧 SHA 声称修复。
