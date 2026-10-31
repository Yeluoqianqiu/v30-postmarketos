# Validation boundaries and recovery

## Historical device observations

The contributor used one LG V30 US998 on China Unicom. The table combines earlier bring-up observations with local r35/r36 acceptance; the latter voice/SMS acceptance was recorded on 2026-10-31 (Asia/Shanghai). They do not qualify the latest kernel branch, other devices or every file in the subsequently published repository.

| Area | Observed scope |
|---|---|
| IMS registration | Successful registration/subscription and automatic recovery after normal boot |
| Calls | One earlier outgoing call of about 20 seconds; after the fix, incoming calls of about 60 seconds in RAM and after normal default boot, with operator confirmation of clear speech in both directions and landscape TTY |
| Audio cleanup | Ten mixer controls restored, four PCM devices closed and audio processes cleaned up after the accepted calls; failure cleanup and separate call lifetimes also have host tests |
| SMS send | One short Chinese UCS2 message, with recipient confirmation after ModemManager reported submission |
| SMS receive | One short Chinese message fully archived and read back through the TTY CLI |
| Normal reboot | SMS service resumed; incoming record/body retained without duplication, and the outgoing request was not resubmitted |
| System checks | Services resumed, cellular-bound DNS/HTTPS checks passed, landscape TTY and Bluetooth-off remained, and ext4 reported zero errors at the checks |
| Charge control | Earlier bring-up hardware checks exercised charge inhibition while retaining USB input power; this did not exercise a full physical 75/80% charging cycle or abnormal-temperature conditions |

Registration, a local active signal or a successful socket write is not proof of remote answer or two-way speech. `submitted` is not proof of delivery. The accepted voice/SMS claims had additional operator or recipient feedback. No voice recording is distributed. This repository publishes sanitized summaries; it does not claim private raw captures are publicly verifiable immutable evidence.

## Host-only validation

The initial publication, localization and review-status work did not operate the phone. The later selected r37 device work is recorded separately below; it does not turn host reconstruction checks into a full-device pass.

- SMS logic: 23 unit cases.
- Voice, alerts and history: 30 unit cases; Linux root covers private-path ownership validation. The root-specific case is skipped when run without root.
- Notification/archive integration: one isolated case uses the real SMS store and verifies counts persist until explicit read without deleting the message.
- Incoming observer: actual Gio snapshots/signals on a private D-Bus/network namespace cover owner replacement, spoof-sender rejection, cancellation/answer and persisted call outcomes, using synthetic calls without audio or modem access.
- Synthetic ModemManager: actual Gio calls on a private D-Bus and network namespace. Checks cover partial-to-complete reception, persistence over watcher restart, no duplicate submission for a reused request ID, and literal Unicode/quote handling. No real modem or SMS is used.
- Charge policy: simulated 75/80% hysteresis, restart-state retention, warm/cold recovery, invalid sensors and charger-health decisions. These are logic checks, not physical thermal-safety tests.
- Packaging helpers: three unit cases cover preservation of the owner's ramdisk/unrelated boot header, rejection of truncated/unsupported input, and staging without overwriting an existing tree or enabling services.
- Historical kernel inputs: source-archive/recipe SHA512 checks and the full patch sequence passed. The reconstructed microphone-route DTB matched the prior local DTB byte-for-byte.
- Boot helper: reproduced the existing local r35 image byte-for-byte using private local inputs. Neither those inputs nor the image are published.
- imsd candidate: eight suites and five products built on aarch64 clang23/libc++ using a manual module build. Crafter lint was not run. This is not a device redeployment test.
- New kernel PR #12: four target objects compiled and five split patches passed strict checkpatch. No complete image was built or booted.

The complete published source tree has not been deployed from scratch to a clean device. Publication-specific font paths, staging, reconstruction helpers, final Bluetooth-off service, and English CLI/message adaptations remain host-validated only. Historical hardware results do not automatically transfer to these adaptations.

[host-validation.json](../provenance/host-validation.json) retains the initial-publication checkpoint. Later scoped checks are recorded in the same provenance directory. Run `scripts/check.py` for the current host checks; successful host tests do not establish device compatibility.

## Qualification sequence for a new deployment

1. Preserve your own recovery material and verify the matching kernel, modules, DT, initramfs and recovery procedure.
2. With the owner present and USB available, arrange a RAM-only test and verify USB, TTY, filesystem and power behavior.
3. Check Wi-Fi and cellular separately. Bind DNS/TCP/TLS/HTTPS checks to the cellular interface; a single ping failure is not a connectivity diagnosis.
4. Verify IMS registration and carrier backoff. The operator must explicitly select destinations and limits for any call/SMS test; old test allowances do not apply.
5. For calls, confirm speech in both directions, duration, hangup behavior and resource cleanup. For SMS, confirm the received body and persistence across a separately arranged reboot. Recheck services, routing, TTY, Bluetooth and storage health.

Open gates include long-term connectivity and re-registration, real multipart SMS, disk-full recovery, hold/transfer/full renegotiation, long calls, headset switching, suspend/resume, other variants/carriers and emergency calling.

## Recovery and rollback

Before installation, save original files, runlevels, NetworkManager connections and your own verified boot/recovery backups. Let the operator handle any active call before stopping services. Then disable the integration in reverse dependency order and restore the operator's original files.

- The SMS SQLite archive is user data. Uninstalling the receiver does not imply deleting the archive. Stop it before a consistent database/WAL/checkpoint backup; do not automatically delete original modem messages.
- Restore console glyphs from the same device's captured original font and restore its tty1 line/rotation without interrupting an interactive login.
- Do not reuse another device's backups or historical one-shot test state. There is no automatic flash/erase/recovery procedure in this repository; stopping a service is not a reason to write an internal partition.

## Additional r37 evidence

Selected userspace additions have their own [incoming-alert, volume, history and notification record](incoming-alerts.md). It separates operator-confirmed ringing/display and a roughly 60-second two-way call from later playback-only ADC-gain preservation and final notification-frame checks. Nonzero SMS/read-clear notification behavior used isolated data with the actual SMS store. No r37 reboot or complete clean-device reconstruction was performed; the historical baseline results do not qualify untested combinations.

The machine-readable [r37 checkpoint](../provenance/r37-validation.json) records selected source hashes and validation limits. The publication host suite contains 57 tests: 23 SMS, 30 voice/alerts/history, three packaging and one SMS-store notification integration case, plus the charge-policy simulation. The private Gio incoming-call bench is separate and uses no real modem or audio.
