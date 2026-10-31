#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Prepare pinned sources locally; never connect to a phone or run a service."""
import argparse, hashlib, json, re, shutil, subprocess, tarfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'sources.lock.json').read_text())['tested_stack']
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('component', choices=['kernel', 'imsd'])
p.add_argument('--output', type=Path, default=ROOT / 'sources')
p.add_argument('--kernel-archive', type=Path, help='Use an existing matching source archive')
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
dest = a.output / a.component
if dest.exists(): p.error('Destination exists; keep it for inspection and use another --output')
def run(args): subprocess.run([str(x) for x in args], check=True)
if a.component == 'kernel':
    recipe = ROOT / 'baseline/kernel'
    text = (recipe / 'APKBUILD').read_text()
    sums = dict((name, digest) for digest, name in re.findall(r'^([0-9a-f]{128})\s+(\S+)$', text, re.M))
    archive_name = 'linux-lge-joan-' + LOCK['kernel_base'] + '.tar.gz'
    cache = ROOT / 'cache'; cache.mkdir(exist_ok=True)
    archive = a.kernel_archive or cache / archive_name
    if not archive.exists(): run(['curl', '--fail', '--location', '--retry', '2', '--output', archive, LOCK['kernel_archive']])
    if hashlib.sha512(archive.read_bytes()).hexdigest() != sums[archive_name]: raise SystemExit('Source archive SHA512 mismatch')
    for name, digest in sums.items():
        if name != archive_name and hashlib.sha512((recipe/name).read_bytes()).hexdigest() != digest:
            raise SystemExit('Recipe input SHA512 mismatch: ' + name)
    dest.mkdir()
    with tarfile.open(archive) as t:
        for member in t:
            member.name = '/'.join(member.name.split('/')[1:])
            if member.name: t.extract(member, dest, filter='data')
    run(['git', 'init', '-q', dest])
    patches = re.findall(r'^\t(v30-[\w-]+\.patch)$', text, re.M)
    for name in patches:
        run(['git', '-C', dest, 'apply', '--check', recipe/name])
        run(['git', '-C', dest, 'apply', recipe/name])
    shutil.copyfile(recipe / 'config-lge-joan.aarch64', a.output / 'kernel.config')
else:
    run(['git', 'clone', '--no-checkout', LOCK['imsd_url'], dest])
    run(['git', '-C', dest, 'checkout', '--detach', LOCK['imsd_base']])
    patch = ROOT / 'patches/imsd/0001-v30-interop.patch'
    run(['git', '-C', dest, 'apply', '--check', patch])
    run(['git', '-C', dest, 'apply', patch])
(dest / '.v30-prepared.json').write_text(json.dumps({'component': a.component, 'base': LOCK[a.component+'_base'], 'device_action': False}, indent=2)+'\n')
print('Prepared pinned', a.component, 'source at', dest)
