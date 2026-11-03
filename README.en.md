# V30 postmarketOS

[Chinese](README.md) | **English**

Unofficial, experimental postmarketOS integration and reconstruction notes for the LG V30 US998, booting to an authenticated TTY with automatic screen orientation.

This project builds on **postmarketOS, Linux and ShapeShifter499's V30 mainline port**. The IMS protocol and media implementation come from **Catcrafts imsd**. Our additions cover component integration, boot ordering, per-call audio ownership and cleanup, persistent SMS, incoming alerts and ringtone volume, call history and persistent notifications, speaker-volume and cellular status, selected interoperability fixes, and scoped validation. See [acknowledgements](ACKNOWLEDGEMENTS.md) and [provenance](PROVENANCE.md) for upstream work and licensing.

**Validation applies to specific versions and tests.** Historical r35/r36 results came from one US998 on China Unicom. Host reconstruction/packaging checks are distinct from device observations; selected r37/r38 userspace changes and later revisions are scoped below. The complete published tree has not undergone a fresh end-to-end deployment on a clean device. The separate upstream PR candidates have no device qualification. Ready for review describes the PR stage, not upstream acceptance or device qualification.

See the [integration contribution map](docs/contributions.md) for our completed work and its upstream foundations, and the [open TODO / roadmap](TODO.md) for server reliability, ringing/caller ID, SMS improvements and remaining qualification work. Roadmap items include acceptance criteria and remain open until supported by evidence.

The Chinese README is a localized overview; the remaining project documentation and CLI messages are currently in English.

## Latest device checkpoint

The local default is r81. The authenticated console rotates with the phone
and keeps the same session. The LVGL touch panel and USB-C desktop start on
demand. Device checks cover two-way rotation and side margins, panel touch,
1080p external output with keyboard and mouse, recording/playback, and a real
incoming call and SMS alert. One normal reboot confirmed automatic orientation
startup and IMS registration.

[Scope by component](docs/r81-progress.md) · [Later implementation sources](runtime/reference-r81/README.md)

The public staging path remains the earlier reconstruction baseline. The
later sources and test summary are separate. The display experiments below
describe their historical baselines.

## Incoming calls and notifications

r37 adds these features to the landscape TTY:

- Audible ringing, automatic display wake and caller ID; missing or unsafe numbers display as `Unknown/withheld`, and the current-call row clears when the call ends.
- Configurable ringtone volume from 0 to 100%, defaulting to 60%, shown as `RING 60%`; zero mutes ringing while display wake/caller ID remain available.
- Persistent local call history distinguishing answered, missed, rejected and unknown outcomes when evidence is incomplete.
- A persistent `MISSED n   SMS n` row that remains until the corresponding marks are explicitly handled, independently of the current-call row's expiry.

```sh
sudo v30-phone ring-volume
sudo v30-phone ring-volume 100
sudo v30-phone history --missed
sudo v30-phone history --missed --mark-read
sudo v30-sms list --unread
sudo v30-sms read ID
```

Listing calls alone leaves notification marks intact. `--mark-read` clears only the displayed records' marks and retains history. Reading an SMS clears its local unread mark without replying. The percentage controls the next call's bounded ringtone amplitude, not in-call gain or measured loudness. Install the alert modules, media wrapper, status bar, commands and configuration together; see [incoming alerts, volume, history and notifications](docs/incoming-alerts.md). The default profile retains login authentication and Bluetooth off, with no automatic answer or dial.

## Volume and cellular status bar (r38)

- **`RING` ringtone level:** saved at 100% on the inspected device for the next incoming call; the shared configuration example still defaults to 60%. This scales the bounded ringtone waveform without changing in-call gain.
- **`VOL` ordinary speaker level:** reads the ALSA playback control; the inspected value of 8/15 displays as 53%, not measured sound pressure.
- **`CELL` current operator:** uses the registered network name, falling back to its network code when empty; `UNICOM` display was checked on the device.
- **`NET` current radio technology:** uses the modem's current report, observed as `4G LTE`. The parser recognizes 2G/3G/4G/5G reports, but V30 hardware supports up to 4G and has no 5G capability.
- **`SIG` signal status:** four bars and quality percentage; old readings retain their last bars with `STALE`, missing readings show `???? --`, and searching/no-service states are explicit.

Landscape TTY, normal login authentication, Bluetooth-off and persistent missed-call/unread-SMS counters remain, using at most five status rows. Device checks covered the 120-column framebuffer, service health and protected files; six new tests bring the Linux-root suite to 63 cases. There was no new ringtone listening at 100%, voice/SMS or reboot qualification. See [console status](docs/console-status.md) and the [r38 checkpoint](provenance/r38-validation.json) for implementation, input capabilities and validation limits.

## Compact status and a manual graphical session (r39)

The normal TTY bar uses two rows while retaining the existing metrics; an incoming call adds a temporary caller row. Fixed Chinese labels cover Unicom/4G, charging/not charging, speaker/ringtone and missed-call/SMS counts; Wi-Fi and Bluetooth show explicit ON/OFF states. Battery and volume values omit percent signs. Signal stairs retain quality/freshness information. Native 24x48 glyph cells improve detail; these fixed console labels are not a general CJK font or input method.

The current experimental session uses Weston/Pixman with an ordinary-memory shadow buffer, software Xwayland, a GTK3 launcher, Openbox, XTerm and Onboard/UIM Pinyin. Enter with `sudo v30-gui start`; leave with Return to TTY or `sudo v30-gui stop`. Authenticated landscape TTY and Bluetooth-off remain the boot default; staging requires `--desktop` and never enables a display manager. Native portrait Xorg touch and Chinese input passed operator checks, but rapid-input lag and strips remained; the coalesced refresh callback was rejected for horizontal strips and withdrawn. Native Phoc/Pixman painted only about three frames per second and was also stopped. The current Weston path reuses the qualified input components: an automated redraw probe had a median paint interval around 33 ms, and isolated Chinese readback plus one stop/cleanup cycle passed. Operator testing subsequently rejected this renderer too: brief horizontal strips and delayed text/key feedback remain. It is retained for diagnosis, not qualified as a stable desktop. An isolated r40 display-diagnostic kernel completed two separately authorized RAM boots: all 138 flips sampled during the first were notified about 10 ms before transfer completion, while median software paint spacing remained about 33.55 ms. The operator was away during the first window. A second separately authorized RAM trial confirmed that horizontal strips and input latency remain; the r40 candidate failed physical quality acceptance. The unchanged r35 default system, IMS and server services were restored after both trials. A subsequent direct Xorg/KMS alternative also failed operator acceptance. After compilation and image audits, the r42 continuous-clock candidate completed one separately authorized RAM test but produced a black screen; it was rejected and the unchanged r35 default/services restored. A lightweight GTK3 keyboard replacing Onboard substantially improved clicks according to the operator, but strips became more frequent; full-window redraw did not fix them. Official libdrm `modetest` then reproduced horizontal strips while flipping two prefilled buffers without GTK, Xorg, a keyboard or cursor, before returning cleanly to TTY. Investigation now focuses on the common DRM/DPU/DSI/DSC/panel path. A stock SCR1 versus current pre-SCR parameter discrepancy passed source-calculation checks, but one separately authorized r46 RAM pattern test retained the same strips. The candidate failed, its GUI branch was skipped, and the unchanged default system plus cellular/IMS/server services were restored; see the [display investigation](docs/display-investigation.md). See the [r41/r42 checkpoint](provenance/r41-r42-display-validation.json). The internal GUI profile is portrait and the default TTY remains landscape. See [manual graphical session](docs/manual-desktop.md).

2026-11-01: The operator considers transient strips a minor experience issue that does not prevent use. Active investigation is deferred and the issue remains a known limitation. The GUI is optional, not a core dependency for the portable-server/TTY workflow; authenticated landscape TTY and Bluetooth-off remain the default. This is not a claim that the strips are fixed.

Native USB-C output remains the priority before Phosh/Plasma Mobile and resource comparisons. r48 passed PD discovery; r49 was rejected for DT-mode errors and unsafe live DRM unbinding, with the default restored. One corrective r50 RAM trial produced the first wired picture: AOC DP entry, valid EDID and one stable 20-second 1080p60 static pattern, with normal phone TTY confirmed by the operator. An ordinary reboot restored r35, IMS, all 11 paused services, archives and protected hashes; authorization is closed. This remains a bounded static-output pass. Its startup module deferral and warnings are preserved; r51's later automatic-loading result is recorded below. Default-system external output, on-demand desktop integration, repeated hotplug, 4K and new-kernel voice compatibility remain unqualified; see [external display progress](docs/external-display.md).

2026-11-02: r51's single USB2 RAM trial has ended and its authorization is closed. The integration image reuses r50's kernel/DTB/modules. All five providers loaded automatically with zero manual modprobes; landscape TTY, Bluetooth-off and no GUI autostart passed. The first GUI request was falsely rejected by a stale sysfs mode cache. A trusted read-only DRM probe confirmed a valid 256-byte EDID and 1080p60; the two premature precheck lines were removed, preserving the old source and once marker. The only actual external GUI then had Weston/Xwayland/GTK processes and DP1080p60/DSI-off state, but the operator saw a white phone screen, blue monitor and no cursor. Physical acceptance failed; the other two windows were skipped. Software tty1 after cleanup did not establish physical recovery. A subsequent ordinary reboot restored r35/r30, with operator-confirmed landscape TTY, registered IMS, all 11 services, preserved archives and protected hashes. Production r30 telephony guards remain unchanged, and default external output is not integrated.

The complete r51 timeline already contains a DPU CTL flush timeout before GUI startup, so disabling DSI is not a proven cause. A later, separately authorized r52 RAM comparison retained DSI `current` and targeted software Xwayland at DP-1. Its bounded legacy `modetest -v` gate completed at least 540 real pageflips; DP VSYNC counts advanced 994 to 1362 to 1637, with DSI retained and no new DPU errors in the gate. The operator confirmed normal TTY and the expected color-bar/plain-color alternation; this was not abnormal flicker. The first dual-output GUI window passed operator-confirmed physical picture, input, Chinese and Return to TTY, followed by successful helper/seatd, mixer, four-PCM and tty8 cleanup. A software PNG proves rendering only; physical interaction acceptance comes from the operator's feedback.

During the second active GUI, the operator unplugged the AOC and reconnected the Mac, saw the LG logo and reached a new r35/r30 boot. The host controller did not run its default-transition script. Detach-to-TTY acceptance failed and the reset cause is unknown. Mounted pstore was empty and the RAM boot had no logbook rows; these do not identify a panic, watchdog, power or driver cause. Default full health, IMS/all 11 services, original two-SMS/four-call content and SQLite checks, protected hashes and physical landscape TTY passed; authorization is closed. Read-only quick_check also passed the live shijing and logbook databases, including WAL; a full application-content comparison was not performed. The public runtime is still the rejected r51 single-output prototype; private r52/r53/r54 profiles and harnesses have not been merged into it, so installing this repository does not reproduce those results. r52 is not promoted; see the [bounded r52 record](provenance/r52-dual-output-validation.json).

A separately authorized r53 RAM comparison then used legacy plain-buffer pageflips with no GUI. The detach gate required at least 240 real completions, advancing DP IRQ counts, retained DSI and no new display errors; the complete stream contained 61 batches, at least 3,660 completions. The operator confirmed a stable gray AOC image and normal TTY after removing AOC, then a reset after inserting the Mac. The host did not request that reboot. A GUI is therefore not necessary to reproduce the reset; its cause remains unknown. Independent Wi-Fi capture preserved 5,352 consecutive kernel records with no sequence gaps or overruns. It shows normal PHY shutdown followed by erroneous re-enabling of an old cached 1280x1024 mode, software-disabled AUX returning `-6`, link startup returning `-104`, then DPU timeouts. This identifies a concrete display-path problem, not a proven reset cause.

After r53, unchanged r35/r30 full health, IMS/all 11 services, original two-SMS/four-call content/SQLite, application database structure including WAL, and protected hashes passed. Forty phone evidence files were archived and hash-verified; authorization is closed, no SQLite was exported and full application content was not compared. See the [bounded r53 record](provenance/r53-legacy-detach-validation.json).

A later, separately authorized r54 RAM trial tested the six-line change in one fbdev helper: process pending hotplug before restoring cached modes. Its single legacy window completed at least 2,640 real pageflips; removing AOC, waiting three seconds and connecting the Mac retained the same RAM boot with no new display errors. The first dual-output GUI passed physical picture/input/Chinese, manual Return to TTY, exit0 and full cleanup. Wide terminal character spacing remains for r55 validation. The phone's compositor background during external GUI is a profile choice, not proof of internal scanout quality.

The second r54 GUI reset within three seconds of removing AOC, before the Mac was connected. Operator feedback and independent USB/Wi-Fi checks confirmed return to the default; automatic detach-to-TTY still failed. All 20,834 received kmsg records are consecutive. Their tail shows DP shutdown followed by new atomic-check resource reservation, without completed hardware re-enable, link training or panic; the caller and reset cause remain unknown. The six-line change passed the legacy stale-cache comparison, not GUI hotplug, and is not promoted. Default r35/r30 full health, IMS/all 11 services, original SMS2/calls4 content/SQLite, read-only application structure checks including WAL, and source/protected/runlevel/boot/recovery hashes passed; drm.debug is 0. Forty-nine phone evidence files were downloaded and hash-verified; authorization is closed, with no calls, sent SMS or partition writes. r56 caller-kprobe/Weston live-stream feasibility work would reuse the r54 image; it remains offline with no new RAM/GUI authorization. Authenticated landscape TTY, Bluetooth-off and no GUI autostart remain the default; Phosh/Plasma follows. See [external display progress](docs/external-display.md), [manual desktop](docs/manual-desktop.md) and the [bounded r54 record](provenance/r54-fbdev-hotplug-validation.json).

## Validation summary

Historical observations summarized as of 2026-10-31 (Asia/Shanghai), including earlier charge-control checks:

| Component | Historical device evidence | Host-only checks and remaining gaps |
|---|---|---|
| TTY interface | Landscape text console, larger glyphs, tmux status bar and normal login authentication | Published font-path/staging changes are host-only; long-term interaction and other variants remain unqualified |
| Wi-Fi and cellular data | Startup integration and DNS/HTTPS checks bound to the cellular interface | Long-term connectivity and other carriers remain unqualified |
| IMS voice | One earlier outgoing call; incoming calls of about 60 seconds in RAM and after normal default boot, with human confirmation of clear two-way speech; mixer/PCM cleanup checked | Published-source redeployment, long calls, hold/transfer, full media renegotiation and emergency calling remain unqualified |
| Incoming alerts | r37 ringing, wake/caller display and cancellation cleanup confirmed by the operator; a later call of about 60.37 seconds had clear two-way speech; persistent missed-call/SMS counters checked in the device framebuffer | [Volume, history and notifications](docs/incoming-alerts.md) separate revisions: later ADC-gain preservation has a local playback cleanup check; nonzero SMS/read-clear uses isolated data, with no further speech or reboot qualification |
| Volume and cellular status | r38 device framebuffer shows separate RING/VOL, operator, 4G LTE, four signal bars and retained notification counts; services and protected files checked | Listening at 100%, normal reboot and the full roaming/network-loss matrix remain unqualified; unknown/stale and width behavior have isolated tests |
| SMS | One short Chinese message sent and confirmed by the recipient, one received, and archive persistence without duplicate submission after one normal reboot | Real multipart SMS, long-term storage and disk-full recovery remain unqualified |
| Charge limiting | Earlier hardware checks exercised charge inhibition while retaining USB input power | The 75/80% hysteresis and temperature/sensor decisions were simulated in logic tests; actual temperature-fault handling and a complete physical charge cycle were not validated |
| Bluetooth policy | Bluetooth remained off in the tested local profile | This is an opt-in policy; the newly packaged final-off service has host checks only |

The charge-limit policy retains existing hardware safeguards; this project does not certify battery safety or service life. See [validation and recovery](docs/validation.md) for the evidence boundaries.

## Version tracks

- **Historical r35/r36 reconstruction inputs:** `baseline/kernel/`, `runtime/` and `patches/imsd/`, with pins in [sources.lock.json](sources.lock.json). The old kernel base is `1b42626…`, with local release `7.2.0-rc2-v30-r30`, microphone MCLK routes and the r35/r36 userspace. Current published adaptations do not inherit the historical device pass.
- **Newer upstream candidates:** `patches/current-kernel/`, corresponding to [kernel PR #12](https://github.com/ShapeShifter499/linux-lg-v30-joan/pull/12), based on `dc9c669…`. Four affected objects compiled, but no complete kernel image was built or booted. [Harness PR #11](https://github.com/ShapeShifter499/lg-v30-port/pull/11) publishes SMS tooling and the version-gated voice reference. Both PRs are Ready for review as of 2026-10-31; neither has been merged.
- **Selected r37 userspace additions:** incoming alerts, configurable ringtone volume, call history and persistent notification counters in `runtime/`. Their [device and host evidence](docs/incoming-alerts.md) retains the old-kernel gates and does not establish a fresh image or reboot pass.

- **r38 status-bar extension:** `runtime/voice/console_status.py` and console metrics show separate levels, the current operator, radio technology and signal; staging includes the new module. The [checkpoint](provenance/r38-validation.json) pins installed source hashes without inheriting historical voice or reboot qualification.

The historical snapshot retains diagnostic parameters and compatibility interfaces needed to explain that older stack. Keep it separate from the cleaned upstream series. The kernel and hardware gates in `runtime/voice` remain in place.

## Getting started

1. Read the [architecture and component map](docs/architecture.md).
2. Follow the [build and installation guide](docs/build-and-install.md), supplying your own firmware and device configuration.
3. Use the [validation and recovery checklist](docs/validation.md) for any new deployment. Calls and SMS require explicit operator actions.
4. Read the [upstream status](docs/upstream.md) to distinguish existing fixes, our changes and patches not yet submitted to their own upstream.

This repository contains source, configuration, build helpers and reconstruction instructions. Firmware, a known-good base boot/initramfs, credentials and filesystem UUIDs are operator-supplied inputs. No whole-device image, private key, raw SMS archive, SIM state, private backup or actual test destination is included.

## Host checks

Use Python 3.12+. The complete Linux isolation test also needs PyGObject/Gio, D-Bus and util-linux:

```sh
python3 scripts/check.py
# Linux root: synthetic ModemManager on a private bus and network namespace.
unshare --net -- dbus-run-session -- sh -c \
  'export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; exec python3 "$1"' \
  qa runtime/sms/bench_private_bus.py
```

English prose and CLI messages do not remove Unicode support: synthetic CJK/UCS2 payloads remain in the tests as escaped literals.

## Licensing and contributions

Original userspace code and documentation use GPL-3.0-only. Kernel patches retain the licenses of the files they modify, including GPL-2.0. Existing copyright notices and patch authorship are preserved; see [PROVENANCE.md](PROVENANCE.md).

Contributions are welcome under the [contribution guidelines](CONTRIBUTING.md). State exact versions and observed scope for every hardware result.

Assisted-by: Codex:OpenAI/GPT-6
