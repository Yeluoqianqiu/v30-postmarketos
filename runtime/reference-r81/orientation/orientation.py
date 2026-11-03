#!/usr/bin/python3
"""Rotate the built-in text console from the V30 US998 accelerometer."""
from collections import deque
import json
import math
import os
from pathlib import Path
import signal
import stat
import statistics
import time

from prepare import start, stop_registry, root
from smgr import Accelerometer
from tty_orientation import active_console, apply_orientation, DESKTOP_LOCK, ORIENTATIONS, ROTATE, ACTIVE, DISPLAY, PANEL

# Physically verified on US998 with the original stock calibration.
DIRECTION_DIR = Path('/run/v30-screen-orientation')
DIRECTIONS = {(0, 1): 'normal', (1, 1): 'right-up', (0, -1): 'bottom-up', (1, -1): 'left-up'}


def stable(window):
    if len(window) != window.maxlen:
        return None
    vector = tuple(statistics.median(axis) for axis in zip(*window))
    magnitude = math.sqrt(sum(value * value for value in vector))
    if not .5 <= magnitude <= 15:
        return None
    if max(math.dist(value, vector) for value in window) > magnitude * .22:
        return None
    in_plane = math.hypot(vector[0], vector[1])
    strongest = max((0, 1), key=lambda axis: abs(vector[axis]))
    if in_plane < .4 * magnitude or abs(vector[strongest]) < .85 * in_plane:
        return None
    return DIRECTIONS[strongest, 1 if vector[strongest] > 0 else -1]


def terminate(*args):
    raise SystemExit(0)


def write_ready(path, state):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state) + '\n')
    tmp.replace(path)


def target(boot):
    if Path('/run/seatd.sock').exists():
        return None
    if active_console():
        return 'tty'
    try:
        panel = json.loads(PANEL.read_text())
        requested = DISPLAY / 'requested'
        if (panel.get('boot_id') == boot and panel.get('active')
                and panel.get('tty') == ACTIVE.read_text().strip()
                and panel['tty'] != 'tty1'
                and (not requested.exists() or requested.read_text().strip() != 'off')):
            return 'panel'
    except (FileNotFoundError, ValueError):
        pass
    return None


def publish(direction):
    path = DIRECTION_DIR / 'direction'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(direction + '\n')
    tmp.chmod(0o644)
    tmp.replace(path)


def main():
    os.umask(0o077)
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(sig, terminate)
    DESKTOP_LOCK.parent.mkdir(mode=0o755, exist_ok=True)
    DIRECTION_DIR.mkdir(mode=0o755, exist_ok=True)
    info = DIRECTION_DIR.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('Invalid display orientation directory')
    DIRECTION_DIR.chmod(0o755)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    registry, state = start()
    ready = root/'ready.json'
    try:
        with Accelerometer() as sensor:
            _, inventory = sensor.discover()
            sensor.start()
            for _ in range(5):
                if sensor.read():
                    break
            else:
                raise RuntimeError('No SLPI accelerometer samples')
        write_ready(ready, {'accelerometer': True, 'slpi': 'running',
                            'boot': boot})
        last = ROTATE.read_text().strip()
        if last in ORIENTATIONS.values():
            publish(last)
        retry_tty_at = 0.0
        while registry.poll() is None and state.read_text().strip() == 'running':
            if not target(boot):
                time.sleep(1)
                continue
            with Accelerometer() as sensor:
                sensor.discover()
                sensor.start()
                history = deque(maxlen=8)
                while (owner := target(boot)) and registry.poll() is None:
                    for values in sensor.read():
                        history.append(values)
                        direction = stable(history)
                        if not direction:
                            continue
                        angle = ORIENTATIONS[direction]
                        if angle != last:
                            publish(angle)
                            last = angle
                        if (owner == 'tty' and time.monotonic() >= retry_tty_at
                                and ROTATE.read_text().strip() != angle):
                            try:
                                apply_orientation(direction)
                            except KeyError as error:
                                if error.args != ('lines',):
                                    raise
                                # A cold status cache has no layout yet. TTY rotation
                                # already rolled back. Retry without losing sensor data.
                                retry_tty_at = time.monotonic() + 1
    finally:
        ready.unlink(missing_ok=True)
        (DIRECTION_DIR / 'direction').unlink(missing_ok=True)
        stop_registry(registry)


if __name__ == '__main__':
    main()
