#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
uim-xim --engine=py > "$XDG_RUNTIME_DIR/uim-xim.log" 2>&1 &
ime=$!
openbox > "$XDG_RUNTIME_DIR/openbox.log" 2>&1 &
wm=$!
gsettings set org.gnome.desktop.interface enable-animations false
gsettings set org.onboard layout Compact
gsettings set org.onboard show-status-icon false
gsettings set org.onboard.auto-show enabled false
gsettings set org.onboard.window docking-enabled true
gsettings set org.onboard.window docking-shrink-workarea true
gsettings set org.onboard.window.landscape height 480
gsettings set org.onboard.window.portrait height 720
gsettings set org.onboard.keyboard audio-feedback-enabled false
onboard > "$XDG_RUNTIME_DIR/onboard.log" 2>&1 &
osk=$!
refresh=
if [ "$V30_GUI_BACKEND" = x11-fbdev ]; then
    /opt/v30-desktop-r72/fb-refresh.py > "$XDG_RUNTIME_DIR/fb-refresh.log" 2>&1 &
    refresh=$!
fi
trap 'if [ -n "$refresh" ]; then kill "$refresh" 2>/dev/null || true; fi; kill "$osk" "$wm" "$ime" 2>/dev/null || true' EXIT HUP INT TERM
/opt/v30-desktop-r72/x11-home.py
