# Integration contributions

This map records the work contributed by this project and the evidence available as of 2026-10-31. It complements the [architecture](architecture.md), [validation record](validation.md) and [open roadmap](../TODO.md).

The Linux kernel, postmarketOS distribution, V30 mainline port and IMS protocol/media engine are upstream work. Our contribution is the integration below, selected fixes and scoped validation on one LG V30 US998. See [acknowledgements](../ACKNOWLEDGEMENTS.md) for the people and projects involved and [provenance](../PROVENANCE.md) for file origins and licenses.

## Boot, data and IMS integration

- Added OpenRC ordering and supervision for modem helpers, Wi-Fi, audio, carrier policy, IPA, cellular data and IMS. ModemManager uses distribution D-Bus activation to avoid duplicate daemon instances.
- Kept the NetworkManager data connection separate from the IMS IPv6 PDN. Added raw-IP address handling, MTU limits, P-CSCF discovery and host routes without installing an IMS default IPv6 route.
- Restricted firewall changes to the integration's own IMS rules and preserved carrier retry backoff across service restarts and boots.
- Integrated the tested voice profile into ordinary default boot after RAM-only testing and operator approval. Recovery was preserved.

Sources: [voice services and supervision](../runtime/voice/), [support services](../runtime/support/).

## IMS interoperability changes

- Added an opt-in LG-style six-combination Security-Client offer, selecting a common server proposal with the highest supported preference. The default single-offer behavior remains available.
- Preserved all Via headers in SIP 200 responses.
- Handled an incoming offerless re-INVITE by sending an SDP offer in the 200 response and accepting the matching ACK answer, with a bounded timeout, duplicate-response caching and protection against stale ACKs. Bodyless UPDATE remains bodyless.
- Added an optional bounded metadata trace, disabled by default, without adding raw identities, SDP bodies or audio to that trace.

These extend [Catcrafts imsd](https://forgejo.catcrafts.net/Catcrafts/imsd); they do not replace its SIP, AKA, IPsec, RTP or codec implementation. The re-INVITE work covers fixed-media behavior, not full media renegotiation, hold or transfer. The patch is [bundled here](../patches/imsd/0001-v30-interop.patch) and has not been submitted to the imsd Forgejo upstream.

## Per-call audio ownership and cleanup

- Connected the US998 microphone and speaker paths through MultiMedia1 capture, MultiMedia2 playback and a temporary PipeWire graph for each call.
- Added exclusive audio ownership, parent/process/boot identity checks and failure cleanup. Checking `/proc/PID/exe` fixed a transient empty-command-line race that could terminate a call immediately after acceptance.
- Saved and restored mixer state, closed PCM devices after teardown and checked cleanup after normal calls and failure paths.

Sources: [audio session](../runtime/voice/audio_session.py), [call media lifecycle](../runtime/voice/call_media.py), [media links](../runtime/voice/link.py). The ADC MUX8 and microphone MCLK dependencies build on upstream driver/device-tree work; we do not claim those fixes as original audio-driver development.

## Persistent TTY SMS tooling

- Added a receiver, SQLite archive and explicit `v30-sms` commands for status, listing, reading and sending. Complete received messages are archived; local unread state is independent of network delivery state.
- Inventoried startup messages through `Messaging.Messages`, including when SMS objects are missing from the ObjectManager snapshot. Bound modem object paths to the D-Bus owner and boot, with startup deduplication that preserves distinct equal-content live messages.
- Persisted outgoing intent before Create/Send and used request IDs for idempotency. Ambiguous results remain pending or unknown; the tooling never automatically retries a send, replies or deletes original modem messages.
- Added GSM7/UCS2 segment accounting and a ten-segment limit. Non-BMP characters are rejected; actual multipart delivery remains unqualified.

Sources: [SMS implementation and tests](../runtime/sms/). The archive is `/var/lib/v30-sms/messages.sqlite`, with SQLite WAL/SHM files in the same directory when in use. The directory is mode 0700 and the database is mode 0600. Message bodies and numbers are stored as unencrypted database text, not one text file per message. `/run/v30-sms/status.json` contains transient status/counts, not the archive. One ordinary reboot preserved the tested messages without duplicate submission; automatic off-device backup is still open work.

## Power and landscape console

- Fixed fuel-gauge charger-status/current reporting and exposed charge inhibition while retaining USB input power. Added a userspace charge-limit policy with 75% resume / 80% inhibition thresholds and conservative sensor/temperature decisions.
- Integrated a landscape TTY, larger console glyphs, a Celsius glyph, corner-aware status placement and shared display/refresh locking while retaining normal login authentication.
- Added short-power-key display toggling and an opt-in Bluetooth-off policy. Display blanking does not suspend the system.

Sources: [support tools](../runtime/support/), [kernel candidates](../patches/current-kernel/). Charge inhibition with USB power was checked on hardware; hysteresis and abnormal-temperature decisions have simulation coverage only. The two GCC clock changes adapt Dmitry Baryshkov's patches and retain his authorship. IPA system-header, GLINK and ADC/MCLK fixes already present in the newer base are not duplicate new contributions.

## Reconstruction, validation and upstream submissions

- Published source pins, historical kernel configuration/patches, build and staging helpers, DTB patching, boot repacking and recovery instructions. Firmware, private configuration, whole-device images and message archives are excluded.
- Added host syntax, packaging, SMS, voice-lifecycle and charge-policy checks, including a private D-Bus/network-namespace SMS bench with synthetic peers.
- Separated signaling from usable speech: historical acceptance required operator confirmation of clear audio in both directions, followed by mixer/PCM cleanup checks.
- Submitted [harness PR #11](https://github.com/ShapeShifter499/lg-v30-port/pull/11) and [kernel PR #12](https://github.com/ShapeShifter499/linux-lg-v30-joan/pull/12). See [upstream status](upstream.md) for review stage, authorship and remaining submission work.

## Evidence boundary

Historical r35/r36 testing used the older `7.2.0-rc2-v30-r30` kernel stack on one US998 with China Unicom. It covered an earlier outgoing call, incoming calls of about 60 seconds in RAM and after default boot, short Chinese SMS in both directions, archive persistence after one ordinary reboot, data checks, landscape TTY and Bluetooth off.

The complete published source tree has not been freshly deployed end to end on a clean device. Publication-specific packaging, paths and English adaptations have host checks only. The newer kernel series has four affected objects compiled, with no full image build or device boot. Final-version 24/72-hour server stability, local audible ringing, automatic TTY caller display and persistent call history are open work, tracked in [TODO](../TODO.md).
