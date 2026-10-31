# Open work

Roadmap updated 2026-10-31. Every unchecked item is open work, including implemented paths that still need qualification. This is a planning document, not a claim that a defect has been reproduced or that a feature has passed. Completed integration work and historical evidence are recorded in the [contribution map](docs/contributions.md) and [validation record](docs/validation.md).

The target remains an experimental portable Linux server on the LG V30 US998, with a landscape TTY, normal login authentication and Bluetooth off. A desktop environment is not required. P0 establishes a dependable server baseline; P1 adds telephony usability and broader validation; P2 is optional. Priorities are not release dates.

r37's core incoming alerts, ringtone-volume display/control, private call history and persistent missed-call/unread-SMS counters are implemented. r38 adds separate speaker/ringtone levels, registered operator, current radio technology and signal status; its device preference is saved at 100% while the shared ringtone example stays at 60%. Checked items below refer to that bounded implementation and its recorded evidence, not completion of the full device matrix or a clean-image/reboot qualification.

## P0 - Server reliability and recovery

- [ ] **Qualify the final baseline for 24 hours, then 72 hours under a representative server workload.**
  Record the exact software/configuration versions and sample services, memory, temperature, storage, logs and connectivity. Check DNS, TCP, TLS and HTTPS separately. Acceptance: no unexplained reboot, filesystem error or service death; no unexplained sampling gap longer than 180 seconds in the initial 24-hour run. Record failures and recovery attempts explicitly. Earlier short calls or an older kernel's uptime do not satisfy this item.

- [ ] **Test network loss and recovery.**
  Exercise Wi-Fi reconnect, cellular reattachment, Wi-Fi/cellular route and DNS changes, and IMS re-registration with carrier backoff. Include ModemManager owner replacement and a long idle interval before an incoming call. Acceptance: the intended data route recovers, IMS re-registers without retry storms, no stale bearer/rule leaks remain, and an authorized call still has clear two-way speech.

- [ ] **Add consistent backups and perform a restore drill.**
  Cover SMS, service configuration and any separately deployed server application's data. Use SQLite's backup API or another documented consistent snapshot method; copying only a live main database can omit WAL data. Acceptance: restore into an isolated environment, compare message counts/content and pending-send records, and confirm restore never triggers an automatic send. Define off-device storage, access protection and retention.

- [ ] **Bound storage use and handle full or failing storage.**
  Define log rotation, archive retention/export and free-space reporting. Test disk-full/failed-write behavior on an isolated filesystem. Acceptance: errors remain visible, existing messages survive, uncertain sends are not retried automatically, and service recovery does not corrupt the archive. Review SD-card write load and an actionable filesystem-recovery procedure.

- [ ] **Qualify shutdown, cold boot and power-source transitions.**
  Verify service ordering and data integrity after controlled shutdown/cold boot, USB removal/reconnection and ordinary low-battery handling. Document whether the device boots automatically when power returns rather than assuming it does. Acceptance: expected services recover, stored messages remain intact and recovery is reproducible. Coordinate physical operations with the owner; do not deliberately exhaust the battery or modify recovery for this test.

- [ ] **Complete physical charge-policy qualification.**
  The existing hardware evidence covers charge inhibition with retained USB power; 75/80% hysteresis and abnormal-temperature decisions have logic tests only. Observe a complete normal charge-limit cycle and supported power sources. Acceptance: the real device resumes/inhibits as intended, USB-powered operation continues and sensor/health failures produce the documented conservative decision. Do not deliberately overheat the device or bypass hardware safeguards.

- [ ] **Measure idle and workload power/temperature.**
  Compare display on/off while networking and server services remain active, using wall/battery measurements where available. Acceptance: publish workload, duration and measurement method, identify excess wakeups and bound sustained workload temperature. Display blanking must not be described as whole-system suspend.

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

- [x] **Implement separate speaker/ringtone levels, current operator/radio technology and bounded signal bars.**
  The r38 reader uses read-only ModemManager properties and ALSA control readback; unknown and stale states are explicit. The 120-column device framebuffer and retained notification counts were inspected; six new cases bring the Linux-root suite to 63 tests. See [console status](docs/console-status.md) for evidence and limitations.

- [ ] **Listen to and qualify the 100% ringtone preference.**
  The application setting is saved, with the existing waveform peak limit and hardware playback gain retained. Arrange a fresh authorized call to confirm perceived level, stop/handoff behavior and clear two-way speech. Changing the stored percentage or reading it on screen is not a listening test.

- [ ] **Qualify the status bar after reboot and during network transitions.**
  Check no service, roaming, modem-owner replacement, stale quality and notifications during an authorized call. Signal percentages are modem estimates, not throughput or calibrated antenna measurements.

- [ ] **Evaluate an optional touch desktop and Chinese input session.**
  The installed kernel exposes DRM/GPU and stmfts touch; the TTY image has graphics libraries but no configured desktop, on-screen keyboard or Chinese IME. Evaluate a compositor/mobile shell, touch rotation, virtual keyboard, CJK font coverage and an integrated input method together. Keep authenticated landscape TTY and Bluetooth-off as the default, with a reliable return path. Do not mark package installation as successful interaction testing.

- [ ] **Assess Android component reuse only for a concrete missing feature.**
  Firmware and driver references can help mainline work; Android HAL binaries depend on the Android userspace/BSP. A libhybris adaptation or Waydroid session is separate compatibility work, not an APK copied into the current TTY. Record kernel/runtime requirements and actual device evidence before claiming support.

## P2 - Optional extensions

- [ ] **Evaluate whole-system suspend only as a separate operating mode.**
  An always-on server needs reachable networking; suspend has different wakeup and incoming-call requirements. Acceptance: document the intended mode, actual wake sources, connectivity restoration and measured savings before enabling it by default.

- [ ] **Evaluate optional hardware/UI features only when needed.**
  Camera, desktop graphics and Bluetooth audio are outside the current TTY-server target. GPU/runtime power management may still matter to idle power. Any extension needs its own compatibility and resource-usage evidence and must preserve the default landscape TTY and Bluetooth-off profile.

## Execution rules

Planning an item does not authorize a live call, SMS, power cycle or flash. Arrange each hardware test and its recovery conditions with the operator; previous one-time call/SMS allowances are not reusable. Keep personal numbers, raw protocol/message logs, credentials and device identifiers out of public reports. Mark an item complete only with linked implementation and scoped evidence, stating what was tested on the host versus the device.
