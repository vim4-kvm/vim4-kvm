# 2026-10-12：采集→编码链路与 USB gadget

**结论**：HDMI 1080p60 → vdin 硬件缩放+NV21 → vfm_cap DMA-buf → `vfmcapsrc` → 原厂 `amlvenc`（DMA-buf 输入，零拷贝）→ H.264，实测 60fps，gst 进程约 6% CPU。

**streambox 用户态没有照搬**：`libvfmcap` / `streamboxsrc` / `vfmcapsrc` 都绑定 Vulkan（Mali）把 10bit AMLY 转 NV12/P010（约 1.2 万行）。让 vdin 直接写 8bit NV21 后不需要这层，改为自写的 [vim4-kvm/gst-plugin-vfmcap](https://github.com/vim4-kvm/gst-plugin-vfmcap)（约 400 行，DQBUF → GET_DMABUF → GstDmaBufMemory，token 立即归还）。编码直接用板上原厂 `gstreamer-aml` 的 `amlvenc`（已支持 dmabuf 输入），不需要移植 streambox 的 gst-plugin-venc / libencoder。

vdin0 运行时设置（`tools/hdmi-setup.sh`，由 `vim4-kvm-hdmi.service` 开机执行）：

| `/sys/class/vdin/vdin0/attr` | 作用 |
|---|---|
| `color_depth_support 0x1` | 只写 8bit（默认 4K 走 10bit packed AMLY） |
| `no_swap_en 1` | 关闭 128bit 内 64bit 字交换 + 大端写入。默认格式是给显示层读的，CPU/编码器直接读 NV21 时每 8 字节反序（看起来像水平镜像） |
| `conversion W H 8` | vdin 硬件缩放到 W×H 并输出 NV21（`TVIN_NV21=8`） |

**修复的 bug**：

- vfm_cap：NV12/NV21 的 canvas 大小检查只算 Y 平面，每帧都被当成越界丢掉，并每帧发 SOURCE_CHANGE
- amvenc_multi（`vpu_multi.c`）：T7 上 `vpu_clk_disable()` 调的是 `vdec_poweron()` 而不是 `vdec_poweroff()`，WAVE 电源引用计数只增不减，电源域从不断电。编码中途被 kill 后 Wave521 固件卡死（`vp5xx_vcpu_status PC=0x112c` 不变），之后所有编码初始化失败，`rmmod` 重载也无效，只能重启。修复后 `kill -9` 编码进程后可立即重新编码（含 `/tmp/vpu_mutex.map` 残留）
- vfmcapsrc：分辨率变化不一定先于新帧发出 SOURCE_CHANGE，帧大小与当前格式不符时主动重新查询并重新协商

**验证**：HDMI 拔插（`hpd0 1` / `hpd1 1`）期间管线暂停，恢复后继续出帧；1080p→720p→1080p 切换，编码器随 caps 重建，输出裸 H.264 无错误（matroskamux 不支持中途改分辨率，属 mux 限制）。

**USB gadget**（`tools/kvm-gadget.sh`，`vim4-kvm-gadget.service`，替代并禁用 `usb-gadget-khadas.service` 的 adb+rndis）：

- `/dev/hidg0` 键盘（boot protocol，8 字节输入 + 1 字节 LED 输出）
- `/dev/hidg1` 绝对坐标鼠标（5 键，X/Y 0..32767，滚轮，6 字节）
- `/dev/hidg2` 相对鼠标（boot protocol，4 字节，BIOS/UEFI 用）
- `ncm.usb0`（macOS / Linux / Windows 10+ 原生驱动）
- 描述符参考 One-KVM 的 `report_desc.rs`，键盘改为带 LED 输出；用离线解析校验了集合平衡和报告长度
- 板上没有 `xxd`，描述符用 `printf '%b'` 写入（`%` = 0x25 会被普通 printf 当格式符）
