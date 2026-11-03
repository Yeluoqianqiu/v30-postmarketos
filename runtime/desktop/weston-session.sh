#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
umask 077
export XDG_RUNTIME_DIR=/run/v30-desktop/user
# Only the privileged controller writes this session's resolved output values.
. /run/v30-desktop/session.env
export XAUTHORITY="$XDG_RUNTIME_DIR/Xauthority"
export DCONF_PROFILE=/etc/v30-desktop/dconf-profile
export XDG_CONFIG_DIRS=/etc/v30-desktop:/etc/xdg
export GDK_BACKEND=x11
export GSK_RENDERER=cairo
export GTK_IM_MODULE=uim
export QT_IM_MODULE=xim
export XMODIFIERS=@im=uim
export LIBUIM_USER_SCM_FILE=/etc/v30-desktop/uim.scm
export V30_GUI_BACKEND=weston-pixman-rootful
export LIBSEAT_BACKEND=seatd
export SEATD_SOCK=/run/seatd.sock
export PULSE_SERVER=unix:/run/v30-desktop/no-audio
export PIPEWIRE_REMOTE=v30-desktop-no-audio
export LANG=C.UTF-8
unset LC_ALL
export LC_CTYPE=zh_CN.UTF-8
exec >> "$XDG_RUNTIME_DIR/weston.log" 2>&1
exec dbus-run-session -- weston --backend=drm --drm-device="$V30_GUI_DRM_DEVICE" --renderer=pixman --shell=kiosk --config=/run/v30-desktop/weston.ini --socket=wayland-0 -- /opt/v30-desktop/weston-x11.sh
