# 2026-11-04：安全媒体移植首段与运行时清点

首段只增加HDCP密钥就绪诊断，尚未完成HDCP认证、Dolby Vision或安全启动移植。
NPU已有ADLA内核兼容实现，无需再次导入厂商驱动。候选输入与复取命令见
[安全媒体输入](../../packaging/security-media/README.md)。没有更新板上内核或引导固件；
候选TA仅在独占会话探针窗口临时安装，退出删除，未保留在系统中。

## 源码与接口

VM任务`security-media-port`基于正式提交`37483692243f9aff9a9e7737f3fde74e97a14908`。
修改`drivers/firmware/meson/t7-tee.c`，在现有T7固件设备上增加按需debugfs查询；
卸载自动删除诊断目录。只查询HDCP14/22_KEY_READY，不调用LOADKEY或认证命令。

厂商依据为common_drivers提交`31619c527655514b4c89516ef609b6db1dd47db6`中的
`drivers/media/vout/hdmitx21/hdmi_tx.h`与`hw/hdcp.c`。
厂商bool接口把SMC非零返回当true；候选区分未就绪、不支持和异常返回，避免把错误码
当作密钥存在。此返回值合同仍需板上核验，不把诊断接口作为认证成功证明。

## 只读板窗

通过board-queue串行执行文件、动态库及启动日志清点，未调用新SMC或执行候选CA：

- 运行身份`7.3.1-vim4-20261104`；OP-TEE报告revision 3.8，tee-supplicant active。
- `/dev/tee0`、`/dev/teepriv0`、`/dev/adla0`存在，ADLA KMD报告1.4.0.3。
- 动态库缓存包含libteec、libnnsdk、libadla_compiler、libadla。
- `/lib/optee_armtz`仅见`526fc4fc-7ee6-4a12-96e3-83da9565bce8.ta`，未见HDCP TA；
  `/usr/bin`的tee前缀文件中未见tee_hdcp。
- OP-TEE启动日志已有PTA_CMD_GET_DEVICES错误ffff0009与RPMB扫描ret -22；
  不能据服务active认为全部安全服务可用。

## 后续实施边界

独立会话窗口已使用板上tee_client_api.h和libteec在VM编译探针，
`-Wall -Wextra -Werror`通过。核对候选TA SHA后临时安装到tee-supplicant目录，
`TEEC_OpenSession`返回`0x00000000`、origin=4；关闭会话并清理临时TA及探针。
未调用TEEC_InvokeCommand，未执行tee_hdcp，未加载密钥或触发认证。
日志保存于忽略目录`build/security-media-port/ta-window.log`。

1. HDCP：已固定官方A311D2开发TA与ARM64 CA候选，TA会话打开通过；
   仍须接tee_comm_hdcp通知、DRM content protection与认证/失锁/热插拔状态机。
   不能创建仅返回成功的通知设备，也不能把KEY_READY映射成DRM ENABLED。
2. Dolby Vision：厂商amdv.c提供register_dv_functions入口，但已查源码中未找到
   对应算法提供者；Dolby音频库不能代替。算法ABI与可用二进制仍是实际依赖。
3. 安全启动：本地U-Boot的fip/t7已有打包、密钥生成与签名工具，下一步是离线
   验证签名链与内核验证入口。Linux固件诊断不是Boot ROM至内核的信任链；
   本次不烧熔丝、不替换BL31/BL32。
4. NPU：保留现有已验运行库；官方转换工具可获得，但模型转换到现有SDK的完整
   回归尚未完成。现有推理证据仍以[ADLA合同](../npu-adla.md)为准。

## 离线验证

新增固件对象W=1编译、strict checkpatch及完整Image/dtbs/modules构建通过。
全量构建包含未改动ADLA文件的fallthrough和函数声明告警，未据此声称零告警。
主仓unittest共512项、10项跳过，其余通过；候选下载SHA核验通过。
没有运行内核KUnit或启动新内核，新增SMC诊断入口未上板；TA会话实测不替代这些门禁。
原始构建和测试日志位于忽略目录`build/security-media-port/`。
