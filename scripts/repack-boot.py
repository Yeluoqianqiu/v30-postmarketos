#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Repack an owner-provided Android v0 boot image. No flashing or USB access."""
import argparse, gzip, hashlib, json, struct
from pathlib import Path

def repack(base, kernel, dtb, cmdline=None):
    if len(base)<1632 or base[:8]!=b'ANDROID!':raise ValueError('Not an Android boot image')
    ks,ka,rs,ra,ss,sa,ta,page,version,osversion=struct.unpack_from('<10I',base,8)
    if page!=4096 or version!=0 or ss!=0:raise ValueError('Only joan v0/4096 without second stage is supported')
    align=lambda n:(n+page-1)//page*page
    end=page+align(ks)+align(rs)
    if not ks or not rs or len(base)!=end:raise ValueError('Truncated image or unhandled appended payload')
    if not kernel or len(dtb)<40 or dtb[:4]!=b'\xd0\x0d\xfe\xed':raise ValueError('Missing kernel or valid FDT header')
    if struct.unpack_from('>I',dtb,4)[0]!=len(dtb):raise ValueError('DTB total size mismatch')
    raw=gzip.decompress(kernel)
    if len(raw)<64 or raw[56:60]!=b'ARM\x64':raise ValueError('Expected gzip-compressed ARM64 Image')
    if max(len(raw),struct.unpack_from('<Q',raw,16)[0])>=57147392:raise ValueError('Kernel exceeds the locally verified memory bound')
    ramdisk=base[page+align(ks):page+align(ks)+rs]
    header=bytearray(base[:page]);payload=kernel+dtb
    struct.pack_into('<I',header,8,len(payload))
    header[576:608]=hashlib.sha1(payload+struct.pack('<I',len(payload))+ramdisk+struct.pack('<I',rs)+struct.pack('<I',0)).digest()+bytes(12)
    if cmdline is not None:
        data=cmdline.strip().encode()
        if b'\0' in data or b'YOUR_' in data or len(data)>=512:raise ValueError('Use a NUL-free command line shorter than 512 bytes')
        header[64:576]=data+bytes(512-len(data));header[608:1632]=bytes(1024)
    result=bytes(header)+payload+bytes(align(len(payload))-len(payload))+ramdisk+bytes(align(rs)-rs)
    if len(result)>=40*1024*1024:raise ValueError('Image exceeds the conservative joan boot size bound')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['base','kernel','dtb','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cmdline-file',type=Path);a=p.parse_args()
    if a.output.exists():p.error('Output exists; refusing to overwrite')
    result=repack(a.base.read_bytes(),a.kernel.read_bytes(),a.dtb.read_bytes(),a.cmdline_file.read_text() if a.cmdline_file else None)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(result)
    report={'bytes':len(result),'sha256':hashlib.sha256(result).hexdigest(),'source_only_tool':True,'image_built':True,'device_booted':False,'flashed':False}
    a.output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
