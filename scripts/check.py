#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Host-only syntax, links, privacy, integrity and logic checks."""
import ast,hashlib,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SKIP={'.git','sources','out','cache','stage','__pycache__'}
files=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in SKIP for x in p.relative_to(ROOT).parts)]
fail=[]
for p in files:
    name=str(p.relative_to(ROOT))
    try:text=p.read_bytes().decode('utf-8')
    except UnicodeError:fail.append(name+': unexpected binary');continue
    if re.search(r'/(?:Users|home)/[^\s/]+',text):fail.append(name+': private host path')
    if 'BEGIN '+'OPENSSH PRIVATE KEY' in text:fail.append(name+': private key header')
    if p.suffix=='.py':
        try:ast.parse(text,filename=name)
        except SyntaxError:fail.append(name+': Python syntax')
    if p.suffix in ('.sh','.init') or p.name=='APKBUILD' or text.startswith(('#!/bin/sh','#!/sbin/openrc-run')):
        r=subprocess.run(['sh','-n',str(p)],capture_output=True,text=True)
        if r.returncode:fail.append(name+': shell syntax: '+r.stderr)
    if p.suffix=='.md':
        for target in re.findall(r'\]\(([^)\s]+)\)',text):
            if re.match(r'^[a-z]+:',target) or target.startswith('#'):continue
            if not (p.parent/target.split('#')[0]).exists():fail.append(name+': broken link '+target)
manifest=ROOT/'SHA256SUMS'
if manifest.exists():
    for line in manifest.read_text().splitlines():
        digest,name=line.split('  ',1)
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:fail.append(name+': SHA256 mismatch')
if fail:raise SystemExit('\n'.join(fail))
for args in [
 [sys.executable,'-m','unittest','discover','-s','runtime/sms','-p','test_sms.py','-v'],
 [sys.executable,'-m','unittest','discover','-s','runtime/voice','-p','test_integration.py','-v'],
 [sys.executable,'-m','unittest','discover','-s','tests','-p','test_packaging.py','-v'],
 [sys.executable,'tests/test_charge_policy.py']]:subprocess.run(args,cwd=ROOT,check=True)
print('PASS: syntax, links, private-path/binary scan, manifest and host tests')
