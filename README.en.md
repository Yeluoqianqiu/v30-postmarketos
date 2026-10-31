# V30 postmarketOS

[Chinese](README.md) | **English**

Unofficial, experimental postmarketOS integration and reconstruction notes for the LG V30 US998, using a landscape TTY interface.

This project builds on **postmarketOS, Linux and ShapeShifter499's V30 mainline port**. The IMS protocol and media implementation come from **Catcrafts imsd**. Our additions cover component integration, boot ordering, per-call audio ownership and cleanup, persistent SMS, incoming alerts and ringtone volume, call history and persistent notifications, speaker-volume and cellular status, selected interoperability fixes, and scoped validation. See [acknowledgements](ACKNOWLEDGEMENTS.md) and [provenance](PROVENANCE.md) for upstream work and licensing.

**Validation applies to specific versions and tests.** Historical r35/r36 results came from one US998 on China Unicom. Host reconstruction/packaging checks are distinct from device observations; selected r37/r38 userspace changes and later revisions are scoped below. The complete published tree has not undergone a fresh end-to-end deployment on a clean device. The newer kernel candidates have not been booted on the device. Ready for review describes the PR stage, not upstream acceptance or device qualification.

See the [integration contribution map](docs/contributions.md) for our completed work and its upstream foundations, and the [open TODO / roadmap](TODO.md) for server reliability, ringing/caller ID, SMS improvements and remaining qualification work. Roadmap items include acceptance criteria and remain open until supported by evidence.

The Chinese README is a localized overview; the remaining project documentation and CLI messages are currently in English.

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
