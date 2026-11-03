"""Authenticated TTY launcher for the LVGL panel."""
import time

PYTHON_ENTRY_MS = time.monotonic_ns() // 1_000_000

import contextlib
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import struct
import subprocess
import sys
import tempfile

from touch_profile import load_profile

BASE = Path(__file__).resolve().parent
RUN = Path("/run/v30-panel")
DESKTOP = Path("/run/v30-desktop-r72")
ACTIVE = Path("/sys/class/tty/tty0/active")
ROTATE = Path("/sys/class/graphics/fbcon/rotate")
DISPLAY_BLANK = Path("/sys/class/graphics/fb0/blank")
DISPLAY_CONTROL = Path("/run/v30-display")
DRM = Path("/sys/class/drm")
DSI = DRM / "card0-DSI-1"
BOOT = Path("/proc/sys/kernel/random/boot_id")
KDSETMODE = 0x4B3A
KDGETMODE = 0x4B3B
VT_OPENQRY = 0x5600
VT_ACTIVATE = 0x5606
stopped = False


def interrupt(*_):
    global stopped
    stopped = True


def write_state(path, state):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state) + "\n")
    temporary.replace(path)


def start_ticks(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def wait_console(name):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if ACTIVE.read_text().strip() == name:
            return
        time.sleep(0.05)
    raise RuntimeError(f"Could not activate {name}")


def tty_value(fd, request):
    return struct.unpack("i", fcntl.ioctl(fd, request, bytes(4)))[0]


def stop_child(process, group=False):
    if process is None or process.poll() is not None:
        return
    try:
        if group:
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if group:
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=2)


def ims_idle():
    service = "net.catcrafts.IMS1"
    gdbus = ("/usr/bin/gdbus", "call", "--system")
    owner = subprocess.check_output(
        [*gdbus, "--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus",
         "--method", "org.freedesktop.DBus.GetNameOwner", service], timeout=3)
    match = re.fullmatch(rb"\('(:[0-9]+\.[0-9]+)',\)\s*", owner)
    if not match:
        raise RuntimeError("IMS D-Bus owner unavailable.")
    calls = subprocess.check_output(
        [*gdbus, "--dest", match[1].decode("ascii"), "--object-path", "/net/catcrafts/IMS1",
         "--method", service + ".GetCalls"], timeout=3)
    return calls.strip() == b"(@aa{sv} [],)"


def preflight():
    sys.path.insert(0, "/opt/v30-platform-r72")
    from install_guard import require_installation

    if require_installation()["mode"] != "installed":
        raise RuntimeError("The r73 installed system is required.")
    if ACTIVE.read_text().strip() != "tty1" or ROTATE.read_text().strip() != "1":
        raise RuntimeError("Start from the authenticated landscape TTY.")
    if Path("/run/seatd.sock").exists():
        raise RuntimeError("Close the external GUI first.")
    if not ims_idle():
        raise RuntimeError("Open the panel after the current call.")
    pcm = list(Path("/proc/asound/LGV30").glob("pcm*/sub*/status"))
    if len(pcm) != 4 or any(p.read_text().strip() != "closed" for p in pcm):
        raise RuntimeError("Audio is already in use.")
    if (DSI / "status").read_text().strip() != "connected" or (DSI / "enabled").read_text().strip() != "enabled":
        raise RuntimeError("The internal display is unavailable.")
    if any(p.parent != DSI and p.read_text().strip() != "disabled" for p in DRM.glob("card0-*/enabled")):
        raise RuntimeError("An external display is active.")
    if any(p.read_text().strip() != "disconnected" for p in DRM.glob("card0-DP-*/status")):
        raise RuntimeError("Disconnect the external display first.")
    connector = int((DSI / "connector_id").read_text())
    touch = [Path("/dev/input") / p.parent.parent.name for p in Path("/sys/class/input").glob("event*/device/name")
             if p.read_text().strip() == "stmfts"]
    if connector <= 0 or len(touch) != 1 or not touch[0].is_char_device():
        raise RuntimeError("The internal touchscreen is unavailable.")
    return connector, touch[0], pwd.getpwnam("v30")


def wake_display():
    DISPLAY_CONTROL.mkdir(mode=0o700, exist_ok=True)
    # Serialize the same wake writes with the existing power-key handler.
    subprocess.run(
        ["/bin/sh", "-ec", """
            exec 9>> "$1/control.lock"
            /usr/bin/flock -x -w 2 9
            printf 'on\\n' > "$1/requested"
            printf '0\\n' > "$2"
        """, "v30-panel-wake", DISPLAY_CONTROL, DISPLAY_BLANK],
        timeout=3, check=True,
    )


def run(args, directory):
    startup_ms = {"python_entry": PYTHON_ENTRY_MS, "run_entry": time.monotonic_ns() // 1_000_000}
    if hasattr(args, "python_loaded_ms"):
        startup_ms["python_loaded"] = args.python_loaded_ms
    coefficients = load_profile()
    connector, touch, account = preflight()
    startup_ms["preflight_done"] = time.monotonic_ns() // 1_000_000
    boot = BOOT.read_text().strip()
    wake_display()
    if DISPLAY_BLANK.read_text().strip() != "0" or ACTIVE.read_text().strip() != "tty1":
        raise RuntimeError("Display wake did not complete on tty1.")
    startup_ms["wake_done"] = time.monotonic_ns() // 1_000_000

    process = broker = None
    reason = "startup-failure"
    with contextlib.ExitStack() as resources:
        console = os.open("/dev/tty0", os.O_RDWR | os.O_NOCTTY)
        resources.callback(os.close, console)
        tty1 = os.open("/dev/tty1", os.O_RDONLY | os.O_NOCTTY)
        resources.callback(os.close, tty1)
        if tty_value(tty1, KDGETMODE) != 0 or stopped:
            raise RuntimeError("TTY is not available.")
        number = tty_value(console, VT_OPENQRY)
        if not 2 <= number <= 12:
            raise RuntimeError("No spare virtual terminal is available.")
        name = f"tty{number}"
        spare = os.open("/dev/" + name, os.O_RDWR | os.O_NOCTTY)
        resources.callback(os.close, spare)
        if tty_value(spare, KDGETMODE) != 0:
            raise RuntimeError("Spare virtual terminal is not in text mode.")
        if args.preview:
            with (BASE / "GUI.once").open("x") as once:
                json.dump({"boot_id": boot, "spare_vt": name}, once)
        control, panel = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        resources.enter_context(control)
        resources.enter_context(panel)
        log = resources.enter_context((directory / "panel.log").open("xb"))
        data = {"active": True, "boot_id": boot, "pid": os.getpid(), "start_ticks": start_ticks(os.getpid()),
                "tty": name, "preview": args.preview, "hardware_key": args.hardware_key,
                "startup_ms": startup_ms}
        write_state(RUN / "state.json", data)
        deadline = time.monotonic() + args.max_seconds if args.max_seconds else None
        try:
            mode = "unlock" if args.hardware_key else "preview" if args.preview else "normal"
            broker = subprocess.Popen([sys.executable, "-B", BASE / "control.py", str(control.fileno()),
                                       mode, directory / "text"],
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      pass_fds=(control.fileno(),), start_new_session=True)
            control.close()
            fcntl.ioctl(spare, KDSETMODE, 1)
            fcntl.ioctl(console, VT_ACTIVATE, number)
            wait_console(name)
            process = subprocess.Popen([BASE / "v30-lvgl-panel", "/dev/dri/card0", str(connector), touch,
                                        str(account.pw_uid), str(account.pw_gid), *coefficients,
                                        str(panel.fileno()), "unlock" if args.hardware_key else args.action],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, pass_fds=(panel.fileno(),))
            panel.close()
            while process.poll() is None and not stopped and (deadline is None or time.monotonic() < deadline):
                if ACTIVE.read_text().strip() != name:
                    reason = "vt-changed"
                    break
                if broker.poll() is not None:
                    reason = "control-service-exit"
                    break
                time.sleep(0.15)
            else:
                reason = "child-exit" if process.poll() is not None else "signal" if stopped else "time-limit"
        finally:
            try:
                stop_child(process)
            finally:
                try:
                    fcntl.ioctl(spare, KDSETMODE, 0)
                    fcntl.ioctl(console, VT_ACTIVATE, 1)
                    wait_console("tty1")
                    subprocess.run(["/usr/local/sbin/v30-display", "on"], timeout=5, check=True)
                finally:
                    try:
                        stop_child(broker, group=True)
                    finally:
                        (RUN / "state.json").unlink(missing_ok=True)

    log = (directory / "panel.log").read_text()
    result = {"boot_id": boot, "tty": ACTIVE.read_text().strip(), "rotation": ROTATE.read_text().strip(),
              "dsi_enabled": (DSI / "enabled").read_text().strip() == "enabled",
              "panel_ready": "panel_ready=1" in log, "stop_reason": reason, "preview": args.preview,
              "cjk_font": "panel_cjk_font=1" in log,
              "hardware_key": args.hardware_key, "authenticated": "panel_unlocked=1" in log,
              "return_button": "return_button=1" in log, "tty_flip": "tty_flip_complete" in log,
              "loaded_profile": "touch_profile " in log, "process_code": process.returncode if process else None}
    if BOOT.read_text().strip() != boot or result["tty"] != "tty1" or result["rotation"] != "1":
        raise RuntimeError("TTY restoration could not be verified.")
    write_state(RUN / "last.json", result)
    if args.preview:
        (BASE / "preview-result.json").write_text(json.dumps(result) + "\n")
        (BASE / "panel.log").write_text(log)
        print(json.dumps(result))
    if (directory / "text").is_file():
        print((directory / "text").read_text())
    return int(not result["panel_ready"] or result["process_code"] != 0 or reason == "control-service-exit")


def launch(args):
    os.umask(0o077)
    RUN.mkdir(mode=0o700, exist_ok=True)
    DESKTOP.mkdir(mode=0o755, exist_ok=True)
    with (DESKTOP / "control.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, interrupt)
        sys.path.insert(0, "/opt/v30-console-orientation")
        from panel_rotation import panel_rotation

        with panel_rotation(), tempfile.TemporaryDirectory(prefix="session-", dir=RUN) as temp:
            return run(args, Path(temp))


def start_from_key(python_loaded_ms):
    from types import SimpleNamespace

    if os.geteuid() != 0:
        raise RuntimeError("The hardware-key worker requires root.")
    return launch(SimpleNamespace(action="start", hardware_key=True, preview=False,
                                  max_seconds=None, python_loaded_ms=python_loaded_ms))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="On-demand V30 touchscreen controls")
    parser.add_argument("action", choices=("start", "input", "status", "stop"), nargs="?", default="start")
    parser.add_argument("--max-seconds", type=int, choices=range(5, 76), metavar="5..75")
    parser.add_argument("--preview", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--hardware-key", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run with sudo v30-panel")
    if args.preview and not (args.action == "start" and args.max_seconds and BASE.parent == Path("/run")):
        parser.error("Preview requires a temporary payload and bounded duration.")
    if args.hardware_key and (args.action != "start" or args.preview):
        parser.error("Hardware-key mode requires an on-demand start.")
    os.umask(0o077)
    RUN.mkdir(mode=0o700, exist_ok=True)
    state = RUN / "state.json"
    if args.action in ("status", "stop"):
        try:
            record = json.loads(state.read_text())
            live = record["boot_id"] == BOOT.read_text().strip() and start_ticks(record["pid"]) == record["start_ticks"]
        except (FileNotFoundError, ProcessLookupError):
            live = False
        if args.action == "stop":
            if live:
                os.kill(record["pid"], signal.SIGTERM)
        else:
            print(json.dumps(record if live else {"active": False}))
        return 0
    return launch(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"v30-panel: {error}", file=sys.stderr)
        raise SystemExit(1)
