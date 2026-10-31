# V30 postmarketOS

**简体中文** | [English](README.en.md)

面向 LG V30 US998 的非官方、实验性 postmarketOS 集成项目与重建说明，采用横屏 TTY 文本界面。

本项目建立在 **postmarketOS、Linux 和 ShapeShifter499 的 V30 主线移植工作**之上。IMS 协议与媒体实现来自 **Catcrafts imsd**。我们的新增工作包括组件集成、开机顺序、每次通话的音频资源管理与清理、短信持久化、部分互操作修复，以及限定范围的验证。上游贡献与许可证信息见[致谢](ACKNOWLEDGEMENTS.md)和[来源记录](PROVENANCE.md)。

**验证结论仅适用于具体版本与测试范围。** 历史 r35/r36 结果来自一台使用中国联通网络的 US998。公开重建工具及后续打包、路径和语言调整仅经过主机端验证。完整公开源码尚未在干净设备上重新完成端到端部署；较新内核候选也尚未在实机启动。Ready for review 仅表示 PR 已进入可评审阶段，不代表上游接受或实机验收通过。

我们的已完成工作及其上游基础集中记录在[贡献说明](docs/contributions.md)中；服务器稳定性、振铃与显号、短信完善及后续验证工作见 [TODO／路线图](TODO.md)。每项待办均附验收条件，在取得证据前保持未完成状态。除本中文 README 外，其余项目文档和命令行消息目前为英文。

## 验证概况

下表汇总截至 2026-10-31（亚洲／上海时区）的历史观察，包括更早的充电控制检查：

| 组件 | 历史实机证据 | 仅主机端检查及待验证范围 |
|---|---|---|
| TTY 界面 | 横屏文本控制台、较大字体、tmux 状态栏与正常登录认证 | 公开版本的字体路径和暂存安装调整仅在主机端验证；长期交互及其他机型尚未验收 |
| Wi-Fi 与蜂窝数据 | 开机集成，以及绑定蜂窝接口的 DNS／HTTPS 检查 | 长期联网与其他运营商尚未验收 |
| IMS 语音 | 较早的一次呼出；RAM 启动与普通默认启动后分别进行了约 60 秒呼入，用户确认双向人声清楚；检查了混音器／PCM 清理 | 公开源码重新部署、长通话、保持／转接、完整媒体重协商及紧急呼叫尚未验收 |
| 短信 | 一条短中文短信发送成功并由收件人确认，一条接收成功；普通重启一次后归档保留且未重复提交发送 | 实际长短信分段、长期存储和磁盘写满恢复尚未验收 |
| 充电限制 | 较早的实机检查验证了禁止充电时仍保留 USB 输入供电 | 75%／80% 迟滞与温度／传感器决策仅经过逻辑模拟；实际温度异常处理及完整物理充电周期尚未验证 |
| 蓝牙策略 | 已测试的本地配置中蓝牙保持关闭 | 此策略需明确选择启用；新打包的最终关闭服务仅经过主机端检查 |

限充策略保留既有硬件保护机制；本项目不提供电池安全或使用寿命认证。证据边界见[验证与恢复说明](docs/validation.md)。

## 版本路线

- **历史 r35/r36 重建输入：** 位于 `baseline/kernel/`、`runtime/` 和 `patches/imsd/`，固定版本见 [sources.lock.json](sources.lock.json)。旧内核基于 `1b42626…`，本地版本为 `7.2.0-rc2-v30-r30`，包含麦克风 MCLK 路由与 r35/r36 用户空间。后续公开版本的调整不能直接沿用历史实机通过结论。
- **较新的上游候选：** 位于 `patches/current-kernel/`，对应[内核 PR #12](https://github.com/ShapeShifter499/linux-lg-v30-joan/pull/12)，基于 `dc9c669…`。四个受影响目标文件已编译，但尚未构建完整内核镜像或在实机启动。[工具集 PR #11](https://github.com/ShapeShifter499/lg-v30-port/pull/11)公开短信工具和带版本限制的语音参考实现。截至 2026-10-31，两个 PR 均为 Ready for review，尚未合并。

历史快照保留了解释旧软件栈所需的诊断参数与兼容接口，应与清理后的上游补丁系列区分使用。`runtime/voice` 中的内核与硬件兼容性检查仍然保留。

## 开始使用

1. 阅读[架构与组件说明](docs/architecture.md)。
2. 按[构建与安装指南](docs/build-and-install.md)操作，并自行提供固件和设备配置。
3. 新部署时使用[验证与恢复清单](docs/validation.md)。通话和短信测试需要操作者明确执行。
4. 阅读[上游状态](docs/upstream.md)，区分上游已有修复、我们的变更和尚未向对应上游提交的补丁。

仓库包含源码、配置、构建辅助工具与重建说明。固件、已知可用的基础 boot／initramfs、凭据和文件系统 UUID 由操作者提供。仓库不包含整机镜像、私钥、原始短信归档、SIM 状态、私人备份或实际测试号码。

## 主机端检查

使用 Python 3.12 或更新版本。完整的 Linux 隔离测试还需要 PyGObject／Gio、D-Bus 和 util-linux：

```sh
python3 scripts/check.py
# Linux root: synthetic ModemManager on a private bus and network namespace.
unshare --net -- dbus-run-session -- sh -c \
  'export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; exec python3 "$1"' \
  qa runtime/sms/bench_private_bus.py
```

英文文档和命令行消息不会移除 Unicode 支持：测试中的合成中文／UCS2 载荷仍以转义字面量保留。

## 许可证与贡献

原创用户空间代码与文档采用 GPL-3.0-only。内核补丁保留被修改文件的许可证，包括 GPL-2.0。既有版权声明与补丁作者信息均予保留，详见 [PROVENANCE.md](PROVENANCE.md)。

欢迎按[贡献指南](CONTRIBUTING.md)参与。每项硬件结果都应注明准确版本和实际观察范围。

Assisted-by: Codex:OpenAI/GPT-6
