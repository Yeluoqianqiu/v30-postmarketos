"""Pure DRM mode selection. Import/default execution performs no device I/O."""
from collections import Counter
from dataclasses import asdict, dataclass
import json

PHSYNC, NHSYNC, PVSYNC, NVSYNC = 1, 2, 4, 8
INTERLACE, DBLSCAN, PREFERRED = 16, 32, 8
SYNC_FLAGS = PHSYNC | NHSYNC | PVSYNC | NVSYNC
# Temporary qualification policy for the unchanged r54/RBR candidate.
# This is not a measured hardware ceiling; a higher-rate candidate needs review.
MAX_WIDTH, MAX_HEIGHT = 1920, 1080


@dataclass(frozen=True)
class Mode:
    clock: int
    hdisplay: int
    hsync_start: int
    hsync_end: int
    htotal: int
    hskew: int
    vdisplay: int
    vsync_start: int
    vsync_end: int
    vtotal: int
    vscan: int
    vrefresh: int
    flags: int
    type: int
    name: str = ''

    def __post_init__(self):
        # One boundary validation, matching public drmModeModeInfo scalar widths.
        for name in ('clock', 'vrefresh', 'flags', 'type'):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 0xffffffff:
                raise ValueError('Invalid DRM uint32: ' + name)
        for name in ('hdisplay', 'hsync_start', 'hsync_end', 'htotal', 'hskew',
                     'vdisplay', 'vsync_start', 'vsync_end', 'vtotal', 'vscan'):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 0xffff:
                raise ValueError('Invalid DRM uint16: ' + name)
        if not (self.clock > 0 and 0 < self.hdisplay <= self.hsync_start < self.hsync_end <= self.htotal
                and 0 < self.vdisplay <= self.vsync_start < self.vsync_end <= self.vtotal):
            raise ValueError('Invalid DRM clock/timing order')
        if not isinstance(self.name, str) or len(self.name) > 32:
            raise ValueError('Invalid DRM mode name metadata')
        if self.vrefresh and self.vrefresh != self.calculated_hz:
            raise ValueError('DRM nominal refresh contradicts timing')

    @property
    def calculated_hz(self):
        numerator = self.clock * 1000 * (2 if self.flags & INTERLACE else 1)
        denominator = self.htotal * self.vtotal * (2 if self.flags & DBLSCAN else 1) * max(1, self.vscan)
        return (numerator + denominator // 2) // denominator

    @property
    def nominal_hz(self):
        return self.vrefresh or self.calculated_hz


def mode_from_drm(raw):
    """Copy a reader's public ModeInfo fields once; never infer timings from names."""
    fields = tuple(Mode.__dataclass_fields__)
    missing = set(fields) - {'name'} - set(raw)
    if missing:
        raise ValueError('Missing actual DRM timing fields: ' + ', '.join(sorted(missing)))
    return Mode(**{name: raw[name] for name in fields if name in raw})


def _modeline(mode):
    horizontal = '+hsync' if mode.flags & PHSYNC else '-hsync'
    vertical = '+vsync' if mode.flags & PVSYNC else '-vsync'
    return (f'{mode.clock // 1000}.{mode.clock % 1000:03d} {mode.hdisplay} {mode.hsync_start} {mode.hsync_end} {mode.htotal} '
            f'{mode.vdisplay} {mode.vsync_start} {mode.vsync_end} {mode.vtotal} {horizontal} {vertical}')


def _rejection(mode):
    if mode.flags & (INTERLACE | DBLSCAN) or mode.vscan > 1:
        return 'interlaced-or-repeated-scan'
    if mode.hdisplay > MAX_WIDTH or mode.vdisplay > MAX_HEIGHT:
        return 'over-1920x1080'
    if not 50 <= mode.nominal_hz <= 60:
        return 'outside-nominal-50-60Hz'
    if (mode.hskew or mode.flags & ~SYNC_FLAGS
            or (mode.flags & (PHSYNC | NHSYNC)) not in (PHSYNC, NHSYNC)
            or (mode.flags & (PVSYNC | NVSYNC)) not in (PVSYNC, NVSYNC)):
        return 'not-representable-by-Weston-modeline'
    return None


def select_mode(modes):
    """1080p60 first, then largest real in-budget mode; model/vendor never enter."""
    if not modes or len(modes) > 512 or any(not isinstance(mode, Mode) for mode in modes):
        raise ValueError('Need 1..512 validated actual DRM Mode values')
    rejected = Counter(); usable = []
    for mode in modes:
        reason = _rejection(mode)
        if reason: rejected[reason] += 1
        else: usable.append(mode)
    if not usable:
        raise ValueError('No compatible progressive <=1920x1080 nominal50-60Hz mode: '
                         + json.dumps(dict(rejected), sort_keys=True))
    def rank(mode):
        return (mode.hdisplay == 1920 and mode.vdisplay == 1080 and mode.nominal_hz == 60,
                mode.hdisplay * mode.vdisplay, mode.nominal_hz,
                bool(mode.type & PREFERRED), -mode.clock, mode.hdisplay,
                mode.hsync_start, mode.hsync_end, mode.htotal, mode.vsync_start, mode.vsync_end, mode.vtotal)
    chosen = max(usable, key=rank)
    return {'mode': f'{chosen.hdisplay}x{chosen.vdisplay}@{chosen.nominal_hz}',
            'geometry': f'{chosen.hdisplay}x{chosen.vdisplay}', 'gtk_scale': 1,
            'weston_mode': _modeline(chosen), 'drm_mode': asdict(chosen),
            'selection': '1080p60' if rank(chosen)[0] else 'actual-mode-fallback',
            'policy': 'temporary-r54-rbr-qualification'}


def reader_plan():
    return {'implemented': True, 'device_io': False, 'interface': 'drm_modes.read_connector_modes',
            'policy': 'progressive <=1920x1080 nominal50-60Hz; 1080p60 first',
            'policy_is_hardware_limit': False,
            'model_allowlist': False, 'mode_timings_synthesized': False}


if __name__ == '__main__':
    print(json.dumps(reader_plan(), indent=2))
