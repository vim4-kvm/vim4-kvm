# 安全媒体候选输入

这里只固定待验证输入，不随系统镜像安装。HDCP CA/TA来自Khadas官方仓库；
目录名A311D2不能证明TA签名与任意BL32兼容，也不证明板内已有HDCP密钥。
本板OP-TEE 3.8的会话打开已通过，范围见[实测记录](../../docs/bringup/2026-11-04-security-media-port.md)。

在仓库根下载并核验：

```sh
python3 packaging/ubuntu/fetch.py packaging/security-media/hdcp-candidates.json build/hdcp-candidates
```

ARM64 CA依赖`libteec.so.1.0`，通知接口为`/dev/tee_comm_hdcp`；
RX固件处理还引用厂商HDMIRX sysfs。当前7.3不能直接运行该程序并宣称支持HDCP。
必须先核对TA加载、通知接口和DRM content protection认证状态机；不能用空实现
返回成功绕过通知，也不能将密钥就绪报告为认证成功。

候选内核的`meson_t7_tee` debugfs目录提供只读`hdcp14_key_ready`和
`hdcp22_key_ready`，按需调用厂商已使用的SMC。0表示未就绪，1表示就绪；
不支持返回EOPNOTSUPP，其他异常值返回EIO。此查询不读取密钥、不加载TA、
不启动认证。它尚未经过本板实测，不能据离线构建认定安全固件支持。

`ta-session-probe.c`只执行TEEC初始化、打开指定HDCP TA会话、关闭会话；
不调用TEEC_InvokeCommand。用目标系统的头文件和运行库在Linux构建：

```sh
cc -Wall -Wextra -Werror ta-session-probe.c -lteec -o ta-session-probe
```

探针需由tee-supplicant找到匹配TA；TA安装与试验须在独占板窗中进行。
成功仅说明TA加载和会话打开通过，不证明TA的密钥加载、认证命令或HDMI链路通过。

NPU的现有ADLA兼容驱动与SDK验收见[ADLA合同](../../docs/npu-adla.md)。
官方[转换工具](https://github.com/khadas/vim4_npu_sdk)可获得，完整转换链仍需单独验证；
不能把SDK闭源等同于SDK不可获得。
