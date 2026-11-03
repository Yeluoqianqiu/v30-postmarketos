"""Session-local command broker for the V30 touch panel."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import pwd
import signal
import sqlite3
import socket
import subprocess
import sys
import time
import unicodedata
import uuid

NM = "org.freedesktop.NetworkManager"
ROOT = "/org/freedesktop/NetworkManager"
SETTINGS = NM + ".Settings"
CONNECTION = SETTINGS + ".Connection"
DEVICE = NM + ".Device"
WIFI = DEVICE + ".Wireless"
ACTIVE = NM + ".Connection.Active"
AP = NM + ".AccessPoint"
PROPS = "org.freedesktop.DBus.Properties"
PHONE = "/usr/local/sbin/v30-phone"
SMS = "/usr/local/sbin/v30-sms"
WIFI_DEVICE = "wlan0"
CELLULAR_APN = "uninet"
LIMIT = 48000
TORCH = Path("/sys/class/leds/white:flash")
BACKLIGHT = Path("/sys/class/backlight/c994000.dsi.0")
PINYIN = Path(__file__).resolve().with_name("pinyin.sqlite")


class ActionError(Exception):
    """A bounded message suitable for the panel."""


def plain(text, keep_lines=False):
    return "".join(
        char if (keep_lines and char == "\n") or not unicodedata.category(char).startswith("C") else " "
        for char in text
    )


def command(*args, timeout=5):
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=timeout, env={**os.environ, "LC_ALL": "C"}, check=True)
    except (OSError, subprocess.SubprocessError):
        raise ActionError("Device operation failed or timed out.") from None
    return plain(result.stdout.strip(), keep_lines=True)


def number(text, maximum):
    if not re.fullmatch(r"[0-9]{1,5}", text) or int(text) > maximum:
        raise ActionError("Invalid selection.")
    return int(text)


def ims_calls():
    from gi.repository import Gio
    name = "net.catcrafts.IMS1"
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
    return bus.call_sync(name, "/net/catcrafts/IMS1", name, "GetCalls", None, None,
                         Gio.DBusCallFlags.NO_AUTO_START, 5000, None).unpack()[0]


class Control:
    def __init__(self, read_only=False):
        from gi.repository import Gio, GLib
        self.gio, self.glib = Gio, GLib
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.read_only = read_only
        self.access_points = []
        self.message_ids = []
        self.missed_numbers = []
        self.input_text = None
        self.terminal = None
        self.media = None
        self.torch_until = 0

    def call(self, service, path, interface, method, signature=None, values=()):
        args = self.glib.Variant(signature, values) if signature else None
        return self.bus.call_sync(service, path, interface, method, args, None,
                                  self.gio.DBusCallFlags.NO_AUTO_START, 3000, None).unpack()

    def nm(self, path, interface, method, signature=None, values=()):
        return self.call(NM, path, interface, method, signature, values)

    def get(self, path, interface, name, service=NM):
        return self.call(service, path, PROPS, "Get", "(ss)", (interface, name))[0]

    def set(self, path, interface, name, signature, value, service=NM):
        self.call(service, path, PROPS, "Set", "(ssv)",
                  (interface, name, self.glib.Variant(signature, value)))

    def connections(self):
        for path in self.nm(ROOT + "/Settings", SETTINGS, "ListConnections")[0]:
            yield path, self.nm(path, CONNECTION, "GetSettings")[0]

    def mobile_profile(self):
        profiles = [(path, settings["connection"]) for path, settings in self.connections()
                    if settings.get("connection", {}).get("type") == "gsm" and
                    settings.get("gsm", {}).get("apn") == CELLULAR_APN]
        if len(profiles) != 1:
            raise ActionError("Expected exactly one Unicom data profile.")
        return profiles[0]

    def mobile_active(self, profile):
        return any(self.get(path, ACTIVE, "Connection") == profile and self.get(path, ACTIVE, "State") == 2
                   for path in self.get(ROOT, NM, "ActiveConnections"))

    def network_status(self):
        wifi, bt, mobile = self.network_states()
        return f"Wi-Fi: {'On' if wifi else 'Off'}    Bluetooth: {'On' if bt else 'Off'}    Mobile data: {('Off', 'On', 'Waiting')[mobile]}"

    def network_states(self):
        wifi = self.get(ROOT, NM, "WirelessEnabled")
        bt = self.get("/org/bluez/hci0", "org.bluez.Adapter1", "Powered", "org.bluez")
        profile, data = self.mobile_profile()
        mobile = 1 if self.mobile_active(profile) else 2 if data.get("autoconnect", True) else 0
        return int(wifi), int(bt), mobile

    def overview(self):
        if "/opt/v30-mobile/libexec" not in sys.path:
            sys.path.insert(0, "/opt/v30-mobile/libexec")
        from alert_view import notification_counts
        counts = notification_counts()
        from console_status import cellular_status

        def read(path):
            try:
                return Path(path).read_text().strip()
            except OSError:
                return ""

        wifi, bt, mobile = self.network_states()
        missed, sms = (min(999, value) if type(value) is int and value >= 0 else -1
                       for value in (counts.get("missed"), counts.get("sms")))
        battery = read("/sys/class/power_supply/qcom-battery/capacity")
        capacity = int(battery) if re.fullmatch(r"[0-9]{1,3}", battery) and int(battery) <= 100 else -1
        charging = int(read("/sys/class/power_supply/qcom-battery/status") == "Charging")
        cellular = cellular_status()
        signal = re.fullmatch(r"[|.]{4} ([0-9]{1,3})%", cellular.get("signal", ""))
        strength = int(signal[1]) if signal and int(signal[1]) <= 100 else -1
        technology = {"4G LTE": "4G", "3G": "3G", "2G": "2G", "5G NR": "5G",
                      "5G NR/LTE": "5G"}.get(cellular.get("network"), "")
        try:
            brightness = int((BACKLIGHT / "brightness").read_text())
            maximum = int((BACKLIGHT / "max_brightness").read_text())
            level = round(100 * brightness / maximum) if 0 <= brightness <= maximum and maximum else -1
        except (OSError, ValueError):
            level = -1
        connected = int(bool(wifi) and read("/sys/class/net/wlan0/operstate") == "up")
        try:
            torch = int(int((TORCH / "brightness").read_text()) > 0)
        except (OSError, ValueError):
            torch = -1
        return f"{wifi} {bt} {mobile} {missed} {sms} {capacity} {charging} {strength} {level} {connected} {torch}\n{technology}"

    def stop_torch(self):
        if self.torch_until:
            (TORCH / "brightness").write_text("0")
            self.torch_until = 0

    def toggle_torch(self):
        path = TORCH / "brightness"
        level = int(path.read_text())
        maximum = int((TORCH / "max_brightness").read_text())
        if not 0 <= level <= maximum or maximum < 1:
            raise ActionError("手电筒不可用。")
        if level:
            path.write_text("0")
            self.torch_until = 0
        else:
            path.write_text(str(max(1, maximum // 2)))
            self.torch_until = time.monotonic() + 60
        return self.overview()

    def set_brightness(self, percent):
        maximum = int((BACKLIGHT / "max_brightness").read_text())
        if maximum < 6:
            raise ActionError("Brightness control unavailable.")
        # Stay above this panel's verified minimum. The power key controls blanking.
        (BACKLIGHT / "brightness").write_text(str(max(6, round(maximum * percent / 100))))
        return self.overview()

    def wifi_scan(self):
        dev = self.nm(ROOT, NM, "GetDeviceByIpIface", "(s)", (WIFI_DEVICE,))[0]
        previous = self.get(dev, WIFI, "LastScan")
        try:
            self.nm(dev, WIFI, "RequestScan", "(a{sv})", ({},))
        except self.glib.Error:
            # A scan may already be running or rate-limited. Use the cache.
            pass
        else:
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and self.get(dev, WIFI, "LastScan") == previous:
                time.sleep(0.25)
        aps = self.nm(dev, WIFI, "GetAccessPoints")[0]
        active_ap = self.get(dev, WIFI, "ActiveAccessPoint")
        found = {}
        for path in aps[:96]:
            try:
                props = self.nm(path, PROPS, "GetAll", "(s)", (AP,))[0]
            except self.glib.Error:
                continue
            ssid = bytes(props.get("Ssid", []))
            if not ssid:
                continue
            flags = props.get("WpaFlags", 0) | props.get("RsnFlags", 0)
            security = ("wpa-psk" if flags & 0x100 else "sae" if flags & 0x400 else
                        "open" if not flags and not props.get("Flags", 0) & 1 else "unsupported")
            key = ssid, security
            item = (dev, path, ssid, security, props.get("Strength", 0), path == active_ap)
            if key not in found or (item[5], item[4]) > (found[key][5], found[key][4]):
                found[key] = item
        self.access_points = sorted(found.values(), key=lambda item: (item[5], item[4]), reverse=True)[:25]
        names = {"open": "Open", "wpa-psk": "WPA", "sae": "WPA3", "unsupported": "Other security"}
        return "\n".join(f"{'* ' if active else ''}{plain(ssid.decode('utf-8', 'replace'))}  [{names[security]}] {strength}%"
                         for _, _, ssid, security, strength, active in self.access_points)

    def wifi_join(self, index, password):
        if not self.access_points:
            raise ActionError("Scan and select a network first.")
        dev, ap, ssid, security, _, current = self.access_points[number(index, len(self.access_points)-1)]
        if security == "unsupported":
            raise ActionError("This network needs a separate enterprise or legacy profile.")
        if current and not password:
            return "Already connected."
        saved = [(path, data) for path, data in self.connections()
                 if bytes(data.get("802-11-wireless", {}).get("ssid", [])) == ssid and
                 data.get("802-11-wireless-security", {}).get("key-mgmt", "open") == security]
        existing = max(saved, key=lambda item: item[1]["connection"].get("timestamp", 0))[0] if saved and not password else None
        if not existing and security != "open" and not (
            re.fullmatch(r"[ -~]{8,63}", password) or security == "wpa-psk" and re.fullmatch(r"[0-9a-fA-F]{64}", password)
        ):
            raise ActionError("Enter the Wi-Fi passphrase, 8–63 printable ASCII characters.")
        if security == "open" and password:
            raise ActionError("Leave the password empty for an open network.")

        checkpoint = self.nm(ROOT, NM, "CheckpointCreate", "(aouu)", ([dev], 30, 0))[0]
        try:
            if existing:
                profile = existing
                active = self.nm(ROOT, NM, "ActivateConnection", "(ooo)", (existing, dev, ap))[0]
            else:
                variant = self.glib.Variant
                settings = {
                    "connection": {"id": variant("s", ssid.decode("utf-8", "replace")),
                                   "uuid": variant("s", str(uuid.uuid4())),
                                   "type": variant("s", "802-11-wireless")},
                    "802-11-wireless": {"ssid": variant("ay", list(ssid)),
                                        "mode": variant("s", "infrastructure")},
                }
                if security != "open":
                    settings["802-11-wireless-security"] = {
                        "key-mgmt": variant("s", security), "psk": variant("s", password)}
                profile, active, _ = self.nm(ROOT, NM, "AddAndActivateConnection2", "(a{sa{sv}}ooa{sv})",
                                              (settings, dev, ap, {"persist": variant("s", "volatile")}))
            deadline = time.monotonic() + 18
            while time.monotonic() < deadline:
                state = self.get(active, ACTIVE, "State")
                if state == 2:
                    break
                if state >= 3:
                    raise ActionError("Wi-Fi authentication or connection failed.")
                time.sleep(0.25)
            else:
                raise ActionError("Wi-Fi connection timed out.")
            if not existing:
                self.nm(profile, CONNECTION, "Save")
            self.nm(ROOT, NM, "CheckpointDestroy", "(o)", (checkpoint,))
        except (self.glib.Error, ActionError):
            try:
                self.nm(ROOT, NM, "CheckpointRollback", "(o)", (checkpoint,))
            except self.glib.Error:
                # The checkpoint has its own rollback deadline.
                pass
            raise ActionError("Wi-Fi could not connect. NetworkManager will restore the previous state.") from None
        return f"Connected to {plain(ssid.decode('utf-8', 'replace'))}."

    def mobile_data(self, enabled):
        profile, data = self.mobile_profile()
        connection = data["uuid"]
        was_auto = data.get("autoconnect", True)
        was_active = self.mobile_active(profile)
        prefix = ("nmcli", "--wait", "15", "connection")
        if enabled:
            if not was_active:
                command(*prefix, "up", "uuid", connection, timeout=18)
            try:
                command(*prefix, "modify", "uuid", connection, "connection.autoconnect", "yes", timeout=5)
            except ActionError:
                if not was_active and self.mobile_active(profile):
                    command(*prefix, "down", "uuid", connection, timeout=8)
                raise
        else:
            command(*prefix, "modify", "uuid", connection, "connection.autoconnect", "no", timeout=5)
            try:
                if was_active:
                    command(*prefix, "down", "uuid", connection, timeout=8)
            except ActionError:
                command(*prefix, "modify", "uuid", connection, "connection.autoconnect", "yes" if was_auto else "no", timeout=5)
                raise
        if self.mobile_active(profile) != enabled:
            raise ActionError("Mobile data has not reached the requested state.")
        return self.network_status()

    def audio_status(self, level=None):
        control = "name=Speaker Playback Volume"
        mixer = ("amixer", "-c", "LGV30")
        if level is not None:
            sys.path.insert(0, "/opt/v30-mobile/libexec")
            from alert_audio import AUDIO_LOCK, PRIORITY_LOCK, lock_file
            try:
                with lock_file(PRIORITY_LOCK) as priority, lock_file(AUDIO_LOCK) as audio:
                    fcntl.flock(priority, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    fcntl.flock(audio, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    raw = command(*mixer, "cget", control)
                    match = re.search(r"type=INTEGER,.*?min=(-?\d+),max=(-?\d+)", raw)
                    if not match:
                        raise ActionError("Speaker volume control unavailable.")
                    low, high = map(int, match.groups())
                    command(*mixer, "cset", control, str(low + round((high-low) * level/100)))
            except BlockingIOError:
                raise ActionError("Audio is in use by a call or ringtone.") from None
        sys.path.insert(0, "/opt/v30-mobile/libexec")
        from console_status import speaker_from_text
        speaker = speaker_from_text(command(*mixer, "cget", control))
        return f"Speaker: {speaker}    {command(PHONE, 'ring-volume')}"

    def handle(self, parts):
        action, *args = parts
        if self.read_only and action not in {"net.status", "overview.status", "wifi.scan", "phone.status", "phone.missed",
                                            "sms.list", "audio.status", "text"}:
            raise ActionError("This preview is read-only.")
        if self.media is not None and self.media.process is not None and not action.startswith("media."):
            raise ActionError("请先结束录音或回放。")
        if action in {"media.status", "media.record", "media.play", "media.stop"} and not args:
            if self.media is None:
                if "/opt/v30-mobile/libexec" not in sys.path:
                    sys.path.insert(0, "/opt/v30-mobile/libexec")
                import alert_audio
                from panel_media import VoiceNote
                self.media = VoiceNote(Path("/var/lib/v30-mobile/recordings"), pwd.getpwnam("v30").pw_gid, alert_audio)
            try:
                if action in {"media.record", "media.play"}:
                    self.media.start(action == "media.record")
                elif action == "media.stop":
                    self.media.stop()
                self.media.tick()
                return self.media.state()
            except (RuntimeError, subprocess.SubprocessError, OSError):
                raise ActionError("音频忙或录放音不可用。") from None
        if action == "overview.status" and not args:
            return self.overview()
        if action == "torch.toggle" and not args:
            return self.toggle_torch()
        if action == "brightness.set" and len(args) == 1:
            return self.set_brightness(number(args[0], 100))
        if action == "overview.set" and len(args) == 2 and args[0] in {"wifi.power", "bt.power", "mobile.data"} and args[1] in {"on", "off"}:
            self.handle(args)
            return self.overview()
        if action == "phone.latest" and not args:
            with contextlib.closing(sqlite3.connect("file:/var/lib/v30-mobile/calls.sqlite?mode=ro",
                                                     uri=True, timeout=0.1)) as calls:
                row = calls.execute(
                    "SELECT number FROM calls WHERE result='missed' AND unread=1 AND evidence!='test-report' "
                    "ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if row is None or not re.fullmatch(r"\+?[0-9]{3,20}", row[0]):
                raise ActionError("这条未接来电没有可回拨的号码。")
            return row[0]
        if action == "sms.latest" and not args:
            self.handle(["sms.list", "unread"])
            return self.handle(["sms.read", "0"])
        if action == "bt.devices" and not args:
            objects = self.call("org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")[0]
            devices = [interfaces["org.bluez.Device1"] for interfaces in objects.values()
                       if "org.bluez.Device1" in interfaces]
            return "\n".join(f"{plain(d.get('Alias', d.get('Address', '')))}   {'已连接' if d.get('Connected') else '已配对'}"
                             for d in devices if d.get("Paired") or d.get("Connected")) or "暂无已配对设备"
        if action == "mobile.summary" and not args:
            profile, config = self.mobile_profile()
            state = "已连接" if self.mobile_active(profile) else "等待连接" if config.get("autoconnect", True) else "关闭"
            return f"蜂窝数据   {state}\n接入点   {CELLULAR_APN}"
        if action == "net.status" and not args:
            return self.network_status()
        if action == "wifi.scan" and not args:
            return self.wifi_scan()
        if action == "wifi.join" and len(args) == 2:
            return self.wifi_join(*args)
        if action in {"wifi.power", "bt.power", "mobile.data"} and args in (["on"], ["off"]):
            enabled = args[0] == "on"
            if action == "mobile.data":
                return self.mobile_data(enabled)
            if action == "wifi.power":
                self.set(ROOT, NM, "WirelessEnabled", "b", enabled)
            else:
                self.set("/org/bluez/hci0", "org.bluez.Adapter1", "Powered", "b", enabled, "org.bluez")
            return self.network_status()
        if action == "phone.status" and not args:
            status = json.loads(command(PHONE, "status", timeout=12))
            calls = json.loads(command(PHONE, "calls", timeout=12))
            return f"IMS: {'Registered' if status.get('registered') else 'Unavailable'}    Calls: {len(calls)}"
        if action == "phone.missed" and not args:
            rows = command(PHONE, "history", "--missed", "--limit", "15").splitlines()
            self.missed_numbers = []
            entries = []
            for row in rows:
                fields = row.split()
                if len(fields) not in (4, 5) or not fields[0].isdigit():
                    continue
                stamp = fields[1]
                caller = fields[4] if len(fields) == 5 else ""
                self.missed_numbers.append(caller)
                entries.append(f"{caller or '未知号码'}   {stamp[:16].replace('T', ' ')}")
            return "\n".join(entries)
        if action == "phone.missed.select" and len(args) == 1 and self.missed_numbers:
            caller = self.missed_numbers[number(args[0], len(self.missed_numbers) - 1)]
            if not re.fullmatch(r"\+?[0-9]{3,20}", caller):
                raise ActionError("此号码无法回拨。")
            return caller
        if action == "phone.dial" and len(args) == 1 and re.fullmatch(r"\+?[0-9]{3,20}", args[0]):
            if json.loads(command(PHONE, "calls", timeout=12)):
                raise ActionError("Another call is active.")
            command(PHONE, "dial", args[0], timeout=12)
            return "Dial request accepted."
        if action == "phone.hangup" and not args:
            command(PHONE, "hangup", timeout=12)
            return "Call ended."
        if action == "sms.list" and args in ([], ["unread"]):
            flags = ("--unread",) if args else ()
            rows = command(SMS, "list", "--limit", "40", *flags).splitlines()
            self.message_ids = []
            entries = []
            for row in rows:
                fields = row.split(" ", 5)
                if len(fields) != 6 or not fields[0].isdigit():
                    continue
                self.message_ids.append(fields[0])
                stamp, sender = fields[4:]
                badge = "未读" if fields[1] in ("unread", "未读") else "发出" if fields[2] == "outgoing" else "收到"
                entries.append(f"{badge}   {sender or '未知号码'}   {stamp[:16].replace('T', ' ')}")
            return "\n".join(entries)
        if action == "sms.read" and len(args) == 1 and self.message_ids:
            index = number(args[0], len(self.message_ids)-1)
            message = command(SMS, "read", self.message_ids[index]).split("\n", 2)
            if len(message) >= 2:
                # v30-sms may use the original or the localized TTY labels.
                for prefix, delimiter in (("Number: ", " Timestamp:"), ("号码: ", " 时间:")):
                    if message[1].startswith(prefix):
                        sender, separator, stamp = message[1][len(prefix):].rpartition(delimiter)
                        if separator:
                            text = message[2] if len(message) == 3 else ""
                            return f"{sender.strip() or '未知号码'}\n{stamp.strip()}\n\n{text}"
            raise ActionError("短信内容无法读取。")
        if action == "audio.status" and not args:
            return self.audio_status()
        if action in {"speaker.set", "ring.set"} and len(args) == 1:
            level = number(args[0], 100)
            if action == "speaker.set":
                return self.audio_status(level)
            command(PHONE, "ring-volume", str(level), timeout=8)
            return self.audio_status()
        if action == "text" and len(args) == 1 and len(args[0].encode()) <= 1024:
            self.input_text = plain(args[0])
            return "Text ready. Tap Return to TTY."
        if action == "text.lookup" and len(args) == 1 and re.fullmatch(r"[a-z]{1,24}", args[0]):
            with contextlib.closing(sqlite3.connect(PINYIN.as_uri() + "?mode=ro", uri=True)) as dictionary:
                rows = dictionary.execute("SELECT word FROM words WHERE code=? ORDER BY weight DESC, word LIMIT 6", args)
                return "\n".join(word for word, in rows)
        if action == "text.paste" and len(args) == 1 and 0 < len(args[0].encode()) <= 1024:
            from tty_input import paste
            if args[0] != plain(args[0]):
                raise ActionError("只能输入单行文字。")
            if not paste(args[0]):
                raise ActionError("请先登录 TTY，并停在 v30 的 shell 提示符。")
            return "文字已送入 TTY。"
        if action.startswith("term."):
            from tty_input import KEYS, Terminal
            try:
                if action == "term.open" and not args:
                    self.terminal = Terminal()
                    return self.terminal.snapshot()
                if self.terminal is not None:
                    if action == "term.poll" and not args:
                        return self.terminal.snapshot()
                    if action == "term.key" and len(args) == 1 and args[0] in KEYS:
                        self.terminal.key(args[0])
                        return ""
                    if action == "term.input" and len(args) == 1 and 0 < len(args[0].encode()) <= 1024 and args[0] == plain(args[0]):
                        self.terminal.input(args[0])
                        return ""
            except (KeyError, OSError, ValueError, subprocess.SubprocessError):
                self.terminal = None
            raise ActionError("请先在横屏 TTY 登录 v30，再接入终端。")
        raise ActionError("Invalid panel request.")


def serve(fd, mode, text_path):
    # Load the broker's modules while the PIN page is open.
    from gi.repository import GLib
    if mode == "unlock":
        from pin_auth import unlock

    def stop(_signal, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    control = None if mode == "unlock" else Control(mode == "preview")
    with socket.socket(fileno=fd) as peer:
        serve_peer(peer, text_path, control, unlock if mode == "unlock" else None, GLib)


def serve_peer(peer, text_path, control, unlock, GLib):
    try:
        while True:
            active_media = control and control.media and control.media.process is not None
            if control and control.torch_until and time.monotonic() >= control.torch_until:
                control.stop_torch()
            peer.settimeout(0.15 if active_media else 0.5 if control and control.torch_until else None)
            try:
                packet = peer.recv(4096)
            except TimeoutError:
                if active_media:
                    control.media.tick()
                continue
            if not packet:
                break
            try:
                parts = packet.decode("utf-8").split("\t")
                if control is None:
                    if len(parts) != 2 or parts[0] != "panel.unlock":
                        raise ActionError("请先输入 6 位面板 PIN。")
                    outcome = unlock(parts[1])
                    if outcome == "wait":
                        raise ActionError("请稍等再试。")
                    if outcome != "ok":
                        raise ActionError("PIN 不正确。")
                    control = Control(False)
                    body = "认证通过"
                else:
                    if control.media:
                        control.media.tick()
                    body = control.handle(parts)
                reply = "1" + body
                if control.input_text is not None:
                    text_path.write_text(control.input_text, encoding="utf-8")
                    control.input_text = None
            except ActionError as error:
                reply = "0" + str(error)
            except (GLib.Error, ValueError, OSError, ImportError, KeyError, sqlite3.Error):
                reply = "0Device operation unavailable."
            try:
                body = reply.encode("utf-8")
                if len(body) > LIMIT:
                    body = body[:LIMIT].decode("utf-8", "ignore").encode("utf-8")
                peer.send(body)
            except BrokenPipeError:
                break

    finally:
        if control:
            try:
                if control.media:
                    control.media.stop()
            finally:
                control.stop_torch()


if __name__ == "__main__":
    serve(int(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))
