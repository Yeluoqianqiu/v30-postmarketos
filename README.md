# V30 postmarketOS

LG V30 US998 的 postmarketOS 纯 TTY 集成方案：横屏文字控制台、Wi-Fi、蜂窝数据、IMS 通话音频、短信收发及充电保护。

Source, configuration and bring-up notes for a headless postmarketOS phone on the LG V30 US998.

本项目建立在 **postmarketOS、Linux 和 ShapeShifter499 的 V30 主线移植**之上，IMS 协议与媒体实现来自 **Catcrafts imsd**。感谢这些项目及其维护者提供的基础工作；我们的主要增量是版本组合、启动与资源生命周期集成、特定互通修复及实机验收。详见[上游与致谢](ACKNOWLEDGEMENTS.md)和[来源与许可证](PROVENANCE.md)。本仓库由独立贡献者维护。

## 当前状态

已在一台 **US998 / 中国联通** 上验证以下范围（2026-10-31）：

| 功能 | 实际结果 | 尚未覆盖 |
|---|---|---|
| 纯 TTY | 横屏、大字、tmux 状态栏，保留正常登录认证 | 长期交互体验、其他 V30 型号 |
| Wi-Fi / 蜂窝数据 | 自动启动及绑定蜂窝接口的 DNS/HTTPS 验证 | 长期在线、所有运营商 |
| IMS 通话 | 真实呼出及呼入；默认开机后约 60 秒呼入，用户确认双向人声清楚；挂断后混音器恢复、PCM 关闭 | 长通话、保持/转接、完整媒体重协商、紧急呼叫 |
| 短信 | 短中文收发各一条；重启后收件保留且不重复 | 真实长短信、长期存储管理、存储满恢复 |
| 充电 | 75–80% 滞回、温度保护；抑制充电时保留 USB 供电 | 完整长周期与电池寿命结论 |
| 蓝牙 | 本方案选择开机关闭 | 此偏好不代表上游蓝牙不能使用 |

完整证据范围见[验收记录](docs/validation.md)。这些结果对应锁定的旧内核方案，不自动适用于最新主线分支。

## 两套版本资料

- **已实测组合**：`baseline/kernel/`、`runtime/`、`patches/imsd/`，版本写在 [sources.lock.json](sources.lock.json)。内核基线为 `1b42626…`，本地 release 为 `7.2.0-rc2-v30-r30`，配合麦克风 MCLK 路由及 r35/r36 用户态。
- **提交上游的候选**：`patches/current-kernel/`，对应[内核 PR #12](https://github.com/ShapeShifter499/linux-lg-v30-joan/pull/12)的新基线 `dc9c669…`；只有目标对象构建验证，尚未启动实机。用户态参考另见[上游 PR #11](https://github.com/ShapeShifter499/lg-v30-port/pull/11)。

旧内核快照保留了构建该实测组合所需的诊断参数/兼容 ABI。它与清理后的上游候选分别存放，不应混用。`runtime/voice` 中的内核和硬件门禁仍然保留。

## 从哪里开始

1. 阅读[架构与文件对应](docs/architecture.md)。
2. 按[构建与安装](docs/build-and-install.md)准备锁定源码、自己的固件与设备配置。
3. 按[验收与回退](docs/validation.md)逐项核对；服务不会自动拨号、接听、发送或重试短信。
4. 根据[上游关系](docs/upstream.md)区分已有工作、我们的增量与尚待投递的补丁。

仓库提供源码、配置、构建辅助及重建步骤；设备固件、基底 boot/initramfs、账号凭据和分区 UUID 由使用者自行准备。这里没有整机镜像、私钥、原始短信、SIM 状态、私人备份或实际测试号码。

## 本机检查

需要 Python 3.12+，Linux 的完整隔离测试还需要 PyGObject/Gio、D-Bus 和 util-linux：

```sh
python3 scripts/check.py
# Linux root，合成 ModemManager；不会向真实手机发短信：
unshare --net -- dbus-run-session -- sh -c \
  'export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; exec python3 "$1"' \
  qa runtime/sms/bench_private_bus.py
```

## 许可证与贡献

自有用户态代码和文档使用 GPL-3.0-only；Linux 内核补丁遵循所修改文件的 GPL-2.0 等原许可证。原有版权声明和补丁作者保留，具体见 [PROVENANCE.md](PROVENANCE.md)。

欢迎按[贡献说明](CONTRIBUTING.md)提交修复，尤其是新内核组合验证、短信边界和资源清理。对外发布的硬件结论应标出准确版本及实测范围。

Assisted-by: Codex:OpenAI/GPT-6
