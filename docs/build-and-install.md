# 构建、配置与安装

本路线面向熟悉 Linux/pmbootstrap 的设备所有者。主机脚本不连接手机，不自动启动服务，
也不写 boot/recovery。当前新整理的打包/字体路径/蓝牙顺序适配只做主机验证；原 r35/r36
实机结果见验收记录。

## 1. 准备环境

已验证的构建环境为 aarch64 的 Alpine chroot：imsd 使用 clang 23.1.4、libc++、lld、
C++26，内核使用 Alpine GCC。可以在 Linux aarch64 主机或 Lima aarch64 VM 中准备。
Python 辅助脚本要求 3.12+；还需要 git、curl、make、dtc/fdtget/fdtput。

内核依赖在 baseline/kernel/APKBUILD 的 makedepends 中，imsd 需要 Gio/GLib 开发头、
pkg-config、LLVM/libc++ 的 std.cppm。运行时除 [packages.txt](../examples/packages.txt)
列出的组件，还需与自身架构/发行版匹配的 libc++/libc++abi/libunwind 及 imsd 使用的
AMR 编解码库。此文件是依赖提示，不是完整 rootfs 包版本锁。

按 postmarketOS 官方文档准备自己的设备 rootfs，并参考锁定的 pmaports 设备包。
从自己的合法设备/系统取得所需固件，遵循上游提取与安装流程。本仓库不携带固件。
使用者自己的 boot/initramfs、根文件系统和分区标识是额外输入，因此不声称从空目录
即可得到与历史镜像逐字节一致的系统。

## 2. 重建已实测内核组合

```sh
python3 scripts/prepare-sources.py kernel
mkdir -p out/kernel
cp sources/kernel.config out/kernel/.config
make -C sources/kernel O="$PWD/out/kernel" ARCH=arm64 olddefconfig
# 在 native aarch64 环境；跨编译时另行设置 CROSS_COMPILE/CC
make -C sources/kernel O="$PWD/out/kernel" ARCH=arm64 -j4 Image.gz modules dtbs
```

源码下载的 SHA512 及所有 recipe 输入会先校验；旧配置和补丁顺序保持历史 recipe。
内核文件留在 sources/kernel，输出走 out/kernel。不要将最新 PR 的五个补丁再叠加到
这个旧基线——baseline 已经有对应本地修改。

r31/r35 的麦克风偏置路由是在 r30 DTB 上增加 MCLK 依赖；复制后仅修正该属性：

```sh
python3 scripts/patch-audio-dtb.py \
  out/kernel/arch/arm64/boot/dts/qcom/msm8998-lge-joan.dtb \
  out/msm8998-lge-joan-mclk.dtb
```

此脚本只接受旧基线的确切原路由。新内核已带完整路由，不能套用。内核/modules 必须
配套安装到设备 rootfs；runtime 的门禁要求 release 为 7.2.0-rc2-v30-r30。

## 3. 构建 IMS

```sh
python3 scripts/prepare-sources.py imsd
# 在上述 Alpine aarch64 C++26 构建环境执行：
python3 scripts/build-imsd.py sources/imsd out/imsd
```

该辅助器按项目模块关系构建并运行 8 组单测，生成 imsd、imsd-pcscf、imsd-media、
imsd-dialerd、imsd-ofonod。本配置使用前三个。它不代替上游 Crafter lint；没有声称
运行完整 Crafter 流程。补丁默认保留原 imsd 单安全提案；本配置显式选择 lg-generic。

## 4. 暂存用户态文件

```sh
python3 scripts/stage-rootfs.py stage --imsd-build out/imsd
```

目标必须为空且不能是 `/`；本步骤只在普通目录生成文件和 STAGING-MANIFEST.json。
没有 rc-update、服务启动或电话/SMS 操作。不要直接覆盖已有手机系统；先对照清单，
将需要的文件合并到自己的离线 rootfs，保存原文件与服务状态。

以下需要操作者根据自身系统完成，不由暂存脚本代替：

- 创建专用 `v30` 用户，UID 10000，并加入 audio 组；不要覆盖已有同 UID 用户。
- 安装 matching 内核 modules、固件及上述运行时依赖。旧版 q6core skip_versions 等
  兼容选项只属于锁定内核；当前主线已去掉的参数不能直接带过去。
- 合并 [rmtfs.conf](../examples/rmtfs.conf)，保持 owner NV 分区只读访问。不要改成
  可写来绕过 modem 错误。
- 保留发行版 nftables inet/filter/input 结构，供 IMS supervisor 管理自己的链；
  不要把整机输入防火墙直接关闭。D-Bus/polkit 使用发行版激活方式。
- 创建自己的 NetworkManager Wi-Fi 和数据连接。中国联通本次使用数据 APN uninet，
  IMS APN ims / profile 2 / IPv6；其他运营商要重新确认。不要写入本机 SIM 身份或复制
  别人的连接 UUID。Wi-Fi 的路由/DNS 优先级应高于蜂窝数据。
- 在配置层保留 IPA alias blacklist，由 v30-ipa 按依赖显式加载；不能改为内核级的
  module_blacklist=ipa，后者会把明确加载也挡住。

## 5. TTY 横屏与蓝牙关闭

字体程序从 `/var/lib/v30-console/font-original.json` 读取本设备原字形。首次配置时，
须在仍是原始 8×16/256 字形、未缩放的 VT 上显式保存：

```sh
sudo python3 scripts/capture-console-font.py /var/lib/v30-console/font-original.json
```

将 [inittab 片段](../examples/inittab-tty1.snippet) 合并到自己的 tty1 行；只在原 tty1
没有交互登录时切换，正常 /bin/login 认证保留。不要使用其他设备导出的字体备份。
内核命令行使用 fbcon=rotate:1，运行时同样保留 rotate=1。

将 [BlueZ Policy 片段](../examples/bluez-policy.conf) 合并到已有 main.conf。
新增的 v30-bluetooth-off 是开机顺序的最后关闭策略，hci0 不存在时直接保持未开启。
这是本方案偏好，不会改写蓝牙地址或要求移除上游蓝牙支持。

## 6. 设备启动前复核与服务启用

boot 包装工具接受使用者已有、已核实可恢复的 joan Android v0/4096 boot 镜像。
它保留 ramdisk/启动地址，仅替换 kernel+DTB，可另给本机命令行。复制 template 后
填写自己的分区 UUID；不要沿用其他设备的标识或强制扩容设置。

```sh
python3 scripts/repack-boot.py \
  --base /path/to/your-known-good.img \
  --kernel out/kernel/arch/arm64/boot/Image.gz \
  --dtb out/msm8998-lge-joan-mclk.dtb \
  --cmdline-file out/my-cmdline.txt \
  --output out/boot-candidate.img
```

构建成功只表明文件生成；还要核对内核/模块、DT、initramfs 所需驱动和完整恢复路径。
在所有者在场、有 USB 和自己校验过的备份时，先安排 RAM-only 启动验证。LG aboot
不使用 fastboot getvar；具体进入/恢复步骤遵循设备上游文档。本仓库没有自动刷分区脚本。

经过设备复核后，由所有者逐项启用自己的 OpenRC 配置。典型服务集合为：

```text
v30-charge-limit, v30-modem-modules, rmtfs, tqftpserv, v30-wifi,
networkmanager, v30-audio, v30-unicom, v30-ipa, v30-cellular, v30-ims,
v30-console-status, v30-power-key, v30-bluetooth-off, v30-sms
```

具体依赖以源码及本机 `rc-update -u` 结果为准；别额外启用重复的 ModemManager。
新整理的 profile 没有自动改写 /etc/inittab、BlueZ 或 NM 私有连接，也没有替使用者
启用上述服务。按 [验收与回退](validation.md) 检查后，再考虑是否设为自己的默认启动。

## 7. 使用

```sh
sudo v30-phone status
sudo v30-phone calls
# 以下仅在操作者实际要处理该通话时运行：
sudo v30-phone answer
sudo v30-phone hangup

sudo v30-sms status
sudo v30-sms list --unread
sudo v30-sms read 1
# 明确发送，正文从本机 UTF-8 文件读取：
sudo v30-sms send FULL_INTERNATIONAL_NUMBER --file message.txt --request-id UNIQUE_ID
```

没有自动拨号、接听、回复、发送或失败重试。发送状态未知时保留记录并排查，不能
因为没有成功回复就换 request-id 重发。当前文本编码支持 GSM7/UCS2，拒绝非 BMP /
emoji，上限 10 段；真实长短信尚未验收。
