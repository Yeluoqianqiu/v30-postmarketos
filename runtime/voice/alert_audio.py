# SPDX-License-Identifier: GPL-3.0-only
"""Playback-only ringtone, crash recovery and priority handoff to call media."""
from contextlib import contextmanager
from pathlib import Path
import array, ctypes, fcntl, json, math, os, signal, stat, subprocess, sys, time, wave
from mobile_common import atomic_json
from alert_view import ring_volume

RUN = Path('/run/v30-alerts')
AUDIO_LOCK = Path('/run/v30-call-audio.lock')
PRIORITY_LOCK = Path('/run/v30-call-priority.lock')
BOOT = Path('/proc/sys/kernel/random/boot_id')
PLAYBACK = [('Speaker Playback Volume', 8),
            ('TERT_MI2S_RX Audio Mixer MultiMedia1', 0),
            ('TERT_MI2S_RX Audio Mixer MultiMedia2', 1)]


def private_directory():
    RUN.mkdir(mode=0o700, exist_ok=True)
    info = RUN.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise RuntimeError('Unsafe alert runtime directory')


def lock_file(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        os.close(fd)
        raise RuntimeError('Unsafe audio lock')
    return os.fdopen(fd, 'a')


def media_pending():
    with lock_file(PRIORITY_LOCK) as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return False
        except BlockingIOError:
            return True


def get_control(name):
    p = subprocess.run(['amixer', '-c', 'LGV30', 'cget', 'name='+name],
                       capture_output=True, text=True, check=True, timeout=2)
    return p.stdout.split('  : values=', 1)[1].splitlines()[0].strip()


def set_control(name, value):
    subprocess.run(['amixer', '-q', '-c', 'LGV30', 'cset', 'name='+name, str(value)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=2)


def recover_ring_mixer():
    """Caller must hold AUDIO_LOCK. Keep the journal if any restore fails."""
    private_directory()
    journal = RUN/'mixer.json'
    if not journal.exists() and not journal.is_symlink():
        return
    info = journal.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise RuntimeError('Unsafe ringtone recovery record')
    saved = json.loads(journal.read_text())
    names={n for n,_ in PLAYBACK}
    if saved['boot'] != BOOT.read_text().strip() or set(saved['before']) not in (names,names|{'ADC3 Volume'}):
        raise RuntimeError('Invalid ringtone recovery record')
    errors = []
    for name, _ in reversed(PLAYBACK):
        try:
            set_control(name, saved['before'][name])
            if get_control(name) != saved['before'][name]:
                raise RuntimeError('Mixer restore did not match')
        except Exception:
            errors.append(name)
    # The speaker power cycle can change the codec's cached ADC gain. Restore
    # it after the playback route is quiescent, without opening capture PCM.
    if 'ADC3 Volume' in saved['before']:
        try:
            set_control('ADC3 Volume',saved['before']['ADC3 Volume'])
            if get_control('ADC3 Volume')!=saved['before']['ADC3 Volume']:
                raise RuntimeError('ADC gain restore did not match')
        except Exception:
            errors.append('ADC3 Volume')
    if errors:
        raise RuntimeError('Ringtone mixer recovery incomplete')
    journal.unlink()


def recover_if_idle():
    """Recover a killed worker without touching a current audio owner's mixers."""
    if not (RUN/'mixer.json').exists():
        return
    with lock_file(AUDIO_LOCK) as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        recover_ring_mixer()


@contextmanager
def media_audio_lock(timeout=8):
    """Reserve priority before waiting, so ringing cannot reacquire the PCM."""
    with lock_file(PRIORITY_LOCK) as priority, lock_file(AUDIO_LOCK) as audio:
        fcntl.flock(priority, fcntl.LOCK_EX | fcntl.LOCK_NB)
        end = time.monotonic()+timeout
        while True:
            try:
                fcntl.flock(audio, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    raise TimeoutError('Ringtone did not release audio')
                time.sleep(.025)
        recover_ring_mixer()
        yield


def write_tone(path, volume=None):
    """Stereo 48 kHz pulses; software volume is bounded to -12 dBFS peak."""
    volume = ring_volume() if volume is None else volume
    if type(volume) is not int or not 0 <= volume <= 100:
        raise ValueError('Ringtone volume must be 0..100')
    peak = round(8192*volume/100)
    data = array.array('h')
    for i in range(96000):
        t = i/48000
        pulse = t if t < .25 else t-.4 if .4 <= t < .65 else None
        gain = min(1, pulse/.01, (.25-pulse)/.01) if pulse is not None else 0
        value = int(peak*max(0, gain)*math.sin(2*math.pi*660*t))
        data.extend((value, value))
    if sys.byteorder != 'little':
        data.byteswap()
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
        stream.writeframes(data.tobytes())
    path.chmod(0o600)


def child_death(parent):
    if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent:
        os._exit(1)


class Ringtone:
    def __init__(self):
        self.lock = None
        self.player = None
        self.journaled = False

    def start(self):
        private_directory()
        self.lock = lock_file(AUDIO_LOCK)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.lock.close(); self.lock = None
            raise
        try:
            if media_pending():
                raise BlockingIOError('Call media has priority')
            recover_ring_mixer()
            pcm = list(Path('/proc/asound/card0').glob('pcm*/sub*/status'))
            if len(pcm) != 4 or any(p.read_text().strip() != 'closed' for p in pcm):
                raise RuntimeError('Audio is already in use')
            before = {name: get_control(name) for name, _ in PLAYBACK}
            before['ADC3 Volume'] = get_control('ADC3 Volume')
            atomic_json(RUN/'mixer.json', {'boot': BOOT.read_text().strip(), 'before': before})
            self.journaled = True
            for name, value in PLAYBACK:
                set_control(name, value)
            write_tone(RUN/'ring.wav')
        except BaseException:
            self.close()
            raise

    def tick(self):
        if media_pending() or ring_volume() == 0:
            return False
        if self.player is not None and self.player.poll() is not None:
            if self.player.returncode != 0:
                raise RuntimeError('Ringtone playback failed')
            self.player = None
        if self.player is None:
            parent = os.getpid()
            self.player = subprocess.Popen(['aplay', '-q', '-D', 'hw:LGV30,1', str(RUN/'ring.wav')],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                preexec_fn=lambda: child_death(parent))
        return True

    def close(self):
        if self.lock is None:
            return
        try:
            if self.player is not None and self.player.poll() is None:
                self.player.terminate()
                try:
                    self.player.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.player.kill(); self.player.wait(timeout=1)
            if self.journaled:
                recover_ring_mixer()
                self.journaled = False
        finally:
            # If restoration failed, leave the journal for the next lock owner.
            # A second close must never retry mixer writes after releasing audio.
            self.journaled = False
            if self.lock is not None:
                self.lock.close(); self.lock = None
