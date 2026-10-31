# SPDX-License-Identifier: GPL-3.0-only
"""Actual Gio observer on a private bus/netns, with synthetic calls and no audio."""
from pathlib import Path
import json, os, subprocess, sys, tempfile, threading, time
from gi.repository import Gio, GLib
NAME = 'net.catcrafts.IMS1'
OBJ = '/net/catcrafts/IMS1'
assert os.environ.get('DBUS_SYSTEM_BUS_ADDRESS') == os.environ.get('DBUS_SESSION_BUS_ADDRESS')
address = os.environ['DBUS_SYSTEM_BUS_ADDRESS']
assert '/run/dbus/system_bus_socket' not in address
assert os.stat('/proc/self/ns/net').st_ino != os.stat('/proc/1/ns/net').st_ino
XML = '''<node><interface name="net.catcrafts.IMS1">
<method name="GetCalls"><arg type="aa{sv}" direction="out"/></method>
<signal name="CallAdded"><arg type="s"/><arg type="a{sv}"/></signal>
<signal name="CallStateChanged"><arg type="s"/><arg type="s"/><arg type="s"/></signal>
<signal name="CallDeleted"><arg type="s"/></signal>
</interface></node>'''
with tempfile.TemporaryDirectory(prefix='v30-incoming-bus-') as directory:
    root = Path(directory)
    calls = []; methods = []
    def callback(connection, sender, path, iface, method, args, invocation):
        methods.append(method)
        if method != 'GetCalls':
            invocation.return_dbus_error('test.Forbidden', 'read-only observer required')
            return
        values = [{k: GLib.Variant('s', v) for k, v in c.items()} for c in calls]
        invocation.return_value(GLib.Variant('(aa{sv})', (values,)))
    def connect():
        c = Gio.DBusConnection.new_for_address_sync(address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
        c.register_object(OBJ, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], callback, None, None)
        return c
    def name(c, method):
        params = GLib.Variant('(su)', (NAME, 0)) if method == 'RequestName' else GLib.Variant('(s)', (NAME,))
        return c.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
            method, params, None, Gio.DBusCallFlags.NONE, 2000, None)
    first = connect(); second = connect(); name(first, 'RequestName')
    loop = GLib.MainLoop(); thread = threading.Thread(target=loop.run, daemon=True); thread.start()
    runner = r'''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import incoming_alerts as a, alert_audio as audio
a.RUN=audio.RUN=Path(sys.argv[2]);a.RUN.mkdir(mode=0o700)
audio.AUDIO_LOCK=a.RUN/'audio.lock';audio.PRIORITY_LOCK=a.RUN/'priority.lock'
def event(kind):
    with (a.RUN/'events.jsonl').open('a') as out:out.write(json.dumps({'event':kind})+'\n')
class Worker:
    done=False
    def poll(self):return 0 if self.done else None
    def terminate(self):self.done=True;event('stop')
    def wait(self,timeout=None):return 0
def spawn(*args,**kwargs):event('ring');return Worker()
def run(args,**kwargs):event('wake' if args[-1]=='on' else 'console')
a.subprocess.Popen=spawn;a.subprocess.run=run
a.Alerts(history=a.History(a.RUN/'history/calls.sqlite')).run()
'''
    out = (root/'observer.log').open('w')
    child = subprocess.Popen([sys.executable, '-c', runner, str(Path(__file__).parent), str(root/'state')],
                             stdout=out, stderr=out)
    def state():
        try: return json.loads((root/'state/status.json').read_text())
        except (OSError, ValueError): return {}
    def display():
        try: return json.loads((root/'state/display.json').read_text())
        except (OSError, ValueError): return {}
    def events(kind):
        try: return sum(json.loads(line)['event'] == kind for line in (root/'state/events.jsonl').read_text().splitlines())
        except OSError: return 0
    def wait_for(predicate):
        end = time.monotonic()+8
        while time.monotonic() < end:
            if child.poll() is not None:
                raise AssertionError('Observer exited: '+(root/'observer.log').read_text())
            if predicate(): return
            time.sleep(.05)
        raise AssertionError('Private observer condition timeout: '+(root/'observer.log').read_text())
    def signal(c, member, value):
        c.emit_signal(None, OBJ, NAME, member, value)
    def add(c, uni):
        calls[:] = [{'uni': uni, 'state': 'incoming', 'direction': 'incoming', 'number': '+8613800000000'}]
        signal(c, 'CallAdded', GLib.Variant('(sa{sv})', (uni, {})))
    try:
        wait_for(lambda: state().get('ready'))
        # Matching interface/path from an unrelated unique sender cannot create calls.
        signal(second, 'CallAdded', GLib.Variant('(sa{sv})', ('spoof', {})))
        time.sleep(.2); assert events('ring') == 0
        add(first, 'synthetic-a')
        wait_for(lambda: events('ring') == 1 and display().get('number') == '+8613800000000')
        signal(first, 'CallAdded', GLib.Variant('(sa{sv})', ('synthetic-a', {})))
        time.sleep(.2); assert events('ring') == events('wake') == 1
        calls[0]['state'] = 'active'
        signal(first, 'CallStateChanged', GLib.Variant('(sss)', ('synthetic-a', 'active', '')))
        wait_for(lambda: events('stop') == 1 and display().get('state') == 'idle')
        add(first, 'synthetic-b'); wait_for(lambda: events('ring') == 2)
        signal(first, 'CallStateChanged', GLib.Variant('(sss)', ('synthetic-b', 'terminated', 'remote-hangup')))
        calls.clear(); signal(first, 'CallDeleted', GLib.Variant('(s)', ('synthetic-b',)))
        wait_for(lambda: events('stop') == 2 and display().get('number') == '')
        add(first, 'reused-id'); wait_for(lambda: events('ring') == 3)
        name(first, 'ReleaseName')
        wait_for(lambda: events('stop') == 3 and state().get('ready') is False)
        name(second, 'RequestName')
        wait_for(lambda: events('ring') == 4 and state().get('ready') is True)
        assert events('wake') == 4
        calls.clear(); signal(second, 'CallDeleted', GLib.Variant('(s)', ('reused-id',)))
        wait_for(lambda: events('stop') == 4)
        assert methods and set(methods) == {'GetCalls'}
        import sqlite3
        db=sqlite3.connect(root/'state/history/calls.sqlite')
        assert db.execute("SELECT result FROM calls WHERE uni='synthetic-b'").fetchone()[0]=='missed'
        assert db.execute("SELECT result FROM calls WHERE uni='synthetic-a'").fetchone()[0]=='answered'
        db.close()
        child.terminate(); assert child.wait(timeout=8) == 0
        assert display()['state'] == 'idle'
        assert (root/'observer.log').read_text() == ''
        print(json.dumps({'passed': True, 'private_bus': True, 'private_network': True,
            'Gio_signals_and_snapshots': True, 'spoof_sender_ignored': True,
            'cancel_answer_owner_restart_cleanup': True, 'number_cleared': True, 'live_history_persisted': True,
            'dial_accept_sms_calls': 0, 'real_audio_or_modem_used': False}), flush=True)
    finally:
        if child.poll() is None: child.terminate(); child.wait(timeout=10)
        out.close(); loop.quit(); thread.join(timeout=3)
        first.close_sync(None); second.close_sync(None)
