#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
umask 077
export GDK_BACKEND=wayland
export XDG_CONFIG_DIRS=/etc/v30-desktop:/etc/xdg
export V30_GUI_BACKEND=phoc-pixman-native
export GSK_RENDERER=cairo
export GTK_IM_MODULE=wayland
export QT_IM_MODULE=wayland
export XDG_CURRENT_DESKTOP=V30
export XDG_RUNTIME_DIR=/run/v30-desktop/user
export NO_AT_BRIDGE=1
# Isolate GUI preferences; keep the user's ordinary desktop settings untouched.
export DCONF_PROFILE=/etc/v30-desktop/dconf-profile
export PULSE_SERVER=unix:/run/v30-desktop/no-audio
export PIPEWIRE_REMOTE=v30-desktop-no-audio
export LIBSEAT_BACKEND=seatd
export SEATD_SOCK=/run/seatd.sock
export XDG_SESSION_TYPE=wayland
export WLR_RENDERER=pixman
export WLR_NO_HARDWARE_CURSORS=1
exec >> "$XDG_RUNTIME_DIR/phoc.log" 2>&1
exec dbus-run-session -- phoc --no-xwayland --config=/etc/v30-desktop/phoc.ini --exec=/opt/v30-desktop/apps.sh
