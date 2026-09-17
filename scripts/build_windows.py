#!/usr/bin/env python3
"""Build PE helpers with a standard x86_64 MinGW-w64 toolchain."""
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from runtime import ROOT, executable

compiler = executable('mingw_cc', 'x86_64-w64-mingw32-gcc')
(ROOT / 'build').mkdir(exist_ok=True)
for source, name in [('bridge/keyboard_host.c', 'keyboard-host'),
                     ('tests/settings_ui_probe.c', 'settings-ui-probe')]:
    subprocess.run([compiler, '-O0', '-std=c11', '-nostdlib', '-fno-builtin',
        '-fno-stack-protector', '-Wl,--entry=mainCRTStartup,--subsystem=console',
        str(ROOT / source), '-lkernel32', '-luser32', '-o', str(ROOT / 'build' / (name + '.exe'))], check=True)
