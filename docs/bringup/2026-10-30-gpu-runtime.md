# 2026-10-30：私有 Mesa 26.2.6 离线运行时

结论：第二轮采用官方最新稳定发布26.2.6，系统Mesa25.2.8保留作对照。
所有构建/验证仅在开发机Docker ARM64执行，未连接板子、安装、重启或运行板上负载。
固定电压与厂商Linux路径一致，非功能缺口；闭源固件是否另行调压仍未证。
用户已认可内核thermal候选`d2cd4c6c981e9`，本轮不修改内核或kernel-edge配置。

## 版本和边界

官方[发布页](https://mesa3d.org/news/)于2026-10-28发布26.2.6，
[发布说明与SHA256](https://docs.mesa3d.org/relnotes/26.2.6.html)核对得到
`b9436b3e1a8be76fbd4823dc884f90596ab7c6ac5e1867a305e66ffccfb31a92`。
下载输入固定在[downloads.lock.json](../../packaging/gpu/downloads.lock.json)。
[26.2.0说明](https://docs.mesa3d.org/relnotes/26.2.0.html)含PanVK扩展及编译器改进，
但并不承诺所有新增扩展适用于G52；Rusticl的OpenCL3.1公告也没有列Panfrost。
选择最新稳定修复版本以验证当前上游路径，不据总API版本宣称G52支持已提升。
实际G52设备版本、扩展与产品性能仍需批量窗口记录。

## 可复现构建入口

[Dockerfile](../../packaging/gpu/Dockerfile)扩展现有Ubuntu builder，固定基础镜像内容标签、
Ubuntu20261012快照，安装LLVM19/translator/libclc、Rust/bindgen0.71.1、Meson1.9.2。
联网准备时，Mesa Rust wraps按源码中SHA验证并缓存，导出包清单及wrap缓存哈希。
现有基础镜像生成方法为`packaging/ubuntu/Dockerfile`，禁止用同名但不同ID的镜像替代封存输入。

```sh
python3 packaging/ubuntu/fetch.py packaging/gpu/downloads.lock.json build/gpu-runtime
docker build -t vim4-gpu-builder:26.2.6 -f packaging/gpu/Dockerfile packaging/gpu
docker image inspect vim4-gpu-builder:26.2.6 --format '{{.Id}}'
# 将输出image ID记录到封存清单后，用该ID而非可变tag运行：
docker volume create vim4-gpu-runtime26
docker run --name vim4-gpu-offline --network none \
  -v vim4-gpu-runtime26:/output -v "$PWD:/repo:ro" \
  -v "$PWD/build/gpu-runtime:/inputs:ro" BUILDER_IMAGE_ID \
  bash /repo/packaging/gpu/build.sh
```

运行[build.sh](../../packaging/gpu/build.sh)时Meson禁止wrap下载，启用Panfrost Gallium、
PanVK、Rusticl、单元测试和drm-shim；libclc SPIR-V及OpenCL头文件静态封装，
避免板上依赖builder的LLVM资源路径。私有前缀为`/opt/vim4-mesa-26.2.6`。
[package.py](../../packaging/gpu/package.py)递归收集ELF依赖并设置相对RUNPATH，
验证依赖闭包、拒绝未解析依赖及动态段builder路径，改写ICD JSON到私有绝对前缀。
glibc/loader由目标Ubuntu24.04提供，其余依赖随包。manifest包含逐文件SHA256。
封存builder镜像ID、完整包清单、wrap哈希和源码锁足以复跑；尚不声称两次独立构建字节相同。

## 统一能力和基准脚本

[gpu-compare.py](../../tools/gpu-compare.py)在三套栈下使用同一探针和工具：

```sh
python3 /opt/vim4-mesa-26.2.6/bin/gpu-compare.py vendor --output /var/tmp/gpu-vendor
python3 /opt/vim4-mesa-26.2.6/bin/gpu-compare.py system --output /var/tmp/gpu-system
python3 /opt/vim4-mesa-26.2.6/bin/gpu-compare.py private --output /var/tmp/gpu-private
```

vendor模式只接受5.15，私有libmali通过该进程LD_PRELOAD和Vulkan/CL ICD选择；
system模式优先系统库且清除继承的私有ICD/实验开关；private模式选择包内GLVND JSON、
DRI、Vulkan、Rusticl并仅对其子进程启用G52实验开关。
探针输出EGL/GLES版本、vendor、renderer和扩展，固定512×512 pbuffer、128次片元循环、
glFinish计帧和中心像素回读。拒绝把非Mali-G52的软件渲染结果算通过。
vulkaninfo和clinfo保存完整设备版本/扩展；clpeak与vkmark来自同一固定Ubuntu快照，版本在包清单中。
vkmark需要可用显示后端；无后端或权限失败会原样保留，不能算Vulkan离屏通过。
脚本不停止服务、不修改governor、不写电压、不操作HID或声音。
每个能力命令40秒超时，基准120秒超时，超时TERM后5秒KILL进程组；结果写入新目录JSON。

## 与 NPU 合并的批量窗口

先取板锁、确认源/服务/温度和版本哈希；5.15保持默认，7.3通过一次性启动候选进入。
GPU与NPU性能测试顺序执行，不能并发占用DDR后仍当作配对基准。

| 项目 | 估时 | 记录 |
|---|---|---|
| 5.15 vendor能力/固定负载 | 4–7分钟 | API版本、扩展、renderer、像素、吞吐，失败项单列 |
| 一次性7.3启动及核对 | 2分钟 | Image/模块build ID、GPU四核/温区、NPU候选版本 |
| 7.3 system、private两套 | 各4–7分钟 | 相同工具/负载/尺寸，API差距与吞吐原始值 |
| GPU五档、thermal/runtime PM | 各3–5分钟 | 复用[首轮清单](../gpu-parity-plan.md)，固定电压只读核对 |
| HDMI/Wave5并行GPU | 8分钟 | 帧序、像素、丢帧、CMA/fence/内核错误；不发HID、不测声音 |
| NPU项目、恢复5.15 | 按NPU清单＋2分钟 | 先结束GPU负载再执行NPU单项；正常重启回默认 |

GPU部分约30–45分钟，单项均≤10分钟；未触发真实thermal trip就记该项未验。
没有相同硬件API/后端时记录阻塞，不能据软件fallback分数推导性能追平。

## 本轮离线结果

- 无网络编译Panfrost Gallium、PanVK和Rusticl成功。Meson测试51通过、0失败、6跳过；跳过项为Rusticl生成绑定/过程宏等测试入口，未将它们算作通过。
- 上游编译有6处忽略read/write/fread/asprintf返回值的warning，另有Meson add_languages native参数warning；未修改上游源码去掩盖诊断。
- 51个ELF完成依赖闭包检查；glibc/loader由目标系统提供，其他动态依赖随包，动态段无`/output`或`/opt/rust`路径。
- EGL/Vulkan JSON及OpenCL ICD均指向`/opt/vim4-mesa-26.2.6/lib`，库文件存在；不是全局注册。
- [compiler-check.sh](../../packaging/gpu/compiler-check.sh)在无网络容器通过：PAN_GPU_ID=0x7402、禁用shader cache，实际生成vertex/fragment NIR和Bifrost clauses，识别G52 r1 MC4。noop无真实执行，中心像素为黑色、探针退出1是预期，只证明编译路径，不证明像素、硬件API或性能。
- 初次打包因stage库解析路径及JSON-lines测试日志被误当ICD解析而失败；修正后重新执行依赖检查/打包成功，没有重跑已经通过的Mesa单元测试。

| 交付物 | SHA256 / ID |
|---|---|
| builder镜像 | `sha256:f5629bfab710550760fe34b7d3abd058fbcb707d78b142b6c7614cea528355fc` |
| builder包清单 | `eb43e5cdac381020683d2390cd6ce4e9461eb2e35e6c4aa6ae59e5fbda3d991a` |
| Rust wrap缓存哈希清单 | `7d74de014e78d79ac507127160167697b5e5a4df9e5395bfb200dd43fe52093d` |
| mesa-26.2.6-arm64.tar.xz | `bab31ffcb5b71b2c3bc699cb552cc556696fb1ee897322b93a5d28a988ad4807` |

归档、manifest与原始日志位于主仓忽略目录`build/gpu-runtime/`；Linux构建输出保留在
Docker volume `vim4-gpu-runtime26`。输入封存在[builder.lock.json](../../packaging/gpu/builder.lock.json)。
归档内部`share/build-proof`保留包清单、wrap哈希、builder锁、Meson选项与testlog；
`manifest.json`列每文件SHA256（自身除外）。源码许可证和工具copyright随包保留。
脚本4项隔离/失败传播单测通过；主仓完整测试301项、7项跳过、无失败。
另在不含builder依赖的干净Ubuntu24.04容器中，仅挂载stage重新执行ldd，
全部探针、库和vkmark插件无未解析依赖；此验证也使用`--network none`。
