#!/usr/bin/python3
"""Coordinate display blanking without requesting shutdown or suspend."""
import fcntl,sys,time
from pathlib import Path
RUN=Path('/run/v30-display');RUN.mkdir(mode=0o700,exist_ok=True)
blank=Path('/sys/class/graphics/fb0/blank')
with (RUN/'control.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    action=sys.argv[1] if len(sys.argv)>1 else 'status'
    if action=='toggle':action='on' if blank.read_text().strip()!='0' or (RUN/'requested').exists() and (RUN/'requested').read_text().strip()=='off' else 'off'
    if action in ('on','off'):
        (RUN/'requested').write_text(action+'\n')
        blank.write_text('0\n' if action=='on' else '4\n')
        if action=='off':
            # Wait for queued console updates before blanking again.
            time.sleep(.15)
            blank.write_text('4\n')
    elif action=='status':
        print(blank.read_text().strip())
        print(Path('/sys/bus/platform/devices/c901000.display-controller/power/runtime_status').read_text().strip())
    else:raise SystemExit('Usage: v30-display on|off|toggle|status')
