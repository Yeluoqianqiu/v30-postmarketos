# 与上游的关系

本项目提供一个可审查的 US998 集成组合。Linux、设备驱动、postmarketOS、IMS 协议
及媒体引擎分别由各自上游维护；本仓库不声称独立实现这些组件。

| 内容 | 位置 / 状态 |
|---|---|
| 纯 TTY SMS 与通话参考源码 | [lg-v30-port #11](https://github.com/ShapeShifter499/lg-v30-port/pull/11)，Draft |
| 电量、充电抑制、IPA QMI、GCC GPU/MMSS 五项 | [linux-lg-v30-joan #12](https://github.com/ShapeShifter499/linux-lg-v30-joan/pull/12)，Draft；基线 dc9c669…，只完成四目标对象构建 |
| LG 六种安全提案、Via 保留、无 offer re-INVITE/ACK SDP | 本仓库 imsd 补丁；尚无 Forgejo PR，提交者尚缺 Forgejo 账号及该项目要求的 GPG 配置 |
| IPA 系统头表、GLINK 死锁、ADC MUX8、MCLK 路由 | 新内核基线已包含，不在 #12 重复提交；旧实测组合仍需要相应来源补丁/路由 |

GCC 两个提交保留 Dmitry Baryshkov 作者身份；移植和集成不是重新发明其时钟修复。
旧实测内核中的诊断/兼容补丁仅留在 baseline，以解释和重建该组合；它们不等于
适合直接合并到 Linux 主线的提交。

## Draft PR 与 DCO

Draft PR 是已经公开的草稿合并请求，可以查看和讨论，但要转为 Ready for review
后才能合并。我们用它明确标示新内核尚未实机验收。参见 [GitHub 文档](https://docs.github.com/en/pull-requests/reference/pull-requests#draft-pull-requests)。

DCO 是 Developer Certificate of Origin，贡献者声明自己有权按相应开源许可证
提交代码，且知道署名记录会公开保留。`Signed-off-by` 记录该认证；它与 GPG 的
密码学提交签名分别处理。原文：[DCO 1.1](https://developercertificate.org/)。

Signed-off-by 的认证应由真人贡献者本人作出，不能由 AI 代作。
