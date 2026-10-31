#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Explicitly snapshot the device's own unscaled console font; no font is bundled."""
import argparse,base64,ctypes,json,os
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
if a.output.exists():p.error('Original font exists; refusing to overwrite')
class Font(ctypes.Structure):
    _fields_=[('op',ctypes.c_uint),('flags',ctypes.c_uint),('width',ctypes.c_uint),('height',ctypes.c_uint),('charcount',ctypes.c_uint),('data',ctypes.c_void_p)]
buf=ctypes.create_string_buffer(512*128*8);obj=Font(1,0,64,128,512,ctypes.cast(buf,ctypes.c_void_p))
fd=os.open('/dev/tty1',os.O_RDWR)
try:
    if ctypes.CDLL(None,use_errno=True).ioctl(fd,0x4B72,ctypes.byref(obj))<0:raise OSError(ctypes.get_errno(),'Cannot read VT font')
    if (obj.width,obj.height,obj.charcount)!=(8,16,256):raise ValueError('Capture requires original 8x16/256 font before scaling')
    value={'width':obj.width,'height':obj.height,'charcount':obj.charcount,'bitmap':base64.b64encode(buf.raw[:256*32]).decode()}
    a.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fdout=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fdout,'w') as f:json.dump(value,f)
finally:os.close(fd)
