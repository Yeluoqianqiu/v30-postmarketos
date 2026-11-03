"""Load the bounded LVGL coordinate profile. Coefficients use logical landscape pixels."""
import json
import math
import os
from pathlib import Path
import re
import stat

CALIBRATION = Path("/etc/v30-lvgl/touch-calibration.json")


def load_profile(path=CALIBRATION):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 4096 or info.st_mode & 0o022:
            raise ValueError("Unsafe LVGL calibration file")
        profile = json.loads(stream.read(4097))
    expected = {"schema": 1, "device": "lge,joan", "input": "stmfts",
                "logical_size": [2880, 1440], "orientation": "clockwise"}
    if not isinstance(profile, dict) or any(profile.get(key) != value for key, value in expected.items()):
        raise ValueError("Calibration geometry does not match LG V30 LVGL")
    evidence = profile.get("evidence_sha256")
    if not isinstance(evidence, str) or not re.fullmatch(r"[a-f0-9]{64}", evidence):
        raise ValueError("Calibration evidence hash missing")
    coefficients = []
    for name in ("x", "y"):
        axis = profile.get(name)
        if not isinstance(axis, dict):
            raise ValueError(f"Missing axis {name}")
        gain, offset = axis.get("gain"), axis.get("offset_px")
        if type(gain) not in (int, float) or type(offset) not in (int, float) or not (
            math.isfinite(gain) and math.isfinite(offset) and 0.95 <= gain <= 1.05 and abs(offset) <= 120
        ):
            raise ValueError(f"Out-of-range calibration on axis {name}")
        coefficients += [str(gain), str(offset)]
    return tuple(coefficients)
