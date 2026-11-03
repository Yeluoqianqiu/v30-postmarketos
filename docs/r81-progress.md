# US998 integration checkpoint through r81

Scope is one LG V30 US998, its existing postmarketOS deployment, and the
specific accessories and carrier used in the recorded tests. r81 is the
local default boot profile. Its kernel release suffix remains r68 because
the later microphone and sensor changes were applied to the device tree.

| Area | Local result | Evidence boundary |
| --- | --- | --- |
| USB-C and external desktop | r68 preserves ownership of discovered Type-C modes, waits for the USB host role before registering DP, and unregisters the owned instances on detach. r71 limited PD negotiation to 2.0. Two display-to-Mac cycles showed a unique DP instance and a clean return to USB gadget with DP disconnected. r72 separately showed 1080p output, mouse clicks, USB keyboard input and manual return to TTY. The r73 default integrated that stack. | One r72 attempt was reported black before the successful repeat. Active-desktop hot unplug, 4K, other display chains and long-duration stability remain open. The PD comparison does not identify the root cause of the earlier resets. |
| Voice recording and playback | r80 added the MIC BIAS3 to MCLK route and was installed as the default. The operator heard their own new recording on the installed system and returned to TTY. | Capture and playback in the panel, within one tested route. Camera, torch and general multimedia are outside that result. |
| TTY and accelerometer | r81 runs authenticated TTY by default, uses SLPI accelerometer readings for orientation, and preserves the tmux pane and four-cell side margins. The operator completed two physical rotation cycles. | On one ordinary reboot the orientation service and IMS became ready on their own, first observed at about 61 and 70 seconds respectively. One reboot is a startup check, not a stability estimate. |
| LVGL panel | On demand from the volume-key chord. Landscape and portrait rendering and touch were checked by the operator. Manual return restored the original TTY session. The phone-specific panel includes Wi-Fi, shortcuts, telephony views, a terminal page and voice notes. | The rotation test did not exercise every panel action. The SMS body parser was separately checked with a temporary store and both supported output languages. |
| Console status and alerts | Native-size icon bitmaps, left and right margins in both orientations, and extra hardware data in landscape. A real incoming call put the number in the center. A real Chinese SMS scrolled its full body three times before the normal status bar returned. | The validation summary omits the number, message and raw logs. New device profiles and long-running use remain unqualified. |
| Browser development | The optional code-server instance saved a browser edit, ran a shell command and read back the saved file on the phone. | Starts on demand. This test does not establish remote exposure or multi-user hardening. |

## Public source layout

- [Reference runtime](../runtime/reference-r81/README.md) contains selected
  source files from the later display, console and LVGL integrations.
- [TCPM patch](../patches/r81-reference/0001-usb-typec-tcpm-preserve-discovered-mode-ownership.patch)
  is an incremental change for the later external-display tree. It requires
  that tree's earlier Type-C, PHY, display and board changes.
- Device-tree deltas after the r68 comparison were a Type-C connector
  `pd-revision = /bits/ 8 <2 0 1 3>` for r71, `MIC BIAS3` to `MCLK` in
  sound routing for r80, and the US998 SLPI remote processor, firmware path
  and reserved-memory change for r81. The orientation reference verifies
  the board and matching device-tree properties before staging firmware.

The [public build guide](build-and-install.md) describes the earlier staged
baseline. It does not reconstruct the complete r81 installation. Device
firmware, private recovery inputs, installation receipts and raw hardware
captures remain with the operator.
