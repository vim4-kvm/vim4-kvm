# 2026-10-30：7.3 kbase 离线候选

结论：固定r44p0 JM UK11.39已在正式7.3基线的完整构建输出上生成外部模块，
W=1、KCFLAGS=-Werror及modpost通过。没有加载模块或连接板子，功能/性能未验。
GLVND EGL vendor注册被blob缺少__egl_Main阻断，不能声称用户态共存目标已全部完成。
设计、API变化、许可证、成本及30分钟清单见[维护方案](../gpu-kbase-7x.md)。

## 固定环境与产物

- VM：OrbStack vim4-build，Ubuntu24.04 ARM64，通过orb本地执行；没有SSH到板子。
- 厂商源码：~/src/linux@80a07ad5406d57855c996285ae75a50a1b9147ae。
- 独立内核：~/src/linux-7.3-kbase，gpu-kbase-7x，基于f71b5c6289cb3254690e57292327e73514f0715f。
  候选DTS本地提交6cdf7ffd90387；无默认DT/内核代码变更。
- 外部构建使用~/build/uhd3完整输出，build/source同为上述正式提交；只读既有Image/config/symvers，
  外部.o/.ko生成在私有source目录。未重新构建Image，也不声称做过完整内核重建。
- 最终干净导出复现目录：~/build/kbase-7x/checked；包含build.log、manifest.json、
  abi-{vendor,candidate}.txt、modinfo.txt、candidate.dtb和stage模块片段。
- 另有候选DTS继承display-m0，在独立worktree提交；正式DT、启动项、部署锁保持原样。

| 输入/输出 | SHA256 |
|---|---|
| Image | 9daea7a17e228cb5ef93b6b9cc926ccce43ec3b8eafb1b22aee447fdcfcb7000 |
| .config | 90eed7736b33a57ed65e6db99aff657e7f6fad1116ee79e9ad6c952b6904a53d |
| Module.symvers | 588ebf28bebc42e4b2cb650dafdca2132291d303d7ad3ce91d87f01f7d2824d2 |
| mali_kbase.ko | 86ff4a3482617909ae59164c85f9de5f93c52c77ff24b9e2e0423258002331ee |
| 源码补丁 | df7c7fa01961bec507b67dcdd7ee03d23d6e73a66f1634a1e65dfa432cf6cc28 |
| ABI记录 | 98b864242a760fae1c20fa6a44254549cd4837d0fd51151887309d63bd19e43a |
| 保留display-m0 DTB | 6e69635a251ff9e2163384cd757d1d204e492d8e2b0fd68a9dbc1c992d1d62eb |
| 保留DTB修改的候选 | 393c32e053572395b89ce4eed04ba6791ce2d4acfa4d865dc2c1de7beee79149 |

## 离线检查边界

1. 固定git archive→应用提交补丁→全新目录编译。完整build.log无warning/error，
   modpost解析322个外部引用，无未解析符号；模块depends为空，无厂商thermal依赖。
   原memory_group_manager softdep已移除，未设置外部manager时走native实现。
2. modinfo：GPL、r44p0-01eac0 (UK version 11.39)、
   `7.3.0-vim4kvm-uhd3+ SMP preempt mod_unload aarch64`，只匹配候选compatible；保留BTF生成。
3. 全部UAPI头逐字节等于固定5.15源码；相同ARM64宿主编译器编译两份UAPI探针，
   34个可见ioctl payload sizeof/alignof与40个ioctl编码完全相同。
   不覆盖32位compat，也不验证运行时协商和ioctl内部语义。
4. 候选DTS预处理/dtc成功，有3条既有板级警告（pinctrl unit_address_vs_reg、simple_bus_reg，
   vpu/video-capture unique_unit_address）。并非全schema零诊断。
   独立DTS提交strict checkpatch有1条“新增文件是否更新MAINTAINERS”通用提示，无error/check。
5. 锁定私有blob仅本地readelf：NEEDED和GBM/Vulkan/CL导出见方案；无__egl_Main。
   没有发布blob，没有全局ICD/库覆盖，没有修改board/vim4-kvm-run正式行为。
6. 保留DTB与候选的dtc排序反编译diff仅有compatible替换和mali-supply删除，
   其余属性/phandle相同。主仓离线unittest共315项、8项跳过，无失败；两份Python入口语法检查通过。
7. 外部源码补丁strict checkpatch：0 errors、28 warnings、9 checks；包括外部兼容层必要的
   LINUX_VERSION_CODE提示、版本比较、宏/回调声明和对齐风格，尚未做到checkpatch全绿。
   W=1编译无告警与此风格检查是不同结论。

提交候选DTS后，再以最终build.py完成delivery目录全新构建，ABI/DT输入哈希相同，
module SHA256为a6a3b71c1b7e7cf459175b6cffffd35c1bad992f39ec0581f92753cec2587aa3。
模块带构建目录调试/BTF信息，换输出目录哈希可变；本轮证明可重建，没有证明逐位可复现。

模块加载、/dev/mali0、时钟/reset/secure域时序、设备查询、shader/CL、dma-buf/fence、
thermal和HDMI/Wave5并行均未运行。编译无法消除旧DDK内存生命周期风险；
本候选保持外部域active，不能拿此前Panfrost runtime suspended结果为它背书。
版本API变化和完整测试结果以本记录与主仓提交为准，不代表正式部署完成。
