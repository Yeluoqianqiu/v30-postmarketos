#!/usr/bin/python3
"""Adjust console glyphs and rotation without changing the kernel or display mode."""
import base64,ctypes,json,os
from pathlib import Path
class Font(ctypes.Structure):
    _fields_=[('op',ctypes.c_uint),('flags',ctypes.c_uint),('width',ctypes.c_uint),('height',ctypes.c_uint),('charcount',ctypes.c_uint),('data',ctypes.c_void_p)]
lib=ctypes.CDLL(None,use_errno=True)
source=json.loads(Path('/var/lib/v30-console/font-original.json').read_text())
original=bytearray(base64.b64decode(source['bitmap']))
# Slot zero maps the nondisplayable NUL; draw U+2103 while preserving the C baseline.
assert source['width']==8 and source['height']==16 and source['charcount']==256
original[:32]=bytes(32)
fd=os.open('/dev/tty1',os.O_RDWR)
rotation=Path('/sys/class/graphics/fbcon/rotate')
# Set the font before rotating to avoid retaining stale rotated glyph caches.
rotation.write_text('0\n')
results=[]
for scale in [3,2]:
    width,height=source['width']*scale,source['height']*scale
    vpitch=height if height>32 else 32
    srcstride=(source['width']+7)//8; dststride=(width+7)//8
    data=bytearray(source['charcount']*dststride*vpitch)
    for g in range(source['charcount']):
        for y in range(source['height']):
            for x in range(source['width']):
                if original[g*srcstride*32+y*srcstride+x//8] & (0x80>>(x%8)):
                    for dy in range(scale):
                        for dx in range(scale):
                            xx=x*scale+dx
                            data[g*dststride*vpitch+(y*scale+dy)*dststride+xx//8] |= 0x80>>(xx%8)
    # Keep the 24x48 cell and height; thin each horizontal run by one rightmost pixel.
    # Preserve box-drawing joins; thin only printable ASCII and the degree symbol.
    def put(g,x,y,on=True):
        i=g*dststride*vpitch+y*dststride+x//8;bit=0x80>>(x%8)
        if on:data[i]|=bit
        else:data[i]&=255^bit
    def slim(g):
        for y in range(height):
            start=None
            for x in range(width+1):
                lit=x<width and bool(data[g*dststride*vpitch+y*dststride+x//8]&(0x80>>(x%8)))
                if lit and start is None:start=x
                if not lit and start is not None:
                    if x-start>=3:put(g,x-1,y,False)
                    start=None
    for g in [*range(33,127),248]:slim(g)
    # Reuse C from the original font at 2x width and 3x height; draw the degree ring separately.
    cscale=max(1,scale-1);offset=width-8*cscale
    for y in range(16):
        for x in range(8):
            if original[ord('C')*32+y] & (0x80>>x):
                for dy in range(scale):
                    for dx in range(cscale):put(0,offset+x*cscale+dx,y*scale+dy)
    slim(0)
    ring=[0b0011100,0b0110110,0b1100011,0b1100011,0b1100011,0b0110110,0b0011100]
    for y,bits in enumerate(ring):
        for x in range(7):
            if bits&(1<<(6-x)):put(0,x,2*scale+y)
    buf=ctypes.create_string_buffer(bytes(data))
    obj=Font(4 if height>32 else 0,0,width,height,source['charcount'],ctypes.cast(buf,ctypes.c_void_p))
    code=lib.ioctl(fd,0x4B72,ctypes.byref(obj))
    results.append({'width':width,'height':height,'returncode':code,'errno':ctypes.get_errno() if code<0 else 0})
    if code==0:break
else:
    raise RuntimeError('Console font change failed: '+repr(results))
class Pair(ctypes.Structure):
    _fields_=[('unicode',ctypes.c_ushort),('fontpos',ctypes.c_ushort)]
class Map(ctypes.Structure):
    _fields_=[('entry_ct',ctypes.c_ushort),('entries',ctypes.POINTER(Pair))]
pairs=(Pair*1)(Pair(0x2103,0));mapping=Map(1,pairs)
if lib.ioctl(fd,0x4b67,ctypes.byref(mapping))<0:
    raise OSError(ctypes.get_errno(),'Cannot map Celsius glyph')
os.write(fd,b'\x1b%G')
rotation.write_text('1\n')
os.close(fd)
print(json.dumps({'attempts':results,'rotation':rotation.read_text().strip()}))
