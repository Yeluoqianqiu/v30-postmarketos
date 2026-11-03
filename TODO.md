# Open work

See the [r81 checkpoint](docs/r81-progress.md) for the latest default and test scope. Older results below describe their original baselines.


Roadmap updated 2026-11-02. Every unchecked item is open work, including implemented paths that still need qualification. This is a planning document, not a claim that a defect has been reproduced or that a feature has passed. Completed integration work and historical evidence are recorded in the [contribution map](docs/contributions.md) and [validation record](docs/validation.md).

The target remains an experimental portable Linux server on the LG V30 US998, with a landscape TTY, normal login authentication and Bluetooth off. A desktop environment is not required. P0 establishes a dependable server baseline; P1 adds telephony usability and broader validation; P2 is optional. Priorities are not release dates.

r37's core incoming alerts, ringtone-volume display/control, private call history and persistent missed-call/unread-SMS counters are implemented. r38 adds separate speaker/ringtone levels, registered operator, current radio technology and signal status; its device preference is saved at 100% while the shared ringtone example stays at 60%. Checked items below refer to that bounded implementation and its recorded evidence, not completion of the full device matrix or a clean-image/reboot qualification.

## Current priority - Native USB-C external display

- [ ] **Bring up USB-C output before testing full mobile shells.**
  The operator requests USB-C direct output to an AOC U27N3G6R4B with a Mac-verified cable. r48 passed PD discovery. r49 failed its DT SVID/child-name check; unsafe live DRM unbinding caused an Oops and operator key recovery. The corrected r50 passed one authorized RAM trial: active DP mode, valid 256-byte EDID, and one 20-second 1080p60 static pattern confirmed complete/stable with normal phone TTY. Ordinary PID1 reboot restored r35, IMS/all 11 services, unchanged partition/file hashes and preserved SMS/call archives; the r50 authorization is closed. Startup DP deferral, one Type-C probe -71 and DSI wait-idle -11 remain recorded. The default has no external output yet; 4K is unqualified. Never live-unbind active DRM. Each RAM experiment needs fresh applicable authorization. See [external display](docs/external-display.md).

- [x] **Qualify bounded automatic provider loading and the TTY baseline in r51.**
  One authorized RAM boot reused r50's kernel/DTB/modules with the r51 initramfs hook. All five providers loaded automatically, manual modprobe count was zero, landscape TTY/Bluetooth-off passed and no GUI autostarted. This closes only that bounded startup check. It does not qualify an external desktop or new-kernel telephony.

- [ ] **Complete external GUI acceptance after the r51 rejection.**
  A stale sysfs mode cache falsely rejected the first request; a read-only DRM probe found valid EDID256/1080p60, and the two premature precheck lines were removed while preserving the old source/once. The only actual GUI had Weston/Xwayland/GTK processes and DP1080p60 with DSI disabled, but the operator reported a white phone screen, blue monitor and no cursor. Physical acceptance failed; the other two windows were skipped. A G102 pointer and its keyboard interface enumerated, but a separate keyboard was not confirmed. Persistent DPU CTL flush/vblank/ppdone/kickoff timeouts mean software tty1 did not prove physical recovery. Ordinary PID1 reboot subsequently restored r35/r30, operator-confirmed landscape TTY, IMS/all 11 services, archives and partition/protected hashes; the r51 authorization is closed.
  The full timeline contains DP CTL flush timeout before GUI startup, so DSI-off is not a proven cause. The later private r52 comparison retained current DSI scanout and targeted Xwayland at DP-1; its bounded passes and detach failure are recorded below. Keep production r30 telephony guards intact and the default external output unintegrated. The public runtime remains the rejected r51 single-output prototype; tested private r52 source/harness is not installed by staging it. See [external display](docs/external-display.md) and [manual desktop](docs/manual-desktop.md).

- [x] **Record r52's bounded legacy flip gate and first interactive dual-output cycle.**
  One separately authorized RAM boot reused the r51 image/r50 kernel/modules. A 10-second legacy `modetest -v` gate completed nine batches of 60 pageflips, at least 540 real completion events; DP VSYNC counts advanced 994 to 1362 to 1637, DSI mapping remained and no new DPU errors were recorded in the gate. The operator confirmed normal phone TTY and expected color-bar/plain-color alternation, not abnormal flicker. The first dual-output GUI passed operator-confirmed physical picture, input, Chinese and ReturnTTY; helper/seatd cleanup, mixers, four closed PCMs and tty8 restoration passed. Software PNG is rendering evidence only. This closes one bounded interaction cycle, not full external-display acceptance.

- [ ] **Diagnose the r52/r53 transition resets and r54 GUI unplug reset before default promotion.**
  The second GUI was active when AOC was unplugged and the Mac connected; the operator saw the LG logo and a new r35/r30 boot followed without the host controller running default-transition. Detach-to-TTY failed; root cause remains unknown. Mounted pstore was empty and the RAM boot had zero logbook rows, leaving no crash record from those channels. Preserve the evidence and do not relabel this as clean GUI return. Default full health, physical landscape TTY, IMS/all 11 services, original two-SMS/four-call content/SQLite and protected/runlevel/partition hashes passed; authorization is closed. Read-only quick_check also passed the live shijing and logbook databases, including WAL; full application-content comparison was not performed. Keep r35 unchanged and retain all production telephony guards; qualify detach/reconnect, repeated cycles, sustained output, both orientations and new-kernel IMS/voice/SMS separately. No old RAM/window authorization is reusable. See the [bounded r52 record](provenance/r52-dual-output-validation.json).

- [x] **Record the bounded r53 no-GUI legacy detach comparison and live evidence.**
  One separately authorized RAM run reached a gate of at least 240 real pageflip completions with DP IRQ progress, DSI retained and no new display errors. The full stream contains 61 batches, at least 3,660 completions, and 5,352 kernel records without sequence gaps or overruns. The operator saw stable gray output, normal TTY after AOC removal, then a reset after Mac insertion; the host did not request reboot. GUI is not required to reproduce the reset. Normal PHY shutdown was followed by an erroneous old cached 1280x1024 re-enable, software-disabled AUX `-6`, link `-104` and DPU timeouts. This concrete display-path failure is not a proven reset cause. Default full health, business-database structure including WAL, original SMS2/calls4 content, protected hashes and all 11 services passed; 40 evidence files were archived/hash-verified and authorization closed, without SQLite export or full application-content comparison. See the [bounded r53 record](provenance/r53-legacy-detach-validation.json).

- [x] **Record r54's bounded legacy hotplug-order pass and first manual GUI return.**
  One separately authorized RAM boot tested the six-line, single-file fbdev helper change: handle pending hotplug before cached-mode restore, preserving force and no-pending paths. The single legacy window completed at least 2,640 real pageflips. Removing AOC, waiting three seconds and connecting the Mac kept the same RAM boot with no new display errors. The first GUI passed physical picture/input/Chinese, manual ReturnTTY, exit0 and full cleanup. The phone's compositor background is profile design, not a scanout-quality proof. The legacy stale-cache comparison passed; GUI hotplug and reset resolution did not. See the [bounded r54 record](provenance/r54-fbdev-hotplug-validation.json).

- [ ] **Resolve r54 GUI unplug failure with a bounded caller/exit-path diagnostic.**
  In GUI2, removing AOC alone caused reset within the three-second observation period, before Mac attachment. The operator and independent USB/Wi-Fi checks confirmed return to the default; the host did not request reboot. The 20,834 consecutive kmsg records stop at new atomic-check resource reservation after DP shutdown, without completed hardware re-enable/link training or panic. Caller and reset cause are unknown; full Weston/controller logs were lost with volatile runtime storage. Default full health, IMS/all 11 services, physical authenticated landscape TTY, SMS2/calls4 content/SQLite, live business-database structure including WAL, protected source/runlevel/partition hashes and drm.debug=0 passed. Forty-nine evidence files were downloaded/hash-verified and authorization closed. The r56 diagnostic harness now has offline source/interface reviews and isolated trace/staging tests for caller kprobes and a live Weston stream using the existing r54 image. Real probe registration, stack readback and GUI detach remain untested, and fresh RAM/GUI authorization is pending. Do not promote a default or relax production r30 guards. The public runtime remains the rejected r51 prototype; private r52/r53/r54 profiles and harnesses are not merged.

- [ ] **Validate the r55 terminal character-spacing correction.**
  r54's otherwise accepted first GUI had overly wide terminal character spacing. A separate ARM64 Xvfb test with the phone's exact font files and xterm 412 reproduced a 27-pixel generic/CJK-mono cell; explicit Adwaita Mono plus the SC-wide face produced a 16-pixel cell. ASCII, CJK, mixed text, bold and box-drawing cursor checks passed, and software PNGs were inspected. This is a headless result; the candidate is not yet deployed or physically qualified on the phone. This does not reopen deferred internal-panel strip investigation or authorize a GUI/RAM experiment.

- [ ] **After external-output work, test Phosh and Plasma Mobile and measure their overhead.**
  Compare idle TTY, a representative TUI and each full mobile shell on the same phone, with consistent sampling and background services. Record system available memory plus process PSS/RSS, CPU and temperature; distinguish idle from active input/refresh and do not sum shared RSS as unique memory. No mobile-shell resource increments have been measured. Neither Phosh nor Plasma Mobile has been installed or launched in the r51/r52/r53/r54 scopes; resolve the Phosh Polkit dependency conflict without replacing production components first. The display-strip issue remains deferred and is not reopened by these shell tests.

## P0 - Server reliability and recovery

- [ ] **Qualify the final baseline for 24 hours, then 72 hours under a representative server workload.**
  Record the exact software/configuration versions and sample services, memory, temperature, storage, logs and connectivity. Check DNS, TCP, TLS and HTTPS separately. Acceptance: no unexplained reboot, filesystem error or service death; no unexplained sampling gap longer than 180 seconds in the initial 24-hour run. Record failures and recovery attempts explicitly. Earlier short calls or an older kernel's uptime do not satisfy this item. An independent bounded sampler and segment evaluator are being prepared; RAM boots, collector/service interruptions and missing evidence must split qualification rather than extend a healthy interval.

- [ ] **Test network loss and recovery.**
  Exercise Wi-Fi reconnect, cellular reattachment, Wi-Fi/cellular route and DNS changes, and IMS re-registration with carrier backoff. Include ModemManager owner replacement and a long idle interval before an incoming call. Acceptance: the intended data route recovers, IMS re-registers without retry storms, no stale bearer/rule leaks remain, and an authorized call still has clear two-way speech. Start with read-only reconnect-policy/route/DNS inventory and isolated failure fixtures; schedule real outages separately from external-display Wi-Fi control.

- [ ] **Add consistent backups and perform a restore drill.**
  Cover SMS, service configuration and any separately deployed server application's data. Use SQLite's backup API or another documented consistent snapshot method; copying only a live main database can omit WAL data. Acceptance: restore into an isolated environment, compare message counts/content and pending-send records, and confirm restore never triggers an automatic send. Define off-device storage, access protection and retention. The operator chose private Mac-side automatic pulls while the Mac is online. Prepare a consistent snapshot, verified private transfer and independent restore directory; no production overwrite or automatic message submission. Owner-specific private tooling has since completed one real four-database snapshot, per-file hash verification and an independent new-directory restore. A Mac LaunchAgent is registered for hourly checks with a 24-hour minimum snapshot age; its first RunAtLoad skipped because that snapshot was recent and exited successfully. This tooling is not yet part of the published portable runtime. The first due scheduled network pull, cross-day behavior and broader recovery/retention qualification remain open.

- [ ] **Bound storage use and handle full or failing storage.**
  Define log rotation, archive retention/export and free-space reporting. Test disk-full/failed-write behavior on an isolated filesystem. Acceptance: errors remain visible, existing messages survive, uncertain sends are not retried automatically, and service recovery does not corrupt the archive. Review SD-card write load and an actionable filesystem-recovery procedure.

- [ ] **Qualify shutdown, cold boot and power-source transitions.**
  Verify service ordering and data integrity after controlled shutdown/cold boot, USB removal/reconnection and ordinary low-battery handling. Document whether the device boots automatically when power returns rather than assuming it does. Acceptance: expected services recover, stored messages remain intact and recovery is reproducible. Coordinate physical operations with the owner; do not deliberately exhaust the battery or modify recovery for this test.

- [ ] **Complete physical charge-policy qualification.**
  The existing hardware evidence covers charge inhibition with retained USB power; 75/80% hysteresis and abnormal-temperature decisions have logic tests only. Observe a complete normal charge-limit cycle and supported power sources. Acceptance: the real device resumes/inhibits as intended, USB-powered operation continues and sensor/health failures produce the documented conservative decision. Do not deliberately overheat the device or bypass hardware safeguards.

- [ ] **Measure idle and workload power/temperature.**
  Compare display on/off while networking and server services remain active, using wall/battery measurements where available. Acceptance: publish workload, duration and measurement method, identify excess wakeups and bound sustained workload temperature. Display blanking must not be described as whole-system suspend. Begin with bounded read-only observations; power-source changes and representative-load tests require a separate coordinated window. Preserve the current charge hysteresis and thermal safeguards.

- [ ] **Audit remote access, updates and rollback.**
  Review SSH authentication, listening ports, firewall ownership and any operator-configured public tunnel/authentication. Inventory package versions and document a recoverable update procedure. Acceptance: required exposure and credentials are documented privately, unnecessary access is disabled, and rollback is demonstrated without losing messages. This is an open audit, not an assertion of a known vulnerability; private application/tunnel configuration is outside this repository.

- [ ] **Recheck historical kernel warnings on the final baseline.**
  Classify SMMU, PMIC, touch and display warnings by reproduction and impact. Acceptance: each relevant warning has evidence, a scoped fix or a documented reason it is harmless; hiding logs does not resolve the item.

## P1 - Incoming calls and TTY usability

- [x] **Implement incoming caller display and wake on the landscape TTY.**
  The [incoming-alert implementation](docs/incoming-alerts.md) includes startup/owner reconciliation and sanitized labels. Operator feedback and device TTY checks covered wake/caller display and removal after cancellation/acceptance. Login and Bluetooth-off policy remain intact. Carrier-specific withheld-identity behavior is still unqualified.

- [x] **Implement an audible ringtone with configured volume and media handoff.**
  The operator confirmed ringing, cancellation and the adjusted level; an accepted call lasted about 60.37 seconds with clear two-way speech. The status bar shows RING volume. A later gain-preservation change passed playback-only cleanup checks for all ten controls, without capture. Exact evidence/revision boundaries are in the [feature document](docs/incoming-alerts.md).

- [ ] **Broaden incoming-alert device qualification.**
  Exercise local reject, timeout, observer/IMS/ModemManager failure, repeated calls, restart during a live call, carrier privacy behavior and ordinary reboot. Acceptance: stop/clear/recovery and media ownership are correct across the matrix. Host failure-path tests and a short accepted call do not complete this matrix.

- [x] **Add private call history and missed-call state with a TTY query.**
  SQLite records direction, sanitized identity, times and outcome. Real device rows include missed and answered calls; one earlier verified test was explicitly imported as test-report evidence. Incomplete terminal evidence becomes unknown. Host tests cover persistence, duplicates and owner-bound IDs. Device reboot, retention/export and full-storage recovery remain open.

- [ ] **Add call-history export, retention and a verified restore path.**
  Define an export format and explicit retention/deletion controls. Acceptance: consistent backup/restore preserves outcomes and unread marks; acknowledging displayed rows never acknowledges a concurrently arriving call; deletion is an explicit operation. Cover archive corruption, disk-full behavior and preservation on uninstall.

- [ ] **Qualify longer and repeated calls.**
  Cover longer duration, successive calls, remote/local hangup, cancellation and crash cleanup. Acceptance: human-confirmed two-way speech, preserved data/TTY behavior, bounded resource use and clean mixer/PCM teardown across the matrix. Keep hold, transfer, headset switching and full SDP media renegotiation explicitly unqualified until separately implemented and tested. Emergency calling is outside the present validation claim.

## P1 - SMS usability and storage

- [x] **Add persistent missed-call and unread-SMS counts to the TTY.**
  The notification row reads archive counts without message bodies or read-state changes, and remains until marks are explicitly handled. Device framebuffer checks show missed-call/SMS counts alongside RING volume and normal login. Isolated tests use the actual SMS store to verify nonzero counts persist until explicit read, with records retained. No fresh carrier SMS was sent for this addition; new-message notification/reboot qualification remains open.

- [ ] **Qualify notification updates with a fresh carrier SMS and ordinary reboot.**
  Arrange a separately authorized incoming message. Acceptance: the unread count appears without marking the message read, remains through observer/console restarts and a device reboot, then clears after explicit reading while the archived message remains. Verify missed-call marks follow the same persistence rule and normal display blanking is respected.

- [ ] **Qualify multipart and boundary-case messages.**
  Short Chinese SMS in each direction passed historically; real multipart and binary SMS have not been qualified. Test GSM7 extension characters, UCS2 boundaries, multiple equal-content messages and the supported segment limit with controlled recipients. Acceptance: exact content/order and no duplicate submission; unsupported encodings and non-BMP input produce a clear error rather than silent corruption.

- [ ] **Exercise modem/service restart and storage exhaustion.**
  Test reused modem object paths, D-Bus owner changes, startup inventories, interrupted sends and modem/SIM storage full conditions using synthetic peers first. Acceptance: complete incoming messages are archived once, distinct equal-content messages remain distinct, and ambiguous outgoing results stay pending/unknown without automatic resend. Define any future modem-message deletion as an explicit operator action after a durable archive.

- [ ] **Provide documented message export and archive maintenance.**
  Add a stable export format, backup/restore instructions and an explicit retention/deletion workflow. Acceptance: exported Unicode and metadata round-trip correctly, backup handles WAL consistently, file permissions remain private and uninstall does not silently delete the archive. The current archive is unencrypted SQLite at `/var/lib/v30-sms/messages.sqlite`; filesystem permissions are not encryption.

## P1 - Upstream and reproducibility

- [ ] **Follow up the two GitHub PRs and address review feedback.**
  Track [harness #11](https://github.com/ShapeShifter499/lg-v30-port/pull/11) and [kernel #12](https://github.com/ShapeShifter499/linux-lg-v30-joan/pull/12). Acceptance: review changes retain attribution, exact validation limits and a link to the final upstream outcome. Ready for review alone is not completion or acceptance.

- [ ] **Prepare the imsd changes for their own upstream.**
  Arrange the maintainer-required Forgejo account/signing setup, split logical interoperability changes, and build/test each commit against the intended upstream revision. Acceptance: submit a reviewable series with DCO/signing requirements satisfied by the human contributor, preserved upstream behavior outside opt-in paths, and scoped protocol evidence. The bundled patch is not an upstream submission.

- [ ] **Build and qualify the newer kernel track.**
  Four affected objects have compiled; a full image and device boot remain open. Build the complete kernel/modules/DT/initramfs combination, review audio/debug-ABI compatibility and preserve a verified known-good rollback. Acceptance: separately authorized RAM-only boot followed by data, audio, power and regression checks. Keep compatibility gates until actual support is established.

- [ ] **Repeat reconstruction from the published sources on a clean target.**
  Pin remaining package/dependency inputs, reconstruct from documented owner-supplied firmware/base boot inputs and record deviations. Acceptance: the published paths, staging, English CLI, Bluetooth-off service and complete boot/data/voice/SMS stack pass a fresh end-to-end deployment. Historical r35/r36 results do not qualify later publication changes.

## Console status and input follow-up

- [x] **Implement a compact two-row TTY layout with native glyphs and explicit labels.**
  Existing metrics and notification counts remain. Fixed Chinese labels and 24x48 drawings replace the coarse icons; Wi-Fi/Bluetooth use ON/OFF and battery/volume values omit percent signs. The framebuffer was inspected.

- [ ] **Low priority / deferred: resolve graphical-session strips and qualify repeated return cycles.**
  On 2026-11-01, the operator judged the transient strips a minor experience issue that does not prevent use. Graphical sessions are optional and are not a core dependency for the portable-server/TTY workflow. Active strip investigation is deferred; retain this open item and its evidence, and reconsider when requested or if its practical impact changes. This is acceptance of a known limitation, not a fix or a new display-quality pass. Do not schedule further display experiments automatically.

  Earlier GPU and software Phoc profiles failed quality checks. Native portrait Xorg with scoped touch access and native UIM passed operator Chinese input but retained latency and strips. The coalesced copy callback was rejected for horizontal strips and withdrawn. Native Phoc/Pixman painted about 3 fps and was stopped automatically. The current Weston/Pixman memory-shadow plus software rootful Xwayland profile painted 187 frames over 8.29 s (median 33.37 ms); isolated Chinese readback and one clean return cycle passed. Operator testing still found brief horizontal strips and delayed text/key feedback, so this profile also failed. An isolated r40 early-pageflip candidate passed full kernel/modules compilation and RAM-image integrity checks, then completed two separately authorized RAM boots. All 138 sampled flips preceded transfer completion by a median 9.95 ms, but software paint spacing remained about 33.55 ms. The operator was away during the first window. A second separately authorized RAM trial reproduced horizontal strips and persistent input latency; r40 failed physical acceptance too. Chinese input was not explicitly reported in that trial. Both runs returned to the unchanged r35 default and services; both one-shot authorizations are closed. A future RAM trial requires fresh on-site authorization; retain existing production r30 telephony guards until separately qualified. Compare captured software frames with physical panel artifacts to distinguish rendering/composition from scanout or panel transfer; do not infer the failing stage from flip timing alone. Diagnose the remaining strip mechanism; qualify rapid input, strip absence and repeated cleanup before calling it stable. Direct Xorg/KMS also reproduced the symptoms, without Weston/Xwayland or a refresh helper. The isolated r42 continuous-clock candidate passed build/image audits, then failed one separately authorized RAM test with a black screen despite unblanked/backlight/DRM-active readbacks. It was rejected and the unchanged default restored; authorization is closed. The lightweight GTK3 keyboard improved operator-perceived clicks but increased strips; full-window redraw also failed. Official libdrm `modetest` reproduced horizontal strips with two immutable prefilled buffers and no GTK/Xorg/OSK/cursor, narrowing investigation to the shared display-output path. Its roughly 59.63 Hz completion-event rate is not a physical correctness measurement. Compare the stock DSC1.1 SCR1 profile with the current pre-SCR selection: five RC ranges and stock first-line BPG differ; source calculations match after a panel-specific SCR1 adjustment. The minimal r46 candidate passed full build/module/image audits, then failed one separately authorized RAM bare-DRM test with unchanged strips; its GUI branch was skipped, the unchanged default/cellular/IMS/services were restored, and authorization closed. SCR1 matching alone is not a fix. The baseline already includes the upstream GPIO10/TE-source routing fix and preserves porches when calculating compressed link clocks; do not repeat changes to already-correct paths. If this deferred issue is reopened, isolate physical panel scan/transfer synchronization with a minimal reproducer and measured timing rather than another GUI replacement. Any further visible experiment needs a new concrete plan and fresh applicable authorization. Do not repeat the continuous-clock, raw PHY/MMIO or packetization changes already rejected in upstream records. Require physical absence of strips, rapid input and repeated cleanup before acceptance. No source-inspection hypothesis is a demonstrated fix. See the [research and evidence](docs/display-investigation.md). Preserve the failed evidence. See [manual desktop](docs/manual-desktop.md).


- [x] **Implement separate speaker/ringtone levels, current operator/radio technology and bounded signal bars.**
  The r38 reader uses read-only ModemManager properties and ALSA control readback; unknown and stale states are explicit. The 120-column device framebuffer and retained notification counts were inspected; six new cases bring the Linux-root suite to 63 tests. See [console status](docs/console-status.md) for evidence and limitations.

- [ ] **Listen to and qualify the 100% ringtone preference.**
  The application setting is saved, with the existing waveform peak limit and hardware playback gain retained. Arrange a fresh authorized call to confirm perceived level, stop/handoff behavior and clear two-way speech. Changing the stored percentage or reading it on screen is not a listening test.

- [ ] **Qualify the status bar after reboot and during network transitions.**
  Check no service, roaming, modem-owner replacement, stale quality and notifications during an authorized call. Signal percentages are modem estimates, not throughput or calibrated antenna measurements.

- [ ] **Evaluate an optional touch desktop and Chinese input session.**
  The installed kernel exposes DRM/GPU and stmfts touch; r39 adds an optional manual graphical session with Onboard/UIM Pinyin and CJK fonts. Broader interaction and application coverage remain open. Evaluate a compositor/mobile shell, touch rotation, virtual keyboard, CJK font coverage and an integrated input method together. Keep authenticated landscape TTY and Bluetooth-off as the default, with a reliable return path. Do not mark package installation as successful interaction testing.

- [ ] **Assess Android component reuse only for a concrete missing feature.**
  Firmware and driver references can help mainline work; Android HAL binaries depend on the Android userspace/BSP. A libhybris adaptation or Waydroid session is separate compatibility work, not an APK copied into the current TTY. Record kernel/runtime requirements and actual device evidence before claiming support.

## P2 - Optional extensions




- [ ] **Evaluate whole-system suspend only as a separate operating mode.**
  An always-on server needs reachable networking; suspend has different wakeup and incoming-call requirements. Acceptance: document the intended mode, actual wake sources, connectivity restoration and measured savings before enabling it by default.

- [ ] **Evaluate optional hardware/UI features only when needed.**
  Camera, desktop graphics and Bluetooth audio are outside the current TTY-server target. GPU/runtime power management may still matter to idle power. Any extension needs its own compatibility and resource-usage evidence and must preserve the default landscape TTY and Bluetooth-off profile.

## Execution rules

Planning an item does not authorize a live call, SMS, power cycle or flash. Arrange each hardware test and its recovery conditions with the operator; previous one-time call/SMS allowances are not reusable. Keep personal numbers, raw protocol/message logs, credentials and device identifiers out of public reports. Mark an item complete only with linked implementation and scoped evidence, stating what was tested on the host versus the device.
