# SPDX-License-Identifier: GPL-3.0-only
"""Read-only cellular and speaker status, with safe fixed-width TTY labels."""
import re
import subprocess

MM = 'org.freedesktop.ModemManager1'
MODEM = MM + '.Modem'
GPP = MODEM + '.Modem3gpp'
UNKNOWN = {'operator': '--', 'network': '--', 'signal': '???? --', 'registered': False}


def operator_label(value, code=None):
    if not isinstance(value, str):
        return '--'
    aliases = {'\u4e2d\u56fd\u8054\u901a': 'UNICOM', '\u4e2d\u56fd\u79fb\u52a8': 'CMCC',
               '\u4e2d\u56fd\u7535\u4fe1': 'TELECOM', 'CHINA UNICOM': 'UNICOM',
               'CHN-UNICOM': 'UNICOM', 'CHINA MOBILE': 'CMCC', 'CHINA TELECOM': 'TELECOM'}
    value = aliases.get(value.strip().upper(), value)
    # Exclude tmux expansion/format characters and terminal control sequences.
    value = re.sub(r'[^A-Za-z0-9 ._+-]', '', value).strip()
    if value:
        return value[:16]
    # These are network PLMN identifiers, never subscriber/SIM identifiers.
    if isinstance(code, str) and re.fullmatch(r'[0-9]{5,6}', code):
        return {'46001': 'UNICOM', '46006': 'UNICOM', '46009': 'UNICOM',
                '46000': 'CMCC', '46002': 'CMCC', '46007': 'CMCC', '46008': 'CMCC',
                '46003': 'TELECOM', '46005': 'TELECOM', '46011': 'TELECOM'}.get(code, code)
    return '--'


def technology(mask):
    if type(mask) is not int or mask <= 0 or mask == 0xffffffff:
        return '--'
    if mask & (1 << 15):
        return '5G NR/LTE' if mask & (1 << 14) else '5G NR'
    if mask & ((1 << 14) | (1 << 16) | (1 << 17)):
        return '4G LTE'
    if mask & sum(1 << n for n in (5, 6, 7, 8, 9, 11, 12, 13)):
        return '3G'
    if mask & sum(1 << n for n in (1, 2, 3, 4, 10)):
        return '2G'
    return '--'


def signal_label(quality):
    if not isinstance(quality, (list, tuple)) or len(quality) != 2:
        return '???? --'
    value, recent = quality
    if type(value) is not int or not 0 <= value <= 100 or type(recent) is not bool:
        return '???? --'
    bars = sum(value >= threshold for threshold in (1, 25, 50, 75))
    return '|' * bars + '.' * (4-bars) + f' {value}%' + ('' if recent else ' STALE')


def cellular_from_objects(objects):
    modems = [interfaces for interfaces in objects.values() if MODEM in interfaces]
    # The profile has one modem. Do not silently choose a SIM/device if that changes.
    if len(modems) != 1:
        return dict(UNKNOWN)
    modem = modems[0].get(MODEM, {})
    gpp = modems[0].get(GPP, {})
    state, registration = modem.get('State', 0), gpp.get('RegistrationState', 0)
    if state < 8 or registration not in (1, 5):
        network = 'SEARCH' if registration == 2 else 'NO SERVICE'
        return dict(UNKNOWN, network=network)
    return {'operator': operator_label(gpp.get('OperatorName', ''), gpp.get('OperatorCode')),
            'network': technology(modem.get('AccessTechnologies')),
            'signal': signal_label(modem.get('SignalQuality')),
            'registered': True, 'roaming': registration == 5}


def cellular_status():
    try:
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        flags = Gio.DBusCallFlags.NO_AUTO_START
        owner = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', 'GetNameOwner', GLib.Variant('(s)', (MM,)),
            GLib.VariantType.new('(s)'), flags, 1000, None).unpack()[0]
        objects = bus.call_sync(owner, '/org/freedesktop/ModemManager1',
            'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects', None,
            None, flags, 1500, None).unpack()[0]
        return cellular_from_objects(objects)
    except ImportError:
        return dict(UNKNOWN)
    except (GLib.Error, OSError, ValueError, TypeError, KeyError):
        return dict(UNKNOWN)


def speaker_from_text(text):
    """Report the playback control fraction, not sound pressure or call gain."""
    bounds = re.search(r'; type=INTEGER,.*?min=(-?\d+),max=(-?\d+)', text)
    values = re.search(r': values=(-?\d+(?:,-?\d+)*)\s*$', text, re.MULTILINE)
    if not bounds or not values:
        return '--'
    low, high = map(int, bounds.groups())
    channels = list(map(int, values.group(1).split(',')))
    if high <= low or any(not low <= v <= high for v in channels):
        return '--'
    percentages = [round(100*(value-low)/(high-low)) for value in channels]
    return '/'.join(map(str, percentages)) + '%'


def speaker_status():
    try:
        result = subprocess.run(['amixer', '-c', 'LGV30', 'cget',
                                 'name=Speaker Playback Volume'],
                                capture_output=True, text=True, timeout=1)
        return speaker_from_text(result.stdout) if result.returncode == 0 else '--'
    except (OSError, subprocess.TimeoutExpired):
        return '--'


def format_rows(columns, items):
    """Pad/clip all cells before adding tmux markup; never wrap the bar."""
    columns = max(1, columns)
    margin = min(4, max(0, (columns-1)//8))
    available = max(1, columns-2*margin)
    cells = len(items)
    if available < cells + 3*(cells-1):
        text = ' '.join(f'{k} {v}'.strip() for k, v in items)[:columns]
        return text.ljust(columns), text.ljust(columns)
    width, remainder = divmod(available-3*(cells-1), cells)
    plain, styled = [], []
    for i, (label, value) in enumerate(items):
        size = width + (i < remainder)
        prefix = label+' ' if label else ''
        value = str(value)[:max(0, size-len(prefix))]
        text = (prefix+value)[:size]
        left = (size-len(text))//2
        padding = ' '*left
        tail = ' '*(size-len(text)-left)
        plain.append(padding+text+tail)
        styled.append(padding+'#[fg=white,nobold]'+prefix[:size]+
                      '#[fg=cyan,nobold]'+value+'#[fg=white,nobold]'+tail)
    return (' '*margin+' | '.join(plain)+' '*margin,
            ' '*margin+' #[fg=blue,nobold]| '.join(styled)+' '*margin)
