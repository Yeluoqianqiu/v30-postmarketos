#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only IMS observer: wake the landscape TTY and ring; never accept calls."""
from pathlib import Path
import argparse, ctypes, fcntl, json, os, signal, sqlite3, subprocess, sys, time
from alert_audio import Ringtone, RUN, BOOT, lock_file, private_directory, recover_if_idle
from alert_view import caller_label, ring_volume
from call_history import History
from mobile_common import atomic_json, start_ticks

NAME = 'net.catcrafts.IMS1'
PATH = '/net/catcrafts/IMS1'


def ring_worker(parent, parent_start):
    stopped = False
    def stop(signum, frame):
        nonlocal stopped
        stopped = True
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    if ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise RuntimeError('Cannot bind ringtone to parent')
    if os.getppid() != parent or start_ticks(parent) != parent_start:
        raise RuntimeError('Ringtone parent changed')
    audio = Ringtone()
    try:
        audio.start()
        end = time.monotonic()+90
        while not stopped and time.monotonic() < end:
            try:
                lease = json.loads((RUN/'lease.json').read_text())
                fresh = (lease['parent'] == parent and lease['start'] == parent_start and
                         0 <= time.monotonic()-lease['updated'] < 5)
            except (OSError, ValueError, KeyError, TypeError):
                fresh = False
            if not fresh or not audio.tick():
                break
            time.sleep(.05)
    finally:
        audio.close()


class Alerts:
    def __init__(self, *, clock=time.monotonic, history=None):
        self.clock = clock
        self.boot = BOOT.read_text().strip()
        self.owner = ''
        self.current = None
        self.attempted = set()
        self.woken = set()
        self.worker = None
        self.stopping = False
        self.pending_refresh = False
        self.display_key = None
        self.history_error = False
        try:
            self.history = History() if history is None else history
        except (OSError, ValueError, sqlite3.Error):
            self.history = None; self.history_error = True

    def history_action(self, method, *args):
        if self.history is None:
            return
        try:
            getattr(self.history, method)(*args)
        except (OSError, ValueError, sqlite3.Error):
            # Storage failure must not stop ringing, display or call media.
            self.history_error = True

    def stop_ring(self):
        if self.worker is not None:
            if self.worker.poll() is None:
                self.worker.terminate()
                try:
                    self.worker.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.worker.kill(); self.worker.wait(timeout=2)
            self.worker = None

    def refresh_console(self):
        try:
            subprocess.run(['/usr/local/sbin/v30-console-metrics', '--force'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def update(self, owner, calls, record=True):
        if owner != self.owner:
            self.stop_ring()
            if self.owner and record:
                self.history_action('owner_left', self.boot+'/'+self.owner)
            self.attempted.clear(); self.woken.clear()
            self.current = None; self.owner = owner
        if owner and record:
            for call in calls:
                self.history_action('observe', self.boot+'/'+owner, call)
            self.history_action('reconcile', self.boot+'/'+owner, calls)
        # An existing active/dialing call suppresses ringing for call waiting.
        incoming = [c for c in calls if c.get('state') == 'incoming' and c.get('direction') == 'incoming'
                    and isinstance(c.get('uni'), str) and 0 < len(c['uni']) <= 256]
        other = any(c.get('state') not in ('incoming', 'terminated') for c in calls)
        selected = incoming[0] if len(incoming) == 1 and not other else None
        uni = selected['uni'] if selected else None
        if uni != self.current:
            self.stop_ring(); self.current = uni
        if uni is None:
            recover_if_idle()
        live = {c.get('uni') for c in incoming}
        self.attempted.intersection_update(live); self.woken.intersection_update(live)
        now = self.clock()
        number = caller_label(selected.get('number')) if selected else ''
        atomic_json(RUN/'display.json', {'boot': self.boot, 'updated': now,
                    'state': 'incoming' if selected else 'idle', 'number': number})
        if uni and uni not in self.woken:
            self.woken.add(uni)
            try:
                subprocess.run(['/usr/local/sbin/v30-display', 'on'], check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            except (OSError, subprocess.SubprocessError):
                pass
        display_key = (owner, uni, number)
        if display_key != self.display_key:
            self.display_key = display_key; self.refresh_console()
        atomic_json(RUN/'lease.json', {'parent': os.getpid(), 'start': start_ticks(os.getpid()), 'updated': self.clock()})
        if uni and uni not in self.attempted:
            self.attempted.add(uni)
            if ring_volume() > 0:
                self.worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--ring',
                    '--parent', str(os.getpid()), '--parent-start', start_ticks(os.getpid())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atomic_json(RUN/'status.json', {'ready': bool(owner), 'incoming': len(incoming),
            'ringing': self.worker is not None and self.worker.poll() is None, 'updated': now,
            'ring_volume': ring_volume(), 'history_ready': self.history is not None and not self.history_error})

    def refresh(self):
        from gi.repository import Gio, GLib
        try:
            result = self.connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'GetNameOwner', GLib.Variant('(s)', (NAME,)),
                GLib.VariantType.new('(s)'), Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
            owner = result.unpack()[0]
            result = self.connection.call_sync(owner, PATH, NAME, 'GetCalls', None,
                GLib.VariantType.new('(aa{sv})'), Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
            calls = result.unpack()[0]
            self.update(owner, calls)
        except GLib.Error:
            self.update('', [])
        return not self.stopping

    def queued_refresh(self):
        self.pending_refresh = False
        self.refresh()
        return False

    def event(self, connection, sender, path, iface, signal_name, params, *unused):
        from gi.repository import GLib
        if sender == 'org.freedesktop.DBus' or iface == 'org.freedesktop.DBus':
            if params.unpack()[0] != NAME:
                return
            # Withdraw old-owner data before obtaining a replacement snapshot.
            self.update('', [])
        elif sender != self.owner:
            return
        else:
            values = params.unpack(); source = self.boot+'/'+self.owner
            if signal_name == 'CallAdded':
                self.history_action('observe', source, dict(values[1], uni=values[0]))
            elif signal_name == 'CallStateChanged':
                self.history_action('state', source, values[0], values[1], values[2])
            elif signal_name == 'CallDeleted':
                self.history_action('disappeared', source, values[0])
        if not self.pending_refresh:
            self.pending_refresh = True
            GLib.idle_add(self.queued_refresh)

    def run(self):
        from gi.repository import Gio, GLib
        self.connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.loop = GLib.MainLoop()
        def stop(signum, frame):
            self.stopping = True
            self.loop.quit()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, stop)
        self.connection.signal_subscribe('org.freedesktop.DBus', 'org.freedesktop.DBus',
            'NameOwnerChanged', '/org/freedesktop/DBus', NAME, Gio.DBusSignalFlags.NONE, self.event)
        for member in ('CallAdded', 'CallStateChanged', 'CallDeleted'):
            self.connection.signal_subscribe(None, NAME, member, PATH, None, Gio.DBusSignalFlags.NONE, self.event)
        try:
            self.refresh()
            GLib.timeout_add(1000, self.refresh)
            self.loop.run()
        finally:
            self.update('', [], record=False)
            (RUN/'lease.json').unlink(missing_ok=True)
            if self.history is not None:
                self.history.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ring', action='store_true'); p.add_argument('--parent', type=int)
    p.add_argument('--parent-start'); args = p.parse_args()
    if os.geteuid() != 0:
        p.error('Run the alert service as root')
    os.umask(0o077); private_directory()
    if args.ring:
        ring_worker(args.parent, args.parent_start)
    else:
        with lock_file(RUN/'service.lock') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            Alerts().run()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # No call number, identity, URI or protocol text in persistent logs.
        print('Incoming alert stopped: '+type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
