"""Stage stock SLPI firmware and sensor registry in RAM after verified boot."""
from pathlib import Path
import shutil
import sys
import struct
import subprocess
import tempfile
import time

root = Path('/run/v30-console-orientation')
program = Path(__file__).resolve().parent
dt = Path('/proc/device-tree')
node = dt / 'soc@0/remoteproc@5800000'
fwparam = Path('/sys/module/firmware_class/parameters/path')
labels = Path('/dev/disk/by-partlabel')

def read(p):
    return p.read_text().strip()

def run(*args, **options):
    return subprocess.run(args, check=True, timeout=12, **options)

def collect():
    image = root / 'firmware/qcom/msm8998/joan'
    image.mkdir(parents=True, mode=0o700, exist_ok=True)
    for partition, fs, options in (('modem', 'vfat', 'ro,nosuid,nodev,noexec'),
                                    ('sns', 'ext4', 'ro,noload,nosuid,nodev,noexec')):
        with tempfile.TemporaryDirectory(dir=root) as mount:
            run('mount', '-t', fs, '-o', options, str((labels / partition).resolve()), mount)
            try:
                if partition == 'modem':
                    items = [Path(mount) / 'image' / 'slpi_v2.mdt']
                    items += [Path(mount) / 'image' / f'slpi_v2.b{i:02d}' for i in range(14)]
                    assert all(p.is_file() and 0 < p.stat().st_size <= 2**21 for p in items)
                    assert items[0].read_bytes()[:6] == b'\x7fELF\x01\x01'
                    for src in items:
                        shutil.copyfile(src, image / ('slpi' + src.suffix))
                    print('firmware_segments', len(items), flush=True)
                else:
                    reg = Path(mount) / 'cal/sns.reg'
                    assert reg.is_file() and reg.stat().st_size == 25468
                    with (root / 'registry.conf').open('wb') as output:
                        run(str(program / 'sns-reg-generator'), str(reg), stdout=output)
                    assert len((root / 'registry.conf').read_text().splitlines()) >= 100
                    print('registry_calibration_staged', flush=True)
            finally:
                run('umount', mount)


def verify_board():
    assert (dt/'model').read_bytes().rstrip(b'\0') == b'LG V30 (US998)'
    assert (node/'status').read_bytes() == b'okay\0'
    assert struct.unpack('>4I', (dt/'reserved-memory/memory@94300000/reg').read_bytes()) == (
        0, 0x96000000, 0, 0xf00000)
    assert (node/'firmware-name').read_bytes() == b'qcom/msm8998/joan/slpi.mdt\0'


def stop_registry(registry):
    if registry.poll() is None:
        registry.terminate()
        try:
            registry.wait(3)
        except subprocess.TimeoutExpired:
            registry.kill()
            registry.wait(3)


def start():
    verify_board()
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
        raise RuntimeError('Expected a private, root-owned runtime directory')
    run('unshare', '--mount', '--propagation', 'private', sys.executable, '-B', __file__, '--collect')
    slpi = [entry for entry in Path('/sys/class/remoteproc').glob('remoteproc*')
            if read(entry/'name') in ('5800000.remoteproc', 'slpi')]
    if len(slpi) != 1:
        raise RuntimeError('Expected one SLPI remoteproc instance')
    state = slpi[0]/'state'
    with (root/'registry.log').open('wb') as output:
        registry = subprocess.Popen([str(program/'sns-reg'), str(root/'registry.conf')],
                                    stdout=output, stderr=output, stdin=subprocess.DEVNULL)
    try:
        time.sleep(.3)
        if registry.poll() is not None:
            raise RuntimeError('Sensor Registry exited')
        if read(state) == 'offline':
            original = fwparam.read_bytes().removesuffix(b'\n')
            try:
                fwparam.write_text(str(root/'firmware'))
                state.write_text('start\n')
            finally:
                fwparam.write_bytes(original + b'\0')
        if read(state) != 'running':
            raise RuntimeError('SLPI failed to start')
    except BaseException:
        stop_registry(registry)
        raise
    return registry, state


if __name__ == '__main__':
    verify_board()
    assert sys.argv[1:] == ['--collect']
    collect()
