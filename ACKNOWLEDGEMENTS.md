# 上游与致谢 / Acknowledgements

感谢上游维护者长期进行的移植、驱动、协议和发行版工作。没有这些基础，本项目的集成与验收无法完成。下面同时记录依赖和参考的实际用途，不将上游成果重新归为本项目原创。

| 项目 / 贡献者 | 链接 | 在本方案中的作用 |
|---|---|---|
| postmarketOS 社区 | [postmarketos.org](https://postmarketos.org/)、[pmbootstrap](https://gitlab.postmarketos.org/postmarketOS/pmbootstrap)、[pmaports](https://gitlab.postmarketos.org/postmarketOS/pmaports) | 系统、设备包、构建工具与包管理基础 |
| Linux / Qualcomm 主线贡献者 | [Linux](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/) | MSM8998、网络、音频、电源、控制台等驱动基础 |
| ShapeShifter499 / Lance 及其合作者 | [lg-v30-port](https://github.com/ShapeShifter499/lg-v30-port)、[linux-lg-v30-joan](https://github.com/ShapeShifter499/linux-lg-v30-joan)、[pmaports-lge-joan](https://github.com/ShapeShifter499/pmaports-lge-joan) | V30 主线内核、设备树、硬件支持、打包与 bring-up 证据；本项目从这些基础继续集成 |
| Catcrafts 及 imsd 贡献者 | [imsd](https://forgejo.catcrafts.net/Catcrafts/imsd) | IMS SIP/AKA/IPsec、RTP/编解码、D-Bus 控制与 PDN 脚本；我们只补充 V30 互通及 OpenRC/音频生命周期集成 |
| ShapeShifter499 / joan-volte-lineage | [joan-volte-lineage](https://github.com/ShapeShifter499/joan-volte-lineage) | LG IMS 参数、能力掩码与 Security-Client 序列化的研究参考；并非直接套用其他运营商配置 |
| Dmitry Baryshkov | [GPU 时钟补丁](https://lore.kernel.org/all/20261019-msm8998-fix-clocks-v1-1-370949e4d8a0@oss.qualcomm.com/)、[MMSS 时钟补丁](https://lore.kernel.org/all/20261019-msm8998-fix-clocks-v1-2-370949e4d8a0@oss.qualcomm.com/) | GCC GPU/MMSS 必须保持开启的原始修复；上游候选保留原作者与 Signed-off-by |
| GLINK 上游贡献者，包括 Vishnu Santhosh | [endpoint destroy deadlock 修复邮件](https://lkml.rescloud.iu.edu/2606.0/08069.html) | 设备解绑期间的死锁修复来源 |
| V30 WCD934x / 设备树修复贡献者 | [ADC MUX8 修复来源](https://github.com/ShapeShifter499/linux-lg-v30-joan/commit/2059bbae94ddfb748278a30a229a94d0882155bf) | ADC3 录音路径及麦克风偏置/MCLK 依赖的实现参考 |
| LG、Qualcomm、LineageOS 社区 | [android_kernel_lge_msm8998](https://github.com/LineageOS/android_kernel_lge_msm8998) | 原厂硬件描述及对照实现；固件由设备所有者自行取得，不在本仓库分发 |
| ModemManager / NetworkManager / libqmi | [ModemManager](https://modemmanager.org/)、[NetworkManager](https://networkmanager.dev/)、[libqmi](https://gitlab.freedesktop.org/mobile-broadband/libqmi) | 数据连接、QMI 与短信 D-Bus 接口 |
| PipeWire、ALSA、OpenRC、tmux、Alpine | [PipeWire](https://pipewire.org/)、[ALSA](https://www.alsa-project.org/)、[OpenRC](https://github.com/OpenRC/openrc)、[tmux](https://github.com/tmux/tmux)、[Alpine](https://alpinelinux.org/) | 媒体图、声卡控制、启动服务、文字界面及用户态环境 |

本项目的主要工作：将上述组件组合成 US998 的纯 TTY 运行配置，处理开机依赖、每次通话的音频资源归属/恢复、持久短信及明确的发送幂等策略，补齐特定 IMS 互通路径，并记录操作者实际听验和验收边界。

Assisted-by: Codex:OpenAI/GPT-6
Date: 2026-10-31
