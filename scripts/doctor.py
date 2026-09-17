#!/usr/bin/env python3
"""Read-only dependency diagnostics, without importing official components."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bridge'))
from runtime import ROOT, KEYBOARD_PREFIX, SETTINGS_PREFIX, OPTIONS, executable, config_path

checks = {}
for name, default in [('wine','wine'),('wineserver','wineserver'),('xvfb','Xvfb'),
                      ('mingw_cc','x86_64-w64-mingw32-gcc'),('innoextract','innoextract')]:
    try: executable(name, default); checks[name] = True
    except RuntimeError: checks[name] = False
for name, path in [('fcitx_addon',ROOT/'build/fcitx/doubaoime.so'),
                   ('windows_host',ROOT/'build/keyboard-host.exe'),
                   ('keyboard_engine',KEYBOARD_PREFIX/'drive_c/DoubaoIme/versions/v0.9.0.0/rpc.dll')]:
    checks[name] = path.is_file()
optional = {
    'settings_launcher': (ROOT/'build/settings-launcher.exe').is_file(),
    'settings_mono': (SETTINGS_PREFIX/'drive_c/windows/mono/mono-2.0/lib/mono/4.5/mscorlib.dll').is_file(),
    'voice_addon': (ROOT/'build/fcitx/doubaovoice.so').is_file(),
    'pygobject': importlib.util.find_spec('gi') is not None,
    'parec': shutil.which('parec') is not None,
    'external_asr': bool(OPTIONS.get('asr_entry') and Path(OPTIONS['asr_entry']).is_file())
}
print(json.dumps({'core_ready':all(checks.values()),'core':checks,'optional':optional},indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
