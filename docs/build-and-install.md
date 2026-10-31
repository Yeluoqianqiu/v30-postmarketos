# Build, configuration and installation

This reconstruction path is intended for device owners familiar with Linux and pmbootstrap. Host helpers do not connect to a phone, start device services or write boot/recovery. The published integration is experimental: initial publication adaptations had host checks, and historical r35/r36 device results are scoped in [validation.md](validation.md). Selected later r37 device changes have separate [incoming-alert evidence](incoming-alerts.md); they do not qualify the full reconstruction path.

## 1. Prepare the environment

The validated build environment was an aarch64 Alpine chroot: imsd used clang 23.1.4, libc++, lld and C++26; the kernel used Alpine GCC. An aarch64 Linux host or Lima VM can provide such an environment. Helpers require Python 3.12+, git, curl, make and dtc/fdtget/fdtput.

Kernel dependencies are listed in baseline/kernel/APKBUILD under makedepends. imsd needs Gio/GLib development headers, pkg-config, LLVM/libc++ and std.cppm. Runtime dependencies include the components in [packages.txt](../examples/packages.txt), architecture/distribution-matched libc++/libc++abi/libunwind and imsd's AMR codec libraries. The package list is a dependency guide, not a fully version-locked rootfs.

Prepare your device rootfs using the postmarketOS documentation and the pinned pmaports reference. Obtain firmware from your own lawful device/system and follow the upstream extraction/installation process. Firmware is not distributed here. Your known-good base boot/initramfs, rootfs and filesystem identifiers are additional inputs, so this is not a claim that an empty directory produces a byte-identical historical system.

## 2. Prepare the historical kernel inputs

```sh
python3 scripts/prepare-sources.py kernel
mkdir -p out/kernel
cp sources/kernel.config out/kernel/.config
make -C sources/kernel O="$PWD/out/kernel" ARCH=arm64 olddefconfig
# Native aarch64 environment; configure CROSS_COMPILE/CC separately if needed.
make -C sources/kernel O="$PWD/out/kernel" ARCH=arm64 -j4 Image.gz modules dtbs
```

The helper checks the archive SHA512 and all recipe inputs before applying the historical patch sequence. Source stays in sources/kernel and output goes to out/kernel. Do not also apply the five newer PR patches to this old baseline; it already contains the local equivalents.

The r31/r35 microphone routing added MCLK dependencies to the r30 DTB. Copy it and modify only that property:

```sh
python3 scripts/patch-audio-dtb.py \
  out/kernel/arch/arm64/boot/dts/qcom/msm8998-lge-joan.dtb \
  out/msm8998-lge-joan-mclk.dtb
```

The helper accepts only the expected old route. The newer kernel already has complete routes and must not receive this adjustment. Install matching kernel/modules into your rootfs; the runtime gate expects release 7.2.0-rc2-v30-r30. Input/patch checks and DTB reconstruction do not establish a fresh full-kernel build or device pass.

## 3. Build imsd

```sh
python3 scripts/prepare-sources.py imsd
# Run in the Alpine aarch64 C++26 environment described above.
python3 scripts/build-imsd.py sources/imsd out/imsd
```

The helper follows the module graph, runs eight unit suites and builds imsd, imsd-pcscf, imsd-media, imsd-dialerd and imsd-ofonod. This profile uses the first three. It does not run Crafter lint or replace the full upstream workflow. The patched default retains imsd's single security offer; the reference supervisor explicitly selects lg-generic.

## 4. Stage userspace files

```sh
python3 scripts/stage-rootfs.py stage --imsd-build out/imsd
```

The destination must be empty and cannot be `/`. Staging produces files and STAGING-MANIFEST.json in an ordinary directory; it does not call rc-update, start services or perform call/SMS operations. Compare the manifest with your own offline rootfs and preserve original files/service state before merging the selected files.

The operator must separately complete these device-specific steps:

- Create a dedicated v30 user with UID 10000 and membership in audio. Do not replace an existing user with that UID.
- Install matching kernel modules, firmware and runtime dependencies. Old q6core skip_versions and similar options belong to the pinned kernel; removed parameters do not apply to current mainline.
- Merge [rmtfs.conf](../examples/rmtfs.conf) while retaining read-only access to the owner's NV partitions. Do not enable writes to work around modem errors.
- Retain the distribution's nftables inet/filter/input structure so the supervisor can manage its own restricted chain. Keep native D-Bus/polkit activation rather than starting duplicate daemons.
- Create your own NetworkManager Wi-Fi/data connections. The tested China Unicom setup used data APN uninet and IMS APN ims / profile 2 / IPv6. Other carriers need separate qualification. Do not copy subscriber identities or another device's connection UUID. Prefer Wi-Fi over cellular for routing and DNS.
- Keep the IPA alias blacklist and let v30-ipa load IPA explicitly in dependency order. Do not substitute module_blacklist=ipa, which would also block explicit loading.

## 5. Landscape TTY and Bluetooth-off policy

The font tool reads this device's original glyphs from `/var/lib/v30-console/font-original.json`. Capture them explicitly while the VT still has the original, unscaled 8x16/256 font:

```sh
sudo python3 scripts/capture-console-font.py /var/lib/v30-console/font-original.json
```

Merge the [inittab snippet](../examples/inittab-tty1.snippet) into your tty1 line only when there is no active interactive login. Normal /bin/login authentication is retained. Do not use another device's exported font state. Use fbcon=rotate:1 on the kernel command line and retain runtime rotate=1.

Merge the [BlueZ policy snippet](../examples/bluez-policy.conf) into the existing main.conf. v30-bluetooth-off supplies the final power-off policy after address setup; if hci0 is absent it leaves Bluetooth off. This profile choice does not rewrite the address or remove upstream Bluetooth support. The newly packaged service has host checks only.

## 6. Review before device startup

The boot helper accepts the operator's known-good, recoverable joan Android v0/4096 boot image. It preserves the ramdisk/boot addresses, replaces kernel+DTB and optionally reads a local command-line file. Supply your own filesystem UUIDs after copying the template; do not reuse another device's identifiers or force-resize settings.

```sh
python3 scripts/repack-boot.py \
  --base /path/to/your-known-good.img \
  --kernel out/kernel/arch/arm64/boot/Image.gz \
  --dtb out/msm8998-lge-joan-mclk.dtb \
  --cmdline-file out/my-cmdline.txt \
  --output out/boot-candidate.img
```

A generated file is not a device pass. Verify kernel/modules, DT, initramfs drivers and recovery before any boot. Arrange an initial RAM-only test with the owner present, USB available and verified personal backups. Do not use fastboot getvar on LG aboot; follow the device upstream's entry/recovery procedure. No automated partition-flashing script is provided here.

After device-specific checks, the owner can explicitly enable the chosen OpenRC services. The typical reference set is:

```text
v30-charge-limit, v30-modem-modules, rmtfs, tqftpserv, v30-wifi,
networkmanager, v30-audio, v30-unicom, v30-ipa, v30-cellular, v30-ims,
v30-console-status, v30-power-key, v30-bluetooth-off, v30-sms,
v30-incoming (optional incoming ringtone, wake and caller-ID profile)
```

Use the actual scripts and the device's rc-update -u output to check dependencies. Avoid a second ModemManager instance. Staging does not rewrite /etc/inittab, BlueZ or private NM connections and does not enable the services. Complete the [validation checklist](validation.md) before considering a default boot change.

The optional [incoming alerts](incoming-alerts.md) require the updated media wrapper, console metrics tool, `v30-phone`, all four alert/history modules and the ringtone configuration together. Host checks do not replace a fresh ringing/display/voice test on the target device.

## 7. Explicit use

```sh
sudo v30-phone status
sudo v30-phone calls
# Only when the operator intends to handle the selected call:
sudo v30-phone answer
sudo v30-phone hangup

sudo v30-sms status
sudo v30-sms list --unread
sudo v30-sms read 1
# Explicit send using a local UTF-8 file:
sudo v30-sms send FULL_INTERNATIONAL_NUMBER --file message.txt --request-id UNIQUE_ID
```

There is no automatic dial, answer, reply, send or failed-send retry. Retain and investigate unknown records rather than choosing a new request ID solely to retry an unconfirmed request. Current text support is GSM7/UCS2, with non-BMP/emoji rejected and a ten-segment limit. Real multipart SMS remains unqualified.
