#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Notify the MSM command-mode panel after X11 framebuffer damage.

The fbdev mmap path bypasses deferred write damage. Commit the existing fbdev
mode/offset after XDamage notifications; never scan/copy the framebuffer.
"""
import ctypes,fcntl,os,select,time
from pathlib import Path
x=ctypes.CDLL('libX11.so.6');damage=ctypes.CDLL('libXdamage.so.1')
x.XOpenDisplay.argtypes=[ctypes.c_char_p];x.XOpenDisplay.restype=ctypes.c_void_p
x.XDefaultRootWindow.argtypes=[ctypes.c_void_p];x.XDefaultRootWindow.restype=ctypes.c_ulong
x.XConnectionNumber.argtypes=[ctypes.c_void_p];x.XConnectionNumber.restype=ctypes.c_int
x.XPending.argtypes=[ctypes.c_void_p];x.XPending.restype=ctypes.c_int
x.XNextEvent.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
x.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int]
x.XFlush.argtypes=[ctypes.c_void_p];x.XCloseDisplay.argtypes=[ctypes.c_void_p]
damage.XDamageQueryExtension.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
damage.XDamageCreate.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int];damage.XDamageCreate.restype=ctypes.c_ulong
damage.XDamageSubtract.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong]
damage.XDamageDestroy.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
d=x.XOpenDisplay(None);assert d,'X11 connection failed'
event_base=ctypes.c_int();error_base=ctypes.c_int()
assert damage.XDamageQueryExtension(d,ctypes.byref(event_base),ctypes.byref(error_base)),'XDamage unavailable'
handle=damage.XDamageCreate(d,x.XDefaultRootWindow(d),3);x.XFlush(d)
fd=os.open('/dev/fb0',os.O_RDWR);var=bytearray(160);fcntl.ioctl(fd,0x4600,var,True)
event=(ctypes.c_long*24)()
print('XDamage framebuffer refresh active',flush=True)
while True:
 if not x.XPending(d):select.select([x.XConnectionNumber(d)],[],[],.5)
 changed=False
 while x.XPending(d):
  x.XNextEvent(d,event)
  if ctypes.cast(event,ctypes.POINTER(ctypes.c_int))[0]==event_base.value:changed=True
 if changed:
  # Allow one short batch of drawing before committing the latest pixels.
  time.sleep(.008)
  # Clear before committing so updates during the commit trigger another event.
  damage.XDamageSubtract(d,handle,0,0);x.XSync(d,False)
  if Path('/sys/class/tty/tty0/active').read_text().strip()=='tty8' and Path('/sys/class/graphics/fb0/blank').read_text().strip()=='0':
   fcntl.ioctl(fd,0x4606,var,True)
