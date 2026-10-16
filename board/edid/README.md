# 已验证的自定义 EDID

`rtk-uhd-hdr.bin` 是从用户连接的 RTK UHD HDR 物理显示器读取的完整
256 字节 EDID，未经字段修改。SHA256：
`32c6a60823dd676e848f8423feff1b469d07f5bac52885723dfa70b74cfda33d`。

2026-10-15，在 Mac M4、macOS 27.0.1 上，经 VIM4 输入两次验证 Apple
Screen Sharing 高性能会话退出后自动恢复；实际协商为 4K60 YUV444 8bit。
没有验证该表声明的全部模式、HDR 或所有主机。它是可复现的自定义配置，
不是已替换的系统默认预设。对照记录见 [上板记录](../../docs/bringup/2026-10-15-screen-sharing-desktop-not-restored.md)。

板级助手 vim4-edid 内置同一张表作为 `RTK-CONTROL` 预设，NanoKVM、One-KVM
与 JetKVM 菜单中显示为 RTK UHD HDR 4K60；vim4-manager 仍用本文件的安装副本。
`apply RTK-CONTROL` 只接受与内置表一致的数据。

加载并保存到板级配置（会重新协商 HDMI）：

```sh
ssh vim4 'sudo -n /usr/libexec/vim4-edid preset RTK-CONTROL'
```

恢复厂商默认表：

```sh
ssh vim4 'sudo -n /usr/libexec/vim4-edid preset VIM4-4K60'
```

NanoKVM 使用板级共享 EDID 配置；One-KVM 通过同一助手修改它，PiKVM
沿用板级输入。JetKVM 有独立保存的 EDID，启动时会加载，不能仅写板级
配置就假设四套应用切换后都保持同一张表。

当前开发板的 JetKVM 独立配置也已同步此表：
`/var/lib/jetkvm/config.json` 的 `hdmi_edid_string` 为本文件的十六进制内容。
这属于该板保存的自定义配置；没有修改 JetKVM 内置默认预设。同步时 JetKVM
处于停止状态，先备份配置再原子替换，只改该字段；不要覆盖运行中应用的配置。
JetKVM 的 edid-apply 助手返回 loaded=false，确认与当前接收端加载的表一致。
尚未进行应用切换或重启验收。
