#!/usr/bin/env python3
"""在隔离 Alpine aarch64 根中构建锁定并应用 V30 补丁的 imsd，固定 ARMv8-A 指令集。

直接复现 project.cpp 的模块/目标依赖，不替代其 Crafter lint 流程。
调用：python3 scripts/build-imsd.py sources/imsd out/imsd
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

src = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
cxx = shutil.which("clang++") or "/usr/lib/llvm23/bin/clang++"
flags = ["-std=c++26", "-stdlib=libc++", "-march=armv8-a", "-O2", "-fPIC"]
modules = {}
objects = []
commands = []


def run(args):
    commands.append([str(a) for a in args])
    print("RUN", " ".join(map(str, args)), flush=True)
    subprocess.run(args, check=True, cwd=src)


def module(name, source):
    stem = name.replace(":", "-")
    pcm = out / f"{stem}.pcm"
    obj = out / f"{stem}.o"
    deps = [f"-fmodule-file={key}={path}" for key, path in modules.items()]
    run([cxx, *flags, *deps, "--precompile", source, "-o", pcm])
    run([cxx, *flags, *deps, "-c", pcm, "-o", obj])
    modules[name] = pcm
    objects.append(obj)


module("std", "/usr/share/libc++/v1/std.cppm")
for part in ["Util", "Aka", "Ipsec", "Qmi", "Sip", "Sdp", "Messages", "Engine"]:
    module(f"Imsd:{part}", src / f"interfaces/Imsd-{part}.cppm")
module("Imsd", src / "interfaces/Imsd.cppm")
core_objects = objects[:]
tests = []
for suite in ["Util", "Aka", "Ipsec", "Qmi", "Messages", "Engine", "Sip", "Sdp"]:
    deps = [f"-fmodule-file={key}={path}" for key, path in modules.items()]
    target = out / f"test-{suite}"
    run([cxx, *flags, *deps, src / f"tests/{suite}/main.cpp", *core_objects,
         "-fuse-ld=lld", "-o", target])
    run([target])
    tests.append(suite)

gio_flags = subprocess.check_output(["pkg-config", "--cflags", "gio-2.0"], text=True).split()
gio_flags = [x for x in gio_flags if x.startswith(("-I", "-D"))]
gio_libs = subprocess.check_output(["pkg-config", "--libs", "gio-2.0"], text=True).split()
# GIO headers occur in ImsdBus's global module fragment.
saved_flags = flags[:]
flags.extend(gio_flags)
module("ImsdBus", src / "interfaces/ImsdBus.cppm")
deps = [f"-fmodule-file={key}={path}" for key, path in modules.items()]
run([cxx, *flags, *deps, src / "implementations/main.cpp", *objects,
     *gio_libs, "-lpthread", "-fuse-ld=lld", "-o", out / "imsd"])
flags = saved_flags
run([cxx, *flags, *deps, src / "implementations/pcscf.cpp", *core_objects,
     "-fuse-ld=lld", "-o", out / "imsd-pcscf"])
for product in ['media', 'dialerd', 'ofonod']:
    extra_flags = gio_flags if product != 'media' else []
    extra_libs = gio_libs if product != 'media' else ['-ldl', '-lpthread']
    objs = [out / 'std.o'] + ([out / 'ImsdBus.o'] if product == 'ofonod' else [])
    run([cxx, *flags, *extra_flags, *deps, src / f'implementations/{product}.cpp',
         *objs, *extra_libs, '-fuse-ld=lld', '-o', out / f'imsd-{product}'])
report = {
    "compiler": subprocess.check_output([cxx, "--version"], text=True),
    "flags": flags,
    "tests_passed": tests,
    "commands": commands,
    "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
               for p in [out / name for name in ["imsd", "imsd-pcscf", "imsd-media", "imsd-dialerd", "imsd-ofonod"]]},
    "note": "manual module build; Crafter lint not run; no device registration performed",
}
(out / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
