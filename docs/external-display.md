# Native USB-C external display bring-up

See the [r81 checkpoint](r81-progress.md) for the latest default and test scope. Older results below describe their original baselines.


Status on 2026-11-02: r50 passed bounded static output and r51 passed automatic
provider loading/TTY but failed its external GUI. Private r52 passed a bounded
legacy pageflip gate and one physical desktop/input/Chinese/ReturnTTY cycle;
a reset to the unchanged r35/r30 default followed its second GUI detach.
Detach acceptance failed. A later r53 no-GUI legacy run also reset after the
operator removed AOC, saw normal TTY and inserted the Mac. Its live stream
identifies a stale-mode re-enable after PHY shutdown, not a proven reset cause.
The separately authorized r54 six-line fbdev change then passed a legacy
AOC-removal/three-second-wait/Mac-attachment cycle in the same RAM boot and one
interactive GUI/manual ReturnTTY cycle. Its second GUI reset after AOC removal
alone, before Mac attachment. The received trace stops at atomic-check resource
reservation; caller and reset cause remain unknown. Default full health and
authorization closure passed. No default promotion is claimed. The operator wants
USB-C direct output to an AOC U27N3G6R4B 4K monitor and confirms that the same
cable displays correctly from a Mac. The monitor model and cable check are
operator evidence; r50 has now read a checksum-valid EDID from this connection.
Full Phosh/Plasma tests and resource comparisons follow this work. The existing
strip issue remains deferred.

## Confirmed default-stack gap

The installed r35/r30 system exposes only the internal DSI connector, no
registered Type-C or USB-role-switch device, and a USB2 peripheral-only board
configuration. A compiled `DRM_MSM_DP` option alone does not provide a wired
MSM8998 DP controller, PHY, USB-C negotiation or output connector.

[LG's regional H930 specification](https://www.lg.com/ro/telefoane-mobile/lg-LGH930)
lists DP-HDMI mirroring with adapter limitations. That does not qualify this
US998 Linux stack or this particular direct connection.

## Upstream history to preserve

The [reverted DP prototype](https://github.com/ShapeShifter499/linux-lg-v30-joan/commit/42eff31685a7)
broke USB PHY references, device-tree graphs and bindings, used mismatched PLL
tables, and omitted a reset. Do not restore it wholesale. The
[later corrected handoff](https://github.com/ShapeShifter499/lg-v30-port/blob/master/docs/handoff-2026-09-25-dp-altmode.md)
clarifies that the DP PLL uses QMP v3 COM/TX registers together with an older
DP PHY layout. Its earlier v2 description, repeated in the revert message, was
wrong. It also records the controller P0 offset, lane orientation, SBU routing,
reset/TCSR sequencing and USB3/DP exclusivity that a complete port must handle.

## First prerequisite candidate: r48

The private diagnostic starts from the qualified r30 source and all 15 inherited
patches. It removes the failed SCR1 experiment, keeps internal display/TE,
charging, fuel-gauge, audio and IPA behavior, and adapts upstream PMI8998
TCPM/VBUS support from revision `e6e796df38f49b51f2b251447dfe697961deacc0`.
The connector is a power sink requesting only fixed 5 V; USB data remains
USB2/QUSB2 with a real role provider. No source PDO, DP PHY, DP controller,
SBU mux or Alt Mode entry is added.

Full ARM64 compilation, all 1,636 matching modules, configuration and independent
DTB/RAM-image audits passed. Configuration differs only in LOCALVERSION. The
DTB retains all 654 existing nodes and adds seven Type-C/VBUS/USB2 endpoint
nodes; existing semantic changes are peripheral-to-OTG and USB-role-switch.
Phandle renumbering is checked through provider paths and argument counts, and
the new endpoint graph is bidirectional. Other existing properties are unchanged.

The RAM image is 28,049,408 bytes, SHA256
`0874828f99e364f59c549ff9df49a77889ec0b1b14f1a29a37db93f6ffb8de75`.
The default command line and 331 unrelated initramfs entries are preserved;
18 module files match the candidate, including four initramfs kernel modules.
One explicitly authorized RAM boot has now passed the prerequisite below; its
authorization is closed. Review patches
have no checkpatch errors; one new-file MAINTAINERS reminder remains for future
upstream review. No new DCO certification or submission is claimed.

## Recorded prerequisite hardware result

One authorized RAM boot on 2026-11-01 registered the PMI8998 Type-C port. After
the operator connected the verified cable to the AOC, TCPM recorded:

- A fixed 5 V / 3 A PD contract, with V30 as power sink. These are negotiated
  contract values, not measured charging current or power consumption.
- Automatic data-host role and reversed plug orientation; no manual role
  request was needed.
- Partner DisplayPort SVID `ff01`, mode 1, VDO `0x00140045` (display sink,
  pin assignments C/E), with `active=no`.
- A USB2 hub and a Billboard device enumerated on the host bus.

The initial Mac connection provided USB gadget data, but no PD partner was
recorded; it is not a passed Mac PD test. DP Alt Mode was not entered, no video
was produced, and EDID/DPCD, link rate and resolution remain unqualified.

The test driver was unloaded before returning to the unchanged r35/r30 default.
USB SSH subsequently confirmed the new default boot; IMS and all 11 paused
services recovered. Landscape TTY, Bluetooth-off, four closed PCM streams,
archive preservation (two SMS and four call records), SQLite checks and
partition/protected-file hashes passed. The restore SSH session disconnected
before its final reboot marker was captured; independent post-boot checks
confirm restoration. Both phone and host authorizations are closed. No next RAM
experiment is authorized by this result.

## Rejected video candidate: r49

The private DP-only candidate adds MSM8998 QMP v3 COM/TX with the older DP PHY
layout, reset/TCSR sequencing, SBU and lane routing, legacy AUX interrupt
acknowledgement, SST controller, DPU INTF0 and clocks. USB data stays on QUSB2
and the connector remains a fixed-5 V sink. The endpoint is limited to RBR
(1.62 Gb/s per lane), initially targeting 1080p rather than 4K.

The port preserves downstream copyright notices and credits the
[pinned LG-derived PLL implementation](https://github.com/LineageOS/android_kernel_lge_msm8998/blob/c022ed57679b432bff277eaca0a2366a72218925/drivers/clk/msm/mdss/mdss-dp-pll-8998-util.c),
[clock graph](https://github.com/LineageOS/android_kernel_lge_msm8998/blob/c022ed57679b432bff277eaca0a2366a72218925/drivers/clk/msm/mdss/mdss-dp-pll-8998.c),
[legacy AUX implementation](https://github.com/LineageOS/android_kernel_lge_msm8998/blob/c022ed57679b432bff277eaca0a2366a72218925/drivers/video/fbdev/msm/mdss_dp_aux.c)
and corrected upstream MMCC work. Offline compilation and image checks passed,
but did not qualify the following runtime paths.

Exactly one authorized r49 RAM boot registered Type-C and a DP connector.
The local Alt Mode exposed SVID `0000`: the DT encoded `ff01` as uint32 and
named the child `altmode-displayport`. The
[USB connector binding](https://github.com/ShapeShifter499/linux-lg-v30-joan/blob/1b42626b2b448d8fe97d7e2e0a63dec93c3bdaae/Documentation/devicetree/bindings/connector/usb-connector.yaml)
requires a uint16 SVID and the child name `displayport`. The earlier validation
selector missed the actual connector schema, so its coverage was incomplete.
No AOC connection, EDID read or pattern was attempted.

The diagnostic's live DP unbind also removed the shared DRM master and internal
DSI components. It triggered a GEM pin-count warning and a delayed NULL-pointer
Oops in the self-refresh worker. A logical module-cleanup receipt was therefore
not evidence of safe teardown. The readonly-root gate aborted, and an ordinary
software reboot did not finish. Operator key recovery restored r35/r30.
Independent checks confirmed IMS and all 11 paused services, landscape TTY,
Bluetooth off, four closed PCM streams, no GUI/seatd, zero ext4 errors, unchanged
partition/protected hashes, and preserved two-SMS/four-call archives with SQLite
checks. The r49 authorization is closed. Do not replay its unbind or cleanup
scripts, and do not reuse this kernel for a DT-only retry.

## Corrective candidate: r50

r50 changes five source files relative to the retained r49 tree:

- Use the standard `displayport` child and `/bits/ 16 <0xff01>` SVID.
- Export the old PHY's link-2x clock rather than the link clock; select the PHY
  link/pixel parents explicitly for MMCC. The source-derived RBR contract is
  a 324 MHz PHY parent divided to the controller's 162 MHz link clock.
- Reinstate suppressed DP bind/unbind attributes. Add normal DP-controller,
  QMP-PHY and TCPM shutdown callbacks without deleting active DRM components.

Full ARM64 kernel and 1,636 matching modules passed compilation and vermagic
checks. Configuration differs from the qualified r30 only in LOCALVERSION.
The independent DTB audit permits only the connector correction and explicit
clock-parent assignments; all 688 common nodes preserve their existing property bytes; the DP node
only gains the explicit clock-parent assignments. The selected connector, DP, PHY and SBU schemas now produce no diagnostics.
Negative controls reject both the old 32-bit SVID and wrong child name. This is
selected-node validation, not a zero-warning claim for the whole board; the
inherited parent-MDSS/disabled-HDMI diagnostics remain outside these changes.

The 51 ordered PLL writes, ten TX initial values and old PHY register offsets
still match pinned stock sources. The five-file review patch applies back to
identical source bytes and has zero checkpatch errors/warnings with signoff
checking disabled. These offline checks alone do not claim new DCO certification, upstream
submission or hardware qualification; see the bounded result below. All four temporary build mounts have been released.

The RAM image is 28,053,504 bytes, SHA256
`94ca6663e386890bd63d8c694e3b9c336b1c97464814228346479c9d69c7c90d`.
It preserves the default command line and 331 unrelated initramfs entries;
18 module files match the candidate, including four kernel modules. Exactly one r50
RAM boot has now passed the bounded result below. CCF clock reports confirm
programmed link/pixel rates, not physically measured frequencies. Normal
shutdown/default recovery passed this one cycle; broader operation remains
unqualified. See the [bounded validation record](../provenance/r48-r50-external-display-validation.json).

## First 1080p60 RAM result

The initial phone screen stayed black while the DP controller waited for its
module providers and the shared DRM master had not bound. SSH subsequently
became available. Loading the planned matching SBU/QMP/TCPM modules created the
DSI/DP connectors and framebuffer; landscape TTY, Bluetooth off, four closed
PCM streams, protected hashes and local uint16/`ff01` checks passed. The operator
then confirmed normal TTY before attaching the AOC. This r50 cycle is not a
clean-boot pass; the later r51 trial below separately passed automatic loading.

The AOC connection entered partner DP mode `ff01`, selected pin C, asserted HPD
and used reversed plug orientation. AUX returned a 256-byte EDID with valid
block checksums. A compatible CRTC and `1920x1080-60` mode were selected.
Exactly one static XR24 pattern ran for 20.17 seconds and exited with code zero.
The operator reported a complete, stable monitor image and normal phone TTY.
The during-pattern CCF report showed a 162 MHz link clock and 148.5 MHz pixel
clock. No raw DPCD character-device result was available. EDID listing 4K modes
does not qualify 4K output.

After reconnecting to the Mac, DP detached and USB SSH recovered. No live
unbind or module removal was used. Ordinary PID1 reboot returned to the
unchanged r35/r30 default without operator key recovery. IMS, UNICOM 4G and all
11 paused services recovered. Landscape TTY, Bluetooth off, four closed PCM
streams, zero ext4 errors, unchanged boot/recovery and protected file hashes,
and preserved two-SMS/four-call archives with SQLite checks passed. Phone and
host authorizations are closed. No additional RAM/pattern is allowed by this
one-shot result.

Logs retain an early USB clock-reference warning, one Type-C DP probe `-71`
and a DSI wait-for-idle `-11`. No Oops was observed in this trial. The successful
static picture does not resolve those warnings or qualify sustained graphics,
repeated hotplug, the opposite plug orientation, external audio, charging
consumption, new-kernel voice/SMS behavior or 4K.

## USB2 integration result: r51 startup passed, external GUI rejected

r51 reuses the audited r50 kernel, DTB and all 1,636 matching modules; the
kernel release still identifies r50. It is an initramfs/userspace integration
candidate rather than another kernel build. Its independently audited RAM image
has SHA256
`3238ccc3b52f50419905ee8c0c8929bc89f9e85530cc99ba3a49c511feb6e2ff`.
Nine matching kernel modules and one early-loading hook are added while all
349 original cpio entries retain their bytes. The hook is intended to make the
DP/Type-C dependencies available before the shared DRM master is needed.
USB data stays on USB2; this does not enable or qualify USB3.

Matching-module reuse verification and staging of 12 private GUI files completed
before exactly one authorized RAM boot. The five planned providers loaded
automatically, with zero manual modprobes. Framebuffer/DSI/DP registration,
authenticated landscape TTY, Bluetooth-off and no GUI autostart passed. This is
a bounded startup pass. Production r30 telephony guards remained unchanged:
the private display entry was bound to the exact release, authorization and RAM
boot, and required IMS to be absent. No new-kernel telephony pass is claimed.

The updated source interface is `sudo v30-gui start --output MODE`, where MODE
is `auto`, `internal` or `external`; `start` defaults to `auto`. At session start,
`auto` chooses connected DP-1 or falls back to DSI-1. Explicit `internal` keeps
the phone profile; explicit `external` refuses an absent/disconnected DP-1.
An initial precheck also rejected a missing sysfs 1920x1080 entry, but that list
was stale. A trusted read-only `modetest` connector/resource probe returned a
valid 256-byte EDID and 1080p60, and refreshed the mode list. Two premature
precheck lines were removed from the private controller, retaining the old
source, original once marker and a separate marker for the next request. No
GUI window had opened before this fix, and the kernel image was unchanged.
The external profile requests a full,
fixed 1080p60 mode line, 1920x1080 rootful Xwayland and GTK scale 1; internal
retains portrait 1440x2880 and GTK scale 2. Weston DRM/Pixman memory-shadow
rendering and Xwayland `-shm` retain the software path, with Glamor disabled.

The only actual GUI window ran Weston/Pixman, rootful Xwayland, GTK and Onboard
on tty8. Software state reported DP-1 enabled at 1080p60 and DSI-1 disabled.
The operator instead saw a white phone screen, blue monitor and no cursor:
physical acceptance failed. The G102 pointer enumerated and was associated
with DP-1; its composite keyboard interface is not proof of a separate USB
keyboard. Visible cursor movement or usable input was not established.
Phone stmfts remained mapped to DSI-1 by the live `WL_OUTPUT` property.

The 180-second diagnostic deadline ended this window. Cleanup reported no
GUI/audio helpers or seatd, restored VT permissions, tty1/rotation1,
Bluetooth-off, closed PCM streams and unchanged mixers. Persistent DPU CTL
flush/vblank/ppdone/kickoff timeouts remained, so software tty1 and exit0 did
not establish physical phone-screen recovery. The second external-detach and
third internal-touch windows were skipped; unplug recovery is unqualified.

After reconnecting the Mac, ordinary PID1 reboot restored the unchanged
r35/r30 default without live-unbind, module removal, force reboot or key reset.
The operator confirmed normal landscape TTY. IMS, all 11 paused services,
Bluetooth-off, four closed PCM streams, unchanged mixers, zero ext4 errors,
preserved two-SMS/four-call archives with SQLite checks, and unchanged
production/runlevel/boot/recovery hashes passed. Both authorizations are closed;
29 evidence files were archived and hash-verified without exporting SQLite.
No call, SMS or flash was performed. No old window or RAM marker is reusable.

## r51 failure timeline

The complete same-boot kernel timeline includes DSI wait-idle `-11` at 129.727 s
and a DP video-path CTL flush timeout at 432.437 s, before GUI startup at
497.11 s. A further timeout appears at 499.901 s after startup. The printed
`vblank timeout:%x` value is the DPU CTL flush value that remained pending;
it is not an IRQ number or mask. DPU VSYNC handling and DP AUX/READY handling
belong to different interrupt domains. No Oops was observed, but repeated
flush/vblank/ppdone/kickoff failures reject sustained presentation health.

Disabling DSI and changing from r50's static legacy KMS operation to Weston's
continuous atomic path are separate differences. Neither is a proven root
cause, and the pre-GUI DP timeout rules out treating all failures as a direct
consequence of DSI-off. The r50 static picture remains a bounded pass; it did
not test sustained pageflip/flush progress.

## Private r52 dual-output trial: interaction passed, detach failed

One separately authorized r52 RAM boot reused the r51 integration image above
and the unchanged r50 kernel/DTB/modules. Its private userspace profile retained
DSI `mode=current`, kept DP at the full fixed 1080p60 timing and targeted rootful
Xwayland at DP-1 with `-output DP-1` plus kiosk
`app-ids=org.freedesktop.Xwayland`. The internal panel was assigned compositor
background, not simultaneous TTY. Pixman/`-shm`, no GUI autostart, disabled
graphical audio and production r30 telephony guards were retained. The public
runtime remains the rejected r51 single-output prototype; it does not contain
the tested private r52/r54 profiles or the r52/r53/r54 harnesses.

The bounded 10-second legacy `modetest -v` gate completed nine batches of 60
pageflips, at least 540 real completion events, and exited normally. Recorded
DP VSYNC counts advanced 994 to 1362 to 1637; DSI mapping remained present and
no new DPU errors were recorded during that gate. Alternation between color
bars and a plain-color buffer is expected diagnostic behavior, not abnormal
flicker. The operator confirmed that alternation and normal phone TTY. This
extends r50's static observation with bounded flip/IRQ progress; it is not a
long-duration or all-path qualification.

The first dual-output GUI window passed operator-confirmed external picture,
mouse/input, Chinese input and Return to TTY. Cleanup passed: GUI/helper and
seatd absence, tty8 permission restoration, unchanged mixers and four closed
PCM streams. The 1920x1080 software PNG only establishes rendered application
pixels; physical input acceptance comes from the operator's direct feedback.

The second GUI was active when the operator unplugged the AOC and connected
the Mac. The LG logo appeared and a new r35/r30 boot followed. The host
controller did not run its default-transition script. This is an unexpected
reset and a failed detach-to-TTY test; do not describe it as a clean graphical
exit or requested default reboot. The root cause is unknown. Pstore was
mounted but empty, and logbook contained zero rows for the RAM boot, leaving
no retained crash evidence from those channels. These absences neither prove
nor exclude a panic, watchdog, power event or display/Type-C failure.

Post-reset full health checks passed unchanged r35/r30, physical landscape TTY,
IMS, all 11 previously paused services, Bluetooth-off, four closed PCM streams,
zero ext4 errors, original two-SMS/four-call content and SQLite checks, and
unchanged protected/runlevel/boot/recovery hashes. Authorization is closed;
read-only quick_check also passed the live shijing and logbook databases,
including WAL; full application-content comparison was not performed. No call, SMS,
partition flash or default promotion was authorized by this display scope.
The first successful interaction does not qualify hotplug safety, sustained
operation, higher modes or new-kernel telephony. See the
[bounded r52 validation record](../provenance/r52-dual-output-validation.json)
and [manual desktop](manual-desktop.md).

## Private r53 legacy active-detach result: no GUI, reset reproduced

One separately authorized RAM boot reused the same r51 image and unchanged
r50 kernel/DTB/modules. No GUI was launched. The trusted legacy
`modetest -F plain -v` window reached the detach gate after at least 240 real
completion events, DP IRQ progress, retained DSI and no new display errors at
that gate. The complete stream contained 61 batches, at least 3,660 pageflip
completions. The operator confirmed a stable gray AOC image; this plain-buffer
test does not require a visibly alternating pattern to prove pageflip progress.

The operator distinguished two stages: normal phone TTY after removing AOC,
then a reset after inserting the Mac. A new default boot was independently
verified. The host did not request default-transition or reboot. Thus a GUI
is not necessary to reproduce the reset, but the operator's timing observation
does not by itself locate the reset mechanism. The active sequence failed;
this is not a clean return or safe-hotplug pass.

An independent Wi-Fi reader preserved 5,352 kernel records, sequence 12,891
through 18,242, with no sequence gaps, kmsg overruns or partial final line.
All records match the trial, and the last kernel timestamp is 261.801160 s.
The SSH connection ended without a final controller result; data not delivered
before reset may still be missing. Pstore remained empty and the previous RAM
boot had no logbook rows, so no panic or reset cause is established.

The received timeline shows a concrete display-path problem: after unplug with
sink_count still 1 and normal PHY shutdown, the old cached
1280x1024@75/135000 timing is re-enabled. AUX has already been disabled in
software and returns `-6`; link startup returns `-104`, followed by DPU
frame/CTL-flush timeouts. These are not evidence of a successful offline-sink
training attempt, nor do they prove that this path caused the system reset.
The last received USB record is an old downstream-device disconnect, not proof
that Mac device-role/PHY initialization was reached.

Post-reset checks passed unchanged r35/r30 full health, authenticated landscape
TTY, Bluetooth-off, IMS, all 11 paused services, closed PCMs, zero ext4 errors,
production/runlevel/boot/recovery hashes and original SMS2/calls4 content with
SQLite checks. Live shijing and logbook databases passed read-only structural
quick_check including WAL; full business content was not compared. Pre-RAM
on-device backups completed. Forty phone evidence files were archived and
hash-verified without exporting SQLite. Authorization is closed; there was no
call, SMS or partition write. See the [bounded r53 record](../provenance/r53-legacy-detach-validation.json).

## Private r54 hardware result: legacy transition passed, GUI unplug failed

One separately authorized RAM boot tested a six-line change in one fbdev helper:
process pending hotplug before cached-mode restore, preserving force and
no-pending paths. Build, complete-module and independent-image audits preceded
this physical test. Automatic providers and landscape TTY passed with zero
manual modprobes. The single legacy window completed at least 2,640 real
pageflips; after AOC removal, a three-second observation and Mac attachment,
the phone retained the same RAM boot with no new display errors and exit0.
This passes the bounded legacy stale-cache comparison.

The first GUI window passed operator-confirmed physical picture/input/Chinese
and manual Return to TTY, with exit0 and full cleanup. Terminal character
spacing was too wide and remains for r55 validation. During external GUI the
phone shows compositor background by profile design; that does not prove
internal scanout quality.

The operator precisely confirmed that the second GUI reset within three seconds
of removing AOC, before connecting the Mac. A new unchanged-default boot and
normal phone TTY were independently confirmed; the host did not request
default-transition or reboot. GUI detach-to-TTY failed. The six-line fix does
not qualify GUI hotplug, explain reset or justify default promotion.

Independent Wi-Fi capture saved 20,834 consecutive kmsg records, sequences
12,864–33,697, with no gaps, overruns or partial final line. The final timestamp
is 1269.762634 s. DP shutdown was followed by new atomic-check resource
reservation for CRTC 89, including LM0/LM1 already-reserved messages. No
completed hardware re-enable, new link training or panic was recorded; the
caller and reset cause are unknown. Pstore was empty, the previous RAM boot
had zero logbook rows, and full Weston/controller logs disappeared with volatile
runtime storage. The tail must not be relabeled as a traced Weston restore or
completed DP enable.

Default r35/r30 full health passed: independently verified normal authenticated
landscape TTY, registered IMS, all 11 services restored, Bluetooth off, four
closed PCM streams, zero ext4 errors and unchanged source/protected/runlevel/
boot/recovery hashes. The original SMS2/calls4 content and SQLite checks passed;
live shijing/logbook read-only quick_check included WAL and passed, without a
full application-content comparison. Default drm.debug is 0 and the private
r54 runtime is absent from the default. Forty-nine owned phone evidence files
were downloaded and hash-verified, without SQLite export. Authorization is
closed; calls, sent SMS and partition writes were all zero. See the
[bounded r54 record](../provenance/r54-fbdev-hotplug-validation.json).

## Current publication and diagnostic boundary

The public runtime is still the rejected r51 single-output prototype. The
tested private r52/r54 profiles and r52/r53/r54 harnesses have not been merged;
staging this repository does not reproduce their bounded results. r56 only
prepares offline feasibility checks for caller kprobes and a persistent Weston
stream using the existing r54 image. It has no new RAM/GUI authorization or
hardware result. Default external
output remains unintegrated and production r30 telephony guards stay unchanged.

## Remaining integration and acceptance

1. Preserve r51's bounded automatic-loading/landscape-TTY/no-autostart pass;
   do not reuse its closed authorization or promote its rejected GUI profile.
2. Preserve r52's bounded flip-progress and first desktop/input/ReturnTTY pass,
   r53's no-GUI reproduction/live evidence and r54's legacy-transition/manual-GUI
   passes. Diagnose the transition and GUI-unplug resets before claiming safe
   hotplug or promoting a default; removing the stale-mode sequence alone did
   not resolve the GUI failure.
3. Keep production r30 telephony guards unchanged until a separately scoped
   integrated candidate qualifies IMS and voice compatibility. The r50 trial
   stopped IMS and performed no call or SMS; r51/r52/r53/r54 display scopes do not
   qualify those services either.
4. For each concrete RAM candidate obtain fresh applicable on-site/key-recovery
   authorization, stage verified modules, preserve one-shot limits and return
   to the unchanged default. Never live-unbind or unload active DRM components.
5. Qualify detach/reconnect, both orientations, sustained output and default
   recovery; then assess higher modes from actual sink/link capabilities. Any
   default boot promotion requires a concrete reviewed candidate and approval.

The unchanged r35 default remains authenticated landscape TTY, Bluetooth off,
with optional graphics. It still has no external output. No boot/recovery
write, call, SMS or GitHub publication was performed for this work. Phosh and
Plasma Mobile testing follows the external-output integration work; the
internal strip investigation remains deferred.
