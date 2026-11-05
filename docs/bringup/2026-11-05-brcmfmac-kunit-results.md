# 2026-11-05：brcmfmac P2P 测试迁移结果

> 本页保留原验证时的 SHA。修订后的对应、完整提交检查与当前利用率修复边界见
> [审查返工记录](2026-11-05-kunit-review-rework.md)。

先合入已审 `debug-splat-fixes`，保留其四个提交，内核 merge 为 `c34249a0729e6`。
风险清单主仓库 `7c39e36` 先行，见 [other-2](2026-11-05-kunit-inventory-other-2.md)。
内核 `11ef9a271b306` 删除唯一剩余 `test_p2p.py`，新增独立 `p2p_kunit.c`、
Kconfig/Makefile/测试配置及私有可见性声明；firmware 解析器和已有测试没有重写。

arm64 QEMU 实际 5/5：新 `brcmfmac-p2p-params` 两项，复用已有
`brcmfmac-nvram` 三项。NVRAM 三项直接来自 `496597ebdf195`，不重复编写，
也不将其结果当作 P2P 生命周期已覆盖，原修复说明见
[启动 splat 记录](2026-11-05-debug-splat-fixes.md)。

新测试直接调用真实生产代码：

- `brcmf_scan_params_v2_to_v1()`：0–64 信道、0–2 SSID，验证奇/偶信道后的 SSID
  对齐与尾数组、参数保持、输出尾边界；使用驱动真实 wire 类型，不抽源码或
  重建 cfg80211，也不假装直接转换证明完整 P2P firmware 请求版本选择通过。
- `brcmf_wcc_feat_update()`：AUTO 在合资格 capability 下选 credit，显式模式
  不被覆盖；查询失败/缺少 capability 保留默认，SAE feature_disable 生效，
  无关 feature 不丢失。使用真实 drvr/settings 类型，不模拟固件响应函数。

scan 转换函数体未变，只增加条件导出。WCC 只把查询后的两段决策原位提为函数：
芯片早退、固件版本资格、quirk 发布仍在原处，`cap` 查询仍先于该决策，错误及
字符串条件顺序不变。未改变固件调用、MMIO、锁、分配或扫描状态更新顺序；
KUNIT=n 时不导出测试接口。

在 VM `/home/deepdream/src/linux-7.3-kunit-migration`，持主仓库 heavy 构建票，
`out=$PWD/.kunit-brcmf`，实际核心命令：

```sh
python3 tools/testing/kunit/kunit.py run 'brcmfmac*' --arch arm64 --jobs 8 \
  --timeout 180 --build_dir "$out" \
  --kunitconfig drivers/net/wireless/broadcom/brcm80211/brcmfmac/.kunitconfig \
  --json="$out/result.json"
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse \
  -j8 drivers/net/wireless/broadcom/brcm80211/brcmfmac/
# 驱动及两个测试 m；KUNIT=n 对照分别完整构建，使用匹配的符号表：
make O="$out" ARCH=arm64 -j8
dir=$PWD/drivers/net/wireless/broadcom/brcm80211/brcmfmac
make O="$out" ARCH=arm64 M="$dir" clean
make O="$out" ARCH=arm64 W=1 C=2 \
  CHECK=/home/deepdream/build/hwdecode-parity-tools/sparse/sparse -j8 M="$dir" modules
scripts/kernel-doc -none drivers/net/wireless/broadcom/brcm80211/brcmfmac/wcc/kunit.h \
  drivers/net/wireless/broadcom/brcm80211/brcmfmac/firmware.h
git diff --cached -- drivers/net/wireless/broadcom/brcm80211/brcmfmac | \
  scripts/checkpatch.pl --strict --no-tree --ignore FILE_PATH_CHANGES -
```

内建、独立测试模块、KUNIT=n 模块 W=1/有效 sparse 完成，范围无诊断；跨配置
清理自身模块产物并确认实际 CC/CHECK。WCC 在原有独立 vendor 模块中时，也实际
链接了测试依赖；测试模块仅编译，未另做加载验证。nm 确认 KUNIT=n 的 brcmfmac
及 WCC 模块没有三个测试导出。VM 保存 builtin.config、module.config、
production.config、test.log、result.json，QEMU 启用 generic KASAN。

strict checkpatch 最终零 error/warning/check；仅 FILE_PATH_CHANGES 人工核对
原有 MAINTAINERS 范围后忽略。新私有头及合入的 firmware.h kernel-doc 无诊断。
sparse 固定 `84ec0658c81db4ccc4aabc420d3dc118c2c6a310`；准备阶段未修改 vDSO
声明诊断保留，不宣称全树零诊断。未改 binding/DTS；smatch 不可用。

主仓库 `build/kunit-migration/` 原始输出：`brcmf-run.log`、`brcmf-gates.log`、
`brcmf-commit.log`、`deferred-style-initial.log`（初次样式失败保留）、
`deferred-style-final.log`；完整实际构建命令 `brcmf-gates.sh`。
最终全套 QEMU 重跑在完成全部迁移后另记，不用编译替代运行。
本记录主仓库全测 `main-tests-brcmf-results.log`：539 项、14 skipped、OK。

V/B/F 全部待实板：nl80211/P2P 完整 scan V1/V2 请求、firmware/discover 和内存
失败不得置 BUSY；discovery 销毁/重建和 wsec；已连接 STA/APSTA 不中断及失败时
仍尝试 UP；芯片/固件资格与真实 cap 返回；ARP/ND radio 控制的 primary 路由、
group 地址表、AP gate、IPv6 表的 clear/add、v1 ABI/填充/真实数据和 clear 失败
不得继续 add。后续以实际固件、标准无线/IPv6 接口和抓包、标准故障注入验证。
本轮未访问板子、请求固件或运行真实无线测试，删除不等于这些风险通过。
