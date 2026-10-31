# Open work

Roadmap updated 2026-10-31. Every unchecked item is open work, including implemented paths that still need qualification. This is a planning document, not a claim that a defect has been reproduced or that a feature has passed. Completed integration work and historical evidence are recorded in the [contribution map](docs/contributions.md) and [validation record](docs/validation.md).

The target remains an experimental portable Linux server on the LG V30 US998, with a landscape TTY, normal login authentication and Bluetooth off. A desktop environment is not required. P0 establishes a dependable server baseline; P1 adds telephony usability and broader validation; P2 is optional. Priorities are not release dates.

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

- [ ] **Display incoming caller ID automatically on the TTY.**
  imsd already exposes a parsed number in call information and `v30-phone calls` can inspect current calls; a persistent TTY notification listener is still needed. Use call lifecycle events and reconcile current calls after restart. Acceptance: show a sanitized number or a clear unknown/withheld label, handle SIP/TEL identities without claiming identity verification, preserve login/input usability, and define display-wake and locked-screen privacy policy. Keep Bluetooth off and require explicit acceptance of a call.

- [ ] **Play an audible incoming ringtone.**
  SIP `180 Ringing` is signaling; it does not establish that a local speaker ringtone exists. Add a bounded-volume ringtone worker that shares the call-audio ownership rules. Stop it and release playback PCM before call media acquires audio. Acceptance: repeated incoming calls ring; accept, reject, remote CANCEL, timeout and service failure all stop ringing, restore mixers and close PCM devices. No idle microphone capture or automatic answer/dial.

- [ ] **Persist call history and missed-call state.**
  Current calls are transient and removed on deletion. Add a private archive for direction, available caller identity, timestamps and outcome. Acceptance: reconcile duplicate events and daemon restarts without fabricating answered calls; define retention and export, and keep call history private.

- [ ] **Qualify longer and repeated calls.**
  Cover longer duration, successive calls, remote/local hangup, cancellation and crash cleanup. Acceptance: human-confirmed two-way speech, preserved data/TTY behavior, bounded resource use and clean mixer/PCM teardown across the matrix. Keep hold, transfer, headset switching and full SDP media renegotiation explicitly unqualified until separately implemented and tested. Emergency calling is outside the present validation claim.

## P1 - SMS usability and storage

- [ ] **Add an unobtrusive unread-SMS indicator or notification.**
  Reuse archive state rather than reading message bodies into status logs. Acceptance: unread counts survive restart, marking a message read changes only local read state, and outgoing submission is never presented as proof of recipient delivery. Define display privacy before exposing sender/content on a logged-out TTY.

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

## P2 - Optional extensions

- [ ] **Evaluate whole-system suspend only as a separate operating mode.**
  An always-on server needs reachable networking; suspend has different wakeup and incoming-call requirements. Acceptance: document the intended mode, actual wake sources, connectivity restoration and measured savings before enabling it by default.

- [ ] **Evaluate optional hardware/UI features only when needed.**
  Camera, desktop graphics and Bluetooth audio are outside the current TTY-server target. GPU/runtime power management may still matter to idle power. Any extension needs its own compatibility and resource-usage evidence and must preserve the default landscape TTY and Bluetooth-off profile.

## Execution rules

Planning an item does not authorize a live call, SMS, power cycle or flash. Arrange each hardware test and its recovery conditions with the operator; previous one-time call/SMS allowances are not reusable. Keep personal numbers, raw protocol/message logs, credentials and device identifiers out of public reports. Mark an item complete only with linked implementation and scoped evidence, stating what was tested on the host versus the device.
