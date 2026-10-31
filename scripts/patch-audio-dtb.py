#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Copy a pinned baseline DTB and add only the verified microphone MCLK routes."""
import argparse, shutil, subprocess
from pathlib import Path
OLD = ['RX_BIAS', 'MCLK', 'AMIC1', 'MIC BIAS1', 'AMIC2', 'MIC BIAS2', 'AMIC3', 'MIC BIAS3']
NEW = OLD[:2] + [s for i in range(1, 5) for s in (f'MIC BIAS{i}', 'MCLK')] + OLD[2:]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():p.error('Output exists; refusing to overwrite')
    # Keep spaces inside route names: fdtget string output is not unambiguous.
    raw=subprocess.check_output(['fdtget','-t','bx',str(a.input),'/sound','audio-routing'],text=True)
    routes=bytes(int(x,16) for x in raw.split()).rstrip(b'\0').decode().split('\0')
    if routes != OLD: p.error('Not the expected baseline route; do not patch another kernel')
    shutil.copyfile(a.input,a.output)
    subprocess.run(['fdtput','-t','s',str(a.output),'/sound','audio-routing',*NEW],check=True)
    raw=subprocess.check_output(['fdtget','-t','bx',str(a.output),'/sound','audio-routing'],text=True)
    assert bytes(int(x,16) for x in raw.split()).rstrip(b'\0').decode().split('\0') == NEW
    print('Copied DTB with microphone MCLK routes:',a.output)
if __name__=='__main__':main()
