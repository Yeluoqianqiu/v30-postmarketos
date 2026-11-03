# Display strip investigation

The manual GUI is experimental and has not passed physical display-quality
acceptance. The authenticated landscape TTY and Bluetooth-off remain the boot
default. No successful kernel display fix is claimed.

## Status: deferred, low priority

On 2026-11-01, the operator judged the transient strips a minor experience
issue that does not prevent use, and confirmed that graphical sessions are
not a core dependency. Pause active investigation and retain the issue and
all evidence for later review. This does not establish a fix or change the
historical display-quality results. Keep the authenticated landscape TTY and
Bluetooth-off as the default, with the graphical session optional. No further
capture, desktop/kernel change or display test is planned under this decision.

The diagnostic directions below are retained for a future explicit reopening,
not an active work queue.

## Observations that narrow the problem

- Xorg framebuffer, Weston/Pixman/software Xwayland and direct Xorg/KMS all
  retained strips and input delay. An early-pageflip RAM candidate did not fix
  them. A continuous-clock RAM candidate produced a black screen and was rejected.
- Replacing Onboard with a small non-focusing GTK3 keyboard and immediate XTest
  key dispatch made clicks substantially better according to the operator, with
  slight remaining delay. Strips became more frequent. Native UIM readback passed
  in an isolated synthetic entry; that trial did not separately confirm Chinese
  or Terminal use with the operator.
- Full-window repainting did not eliminate strips, which appeared near touches
  and at the page top. Both private keyboard profiles stopped cleanly.
- Official Alpine-signed libdrm 2.4.134 `modetest` reproduced horizontal strips
  during a single approximately 20-second native-resolution XR24 pageflip test.
  The operator saw alternating patterns, the strips, and automatic return to
  normal landscape TTY. Source inspection confirms that two buffers were filled
  once and unmapped, then alternated on pageflip completion. No GTK, Xorg,
  keyboard, cursor or ongoing CPU pixel writes were involved.

The last observation removes those GUI components as necessary conditions for
the artifact. It supports investigating the shared DRM/DPU/DSI/DSC/panel output
path; it does not identify which component is wrong. Completion events ranged
from 59.54 to 59.70 Hz, median 59.63 Hz. This measures event delivery, not visible
frame correctness or touch-to-photon latency. IMS and all 13 service checks,
closed audio PCMs, TTY, Bluetooth-off, device permissions and protected files
passed afterwards. No reboot, flash, phone call or SMS was performed for this
diagnostic.

Tool sources: [official Alpine package](https://pkgs.alpinelinux.org/package/edge/main/aarch64/libdrm-tests),
[official libdrm source release](https://dri.freedesktop.org/libdrm/libdrm-2.4.134.tar.xz).
The APK signature was checked against a public key already trusted by the
device. No package database or existing library was replaced.

## A concrete but unproven DSC discrepancy

The pinned [stock DV3.1 panel configuration](https://github.com/LineageOS/android_kernel_lge_msm8998/blob/c022ed57679b432bff277eaca0a2366a72218925/arch/arm64/boot/dts/lge/dsi-panel-sw43402-dsc-qhd-cmd-dv3_1.dtsi)
declares DSC version 1.1, SCR revision 1. Its selected
[config3](https://github.com/LineageOS/android_kernel_lge_msm8998/blob/c022ed57679b432bff277eaca0a2366a72218925/arch/arm64/boot/dts/lge/dsi-panel-sw43402-dynamic-resolution-switching-config.dtsi)
uses 720×16 slices, 8 bpc and 8 bpp. The retained r30 host instead unconditionally
selects `DRM_DSC_1_1_PRE_SCR`.

The [stock calculation and tables](https://github.com/LineageOS/android_kernel_lge_msm8998/blob/c022ed57679b432bff277eaca0a2366a72218925/drivers/video/fbdev/msm/mdss_panel.c)
select SCR1 quantization ranges and a first-line BPG offset of 15. All 15 SCR1
ranges match the helper's `DRM_DSC_1_2_444` table; the last five differ from
pre-SCR. The table name does not require changing the DSC wire version to 1.2.
A [DRM maintainer's review](https://lists.openwall.net/linux-kernel/2026/03/06/2018)
also identifies the shared SCR/1.2 4:4:4 table. That discussion does not establish
this V30 artifact's cause or promise a visible improvement.

Both original C calculation functions were compiled in an isolated userspace
harness, with equivalent 720×16 RGB 8 bpc/8 bpp inputs. The stock outputs match
the candidate outputs for every compared derived field after selecting SCR1
ranges and setting the stock first-line offset before dependent calculations:

| Field | Current pre-SCR profile | Stock SCR1 profile |
| --- | ---: | ---: |
| First-line BPG offset | 12 | 15 |
| Initial decode delay | 616 | 706 |
| Non-first-line BPG offset | 1639 | 2048 |
| Scale increment interval | 443 | 388 |

This is source-calculation evidence, not a captured live PPS comparison or
hardware qualification. The r46 diagnostic candidate applies only to SW43402,
keeps DSC wire version 1.1, the original clock flags, PHY, TE, mode, DTB and r30
patch stack, and excludes the failed r40/r42 changes. Full ARM64 compilation, all 1,636 matching modules and independent RAM-image
audits passed; configuration differs only in LOCALVERSION. The candidate subsequently completed one separately authorized RAM boot. The
operator reported the same horizontal strips in the official two-buffer
pattern, so the GUI branch was skipped. The candidate failed physical quality
acceptance. It returned to TTY, then rebooted to the unchanged r35 default;
cellular registration and the status bar, IMS, all previously paused services,
archives and protected partition/file hashes passed restoration checks. The
one-shot authorization is closed. SCR1 matching alone did not fix the artifact. Image SHA256: `e6821a611c6d985ce052aca562714590ddd47b00d9c7c912da3924c08ced4f78`.

## Known upstream findings and limits

The [upstream DSI experiment record](https://github.com/ShapeShifter499/lg-v30-port/blob/master/docs/d1-dsi-link-rate-fix.md)
already rejected continuous clock for a blank/wake regression, and rejected
raw vendor PHY timing and packetization experiments. Raw MMIO also hung the
bus. These records were found only after our failed r42 clock experiment;
they should have been reviewed first. Do not repeat those directions. The
record's older approximately 30 fps observation is not a universal hardware
ceiling or a characterization of the later bare-DRM test.

The [upstream wake-rainbow fix](https://github.com/ShapeShifter499/lg-v30-port/blob/master/docs/ember-2026-08-10-rainbow-on-wake-was-brightness.md)
removed maximum-brightness initialization; r30 already avoids that step. A
wake artifact is not automatically the same defect as transient interactive
strips. Upstream also documented high-resolution software GTK3/Cairo slowness
in its [BIMC investigation](https://github.com/ShapeShifter499/lg-v30-port/blob/master/docs/ember-handoff-2026-08-07-bimc-qos-closed.md).
The relevant BIMC/GPU clock changes are already present in our baseline.

Android's common Linux ancestry does not imply an identical display driver or
presentation path. Its vendor driver programs panel-specific parameters, while
SurfaceFlinger/HWC and synchronization fences coordinate frame ownership and
presentation; see [Android graphics synchronization](https://source.android.com/docs/core/graphics/sync)
and [VSync](https://source.android.com/docs/core/graphics/implement-vsync).
That explains why Android can work without proving which mainline parameter or
driver behavior causes this fault. No exact ready-made fix for this observed
V30 strip was found in the reviewed primary sources.

Curated results: [r41/r42](../provenance/r41-r42-display-validation.json) and
[r43–r46](../provenance/r43-r46-display-investigation.json). Private raw notes,
device identifiers and captures are intentionally excluded.

## r46 verification limits and next diagnostic boundary

The expected one-time SCR1 boot message had already rolled out of the kernel
ring buffer amid existing audio/modem debug output. An initial preparation gate
stopped before installing profiles. Preparation then independently matched the
running GNU Build ID against the audited `vmlinux` and checked the exact
SW43402 device-tree binding before the single pattern run. This is identity and
source-path evidence, not a live PPS readback. Pattern completion events ranged
from 59.21 to 59.70 Hz, median 59.635 Hz; physical strips remained.

The operator also noted missing cellular information in the RAM TTY. This trial
intentionally interrupted telephony and status services. After the ordinary
default reboot, read-only checks explicitly confirmed UNICOM 4G registration
and refreshed the status bar; this is not left as an unresolved SIM regression.

The baseline already contains the upstream K080 TE routing fix: GPIO10 muxed as
`mdp_vsync_a`, with `qcom,te-source = "mdp_vsync_p"`. The retained host also
compresses active width while preserving porch overhead. These checks reject
new proposals to blindly change TE routing or divide porch widths again.
The next investigation concerns physical scan/transfer synchronization and
which output stage produces the strip, using the bare-DRM reproducer. It has no
new kernel candidate or hardware authorization yet.

A subsequent read-only check on the restored default found configured byte,
byte-interface and pixel rates of 85.555279, 42.777640 and 114.073706 MHz. The
display was blanked and the DSI clock enable counts were zero: these are cached
configured rates, not a measurement during an artifact. Their expected 2:1
byte/interface relationship does not support reapplying the old divider fix.
The default-TTY underrun counter was zero; it does not exclude an underrun
during the earlier visible test.

The compressed frame budget is 720-byte chunks × 2 slices × 2,880 lines =
4,147,200 bytes at 8 bpp. At the configured 85.555279 MHz byte clock and four
lanes, payload-only time is approximately 12.12 ms, before packet/transfer
overhead. The upstream D5 note's later 1.38 MB/4 ms calculation appears to
apply compression twice. This arithmetic correction does not establish a link
shortage or a strip fix; actual timing needs measurement.

## Minimal reproducer for maintainer review

The reproducible symptom is a brief horizontal corruption strip during
alternating native-resolution test buffers. It also occurs during interactive
GUI updates. It has not been classified as ordinary old/new-frame tearing
versus a corrupted line or DSC slice; a synchronized physical capture is still
missing. A framebuffer screenshot alone cannot capture panel-side output.

The upstream test is libdrm 2.4.134 `modetest`, run on a separately owned manual
VT with no concurrent display server. Query resources with `-M msm -c -p`, then
use the current connector/CRTC IDs in `-M msm -s
CONNECTOR_ID@CRTC_ID:1440x2880@XR24 -v`. In our controlled test, a newline ended
the process after 20 seconds, with a finite fallback and explicit VT cleanup.
No cursor test, rendering loop or live CPU buffer writes were used. A fresh
visible observation requires operator coordination; do not replay private
once-marked scripts.

Useful next evidence is the physical strip's content/height/location matched
to TE/read-pointer, kickoff and transfer-complete timing for the same frame.
Then distinguish a scan/transfer-window problem from DPU fetch/encode or link
corruption. Do not select another speculative patch based solely on a normal
pageflip rate or an old generic display warning.
