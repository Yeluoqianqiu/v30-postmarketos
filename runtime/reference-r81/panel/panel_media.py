"""Bounded voice notes using the handset audio lock and its physical ALSA routes."""
from array import array
from contextlib import ExitStack
import fcntl
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import time
import wave

AUDIO_ROUTING = Path("/proc/device-tree/sound/audio-routing")

CAPTURE = (
    ("ADC3 Volume", 12),
    ("AMIC MUX8", "ADC3"),
    ("ADC MUX8", "AMIC"),
    ("CDC_IF TX8 MUX", "DEC8"),
    ("DEC8 Volume", 84),
    ("AIF1_CAP Mixer SLIM TX8", 1),
    ("MultiMedia1 Mixer SLIMBUS_0_TX", 1),
)
PLAYBACK = (("TERT_MI2S_RX Audio Mixer MultiMedia1", 0),
            ("TERT_MI2S_RX Audio Mixer MultiMedia2", 1))


class VoiceNote:
    def __init__(self, root, gid, audio):
        self.root = root
        self.gid = gid
        self.audio = audio
        self.resources = None
        self.process = None
        self.before = {}
        self.capture = False
        self.partial = self.final = None
        self.result = 0
        self.last_recording = None

    @staticmethod
    def microphone_ready():
        try:
            routes = AUDIO_ROUTING.read_bytes().rstrip(b"\0").split(b"\0")
        except OSError:
            return False
        return (b"MIC BIAS3", b"MCLK") in zip(routes[::2], routes[1::2])

    @staticmethod
    def duration(path):
        try:
            with wave.open(str(path), "rb") as recording:
                if recording.getparams()[:3] != (1, 2, 48000):
                    return 0
                frames = recording.getnframes()
                if not 0 < frames <= 60 * 48000:
                    return 0
                has_signal = False
                remaining = frames
                while remaining:
                    count = min(remaining, 48000)
                    data = recording.readframes(count)
                    if len(data) != count * 2:
                        return 0
                    if not has_signal:
                        samples = array("h", data)
                        has_signal = any(samples)
                    remaining -= count
                return max(1, round(1000 * frames / 48000)) if has_signal else 0
        except (wave.Error, EOFError, OSError):
            return 0

    def latest(self):
        if self.last_recording is None:
            self.last_recording = self.find_latest()
        return self.last_recording

    def find_latest(self):
        if not self.root.exists():
            return None, 0
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o027:
            raise RuntimeError("Unsafe recordings directory.")
        for path in sorted(self.root.glob("note-*.wav"), reverse=True):
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
                continue
            duration = self.duration(path)
            if duration:
                return path, duration
        return None, 0

    def state(self):
        return f"{int(self.capture and self.process is not None)} {int(not self.capture and self.process is not None)} {int(self.microphone_ready())} {self.latest()[1]} {self.result}"

    def start(self, capture):
        if self.process is not None:
            raise RuntimeError("A recording or playback is already running.")
        action = "arecord" if capture else "aplay"
        program = shutil.which(action)
        if not program:
            raise RuntimeError("ALSA tools unavailable.")
        if capture and not self.microphone_ready():
            raise RuntimeError("Microphone clock route unavailable.")
        last = self.latest()[0] if not capture else None
        if not capture and last is None:
            raise RuntimeError("There is no saved recording.")
        self.result = 0
        self.capture = capture
        self.resources = ExitStack()
        try:
            lock = self.resources.enter_context(self.audio.lock_file(self.audio.AUDIO_LOCK))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.audio.media_pending():
                raise BlockingIOError("A call has audio priority.")
            self.audio.recover_ring_mixer()
            pcm = list(Path("/proc/asound/card0").glob("pcm*/sub*/status"))
            if len(pcm) != 4 or any(path.read_text().strip() != "closed" for path in pcm):
                raise RuntimeError("Audio is busy.")
            settings = CAPTURE if capture else PLAYBACK
            self.before = {name: self.audio.get_control(name) for name, _ in settings}
            if not capture:
                self.before["ADC3 Volume"] = self.audio.get_control("ADC3 Volume")
            for name, value in settings:
                self.audio.set_control(name, value)

            if capture:
                if not self.root.exists():
                    self.root.mkdir(mode=0o750)
                    os.chown(self.root, os.geteuid(), self.gid)
                    self.root.chmod(0o750)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                name = f"note-{stamp}-{time.monotonic_ns()}.wav"
                self.final = self.root / name
                self.partial = self.root / (name + ".part")
                with self.partial.open("xb") as stream:
                    os.fchown(stream.fileno(), os.geteuid(), self.gid)
                    os.fchmod(stream.fileno(), 0o640)
                args = ["-D", "hw:LGV30,0", "-f", "S16_LE", "-r", "48000", "-c", "1",
                        "-d", "60", "-t", "wav", str(self.partial)]
            else:
                args = ["-D", "plughw:LGV30,1", str(last)]
            parent = os.getpid()
            self.process = subprocess.Popen([program, "-q", *args],
                                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, start_new_session=True,
                                             preexec_fn=lambda: self.audio.child_death(parent))
        except BaseException:
            self.stop()
            raise

    def tick(self):
        if self.process is not None and (self.process.poll() is not None or self.audio.media_pending()):
            self.stop()

    def stop(self):
        if self.resources is None:
            return
        restore_error = None
        try:
            if self.process is not None:
                interrupted = self.process.poll() is None
                if interrupted:
                    self.process.send_signal(signal.SIGINT)
                    try:
                        self.process.wait(timeout=0.6)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=0.4)
                clean = self.process.returncode == 0 or (interrupted and self.process.returncode == 1)
                if self.partial is not None:
                    duration = self.duration(self.partial) if clean else 0
                    if duration:
                        self.partial.replace(self.final)
                        self.last_recording = (self.final, duration)
                        self.result = 1
                    else:
                        self.result = 2
                elif not clean and not interrupted:
                    self.result = 3
        finally:
            try:
                for name in [*reversed([n for n in self.before if n != "ADC3 Volume"]),
                             *(["ADC3 Volume"] if "ADC3 Volume" in self.before else [])]:
                    try:
                        self.audio.set_control(name, self.before[name])
                    except (OSError, subprocess.SubprocessError) as error:
                        restore_error = error
                if self.partial is not None:
                    self.partial.unlink(missing_ok=True)
            finally:
                self.resources.close()
                self.resources = self.process = self.partial = self.final = None
                self.before = {}
        if restore_error is not None:
            raise restore_error
