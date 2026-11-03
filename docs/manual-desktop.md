# Optional manual graphical session

See the [r81 checkpoint](r81-progress.md) for the latest default and test scope. Older results below describe their original baselines.


The r39 extension keeps authenticated landscape tty1 and Bluetooth-off as the
boot default. The current experimental profile starts Weston on tty8 with its
DRM Pixman renderer and an ordinary-memory shadow framebuffer. Software rootful
Xwayland hosts Openbox, a GTK3 touch launcher/scratchpad, XTerm, Onboard and UIM
Pinyin. The internal profile uses native portrait 1440x2880, identity touch
mapping and GTK scale 2; returning restores landscape tty1. This r39 profile
failed physical display-quality and rapid-input acceptance and is retained for
diagnosis. This is a minimal server UI.

On 2026-11-02, the single authorized r51 USB2 RAM trial passed automatic provider
loading, landscape TTY and no GUI autostart, but its only actual external GUI
failed: the operator saw a white phone screen, blue monitor and no cursor.
The other two planned GUI windows were skipped. Ordinary reboot subsequently
restored r35/r30, with physically confirmed landscape TTY, IMS/all 11 services,
preserved archives and protected hashes. The authorization is closed; default
external output is not integrated. The source adds output selection to this
software-rendered session, without enabling GUI/greetd/seatd at boot.

A separately authorized r52 RAM trial subsequently passed its legacy pageflip
gate and one physically confirmed dual-output desktop/input/Chinese/Return to
TTY cycle. The second GUI window failed detach acceptance: unplugging the AOC
and reconnecting the Mac was followed by an LG-logo reset into the unchanged
r35/r30 default. Its cause is unknown, and r52 is not promoted. The runtime
published here remains the rejected r51 single-output prototype. The tested
r52/r54 profiles and r52/r53/r54 authorization-bound harnesses are private; staging this
public runtime does not install those tested profiles. A later r53 legacy
plain-buffer run reproduced reset without any GUI: the operator saw normal TTY
after removing AOC, then reset after inserting the Mac. The cause remains
unknown. The later r54 hardware test passed the bounded legacy transition and
one manual GUI return, but its second GUI reset after removing AOC alone,
before Mac attachment. The stale-mode sequence has a bounded correction;
GUI hotplug and the reset mechanism remain unresolved.

## Installation and use

Include files with `python3 scripts/stage-rootfs.py out/rootfs --desktop`.
Staging never installs packages, enables a display manager or starts a session.
The inspected distribution splits Weston into `weston`, `libweston`,
`weston-backend-drm` and `weston-shell-kiosk`. The profile also uses `seatd`,
`xwayland`, `xinit`, `xauth`, `openbox`, `xterm`, `onboard`, `uim`, `uim-gtk3`,
`font-noto-cjk`, `greetd`, GTK3 introspection, PyGObject and XTest. Inspect the
version-specific signed package plan before changing a working device. Existing
packages were not upgraded or replaced in this experiment. Full Phosh was not
selected because its inspected plan replaced polkit and added PulseAudio to a
baseline reserving physical audio for calls. Phoc and legacy fbdev files are
experimental references, not additional recommended profiles.

```sh
sudo v30-gui start
sudo v30-gui start --output auto
sudo v30-gui start --output internal
sudo v30-gui start --output external
sudo v30-gui status
sudo v30-gui stop
```

These commands describe the public r51 prototype's interface, not the tested
private r52 candidate or installation on the unchanged default. `start`
defaults to `auto`: a connected DP-1 at session start
selects external output; otherwise it selects DSI-1. `internal` keeps the phone
profile even when DP is connected. `external` requires a connected DP-1.
The r51 trial exposed a stale sysfs mode cache: an initial missing-1080p check
refused startup before a window opened, but a trusted read-only DRM probe
returned valid EDID256/1080p60. The two premature precheck lines were removed,
preserving the old source/once and using a new marker for the actual attempt.
Selection happens once per session; connecting a monitor later does not migrate
an internal session.

The external profile requests the fixed 1080p60 timing used by r50, with a
1920x1080 rootful Xwayland desktop and GTK scale 1. A full mode line avoids
Weston falling back to a sink's preferred 4K mode when shorthand matching
fails. Weston still uses DRM/Pixman with its memory shadow; Xwayland stays on
`-shm`, disabling Glamor. This is a requested mode and software path, not a
physical GUI-output or frame-rate result.

The rejected r51 profile enables only the selected output and disables DSI
scanout during external GUI. Its physical result was a white phone screen and
blue monitor, so neither a clean dark phone nor physical TTY restoration after
GUI exit is promised by this result. The compositor owns DRM on tty8;
simultaneous visible phone TTY is not promised. The intended external desktop
requires a USB keyboard and mouse.
The stmfts touchscreen is confined to DSI-1 with `WL_OUTPUT`; external startup
checks the live udev property and refuses a stale mapping. Installing the rule
alone is insufficient for an already enumerated device. With DSI disabled,
phone touch does not navigate the external desktop.

External disconnect requests session cleanup and TTY return; it does not switch
to phone GUI. This path has offline simulation coverage, but the r51 detach
window was skipped and physical recovery remains unqualified. As with forced stop,
disconnect does not promise to save unsaved scratchpad edits. `start` launches
the controller in the background; its return code does not establish GUI
readiness. Inspect `status` and `/run/v30-desktop/controller.log` for startup
failures.

The explicit privileged start launches the configured local `v30` account
through greetd/PAM on unused tty8. No integration file replaces the default
greetd configuration or enables passwordless login at boot. Check the configured
account and free VT when adapting this profile. The controller starts its own
temporary seatd broker and removes it on exit; it refuses to replace an existing
seat socket. Neither greetd nor seatd is enabled in a boot runlevel.

The public controller retains the production call-state gate. The closed r51
and r52 RAM trials used separate controllers bound to their exact release,
authorization and boot, requiring IMS to be absent; they did not add a general skip-call option or relax
the production r30 telephony guards. New-kernel IMS/voice/SMS compatibility is
outside the display trial's acceptance claim.

Use Keyboard to show Onboard, then touch the scratchpad. Chinese / EN toggles
Pinyin for that field. Ctrl+Space and Shift+Space are configured explicitly in
`/etc/v30-desktop/uim.scm`, selected with `LIBUIM_USER_SCM_FILE` without changing
`~/.uim`. The GTK3 launcher uses native UIM; XTerm uses its XIM bridge. The
installed UIM default was Shift+Space, so the earlier Ctrl+Space guidance was
incorrect before this session-specific configuration was added.

UIM py is a basic syllable-based Pinyin table. Enter nihao and press Return for
the default greeting; Space advances candidates. Both an isolated GTK3 entry
and operator testing passed Chinese input on the earlier native Xorg profile.
The new Weston/Xwayland path also read back the greeting in an isolated entry;
the subsequent physical test still found delayed text/key feedback and horizontal strips. This is not Android phrase
prediction. Terminal opens XTerm; run exit to return to the launcher.

Return to TTY saves plaintext to `$HOME/.local/share/v30-desktop/note.txt`, mode
0600, and ends the session. This scratchpad is separate from the SMS archive.
Forced stop does not promise to save edits.

## Private r52 dual-output result

The private r52 profile reuses r51's integration image and r50 kernel/modules.
It retains DSI `mode=current`, requests fixed 1080p60 on DP-1, assigns
`app-ids=org.freedesktop.Xwayland` to DP and launches rootful Xwayland with
`-output DP-1`. During this GUI the phone has compositor background rather than
a simultaneous TTY. Software Pixman/`-shm`, disabled graphical audio, manual
startup and the production telephony guards remain in place. This comparison
does not prove which difference caused r51's failure.

Before GUI, one bounded legacy `modetest -v` run completed nine batches of 60
pageflips, at least 540 real completion events. The recorded DP VSYNC count
advanced 994 to 1362 to 1637, DSI mapping stayed present and no new DPU display
errors were recorded in this gate. Alternating color bars and a plain-color
buffer are the diagnostic's expected pattern, not abnormal flicker. The
operator confirmed that alternation and normal phone TTY.

In the first dual-output GUI window, the operator confirmed a normal external
desktop, mouse/input, Chinese input and Return to TTY. Cleanup verified no GUI
helpers or seatd, restored tty8 permissions, unchanged mixers and four closed
PCM streams. A 1920x1080 software PNG corroborates application rendering; it
does not establish physical presentation. Physical interaction acceptance here
comes from the operator's feedback.

In the second active GUI, the operator unplugged the AOC and reconnected the
Mac, saw the LG logo and reached a new r35/r30 boot. The controller did not
execute its default-transition script. This is a failed detach/recovery test,
not a successful session-only return or ordinary requested reboot. Pstore was
mounted but empty, and the RAM boot had zero logbook rows, so those sources do
not establish a panic, watchdog, power or driver cause.

Post-reset checks passed physical landscape TTY, IMS, all 11 previously paused
services, Bluetooth-off, four closed PCM streams, zero ext4 errors, preserved
two-SMS/four-call archives with SQLite checks and unchanged protected/runlevel/
boot/recovery hashes. Authorization is closed; read-only quick_check also
passed the live shijing and logbook databases, including WAL; full application
content comparison was not performed. The unchanged r35 default has no
integrated external output, and GUI remains manual. Detach safety, repeated
cycles, sustained output and new-kernel telephony are still unqualified.
Phosh/Plasma and resource comparisons follow this work. See the
[bounded r52 record](../provenance/r52-dual-output-validation.json).

## Private r53 no-GUI comparison

The separately authorized r53 RAM trial reused the same r51 integration image
and r50 kernel/modules, with zero GUI windows. Its legacy `-F plain -v` gate
passed at least 240 real completion events, DP IRQ progress, preserved DSI and
no new display errors at the gate. In total, 61 batches show at least 3,660
completed pageflips. The operator saw a stable gray monitor, normal phone TTY
after removing AOC, then reset after inserting the Mac. The host did not request
reboot. This shows that a GUI is not necessary for the reset; it does not
identify whether the reset originated in display, USB/Type-C, power or another
path.

Independent Wi-Fi capture saved 5,352 consecutive kernel records without gaps
or overruns. After normal PHY shutdown, the old cached 1280x1024@75 timing was
incorrectly enabled again; software-disabled AUX returned `-6`, link startup
returned `-104` and DPU timeouts followed. This is a specific display-path
failure, not a proven cause of reset. The stream ends before a final controller
result and cannot guarantee receipt of the last pre-reset messages.

Default r35/r30 full health, IMS/all 11 services, authenticated landscape TTY,
original SMS2/calls4 content/SQLite and protected hashes passed. Shijing and
logbook live databases passed read-only structural quick_check including WAL;
full business content was not compared. Forty phone evidence files were
archived/hash-verified without SQLite export, and authorization is closed.
No GUI, call, SMS or partition write was performed. See the
[bounded r53 record](../provenance/r53-legacy-detach-validation.json).

## Private r54 hardware result

One separately authorized RAM boot physically tested the six-line change in
one fbdev helper: process pending hotplug before cached-mode restore, with
force and no-pending paths preserved. The single legacy window completed at
least 2,640 real pageflips. Removing AOC, observing for three seconds and
connecting the Mac left the same RAM boot running, with no new display errors
and exit0. Automatic loading required zero manual modprobes.

The first GUI passed physical picture/input/Chinese, manual ReturnTTY, exit0
and full cleanup. Terminal character spacing was overly wide; r55 is preparing
a separately verified correction. The phone's compositor background during
external GUI is profile design, not a scanout-quality test.

The second GUI reset during the three seconds after removing AOC alone, before
Mac attachment. The operator confirmed that distinction and normal TTY after
reconnecting; independent USB/Wi-Fi checks verified the new default boot. The
host did not request reboot. Thus the legacy stale-cache sequence passed its
bounded comparison, while GUI hotplug and automatic detach-to-TTY still failed.

The independent live stream contains 20,834 consecutive kmsg records without
gaps or overruns, ending at 1269.762634 s. DP shutdown is followed by new
atomic-check resource reservation for CRTC 89. No completed hardware re-enable,
link training or panic was recorded; caller and reset cause remain unknown.
Full Weston/controller logs were lost with volatile runtime storage. Pstore
was empty and the old RAM boot had zero logbook rows. These absences cannot
identify the reset mechanism or establish that Weston restored an initial mode.

Default r35/r30 full health passed, including authenticated landscape TTY,
IMS/all 11 services, Bluetooth off, four closed PCMs, zero ext4 errors, original
SMS2/calls4 content and SQLite checks, and unchanged source/protected/runlevel/
boot/recovery hashes. Live business-database read-only quick_check included
WAL and passed, without full application-content comparison. Default drm.debug
is 0 and private r54 runtime is absent from the default. Forty-nine phone
evidence files were downloaded/hash-verified without SQLite export;
authorization is closed, with no calls, sent SMS or partition writes. See the
[bounded r54 record](../provenance/r54-fbdev-hotplug-validation.json).

Public runtime remains the failed r51 prototype; the tested private r52/r54
profiles and r52/r53/r54 harnesses are not merged. r56 only prepares offline
caller-kprobe and persistent Weston-stream feasibility checks using the existing
r54 image. No new RAM/GUI authorization remains. Default external integration,
GUI hotplug and new-kernel telephony remain unqualified; production r30 guards
are unchanged.

## Display failures and current candidate

- Phoc GLES/GTK GL accepted touch/Pinyin but produced GPU translation faults,
  lag and corruption. A landscape Pixman/Cairo variant had no new GPU fault in
  the inspected interval, but the operator still rejected its display quality.
- Xorg fbdev initially lacked stmfts permissions. A scoped rule assigns only
  that touchscreen to the existing video group with mode 0660; group membership,
  other input-device permissions and PAM were not changed. Later taps changed
  application pixels while the physical panel stayed stale. Blank/unblank
  revealed the updated page. The inspected MSM fbdev mmap path bypasses deferred
  write damage; this was a presentation failure distinct from touch handling.
- XDamage plus unchanged-offset FBIOPAN_DISPLAY restored clicking. Native
  portrait, session-local GTK animation settings and the UIM fix improved
  usability enough for operator-confirmed Chinese input, with occasional strips
  and residual latency. Full-frame CRC polling took about 549 ms and was rejected.
- An integration-owned Xorg copy-completion callback was compiled and loaded,
  then rejected: committing after every copy regressed synthetic latency;
  coalescing copies still produced operator-observed horizontal strips and slow
  rapid input. Its binary, source wrapper and build/staging option have been
  withdrawn from the current solution. Private diagnostic evidence is retained.
- Native portrait Phoc/Pixman switched DRM scanout buffers, but an automated
  label probe painted only 20 frames over 7.88 seconds, with a median interval
  of 327.84 ms. It was stopped without asking for another physical test.
- Weston Pixman now draws into an ordinary-memory shadow before copying into
  separate DRM scanout buffers. Xwayland uses `-shm`, disabling Glamor. No fbdev
  refresh helper or preload runs in this profile. A GTK3 label probe requested
  188 updates and painted 187 frames over 8.29 seconds; median paint interval
  was 33.37 ms, with a 544.24 ms maximum including startup. DRM state sampling
  observed 143 framebuffer changes with a 51 ms median interval. These are
  diagnostic software timings, not calibrated touch-to-photon latency, and do
  not establish physical freedom from strips. Operator acceptance failed: brief horizontal strips and delayed text/key feedback remain. The profile was stopped and tty1 restored.

The memory-shadow configuration follows the inspected Weston 16.0.0 source
(`pixman-shadow=true`) and the
[official Weston running guide](https://wayland.pages.freedesktop.org/weston/toc/running-weston.html).
The device log confirms Pixman and a shadow framebuffer. This avoids the
previous single fbdev frontbuffer workaround; it does not resolve the separate
GPU driver fault or qualify hardware acceleration.

## Isolation and return path

GUI preferences use the separate dconf database `v30_desktop` and per-session
XDG_CONFIG_DIRS. GTK animations and cursor blink are disabled only for this
profile. Runtime files use `/run/v30-desktop/user`; graphical PulseAudio and
PipeWire endpoints are disabled, separate from per-call audio. TTY metrics
pause while tty1 is inactive and resume after return.

Cleanup stops the owned graphical session and seat broker, then known GUI
helpers matching both the configured UID and private runtime. It does not kill
arbitrary background jobs or default user/system buses. The controller restores
text/automatic VT mode and activates tty1; PAM/elogind descriptor revocation
requires reopening the console on EIO. One Weston start/stop cycle returned
inactive/exit0 and tty1 with no remaining GUI/private-runtime process or seat
socket. Six baseline services stayed running, IMS registered, four PCM devices
closed, SMS counts unchanged, Bluetooth off, and boot/protected files/runlevels
unchanged. No new GPU fault appeared in that interval. Repeated and physical
return cycles remain to be qualified for this renderer.

On the unchanged r39/r30 profile, cellular/IMS/SMS services continue
independently; they were intentionally paused in the r51 display-only RAM scope.
Calls during a GUI session have not been qualified. The caller row and persistent missed/unread counts
belong to tty1. This launcher has no graphical phone, SMS client or notification
shade. No new call/SMS, reboot, flash or long-running GUI test is included in r39.
The private root receipt tracks installed hashes and rollback while preserving
message/call archives and notes.

## USB external display

The operator has prioritized USB2 plus native USB-C external output and an
on-demand GUI before full Phosh/Plasma testing. The r50 RAM trial produced one
operator-confirmed stable 1080p60 static image. r51 then passed automatic loading
of all five providers with zero manual modprobes, authenticated landscape TTY,
Bluetooth-off and no GUI autostart. Its only actual external GUI reached
DP1080p60/DSI-off with Weston/Xwayland/GTK/Onboard running, but physical output
failed: white phone, blue monitor, no cursor. G102 pointer enumeration and
association with DP-1 do not prove a visible cursor; the G102's keyboard
interface is not confirmation of a separate keyboard. The other two windows
were skipped.

The 180-second deadline ended the window. Process/seatd/VT/mixer cleanup passed,
but continuing DPU CTL flush/vblank/ppdone/kickoff timeouts meant software tty1
did not prove physical screen recovery. Ordinary PID1 reboot later restored
the unchanged r35/r30 default, with operator-confirmed normal landscape TTY,
IMS/all 11 services, archives and partition/protected hashes. The r51 scope is
closed, and the default still has no external output.

The complete kernel timeline already contains DP CTL flush timeout before GUI
startup. The reported value is a pending CTL flush value, not an IRQ mask;
DSI-off is not a proven root cause. The separate private r52 trial retained
DSI `mode=current` with compositor background while targeting Xwayland at DP-1.
It passed one physical GUI/input/ReturnTTY cycle after a bounded legacy
pageflip gate; its next detach test reset the phone. The later r53 legacy
comparison reproduced reset with no GUI, while distinguishing normal TTY after
AOC removal from reset after Mac insertion. r54 subsequently passed its bounded
legacy detach/reconnect and first manual GUI return, then reset during GUI
AOC removal before Mac attachment. See the bounded results above.
Production r30 telephony guards remain unchanged, and the public runtime is
still the rejected r51 prototype; private r52/r53/r54 profiles and harnesses are
not merged. r56 caller/Weston-stream work is offline feasibility preparation
without new RAM/GUI authorization. Phosh/Plasma and resource comparisons remain
later work. See the [current bring-up and bounded results](external-display.md).

[LG's V30 specifications](https://www.lg.com/ro/telefoane-mobile/lg-LGH930) list
DP-HDMI wired mirroring with adapter compatibility limits. This differs from
support in the unchanged r35/r30 US998 Linux stack, which exposes only the
internal DSI connector and no registered Type-C port. The r50 diagnostic kernel
and its bounded AOC result are separate from that installed default. A GUI
alone does not supply missing Type-C, Alt Mode, PHY or DRM support; a static
output pass does not qualify interactive desktop/input or default integration.

## Follow-up diagnosis after physical rejection

A private trace instance captured 270 commits on the unchanged r30 kernel.
Kickoff-to-transfer-done time had a 25.33 ms median and a 26.90 ms maximum.
Pageflip completion followed transfer-done by a median 0.55 ms. No enabled
underrun or transfer-timeout event fired in that automated label workload;
this does not establish that the operator-observed strip was reproduced.
The trace instance was removed and the GUI stopped afterward.

The installed kernel source lacks the newer upstream
[read-pointer pageflip patch](https://github.com/ShapeShifter499/linux-lg-v30-joan/commit/30d498482b40a09e6652fe40f301c7a6b747efd2).
That patch targets late pageflip notification. An isolated r40 build against
the existing r30 patch stack passed full ARM64 compilation, all 1,636 matching
module checks and an independent RAM-image audit. Its device tree, default
boot parameters and all non-module initramfs entries are preserved. It is not
selected by the default boot. One explicitly authorized RAM boot was completed
with the full matching module tree; no partition was flashed. This is not
evidence of a fix for the separate horizontal strip. Whole-kernel
rebasing and raw MMIO reads are not part of this diagnosis.

Existing cellular/IMS and call-media entry points pin the qualified r30 kernel
release. Those production guards remained intact during the display-only RAM
trial, which temporarily interrupted telephony and used a private diagnostic
entry point. After the test window elapsed, the agent requested normal window
closure through the application's save handler, verified TTY return and rebooted
into the unchanged r35 default. IMS, all previously stopped server services,
landscape TTY and Bluetooth-off were restored; boot/recovery hashes, two SMS
records and four call records were preserved. No fresh call or SMS test was made.
The operator later reported being away during the window and seeing TTY on
return. Physical strips, input responsiveness and Chinese input on r40 were
therefore **not assessed**. The one-shot authorization is closed.

A paired trace compared 270 r30 frames with 138 r40 frames. On r30, flip
notification followed transfer completion by a median 0.55 ms; on r40 all
sampled flips preceded it by a median 9.95 ms. Kickoff-to-transfer-done medians
were 25.33 ms and 13.65 ms respectively. This demonstrates that the upstream
mechanism ran; different runs and frame phases limit performance conclusions.
The r40 software probe painted 193 frames over 8.69 s, with a median interval
of 33.55 ms, so overall responsiveness has not clearly improved. Neither these
measurements nor the absence of enabled underrun/timeout events establishes
physical quality. No stable desktop qualification is claimed.

Any further RAM trial requires fresh on-site authorization and restoration to
the known-good default. A display-only result does not qualify calls on a new
kernel. Normal Linux USB enumeration returned after restoration, but USB SSH
still timed out; Wi-Fi was used for restoration health checks. USB reconnect
reliability remains open.

### Separately authorized r40 physical retest

A second, separately authorized RAM boot used the identical audited image and
reverified matching module tree. No automatic redraw workload was run during
the human test. The operator reported that horizontal strips and input latency
still occurred. Chinese input was not explicitly reported. The GUI exited
normally with status zero and returned to tty1; the phone then rebooted to the
unchanged r35 default. IMS, all 11 previously stopped services, landscape TTY,
Bluetooth-off, both archives and boot/recovery hashes passed restoration checks.
USB SSH worked in this trial and during restoration. Both RAM authorizations
are now closed; no partition flash or fresh call/SMS test occurred.

This rejects r40 as a symptom fix. It does not isolate the defect to rendering:
software composition, scanout and panel transfer remain possible stages. The
next diagnostic step is to compare a captured software frame with the physical
artifact before changing another stage of the pipeline. Do not promote the
candidate or relax the production r30 telephony guards on this evidence.

## Direct KMS rejection and a clock-only candidate

A later isolated profile removed Weston, Xwayland and the fbdev refresh helper:
Xorg's modesetting driver used native DRM/KMS with `AccelMethod none` and
`ShadowFB true`. It ran on the unchanged r30 kernel with the same GTK3/UIM
input components. After reboot, Xorg first failed to open tty8; the private
controller temporarily assigned only tty8 to the graphical account and restored
its original ownership/mode on cleanup. Touch and kernel damage tracking then
initialized. No global device permissions, production GUI files, packages or
boot runlevels changed. The operator still reported the same symptoms, so this
alternative is rejected too. It was stopped; landscape TTY, Bluetooth-off, IMS
and the six core services passed health checks.

Automated software probes had median paint spacing near 16.7 ms when requesting
16 ms updates, but also stalled for 3.18 s and 1.18 s. The 128 sampled synchronous
kernel commits had a 19.75 ms median and 25.86 ms maximum, with no enabled
underrun/timeout events. These results neither explain the software stalls nor
locate the physical strip. The prior probes requested 33 ms updates, so a lower
median alone is not an equivalent throughput comparison. Console metrics are
already gated to tty1, which rules out the simple theory of unconditional TTY
status writes over the GUI.

The [stock DV3.1 panel configuration](https://github.com/LineageOS/android_kernel_lge_msm8998/blob/c022ed57679b432bff277eaca0a2366a72218925/arch/arm64/boot/dts/lge/dsi-panel-sw43402-dsc-qhd-cmd-dv3_1.dtsi) enables
`qcom,mdss-dsi-force-clock-lane-hs`, and its
[clock controller](https://github.com/LineageOS/android_kernel_lge_msm8998/blob/c022ed57679b432bff277eaca0a2366a72218925/drivers/video/fbdev/msm/msm_mdss_io_8974.c) sets lane-control bit 28 while link clocks are
on. The current mainline panel enables `MIPI_DSI_CLOCK_NON_CONTINUOUS`; its DSI
host selects the corresponding HS force request only when that flag is absent.
This difference motivated the r42 experiment, but a later review found that upstream had already rejected the same continuous-clock direction for a blank/wake regression. That historical failure should have been checked first; this direction is closed. See the [upstream D2 record](https://github.com/ShapeShifter499/lg-v30-port/blob/master/docs/d1-dsi-link-rate-fix.md). The
stock TE-on command also has one byte, so it was not changed on speculation.

An isolated r42 candidate starts from the qualified r30 patch stack, excludes
the r40 early-flip change, and removes only the non-continuous-clock flag from
the panel. Mode timing, DSC, TE commands, brightness and power sequences stay
the same; configuration differs only in LOCALVERSION. Full ARM64 compilation,
all 1,636 matching modules and an independent RAM-image audit passed. The candidate subsequently completed one separately authorized RAM boot with
matching modules. The operator reported a black screen and did not observe the
initial TTY stage. Readback showed fb blank=0, backlight=255 and DRM active;
logs included an encoder-disabled transfer wait returning -11 and a touch error.
These messages do not prove causality, but physical black screen rejects the
candidate. The agent requested normal window closure through the save handler,
then rebooted to the unchanged r35 default. IMS, all 11 previously stopped
services, archives, landscape TTY, Bluetooth-off and partition hashes passed
restoration checks. The authorization is closed, production telephony guards
remain intact and no flash occurred. This failed candidate must not be promoted.

A separate input experiment now replaces Onboard with a small non-focusing GTK3
dock keyboard on the unchanged default kernel. It retains the same Xorg direct
KMS, Openbox and native UIM/Terminal path, and installs no new packages or
production-GUI replacements. Layout inspection and isolated native UIM readback passed. The operator reported much better clicks with slight remaining delay, but more frequent strips near touches; overall GUI quality still failed. Chinese input and Terminal were not separately confirmed in that manual trial. A full-window redraw comparison also failed, with strips near touches and the page top. Both profiles stopped cleanly and restored TTY/IMS/permissions.

An official libdrm two-buffer diagnostic subsequently reproduced the physical strips without GTK, Xorg, keyboard or cursor. See the [display investigation](display-investigation.md) for this stronger isolation result and the unproven DSC SCR1 candidate. The public launcher still retains the earlier experimental profile; these private comparisons are not a qualified production backend.
