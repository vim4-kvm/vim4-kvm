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

`ta-session-probe.c`默认只执行TEEC初始化、打开指定HDCP TA会话、关闭会话。
显式指定`--load-tx-keys`时才调用TA的既有TX密钥加载接口，分别报告1.4和2.2的
结果与错误来源，任一失败返回非零。不会输入或输出密钥材料，不操作RX或发起认证。
用目标系统的头文件和运行库在Linux构建：

```sh
cc -Wall -Wextra -Werror ta-session-probe.c -lteec -o ta-session-probe
```

探针需由tee-supplicant找到匹配TA；TA安装与试验须在独占板窗中进行。
默认探针成功仅说明TA加载和会话打开通过，不证明密钥加载、认证命令或HDMI链路通过。
本板TX密钥加载实测均返回TA的ITEM_NOT_FOUND；不能据此区分缺少密钥、配置
或安全存储对象，更不能自动生成或替换厂商密钥。官方CA会在密钥加载失败后返回0，
因此不得以其进程退出码作为验收门禁。

候选清单还包含独立Provision TA及`libprovision.so`。`provision-query.c`通过
该库的只读查询API检查HDCP TX对象，只输出结果码及成功时的存储类型/长度，
不读取密钥材料、不调用store/delete。目标系统需具备libteec及匹配Provision TA：

```sh
cc -Wall -Wextra -Werror provision-query.c -ldl -o provision-query
./provision-query /path/to/libprovision.so
```

本板在临时补齐Provision TA后仍找不到两个TX对象；文件访问跟踪确认
tee-supplicant能够打开`/tee/dirf.db`。这不是目录缺失的证据，也不能证明
其他固件/旧unifykey命名空间中绝无密钥。补齐软件依赖不等于完成设备密钥配置。

NPU的现有ADLA兼容驱动与SDK验收见[ADLA合同](../../docs/npu-adla.md)。
官方[转换工具](https://github.com/khadas/vim4_npu_sdk)可获得，完整转换链仍需单独验证；
不能把SDK闭源等同于SDK不可获得。
