#!/usr/bin/python3
"""Hold both volume buttons to open or close the authenticated V30 panel."""
import os
import sys

if __name__ == "__main__" and not sys.flags.no_site:
    # The listener and its launch worker use only standard-library modules.
    os.execv(sys.executable, [sys.executable, "-BS", __file__])

import fcntl
from pathlib import Path
import selectors
import signal
import struct
import time

KEYS = {"Volume up": 115, "pm8941_resin": 114}
EVENT = struct.Struct("llHHi")
EVIOCGKEY = 0x80104518  # _IOR('E', 0x18, 16 bytes)
VT = Path("/sys/class/tty/tty0/active")
RUN = Path("/run/v30-panel-key")
HOLD = 0.7
WORKER_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
ending = False


class Chord:
    def __init__(self, held=()):
        self.held = set(held)
        self.fired = bool(self.held)
        self.since = None

    def event(self, code, value, now):
        if code not in KEYS.values() or value not in (0, 1):
            return
        if value == 0:
            self.held.discard(code)
            self.since = None
            if not self.held:
                self.fired = False
            return
        if code in self.held:
            return
        self.held.add(code)
        if len(self.held) == 2:
            self.since = now

    def ready(self, now):
        if self.fired or self.since is None or now - self.since < HOLD:
            return False
        self.fired = True
        return True


def held_keys(nodes):
    held = []
    for fd, key in nodes.items():
        state = bytearray(16)
        fcntl.ioctl(fd, EVIOCGKEY, state, True)
        if state[key // 8] & (1 << (key % 8)):
            held.append(key)
    return held


def record(event, **details):
    temp = RUN / "last.tmp"
    # Event names and field names are fixed literals at the call sites.
    fields = "".join(f',"{name}":{value:d}' for name, value in details.items())
    temp.write_text(f'{{"event":"{event}"{fields}}}\n')
    temp.replace(RUN / "last.json")


def finish(*_):
    global ending
    ending = True


def start_panel():
    # Only the child imports the launcher. The listener keeps its idle footprint.
    reader, writer = os.pipe()
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, WORKER_SIGNALS)
    try:
        try:
            pid = os.fork()
        except OSError:
            os.close(reader)
            os.close(writer)
            raise
        if pid:
            os.close(reader)
            return pid, writer
        code = 1
        try:
            os.setsid()
            if reader < 3:
                copy = fcntl.fcntl(reader, fcntl.F_DUPFD_CLOEXEC, 3)
                os.close(reader)
                reader = copy
            null = os.open(os.devnull, os.O_RDWR)
            for fd in (0, 1, 2):
                os.dup2(null, fd)
            for entry in os.listdir("/proc/self/fd"):
                fd = int(entry)
                if fd > 2 and fd != reader:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            for sig in WORKER_SIGNALS:
                signal.signal(sig, signal.SIG_DFL)
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            from runner import start_from_key
            loaded_ms = time.monotonic_ns() // 1_000_000
            # EOF is cancellation. No display or device checks run before the go byte.
            command = os.read(reader, 1)
            os.close(reader)
            code = start_from_key(loaded_ms) if command == b"1" else 0
        finally:
            os._exit(code)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def request_close(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def cancel_preparation(prepared, retiring):
    pid, gate, _ = prepared
    os.close(gate)
    request_close(pid)
    retiring.add(pid)


def main():
    if os.geteuid() != 0:
        raise SystemExit("v30-panel-key requires root")
    os.umask(0o077)
    RUN.mkdir(mode=0o700, exist_ok=True)
    signal.signal(signal.SIGTERM, finish)
    signal.signal(signal.SIGINT, finish)
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    panel = None
    retiring = set()
    try:
        while not ending:
            nodes = {}
            prepared = None
            try:
                with selectors.DefaultSelector() as selector:
                    devices = {name: [] for name in KEYS}
                    for path in Path("/sys/class/input").glob("event*"):
                        try:
                            name = (path / "device/name").read_text().strip()
                        except FileNotFoundError:
                            continue
                        if name in devices:
                            devices[name].append(Path("/dev/input") / path.name)
                    if any(len(paths) != 1 for paths in devices.values()):
                        raise OSError("Expected one event device for each volume key")
                    for name, (path,) in devices.items():
                        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
                        nodes[fd] = KEYS[name]
                        selector.register(fd, selectors.EVENT_READ)
                    chord = Chord(held_keys(nodes))
                    dropped = set()
                    record("listening")
                    while not ending:
                        timeout = (1.0 if chord.since is None or chord.fired or dropped else
                                   max(0.0, chord.since + HOLD - time.monotonic()))
                        if retiring:
                            timeout = min(timeout, 0.05)
                        for key, _ in selector.select(timeout=timeout):
                            fd = key.fd
                            try:
                                data = os.read(fd, 64 * EVENT.size)
                            except BlockingIOError:
                                continue
                            if not data or len(data) % EVENT.size:
                                raise OSError("Volume-key stream interrupted")
                            for _, _, kind, code, value in EVENT.iter_unpack(data):
                                if kind == 0 and code == 3:  # SYN_DROPPED
                                    dropped.add(fd)
                                elif fd in dropped:
                                    if kind == 0 and code == 0:
                                        dropped.remove(fd)
                                        chord = Chord(held_keys(nodes))
                                elif kind == 1 and code == nodes[fd]:
                                    chord.event(code, value, time.monotonic())
                        if ending:
                            break
                        for pid in tuple(retiring):
                            if os.waitpid(pid, os.WNOHANG)[0]:
                                retiring.remove(pid)
                        if prepared is not None and (dropped or chord.since != prepared[2]):
                            cancel_preparation(prepared, retiring)
                            prepared = None
                        if prepared is not None:
                            exited, status = os.waitpid(prepared[0], os.WNOHANG)
                            if exited:
                                os.close(prepared[1])
                                prepared = None
                                chord.fired = True
                                record("prepare-exited", code=os.waitstatus_to_exitcode(status))
                        if panel is not None:
                            exited, status = os.waitpid(panel, os.WNOHANG)
                            if exited:
                                record("panel-exited", code=os.waitstatus_to_exitcode(status))
                                panel = None
                        if (not dropped and not chord.fired and chord.since is not None and
                            panel is None and prepared is None and not retiring and VT.read_text().strip() == "tty1"):
                            pid, gate = start_panel()
                            prepared = (pid, gate, chord.since)
                        if not dropped and chord.ready(time.monotonic()):
                            if panel is not None:
                                request_close(panel)
                                record("close-requested")
                            elif prepared is not None:
                                pid, gate, _ = prepared
                                if (VT.read_text().strip() != "tty1" or
                                    len(held_keys(nodes)) != len(KEYS) or ending):
                                    cancel_preparation(prepared, retiring)
                                    prepared = None
                                    continue
                                prepared = None
                                trigger = time.monotonic_ns() // 1_000_000
                                try:
                                    os.write(gate, b"1")
                                except OSError as error:
                                    retiring.add(pid)
                                    if not isinstance(error, BrokenPipeError):
                                        raise
                                    record("prepare-closed")
                                else:
                                    panel = pid
                                    record("open-requested", pid=panel, trigger_monotonic_ms=trigger)
                                finally:
                                    os.close(gate)
            except OSError:
                record("retry")
                time.sleep(1)
            finally:
                if prepared is not None:
                    cancel_preparation(prepared, retiring)
                for fd in nodes:
                    os.close(fd)
    finally:
        if panel is not None:
            request_close(panel)
            retiring.add(panel)
        if retiring:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                for pid in tuple(retiring):
                    if os.waitpid(pid, os.WNOHANG)[0]:
                        retiring.remove(pid)
                if not retiring:
                    break
                time.sleep(0.05)
            else:
                record("close-pending")


if __name__ == "__main__":
    main()
