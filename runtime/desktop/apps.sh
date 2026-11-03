#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
gsettings set org.gnome.desktop.interface enable-animations false
gsettings set org.gnome.desktop.a11y.applications screen-keyboard-enabled true
gsettings set org.gnome.desktop.input-sources sources "[('xkb', 'us'), ('ibus', 'uim:cn')]"
gsettings set mobi.phosh.osk ignore-hw-keyboards true
phosh-osk-stevia > "$XDG_RUNTIME_DIR/v30-osk.log" 2>&1 &
osk=$!
trap 'kill "$osk" 2>/dev/null || true' EXIT HUP INT TERM
/opt/v30-desktop/home.py
