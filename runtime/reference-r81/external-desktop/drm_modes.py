#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""libdrm public connector ABI. Import/default CLI never opens a device."""
import ctypes
import json
import os
from pathlib import Path
import re

from mode_plan import Mode


# Public declarations in libdrm 2.4.134 xf86drmMode.h; enum values use C int.
class DrmModeModeInfo(ctypes.Structure):
    _fields_ = [('clock', ctypes.c_uint32)] + [
        (name, ctypes.c_uint16) for name in
        ('hdisplay', 'hsync_start', 'hsync_end', 'htotal', 'hskew',
         'vdisplay', 'vsync_start', 'vsync_end', 'vtotal', 'vscan')
    ] + [(name, ctypes.c_uint32) for name in ('vrefresh', 'flags', 'type')] + [
        ('name', ctypes.c_char * 32)]


class DrmModeConnector(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in
                ('connector_id', 'encoder_id', 'connector_type', 'connector_type_id')] + [
        ('connection', ctypes.c_int), ('mmWidth', ctypes.c_uint32),
        ('mmHeight', ctypes.c_uint32), ('subpixel', ctypes.c_int),
        ('count_modes', ctypes.c_int), ('modes', ctypes.POINTER(DrmModeModeInfo)),
        ('count_props', ctypes.c_int), ('props', ctypes.POINTER(ctypes.c_uint32)),
        ('prop_values', ctypes.POINTER(ctypes.c_uint64)),
        ('count_encoders', ctypes.c_int), ('encoders', ctypes.POINTER(ctypes.c_uint32))]


def bind_libdrm(library):
    if (ctypes.sizeof(ctypes.c_void_p), ctypes.sizeof(DrmModeModeInfo),
            ctypes.sizeof(DrmModeConnector)) != (8, 68, 88):
        raise RuntimeError('This reader requires the reviewed 64-bit libdrm ABI')
    library.drmModeGetConnector.argtypes = [ctypes.c_int, ctypes.c_uint32]
    library.drmModeGetConnector.restype = ctypes.POINTER(DrmModeConnector)
    library.drmModeFreeConnector.argtypes = [ctypes.POINTER(DrmModeConnector)]
    library.drmModeFreeConnector.restype = None
    return library


def read_connector_modes(connector, device_root=Path('/dev/dri'), *,
                         library=None, opener=None, closer=None):
    """Called only after a future scope authorizes GETCONNECTOR and primary close.

    No modeset, SET_MASTER, atomic ioctl, extra resource scan or application retry.
    GETCONNECTOR may probe EDID/AUX and retry internally. Even primary fd close
    can invoke lastclose/fbdev restore; this is not a side-effect-free inspection.
    """
    connector = Path(connector)
    match = re.fullmatch(r'(card[0-9]+)-DP-([1-9][0-9]*)', connector.name)
    if not match:
        raise ValueError('Need the selected cardN-DP-M sysfs connector')
    connector_id_text = (connector / 'connector_id').read_text().strip()
    if not re.fullmatch(r'[1-9][0-9]*', connector_id_text):
        raise ValueError('Invalid sysfs connector_id')
    connector_id = int(connector_id_text)
    if connector_id > 0xffffffff:
        raise ValueError('connector_id exceeds DRM uint32')
    if (connector / 'status').read_text().strip() != 'connected':
        raise RuntimeError('Selected DP connector is not connected')
    library = bind_libdrm(library if library is not None else
                          ctypes.CDLL('libdrm.so.2', use_errno=True))
    fd = (opener or os.open)(str(Path(device_root) / match[1]), os.O_RDWR | os.O_CLOEXEC)
    try:
        pointer = library.drmModeGetConnector(fd, connector_id)
        if not pointer:
            raise RuntimeError('drmModeGetConnector failed, errno=' + str(ctypes.get_errno()))
        try:
            info = pointer.contents
            if (info.connector_id != connector_id or info.connector_type != 10
                    or info.connector_type_id != int(match[2])):
                raise RuntimeError('DRM connector identity does not match the selected sysfs connector')
            if info.connection != 1:
                raise RuntimeError('Selected DRM connector is not connected')
            for count, pointers, maximum in (
                    (info.count_modes, (info.modes,), 512),
                    (info.count_props, (info.props, info.prop_values), 512),
                    (info.count_encoders, (info.encoders,), 64)):
                if not 0 <= count <= maximum or (count and not all(pointers)):
                    raise ValueError('Invalid DRM connector array count/pointer')
            if not info.count_modes:
                raise ValueError('Selected DRM connector reported no actual modes')
            # Copy scalar values into immutable Modes before freeing libdrm memory.
            return tuple(Mode(**{name: (raw.name.decode('utf-8', errors='replace')
                                       if name == 'name' else getattr(raw, name))
                                 for name in Mode.__dataclass_fields__})
                         for raw in info.modes[:info.count_modes])
        finally:
            library.drmModeFreeConnector(pointer)
    finally:
        (closer or os.close)(fd)


def reader_plan():
    return {'implemented': True, 'device_io': False, 'installed': False,
            'interface': 'libdrm.so.2 public ModeInfo/Connector, 64-bit ABI',
            'entry': 'read_connector_modes(selected_sysfs_connector)',
            'live_read_requires': 'new scope authorizing GETCONNECTOR and primary fd close',
            'probe_and_close_may_change_display_state': True,
            'model_allowlist': False, 'mode_timings_synthesized': False}


if __name__ == '__main__':
    print(json.dumps(reader_plan(), indent=2))
