# 来源、许可证与发布边界

| 路径 | 来源与许可 |
|---|---|
| `baseline/kernel/` | ShapeShifter499 的 Linux 分支和本地 r30 打包修改。内核补丁继承原文件的 GPL-2.0 等许可；APKBUILD 中保留原始维护者元数据，表示历史来源，不代表上游维护本仓库。 |
| `patches/current-kernel/` | 已投递的五个内核提交。GCC 两项源自 Dmitry Baryshkov，保留原作者、原始 Signed-off-by 和移植者签名。 |
| `patches/imsd/` | Catcrafts imsd `2b5de7a…` 的 V30 互通增量，GPL-3.0-only；不能理解为 imsd 上游已经接收。 |
| `runtime/voice/ims-pdn-up.sh`、D-Bus/polkit 文件 | 从 Catcrafts imsd 衍生，保留 Catcrafts 原始 GPL-3.0-only 与版权头。 |
| 其余 `runtime/`、`scripts/`、`tests/`、本仓库文档 | 本地集成/工具与发布整理，GPL-3.0-only；参考来源见致谢。 |
| 控制台字体 | 仓库不携带位图。使用者在设备上显式读取原控制台字形后缩放；原字体的许可仍适用。 |

根目录 LICENSE 和 LICENSES/GPL-3.0-only.txt 为 GPLv3 正文；LICENSES/GPL-2.0-only.txt 为 Linux 提供的 GPLv2 文本。根许可证不改变其他项目原有代码的许可。

文件的来源标签与 SHA256 位于 [FILE_ORIGINS.json](provenance/FILE_ORIGINS.json)，公开文件的内容指纹位于 [SHA256SUMS](SHA256SUMS)。这些指纹用于完整性核对，不把尚未公开的原始设备记录宣称为公开、不可变的验收证据。

未分发：原厂/设备提取固件、codec 二进制、个人 boot/initramfs、SIM/NV 状态、联系人/短信档案、凭据、私钥、原始设备日志、分区备份、个人分区 UUID。构建得到的二进制和操作者生成的配置放在 Git 忽略目录。

AI 协助声明为 `Assisted-by: Codex:OpenAI/GPT-6`；会话没有提供更细的模型变体，不虚构路由。既有贡献者署名不会被替换。
