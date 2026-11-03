"""Give the KMS panel its tested landscape geometry while it owns the desktop lock."""
from contextlib import contextmanager
import fcntl
from pathlib import Path
import subprocess

ACTIVE = Path('/sys/class/tty/tty0/active')
ROTATE = Path('/sys/class/graphics/fbcon/rotate')
DISPLAY = Path('/run/v30-display')


@contextmanager
def panel_rotation():
    if ACTIVE.read_text().strip() != 'tty1':
        raise RuntimeError('Start the panel from tty1')
    original = ROTATE.read_text().strip()
    if original not in ('0', '1', '2', '3'):
        raise RuntimeError('Unknown TTY rotation')
    if original == '1':
        yield
        return
    DISPLAY.mkdir(mode=0o700, exist_ok=True)
    with (DISPLAY/'control.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ROTATE.write_text('1\n')
    try:
        yield
    finally:
        if ACTIVE.read_text().strip() == 'tty1':
            with (DISPLAY/'control.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                ROTATE.write_text(original+'\n')
            subprocess.run(['/usr/local/sbin/v30-console-metrics', '--reflow'],
                           stdout=subprocess.DEVNULL, timeout=5, check=False)
