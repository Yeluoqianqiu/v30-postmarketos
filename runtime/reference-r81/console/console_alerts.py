# SPDX-License-Identifier: GPL-3.0-only
"""TTY-only incoming notices. Read the inbox without changing read state."""
from contextlib import closing
import fcntl
import json
import os
import re
from pathlib import Path
import sqlite3
import struct
import subprocess
import time
import unicodedata

from alert_view import incoming_line

RUN = Path('/run/v30-console')
DISPLAY = Path('/run/v30-display')
ACTIVE = Path('/sys/class/tty/tty0/active')
ROTATE = Path('/sys/class/graphics/fbcon/rotate')
BLANK = Path('/sys/class/graphics/fb0/blank')
PANEL = Path('/run/v30-panel/state.json')
CALL = Path('/run/v30-alerts/display.json')
SMS = Path('/var/lib/v30-sms/messages.sqlite')
RASTER = Path('/opt/v30-mobile/libexec/sms-raster')
CURSOR = RUN / 'sms-marquee-id'
LEASE = RUN / 'sms-marquee-lease'
BOOT = Path('/proc/sys/kernel/random/boot_id')
HEIGHT, WIDTH, PITCH, GUTTER = 48, 1440, 5760, 96
BATTERY_INSET = 3
COLUMNS = {'0': 60, '1': 120, '2': 60, '3': 120}
MAX_TEXT_BYTES = 65536


def console_visible():
    return (ACTIVE.read_text().strip() == 'tty1' and BLANK.read_text().strip() == '0'
            and not PANEL.exists()
            and (DISPLAY / 'requested').read_text().strip() != 'off')


def active_lease():
    try:
        return 0 <= time.time() - LEASE.stat().st_mtime < 2
    except FileNotFoundError:
        return False


def selection(pairs, columns, boot, call=CALL):
    if active_lease():
        return (' ' * columns, ' ' * columns)
    return incoming_line(call, boot, time.monotonic(), columns) or pairs


def query(path, sql, args=()):
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.1)) as db:
        return db.execute(sql, args).fetchone()


def last_message(path):
    return query(path, 'SELECT coalesce(max(id), 0) FROM messages')[0]


def next_message(path, cursor):
    return query(path, """SELECT id, text FROM messages
        WHERE id>? AND direction='incoming' AND state='received' ORDER BY id LIMIT 1""", (cursor,))


def record_cursor(path, ident):
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as file:
        file.write(f'{ident}\n')
    temporary.replace(path)


def sanitize(text):
    # Discard terminal, bidi and zero-width controls, collapse line breaks.
    text = ''.join(' ' if unicodedata.category(char).startswith('C') else char for char in text)
    return ' '.join(text.split()) or '[SMS]'


def raster(text, renderer=RASTER):
    body = sanitize(text).encode('utf-8')
    if len(body) > MAX_TEXT_BYTES:
        body = body[:MAX_TEXT_BYTES - 3].decode('utf-8', errors='ignore').encode() + b'...'
    pixels = subprocess.check_output([renderer], input=body, stderr=subprocess.DEVNULL, timeout=5)
    width, = struct.unpack_from('<I', pixels)
    if not width or len(pixels) != 4 + width * HEIGHT:
        raise ValueError('Invalid SMS glyph strip')
    return width, memoryview(pixels)[4:]


def blank_row(columns):
    with open('/dev/vcsa1', 'rb', buffering=0) as console:
        _, width, _, _ = console.read(4)
        return width == columns and console.read(width * 2)[::2] == b' ' * columns


def check_framebuffer(fd):
    variable, fixed = bytearray(160), bytearray(80)
    fcntl.ioctl(fd, 0x4600, variable)
    fcntl.ioctl(fd, 0x4602, fixed)
    if (struct.unpack_from('20I', variable) !=
            (1440, 2880, 1440, 2880, 0, 0, 32, 0, 16, 8, 0, 8, 8, 0, 0, 8, 0, 0, 0, 0)
            or struct.unpack_from('I', fixed, 48)[0] != PITCH):
        raise RuntimeError('Unexpected framebuffer geometry')


def trim_battery():
    """Trim the colored numeric cells to the matching 42px battery caps."""
    with (DISPLAY / 'control.lock').open('a') as display:
        try:
            fcntl.flock(display, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if not console_visible() or active_lease():
            return
        angle = ROTATE.read_text().strip()
        with open('/dev/vcsa1', 'rb', buffering=0) as console:
            _, columns, _, _ = console.read(4)
            row = console.read(2 * columns)
        if COLUMNS.get(angle) != columns:
            return
        chars, attributes = row[::2], row[1::2]
        match = re.match(rb'    [0-9]{2}:[0-9]{2} \x01([0-9]{1,3}|--)\x02', chars)
        if not match:
            return
        start, end = match.span(1)
        color = attributes[start - 1]
        if (color not in (2, 6) or attributes[end] != color
                or attributes[start:end] != bytes([color << 4]) * (end - start)):
            return
        left, right = start * 24, end * 24

        def offset(x, y):
            if angle == '0':
                return y * PITCH + x * 4
            if angle == '1':
                return x * PITCH + (WIDTH - 1 - y) * 4
            if angle == '2':
                return (2879 - y) * PITCH + (WIDTH - 1 - x) * 4
            return (2879 - x) * PITCH + y * 4

        fd = os.open('/dev/fb0', os.O_RDWR | os.O_CLOEXEC)
        try:
            check_framebuffer(fd)
            fill = os.pread(fd, 3, offset(left - 1, HEIGHT // 2))
            if not any(fill):
                return
            black = b'\0' * 3
            # If tmux has not redrawn any numeric cell, the top and bottom
            # samples are already clear. Only write after a real repaint.
            if all(os.pread(fd, 3, offset(x, y)) == black
                   for x in range(left, right, 24) for y in (0, HEIGHT - 1)):
                return
            inset = BATTERY_INSET
            if angle in ('0', '2'):
                x = left if angle == '0' else right - 1
                edges = (*range(inset), *range(HEIGHT - inset, HEIGHT))
                spans = [(offset(x, y), (right - left) * 4) for y in edges]
            else:
                edges = (inset - 1, HEIGHT - 1) if angle == '1' else (0, HEIGHT - inset)
                spans = [(offset(x, y), inset * 4) for x in range(left, right) for y in edges]
            dirty = []
            for at, size in spans:
                pixels = os.pread(fd, size, at)
                colors = {pixels[i:i + 3] for i in range(0, len(pixels), 4)}
                if len(pixels) != size or colors - {black, fill}:
                    return
                if fill in colors:
                    dirty.append((at, size))
            for at, size in dirty:
                if os.pwrite(fd, bytes(size), at) != size:
                    raise OSError('Short write while trimming battery')
        finally:
            os.close(fd)


class Strip:
    """Write only the already blank physical status row, below no shell text."""

    def __init__(self):
        self.angle = None

    @staticmethod
    def region(angle):
        width = COLUMNS[angle] * 24
        window = min(width - 2 * GUTTER, 1200)
        return (width - window) // 2, window

    def paint(self, angle, rows):
        left, width = self.region(angle)
        fd = os.open('/dev/fb0', os.O_RDWR | os.O_CLOEXEC)
        try:
            check_framebuffer(fd)
            if angle in ('0', '2'):
                reverse = angle == '2'
                x = WIDTH - left - width if reverse else left
                for y, row in enumerate(rows):
                    if reverse:
                        row = b''.join(row[i:i + 4] for i in range(len(row) - 4, -1, -4))
                    offset = (2879 - y if reverse else y) * PITCH + x * 4
                    if os.pwrite(fd, row, offset) != width * 4:
                        raise OSError('Short write of SMS status row')
            else:
                reverse = angle == '3'
                for x in range(width):
                    row = b''.join(rows[y][x * 4:x * 4 + 4]
                                   for y in (range(HEIGHT) if reverse else range(HEIGHT - 1, -1, -1)))
                    offset = ((2879 - left - x) * PITCH if reverse else
                              (left + x) * PITCH + (WIDTH - HEIGHT) * 4)
                    if os.pwrite(fd, row, offset) != HEIGHT * 4:
                        raise OSError('Short write of SMS status column')
        finally:
            os.close(fd)

    def draw(self, angle, picture, phase):
        _, window = self.region(angle)
        width, mask = picture
        if width <= window:
            middle = (window - width) // 2
            travel = min(144, middle)
            x = middle + round(travel * (1 - 2 * phase))
        else:
            x = 72 - round((width - window + 144) * phase)
        src, dst = max(0, -x), max(0, x)
        length = min(width - src, window - dst)
        rows = []
        for y in range(HEIGHT):
            alpha = bytearray(window)
            if length > 0:
                start = y * width + src
                alpha[dst:dst + length] = mask[start:start + length]
            row = bytearray(window * 4)
            row[0::4] = row[1::4] = row[2::4] = alpha
            rows.append(bytes(row))
        self.angle = angle
        self.paint(angle, rows)

    def clear(self):
        angle, self.angle = self.angle, None
        if angle in COLUMNS and ROTATE.read_text().strip() == angle and blank_row(COLUMNS[angle]):
            self.paint(angle, [bytes(self.region(angle)[1] * 4)] * HEIGHT)


class Marquee:
    def __init__(self, inbox=SMS, cursor=CURSOR):
        self.inbox, self.cursor = inbox, cursor
        self.ident = None
        self.picture = None
        self.pass_number = 0
        self.progress = 0.0
        self.stamp = None
        self.last = None

    def poll(self):
        if self.last is None:
            try:
                self.last = int(self.cursor.read_text())
            except FileNotFoundError:
                self.last = last_message(self.inbox)
                record_cursor(self.cursor, self.last)
        if self.picture is None:
            item = next_message(self.inbox, self.last)
            if item is not None:
                self.ident, text = item
                self.picture = raster(text)
        return self.picture is not None

    def advance(self, now, window):
        width, _ = self.picture
        travel = min(288, window - width) if width <= window else width - window + 144
        duration = max(3.0, travel / 115 + 1.0)
        if self.stamp is not None:
            self.progress += min(.3, now - self.stamp) / duration
        self.stamp = now
        if self.progress >= 1:
            self.pass_number += 1
            self.progress = 0.0
            if self.pass_number == 3:
                record_cursor(self.cursor, self.ident)
                self.last = self.ident
                self.picture = self.ident = self.stamp = None
                self.pass_number = 0
                return None
        # Hold briefly at both ends so the first and last characters can be read.
        hold = .5 / duration
        return min(1.0, max(0.0, (self.progress - hold) / (1 - 2 * hold)))


def tick_notices(refresh, *, boot=None, inbox=SMS, cursor=CURSOR, call=CALL, stop=None):
    """Run on a separate thread so slow modem metrics never stall animation."""
    boot = boot or BOOT.read_text().strip()
    ticker, strip = Marquee(inbox, cursor), Strip()
    mode = 'normal'

    def end_sms():
        with (DISPLAY / 'control.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if console_visible():
                    strip.clear()
                else:
                    strip.angle = None
            finally:
                LEASE.unlink(missing_ok=True)
        ticker.stamp = None

    try:
        if LEASE.exists():
            strip.angle = ROTATE.read_text().strip()
            end_sms()
            refresh()
        while stop is None or not stop.is_set():
            delay = .5
            try:
                if not console_visible():
                    if mode == 'sms':
                        end_sms()
                    mode = 'hidden'
                else:
                    ringing = incoming_line(call, boot, time.monotonic(), 60)
                    if ringing:
                        if mode == 'sms':
                            end_sms()
                        if mode != ringing[0]:
                            refresh()
                            mode = ringing[0]
                    elif ticker.poll():
                        if mode != 'sms':
                            LEASE.touch(mode=0o600)
                            refresh()
                            mode = 'sms'
                        delay = .15
                        with (DISPLAY / 'control.lock').open('a') as lock:
                            fcntl.flock(lock, fcntl.LOCK_EX)
                            if console_visible():
                                LEASE.touch(mode=0o600)
                                angle = ROTATE.read_text().strip()
                                if angle in COLUMNS and blank_row(COLUMNS[angle]):
                                    phase = ticker.advance(time.monotonic(), strip.region(angle)[1])
                                    if phase is not None:
                                        strip.draw(angle, ticker.picture, phase)
                        if ticker.picture is None:
                            end_sms()
                            refresh()
                            mode = 'normal'
                    else:
                        if mode != 'normal':
                            refresh()
                            mode = 'normal'
                        trim_battery()
            except (OSError, ValueError, RuntimeError, sqlite3.Error, subprocess.SubprocessError, struct.error):
                if mode == 'sms' or LEASE.exists():
                    try:
                        end_sms()
                    except (OSError, RuntimeError):
                        pass
                mode = 'hidden'
                delay = 1.0
            if stop is None:
                time.sleep(delay)
            else:
                stop.wait(delay)
    finally:
        if mode == 'sms':
            end_sms()
            refresh()
