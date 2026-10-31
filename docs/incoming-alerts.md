# Incoming alerts, ringtone volume and call history

The optional `v30-incoming` service observes imsd calls through D-Bus. It adds a speaker ringtone, wakes the display once per incoming call, inserts an `INCOMING` caller row into the existing landscape TTY status bar and records local call history. It does not accept, dial, reject or hang up a call. Bluetooth and login authentication are unchanged.

## Status and scope

On 2026-10-31, the operator confirmed audible ringing, automatic wake/caller display and stop/clear after cancellation. After raising the configured ringtone level, an accepted incoming call lasted about 60.37 seconds with operator-confirmed clear two-way speech and normal display/volume behavior. The final media lifecycle reported all ten controls restored and all four PCM devices closed. A pre-ringing ADC-gain comparison differed; additional gain preservation was added afterward and passed a playback-only test checking all ten controls. This final gain change and the later persistent counters have host/playback/idle checks, without another speech call or reboot.

The implementation also has Linux-root lifecycle/locking tests and a private D-Bus/network-namespace test using actual Gio snapshots/signals. The service targets the historical `7.2.0-rc2-v30-r30` US998 stack; it does not establish compatibility with a newer kernel or another audio topology. No new boot image is required for this userspace addition. Repeated-call, reject/timeout/crash and reboot qualification remain open.

The [r37 validation checkpoint](../provenance/r37-validation.json) lists the nine selected runtime/configuration source hashes and separates the speech observation from subsequent playback/notification checks. It is a sanitized summary, not publicly distributed raw device evidence.

## Audio ownership

The ringtone uses only `hw:LGV30,1` stereo playback at 48 kHz. A synthesized two-pulse tone repeats every two seconds, with fixed speaker volume control 8. Software amplitude is configurable from 0 to 100%, capped at -12 dBFS peak; the default 60% is approximately -16.5 dBFS. This raises the signal from the initial quiet test while retaining the hardware gain. It does not open a microphone or start PipeWire. A worker is bounded to 90 seconds and stops if its parent dies or its heartbeat is stale.

Ringtone and call media share `/run/v30-call-audio.lock`. Before waiting for that lock, call media reserves `/run/v30-call-priority.lock`; the ringtone checks this reservation every 50 ms and stops. Call media starts only after playback exits and its mixers have been restored. The journal also preserves ADC3 gain across the speaker power cycle, restoring it after playback routing without opening capture PCM. Recovery after worker failure occurs only under the audio lock. Cleanup failures retain the journal and prevent a false successful handoff.

Active or outgoing calls suppress a second ringtone. Call waiting, headset switching and multiple simultaneous calls are outside this implementation's scope. A failed or expired ringtone worker is not automatically restarted for the same observed call.

## Display and privacy

The observer binds snapshots/signals to the current unique imsd bus owner and withdraws old-owner state on replacement. It queries `GetCalls` with no auto-start flag and never invokes call-control methods. It reconciles events with periodic snapshots so startup and missed events do not depend on one signal.

Only bounded phone-number characters can reach the tmux format. Missing, anonymous or unsafe values become `Unknown/withheld`; displayed caller ID is network-provided information, not verified identity. The row is removed on answer, cancellation, termination or owner loss. It also expires after six seconds without a fresh status record.

The current imsd call-information API has no separate privacy indicator. Carrier-specific identity-withholding behavior is not qualified; the observer can only use the number or anonymous value provided by that API.

Caller display is intentionally visible at the physical login screen. It does not inject text into a shell/login prompt, switch VTs or bypass authentication. The display is woken once; a later power-key press is respected. Ending a call clears its number but leaves the display on for the user's normal display controls.

Display/audio state is private and transient in `/run/v30-alerts` (0700, files 0600), including `display.json`, `status.json`, a heartbeat and any outstanding mixer journal. The metrics cache also resides in private `/run`. Numbers are not written to service logs; the separate call-history archive below intentionally persists caller information.

## Volume and history commands

```sh
sudo v30-phone ring-volume       # Read the configured ringtone percentage.
sudo v30-phone ring-volume 60    # Set the next incoming call's ringtone level.
sudo v30-phone ring-volume 0     # Mute ringing; display wake/caller ID still work.
sudo v30-phone history --missed  # Confirmed missed calls, newest first.
sudo v30-phone history --missed --mark-read  # Clear marks for the rows shown.
sudo v30-phone history --limit 20
sudo v30-sms list --unread
sudo v30-sms read ID             # Read one message and clear its local unread flag.
```

The status bar shows `RING 60%` or `RING MUTE` alongside Bluetooth state. This is the configured ringtone amplitude within the capped range, not an acoustic loudness measurement or in-call voice volume. Settings persist in `/etc/v30-incoming.json` (0600). Apply changes before the next call; increasing the level does not restart a ringtone already suppressed for the current call. Invalid configuration mutes the ringtone rather than selecting an uncontrolled level.

Call history is unencrypted SQLite in `/var/lib/v30-mobile/calls.sqlite` (0600, directory 0700), with same-directory WAL/SHM files while open. Rows contain number, direction, start/answer/end times, result and evidence source. The history command works without contacting imsd or a modem. It does not read or modify the SMS archive.

An incoming call with a terminal remote-hangup event and no observed answer is `missed`; a locally rejected incoming call is `rejected`. An observed active state records `answered`. Owner loss or disappearance without enough terminal evidence becomes `unknown`, not a fabricated missed call. Duplicate events and owner-bound IDs are reconciled. Storage errors set `history_ready` false while notifications continue. Existing rows survive service restart; device reboot persistence has not yet been separately tested for this new archive.

One operator-confirmed missed call from before history installation was imported from its test report and is explicitly labelled `[test-report]`. Other records are observed live. History retention/deletion/export and full-storage recovery remain open work. Back up the database consistently with SQLite's backup API, including committed WAL data; rollback preserves the archive.

## Persistent notification row

The TTY keeps a `MISSED n   SMS n` row while either archive has an unhandled missed call or unread incoming message. Counts come from read-only SQLite queries and do not expire with the six-second current-caller display. They survive observer/console service restarts because their marks live in the archives. The row remains until explicitly handled, and disappears when both counts are zero. Unknown/failed database reads show `?` rather than silently clearing a notification.

Listing call history alone leaves its marks intact. `history --missed --mark-read` clears only the selected displayed rows, so a concurrently arriving call is not acknowledged accidentally. It does not delete calls. `v30-sms read ID` uses the existing SMS tool's local read state; it does not reply or acknowledge network delivery. Notification reads never mark SMS read. No actual unread message or missed-call mark was cleared during the device checks.

The final device framebuffer showed the notification row alongside `RING 60%`, Bluetooth off and normal login. SMS nonzero/read-clear behavior was exercised against the actual SMS store implementation with isolated synthetic data; no fresh carrier SMS was sent for this addition. Refresh follows the existing roughly five-second visible-console cycle. A blank display remains blank; the counts reappear when it is lit. On narrow layouts the status area stays within tmux's five-row limit.

## Installation and rollback

[Staging](build-and-install.md) includes four new Python modules, `/etc/init.d/v30-incoming`, the updated call-media wrapper, console metrics tool and `v30-phone`, plus the ringtone configuration. Install these together: the commands and services import the new modules. Dependencies are Python with SQLite and Gio/GLib, D-Bus, ALSA `aplay`/`amixer` and the existing tmux/display tools. Do not replace modem, imsd, SMS, getty or boot/recovery for this feature.

Before installation, verify no active call and all PCM devices closed, preserve original files and runlevel state, and prepare a rollback. After installing the selected files, restart only `v30-console-status`, then explicitly start/enable `v30-incoming` as part of the chosen TTY profile. Its OpenRC dependency ordering follows audio/IMS/console services. Staging itself does not start or enable anything.

For rollback, first finish any live call, stop/disable `v30-incoming`, wait for its ringtone to release audio, restore the original call-media, console-metrics and `v30-phone` files, then remove only the new files owned by this installation. Recover any outstanding mixer journal under the audio lock before removing the recovery module. Preserve changed operator settings in the backup and retain the call-history and SMS archives. Restart the console metrics service and keep the backup/receipt.

## Checks and hardware acceptance

```sh
python3 -m unittest discover -s runtime/voice -p 'test_*.py' -v
# Linux root, private bus and network namespace, synthetic calls only:
unshare --net -- dbus-run-session -- sh -c \
  'export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; exec python3 "$1"' \
  qa runtime/voice/bench_incoming_bus.py
```

Arrange fresh call authorization with the operator before physical acceptance. Begin with the display off: observe audible ringing, a lit landscape TTY and correct/unknown caller display. Exercise remote cancellation, then a separately authorized accepted call with human-confirmed two-way speech. Confirm ringing stops before call media starts, the caller row clears, mixers restore, all PCM devices close, IMS/SMS remain healthy and Bluetooth remains off. Do not convert host tests into hardware claims or reuse an earlier one-time call allowance.

One accepted-call attempt was stopped before Accept because the test sampler failed to observe playback. The operator heard the ringtone; a separate local probe observed both RUNNING and DRAINING playback states (see the [ALSA PCM interface reference](https://www.alsa-project.org/alsa-doc/alsa-lib/pcm.html)). The retry sampler accepted both states and waited longer for evidence. Raw failed test records are retained privately. This test-controller correction did not enable automatic acceptance in the production observer.
