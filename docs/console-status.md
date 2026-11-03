# Console status and optional input

See the [r81 checkpoint](r81-progress.md) for the latest default and test scope. Older results below describe their original baselines.


The r38 userspace change preserves authenticated landscape TTY, Bluetooth-off,
call/SMS archives and the r35 boot image. It changes only the metrics program and
adds `console_status.py` under `/opt/v30-mobile/libexec/`.

The status bar retains the incoming caller row and persistent missed-call/SMS
row, with at most five rows total. At the tested landscape width of 120 columns,
three base rows show battery/volume/connectivity/clock, cellular status, and
CPU/GPU/memory/storage. Narrower terminals use a compact three-row layout.

| Label | Source and interpretation |
| --- | --- |
| RING | `/etc/v30-incoming.json`, 0-100% bounded ringtone waveform scale; the shared example remains 60% |
| VOL | Read-only ALSA `Speaker Playback Volume`, normalized over its integer control range; 8/15 reads as 53% |
| CELL | Current registered ModemManager 3GPP `OperatorName`; an empty name falls back to `OperatorCode` with selected PLMN aliases, otherwise the numeric code |
| NET | ModemManager `AccessTechnologies` for the current registration, never supported-band/mode lists; LTE is 4G |
| SIG | `SignalQuality` percentage and freshness flag; thresholds 1/25/50/75 give one/two/three/four ASCII bars |

`.... 0%` is a fresh zero reading. `|||| 90% STALE` shows the last known bars and
percentage with an explicit old-reading warning;
`???? --` is unavailable. These bars are a UI convention, not a standardized
dBm conversion. Extended signal polling remains disabled when already disabled;
the reader never enables it or invents RSRP/RSSI values. No registration is
shown as `NO SERVICE` or `SEARCH`, with no old operator or quality presented as
current. Stale registered readings retain their last bars with `STALE`; missing
or ambiguous modems return unknown. A roaming registration gets
`ROAM`. Operator labels are bounded ASCII, excluding tmux/terminal expansion.

Each visible refresh performs bounded read-only bus/mixer queries. The bus
owner is pinned for the snapshot; a replacement/failure yields unknown for that
refresh. No modem setup, radio-mode change, SIM access, audio playback/capture,
volume-control write, call action or SMS action is part of the reader. It does
not persist subscriber identifiers or message contents. Blanked displays retain
the existing policy of stopping refreshes until the next visible update.

`VOL` is a speaker control fraction, not perceived loudness, microphone gain,
in-call gain or a PipeWire stream volume. `RING 100%` is the application's upper
bound; it retains the existing peak limit and hardware playback gain of 8/15.
Changing that preference does not play a ringtone. The owner's setting is
separate from the conservative example default for other installations.

## Graphics, touch and Chinese

The inspected TTY installation has DRM `card0`/`renderD128`, Mesa/freedreno,
Wayland/GTK libraries and an `stmfts` input node. It has no installed Phosh,
Phoc, virtual keyboard or Chinese input-method package in the inspected package
database. Driver nodes establish detection, not a fresh touch interaction test.
The [upstream V30 port](https://github.com/ShapeShifter499/lg-v30-port) reports
Phosh, display/GPU and touch working on its own documented baseline.

An optional graphical session can therefore be evaluated without making it the
default boot target. It still needs compositor/shell installation, touch-axis
mapping in landscape, a virtual keyboard and Unicode font/input integration.
[Stevia](https://github.com/PhoshMobi/stevia) provides a Phosh on-screen keyboard
with experimental Chinese/Japanese via uim. Alternatively,
[Fcitx 5](https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland) has Chinese engines,
but compositor, application and virtual-keyboard integration must be tested
together. None of those graphical input paths has been qualified on this image.
Existing UTF-8 SMS storage is independent of full CJK rendering/input on the
current limited-glyph framebuffer console. A remote Unicode SSH terminal can
use its client's fonts and Chinese input method.

Android also uses a Linux kernel, but its ART/framework, Binder interfaces and
[HAL services](https://source.android.com/docs/core/architecture/hal) add separate
dependencies. Firmware/device-tree/driver knowledge can be reused where
compatible; arbitrary Android HAL libraries, kernel modules or APKs are not
drop-in native Linux components. A
[libhybris adaptation](https://docs.sailfishos.org/Reference/Architecture/) or
[Waydroid session](https://docs.waydro.id/usage/install-on-desktops) is separate
work with its own kernel/userspace requirements and device validation. The V30's
[Snapdragon 835 / X16 LTE hardware](https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/snapdragon_product_brief_835_0.pdf)
cannot acquire a 5G NR radio through software.

## Validation scope

Host tests cover registration loss, multiple modems, LTE/NR bitmasks, fresh-zero
versus stale/invalid quality, PLMN fallback, hostile operator text, ALSA ranges,
and fixed-width layout. Package staging includes the new helper. On the inspected device, both userspace files were installed with a guarded
backup/rollback and their hashes verified. The 120-column framebuffer shows
separate levels, the network operator, LTE, fresh four-bar signal quality,
and the existing unread counters. The earlier readout also confirmed that stale
quality is explicitly labeled; stale-bar formatting has isolated tests. Six services remain healthy, IMS registered,
SMS ready, Bluetooth off, framebuffer rotation 1 and four PCM devices closed;
protected files and boot are unchanged. The owner preference is now `RING 100%`.
See the [r38 validation checkpoint](../provenance/r38-validation.json).

These checks are not another voice/SMS, ringtone listening, reboot, GUI or
touch-interaction pass.

## r39 compact rendering

The later renderer places the ordinary indicators and notification counts in
one row, with CPU/GPU/temperature/RAM/storage on the second. A temporary incoming
caller row is still separate. Wi-Fi/Bluetooth use explicit ON/OFF text; battery
and speaker/ringtone values omit the percent sign. Signal quality keeps its
percentage and explicit stale indication. No archive/read marks are changed.

Thirty native 24x48 glyph cells replace the coarse scaled icons. Battery and
signal bars are original drawings with separated signal columns. Ten Chinese
characters form fixed labels for Unicom, charging/not charging, speaker,
ringtone, missed calls and SMS. Each Chinese character uses two private-use
cells, avoiding disagreement between tmux CJK widths and the Linux console.
This does not install a general Chinese TTY font or input method. The original
console font snapshot stays device-owned; the derived Noto CJK subset retains
OFL-1.1 attribution and its source-font digest.

An optional [graphical session](manual-desktop.md) provides full CJK fonts and
an on-screen input path. It is independent of the default two-row TTY profile.
