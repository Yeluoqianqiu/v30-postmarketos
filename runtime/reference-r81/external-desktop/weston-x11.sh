#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
python3 - <<'PY'
import os,secrets,subprocess
subprocess.run(['xauth','-f',os.environ['XAUTHORITY'],'source','-'],
               input='add :1 . '+secrets.token_hex(16)+'\n',text=True,check=True)
PY
# Rootful Xwayland keeps the qualified Openbox/Onboard/UIM input layout.
# -shm disables Glamor; all rendering stays on the software path.
exec xinit /opt/v30-desktop-r72/x11-apps.sh -- /usr/bin/Xwayland :1 -shm -fullscreen -output "$V30_GUI_CONNECTOR" -geometry "$V30_GUI_GEOMETRY" -auth "$XAUTHORITY" -nolisten tcp -dpi 96
