# Later US998 runtime source reference

This is a source snapshot for review. The public staging tool still selects
the earlier baseline. These components expect the corresponding device
configuration, a matching kernel and boot profile, a locally generated
installation receipt and the runtime paths used by that installation.

- `external-desktop/` contains the r73 display controller, mode reader and
  Weston/Xwayland session code. The caller supplies the installed launcher
  link, dependencies and a matching USB-C/DRM profile. Exit to TTY before
  disconnecting the monitor.
- `orientation/` contains the r81 accelerometer and TTY rotation code,
  including the follow-up for panel rotation. The registry helpers and
  device-owned firmware/calibration are separate prerequisites. Firmware
  and sensor calibration are staged from read-only partitions at runtime.
- `console/` contains status formatting, fonts and the SMS text renderer.
  These files use the existing tmux session, incoming-call state and SMS
  store. The original console font is captured locally, and the operator
  supplies the font package used for full Chinese text rendering.
- `panel/` contains the LVGL 9.5 source and the broker, media, touch and PIN
  components. The target also requires FreeType and the kernel DRM/input
  interfaces, a local font, a device-calibrated touch profile and a locally
  enrolled PIN. The source snapshot includes no credentials. The C fixture
  renders panel states with synthetic inputs.

Firmware, compiled executables, handset-specific installation scripts,
and one-time field test authorizations are outside this source snapshot.
Read the [r81 progress and validation scope](../../docs/r81-progress.md).
