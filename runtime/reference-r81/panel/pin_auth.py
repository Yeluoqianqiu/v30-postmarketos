"""Local six-digit LVGL PIN, with no changes to system authentication."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

PIN = Path("/etc/v30-lvgl/panel-pin.json")
RATE = Path("/run/v30-panel/pin-auth.json")
ROUNDS = 600_000
HELPER = Path(__file__).resolve().with_name("pin-helper")


def read_pin(path=PIN):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size > 512:
            raise ValueError("Unsafe panel PIN file")
        record = json.loads(stream.read(513))
    if not isinstance(record, dict) or record.get("schema") != 1 or record.get("algorithm") != "pbkdf2-sha256" or record.get("rounds") != ROUNDS:
        raise ValueError("Unsupported panel PIN file")
    salt, digest = record.get("salt"), record.get("digest")
    if (not isinstance(salt, str) or not re.fullmatch(r"[0-9a-f]{32}", salt) or
        not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ValueError("Invalid panel PIN file")
    return bytes.fromhex(salt), bytes.fromhex(digest)


def derive(pin, salt):
    password = pin.encode("ascii")
    try:
        result = subprocess.run([HELPER], input=password + salt, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, check=True, timeout=4).stdout
        if len(result) == 32:
            return result
    except (OSError, subprocess.SubprocessError):
        pass
    return hashlib.pbkdf2_hmac("sha256", password, salt, ROUNDS)


def unlock(pin, path=PIN, rate=RATE):
    if not re.fullmatch(r"[0-9]{6}", pin):
        return "denied"
    try:
        record = json.loads(rate.read_text())
    except FileNotFoundError:
        record = {"failures": 0, "until": 0}
    now = time.monotonic()
    if now < record["until"]:
        return "wait"
    failures = record["failures"] + 1
    temporary = rate.with_suffix(".tmp")
    temporary.write_text(json.dumps({"failures": failures if failures < 5 else 0,
                                     "until": now + (60 if failures >= 5 else 2)}) + "\n")
    temporary.replace(rate)
    salt, expected = read_pin(path)
    actual = derive(pin, salt)
    if not hmac.compare_digest(actual, expected):
        return "denied"
    rate.unlink(missing_ok=True)
    return "ok"
