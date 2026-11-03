#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
umask 077
export XDG_RUNTIME_DIR=/run/v30-desktop/user
export XAUTHORITY="$XDG_RUNTIME_DIR/Xauthority"
export DCONF_PROFILE=/etc/v30-desktop/dconf-profile
export GDK_BACKEND=x11
export GSK_RENDERER=cairo
export GDK_SCALE=2
export XDG_CONFIG_DIRS=/etc/v30-desktop:/etc/xdg
export GTK_IM_MODULE=uim
export LIBUIM_USER_SCM_FILE=/etc/v30-desktop/uim.scm
export QT_IM_MODULE=xim
export XMODIFIERS=@im=uim
export V30_GUI_BACKEND=x11-fbdev
export NO_AT_BRIDGE=1
export PULSE_SERVER=unix:/run/v30-desktop/no-audio
export PIPEWIRE_REMOTE=v30-desktop-no-audio
export LANG=C.UTF-8
unset LC_ALL
export LC_CTYPE=zh_CN.UTF-8
exec >> "$XDG_RUNTIME_DIR/x11.log" 2>&1
exec dbus-run-session -- startx /opt/v30-desktop/x11-apps.sh -- /usr/bin/Xorg :1 -config /etc/v30-desktop/xorg.conf -nolisten tcp vt8 -keeptty -dpi 96
