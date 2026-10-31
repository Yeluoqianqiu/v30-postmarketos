# SPDX-License-Identifier: GPL-3.0-only
"""Small, bounded caller labels; never interpolate network text into tmux."""
from pathlib import Path
import json, math, re, sqlite3

CONFIG = Path('/etc/v30-incoming.json')


def ring_volume(path=None):
    path = CONFIG if path is None else Path(path)
    try:
        value = json.loads(path.read_text())['ring_volume']
        return value if type(value) is int and 0 <= value <= 100 else 0
    except FileNotFoundError:
        return 60
    except (OSError, ValueError, TypeError, KeyError):
        return 0


def notification_counts(calls='/var/lib/v30-mobile/calls.sqlite', sms='/var/lib/v30-sms/messages.sqlite'):
    def count(path, query):
        path=Path(path)
        if not path.exists():return 0
        try:
            connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.1)
            try:return connection.execute(query).fetchone()[0]
            finally:connection.close()
        except (OSError, sqlite3.Error):return None
    return {'missed':count(calls,"SELECT count(*) FROM calls WHERE result='missed' AND unread=1"),
            'sms':count(sms,"SELECT count(*) FROM messages WHERE direction='incoming' AND unread=1")}


def notification_line(counts, columns):
    if counts['missed']==0 and counts['sms']==0:return None
    def value(n):return (str(n) if n<=999 else '999+') if type(n) is int and n>=0 else '?'
    text=('MISSED '+value(counts['missed'])+'   SMS '+value(counts['sms']))[:max(1,columns-8)]
    pad=max(0,columns-len(text));left=' '*(pad//2);right=' '*(pad-pad//2)
    return left+text+right,left+'#[fg=yellow,nobold]'+text+'#[default]'+right


def caller_label(value):
    if not isinstance(value, str) or len(value) > 32:
        return 'Unknown/withheld'
    value = value.strip()
    if not re.fullmatch(r'\+?[0-9][0-9() .-]*', value) or not 3 <= sum(c.isdigit() for c in value) <= 20:
        return 'Unknown/withheld'
    return value


def incoming_line(path, boot, now, columns):
    try:
        info = json.loads(Path(path).read_text())
        updated = float(info['updated'])
        if info['boot'] != boot or not math.isfinite(updated) or not 0 <= now-updated <= 6:
            return None
        if info['state'] != 'incoming':
            return None
        label = caller_label(info.get('number'))
        text = ('INCOMING  '+label)[:max(1, columns-8)]
        pad = max(0, columns-len(text))
        return (' '*(pad//2)+text+' '*(pad-pad//2),
                ' '*(pad//2)+'#[fg=yellow,bold]'+text+'#[default]'+' '*(pad-pad//2))
    except (OSError, ValueError, TypeError, KeyError):
        return None
