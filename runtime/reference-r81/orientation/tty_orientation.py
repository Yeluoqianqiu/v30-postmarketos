# SPDX-License-Identifier: GPL-3.0-only
"""Apply a screen orientation while preserving the authenticated tty1 session."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

ACTIVE = Path('/sys/class/tty/tty0/active')
ROTATE = Path('/sys/class/graphics/fbcon/rotate')
BLANK = Path('/sys/class/graphics/fb0/blank')
DISPLAY = Path('/run/v30-display')
DESKTOP_LOCK = Path('/run/v30-desktop-r72/control.lock')
PANEL = Path('/run/v30-panel/state.json')
TMUX = ('/usr/bin/tmux', '-u', '-S', '/run/v30-console/tmux.sock')
ORIENTATIONS = {'normal': '0', 'right-up': '1', 'bottom-up': '2', 'left-up': '3'}


def client():
    return subprocess.check_output(
        [*TMUX, 'list-clients', '-F', '#{client_pid}:#{session_id}:#{client_width}x#{client_height}'],
        env=dict(os.environ, LC_ALL='C.UTF-8'), text=True, timeout=3).strip()


def active_console():
    requested = DISPLAY / 'requested'
    return (ACTIVE.read_text().strip() == 'tty1' and BLANK.read_text().strip() == '0'
            and (not requested.is_file() or requested.read_text().strip() != 'off')
            and not PANEL.exists())


def apply_orientation(orientation):
    direction = ORIENTATIONS.get(orientation)
    if direction is None:
        return None
    try:
        with DESKTOP_LOCK.open('a') as desktop, (DISPLAY / 'control.lock').open('a') as display:
            fcntl.flock(desktop, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(display, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not active_console():
                return None
            original = ROTATE.read_text().strip()
            if direction == original:
                return None
            before, _ = client().rsplit(':', 1)
            expected = '120x30' if int(direction) % 2 else '60x60'
            ROTATE.write_text(direction + '\n')
            fcntl.flock(display, fcntl.LOCK_UN)
            try:
                limit = time.monotonic() + 3
                while time.monotonic() < limit:
                    if client() == f'{before}:{expected}':
                        break
                    time.sleep(0.08)
                else:
                    raise RuntimeError('Console resize did not retain the original tmux client')
                result = json.loads(subprocess.check_output(
                    ['/usr/local/sbin/v30-console-metrics', '--reflow'], timeout=4))
                row = result['lines'][-1]
                if len(row) != int(expected.split('x')[0]) or not row.endswith('F2    ') or not row.startswith('    '):
                    raise RuntimeError('Status row did not reflow with the original edge padding')
                return expected
            except (OSError, ValueError, KeyError, IndexError, RuntimeError, subprocess.SubprocessError):
                fcntl.flock(display, fcntl.LOCK_EX)
                if ACTIVE.read_text().strip() == 'tty1':
                    ROTATE.write_text(original + '\n')
                raise
    except BlockingIOError:
        return None
